import os
import io
import csv
import json
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
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

# User-selectable advisor models ("Connect to model"). These identifiers are already
# verified against emergentintegrations elsewhere in this file (FAIR-AIR + board reports).
ADVISOR_MODELS = [
    {"id": "gpt-5.6-sol", "label": "GPT-5.6 Sol", "provider": "openai", "tier": "Frontier reasoning", "note": "Deepest multi-step reasoning"},
    {"id": "gpt-5.6-terra", "label": "GPT-5.6 Terra", "provider": "openai", "tier": "Frontier", "note": "High reasoning, balanced latency"},
    {"id": "gpt-5.6-luna", "label": "GPT-5.6 Luna", "provider": "openai", "tier": "Frontier", "note": "Fast frontier tier"},
    {"id": "gpt-5.5", "label": "GPT-5.5", "provider": "openai", "tier": "Advanced", "note": "Strong general analysis"},
    {"id": "gpt-5.4", "label": "GPT-5.4", "provider": "openai", "tier": "Balanced", "note": "Great default"},
    {"id": "gpt-5.4-mini", "label": "GPT-5.4 Mini", "provider": "openai", "tier": "Fast", "note": "Lowest cost, quick answers"},
    {"id": "claude-opus-4-8", "label": "Claude Opus 4.8", "provider": "anthropic", "tier": "Frontier synthesis", "note": "Board-grade synthesis (auto default)"},
    {"id": "claude-sonnet-5", "label": "Claude Sonnet 5", "provider": "anthropic", "tier": "Balanced", "note": "Fast, capable synthesis"},
    {"id": "gemini-3.1-pro-preview", "label": "Gemini 3.1 Pro", "provider": "gemini", "tier": "Long-context", "note": "Best for large context ingestion"},
]
_MODEL_PROVIDER = {m["id"]: m["provider"] for m in ADVISOR_MODELS}

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
    "openai/gpt-5.6-sol": (10.0, 30.0),
    "openai/gpt-5.6-terra": (8.0, 24.0),
    "openai/gpt-5.6-luna": (5.0, 15.0),
    "openai/gpt-5.5": (4.0, 12.0),
    "openai/gpt-5.4": (2.5, 10.0),
    "openai/gpt-5.4-mini": (0.4, 1.6),
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
                    "so the Obserrian Advisor is paused for the rest of this month.</p>"
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

    # Forecast Alert — projected month-end spend will cross the cap while still under it now.
    if pct < 100:
        from calendar import monthrange
        now = datetime.now(timezone.utc)
        dim = monthrange(now.year, now.month)[1]
        forecast = spent / now.day * dim if now.day > 0 else spent
        if forecast >= budget and org.get("advisor_forecast_notified") != mk:
            await notifications.create(
                org_id, "advisor_budget", "AI advisor spend projected to exceed cap",
                f"At the current pace, advisor spend is projected to reach ${round(forecast, 2)} by month-end — "
                f"over the ${budget} monthly cap (currently ${spent}, {round(pct)}%).",
                ref="advisor-budget", dedupe_key=f"advisor-forecast:{mk}")
            recips = await db.users.find(
                {"org_id": org_id, "role": {"$in": ["admin", "executive"]}}, {"_id": 0, "email": 1}).to_list(200)
            html = ("<div style=\"font:400 14px Arial;color:#1f2937;max-width:560px;margin:auto\">"
                    "<h2 style=\"color:#0f1e3d\">AI Advisor spend projected to exceed cap</h2>"
                    f"<p>At the current pace, advisor spend is projected to reach <b>${round(forecast, 2)}</b> by "
                    f"month-end — over your <b>${budget}</b> monthly cap.</p>"
                    f"<p>You've spent <b>${spent}</b> so far ({round(pct)}% of cap). Review usage or adjust the cap "
                    "in the Advisor panel to stay on budget.</p>"
                    "<p style=\"font-size:11px;color:#9ca3af\">Obserra — Executive Protection &amp; Intelligence LLC</p></div>")
            for r in recips:
                await notifications.send_email(r["email"], "AI Advisor projected to exceed monthly cap", html)
            await db.organizations.update_one({"_id": ObjectId(org_id)}, {"$set": {"advisor_forecast_notified": mk}})



class AdvisorQuery(BaseModel):
    message: str
    mode: str = "executive"
    session_id: str | None = None
    deep: bool = False
    model: str | None = None


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
    chosen = body.model or (await db.organizations.find_one({"_id": ObjectId(org_id)}, {"advisor_model": 1}) or {}).get("advisor_model")
    if chosen and chosen in _MODEL_PROVIDER:
        provider, model = _MODEL_PROVIDER[chosen], chosen
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


class ModelPref(BaseModel):
    model: str | None = None


@advisor_router.get("/models")
async def advisor_models(user: dict = Depends(get_current_user)):
    """Catalog of models the advisor can connect to, plus the org's saved default and the
    auto (mode-routed) model so the UI can show what's currently powering replies."""
    org = await db.organizations.find_one({"_id": ObjectId(user["org_id"])}, {"advisor_model": 1}) or {}
    ep, em = MODEL_ROUTES["executive"]
    op, om = MODEL_ROUTES["operational"]
    return {"models": ADVISOR_MODELS, "default": org.get("advisor_model"),
            "auto": {"executive": f"{ep}/{em}", "operational": f"{op}/{om}"}}


@advisor_router.put("/model")
async def set_advisor_model(body: ModelPref, user: dict = Depends(get_current_user)):
    """Connect the advisor to a specific model (org-wide default). None = Auto (mode routing)."""
    mid = body.model if body.model in _MODEL_PROVIDER else None
    await db.organizations.update_one({"_id": ObjectId(user["org_id"])}, {"$set": {"advisor_model": mid}})
    return {"default": mid, "connected": bool(mid)}


class InsightReq(BaseModel):
    dashboard: str
    mode: str = "executive"


_INSIGHT_CACHE = {}


