"""Obserra SAP UAC — Ask-AI channels (in-app multi-turn Q&A + Slack/Teams inbound slash
commands + answer log/analytics + Q&A export/email/history). Attached to the shared sap_router.
Extracted from sap_digest.py for maintainability."""
import os
import io
from datetime import datetime, timedelta

import httpx
from bson import ObjectId
from fastapi import Depends, HTTPException, Request, BackgroundTasks
from fastapi.responses import Response
from pydantic import BaseModel

from db import db
from auth import get_current_user, require_roles
from sap_engine import _now, _correlate, _ensure
from sap_uac import sap_router, _audit
from sap_digest import _governance_digest_data, _scorecard_payload, _get_digest_config


# ── Ask-AI-about-this-digest (in-app leadership Q&A, multi-turn) ───────────────
class DigestAskBody(BaseModel):
    session_id: str = ""
    question: str


async def _digest_ai_context(org_id):
    """Compact, grounded live snapshot the AI answers strictly from (no mock)."""
    d = await _governance_digest_data(org_id)
    sc = await _scorecard_payload(org_id, record=False)
    persons, accounts, conflicts, pmap = await _correlate(org_id)
    open_conf = [c for c in conflicts if c.get("status") == "Open"]
    by_area, by_system, by_rule = {}, {}, {}
    for c in open_conf:
        by_area[c.get("area", "—")] = by_area.get(c.get("area", "—"), 0) + 1
        by_system[c.get("system", "—")] = by_system.get(c.get("system", "—"), 0) + 1
        by_rule[c.get("rule_name", "—")] = by_rule.get(c.get("rule_name", "—"), 0) + 1
    return {
        "digest": d,
        "scorecard": {"current": sc.get("current"), "forecast": sc.get("forecast"),
                      "trend_source": sc.get("trend_source"), "trend": sc.get("trend")},
        "open_conflicts_by_area": dict(sorted(by_area.items(), key=lambda x: -x[1])),
        "open_conflicts_by_system": dict(sorted(by_system.items(), key=lambda x: -x[1])),
        "top_open_rules": dict(sorted(by_rule.items(), key=lambda x: -x[1])[:8]),
    }


def _digest_ask_suggestions(ctx):
    areas = list(ctx.get("open_conflicts_by_area", {}).keys())
    top_area = areas[0] if areas else "Finance"
    return ["What are the top risks in this digest right now?",
            f"Why is {top_area} the biggest area of open conflicts?",
            "What should we prioritise remediating this week?",
            "Is the governance score expected to improve next week?"]


def _digest_ask_fallback(ctx):
    d, sc = ctx["digest"], ctx["scorecard"]["current"]
    return (f"Right now there are {d['open_sod']} open SoD conflicts (Critical {d['sev']['Critical']}, "
            f"High {d['sev']['High']}, Medium {d['sev']['Medium']}), a governance score of {sc['governance_score']}/100, "
            f"{d['residual_count']} terminated identities with residual access, and {d['autorem_24h']} auto-remediations "
            "in the last 24h. Ask about a specific risk area, system, or the score trend for more detail.")


@sap_router.get("/digest/ask/intro")
async def digest_ask_intro(user: dict = Depends(get_current_user)):
    org_id = user["org_id"]
    await _ensure(org_id)
    ctx = await _digest_ai_context(org_id)
    d, cur = ctx["digest"], ctx["scorecard"]["current"]
    greeting = (f"I'm your SAP Access Governance analyst. This digest shows {d['open_sod']} open SoD conflicts "
                f"({d['sev']['Critical']} critical) and a governance score of {cur['governance_score']}/100. "
                "Ask me anything about it.")
    return {"greeting": greeting, "suggestions": _digest_ask_suggestions(ctx)}


_ASK_SHORTCUTS = {
    "top risks": "What are the top risks in this digest right now?",
    "score": "What is the current governance score and is it expected to improve next week?",
    "score trend": "What is the current governance score and is it expected to improve next week?",
    "critical": "How many open Critical SoD conflicts are there and in which areas?",
    "residual": "Which terminated identities still have residual SAP access?",
    "residual access": "Which terminated identities still have residual SAP access?",
    "priorities": "What should we prioritise remediating this week?",
    "auto": "How many auto-remediations happened in the last 24 hours?",
}


