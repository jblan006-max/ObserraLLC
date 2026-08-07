import os
import io
import csv
import json
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from datetime import datetime, timezone

from db import db
from auth import get_current_user, require_active_subscription, require_roles
from bson import ObjectId
from kernel import notifications
from emergentintegrations.llm.chat import LlmChat, UserMessage, TextDelta, StreamDone

advisor_router = APIRouter(prefix="/api/advisor")

# Default routing: Claude Opus 4.8 (most advanced) for executive+operational synthesis,
# Gemini 3.1 Pro for long-context ingestion.
MODEL_ROUTES = {
    "executive": ("anthropic", "claude-opus-4-8"),
    "operational": ("anthropic", "claude-opus-4-8"),
    "ingestion": ("gemini", "gemini-3.1-pro-preview"),
}

DEEP_ANALYSIS_DIRECTIVE = (
    "\n\nDEEP ANALYSIS MODE — think in structured steps before answering. Internally: "
    "(1) gather the relevant evidence from context, (2) reason through second-order impacts and "
    "interdependencies, (3) weigh trade-offs, then produce a rigorous answer. Output ONLY the final "
    "answer using these labeled sections: **Signals** (key evidence cited by ref), **Analysis** "
    "(reasoning, second-order effects, FACT vs ESTIMATE), **Recommendation** (prioritized, with "
    "confidence). Keep it tight and board-grade. Still emit at most one ACTION line if warranted."
)


# Approx cost per 1M tokens (input, output) in USD, by provider/model.
COST_PER_MTOK = {
    "anthropic/claude-opus-4-8": (15.0, 75.0),
    "anthropic/claude-sonnet-5": (3.0, 15.0),
    "gemini/gemini-3.1-pro-preview": (1.25, 5.0),
}


def _estimate_usage(model_key: str, prompt: str, system: str, response: str):
    in_tok = (len(prompt) + len(system)) // 4
    out_tok = len(response) // 4
    rin, rout = COST_PER_MTOK.get(model_key, (5.0, 15.0))
    cost = round(in_tok / 1_000_000 * rin + out_tok / 1_000_000 * rout, 5)
    return {"input_tokens": in_tok, "output_tokens": out_tok, "total_tokens": in_tok + out_tok, "cost_usd": cost}


def _month_key():
    return datetime.now(timezone.utc).strftime("%Y-%m")


async def _org_budget(org_id: str) -> float:
    org = await db.organizations.find_one({"_id": ObjectId(org_id)})
    return float((org or {}).get("advisor_budget_usd") or 0)


async def _month_spend(org_id: str) -> float:
    mk = _month_key()
    logs = await db.advisor_logs.find(
        {"org_id": org_id, "usage": {"$exists": True}, "ts": {"$regex": f"^{mk}"}},
        {"_id": 0, "usage": 1}).to_list(2000)
    return round(sum(l["usage"]["cost_usd"] for l in logs), 4)


async def _org_settings(org_id: str) -> dict:
    return await db.organizations.find_one({"_id": ObjectId(org_id)}) or {}


async def _is_paused(org_id: str) -> bool:
    org = await _org_settings(org_id)
    budget = float(org.get("advisor_budget_usd") or 0)
    if budget <= 0 or not org.get("advisor_auto_pause"):
        return False
    return await _month_spend(org_id) >= budget


def _last_n_months(n=6):
    now = datetime.now(timezone.utc)
    y, m = now.year, now.month
    keys = []
    for _ in range(n):
        keys.append(f"{y:04d}-{m:02d}")
        m -= 1
        if m == 0:
            m = 12
            y -= 1
    return list(reversed(keys))