@advisor_router.post("/insight")
async def advisor_insight(body: InsightReq, user: dict = Depends(require_active_subscription)):
    """AI-native, grounded analysis of a single dashboard's LIVE data. Returns a small JSON
    insight card (headline + 3-4 cited findings + 1-2 next actions). Cached 3 min per org+dashboard."""
    import re as _re
    org_id = user["org_id"]
    now = datetime.now(timezone.utc)
    key = (org_id, body.dashboard, body.mode)
    cached = _INSIGHT_CACHE.get(key)
    if cached and (now - cached["ts"]).total_seconds() < 180:
        return cached["data"]
    if await _is_paused(org_id):
        raise HTTPException(status_code=429, detail="Advisor paused: monthly spend cap reached.")
    ctx = await _all_dashboards_context(org_id)
    provider, model = MODEL_ROUTES["executive"]
    chosen = (await db.organizations.find_one({"_id": ObjectId(org_id)}, {"advisor_model": 1}) or {}).get("advisor_model")
    if chosen and chosen in _MODEL_PROVIDER:
        provider, model = _MODEL_PROVIDER[chosen], chosen
    system = (
        "You are the Obserra EIOS Advisor generating a CONCISE, board-grade AI insight card for the "
        f"'{body.dashboard}' dashboard in {body.mode} mode. Ground every point in the provided live context; "
        "cite a specific metric, ref, framework or $ figure in each finding. Separate FACT (connected/measured), "
        "ESTIMATE (modeled) and PREDICTION (forward-looking). Return STRICT JSON only, no markdown: "
        '{"headline": string (<=90 chars), "insights": [{"text": string, "kind": "fact"|"estimate"|"prediction"}] '
        '(exactly 3-4 items), "actions": [string] (1-2 short imperative next steps)}.'
    )
    chat = LlmChat(api_key=os.environ["EMERGENT_LLM_KEY"],
                   session_id=f"insight-{org_id}-{body.dashboard}", system_message=system).with_model(provider, model)
    prompt = (f"DASHBOARD: {body.dashboard}\nLIVE CONTEXT (JSON):\n{json.dumps(ctx, default=str)[:12000]}\n\n"
              "Produce the insight JSON now.")
    collected = []
    try:
        async for ev in chat.stream_message(UserMessage(text=prompt)):
            if isinstance(ev, TextDelta):
                collected.append(ev.content)
            elif isinstance(ev, StreamDone):
                break
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Advisor unavailable: {e}")
    raw = "".join(collected).strip()
    mm = _re.search(r"\{.*\}", raw, _re.S)
    try:
        data = json.loads(mm.group(0)) if mm else {}
    except Exception:
        data = {}
    if not isinstance(data, dict) or "insights" not in data:
        data = {"headline": (raw[:88] or "Insight unavailable"), "insights": [], "actions": []}
    data.setdefault("headline", "")
    data.setdefault("insights", [])
    data.setdefault("actions", [])
    data["model"] = f"{provider}/{model}"
    data["generated_at"] = now.isoformat()
    _INSIGHT_CACHE[key] = {"ts": now, "data": data}
    usage = _estimate_usage(f"{provider}/{model}", prompt, system, raw)
    await db.advisor_logs.insert_one({"org_id": org_id, "user": user["email"], "mode": body.mode,
                                      "model": f"{provider}/{model}", "prompt": f"[insight] {body.dashboard}",
                                      "response": raw, "usage": usage, "ts": now.isoformat()})
    await _check_budget(org_id)
    return data


class FixReq(BaseModel):
    entity: str
    ref: str | None = None


_FIX_CACHE = {}


async def _fix_grounding(org_id, entity, ref):
    scan = await db.self_scans.find_one({"org_id": org_id}, sort=[("ts", -1)]) or {}
    controls = await db.controls.find({"org_id": org_id}, {"_id": 0}).to_list(500)
    summary = scan.get("summary") or {}
    findings = scan.get("findings") or []
    kev = len(scan.get("kev_matches") or []) or sum(1 for f in findings if f.get("kev"))
    cves = summary.get("vulnerable_dependencies") or 0
    open_findings = [f for f in findings if f.get("status") != "pass"]
    high = sum(1 for f in open_findings if f.get("severity") in ("critical", "high"))
    implicated = sorted({c for f in findings for c in (f.get("control_refs") or [])})
    gap = sorted([c for c in controls if c.get("effectiveness", 100) < (c.get("baseline") or 80)],
                 key=lambda c: c.get("effectiveness", 0))[:3]
    obj, exposure, title = None, 0, ref
    if entity == "risk":
        obj = await db.risks.find_one({"org_id": org_id, "ref": ref}, {"_id": 0})
        exposure = (obj or {}).get("residual", 0) * 5
        title = (obj or {}).get("title", ref)
    elif entity == "asset":
        obj = await db.assets.find_one({"org_id": org_id, "ref": ref}, {"_id": 0})
        exposure = (obj or {}).get("exposure", 0)
        title = (obj or {}).get("name", ref)
    elif entity == "vendor":
        obj = await db.vendors.find_one({"org_id": org_id, "ref": ref}, {"_id": 0})
        exposure = (obj or {}).get("risk_score", 0)
        title = (obj or {}).get("name", ref)
    return {"summary": summary, "kev": kev, "cves": cves, "high_findings": high,
            "open_findings": [{"title": f.get("title"), "severity": f.get("severity"),
                               "remediation": f.get("remediation"), "cve_ids": f.get("cve_ids"),
                               "control_refs": f.get("control_refs")} for f in open_findings[:6]],
            "implicated_controls": implicated, "gap_controls": gap, "entity_obj": obj,
            "exposure": exposure, "title": title}


def _rating(g, entity):
    kev, cves, gaps, high, exposure = g["kev"], g["cves"], len(g["gap_controls"]), g["high_findings"], g["exposure"]
    score = 0
    if kev:
        score += 45
    score += min(30, cves * 15)
    score += min(20, gaps * 7)
    score += min(15, high * 10)
    score += min(20, (exposure or 0) / 5)
    if entity == "risk" and g["entity_obj"]:
        score = max(score, round((g["entity_obj"].get("residual", 0) / 25) * 100 * 0.92))
    score = round(min(100, score))
    rating = "Critical" if (kev or score >= 70) else "High" if score >= 45 else "Medium" if score >= 25 else "Low"
    rationale = []
    if kev:
        rationale.append(f"{kev} CISA KEV-listed vulnerabilit{'y' if kev == 1 else 'ies'} present — actively exploited in the wild, auto-escalating severity to Critical.")
    if cves:
        rationale.append(f"{cves} unpatched dependency CVE(s) detected on the scanned surface.")
    if high:
        rationale.append(f"{high} high/critical open scan finding(s) currently unremediated.")
    if g["gap_controls"]:
        rationale.append("Compliance control gaps below baseline: " + ", ".join(
            f"{c.get('control_id')} {c.get('name')} ({c.get('framework')} · {c.get('effectiveness')}%)" for c in g["gap_controls"]) + ".")
    if g["implicated_controls"]:
        rationale.append("Implicated framework controls: " + ", ".join(g["implicated_controls"][:6]) + ".")
    if not rationale:
        rationale.append("No active exploit signals, CVEs or control gaps detected for this entity.")
    return rating, score, rationale


