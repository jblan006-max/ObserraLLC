"""AI grounding / hallucination monitor.

Every AI answer can be scored against the LIVE context that produced it (faithfulness).
Hybrid detection: a cheap deterministic fact-match (numbers / control-IDs the answer cites
must exist in the live context) + an LLM "verifier" pass for nuanced claims. Warn-only:
we never block an answer, we just score it and flag unsupported claims. Results are logged to
`ai_grounding_log` for the admin monitor panel.
"""
import os
import re
import json
import asyncio
import logging
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from bson import ObjectId  # noqa: F401 - kept for parity with other CI modules

from db import db
from auth import require_roles, require_active_subscription
from emergentintegrations.llm.chat import LlmChat, UserMessage, TextDelta, StreamDone

logger = logging.getLogger("hallucination")
hallucination_router = APIRouter(prefix="/api/hallucination")

# Cheap, fast verifier so grounding never dominates cost/latency of the primary answer.
VERIFIER_MODEL = ("openai", "gpt-5.4-mini")

_LABELS = [(80, "Grounded"), (50, "Partially grounded"), (0, "Unverified")]


def _label(score):
    for th, lbl in _LABELS:
        if score >= th:
            return lbl
    return "Unverified"


# ---------------------------------------------------------------- deterministic fact match
_NUM_RE = re.compile(r"(?:\$\s?\d[\d,]*\.?\d*|\d[\d,]*\.?\d*\s?%)")
_ID_RE = re.compile(r"\b[A-Z]{2,4}-\d{1,4}\b")


def _norm_num(s):
    return s.replace(",", "").replace("$", "").replace(" ", "").rstrip("%").strip()


def _deterministic(answer, context_str):
    ctx = context_str or ""
    ctx_l = ctx.lower()
    ctx_nums = {_norm_num(x) for x in _NUM_RE.findall(ctx)}
    claims, seen = [], set()
    for m in _NUM_RE.findall(answer or ""):
        key = _norm_num(m)
        if not key or key in seen:
            continue
        seen.add(key)
        if key not in ctx_nums and not any(len(key) > 2 and key in c for c in ctx_nums):
            claims.append({"claim": f"cites the figure {m.strip()}", "status": "unsupported",
                           "note": "not found in the live context"})
    for m in set(_ID_RE.findall(answer or "")):
        if m.lower() not in ctx_l:
            claims.append({"claim": f"references {m}", "status": "unsupported",
                           "note": "identifier not in the live context"})
    return claims[:12]


# ---------------------------------------------------------------- LLM verifier
_VERIFY_SYS = (
    "You are a strict grounding auditor. You are given CONTEXT (the ONLY allowed source of truth) "
    "and an AI ANSWER. Break the answer into its distinct factual claims. For EACH claim decide: "
    "'supported' (directly backed by CONTEXT), 'unsupported' (contradicts CONTEXT or is a specific "
    "fact/number not present in CONTEXT), or 'uncertain' (generic advice, opinion, or not verifiable). "
    "Treat recommendations and hedged advice as 'uncertain', not unsupported. "
    'Return STRICT JSON only, no prose: {"score": <int 0-100>, "claims": '
    '[{"claim": "<=140 chars", "status": "supported|unsupported|uncertain", "note": "<=140 chars"}]}. '
    "score = percentage of verifiable factual claims that are supported (100 if there are no factual claims)."
)


async def _llm_verify(answer, context_str):
    answer = (answer or "").strip()
    if not answer:
        return {"score": 100, "claims": [], "ok": True}
    try:
        chat = LlmChat(
            api_key=os.environ["EMERGENT_LLM_KEY"],
            session_id=f"ground-{datetime.now(timezone.utc).timestamp()}",
            system_message=_VERIFY_SYS,
        ).with_model(*VERIFIER_MODEL)
        prompt = (f"CONTEXT (JSON, sole source of truth):\n{(context_str or '')[:12000]}\n\n"
                  f"AI ANSWER:\n{answer[:6000]}\n\nReturn the JSON now.")
        collected = []

        async def _run():
            async for ev in chat.stream_message(UserMessage(text=prompt)):
                if isinstance(ev, TextDelta):
                    collected.append(ev.content)
                elif isinstance(ev, StreamDone):
                    break

        await asyncio.wait_for(_run(), timeout=30)
        raw = "".join(collected).strip()
        js = raw[raw.find("{"): raw.rfind("}") + 1]
        data = json.loads(js)
        claims = [{"claim": str(c.get("claim", ""))[:240],
                   "status": c.get("status", "uncertain") if c.get("status") in ("supported", "unsupported", "uncertain") else "uncertain",
                   "note": str(c.get("note", ""))[:240]}
                  for c in (data.get("claims") or [])][:24]
        score = int(max(0, min(100, round(float(data.get("score", 100))))))
        return {"score": score, "claims": claims, "ok": True}
    except Exception as e:
        logger.warning(f"grounding verifier failed: {e}")
        return {"score": None, "claims": [], "ok": False}