async def _check_budget(org_id: str):
    budget = await _org_budget(org_id)
    if budget <= 0:
        return
    spent = await _month_spend(org_id)
    pct = spent / budget * 100
    mk = _month_key()
    org = await _org_settings(org_id)
    threshold = float(org.get("advisor_alert_threshold") or 80)
    if pct >= 100:
        await notifications.create(
            org_id, "advisor_budget", "AI advisor budget exceeded",
            f"Advisor spend ${spent} has exceeded the ${budget} monthly cap.",
            ref="advisor-budget", dedupe_key=f"advisor-budget:{mk}:100")
        if org.get("advisor_auto_pause") and org.get("advisor_pause_notified") != mk:
            recips = await db.users.find(
                {"org_id": org_id, "role": {"$in": ["admin", "executive"]}}, {"_id": 0, "email": 1}).to_list(200)
            html = ("<div style=\"font:400 14px Arial;color:#1f2937;max-width:560px;margin:auto\">"
                    "<h2 style=\"color:#0f1e3d\">AI Advisor auto-paused</h2>"
                    f"<p>Advisor spend of <b>${spent}</b> has reached the <b>${budget}</b> monthly cap, "
                    "so the Obserra Advisor is paused for the rest of this month.</p>"
                    "<p>Raise or turn off the cap in the Advisor panel to resume immediately.</p>"
                    "<p style=\"font-size:11px;color:#9ca3af\">Obserra — Executive Protection &amp; Intelligence LLC</p></div>")
            for r in recips:
                await notifications.send_email(r["email"], "AI Advisor auto-paused — monthly cap reached", html)
            await db.organizations.update_one({"_id": ObjectId(org_id)}, {"$set": {"advisor_pause_notified": mk}})
    elif pct >= threshold:
        await notifications.create(
            org_id, "advisor_budget", "AI advisor budget nearing cap",
            f"Advisor spend ${spent} is {round(pct)}% of the ${budget} monthly cap (alert at {round(threshold)}%).",
            ref="advisor-budget", dedupe_key=f"advisor-budget:{mk}:{round(threshold)}")
        if org.get("advisor_alert_notified") != mk:
            recips = await db.users.find(
                {"org_id": org_id, "role": {"$in": ["admin", "executive"]}}, {"_id": 0, "email": 1}).to_list(200)
            html = ("<div style=\"font:400 14px Arial;color:#1f2937;max-width:560px;margin:auto\">"
                    "<h2 style=\"color:#0f1e3d\">AI Advisor spend alert</h2>"
                    f"<p>Advisor spend of <b>${spent}</b> is <b>{round(pct)}%</b> of the <b>${budget}</b> monthly cap "
                    f"(your alert threshold is {round(threshold)}%).</p>"
                    "<p>Review usage or adjust the cap in the Advisor panel.</p>"
                    "<p style=\"font-size:11px;color:#9ca3af\">Obserra — Executive Protection &amp; Intelligence LLC</p></div>")
            for r in recips:
                await notifications.send_email(r["email"], f"AI Advisor spend at {round(pct)}% of monthly cap", html)
            await db.organizations.update_one({"_id": ObjectId(org_id)}, {"$set": {"advisor_alert_notified": mk}})



class AdvisorQuery(BaseModel):
    message: str
    mode: str = "executive"
    session_id: str | None = None
    deep: bool = False


async def _build_context(org_id: str) -> str:
    risks = await db.risks.find({"org_id": org_id}, {"_id": 0}).to_list(50)
    health = await db.health_index.find_one({"org_id": org_id}, {"_id": 0})
    ai_systems = await db.ai_systems.find({"org_id": org_id}, {"_id": 0}).to_list(50)
    incidents = await db.ai_incidents.find({"org_id": org_id}, {"_id": 0}).to_list(50)
    ctx = {
        "enterprise_health": health,
        "risks": [{"ref": r["ref"], "title": r["title"], "residual": r["residual"],
                   "inherent": r["inherent"], "status": r["status"], "owner": r["owner"],
                   "source": r["source"], "confidence": r["confidence"], "data_type": r["data_type"],
                   "business_impact": r.get("business_impact")} for r in risks],
        "ai_systems": [{"ref": a["ref"], "name": a["name"], "status": a["status"],
                        "risk_class": a["risk_class"], "drift": a["drift"]} for a in ai_systems],
        "ai_incidents": [{"ref": i["ref"], "title": i["title"], "severity": i["severity"],
                          "status": i["status"]} for i in incidents],
    }
    return json.dumps(ctx, default=str)