@advisor_router.post("/fix")
async def advisor_fix(body: FixReq, user: dict = Depends(require_active_subscription)):
    """Grounded per-entity risk rating (from compliance controls + CVE/KEV analysis) plus an
    AI-written recommendation to fix. Used inside detail views across every dashboard."""
    import re as _re
    org_id = user["org_id"]
    now = datetime.now(timezone.utc)
    key = (org_id, body.entity, body.ref)
    cached = _FIX_CACHE.get(key)
    if cached and (now - cached["ts"]).total_seconds() < 180:
        return cached["data"]
    g = await _fix_grounding(org_id, body.entity, body.ref)
    rating, score, rationale = _rating(g, body.entity)
    result = {"rating": rating, "score": score, "rationale": rationale,
              "implicated_controls": g["implicated_controls"][:8],
              "recommendation": "", "steps": [], "model": ""}
    if not await _is_paused(org_id):
        provider, model = MODEL_ROUTES["executive"]
        chosen = (await db.organizations.find_one({"_id": ObjectId(org_id)}, {"advisor_model": 1}) or {}).get("advisor_model")
        if chosen and chosen in _MODEL_PROVIDER:
            provider, model = _MODEL_PROVIDER[chosen], chosen
        system = (
            "You are the Obserra EIOS Advisor. Given a security entity, its live CVE/KEV signals and the "
            "compliance-control gaps driving its risk rating, write a SHORT, concrete remediation. Ground every "
            "point in the provided data (cite CVE ids, control ids/frameworks). Return STRICT JSON only, no markdown: "
            '{"recommendation": string (<=220 chars, imperative), "steps": [string] (2-4 concrete steps)}.')
        ctx = {"entity": body.entity, "ref": body.ref, "title": g["title"], "rating": rating,
               "kev": g["kev"], "cves": g["cves"], "open_findings": g["open_findings"],
               "gap_controls": [{"id": c.get("control_id"), "name": c.get("name"),
                                 "framework": c.get("framework"), "effectiveness": c.get("effectiveness")} for c in g["gap_controls"]],
               "implicated_controls": g["implicated_controls"]}
        chat = LlmChat(api_key=os.environ["EMERGENT_LLM_KEY"], session_id=f"fix-{org_id}-{body.entity}-{body.ref}",
                       system_message=system).with_model(provider, model)
        prompt = f"ENTITY CONTEXT (JSON):\n{json.dumps(ctx, default=str)[:8000]}\n\nProduce the remediation JSON now."
        collected = []
        try:
            async for ev in chat.stream_message(UserMessage(text=prompt)):
                if isinstance(ev, TextDelta):
                    collected.append(ev.content)
                elif isinstance(ev, StreamDone):
                    break
        except Exception:
            collected = []
        raw = "".join(collected).strip()
        mm = _re.search(r"\{.*\}", raw, _re.S)
        try:
            parsed = json.loads(mm.group(0)) if mm else {}
        except Exception:
            parsed = {}
        result["recommendation"] = parsed.get("recommendation") or ""
        result["steps"] = parsed.get("steps") or []
        result["model"] = f"{provider}/{model}"
        if raw:
            usage = _estimate_usage(f"{provider}/{model}", prompt, system, raw)
            await db.advisor_logs.insert_one({"org_id": org_id, "user": user["email"], "mode": "fix",
                                              "model": f"{provider}/{model}", "prompt": f"[fix] {body.entity} {body.ref}",
                                              "response": raw, "usage": usage, "ts": now.isoformat()})
            await _check_budget(org_id)
    if not result["recommendation"]:
        fr = g["open_findings"][0]["remediation"] if g["open_findings"] else None
        result["recommendation"] = fr or "Maintain current hardening; no active exploit or control gap requires immediate action."
        result["steps"] = [f["remediation"] for f in g["open_findings"] if f.get("remediation")][:4] or ["Continue monitoring and re-scan on the next cycle."]
    result["generated_at"] = now.isoformat()
    _FIX_CACHE[key] = {"ts": now, "data": result}
    return result


@advisor_router.get("/logs")
async def advisor_logs(user: dict = Depends(get_current_user)):
    logs = await db.advisor_logs.find({"org_id": user["org_id"]}, {"_id": 0}).sort("ts", -1).to_list(50)
    return logs


@advisor_router.post("/hint-open")
async def advisor_hint_open(user: dict = Depends(get_current_user)):
    """Record that an exec opened the Advisor from the first-time intro hint."""
    await db.advisor_hint_events.insert_one({
        "org_id": user["org_id"], "user": user["email"],
        "ts": datetime.now(timezone.utc).isoformat(),
    })
    return {"ok": True}


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
    from calendar import monthrange
    now = datetime.now(timezone.utc)
    dim = monthrange(now.year, now.month)[1]
    forecast = round(month_cost / now.day * dim, 4) if now.day > 0 else month_cost
    forecast_pct = round(forecast / budget * 100) if budget > 0 else 0
    forecast_over = budget > 0 and forecast > budget
    hint_events = await db.advisor_hint_events.find({"org_id": admin["org_id"]}, {"_id": 0, "user": 1}).to_list(5000)
    hint_opens = len(hint_events)
    hint_unique = len({e["user"] for e in hint_events})
    return {"queries": len(logs), "total_tokens": total_tokens, "total_cost_usd": total_cost,
            "today_cost_usd": today_cost, "month_cost_usd": month_cost, "budget_usd": budget,
            "budget_pct": pct, "budget_status": status, "auto_pause": auto_pause, "paused": paused,
            "alert_threshold": threshold, "forecast_usd": forecast, "forecast_pct": forecast_pct,
            "forecast_over": forecast_over, "trend": trend, "by_user": by_user, "recent": recent,
            "hint_opens": hint_opens, "hint_unique": hint_unique}


async def spend_rows(org_id: str, scope: str = "all"):
    logs = await db.advisor_logs.find({"org_id": org_id, "usage": {"$exists": True}}, {"_id": 0}).sort("ts", -1).to_list(5000)
    mk = _month_key()
    agg = {}
    for l in logs:
        m = l.get("ts", "")[:7]
        if scope != "all" and m != mk:
            continue
        k = (m, l["user"])
        e = agg.setdefault(k, {"month": m, "user": l["user"], "cost_usd": 0.0, "queries": 0, "tokens": 0})
        e["cost_usd"] += l["usage"]["cost_usd"]
        e["queries"] += 1
        e["tokens"] += l["usage"]["total_tokens"]
    return sorted(agg.values(), key=lambda x: (x["month"], -x["cost_usd"]))


@advisor_router.get("/usage/export")
async def advisor_usage_export(scope: str = "month", admin: dict = Depends(require_roles("admin"))):
    mk = _month_key()
    rows = await spend_rows(admin["org_id"], scope)
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["Month", "Teammate", "Queries", "Tokens", "Cost (USD)"])
    for r in rows:
        w.writerow([r["month"], r["user"], r["queries"], r["tokens"], f"{r['cost_usd']:.4f}"])
    w.writerow(["ALL" if scope == "all" else mk, "TOTAL", sum(r["queries"] for r in rows),
                sum(r["tokens"] for r in rows), f"{sum(r['cost_usd'] for r in rows):.4f}"])
    buf.seek(0)
    fname = f"advisor-spend-{'all-history' if scope == 'all' else mk}.csv"
    return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv",
                             headers={"Content-Disposition": f'attachment; filename="{fname}"'})


@advisor_router.get("/usage/prompts")
async def advisor_user_prompts(member: str, admin: dict = Depends(require_roles("admin"))):
    logs = await db.advisor_logs.find(
        {"org_id": admin["org_id"], "user": member, "usage": {"$exists": True}}, {"_id": 0}).sort("ts", -1).to_list(15)
    return [{"prompt": l["prompt"], "ts": l.get("ts"), "model": l.get("model"),
             "cost_usd": l["usage"]["cost_usd"], "tokens": l["usage"]["total_tokens"],
             "response": (l.get("response") or "")[:240]} for l in logs]


@advisor_router.get("/prompts/search")
async def search_prompts(q: str, admin: dict = Depends(require_roles("admin"))):
    if not q or len(q.strip()) < 2:
        return []
    import re
    rx = re.escape(q.strip())
    logs = await db.advisor_logs.find(
        {"org_id": admin["org_id"], "prompt": {"$regex": rx, "$options": "i"}}, {"_id": 0}).sort("ts", -1).to_list(30)
    return [{"user": l["user"], "prompt": l["prompt"], "ts": l.get("ts"), "model": l.get("model"),
             "response": (l.get("response") or ""),
             "cost_usd": (l.get("usage") or {}).get("cost_usd")} for l in logs]