def _expand_shortcut(text):
    """Map a one-tap shortcut keyword to a full grounded question (else return text unchanged)."""
    return _ASK_SHORTCUTS.get((text or "").strip().lower(), text)


async def _log_ask(org_id, source, user_name, question, answer, model):
    """Record a Slack/Teams 'ask the digest' Q&A for the in-app answer log (No-Mock — real questions)."""
    await db.sap_ask_log.insert_one({
        "org_id": org_id, "source": source, "user_name": user_name or "leader",
        "question": question, "answer": answer, "model": model, "at": _now().isoformat()})


async def _run_digest_ask(org_id, question, session_id=None, actor="", channel="app", timeout=20):
    """Core grounded Q&A used by the in-app endpoint AND the Slack/Teams commands (multi-turn)."""
    await _ensure(org_id)
    q = (question or "").strip()[:500]
    if not q:
        raise HTTPException(400, "Ask a question about the digest")
    session_id = (session_id or "").strip() or f"{org_id}-{int(_now().timestamp())}"
    ctx = await _digest_ai_context(org_id)
    convo = await db.sap_digest_chat.find_one({"org_id": org_id, "session_id": session_id},
                                              {"_id": 0, "messages": 1}) or {}
    is_first = len(convo.get("messages") or []) == 0
    history = (convo.get("messages") or [])[-6:]
    answer, model = None, "deterministic-fallback"
    try:
        import asyncio
        import json as _json
        from emergentintegrations.llm.chat import LlmChat, UserMessage, TextDelta, StreamDone
        system = ("You are the Obserra SAP UAC AI Analyst answering a leader's follow-up question about the SAP "
                  "Access Governance Digest. Ground EVERY answer strictly in the provided live snapshot JSON "
                  "(open SoD conflicts, severities, per-area/system breakdown, governance score, forecast, residual "
                  "leavers, auto-remediation). Be concise and executive (2-4 sentences), cite the numbers, and if the "
                  "data does not contain the answer, say what connector or report would provide it. No markdown headers.")
        chat = LlmChat(api_key=os.environ["EMERGENT_LLM_KEY"], session_id=f"sap-ask-{session_id}",
                       system_message=system).with_model("openai", "gpt-5.4")
        hist_txt = "\n".join(f"{m['role'].upper()}: {m['text']}" for m in history)
        prompt = (f"LIVE DIGEST SNAPSHOT (JSON):\n{_json.dumps(ctx, default=str)[:8000]}\n\n"
                  + (f"PRIOR CONVERSATION:\n{hist_txt}\n\n" if hist_txt else "")
                  + f"LEADER'S QUESTION: {q}")
        collected = []

        async def _run():
            async for ev in chat.stream_message(UserMessage(text=prompt)):
                if isinstance(ev, TextDelta):
                    collected.append(ev.content)
                elif isinstance(ev, StreamDone):
                    break
        await asyncio.wait_for(_run(), timeout=timeout)
        answer = "".join(collected).strip()
        if answer:
            model = "openai/gpt-5.4"
    except Exception:
        answer = None
    if not answer:
        answer = _digest_ask_fallback(ctx)
    now = _now().isoformat()
    await db.sap_digest_chat.update_one(
        {"org_id": org_id, "session_id": session_id},
        {"$push": {"messages": {"$each": [{"role": "user", "text": q, "at": now},
                                          {"role": "assistant", "text": answer, "at": now}]}},
         "$set": {"org_id": org_id, "session_id": session_id, "updated_at": now}},
        upsert=True)
    await _audit(org_id, actor or f"slack:{channel}", "sap.digest.ask", q[:120])
    if is_first:
        title = await _suggest_thread_title(q)
        if title:
            await db.sap_digest_chat.update_one(
                {"org_id": org_id, "session_id": session_id,
                 "$or": [{"title": {"$exists": False}}, {"title": ""}]},
                {"$set": {"title": title}})
    return {"session_id": session_id, "answer": answer[:1200], "model": model,
            "suggestions": _digest_ask_suggestions(ctx)}