async def ground_answer(answer, context_str, use_llm=True):
    answer = (answer or "").strip()
    det = _deterministic(answer, context_str or "")
    llm = await _llm_verify(answer, context_str or "") if (use_llm and answer) else {"score": None, "claims": [], "ok": False}

    claims = list(llm["claims"])
    existing = {c["claim"] for c in claims}
    for d in det:
        if d["claim"] not in existing:
            claims.append(d)

    if llm["ok"] and llm["score"] is not None:
        score = max(0, llm["score"] - 5 * len(det))
    else:
        score = 100 if not det else max(30, 100 - 20 * len(det))
    score = int(max(0, min(100, score)))

    flagged = [c for c in claims if c["status"] == "unsupported"]
    return {"score": score, "label": _label(score), "claims": claims[:24],
            "flagged": flagged, "flagged_count": len(flagged),
            "method": "hybrid" if llm["ok"] else "deterministic"}


async def record_grounding(org_id, surface, question, answer, result, model=None, user=None):
    try:
        await db.ai_grounding_log.insert_one({
            "org_id": org_id, "at": datetime.now(timezone.utc).isoformat(), "surface": surface,
            "model": model, "user": user, "question": (question or "")[:500], "answer": (answer or "")[:2000],
            "score": result.get("score"), "label": result.get("label"), "method": result.get("method"),
            "flagged_count": result.get("flagged_count", 0), "claims": result.get("claims", [])})
    except Exception as e:
        logger.warning(f"grounding log failed: {e}")


# ---------------------------------------------------------------- endpoints
class CheckReq(BaseModel):
    text: str
    context: str | None = None
    question: str | None = None
    surface: str | None = None
    model: str | None = None
    use_llm: bool | None = True


@hallucination_router.post("/check")
async def check(body: CheckReq, user: dict = Depends(require_active_subscription)):
    org_id = user["org_id"]
    context = body.context
    if not context:
        try:
            from ai_advisor import _build_context
            context = await _build_context(org_id)
        except Exception:
            context = ""
    result = await ground_answer(body.text, context, use_llm=bool(body.use_llm))
    await record_grounding(org_id, body.surface or "check", body.question, body.text, result,
                           model=body.model, user=user.get("email"))
    return result


@hallucination_router.get("/log")
async def log(limit: int = 50, admin: dict = Depends(require_roles("admin"))):
    limit = max(1, min(200, int(limit or 50)))
    rows = await db.ai_grounding_log.find(
        {"org_id": admin["org_id"]}, {"_id": 0, "org_id": 0}).sort("at", -1).to_list(limit)
    return {"events": rows}


@hallucination_router.get("/summary")
async def summary(days: int = 30, admin: dict = Depends(require_roles("admin"))):
    days = max(1, min(180, int(days or 30)))
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    rows = await db.ai_grounding_log.find(
        {"org_id": admin["org_id"], "at": {"$gte": since}}, {"_id": 0}).sort("at", 1).to_list(5000)
    total = len(rows)
    scored = [r["score"] for r in rows if isinstance(r.get("score"), int)]
    avg = round(sum(scored) / len(scored)) if scored else None
    flagged = sum(1 for r in rows if (r.get("flagged_count") or 0) > 0)
    by_surface, by_day, worst = {}, {}, []
    for r in rows:
        s = r.get("surface") or "other"
        bs = by_surface.setdefault(s, {"surface": s, "count": 0, "flagged": 0, "_ss": 0, "_sc": 0})
        bs["count"] += 1
        if (r.get("flagged_count") or 0) > 0:
            bs["flagged"] += 1
        if isinstance(r.get("score"), int):
            bs["_ss"] += r["score"]
            bs["_sc"] += 1
        day = (r.get("at") or "")[:10]
        bd = by_day.setdefault(day, {"date": day, "count": 0, "_ss": 0, "_sc": 0})
        bd["count"] += 1
        if isinstance(r.get("score"), int):
            bd["_ss"] += r["score"]
            bd["_sc"] += 1
        if r.get("label") == "Unverified":
            worst.append({"at": r.get("at"), "surface": s, "score": r.get("score"),
                          "question": r.get("question"), "flagged_count": r.get("flagged_count")})
    surfaces = []
    for d in by_surface.values():
        surfaces.append({"surface": d["surface"], "count": d["count"], "flagged": d["flagged"],
                         "avg_score": round(d["_ss"] / d["_sc"]) if d["_sc"] else None})
    trend = [{"date": d["date"], "count": d["count"],
              "avg_score": round(d["_ss"] / d["_sc"]) if d["_sc"] else None}
             for d in sorted(by_day.values(), key=lambda x: x["date"])]
    return {"total": total, "avg_score": avg, "flagged": flagged,
            "flagged_pct": round(100 * flagged / total) if total else 0,
            "by_surface": sorted(surfaces, key=lambda x: -x["count"]),
            "trend": trend,
            "worst": sorted(worst, key=lambda x: (x["score"] if x["score"] is not None else 0))[:10]}