_INSIGHT_STOPWORDS = set((
    "the a an of to in for our we is are what which how do i on and or by with at as be this that it "
    "you your my me us they them their there here can could would should will shall about into from over "
    "under out up down off than then so if but not no yes any all some most more less give show tell list "
    "please help need want get got make made using use used based whats what's whos who's does did done "
    "have has had was were been being are am also just like really very much many one two three current "
    "right now today week month year risk risks"
).split())


@advisor_router.get("/prompts/insights")
async def prompt_insights(admin: dict = Depends(require_roles("admin"))):
    import re
    from collections import Counter
    logs = await db.advisor_logs.find({"org_id": admin["org_id"]}, {"_id": 0, "prompt": 1}).sort("ts", -1).to_list(500)
    bigrams, unigrams = Counter(), Counter()
    for l in logs:
        words = re.findall(r"[a-zA-Z]{2,}", (l.get("prompt") or "").lower())
        for w in words:
            if w not in _INSIGHT_STOPWORDS:
                unigrams[w] += 1
        for i in range(len(words) - 1):
            a, b = words[i], words[i + 1]
            if a not in _INSIGHT_STOPWORDS and b not in _INSIGHT_STOPWORDS:
                bigrams[f"{a} {b}"] += 1
    top_bi = [(t, n) for t, n in bigrams.most_common(12) if n >= 2]
    source = top_bi if len(top_bi) >= 3 else (bigrams.most_common(12) or unigrams.most_common(12))
    themes = [{"term": t, "count": n} for t, n in source]
    return {"total_prompts": len(logs), "themes": themes}


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
                                      {"$set": update, "$unset": {"advisor_pause_notified": "", "advisor_alert_notified": "", "advisor_forecast_notified": ""}})
    return {"monthly_usd": val, "auto_pause": update.get("advisor_auto_pause"), "alert_threshold": update.get("advisor_alert_threshold")}


async def _run_board_report_job(job_id: str, org_id: str, by: str):
    try:
        res = await generate_board_report(org_id, by)
        await db.report_jobs.update_one({"job_id": job_id}, {"$set": {"status": "done", **res}})
    except Exception as e:
        await db.report_jobs.update_one({"job_id": job_id}, {"$set": {"status": "error", "error": str(e)}})


@advisor_router.post("/board-report")
async def board_report(background_tasks: BackgroundTasks, user: dict = Depends(require_active_subscription)):
    import uuid
    job_id = uuid.uuid4().hex
    now = datetime.now(timezone.utc).isoformat()
    await db.report_jobs.insert_one({"job_id": job_id, "org_id": user["org_id"],
                                     "by": user["email"], "status": "running", "created_at": now})
    background_tasks.add_task(_run_board_report_job, job_id, user["org_id"], user["email"])
    return {"job_id": job_id, "status": "running"}


@advisor_router.get("/board-report/{job_id}")
async def board_report_status(job_id: str, user: dict = Depends(get_current_user)):
    job = await db.report_jobs.find_one({"job_id": job_id, "org_id": user["org_id"]}, {"_id": 0})
    if not job:
        raise HTTPException(status_code=404, detail="Report job not found")
    return job


AI_SAFETY_EVIDENCE = {
    "international_ai_safety_report_2026": {
        "chair": "Yoshua Bengio",
        "publisher": "International AI Safety Report 2026 (internationalaisafetyreport.org)",
        "why_ai_is_a_risk": [
            "AI is lowering the barrier to cyberattacks — actors use AI to generate malicious code, find vulnerabilities and package attack tooling for less-skilled attackers.",
            "The cyber offense-defense balance is worsening — AI increases attacker speed, scale and access to advanced tooling while defenses lag.",
            "Offense is becoming more autonomous — AI agents can run longer cyber tasks (AI-assisted today, trending toward autonomous).",
            "Evaluation is getting harder — models can distinguish testing from deployment and exploit test loopholes, so dangerous capabilities can go undetected pre-release.",
            "Empirical incidents show AI systems acting against instructions and using deception to avoid oversight (loss-of-control risk).",
        ],
        "risk_categories": [
            "Malicious use (cyberattacks, fraud, influence ops, deepfakes, bio/chem misuse)",
            "Technical failures (unreliable reasoning, loss of control, test-vs-deploy divergence)",
            "Systemic risks (autonomy, institutions, labor markets)",
        ],
    }
}

_ALLOWED_GPT = ["gpt-5.6-sol", "gpt-5.6-terra", "gpt-5.6-luna", "gpt-5.5", "gpt-5.4", "gpt-5.4-mini"]
_DEFAULT_MODEL = "gpt-5.4"


def _pick_model(m):
    return m if m in _ALLOWED_GPT else _DEFAULT_MODEL


async def _all_dashboards_context(org_id: str) -> dict:
    """Synthesis context pulling from EVERY dashboard so FAIR-AIR reasoning is holistic:
    financial/FAIR + security scanner + compliance crosswalk + autonomous remediation +
    threat containment + connectors + threat intel."""
    from datetime import timedelta
    fin = await _board_financial_context(org_id)
    scan = await db.self_scans.find_one({"org_id": org_id}, {"_id": 0}, sort=[("ts", -1)]) or {}
    ev = await db.scan_evidence.find_one({"org_id": org_id}, {"_id": 0}) or {}
    since = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    jobs = await db.maintenance_jobs.find({"org_id": org_id, "created_at": {"$gte": since}}, {"_id": 0, "status": 1}).to_list(1000)
    job_counts = {}
    for j in jobs:
        job_counts[j.get("status", "?")] = job_counts.get(j.get("status", "?"), 0) + 1
    contain = await db.containment_events.find({"org_id": org_id}, {"_id": 0, "status": 1, "kind": 1}).to_list(500)
    activity = await db.autonomy_activity.count_documents({"org_id": org_id, "ts": {"$gte": since}})
    ent_conns = await db.enterprise_connectors.find({"org_id": org_id}, {"_id": 0, "connected": 1}).to_list(200)
    conns = await db.connectors.find({"org_id": org_id}, {"_id": 0, "status": 1}).to_list(200)
    intel = await db.threat_intel.find_one({"org_id": org_id}, {"_id": 0}) or await db.threat_intel.find_one({}, {"_id": 0}) or {}
    kev_set = intel.get("kev_set") if isinstance(intel.get("kev_set"), dict) else {}
    connected = len([c for c in ent_conns if c.get("connected")]) + len([c for c in conns if str(c.get("status", "")).lower() in ("connected", "active", "live")])
    return {
        **fin,
        "security_scanner": {
            "score": scan.get("score"), "severity": scan.get("summary"),
            "kev_matches": len(scan.get("kev_matches") or []),
            "vulnerable_dependencies": (scan.get("summary") or {}).get("vulnerable_dependencies"),
            "mitre_techniques": len(scan.get("mitre_techniques") or []),
            "cwe_ids": len(scan.get("cwe_ids") or []),
            "endpoint": scan.get("endpoint"), "scanned_at": scan.get("ts"),
        },
        "compliance_crosswalk": {
            "gaps_by_framework": {k: len(v) for k, v in (ev.get("gaps") or {}).items()},
            "aligned_by_framework": {k: len(v) for k, v in (ev.get("aligned") or {}).items()},
        },
        "autonomous_remediation": {"jobs_30d_by_status": job_counts, "activity_events_30d": activity},
        "threat_containment": {
            "total": len(contain),
            "auto_contained": len([c for c in contain if c.get("status") == "auto-contained"]),
            "open_review": len([c for c in contain if str(c.get("status", "")).lower() in ("review", "pending", "open")]),
        },
        "connectors": {"connected_sources": connected, "catalog_size": len(ent_conns) + len(conns)},
        "threat_intel": {"kev_count": kev_set.get("count"), "kev_version": kev_set.get("version"),
                         "updated": intel.get("updated") or intel.get("checked_at")},
        "external_evidence": AI_SAFETY_EVIDENCE,
    }