@sap_router.post("/digest/ask")
async def digest_ask(body: DigestAskBody, user: dict = Depends(get_current_user)):
    """Answer a leader's follow-up question about the governance digest, grounded in the live snapshot (multi-turn)."""
    return await _run_digest_ask(user["org_id"], body.question, body.session_id, actor=user["email"])


_ASK_RL = {}
_ASK_RESET_WORDS = {"reset", "new", "clear", "restart", "start over"}


def _rate_limited(bucket, limit=20, window=60):
    """Light in-memory per-org sliding-window guard for the public ask endpoints (HMAC is still required first)."""
    import time as _t
    now = _t.time()
    hits = [t for t in _ASK_RL.get(bucket, []) if now - t < window]
    if len(hits) >= limit:
        _ASK_RL[bucket] = hits
        return True
    hits.append(now)
    _ASK_RL[bucket] = hits
    return False


async def _reset_ask_session(org_id, session_id):
    """Start a fresh multi-turn thread for a Slack/Teams conversation."""
    await db.sap_digest_chat.delete_one({"org_id": org_id, "session_id": session_id})


# ── Slack Ask — inbound slash command (e.g. /askdigest) grounded in the live digest ──
def _verify_slack_sig(secret, ts, body_bytes, signature):
    """Real Slack HMAC-SHA256 request verification (No-Mock)."""
    import hmac
    import hashlib
    if not (secret and ts and signature):
        return False
    base = b"v0:" + ts.encode() + b":" + body_bytes
    digest = "v0=" + hmac.new(secret.encode(), base, hashlib.sha256).hexdigest()
    try:
        return hmac.compare_digest(digest, signature)
    except Exception:
        return False


async def _resolve_slack_org(ts, body_bytes, signature):
    """Find the org whose configured Slack signing secret validates this request — the shared
    secret both authenticates the call and identifies the workspace (No-Mock HMAC)."""
    cursor = db.sap_digest_config.find(
        {"slack_ask": True, "slack_signing_secret": {"$nin": ["", None]}},
        {"_id": 0, "org_id": 1, "slack_signing_secret": 1})
    async for c in cursor:
        if _verify_slack_sig(c.get("slack_signing_secret", ""), ts, body_bytes, signature):
            return c["org_id"]
    return None


async def _slack_answer_and_respond(org_id, question, response_url, user_name, session_id=None):
    """Compute the grounded answer and POST it back to Slack's response_url (delayed response)."""
    try:
        res = await _run_digest_ask(org_id, question, session_id=session_id, actor=f"slack:{user_name}", channel="slack")
        await _log_ask(org_id, "slack", user_name, question, res["answer"], res["model"])
        payload = {"response_type": "in_channel",
                   "blocks": [
                       {"type": "section", "text": {"type": "mrkdwn",
                        "text": f":lock: *SAP Access Governance* — asked by @{user_name}\n>{question}"}},
                       {"type": "section", "text": {"type": "mrkdwn", "text": res["answer"]}},
                       {"type": "context", "elements": [{"type": "mrkdwn",
                        "text": "Grounded in the live SAP access snapshot · Obserra SAP UAC"}]},
                   ]}
    except Exception as e:
        payload = {"response_type": "ephemeral", "text": f"Sorry — I couldn't answer that right now ({str(e)[:120]})."}
    try:
        async with httpx.AsyncClient(timeout=15) as c:
            await c.post(response_url, json=payload)
    except Exception:
        pass