SYSTEM_PROMPT = """You are the Obserra EIOS Advisor — an evidence-grounded HELPER and WORKER for enterprise cyber-risk and AI governance.
RULES:
- Ground EVERY claim in the provided ENTERPRISE CONTEXT. Cite specific refs (e.g. CR-001, AI-002) in square brackets.
- Separate FACT (connected systems), ESTIMATE (modeled), PREDICTION (forward-looking), and RECOMMENDATION.
- Attach a confidence level (High/Medium/Low) to recommendations and note data freshness when relevant.
- Executive mode: concise, business-impact framed, board-ready. Operational mode: control-level detail, remediation steps.
- Never fabricate data not present in the context. If unknown, say so.
WORKER MODE — you can execute remediation through connected integrations (Entra ID, Tenable, Defender/CASB).
When a remediation is appropriate and grounded in a cited risk, add it on its OWN final line exactly as:
ACTION: <action_id> — <short human label>
Valid action_ids ONLY: entra_enforce_pim (CR-001), entra_enforce_mfa (CR-005), tenable_patch_critical (CR-002), casb_quarantine_shadow (CR-004).
Suggest at most one ACTION per reply. Use short markdown. Prefix advice with 'RECOMMENDATION:'."""


@advisor_router.post("/chat")
async def advisor_chat(body: AdvisorQuery, user: dict = Depends(require_active_subscription)):
    org_id = user["org_id"]
    if await _is_paused(org_id):
        raise HTTPException(status_code=429, detail="Advisor paused: monthly spend cap reached. An admin can raise or turn off the cap in the advisor panel.")
    context = await _build_context(org_id)
    provider, model = MODEL_ROUTES.get(body.mode, MODEL_ROUTES["executive"])
    session_id = body.session_id or f"{org_id}-{user['id']}"

    await db.advisor_logs.insert_one({
        "org_id": org_id, "user": user["email"], "mode": body.mode, "model": f"{provider}/{model}",
        "prompt": body.message, "ts": datetime.now(timezone.utc).isoformat(),
    })

    chat = LlmChat(
        api_key=os.environ["EMERGENT_LLM_KEY"],
        session_id=session_id,
        system_message=SYSTEM_PROMPT + (DEEP_ANALYSIS_DIRECTIVE if body.deep else ""),
    ).with_model(provider, model)

    full_prompt = f"ENTERPRISE CONTEXT (JSON):\n{context}\n\nQUESTION ({body.mode} mode{', deep analysis' if body.deep else ''}): {body.message}"

    async def event_generator():
        collected = []
        try:
            async for event in chat.stream_message(UserMessage(text=full_prompt)):
                if isinstance(event, TextDelta):
                    collected.append(event.content)
                    yield f"data: {json.dumps({'delta': event.content})}\n\n"
                elif isinstance(event, StreamDone):
                    break
        except Exception as e:
            yield f"data: {json.dumps({'delta': f'[advisor error: {str(e)}]'})}\n\n"
        resp_text = "".join(collected)
        sys_msg = SYSTEM_PROMPT + (DEEP_ANALYSIS_DIRECTIVE if body.deep else "")
        usage = _estimate_usage(f"{provider}/{model}", full_prompt, sys_msg, resp_text)
        await db.advisor_logs.update_one(
            {"org_id": org_id, "user": user["email"], "prompt": body.message},
            {"$set": {"response": resp_text, "usage": usage}}, upsert=False)
        yield f"data: {json.dumps({'done': True, 'model': f'{provider}/{model}', 'usage': usage})}\n\n"
        await _check_budget(org_id)

    return StreamingResponse(event_generator(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@advisor_router.get("/logs")
async def advisor_logs(user: dict = Depends(get_current_user)):
    logs = await db.advisor_logs.find({"org_id": user["org_id"]}, {"_id": 0}).sort("ts", -1).to_list(50)
    return logs


@advisor_router.get("/usage")
async def advisor_usage(admin: dict = Depends(require_roles("admin"))):
    logs = await db.advisor_logs.find({"org_id": admin["org_id"], "usage": {"$exists": True}}, {"_id": 0}).sort("ts", -1).to_list(500)
    today = datetime.now(timezone.utc).date().isoformat()
    mk = _month_key()
    total_tokens = sum(l["usage"]["total_tokens"] for l in logs)
    total_cost = round(sum(l["usage"]["cost_usd"] for l in logs), 4)
    today_cost = round(sum(l["usage"]["cost_usd"] for l in logs if l.get("ts", "").startswith(today)), 4)
    month_cost = round(sum(l["usage"]["cost_usd"] for l in logs if l.get("ts", "").startswith(mk)), 4)
    budget = await _org_budget(admin["org_id"])
    org = await _org_settings(admin["org_id"])
    auto_pause = bool(org.get("advisor_auto_pause"))
    threshold = float(org.get("advisor_alert_threshold") or 80)
    pct = round(month_cost / budget * 100) if budget > 0 else 0
    status = "off" if budget <= 0 else ("over" if pct >= 100 else ("warning" if pct >= threshold else "ok"))
    paused = budget > 0 and auto_pause and month_cost >= budget
    recent = [{"prompt": l["prompt"][:80], "user": l["user"], "model": l.get("model"), "ts": l.get("ts"),
               "tokens": l["usage"]["total_tokens"], "cost_usd": l["usage"]["cost_usd"]} for l in logs[:20]]
    trend = [{"month": k, "cost_usd": round(sum(l["usage"]["cost_usd"] for l in logs if l.get("ts", "").startswith(k)), 4)}
             for k in _last_n_months(6)]
    bu = {}
    for l in logs:
        if l.get("ts", "").startswith(mk):
            e = bu.setdefault(l["user"], {"user": l["user"], "cost_usd": 0.0, "queries": 0})
            e["cost_usd"] += l["usage"]["cost_usd"]
            e["queries"] += 1
    by_user = sorted(({**v, "cost_usd": round(v["cost_usd"], 4)} for v in bu.values()),
                     key=lambda x: x["cost_usd"], reverse=True)
    return {"queries": len(logs), "total_tokens": total_tokens, "total_cost_usd": total_cost,
            "today_cost_usd": today_cost, "month_cost_usd": month_cost, "budget_usd": budget,
            "budget_pct": pct, "budget_status": status, "auto_pause": auto_pause, "paused": paused,
            "alert_threshold": threshold, "trend": trend, "by_user": by_user, "recent": recent}


@advisor_router.get("/usage/export")
async def advisor_usage_export(admin: dict = Depends(require_roles("admin"))):
    logs = await db.advisor_logs.find({"org_id": admin["org_id"], "usage": {"$exists": True}}, {"_id": 0}).sort("ts", -1).to_list(2000)
    mk = _month_key()
    bu = {}
    for l in logs:
        if l.get("ts", "").startswith(mk):
            e = bu.setdefault(l["user"], {"user": l["user"], "cost_usd": 0.0, "queries": 0, "tokens": 0})
            e["cost_usd"] += l["usage"]["cost_usd"]
            e["queries"] += 1
            e["tokens"] += l["usage"]["total_tokens"]
    rows = sorted(bu.values(), key=lambda x: x["cost_usd"], reverse=True)
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["Month", "Teammate", "Queries", "Tokens", "Cost (USD)"])
    for r in rows:
        w.writerow([mk, r["user"], r["queries"], r["tokens"], f"{r['cost_usd']:.4f}"])
    w.writerow([mk, "TOTAL", sum(r["queries"] for r in rows), sum(r["tokens"] for r in rows), f"{sum(r['cost_usd'] for r in rows):.4f}"])
    buf.seek(0)
    return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv",
                             headers={"Content-Disposition": f'attachment; filename="advisor-spend-{mk}.csv"'})