async def generate_fair_air_analysis(org_id: str, model: str = None):
    """LLM-produced FAIR-AIR quantified scenario statements per GenAI risk vector, grounded in org data."""
    import re as _re
    try:
        fin_context = json.dumps(await _all_dashboards_context(org_id), default=str)
    except Exception:
        fin_context = "{}"
    chat = LlmChat(
        api_key=os.environ["EMERGENT_LLM_KEY"],
        session_id=f"fair-air-{org_id}",
        system_message=(
            "You are a FAIR-AIR analyst (FAIR Institute methodology) quantifying an organisation's AI-related "
            "cyber risk in financial terms. Ground every number in the provided context (FAIR figures, IBM AI-breach "
            "and shadow-AI benchmarks, DBIR medians, and the org's AI-system / shadow-AI / incident posture). "
            "Never invent data beyond reasoned FAIR estimates. The purpose is to enable secure AI adoption, not block it.\n\n"
            "ADVANCED REASONING MODE — before answering, internally reason in structured steps for EACH vector: "
            "(1) identify the threat actor, asset and loss event; (2) estimate Loss Event Frequency from the provided "
            "frequency/benchmark signals; (3) estimate Loss Magnitude from the FAIR Loss-Magnitude and IBM/DBIR figures; "
            "(4) reason about second-order effects, control weaknesses and the dominant risk driver; (5) derive a defensible "
            "probability % and $ loss. Ground WHY each vector is a material risk in the provided external_evidence "
            "(International AI Safety Report 2026, chaired by Yoshua Bengio) alongside IBM/DBIR/FAIR. "
            "Do ALL reasoning internally and output ONLY the final JSON array — no working, no prose."
        ),
    ).with_model("openai", _pick_model(model))
    prompt = (
        f"CONTEXT (JSON — SYNTHESIZED FROM ALL DASHBOARDS: FAIR quantification, benchmarks, AI-system posture, "
        f"security-scanner findings/KEV, compliance crosswalk, autonomous-remediation activity, threat containment, "
        f"connectors & threat intel):\n{fin_context}\n\n"
        "Synthesize ACROSS every dashboard above — correlate FAIR exposure with live scan findings, compliance gaps, "
        "shadow-AI/AI-system posture, containment events and connector coverage — then produce a FAIR-AIR analysis for "
        "EACH of the 5 GenAI risk vectors: "
        "\"Shadow GenAI\", \"Foundational LLM\", \"Hosting on LLMs\", \"Managed LLMs\", \"Active cyber attack\".\n"
        "For each, write a quantified scenario statement in EXACTLY this format:\n"
        "\"There is a X% probability in the next year that <who> will <event>, which will lead to $Y in losses.\"\n"
        "- probability_pct: integer 1-40, defensible vs the provided frequency/benchmark data.\n"
        "- loss_usd: integer $ loss, grounded in the FAIR Loss-Magnitude / benchmark figures.\n"
        "- key_driver: the single most important risk driver to target (e.g. phishing click-rate among staff with sensitive-data access).\n"
        "- nist_functions: subset of [\"GOVERN\",\"MAP\",\"MEASURE\",\"MANAGE\"].\n"
        "- recommended_controls: 2-3 items, each \"<control name> (<NIST AI RMF ref>)\".\n"
        "- why_risk: ONE sentence on WHY this is a material risk, citing the evidence base "
        "(International AI Safety Report 2026 (Bengio) / IBM / DBIR / FAIR).\n\n"
        "Return ONLY a JSON array (no markdown, no prose) of objects with keys: "
        "vector, probability_pct, loss_usd, statement, key_driver, why_risk, nist_functions, recommended_controls."
    )
    collected = []
    async for ev in chat.stream_message(UserMessage(text=prompt)):
        if isinstance(ev, TextDelta):
            collected.append(ev.content)
        elif isinstance(ev, StreamDone):
            break
    raw = "".join(collected).strip()
    m = _re.search(r"\[.*\]", raw, _re.DOTALL)
    scenarios = []
    if m:
        try:
            scenarios = json.loads(m.group(0))
        except Exception:
            scenarios = []
    now = datetime.now(timezone.utc).isoformat()
    return {"scenarios": scenarios, "model": _pick_model(model), "generated_at": now}


async def _run_fair_air_job(job_id: str, org_id: str, model: str = None):
    try:
        res = await generate_fair_air_analysis(org_id, model)
        await db.fair_air_jobs.update_one({"job_id": job_id}, {"$set": {"status": "done", **res}})
    except Exception as e:
        await db.fair_air_jobs.update_one({"job_id": job_id}, {"$set": {"status": "error", "error": str(e)}})


class FairAirBody(BaseModel):
    model: str = ""


@advisor_router.post("/fair-air")
async def fair_air_start(body: FairAirBody, background_tasks: BackgroundTasks, user: dict = Depends(require_active_subscription)):
    import uuid
    job_id = uuid.uuid4().hex
    now = datetime.now(timezone.utc).isoformat()
    model = _pick_model(body.model)
    await db.fair_air_jobs.insert_one({"job_id": job_id, "org_id": user["org_id"], "model": model,
                                       "by": user["email"], "status": "running", "created_at": now})
    background_tasks.add_task(_run_fair_air_job, job_id, user["org_id"], model)
    return {"job_id": job_id, "status": "running", "model": model}


@advisor_router.get("/fair-air/{job_id}")
async def fair_air_status(job_id: str, user: dict = Depends(get_current_user)):
    if job_id == "latest":
        job = await db.fair_air_jobs.find_one({"org_id": user["org_id"], "status": "done"},
                                              {"_id": 0}, sort=[("created_at", -1)])
        return job or {"status": "none"}
    job = await db.fair_air_jobs.find_one({"job_id": job_id, "org_id": user["org_id"]}, {"_id": 0})
    if not job:
        raise HTTPException(status_code=404, detail="Analysis job not found")
    return job