@sap_router.post("/slack/ask")
async def slack_ask(request: Request, background: BackgroundTasks):
    """Slack slash-command endpoint. Authenticity is verified via the org's Slack signing secret;
    answers the governance digest question grounded in the live snapshot and posts to response_url."""
    import time
    raw = await request.body()
    ts = request.headers.get("X-Slack-Request-Timestamp", "")
    sig = request.headers.get("X-Slack-Signature", "")
    try:
        if abs(time.time() - int(ts)) > 300:
            raise HTTPException(401, "stale request")
    except (ValueError, TypeError):
        raise HTTPException(401, "invalid request")
    org_id = await _resolve_slack_org(ts, raw, sig)
    if not org_id:
        return {"response_type": "ephemeral",
                "text": "This Slack app isn't linked to a SAP UAC workspace yet, or the signing secret doesn't match. "
                        "Ask an admin to enable Slack Ask on the SoD Command Center and paste the app's signing secret."}
    from urllib.parse import parse_qs
    form = {k: v[0] for k, v in parse_qs(raw.decode()).items()}
    if _rate_limited(f"slack:{org_id}"):
        return {"response_type": "ephemeral", "text": ":hourglass: You're asking a lot at once — give it a few seconds and try again."}
    raw_text = (form.get("text") or "").strip()
    user_name = form.get("user_name", "leader")
    team_id = form.get("team_id", "")
    channel_id = form.get("channel_id", "")
    user_id = form.get("user_id", "")
    response_url = form.get("response_url", "")
    session_id = f"slack:{team_id}:{channel_id}:{user_id}"
    if team_id:
        await db.sap_digest_config.update_one({"org_id": org_id}, {"$set": {"slack_team_id": team_id}})
    if raw_text.lower() in _ASK_RESET_WORDS:
        await _reset_ask_session(org_id, session_id)
        return {"response_type": "ephemeral", "text": ":arrows_counterclockwise: Started a new conversation — your next question begins a fresh thread."}
    question = _expand_shortcut(raw_text)
    if not question:
        shortcuts = " · ".join(f"`{k}`" for k in list(_ASK_SHORTCUTS)[:5])
        ctx = await _digest_ai_context(org_id)
        sugg = "\n".join(f"• {s}" for s in _digest_ask_suggestions(ctx))
        return {"response_type": "ephemeral",
                "text": f"Ask me about the SAP Access Governance digest. Follow-ups continue the thread — say `reset` to start over. Shortcuts: {shortcuts}\n{sugg}"}
    if response_url:
        background.add_task(_slack_answer_and_respond, org_id, question, response_url, user_name, session_id)
        return {"response_type": "ephemeral",
                "text": ":hourglass_flowing_sand: Analyzing the live SAP access governance digest…"}
    res = await _run_digest_ask(org_id, question, session_id=session_id, actor=f"slack:{user_name}", channel="slack")
    await _log_ask(org_id, "slack", user_name, question, res["answer"], res["model"])
    return {"response_type": "in_channel", "text": res["answer"]}


class SlackTestBody(BaseModel):
    question: str = "What are the top risks in this digest right now?"


@sap_router.post("/slack/test")
async def slack_ask_test(body: SlackTestBody, user: dict = Depends(require_roles("admin"))):
    """Admin round-trip check: runs the grounded ask and (if a dedicated Slack webhook is set)
    posts the answer to Slack so the admin can confirm the whole pipeline right after setup."""
    org_id = user["org_id"]
    await _ensure(org_id)
    cfg = await _get_digest_config(org_id)
    q = _expand_shortcut((body.question or "").strip() or "What are the top risks in this digest right now?")
    res = await _run_digest_ask(org_id, q, actor=f"slack-test:{user['email']}", channel="slack-test")
    await _log_ask(org_id, "test", user["email"], q, res["answer"], res["model"])
    slack_url = (cfg.get("slack_url") or "").strip()
    posted = False
    if slack_url:
        try:
            async with httpx.AsyncClient(timeout=15) as c:
                r = await c.post(slack_url, json={"text": f"*SAP Access Governance — Slack Ask test*\n>{q}\n{res['answer']}"})
                posted = r.status_code < 400
        except Exception:
            posted = False
    return {"ok": True, "question": q, "answer": res["answer"], "model": res["model"],
            "signing_secret_set": bool((cfg.get("slack_signing_secret") or "").strip()),
            "webhook_configured": bool(slack_url), "webhook_posted": posted}