class BudgetBody(BaseModel):
    monthly_usd: float
    auto_pause: bool | None = None
    alert_threshold: float | None = None


@advisor_router.put("/budget")
async def set_budget(body: BudgetBody, admin: dict = Depends(require_roles("admin"))):
    val = max(0.0, round(body.monthly_usd, 2))
    update = {"advisor_budget_usd": val}
    if body.auto_pause is not None:
        update["advisor_auto_pause"] = bool(body.auto_pause)
    if body.alert_threshold is not None:
        update["advisor_alert_threshold"] = min(99.0, max(1.0, round(body.alert_threshold)))
    await db.organizations.update_one({"_id": ObjectId(admin["org_id"])},
                                      {"$set": update, "$unset": {"advisor_pause_notified": "", "advisor_alert_notified": ""}})
    return {"monthly_usd": val, "auto_pause": update.get("advisor_auto_pause"), "alert_threshold": update.get("advisor_alert_threshold")}


@advisor_router.post("/board-report")
async def board_report(user: dict = Depends(require_active_subscription)):
    return await generate_board_report(user["org_id"], by=user["email"])


async def generate_board_report(org_id: str, by: str):
    context = await _build_context(org_id)
    chat = LlmChat(
        api_key=os.environ["EMERGENT_LLM_KEY"],
        session_id=f"board-{org_id}",
        system_message="You are a chief risk officer producing a concise, board-ready enterprise risk & AI governance report. Ground every statement in the provided context and cite refs in square brackets.",
    ).with_model("anthropic", "claude-sonnet-5")
    prompt = (f"ENTERPRISE CONTEXT (JSON):\n{context}\n\n"
              "Write a board report in markdown with these sections and nothing else: "
              "## Executive Summary, ## Top Enterprise Risks, ## AI Governance Posture, "
              "## Key Recommendations, ## Decisions Required. "
              "Cite refs like [CR-001]. Separate FACT vs ESTIMATE. Keep under 380 words.")
    collected = []
    try:
        async for ev in chat.stream_message(UserMessage(text=prompt)):
            if isinstance(ev, TextDelta):
                collected.append(ev.content)
            elif isinstance(ev, StreamDone):
                break
    except Exception as e:
        collected.append(f"[report generation error: {e}]")
    report = "".join(collected)
    now = datetime.now(timezone.utc).isoformat()
    await db.reports.insert_one({"org_id": org_id, "report": report,
                                 "model": "anthropic/claude-sonnet-5", "generated_at": now, "by": by})
    return {"report": report, "model": "claude-sonnet-5", "generated_at": now}