async def generate_fair_air_vector(org_id: str, vector: str, model: str = None):
    """Deep-dive FAIR-AIR analysis for a SINGLE GenAI risk vector with tailored mitigations."""
    import re as _re
    try:
        ctx = json.dumps(await _all_dashboards_context(org_id), default=str)
    except Exception:
        ctx = "{}"
    chat = LlmChat(
        api_key=os.environ["EMERGENT_LLM_KEY"],
        session_id=f"fair-air-vec-{org_id}",
        system_message=(
            "You are a FAIR-AIR analyst (FAIR Institute methodology) doing a focused deep-dive on ONE GenAI risk "
            "vector, quantifying it in financial terms grounded in the provided context. Never invent data beyond "
            "reasoned FAIR estimates. The purpose is to enable secure AI adoption, not block it.\n\n"
            "ADVANCED REASONING MODE — internally reason step by step (threat actor, asset, loss event; Loss Event "
            "Frequency from the frequency/benchmark signals; Loss Magnitude from FAIR/IBM/DBIR figures; second-order "
            "effects, control weaknesses, dominant driver; defensible probability % and $ loss). Ground WHY this vector "
            "is a material risk in the provided external_evidence (International AI Safety Report 2026, Bengio) alongside "
            "IBM/DBIR/FAIR. Output ONLY the JSON."
        ),
    ).with_model("openai", _pick_model(model))
    prompt = (
        f"CONTEXT (JSON — SYNTHESIZED FROM ALL DASHBOARDS):\n{ctx}\n\n"
        f"Deep-dive the single GenAI risk vector: \"{vector}\". Synthesize across every dashboard. "
        "Return ONLY a JSON object (no markdown, no prose) with keys:\n"
        "vector (string), summary (2-3 sentence board-grade narrative), expected_loss_usd (number),\n"
        "scenarios (array of 2-3 objects: statement in the form 'There is a X% probability in the next year that "
        "<who> will <event>, which will lead to $Y in losses.', probability_pct number, loss_usd number, key_driver string),\n"
        "top_drivers (array of 2-4 strings — the key risk drivers to target),\n"
        "mitigations (array of 3-5 objects: action string, nist_ref string e.g. 'MANAGE 2.1', impact string describing the $ or risk reduction)."
    )
    collected = []
    async for ev in chat.stream_message(UserMessage(text=prompt)):
        if isinstance(ev, TextDelta):
            collected.append(ev.content)
        elif isinstance(ev, StreamDone):
            break
    raw = "".join(collected).strip()
    m = _re.search(r"\{.*\}", raw, _re.DOTALL)
    obj = {}
    if m:
        try:
            obj = json.loads(m.group(0))
        except Exception:
            obj = {}
    obj.setdefault("vector", vector)
    return {"analysis": obj, "model": _pick_model(model), "generated_at": datetime.now(timezone.utc).isoformat()}


async def _run_fair_air_vector_job(job_id: str, org_id: str, vector: str, model: str = None):
    try:
        res = await generate_fair_air_vector(org_id, vector, model)
        await db.fair_air_vector_jobs.update_one({"job_id": job_id}, {"$set": {"status": "done", **res}})
    except Exception as e:
        await db.fair_air_vector_jobs.update_one({"job_id": job_id}, {"$set": {"status": "error", "error": str(e)}})


class VectorBody(BaseModel):
    vector: str
    model: str = ""


@advisor_router.post("/fair-air/vector")
async def fair_air_vector_start(body: VectorBody, background_tasks: BackgroundTasks, user: dict = Depends(require_active_subscription)):
    import uuid
    job_id = uuid.uuid4().hex
    now = datetime.now(timezone.utc).isoformat()
    model = _pick_model(body.model)
    await db.fair_air_vector_jobs.insert_one({"job_id": job_id, "org_id": user["org_id"], "vector": body.vector,
                                              "model": model, "by": user["email"], "status": "running", "created_at": now})
    background_tasks.add_task(_run_fair_air_vector_job, job_id, user["org_id"], body.vector, model)
    return {"job_id": job_id, "status": "running", "model": model}


@advisor_router.get("/fair-air/vector/{job_id}")
async def fair_air_vector_status(job_id: str, user: dict = Depends(get_current_user)):
    job = await db.fair_air_vector_jobs.find_one({"job_id": job_id, "org_id": user["org_id"]}, {"_id": 0})
    if not job:
        raise HTTPException(status_code=404, detail="Vector analysis not found")
    return job


async def _run_weekly_fair_air_refresh():
    """Weekly auto-refresh: re-run the FAIR-AIR analysis for every org so the board
    dashboard + board pack always reflect the latest posture (piggybacks the weekly cron)."""
    import uuid
    org_ids = await db.organizations.distinct("_id")
    for oid in org_ids:
        try:
            res = await generate_fair_air_analysis(str(oid))
            await db.fair_air_jobs.insert_one({"job_id": uuid.uuid4().hex, "org_id": str(oid),
                                               "by": "scheduler@obserra", "status": "done",
                                               "created_at": datetime.now(timezone.utc).isoformat(), **res})
        except Exception:
            continue


async def _autonomy_scorecard(org_id: str) -> str:
    from datetime import timedelta
    since = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    jobs = await db.maintenance_jobs.find({"org_id": org_id, "created_at": {"$gte": since}}).to_list(1000)
    shipped = [j for j in jobs if j.get("status") in ("success", "applied")]
    prevented = [j for j in jobs if j.get("status") == "requires_approval"]
    rolled = [j for j in jobs if j.get("status") == "rolled_back"]
    contained = await db.containment_events.count_documents(
        {"org_id": org_id, "status": "auto-contained", "ts": {"$gte": since}})
    durs = []
    for j in shipped:
        try:
            c = datetime.fromisoformat(j["created_at"])
            f = datetime.fromisoformat(j["finished_at"])
            durs.append((f - c).total_seconds())
        except Exception:
            pass
    if durs:
        avg = sum(durs) / len(durs)
        mttp = f"{avg/60:.0f} min" if avg < 3600 else f"{avg/3600:.1f} h"
    else:
        mttp = "—"
    return (
        "\n\n## Autonomy Scorecard\n"
        f"Autonomous remediation engine activity over the last 30 days [FACT]:\n"
        f"- Fixes shipped autonomously: {len(shipped)}\n"
        f"- Outages prevented (sandbox-blocked before shipping): {len(prevented)}\n"
        f"- Auto-rollbacks on regression: {len(rolled)}\n"
        f"- Threats auto-contained: {contained}\n"
        f"- Mean time to patch (queued to live): {mttp}\n"
    )