@sap_router.get("/ask-log")
async def sap_ask_log(source: str = "", limit: int = 50, user: dict = Depends(get_current_user)):
    """Recent Slack/Teams 'ask the digest' questions + answers — a leadership self-service log."""
    org_id = user["org_id"]
    await _ensure(org_id)
    q = {"org_id": org_id}
    if source in ("slack", "teams", "test"):
        q["source"] = source
    rows = await db.sap_ask_log.find(q, {"_id": 0}).sort("at", -1).to_list(max(1, min(200, limit)))
    total = await db.sap_ask_log.count_documents({"org_id": org_id})
    agg = await db.sap_ask_log.aggregate([
        {"$match": {"org_id": org_id}},
        {"$group": {"_id": "$source", "n": {"$sum": 1}}}]).to_list(20)
    by_source = {(a["_id"] or "?"): a["n"] for a in agg}
    return {"entries": rows, "total": total, "by_source": by_source}


@sap_router.get("/ask-analytics")
async def sap_ask_analytics(user: dict = Depends(get_current_user)):
    """Most-asked questions and busiest askers across Slack/Teams — leadership self-service analytics."""
    org_id = user["org_id"]
    await _ensure(org_id)
    total = await db.sap_ask_log.count_documents({"org_id": org_id})
    src = await db.sap_ask_log.aggregate([
        {"$match": {"org_id": org_id}},
        {"$group": {"_id": "$source", "n": {"$sum": 1}}}]).to_list(20)
    tq = await db.sap_ask_log.aggregate([
        {"$match": {"org_id": org_id}},
        {"$group": {"_id": {"$toLower": {"$trim": {"input": "$question"}}}, "n": {"$sum": 1},
                    "sample": {"$first": "$question"}}},
        {"$sort": {"n": -1}}, {"$limit": 8}]).to_list(8)
    ta = await db.sap_ask_log.aggregate([
        {"$match": {"org_id": org_id}},
        {"$group": {"_id": "$user_name", "n": {"$sum": 1}, "last": {"$max": "$at"}}},
        {"$sort": {"n": -1}}, {"$limit": 8}]).to_list(8)
    return {"total": total,
            "by_source": {(a["_id"] or "?"): a["n"] for a in src},
            "top_questions": [{"question": (t.get("sample") or t["_id"]), "count": t["n"]} for t in tq],
            "top_askers": [{"user": (a["_id"] or "leader"), "count": a["n"], "last": a.get("last")} for a in ta]}


# ── Teams Ask — inbound Microsoft Teams Outgoing Webhook (HMAC) grounded in the digest ──
def _verify_teams_sig(secret_b64, body_bytes, auth_header):
    """Verify a Microsoft Teams Outgoing Webhook HMAC signature (Authorization: HMAC <base64>)."""
    import hmac
    import hashlib
    import base64
    if not (secret_b64 and auth_header):
        return False
    provided = auth_header.strip()
    if provided.upper().startswith("HMAC "):
        provided = provided[5:].strip()
    try:
        key = base64.b64decode(secret_b64)
        digest = base64.b64encode(hmac.new(key, body_bytes, hashlib.sha256).digest()).decode()
        return hmac.compare_digest(digest, provided)
    except Exception:
        return False


async def _resolve_teams_org(body_bytes, auth_header):
    """Find the org whose configured Teams HMAC secret validates this request (No-Mock)."""
    cursor = db.sap_digest_config.find(
        {"teams_ask": True, "teams_ask_secret": {"$nin": ["", None]}},
        {"_id": 0, "org_id": 1, "teams_ask_secret": 1})
    async for c in cursor:
        if _verify_teams_sig(c.get("teams_ask_secret", ""), body_bytes, auth_header):
            return c["org_id"]
    return None