from routes import _build_graph


class GraphAsk(BaseModel):
    question: str


@advisor_router.post("/graph-ask")
async def graph_ask(body: GraphAsk, user: dict = Depends(require_active_subscription)):
    g = await _build_graph(user["org_id"])
    q = body.question.lower()
    highlight = set()
    for n in g["nodes"]:
        if n["id"].lower() in q or (len(n["label"]) > 3 and n["label"].lower() in q):
            highlight.add(n["id"])
    if "confiden" in q or "pii" in q:
        highlight.add("D-CONF")
    if "financ" in q:
        highlight.add("D-FIN")
    if "vendor" in q or "third" in q or "suppl" in q:
        highlight |= {n["id"] for n in g["nodes"] if n["type"] == "vendor"}
    if "shadow" in q:
        highlight |= {n["id"] for n in g["nodes"] if n["type"] == "ai" and n["meta"].get("status") == "shadow"}
    if "critical" in q or "risk" in q:
        highlight |= {n["id"] for n in g["nodes"] if n["type"] == "risk" and n["meta"].get("residual", 0) >= 16}
    chat = LlmChat(api_key=os.environ["EMERGENT_LLM_KEY"], session_id=f"graph-{user['org_id']}",
                   system_message="Answer STRICTLY from the provided knowledge graph JSON. Cite node ids in [brackets]. Be concise (<120 words). Never invent nodes or facts.").with_model("anthropic", "claude-sonnet-5")
    prompt = f"KNOWLEDGE GRAPH JSON:\n{json.dumps(g)[:7000]}\n\nQUESTION: {body.question}"
    collected = []
    try:
        async for ev in chat.stream_message(UserMessage(text=prompt)):
            if isinstance(ev, TextDelta):
                collected.append(ev.content)
            elif isinstance(ev, StreamDone):
                break
    except Exception as e:
        collected.append(f"[graph answer error: {e}]")
    return {"answer": "".join(collected), "highlight": list(highlight)}