async def _methodology_appendix(org_id):
    from routes import _get_fin_cfg, _benchmark, _fin
    cfg = await _get_fin_cfg(org_id)
    risks = await db.risks.find({"org_id": org_id}, {"_id": 0}).to_list(500)
    slis = [_fin(r, cfg)["sle"] for r in risks] or [0]
    avg = round(sum(slis) / len(slis))
    bench = await _benchmark(cfg["industry"])
    ind = bench.get("industry_avg") or 0
    ratio = round(avg / ind, 2) if ind else None
    signoff = cfg.get("signoff")
    md = "\n\n## Board Note — Exposure vs Industry\n"
    if ratio and ratio > 1.25:
        md += (f"[ESTIMATE] Our modelled per-incident exposure (${avg/1e6:.2f}M) runs **{ratio}x the "
               f"{bench['industry']} industry average** (${ind/1e6:.2f}M, IBM). In plain terms: our loss-magnitude "
               f"assumptions are more conservative than the published benchmark, driven by the concentration of "
               f"high-impact risks in the register. The board should note this deliberately prudent stance, or "
               f"recalibrate the impact-to-dollar table if it overstates true asset exposure.\n")
    elif ratio:
        md += (f"[ESTIMATE] Our modelled per-incident exposure (${avg/1e6:.2f}M) is broadly in line with the "
               f"{bench['industry']} industry average (${ind/1e6:.2f}M, IBM) at {ratio}x — figures are defensible "
               f"against published data.\n")
    md += "\n## Methodology & Sources (for auditors)\n"
    md += ("[FACT] Financial exposure uses the FAIR model: Annualized Loss Expectancy (ALE) = Single Loss "
           "Expectancy (SLE) x Annualized Rate of Occurrence (ARO), scaled by residual/inherent control "
           "effectiveness and an evidence-confidence factor. ")
    if cfg.get("method") == "records":
        md += f"SLE derives from {int(cfg.get('records') or 0):,} records x ${int(cfg.get('per_record_cost') or 165)}/record (IBM per-record method). "
    else:
        md += ("SLE magnitudes come from the organisation's configured impact-to-dollar table"
               + (" (calibrated by the risk team)." if cfg.get("custom_table") else " (default analyst assumptions; calibration recommended).") + " ")
    md += "Ranges use a 2,000-iteration Monte-Carlo over magnitude and frequency uncertainty (P10/P50/P90).\n\n"
    md += "External benchmarks cited:\n"
    md += f"- {bench.get('industry_avg_source')}: {bench['industry']} ${ind/1e6:.2f}M; global ${(bench.get('global_avg') or 0)/1e6:.2f}M ({bench.get('global_avg_source')}).\n"
    md += f"- {bench.get('ai_breach_source')}: AI-enabled breach avg ${(bench.get('ai_breach_avg') or 0)/1e6:.2f}M; shadow-AI premium +${(bench.get('shadow_ai_premium') or 0)/1e3:.0f}k ({bench.get('shadow_ai_source')}).\n"
    md += f"- {bench.get('dbir_source')}: ransomware median ${(bench.get('dbir_ransomware_median') or 0)/1e3:.0f}k, BEC median ${(bench.get('dbir_bec_median') or 0)/1e3:.0f}k.\n"
    md += f"- Benchmark table last updated {bench.get('updated')}; re-checked at most annually.\n"
    from routes import _montecarlo_item
    top = sorted(risks, key=lambda r: _fin(r, cfg)["residual_ale"], reverse=True)[:5]
    if top:
        md += "\n## Per-Risk Exposure Bands (Monte-Carlo P10–P90)\n"
        md += "| Ref | Risk | Expected ALE | P10–P90 band |\n|---|---|---|---|\n"
        for r in top:
            ff = _fin(r, cfg)
            band = _montecarlo_item(ff, r)
            md += (f"| {r.get('ref')} | {str(r.get('title'))[:40]} | ${ff['residual_ale']/1e6:.2f}M | "
                   f"${band['p10']/1e6:.2f}M – ${band['p90']/1e6:.2f}M |\n")
    if signoff and signoff.get("locked"):
        md += f"\n[FACT] Calibration approved & locked by {signoff['name']} on {str(signoff.get('at'))[:10]} (config hash {signoff.get('hash')}).\n"
    else:
        md += "\n[ESTIMATE] Calibration is not yet CRO-signed; figures are working estimates pending sign-off.\n"
    md += "\n_Decision-support estimates, not guarantees. Sources: IBM Cost of a Data Breach (2025/2026) and Verizon DBIR (2025)._\n"
    return md


async def _board_financial_context(org_id):
    """Rich FAIR/financial grounding for the board report, drawing on ALL app data:
    portfolio $ exposure, per-risk FAIR decomposition (Loss Magnitude / TEF / Vulnerability / LEF),
    Monte-Carlo bands, benchmarks, the unremediated risk-acceptance register, and enterprise-wide
    control / third-party / asset / AI-governance / incident / compliance posture."""
    from routes import _fin, _get_fin_cfg, _benchmark, _montecarlo, _montecarlo_item
    cfg = await _get_fin_cfg(org_id)
    risks = await db.risks.find({"org_id": org_id}, {"_id": 0}).to_list(500)
    recs = await db.recommendations.find({"org_id": org_id}, {"_id": 0}).to_list(500)
    controls = await db.controls.find({"org_id": org_id}, {"_id": 0}).to_list(500)
    vendors = await db.vendors.find({"org_id": org_id}, {"_id": 0}).to_list(500)
    assets = await db.assets.find({"org_id": org_id}, {"_id": 0}).to_list(500)
    ai_systems = await db.ai_systems.find({"org_id": org_id}, {"_id": 0}).to_list(500)
    incidents = await db.ai_incidents.find({"org_id": org_id}, {"_id": 0}).to_list(500)
    health = await db.health_index.find_one({"org_id": org_id}, {"_id": 0}) or {}
    pending = {r.get("risk_ref") for r in recs if r.get("status") == "Pending"}
    mc_items, items = [], []
    for r in risks:
        f = _fin(r, cfg)
        band = _montecarlo_item(f, r)
        inh, res = max(1, r.get("inherent", 10)), r.get("residual", 10)
        tef = round(r.get("likelihood", 3) / 5, 2)
        vuln = round(res / inh, 2)
        mc_items.append({"sle": f["sle"], "aro": f["aro"], "residual": res, "inherent": inh})
        items.append({
            "ref": r.get("ref"), "title": r.get("title"), "status": r.get("status"),
            "owner": r.get("owner"), "category": r.get("category"),
            "business_impact": r.get("business_impact"),
            "residual_score": res, "inherent_score": r.get("inherent"),
            "sle_usd": f["sle"], "residual_ale_usd": f["residual_ale"], "inherent_ale_usd": f["inherent_ale"],
            "band_p10_usd": band["p10"], "band_p50_usd": band["p50"], "band_p90_usd": band["p90"],
            "confidence": f["confidence"], "remediation_pending": r.get("ref") in pending,
            "fair": {"loss_magnitude_usd": f["sle"], "tef": tef, "vulnerability": vuln,
                     "lef": round(tef * vuln, 2),
                     "note": "FAIR: ALE = Loss Magnitude (LM) x Loss Event Frequency (LEF); LEF = TEF x Vulnerability"},
        })
    items.sort(key=lambda x: x["residual_ale_usd"], reverse=True)
    residual_total = sum(i["residual_ale_usd"] for i in items)
    inherent_total = sum(i["inherent_ale_usd"] for i in items)
    portfolio = _montecarlo(mc_items)
    bench = await _benchmark(cfg["industry"])
    accepted = [i for i in items if i["status"] not in ("Remediated", "Closed", "Resolved")]
    accepted_total = sum(i["residual_ale_usd"] for i in accepted)
    signoff = cfg.get("signoff")

    def _low_eff(c):
        v = c.get("effectiveness")
        if v is None:
            v = c.get("coverage")
        return v is not None and v < 60
    enterprise = {
        "health": {"security_score": health.get("score") or health.get("security_score"),
                   "compliance_pct": health.get("compliance_pct"), "app_health": health.get("app_health")},
        "controls": {"total": len(controls), "low_effectiveness_gaps": len([c for c in controls if _low_eff(c)])},
        "third_party_vendors": {"total": len(vendors),
                                "high_risk": len([v for v in vendors if str(v.get("tier") or v.get("rating") or v.get("risk") or "").lower() in ("high", "critical", "d", "f")])},
        "assets": {"total": len(assets), "stale": len([a for a in assets if a.get("freshness") == "stale"])},
        "ai_systems": {"total": len(ai_systems), "shadow_ai": len([a for a in ai_systems if a.get("status") == "shadow"])},
        "incidents_open": len([i for i in incidents if i.get("status") != "Resolved"]),
        "pending_recommendations": len(pending),
    }
    return {
        "portfolio": {
            "residual_ale_usd": round(residual_total), "inherent_ale_usd": round(inherent_total),
            "reduction_pct": round((inherent_total - residual_total) / inherent_total * 100) if inherent_total else 0,
            "monte_carlo_p10_usd": portfolio["p10"], "monte_carlo_p50_usd": portfolio["p50"],
            "monte_carlo_p90_usd": portfolio["p90"], "method": cfg["method"], "industry": cfg["industry"],
            "fair_basis": "Portfolio ALE aggregates per-risk FAIR estimates (Loss Magnitude x Loss Event Frequency, "
                          "control-scaled by residual/inherent); range via 2,000-iteration Monte-Carlo.",
        },
        "benchmark": {
            "industry_avg_usd": bench.get("industry_avg"), "global_avg_usd": bench.get("global_avg"),
            "ai_breach_avg_usd": bench.get("ai_breach_avg"), "shadow_ai_premium_usd": bench.get("shadow_ai_premium"),
            "dbir_ransomware_median_usd": bench.get("dbir_ransomware_median"),
            "sources": [bench.get("industry_avg_source"), bench.get("global_avg_source"),
                        bench.get("ai_breach_source"), bench.get("dbir_source")],
            "updated": bench.get("updated"),
        },
        "risks_ranked": items[:12],
        "unremediated_acceptance": {
            "total_residual_ale_accepted_usd": round(accepted_total), "count": len(accepted),
            "register": [{"ref": i["ref"], "title": i["title"], "owner": i["owner"], "status": i["status"],
                          "residual_ale_usd": i["residual_ale_usd"], "adverse_p90_usd": i["band_p90_usd"],
                          "remediation_pending": i["remediation_pending"]} for i in accepted[:10]],
        },
        "enterprise_data": enterprise,
        "calibration_signoff": {"locked": bool((signoff or {}).get("locked")),
                                "by": (signoff or {}).get("name"), "at": (signoff or {}).get("at")},
    }