@sap_router.post("/teams/ask")
async def teams_ask(request: Request):
    """Microsoft Teams Outgoing Webhook endpoint. Authenticity is verified via the org's Teams HMAC
    secret; answers synchronously (Teams requires an immediate reply) grounded in the live snapshot."""
    import json as _json
    import re as _re
    raw = await request.body()
    auth = request.headers.get("Authorization", "")
    org_id = await _resolve_teams_org(raw, auth)
    if not org_id:
        return {"type": "message",
                "text": "This Teams webhook isn't linked to a SAP UAC workspace yet, or the HMAC secret doesn't match. "
                        "Ask an admin to enable Teams Ask on the SoD Command Center and paste the outgoing-webhook secret."}
    if _rate_limited(f"teams:{org_id}"):
        return {"type": "message", "text": "You're asking a lot at once — give it a few seconds and try again."}
    try:
        payload = _json.loads(raw.decode() or "{}")
    except Exception:
        payload = {}
    text_raw = _re.sub(r"<at>.*?</at>", "", (payload.get("text") or "")).strip()
    user_name = ((payload.get("from") or {}).get("name")) or "leader"
    conv_id = ((payload.get("conversation") or {}).get("id")) or ((payload.get("from") or {}).get("id")) or "default"
    session_id = f"teams:{conv_id}"
    if text_raw.lower() in _ASK_RESET_WORDS:
        await _reset_ask_session(org_id, session_id)
        return {"type": "message", "text": "Started a new conversation — your next question begins a fresh thread."}
    text = _expand_shortcut(text_raw)
    if not text:
        ctx = await _digest_ai_context(org_id)
        sugg = "\n".join(f"- {s}" for s in _digest_ask_suggestions(ctx))
        return {"type": "message", "text": f"Ask me about the SAP Access Governance digest (follow-ups continue the thread; say 'reset' to start over). For example:\n{sugg}"}
    res = await _run_digest_ask(org_id, text, session_id=session_id, actor=f"teams:{user_name}", channel="teams", timeout=8)
    await _log_ask(org_id, "teams", user_name, text, res["answer"], res["model"])
    return {"type": "message", "text": res["answer"]}


@sap_router.post("/teams/test")
async def teams_ask_test(body: SlackTestBody, user: dict = Depends(require_roles("admin"))):
    """Admin round-trip check for Teams Ask: runs the grounded ask and (if a dedicated SAP Teams
    webhook is set) posts the answer to Teams so the admin can confirm right after setup."""
    org_id = user["org_id"]
    await _ensure(org_id)
    cfg = await _get_digest_config(org_id)
    q = _expand_shortcut((body.question or "").strip() or "What are the top risks in this digest right now?")
    res = await _run_digest_ask(org_id, q, actor=f"teams-test:{user['email']}", channel="teams-test")
    await _log_ask(org_id, "test", user["email"], q, res["answer"], res["model"])
    teams_url = (cfg.get("teams_url") or "").strip()
    posted = False
    if teams_url:
        try:
            async with httpx.AsyncClient(timeout=15) as c:
                r = await c.post(teams_url, json={"@type": "MessageCard", "@context": "https://schema.org/extensions",
                                                  "summary": "SAP Access Governance — Teams Ask test", "themeColor": "0f1e3d",
                                                  "title": "SAP Access Governance — Teams Ask test", "text": f"**{q}**\n\n{res['answer']}"})
                posted = r.status_code < 400
        except Exception:
            posted = False
    return {"ok": True, "question": q, "answer": res["answer"], "model": res["model"],
            "secret_set": bool((cfg.get("teams_ask_secret") or "").strip()),
            "webhook_configured": bool(teams_url), "webhook_posted": posted}


# ── Chat Export (PDF + email the AI Q&A thread, stamped to the audit trail) ────
class DigestAskEmailBody(BaseModel):
    session_id: str
    recipients: list[str] = []


def _chat_pdf(messages, meta):
    """Branded PDF of an AI Q&A thread (leadership note)."""
    from reportlab.lib.pagesizes import LETTER
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image as RLImage
    import html as _h
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=LETTER, topMargin=0.6 * inch, bottomMargin=0.6 * inch,
                            leftMargin=0.7 * inch, rightMargin=0.7 * inch)
    ss = getSampleStyleSheet()
    navy = colors.HexColor("#0f1e3d")
    title_st = ParagraphStyle("t", parent=ss["Title"], textColor=navy, fontSize=17, spaceAfter=2)
    sub_st = ParagraphStyle("s", parent=ss["Normal"], textColor=colors.HexColor("#64748b"), fontSize=9)
    q_st = ParagraphStyle("q", parent=ss["Normal"], fontSize=10.5, leading=14, textColor=navy,
                          fontName="Helvetica-Bold", spaceBefore=10, spaceAfter=2)
    a_st = ParagraphStyle("a", parent=ss["Normal"], fontSize=10, leading=14,
                          textColor=colors.HexColor("#1f2937"), leftIndent=10, spaceAfter=4)
    flow = []
    badge = "/app/backend/assets/brand-badge.png"
    if os.path.exists(badge):
        flow.append(RLImage(badge, width=32, height=32))
    flow.append(Paragraph("SAP Access Governance — AI Q&amp;A Note", title_st))
    flow.append(Paragraph(_h.escape(meta), sub_st))
    flow.append(Spacer(1, 8))
    for m in messages:
        txt = _h.escape(m.get("text", "")).replace("\n", "<br/>")
        flow.append(Paragraph(("Q · " + txt) if m.get("role") == "user" else ("A · " + txt),
                              q_st if m.get("role") == "user" else a_st))
    flow.append(Spacer(1, 12))
    flow.append(Paragraph("Obserra — Executive Protection &amp; Intelligence LLC · Confidential · "
                          "Answers grounded in the live SAP access snapshot at time of asking.", sub_st))
    doc.build(flow)
    buf.seek(0)
    return buf


def _ask_email_html(msgs, meta):
    import html as _h
    body = ""
    for m in msgs:
        t = _h.escape(m.get("text", "")).replace("\n", "<br/>")
        if m.get("role") == "user":
            body += f'<div style="margin:12px 0 2px;font-weight:700;color:#0f1e3d;font-size:14px">Q · {t}</div>'
        else:
            body += f'<div style="margin:0 0 8px;color:#334155;font-size:13px;line-height:1.5">A · {t}</div>'
    return ('<div style="font:400 14px Arial,Helvetica,sans-serif;color:#1f2937;max-width:640px;margin:auto">'
            '<div style="background:#0f1e3d;color:#fff;padding:18px 22px;border-radius:12px 12px 0 0">'
            '<div style="font-size:11px;letter-spacing:2px;opacity:.7">OBSERRA SAP UAC</div>'
            '<h2 style="margin:4px 0 0;font-size:20px">AI Q&amp;A Note</h2>'
            f'<div style="font-size:12px;opacity:.75;margin-top:2px">{_h.escape(meta)}</div></div>'
            '<div style="border:1px solid #e2e8f0;border-top:0;border-radius:0 0 12px 12px;padding:14px 18px">'
            + body +
            '<p style="font-size:11px;color:#9ca3af;margin-top:18px;border-top:1px solid #e2e8f0;padding-top:10px">'
            'Obserra — Executive Protection &amp; Intelligence LLC · Confidential · Grounded in the live SAP access '
            'snapshot. A branded PDF copy is attached.</p></div></div>')


async def _get_ask_thread(org_id, session_id):
    convo = await db.sap_digest_chat.find_one({"org_id": org_id, "session_id": session_id},
                                              {"_id": 0, "messages": 1}) or {}
    return convo.get("messages") or []