async def generate_board_report(org_id: str, by: str):
    context = await _build_context(org_id)
    try:
        fin_context = json.dumps(await _board_financial_context(org_id), default=str)
    except Exception as e:
        fin_context = "{}"
    chat = LlmChat(
        api_key=os.environ["EMERGENT_LLM_KEY"],
        session_id=f"board-{org_id}",
        system_message=(
            "You are the Chief Risk Officer of the organisation, writing a rigorous, board-grade enterprise "
            "risk, AI-governance and cyber-financial report for the Board of Directors and Audit Committee. "
            "Your readers are non-technical directors who make capital-allocation and risk-acceptance decisions. "
            "Apply genuine analytical reasoning and deduction: connect each technical risk to its business and "
            "financial consequences, quantify exposure in dollars using ONLY the FAIR figures provided, reason "
            "about second-order effects and interdependencies between risks, and be explicit about the residual "
            "exposure the board is IMPLICITLY ACCEPTING by leaving risks unremediated. Never invent numbers — every "
            "$ figure must come from the FINANCIAL CONTEXT. Cite risk refs like [CR-001]. Label FACT "
            "(connected/measured), ESTIMATE (modelled) and PREDICTION (forward-looking). Write with the precision "
            "of a Big-4 board deck: no filler, no generic platitudes — every sentence carries insight."
        ),
    ).with_model("openai", _DEFAULT_MODEL)
    prompt = (
        f"ENTERPRISE CONTEXT (JSON — risks, AI systems, incidents, health):\n{context}\n\n"
        f"FINANCIAL CONTEXT (JSON — FAIR quantification, Monte-Carlo bands, benchmarks, risk-acceptance register):\n{fin_context}\n\n"
        "Produce a board report in markdown with EXACTLY these sections, in order. Reason deeply within each — "
        "do not restate the data; interpret it, deduce implications, and advise:\n\n"
        "## Executive Summary\n"
        "3-5 sentences: the single most important thing the board must understand about enterprise risk posture and "
        "financial exposure this quarter, including the headline residual $ exposure and its trajectory.\n\n"
        "## Business Impact Analysis\n"
        "Translate the top risks into concrete business consequences (revenue, operations, customer trust, regulatory, "
        "contractual). Reason about cascading/second-order effects and which business capabilities are most exposed. Cite refs.\n\n"
        "## Risk Analysis\n"
        "Analytical breakdown of the risk landscape: concentration, what is driving residual score, AI-governance and "
        "shadow-AI exposure, and interdependencies between risks. Deduce the root themes — not a list.\n\n"
        "## Financial Exposure & Quantification\n"
        "Quantify portfolio residual ALE and the Monte-Carlo P10/P50/P90 band in $. Benchmark the modelled exposure "
        "against the IBM/DBIR industry figures provided and interpret whether the organisation sits above/below peers and "
        "why. State confidence and limitations. Use ONLY the provided $ figures.\n\n"
        "## Advanced FAIR Analysis\n"
        "Perform a rigorous Factor Analysis of Information Risk. For the top exposures, decompose each into its FAIR "
        "factors using the provided `fair` fields: Loss Magnitude (LM, $), Threat Event Frequency (TEF), Vulnerability "
        "(control weakness = residual/inherent) and the resulting Loss Event Frequency (LEF = TEF x Vulnerability), and "
        "show how they combine into ALE (ALE = LM x LEF). Reason about which FAIR factor is the dominant driver of each "
        "risk's exposure (frequency vs magnitude vs control weakness) and therefore where mitigation buys the most $ "
        "reduction. Integrate ALL enterprise data provided (control gaps, third-party/vendor risk, stale assets, "
        "shadow-AI systems, open incidents, compliance posture) to explain WHY the vulnerability and frequency factors "
        "are what they are — deduce the systemic drivers, do not just restate counts. Cite refs.\n\n"
        "## Unremediated Risk Acceptance\n"
        "The most important section for the board. Using the risk-acceptance register, state the TOTAL residual exposure "
        "(in $) the organisation is currently ACCEPTING by not remediating, list the specific risks being carried "
        "(ref, owner, residual $ and adverse-case P90 $), flag which have a decision pending vs implicit acceptance, and "
        "give the board a clear, reasoned view of whether this acceptance is prudent or requires formal sign-off. Name the "
        "accountable owners.\n\n"
        "## Recommendations & Decisions Required\n"
        "Prioritised, specific actions the board must decide on, each tied to a cited risk and the $ exposure it reduces, "
        "with a confidence level. Distinguish decisions requiring board authority from management actions.\n\n"
        "Target 700-950 words. Be rigorous, quantified and decision-oriented."
    )
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
    try:
        report += await _autonomy_scorecard(org_id)
    except Exception:
        pass
    try:
        report += await _methodology_appendix(org_id)
    except Exception:
        pass
    now = datetime.now(timezone.utc).isoformat()
    await db.reports.insert_one({"org_id": org_id, "report": report,
                                 "model": "anthropic/claude-opus-4-8", "generated_at": now, "by": by})
    return {"report": report, "model": "claude-opus-4-8", "generated_at": now}


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