@sap_router.get("/digest/ask/export")
async def digest_ask_export(session_id: str, user: dict = Depends(get_current_user)):
    org_id = user["org_id"]
    await _ensure(org_id)
    msgs = await _get_ask_thread(org_id, session_id)
    if not msgs:
        raise HTTPException(status_code=404, detail="No Q&A thread to export yet — ask a question first.")
    qn = len([m for m in msgs if m.get("role") == "user"])
    meta = f"{qn} question(s) · Exported {_now().strftime('%B %d, %Y %H:%M UTC')} · by {user['email']}"
    pdf = _chat_pdf(msgs, meta)
    await _audit(org_id, user["email"], "sap.digest.ask.export", f"AI Q&A note exported ({qn} Q, session {session_id[:8]})")
    ts = _now().strftime("%Y%m%d-%H%M")
    return Response(content=pdf.getvalue(), media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="sap-digest-ai-qa-{ts}.pdf"'})


@sap_router.post("/digest/ask/email")
async def digest_ask_email(body: DigestAskEmailBody, user: dict = Depends(get_current_user)):
    org_id = user["org_id"]
    await _ensure(org_id)
    from kernel import notifications
    import base64
    msgs = await _get_ask_thread(org_id, body.session_id)
    if not msgs:
        raise HTTPException(status_code=404, detail="No Q&A thread to email yet — ask a question first.")
    emails = [e.strip() for e in body.recipients if e.strip()] or [user["email"]]
    qn = len([m for m in msgs if m.get("role") == "user"])
    meta = f"AI Q&A note · {qn} question(s) · {_now().strftime('%B %d, %Y')} · by {user['email']}"
    pdf = _chat_pdf(msgs, meta)
    att = [{"filename": f"sap-digest-ai-qa-{_now().strftime('%Y%m%d')}.pdf",
            "content": base64.b64encode(pdf.getvalue()).decode()}]
    html = _ask_email_html(msgs, meta)
    sent = 0
    for e in emails:
        if await notifications.send_email(e, "SAP Governance — AI Q&A Note — Obserra UAC", html, attachments=att):
            sent += 1
    await _audit(org_id, user["email"], "sap.digest.ask.email",
                 f"AI Q&A note emailed to {len(emails)} recipient(s), {sent} sent ({qn} Q)")
    return {"ok": True, "sent": sent, "recipients": emails}


@sap_router.get("/digest/ask/history")
async def digest_ask_history(user: dict = Depends(get_current_user)):
    """Recent AI Q&A threads for the org, newest first (for the Ask-AI dialog history)."""
    org_id = user["org_id"]
    await _ensure(org_id)
    docs = await db.sap_digest_chat.find({"org_id": org_id},
        {"_id": 0, "session_id": 1, "messages": 1, "updated_at": 1, "title": 1}).sort("updated_at", -1).to_list(30)
    out = []
    for d in docs:
        msgs = d.get("messages") or []
        qn = len([m for m in msgs if m.get("role") == "user"])
        if not qn:
            continue
        first_q = next((m["text"] for m in msgs if m.get("role") == "user"), "")
        out.append({"session_id": d["session_id"], "title": (d.get("title") or first_q[:90] or "Untitled thread"),
                    "custom": bool(d.get("title")), "questions": qn, "updated_at": d.get("updated_at")})
    return {"threads": out}


@sap_router.get("/digest/ask/thread")
async def digest_ask_thread(session_id: str, user: dict = Depends(get_current_user)):
    """Full messages of a past AI Q&A thread so leaders can reopen and continue it."""
    org_id = user["org_id"]
    await _ensure(org_id)
    msgs = await _get_ask_thread(org_id, session_id)
    if not msgs:
        raise HTTPException(status_code=404, detail="Thread not found")
    return {"session_id": session_id, "messages": [{"role": m["role"], "text": m["text"]} for m in msgs]}


# ── Rename a saved AI Q&A thread ──────────────────────────────────────────────
class AskRenameBody(BaseModel):
    session_id: str
    title: str


@sap_router.post("/digest/ask/rename")
async def digest_ask_rename(body: AskRenameBody, user: dict = Depends(get_current_user)):
    org_id = user["org_id"]
    await _ensure(org_id)
    title = (body.title or "").strip()[:90]
    res = await db.sap_digest_chat.update_one({"org_id": org_id, "session_id": body.session_id},
                                              {"$set": {"title": title}})
    if not res.matched_count:
        raise HTTPException(status_code=404, detail="Thread not found")
    return {"ok": True, "session_id": body.session_id, "title": title}


async def _suggest_thread_title(question):
    """Best-effort 3-6 word AI title for a new Q&A thread (falls back to empty on failure)."""
    try:
        import asyncio
        from emergentintegrations.llm.chat import LlmChat, UserMessage, TextDelta, StreamDone
        chat = LlmChat(api_key=os.environ["EMERGENT_LLM_KEY"], session_id=f"sap-title-{int(_now().timestamp())}",
                       system_message="You write a 3-6 word title in Title Case (no quotes, no trailing punctuation) that "
                                       "summarizes the TOPIC of a leadership question about SAP access governance.").with_model("openai", "gpt-5.4")
        parts = []

        async def _run():
            async for ev in chat.stream_message(UserMessage(text=f"Question: {question}\nTitle:")):
                if isinstance(ev, TextDelta):
                    parts.append(ev.content)
                elif isinstance(ev, StreamDone):
                    break
        await asyncio.wait_for(_run(), timeout=12)
        return "".join(parts).strip().strip('"').strip()[:60]
    except Exception:
        return ""
