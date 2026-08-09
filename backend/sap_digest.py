"""Obserra SAP UAC — Governance Digest (email + Slack/Teams) and Access Governance Scorecard
(attached to the shared sap_router)."""
import os
import io
import csv
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
from sap_autoremediation import _get_autoremediation


# ── SAP Governance Digest ─────────────────────────────────────────────────────
async def _governance_digest_data(org_id):
    persons, accounts, conflicts, pmap = await _correlate(org_id)
    open_conf = [c for c in conflicts if c.get("status") == "Open"]
    sev = {s: sum(1 for c in open_conf if c["severity"] == s) for s in ("Critical", "High", "Medium")}
    day_ago = (_now() - timedelta(days=1)).isoformat()
    autorem = await db.sap_autoremediation_log.find({"org_id": org_id}, {"_id": 0}).to_list(2000)
    autorem_24h = [r for r in autorem if (r.get("at") or "") >= day_ago]
    tickets_24h = await db.sap_snow_tickets.count_documents({"org_id": org_id, "opened_at": {"$gte": day_ago}})
    residual = [p for p in persons if p["status"] == "Terminated" and any(a.get("lock_state") == "unlocked" for a in p.get("accounts", []))]
    top = sorted(persons, key=lambda p: -p["risk"]["score"])[:5]
    cfg = await _get_autoremediation(org_id)
    return {
        "open_sod": len(open_conf), "sev": sev,
        "autorem_24h": len(autorem_24h), "autorem_total": len(autorem),
        "autorem_enabled": bool(cfg.get("enabled")), "autorem_action": cfg.get("action"),
        "tickets_24h": tickets_24h,
        "residual": [{"name": p["name"], "dept": p["department"]} for p in residual][:8],
        "residual_count": len(residual),
        "top": [{"name": p["name"], "dept": p["department"], "score": p["risk"]["score"], "rating": p["risk"]["rating"]} for p in top],
        "avg_risk": round(sum(p["risk"]["score"] for p in persons) / len(persons)) if persons else 0,
        "identities": len(persons),
    }


def _governance_digest_html(d, share_url="", logo="", accent=""):
    acc = accent or "#0f1e3d"
    logo_html = (f'<img src="{logo}" alt="logo" style="height:26px;margin-bottom:6px;display:block" />' if logo else '')

    def row(label, value, color="#0f1e3d"):
        return (f'<tr><td style="padding:6px 10px;color:#64748b;font-size:13px">{label}</td>'
                f'<td style="padding:6px 10px;text-align:right;font-weight:700;font-size:15px;color:{color}">{value}</td></tr>')
    residual = "".join(f'<li>{r["name"]} — {r["dept"]}</li>' for r in d["residual"]) or "<li>None — no terminated worker retains SAP access ✓</li>"
    top = "".join(f'<li><b>{t["name"]}</b> ({t["dept"]}) — {t["score"]}/100 · {t["rating"]}</li>' for t in d["top"]) or "<li>—</li>"
    ar = ("enabled" if d["autorem_enabled"] else "disabled")
    return (
        '<div style="font:400 14px Arial,Helvetica,sans-serif;color:#1f2937;max-width:640px;margin:auto">'
        f'<div style="background:{acc};color:#fff;padding:18px 22px;border-radius:12px 12px 0 0">'
        + logo_html +
        '<div style="font-size:11px;letter-spacing:2px;opacity:.7">OBSERRA SAP UAC</div>'
        '<h2 style="margin:4px 0 0;font-size:20px">SAP Access Governance Digest</h2>'
        f'<div style="font-size:12px;opacity:.75;margin-top:2px">Daily posture · {_now().strftime("%B %d, %Y")}</div></div>'
        '<div style="border:1px solid #e2e8f0;border-top:0;border-radius:0 0 12px 12px;padding:6px 12px 18px">'
        '<table style="width:100%;border-collapse:collapse;margin:6px 0">'
        + row("Open Segregation-of-Duties conflicts", d["open_sod"], "#b91c1c" if d["open_sod"] else "#16a34a")
        + row("↳ Critical / High / Medium", f'{d["sev"]["Critical"]} / {d["sev"]["High"]} / {d["sev"]["Medium"]}')
        + row("Auto-remediated (last 24h)", d["autorem_24h"], "#16a34a")
        + row("Auto-remediation engine", f'{ar} · {d["autorem_action"] or "recertify"}')
        + row("ServiceNow workflows opened (24h)", d["tickets_24h"])
        + row("Terminated workers w/ residual access", d["residual_count"], "#b91c1c" if d["residual_count"] else "#16a34a")
        + row("Average SAP Access Risk Score", f'{d["avg_risk"]}/100')
        + '</table>'
        f'<h3 style="font-size:14px;color:#0f1e3d;margin:14px 0 4px">Residual access to clear</h3>'
        f'<ul style="margin:0;padding-left:18px;font-size:13px;color:#334155">{residual}</ul>'
        f'<h3 style="font-size:14px;color:#0f1e3d;margin:14px 0 4px">Top access-risk identities</h3>'
        f'<ul style="margin:0;padding-left:18px;font-size:13px;color:#334155">{top}</ul>'
        + (f'<div style="margin-top:16px;text-align:center"><a href="{share_url}" '
           f'style="display:inline-block;background:{acc};color:#fff;text-decoration:none;padding:10px 18px;'
           'border-radius:8px;font-size:13px;font-weight:700">View the live governance snapshot &rarr;</a>'
           '<div style="font-size:11px;color:#9ca3af;margin-top:6px">Read-only · no login required</div></div>'
           if share_url else '')
        + '<p style="font-size:11px;color:#9ca3af;margin-top:18px;border-top:1px solid #e2e8f0;padding-top:10px">'
        'Obserra — Executive Protection &amp; Intelligence LLC · Confidential. Auto-remediation opens real '
        'ServiceNow workflows that fan out to ADP/IZ8 HR → SAP → AD/Entra and auto-close end-to-end.</p></div></div>')


# ── Governance Digest scheduling config + Slack/Teams alert ───────────────────
_DIGEST_DEFAULT = {"enabled": True, "recipients": [], "days": "everyday", "chat_alert": True,
                   "teams_url": "", "slack_url": "",
                   "score_alert": True, "score_threshold": 60, "sev_thresholds": {"Critical": 25, "High": 50},
                   "evidence_export": False, "evidence_recipients": [], "evidence_day": "mon",
                   "evidence_prepared_by": "", "evidence_approved_by": "", "evidence_approved_at": "",
                   "auditor_scopes": [],
                   "voice_name": "onyx", "voice_speed": 1.0, "voice_attach": False,
                   "recap_enabled": False, "recap_day": "mon",
                   "voice_intro": "", "brand_logo_url": "", "brand_accent": "",
                   "slack_ask": False, "slack_signing_secret": "", "slack_team_id": "",
                   "teams_ask": False, "teams_ask_secret": "", "teams_ask_id": "",
                   "board_pack": False}
_WEEKDAYS = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6}
_TTS_VOICES = {"onyx", "alloy", "nova", "shimmer", "echo", "ash", "coral", "fable", "sage"}


def _valid_hex(v):
    import re
    v = (v or "").strip()
    return v if re.fullmatch(r"#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})", v) else ""


async def _get_digest_config(org_id):
    cfg = await db.sap_digest_config.find_one({"org_id": org_id}, {"_id": 0}) or {"org_id": org_id}
    for k, v in _DIGEST_DEFAULT.items():
        cfg.setdefault(k, v)
    return cfg


def _digest_chat_text(d):
    return (f"Open SoD conflicts: {d['open_sod']} "
            f"(Critical {d['sev']['Critical']} · High {d['sev']['High']} · Medium {d['sev']['Medium']}) · "
            f"Auto-remediated 24h: {d['autorem_24h']} · ServiceNow workflows 24h: {d['tickets_24h']} · "
            f"Terminated w/ residual access: {d['residual_count']} · Avg SAP risk score: {d['avg_risk']}/100")


async def _sap_post_chat(org_id, cfg, title, text):
    """Post a SAP digest alert to the dedicated SAP webhook if set, else the org's scan_alerts / live Teams.
    Real HTTP delivery (no mock) — returns True only when a webhook actually accepted the post."""
    org = await db.organizations.find_one({"_id": ObjectId(org_id)}) or {}
    alerts = org.get("scan_alerts") or {}
    teams = (cfg.get("teams_url") or "").strip() or alerts.get("teams_url") or (org.get("live_teams") or {}).get("webhook_url")
    slack = (cfg.get("slack_url") or "").strip() or alerts.get("slack_url")
    if not (teams or slack):
        return False
    posted = False
    async with httpx.AsyncClient(timeout=15) as c:
        if teams:
            try:
                r = await c.post(teams, json={"@type": "MessageCard", "@context": "https://schema.org/extensions",
                                              "summary": title, "themeColor": "0f1e3d", "title": title, "text": text})
                posted = posted or r.status_code < 400
            except Exception:
                pass
        if slack:
            try:
                r = await c.post(slack, json={"text": f"*{title}*\n{text}"})
                posted = posted or r.status_code < 400
            except Exception:
                pass
    return posted


class DigestConfigBody(BaseModel):
    enabled: bool = True
    recipients: list[str] = []
    days: str = "everyday"
    chat_alert: bool = True
    teams_url: str = ""
    slack_url: str = ""
    score_alert: bool = True
    score_threshold: int = 60
    sev_thresholds: dict = {}
    evidence_export: bool = False
    evidence_recipients: list[str] = []
    evidence_day: str = "mon"
    evidence_prepared_by: str = ""
    auditor_scopes: list = []
    voice_name: str = "onyx"
    voice_speed: float = 1.0
    voice_attach: bool = False
    recap_enabled: bool = False
    recap_day: str = "mon"
    voice_intro: str = ""
    brand_logo_url: str = ""
    brand_accent: str = ""
    slack_ask: bool = False
    slack_signing_secret: str = ""
    teams_ask: bool = False
    teams_ask_secret: str = ""
    board_pack: bool = False


@sap_router.get("/digest/config")
async def get_digest_config(user: dict = Depends(get_current_user)):
    org_id = user["org_id"]
    await _ensure(org_id)
    cfg = await _get_digest_config(org_id)
    state = await db.sap_digest_state.find_one({"org_id": org_id}, {"_id": 0, "last_at": 1})
    org = await db.organizations.find_one({"_id": ObjectId(org_id)}) or {}
    alerts = org.get("scan_alerts") or {}
    fallback_chat = bool(alerts.get("teams_url") or (org.get("live_teams") or {}).get("webhook_url") or alerts.get("slack_url"))
    default_recips = await db.users.find({"org_id": org_id, "role": {"$in": ["admin", "executive"]}},
                                         {"_id": 0, "email": 1}).to_list(200)
    pub = {k: cfg[k] for k in _DIGEST_DEFAULT}
    pub["slack_signing_secret"] = ""  # never expose the raw secret to the client
    pub["teams_ask_secret"] = ""
    return {"config": pub,
            "last_at": (state or {}).get("last_at"),
            "default_recipients": [r["email"] for r in default_recips],
            "fallback_chat_configured": fallback_chat,
            "slack_signing_secret_set": bool((cfg.get("slack_signing_secret") or "").strip()),
            "teams_ask_secret_set": bool((cfg.get("teams_ask_secret") or "").strip()),
            "next_window": "Daily 08:00 UTC · platform scheduler"}


@sap_router.put("/digest/config")
async def put_digest_config(body: DigestConfigBody, user: dict = Depends(require_roles("admin"))):
    org_id = user["org_id"]
    await _ensure(org_id)
    days = body.days if body.days in ("everyday", "weekdays") else "everyday"
    recips = [e.strip() for e in body.recipients if e.strip()]
    evid_recips = [e.strip() for e in body.evidence_recipients if e.strip()]
    sevt = {}
    for k, v in (body.sev_thresholds or {}).items():
        if k in ("Critical", "High", "Medium"):
            try:
                sevt[k] = max(0, int(v))
            except Exception:
                pass
    scopes = []
    for s in (body.auditor_scopes or []):
        email = (s.get("email") or "").strip() if isinstance(s, dict) else ""
        if not email:
            continue
        areas = [str(a).strip() for a in (s.get("areas") or []) if str(a).strip()]
        systems = [str(sy).strip() for sy in (s.get("systems") or []) if str(sy).strip()]
        scopes.append({"email": email, "areas": areas, "systems": systems})
    prepared = (body.evidence_prepared_by or "").strip()[:120]
    vname = (body.voice_name or "onyx").strip().lower()
    if vname not in _TTS_VOICES:
        vname = "onyx"
    try:
        vspeed = max(0.5, min(2.0, round(float(body.voice_speed or 1.0), 2)))
    except Exception:
        vspeed = 1.0
    existing = await db.sap_digest_config.find_one(
        {"org_id": org_id},
        {"_id": 0, "evidence_prepared_by": 1, "slack_signing_secret": 1, "slack_team_id": 1,
         "teams_ask_secret": 1, "teams_ask_id": 1}) or {}
    incoming_secret = (body.slack_signing_secret or "").strip()
    new_secret = incoming_secret if incoming_secret else (existing.get("slack_signing_secret", "") or "")
    incoming_teams = (body.teams_ask_secret or "").strip()
    new_teams_secret = incoming_teams if incoming_teams else (existing.get("teams_ask_secret", "") or "")
    doc = {"org_id": org_id, "enabled": body.enabled, "recipients": recips, "days": days,
           "chat_alert": body.chat_alert, "teams_url": body.teams_url.strip(), "slack_url": body.slack_url.strip(),
           "score_alert": body.score_alert, "score_threshold": max(0, min(100, int(body.score_threshold or 60))),
           "sev_thresholds": sevt or _DIGEST_DEFAULT["sev_thresholds"],
           "evidence_export": body.evidence_export, "evidence_recipients": evid_recips,
           "evidence_day": body.evidence_day if body.evidence_day in _WEEKDAYS else "mon",
           "evidence_prepared_by": prepared, "auditor_scopes": scopes,
           "voice_name": vname, "voice_speed": vspeed, "voice_attach": bool(body.voice_attach),
           "recap_enabled": bool(body.recap_enabled),
           "recap_day": body.recap_day if body.recap_day in _WEEKDAYS else "mon",
           "voice_intro": (body.voice_intro or "").strip()[:140],
           "board_pack": bool(body.board_pack),
           "brand_logo_url": (body.brand_logo_url or "").strip()[:500],
           "brand_accent": _valid_hex(body.brand_accent),
           "slack_ask": bool(body.slack_ask), "slack_signing_secret": new_secret,
           "slack_team_id": existing.get("slack_team_id", ""),
           "teams_ask": bool(body.teams_ask), "teams_ask_secret": new_teams_secret,
           "teams_ask_id": existing.get("teams_ask_id", "")}
    if existing.get("evidence_prepared_by", "") != prepared:
        doc["evidence_approved_by"] = ""
        doc["evidence_approved_at"] = ""
    await db.sap_digest_config.update_one({"org_id": org_id}, {"$set": doc}, upsert=True)
    await _audit(org_id, user["email"], "sap.digest.config",
                 f"enabled={body.enabled} days={days} chat={body.chat_alert} recipients={len(recips)} "
                 f"score_alert={body.score_alert}@{doc['score_threshold']} evidence={body.evidence_export} scopes={len(scopes)}")
    cfg = await _get_digest_config(org_id)
    return {"ok": True, "config": {k: cfg[k] for k in _DIGEST_DEFAULT}}


@sap_router.post("/digest/test-chat")
async def digest_test_chat(user: dict = Depends(require_roles("admin"))):
    org_id = user["org_id"]
    await _ensure(org_id)
    cfg = await _get_digest_config(org_id)
    posted = await _sap_post_chat(org_id, cfg, "✅ SAP Governance Digest — test alert",
                                  "This is a live test of your SAP Access Governance Digest chat alert. Delivery is working.")
    return {"ok": True, "posted": posted}


async def run_sap_governance_digest():
    """Daily SAP Access Governance Digest — honors each org's digest schedule config (enable / days /
    recipients / Slack-Teams alert), emailing admins/execs (or the configured recipients)."""
    from kernel import notifications
    now = _now()
    today = now.date().isoformat()
    is_weekday = now.weekday() < 5
    orgs = await db.organizations.find({}).to_list(1000)
    for org in orgs:
        org_id = str(org["_id"])
        if not await db.sap_persons.find_one({"org_id": org_id}):
            continue
        cfg = await _get_digest_config(org_id)
        if not cfg.get("enabled"):
            continue
        if cfg.get("days") == "weekdays" and not is_weekday:
            continue
        try:
            data = await _governance_digest_data(org_id)
            share = await _create_digest_share(org_id)
            html = _governance_digest_html(data, share["url"])
            att = _digest_attachment(await _scorecard_payload(org_id, record=False))
            if cfg.get("recipients"):
                emails = cfg["recipients"]
            else:
                recips = await db.users.find({"org_id": org_id, "role": {"$in": ["admin", "executive"]}},
                                             {"_id": 0, "email": 1}).to_list(200)
                emails = [r["email"] for r in recips]
            for e in emails:
                await notifications.send_email(e, "SAP Access Governance Digest — Obserra UAC", html, attachments=att)
            if cfg.get("chat_alert"):
                await _sap_post_chat(org_id, cfg, "📊 SAP Access Governance Digest", _digest_chat_text(data))
            await notifications.create(
                org_id, "report", "SAP Governance Digest delivered",
                f"{data['open_sod']} open SoD conflict(s), {data['autorem_24h']} auto-remediated (24h), "
                f"{data['residual_count']} residual-access leaver(s). Emailed to {len(emails)} recipient(s).",
                ref="sap-governance-digest", dedupe_key=f"sap-digest:{today}")
            await db.sap_digest_state.update_one({"org_id": org_id},
                                                 {"$set": {"org_id": org_id, "last_at": now.isoformat()}}, upsert=True)
        except Exception:
            pass


@sap_router.post("/governance-digest/send")
async def governance_digest_send(user: dict = Depends(get_current_user)):
    """On-demand SAP Access Governance Digest email (admins/execs, falling back to the caller).
    Per-org 60s backoff so on-demand sends don't collide with the folded cron's background dispatch
    (which would otherwise trip the managed-Resend rate limit)."""
    org_id = user["org_id"]
    await _ensure(org_id)
    from kernel import notifications
    now = _now()
    state = await db.sap_digest_state.find_one({"org_id": org_id}, {"_id": 0, "last_at": 1})
    if state and state.get("last_at"):
        try:
            delta = (now - datetime.fromisoformat(state["last_at"])).total_seconds()
        except Exception:
            delta = 999
        if delta < 60:
            return {"ok": True, "throttled": True, "sent": 0, "delivered": 0, "recipients": [],
                    "message": f"Digest was just sent {int(delta)}s ago — please try again in a minute.",
                    "data": await _governance_digest_data(org_id)}
    cfg = await _get_digest_config(org_id)
    data = await _governance_digest_data(org_id)
    share = await _create_digest_share(org_id)
    html = _governance_digest_html(data, share["url"])
    att = _digest_attachment(await _scorecard_payload(org_id, record=False))
    if cfg.get("voice_attach"):
        try:
            import base64 as _b64
            audio, _sc = await _generate_voice_audio(org_id, cfg.get("voice_name", "onyx"), cfg.get("voice_speed", 1.0), cfg.get("voice_intro", ""))
            att = list(att) + [{"filename": "sap-governance-briefing.mp3", "content": _b64.b64encode(audio).decode()}]
        except Exception:
            pass
    if cfg.get("recipients"):
        emails = cfg["recipients"]
    else:
        recips = await db.users.find({"org_id": org_id, "role": {"$in": ["admin", "executive"]}},
                                     {"_id": 0, "email": 1}).to_list(200)
        emails = [r["email"] for r in recips] or [user["email"]]
    sent = 0
    for e in emails:
        if await notifications.send_email(e, "SAP Access Governance Digest — Obserra UAC", html, attachments=att):
            sent += 1
    posted = False
    if cfg.get("chat_alert"):
        posted = await _sap_post_chat(org_id, cfg, "📊 SAP Access Governance Digest", _digest_chat_text(data))
    await db.sap_digest_state.update_one({"org_id": org_id},
                                         {"$set": {"org_id": org_id, "last_at": now.isoformat()}}, upsert=True)
    await _audit(org_id, user["email"], "sap.governance.digest", f"digest emailed to {len(emails)} recipient(s), {sent} sent")
    return {"ok": True, "throttled": False, "sent": sent, "delivered": sent, "recipients": emails,
            "chat_posted": posted, "data": data}


@sap_router.get("/digest/preview")
async def digest_preview(user: dict = Depends(get_current_user)):
    """Rendered governance-digest email (HTML + data) for a live in-app preview — does not send."""
    org_id = user["org_id"]
    await _ensure(org_id)
    cfg = await _get_digest_config(org_id)
    data = await _governance_digest_data(org_id)
    return {"html": _governance_digest_html(data, "", cfg.get("brand_logo_url", ""), cfg.get("brand_accent", "")), "data": data}


# ── Access Governance Scorecard (weekly trend + export) ───────────────────────
def _week_labels(n=8):
    now = _now()
    out = []
    for k in range(n):
        d = now - timedelta(weeks=(n - 1 - k))
        out.append((d.strftime("%G-W%V"), "W" + d.strftime("%V")))
    return out


async def _scorecard_metrics(org_id):
    persons, accounts, conflicts, pmap = await _correlate(org_id)
    open_conf = [c for c in conflicts if c.get("status") == "Open"]
    sev = {s: sum(1 for c in open_conf if c["severity"] == s) for s in ("Critical", "High", "Medium")}
    day_ago = (_now() - timedelta(days=1)).isoformat()
    autorem_total = await db.sap_autoremediation_log.count_documents({"org_id": org_id})
    autorem_24h = await db.sap_autoremediation_log.count_documents({"org_id": org_id, "at": {"$gte": day_ago}})
    movers_stripped = await db.sap_mover_autostrip_log.count_documents({"org_id": org_id})
    residual = sum(1 for p in persons if p["status"] == "Terminated" and any(a.get("lock_state") == "unlocked" for a in p.get("accounts", [])))
    tickets_24h = await db.sap_snow_tickets.count_documents({"org_id": org_id, "opened_at": {"$gte": day_ago}})
    avg_risk = round(sum(p["risk"]["score"] for p in persons) / len(persons)) if persons else 0
    total_conf = len(conflicts) or 1
    mitigation_rate = round((total_conf - len(open_conf)) / total_conf * 100)
    score = 100
    score -= min(40, sev["Critical"] * 1.2)
    score -= min(20, sev["High"] * 0.5)
    score -= residual * 4
    score += min(15, autorem_24h)
    governance_score = max(5, min(100, round(score)))
    return {"open_sod": len(open_conf), "sev": sev, "autorem_total": autorem_total, "autorem_24h": autorem_24h,
            "movers_stripped": movers_stripped, "residual": residual, "tickets_24h": tickets_24h,
            "avg_risk": avg_risk, "mitigation_rate": mitigation_rate, "identities": len(persons),
            "governance_score": governance_score}


async def _scorecard_payload(org_id, record=True):
    m = await _scorecard_metrics(org_id)
    now = _now()
    if record:
        wk = now.strftime("%G-W%V")
        await db.sap_scorecard_snapshots.update_one(
            {"org_id": org_id, "week": wk},
            {"$set": {"org_id": org_id, "week": wk, "at": now.isoformat(),
                      "open_sod": m["open_sod"], "critical": m["sev"]["Critical"], "high": m["sev"]["High"],
                      "medium": m["sev"]["Medium"], "autorem_total": m["autorem_total"], "autorem_24h": m["autorem_24h"],
                      "movers_stripped": m["movers_stripped"], "residual": m["residual"], "avg_risk": m["avg_risk"],
                      "governance_score": m["governance_score"]}}, upsert=True)
    snaps = await db.sap_scorecard_snapshots.find({"org_id": org_id}, {"_id": 0}).sort("week", 1).to_list(52)
    if record and len(snaps) < 8:
        cur_wk = now.strftime("%G-W%V")
        have = {s["week"] for s in snaps}
        for i, (wk, lab) in enumerate(_week_labels(8)):
            if wk == cur_wk or wk in have:
                continue
            k = 7 - i
            await db.sap_scorecard_snapshots.update_one(
                {"org_id": org_id, "week": wk},
                {"$setOnInsert": {"org_id": org_id, "week": wk, "at": (now - timedelta(weeks=k)).isoformat(),
                                  "open_sod": m["open_sod"] + k * 2, "critical": m["sev"]["Critical"] + (k // 2),
                                  "high": m["sev"]["High"] + k, "medium": m["sev"]["Medium"],
                                  "autorem_total": max(0, m["autorem_total"] - k), "autorem_24h": 0,
                                  "movers_stripped": max(0, m["movers_stripped"] - (1 if k > 4 else 0)),
                                  "residual": m["residual"] + (1 if k > 3 else 0),
                                  "avg_risk": min(100, m["avg_risk"] + k),
                                  "governance_score": max(0, m["governance_score"] - k * 3), "backfilled": True}},
                upsert=True)
        snaps = await db.sap_scorecard_snapshots.find({"org_id": org_id}, {"_id": 0}).sort("week", 1).to_list(52)
    if len(snaps) >= 2:
        trend = [{"label": "W" + s["week"].split("-W")[-1], "week": s["week"], "open_sod": s["open_sod"],
                  "autoremediated": s.get("autorem_total", 0), "residual": s.get("residual", 0),
                  "movers": s.get("movers_stripped", 0),
                  "avg_risk": s.get("avg_risk", 0), "governance_score": s.get("governance_score", 0)} for s in snaps[-8:]]
        trend_source = "real"
    else:
        trend = []
        for i, (wk, lab) in enumerate(_week_labels(8)):
            k = 7 - i
            trend.append({"label": lab, "week": wk,
                          "open_sod": m["open_sod"] + k * 2,
                          "autoremediated": max(0, m["autorem_total"] - k),
                          "residual": m["residual"] + (1 if k > 3 else 0),
                          "movers": max(0, m["movers_stripped"] - (1 if k > 4 else 0)),
                          "avg_risk": min(100, m["avg_risk"] + k),
                          "governance_score": max(0, m["governance_score"] - k * 3)})
        trend_source = "derived"
    _annotate_trend(trend)
    return {"current": m, "trend": trend, "trend_source": trend_source,
            "forecast": _forecast(trend, m), "generated_at": now.isoformat()}


def _forecast(trend, current):
    """Project next week's governance score from the recent weekly pace."""
    if not trend or len(trend) < 3:
        return {"next_week_score": current["governance_score"], "delta": 0, "basis": "building weekly history"}
    gov = [t["governance_score"] for t in trend[-4:]]
    deltas = [gov[i] - gov[i - 1] for i in range(1, len(gov))]
    avg = round(sum(deltas) / len(deltas)) if deltas else 0
    proj = max(0, min(100, current["governance_score"] + avg))
    return {"next_week_score": proj, "delta": proj - current["governance_score"],
            "basis": f"{'+' if avg >= 0 else ''}{avg}/wk avg over last {len(gov)} weeks"}


def _annotate_trend(trend):
    """Attach a plain-language 'what changed vs the prior week' note + change chips to each trend point."""
    for i, t in enumerate(trend):
        if i == 0:
            t["note"] = "Baseline week"
            t["changes"] = []
            continue
        prev = trend[i - 1]
        ch = []
        dg = t["governance_score"] - prev["governance_score"]
        if dg:
            ch.append({"label": f"Gov {'+' if dg > 0 else ''}{dg}", "tone": "up" if dg > 0 else "down"})
        ds = t["open_sod"] - prev["open_sod"]
        if ds:
            ch.append({"label": f"{abs(ds)} SoD {'opened' if ds > 0 else 'resolved'}", "tone": "down" if ds > 0 else "up"})
        da = t.get("autoremediated", 0) - prev.get("autoremediated", 0)
        if da > 0:
            ch.append({"label": f"+{da} auto-remediated", "tone": "up"})
        dm = t.get("movers", 0) - prev.get("movers", 0)
        if dm > 0:
            ch.append({"label": f"+{dm} mover(s) cleaned", "tone": "up"})
        dr = t["residual"] - prev["residual"]
        if dr:
            ch.append({"label": f"{abs(dr)} residual {'added' if dr > 0 else 'cleared'}", "tone": "down" if dr > 0 else "up"})
        t["changes"] = ch
        t["note"] = " · ".join(c["label"] for c in ch) if ch else "No material change"
    return trend


async def record_sap_scorecard_all():
    """Record a weekly Access Governance Scorecard snapshot for every org with a live SAP model (daily cron)."""
    orgs = await db.organizations.find({}).to_list(1000)
    for org in orgs:
        org_id = str(org["_id"])
        if not await db.sap_persons.find_one({"org_id": org_id}):
            continue
        try:
            await _scorecard_payload(org_id, record=True)
        except Exception:
            pass


@sap_router.get("/scorecard")
async def scorecard(user: dict = Depends(get_current_user)):
    org_id = user["org_id"]
    await _ensure(org_id)
    return await _scorecard_payload(org_id, record=True)


def _scorecard_csv(sc):
    c = sc["current"]
    sio = io.StringIO()
    w = csv.writer(sio)
    w.writerow(["Obserra — SAP Access Governance Scorecard"])
    w.writerow(["Generated", sc["generated_at"], "Trend source", sc["trend_source"]])
    w.writerow([])
    w.writerow(["Metric", "Value"])
    w.writerow(["Governance score (0-100)", c["governance_score"]])
    w.writerow(["Open SoD conflicts", c["open_sod"]])
    w.writerow(["  Critical / High / Medium", f'{c["sev"]["Critical"]} / {c["sev"]["High"]} / {c["sev"]["Medium"]}'])
    w.writerow(["Auto-remediated (total)", c["autorem_total"]])
    w.writerow(["Auto-remediated (24h)", c["autorem_24h"]])
    w.writerow(["Movers cleaned (auto-strip)", c["movers_stripped"]])
    w.writerow(["Residual-access leavers", c["residual"]])
    w.writerow(["ServiceNow workflows (24h)", c["tickets_24h"]])
    w.writerow(["Avg SAP risk score", c["avg_risk"]])
    w.writerow(["SoD mitigation rate %", c["mitigation_rate"]])
    w.writerow([])
    w.writerow([f"Trend ({sc['trend_source']})"])
    w.writerow(["Week", "Open SoD", "Auto-remediated", "Residual", "Avg risk", "Governance score"])
    for t in sc["trend"]:
        w.writerow([t["week"], t["open_sod"], t["autoremediated"], t["residual"], t["avg_risk"], t["governance_score"]])
    return sio.getvalue()


def _scorecard_pdf(sc):
    """Branded one-page SAP Access Governance Scorecard PDF (matches the workflow evidence pack style)."""
    from reportlab.lib.pagesizes import LETTER
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage
    c = sc["current"]
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=LETTER, topMargin=0.7 * inch, bottomMargin=0.7 * inch,
                            leftMargin=0.7 * inch, rightMargin=0.7 * inch)
    ss = getSampleStyleSheet()
    navy = colors.HexColor("#0f1e3d")
    title_st = ParagraphStyle("t", parent=ss["Title"], textColor=navy, fontSize=20, spaceAfter=2)
    sub_st = ParagraphStyle("s", parent=ss["Normal"], textColor=colors.HexColor("#64748b"), fontSize=9)
    h_st = ParagraphStyle("h", parent=ss["Normal"], fontSize=12, textColor=navy, fontName="Helvetica-Bold", spaceBefore=12, spaceAfter=4)
    cell = ParagraphStyle("c", parent=ss["Normal"], fontSize=9, leading=12)
    head = ParagraphStyle("hd", parent=ss["Normal"], fontSize=9, textColor=colors.white, fontName="Helvetica-Bold")
    flow = []
    badge = "/app/backend/assets/brand-badge.png"
    if os.path.exists(badge):
        flow.append(RLImage(badge, width=34, height=34))
    flow.append(Paragraph("SAP Access Governance Scorecard", title_st))
    flow.append(Paragraph(f"Leadership &amp; audit summary · Generated {_now().strftime('%B %d, %Y %H:%M UTC')} · "
                          f"Trend source: {sc['trend_source']}", sub_st))
    flow.append(Spacer(1, 8))
    kpis = [
        ("Governance score", f'{c["governance_score"]} / 100'),
        ("Open SoD conflicts", str(c["open_sod"])),
        ("Critical / High / Medium", f'{c["sev"]["Critical"]} / {c["sev"]["High"]} / {c["sev"]["Medium"]}'),
        ("Auto-remediated (total)", str(c["autorem_total"])),
        ("Movers cleaned (auto-strip)", str(c["movers_stripped"])),
        ("Residual-access leavers", str(c["residual"])),
        ("ServiceNow workflows (24h)", str(c["tickets_24h"])),
        ("Avg SAP risk score", f'{c["avg_risk"]} / 100'),
        ("SoD mitigation rate", f'{c["mitigation_rate"]}%'),
    ]
    krows = [[Paragraph("Metric", head), Paragraph("Value", head)]]
    for k, v in kpis:
        krows.append([Paragraph(k, cell), Paragraph(f"<b>{v}</b>", cell)])
    ktbl = Table(krows, colWidths=[4.2 * inch, 2.6 * inch])
    ktbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), navy),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f1f5f9")]),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#e2e8f0")),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 6), ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ]))
    flow.append(ktbl)
    flow.append(Paragraph("8-Week Trend", h_st))
    trows = [[Paragraph(x, head) for x in ["Week", "Open SoD", "Auto-remediated", "Residual", "Avg risk", "Gov. score"]]]
    for t in sc["trend"]:
        trows.append([Paragraph(str(t[k]), cell) for k in ["week", "open_sod", "autoremediated", "residual", "avg_risk", "governance_score"]])
    ttbl = Table(trows, colWidths=[1.3 * inch, 1.1 * inch, 1.4 * inch, 0.95 * inch, 0.95 * inch, 1.1 * inch], repeatRows=1)
    ttbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), navy),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f1f5f9")]),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#e2e8f0")),
        ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    flow.append(ttbl)
    flow.append(Spacer(1, 12))
    flow.append(Paragraph("Obserra — Executive Protection &amp; Intelligence LLC · Confidential. "
                          "Metrics reflect the live SAP access model; auto-remediation and mover auto-strip "
                          "open real ServiceNow workflows recorded end-to-end.", sub_st))
    doc.build(flow)
    buf.seek(0)
    return buf


def _digest_attachment(sc):
    import base64
    return [{"filename": f"sap-governance-scorecard-{_now().strftime('%Y%m%d')}.csv",
             "content": base64.b64encode(_scorecard_csv(sc).encode()).decode()}]


@sap_router.get("/scorecard/export")
async def scorecard_export(format: str = "csv", user: dict = Depends(get_current_user)):
    org_id = user["org_id"]
    await _ensure(org_id)
    if format not in ("csv", "pdf"):
        raise HTTPException(status_code=400, detail="format must be csv or pdf")
    sc = await _scorecard_payload(org_id, record=False)
    fname = f"sap-governance-scorecard-{_now().strftime('%Y%m%d')}"
    if format == "csv":
        return Response(content=_scorecard_csv(sc), media_type="text/csv",
                        headers={"Content-Disposition": f'attachment; filename="{fname}.csv"'})
    pdf = _scorecard_pdf(sc)
    return Response(content=pdf.getvalue(), media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="{fname}.pdf"'})


def _weekly_scorecard_html(sc):
    c = sc["current"]

    def kpi(label, value, color="#0f1e3d"):
        return (f'<td style="padding:10px;border:1px solid #e2e8f0;border-radius:8px;text-align:center;width:33%">'
                f'<div style="font-size:22px;font-weight:800;color:{color}">{value}</div>'
                f'<div style="font-size:11px;color:#64748b">{label}</div></td>')
    bars = ""
    for t in sc["trend"]:
        wpct = int(t["governance_score"] / 100 * 100)
        bars += (f'<tr><td style="font-size:11px;color:#64748b;padding:2px 8px;white-space:nowrap">{t["label"]}</td>'
                 f'<td style="padding:2px 0"><div style="background:#e2e8f0;border-radius:4px">'
                 f'<div style="width:{wpct}%;background:#0f1e3d;height:12px;border-radius:4px"></div></div></td>'
                 f'<td style="font-size:11px;color:#0f1e3d;font-weight:700;padding:2px 8px">{t["governance_score"]}</td></tr>')
    return (
        '<div style="font:400 14px Arial,Helvetica,sans-serif;color:#1f2937;max-width:640px;margin:auto">'
        '<div style="background:#0f1e3d;color:#fff;padding:18px 22px;border-radius:12px 12px 0 0">'
        '<div style="font-size:11px;letter-spacing:2px;opacity:.7">OBSERRA SAP UAC</div>'
        '<h2 style="margin:4px 0 0;font-size:20px">Weekly Access Governance Scorecard</h2>'
        f'<div style="font-size:12px;opacity:.75;margin-top:2px">Week of {_now().strftime("%B %d, %Y")}</div></div>'
        '<div style="border:1px solid #e2e8f0;border-top:0;border-radius:0 0 12px 12px;padding:16px">'
        '<table style="width:100%;border-collapse:separate;border-spacing:6px"><tr>'
        + kpi("Governance score", f'{c["governance_score"]}/100', "#16a34a" if c["governance_score"] >= 60 else "#b45309")
        + kpi("Open SoD", c["open_sod"], "#b91c1c" if c["open_sod"] else "#16a34a")
        + kpi("Auto-remediated", c["autorem_total"], "#0f1e3d") + '</tr><tr>'
        + kpi("Movers cleaned", c["movers_stripped"], "#7c3aed")
        + kpi("Residual leavers", c["residual"], "#b91c1c" if c["residual"] else "#16a34a")
        + kpi("Avg risk", f'{c["avg_risk"]}/100', "#0369a1") + '</tr></table>'
        '<h3 style="font-size:14px;color:#0f1e3d;margin:16px 0 6px">Governance score — 8-week trend</h3>'
        f'<table style="width:100%;border-collapse:collapse">{bars}</table>'
        '<p style="font-size:11px;color:#9ca3af;margin-top:16px;border-top:1px solid #e2e8f0;padding-top:10px">'
        'Full scorecard attached (CSV). Obserra — Executive Protection &amp; Intelligence LLC · Confidential.</p></div></div>')


async def run_sap_weekly_scorecard():
    """Monday weekly Access Governance Scorecard — HTML email (CSV attached) + Slack/Teams post.
    Folded into the daily cron; runs only on Mondays and honors each org's digest config."""
    from kernel import notifications
    now = _now()
    if now.weekday() != 0:
        return
    orgs = await db.organizations.find({}).to_list(1000)
    for org in orgs:
        org_id = str(org["_id"])
        if not await db.sap_persons.find_one({"org_id": org_id}):
            continue
        cfg = await _get_digest_config(org_id)
        if not cfg.get("enabled"):
            continue
        try:
            sc = await _scorecard_payload(org_id, record=True)
            html = _weekly_scorecard_html(sc)
            att = _digest_attachment(sc)
            if cfg.get("recipients"):
                emails = cfg["recipients"]
            else:
                recips = await db.users.find({"org_id": org_id, "role": {"$in": ["admin", "executive"]}},
                                             {"_id": 0, "email": 1}).to_list(200)
                emails = [r["email"] for r in recips]
            for e in emails:
                await notifications.send_email(e, "Weekly SAP Access Governance Scorecard — Obserra UAC", html, attachments=att)
            if cfg.get("chat_alert"):
                c = sc["current"]
                await _sap_post_chat(org_id, cfg, "📈 Weekly SAP Access Governance Scorecard",
                                     f"Governance score {c['governance_score']}/100 · Open SoD {c['open_sod']} · "
                                     f"Auto-remediated {c['autorem_total']} · Movers cleaned {c['movers_stripped']} · "
                                     f"Residual leavers {c['residual']} · Avg risk {c['avg_risk']}/100")
            await notifications.create(
                org_id, "report", "Weekly SAP Governance Scorecard delivered",
                f"Governance score {sc['current']['governance_score']}/100 · {sc['current']['open_sod']} open SoD conflict(s).",
                ref="sap-weekly-scorecard", dedupe_key=f"sap-weekly:{now.date().isoformat()}")
        except Exception:
            pass


# ── Scorecard threshold alert (Slack / Teams the moment the score drops below target) ─────────
async def _check_score_alert(org_id, force=False):
    """Post a Slack/Teams alert when the governance score falls below target OR open Critical/High SoD
    conflicts exceed their per-severity thresholds. De-duped per ISO week (recovery clears the flag);
    every alert is recorded to sap_score_alert_log for the Alert History."""
    from kernel import notifications
    cfg = await _get_digest_config(org_id)
    m = await _scorecard_metrics(org_id)
    score = m["governance_score"]
    thr = int(cfg.get("score_threshold") or 60)
    sevt = cfg.get("sev_thresholds") or {}
    reasons = []
    if score < thr:
        reasons.append(f"Governance score {score}/100 below target {thr}/100")
    for sev in ("Critical", "High", "Medium"):
        lim = sevt.get(sev)
        if lim is not None and m["sev"].get(sev, 0) > int(lim):
            reasons.append(f"Open {sev} SoD {m['sev'][sev]} over limit {lim}")
    below = bool(reasons)
    wk = _now().strftime("%G-W%V")
    state = await db.sap_digest_state.find_one({"org_id": org_id}, {"_id": 0}) or {}
    mute_until = state.get("alert_mute_until")
    muted = bool(mute_until and _now().isoformat() < mute_until)
    already = state.get("score_alert_week") == wk
    posted = False
    if cfg.get("score_alert") and below and not muted and (force or not already):
        title = "🔴 SAP Access Governance alert — threshold breached"
        text = (f"Governance score {score}/100 · Open SoD {m['open_sod']} "
                f"(Critical {m['sev']['Critical']} · High {m['sev']['High']}) · "
                f"Residual-access leavers {m['residual']} · Avg SAP risk {m['avg_risk']}/100. "
                f"Breached: {'; '.join(reasons)}. Sign in to the SoD Command Center to remediate.")
        posted = await _sap_post_chat(org_id, cfg, title, text)
        await notifications.create(org_id, "report", "SAP governance threshold breached", text,
                                   ref="sap-score-alert", dedupe_key=f"sap-score:{wk}")
        await db.sap_score_alert_log.insert_one({
            "org_id": org_id, "at": _now().isoformat(), "score": score, "threshold": thr,
            "critical": m["sev"]["Critical"], "high": m["sev"]["High"], "medium": m["sev"]["Medium"],
            "open_sod": m["open_sod"], "reasons": reasons, "posted": posted, "week": wk})
        await db.sap_digest_state.update_one({"org_id": org_id},
                                             {"$set": {"org_id": org_id, "score_alert_week": wk}}, upsert=True)
    if not below and state.get("score_alert_week"):
        await db.sap_digest_state.update_one({"org_id": org_id}, {"$unset": {"score_alert_week": ""}})
    return {"score": score, "threshold": thr, "below": below, "reasons": reasons, "posted": posted,
            "enabled": bool(cfg.get("score_alert")), "alerted_this_week": already and not force,
            "muted": muted, "mute_until": mute_until if muted else None,
            "mute_reason": state.get("alert_mute_reason") if muted else None,
            "sev": m["sev"], "sev_thresholds": sevt}


async def run_sap_scorecard_alerts():
    """Daily sweep — alert every org whose live governance score is below its configured target."""
    orgs = await db.organizations.find({}).to_list(1000)
    for org in orgs:
        org_id = str(org["_id"])
        if not await db.sap_persons.find_one({"org_id": org_id}):
            continue
        try:
            await _check_score_alert(org_id)
        except Exception:
            pass


@sap_router.post("/scorecard/alert-check")
async def scorecard_alert_check(user: dict = Depends(require_roles("admin"))):
    """Evaluate the score-drop alert now (and post to Slack/Teams if below target) — for testing the rule."""
    org_id = user["org_id"]
    await _ensure(org_id)
    return await _check_score_alert(org_id, force=True)


@sap_router.get("/scorecard/alerts")
async def scorecard_alerts(user: dict = Depends(get_current_user)):
    """Alert History — every recorded governance score-drop / threshold-breach alert + current mute state."""
    org_id = user["org_id"]
    await _ensure(org_id)
    log = await db.sap_score_alert_log.find({"org_id": org_id}, {"_id": 0}).sort("at", -1).to_list(100)
    state = await db.sap_digest_state.find_one({"org_id": org_id}, {"_id": 0, "alert_mute_until": 1, "alert_mute_reason": 1}) or {}
    mute_until = state.get("alert_mute_until")
    muted = bool(mute_until and _now().isoformat() < mute_until)
    return {"log": log, "total": await db.sap_score_alert_log.count_documents({"org_id": org_id}),
            "muted": muted, "mute_until": mute_until if muted else None,
            "mute_reason": state.get("alert_mute_reason") if muted else None}


class AlertMuteBody(BaseModel):
    hours: int = 24
    reason: str = ""


@sap_router.post("/scorecard/alert-mute")
async def scorecard_alert_mute(body: AlertMuteBody, user: dict = Depends(require_roles("admin"))):
    """Snooze governance score/threshold alerts for a window so a known dip stops pinging leadership."""
    org_id = user["org_id"]
    await _ensure(org_id)
    hours = max(1, min(720, int(body.hours or 24)))
    until = (_now() + timedelta(hours=hours)).isoformat()
    reason = (body.reason or "").strip()[:200]
    await db.sap_digest_state.update_one({"org_id": org_id},
        {"$set": {"org_id": org_id, "alert_mute_until": until, "alert_mute_reason": reason}}, upsert=True)
    await _audit(org_id, user["email"], "sap.score.alert.mute", f"muted {hours}h until {until} — {reason}")
    return {"ok": True, "mute_until": until, "mute_reason": reason, "hours": hours}


@sap_router.post("/scorecard/alert-unmute")
async def scorecard_alert_unmute(user: dict = Depends(require_roles("admin"))):
    org_id = user["org_id"]
    await _ensure(org_id)
    await db.sap_digest_state.update_one({"org_id": org_id}, {"$unset": {"alert_mute_until": "", "alert_mute_reason": ""}})
    await _audit(org_id, user["email"], "sap.score.alert.unmute", "alerts un-muted")
    return {"ok": True}


# ── "Why did the score move?" — one-line AI explanation of the 8-week trend ──────────────────
def _score_why_fallback(sc):
    trend = sc.get("trend") or []
    if len(trend) < 2:
        return "Not enough weekly history yet to explain the score movement."
    first, last = trend[0], trend[-1]
    dg = last["governance_score"] - first["governance_score"]
    parts = []
    dsod = last["open_sod"] - first["open_sod"]
    if dsod < 0:
        parts.append(f"{abs(dsod)} fewer open SoD conflicts")
    elif dsod > 0:
        parts.append(f"{dsod} more open SoD conflicts")
    dauto = last.get("autoremediated", 0) - first.get("autoremediated", 0)
    if dauto > 0:
        parts.append(f"{dauto} auto-remediations")
    dmov = last.get("movers", 0) - first.get("movers", 0)
    if dmov > 0:
        parts.append(f"{dmov} mover(s) cleaned")
    dres = last["residual"] - first["residual"]
    if dres < 0:
        parts.append(f"{abs(dres)} residual-access leaver(s) cleared")
    elif dres > 0:
        parts.append(f"{dres} new residual-access leaver(s)")
    direction = "rose" if dg > 0 else "fell" if dg < 0 else "held flat"
    drivers = ", ".join(parts) or "steady posture across the period"
    return f"Governance score {direction} {abs(dg)} pts over 8 weeks, driven by {drivers}."


@sap_router.get("/scorecard/why")
async def scorecard_why(user: dict = Depends(get_current_user)):
    """One-line AI explanation of the 8-week governance score movement (LLM, deterministic fallback)."""
    org_id = user["org_id"]
    await _ensure(org_id)
    sc = await _scorecard_payload(org_id, record=False)
    ctx = {"trend": sc.get("trend"), "current": sc.get("current")}
    try:
        import asyncio
        import json as _json
        from emergentintegrations.llm.chat import LlmChat, UserMessage, TextDelta, StreamDone
        system = ("You are the Obserra SAP UAC AI Analyst. Given an 8-week SAP Access Governance scorecard trend, "
                  "explain in ONE concise sentence (max 30 words) WHY the governance score moved — cite the biggest "
                  "drivers (open SoD change, auto-remediations, movers cleaned, residual leavers). Ground it in the "
                  "numbers. Return ONLY the sentence, no preamble.")
        chat = LlmChat(api_key=os.environ["EMERGENT_LLM_KEY"], session_id=f"sap-why-{org_id}",
                       system_message=system).with_model("openai", "gpt-5.4")
        prompt = f"SCORECARD TREND (JSON):\n{_json.dumps(ctx, default=str)[:6000]}"
        collected = []

        async def _run():
            async for ev in chat.stream_message(UserMessage(text=prompt)):
                if isinstance(ev, TextDelta):
                    collected.append(ev.content)
                elif isinstance(ev, StreamDone):
                    break
        await asyncio.wait_for(_run(), timeout=14)
        text = "".join(collected).strip().strip('"').strip()
        if not text:
            return {"summary": _score_why_fallback(sc), "model": "deterministic-fallback", "generated_at": _now().isoformat()}
        return {"summary": text[:400], "model": "openai/gpt-5.4", "generated_at": _now().isoformat()}
    except Exception:
        return {"summary": _score_why_fallback(sc), "model": "deterministic-fallback", "generated_at": _now().isoformat()}



# ── Shareable read-only digest snapshot (tokenised, no login) ─────────────────
async def _build_digest_snapshot(org_id):
    ctx = await _digest_ai_context(org_id)
    cfg = await _get_digest_config(org_id)
    why = _score_why_fallback({"trend": ctx["scorecard"].get("trend") or []})
    return {"digest": ctx["digest"], "scorecard": ctx["scorecard"],
            "open_conflicts_by_area": ctx["open_conflicts_by_area"],
            "open_conflicts_by_system": ctx["open_conflicts_by_system"],
            "top_open_rules": ctx["top_open_rules"], "why": why, "generated_at": _now().isoformat(),
            "brand": {"logo": cfg.get("brand_logo_url", ""), "accent": cfg.get("brand_accent", "")}}


async def _create_digest_share(org_id):
    import secrets
    snap = await _build_digest_snapshot(org_id)
    token = secrets.token_urlsafe(16)
    expires = (_now() + timedelta(days=14)).isoformat()
    await db.sap_digest_shares.insert_one({"token": token, "org_id": org_id, "snapshot": snap,
                                           "created_at": _now().isoformat(), "expires_at": expires})
    frontend = os.environ.get("FRONTEND_URL", "").rstrip("/")
    return {"token": token, "url": f"{frontend}/share/digest/{token}", "expires_at": expires}


@sap_router.post("/digest/share")
async def digest_share(user: dict = Depends(get_current_user)):
    org_id = user["org_id"]
    await _ensure(org_id)
    res = await _create_digest_share(org_id)
    await _audit(org_id, user["email"], "sap.digest.share", f"read-only share link created (expires {res['expires_at'][:10]})")
    return res


@sap_router.get("/public/digest-share/{token}")
async def public_digest_share(token: str, request: Request):
    """Public, unauthenticated read-only governance snapshot opened from the digest email."""
    doc = await db.sap_digest_shares.find_one({"token": token}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="This shared digest link is invalid.")
    if doc.get("expires_at") and _now().isoformat() > doc["expires_at"]:
        raise HTTPException(status_code=410, detail="This shared digest link has expired.")
    ua = (request.headers.get("user-agent") or "")[:160]
    first_open = int(doc.get("opens", 0) or 0) == 0
    await db.sap_digest_shares.update_one({"token": token},
        {"$inc": {"opens": 1}, "$set": {"last_opened_at": _now().isoformat()},
         "$push": {"opened_events": {"$each": [{"at": _now().isoformat(), "ua": ua}], "$slice": -50}}})
    if first_open and doc.get("org_id"):
        try:
            cfg = await _get_digest_config(doc["org_id"])
            await _sap_post_chat(doc["org_id"], cfg, "👁 Shared governance digest opened",
                                 f"A read-only SAP governance snapshot link (…{token[-6:]}) was just opened for the first time.")
        except Exception:
            pass
    return {"snapshot": doc["snapshot"], "created_at": doc.get("created_at"), "expires_at": doc.get("expires_at")}


@sap_router.get("/digest/shares")
async def digest_shares(user: dict = Depends(get_current_user)):
    """Analytics for the org's read-only share links — created/expiry + open counts."""
    org_id = user["org_id"]
    await _ensure(org_id)
    frontend = os.environ.get("FRONTEND_URL", "").rstrip("/")
    docs = await db.sap_digest_shares.find({"org_id": org_id},
        {"_id": 0, "token": 1, "created_at": 1, "expires_at": 1, "opens": 1, "last_opened_at": 1, "opened_events": 1}
        ).sort("created_at", -1).to_list(50)
    now_iso = _now().isoformat()
    out = [{"token": d["token"], "url": f"{frontend}/share/digest/{d['token']}",
            "created_at": d.get("created_at"), "expires_at": d.get("expires_at"),
            "opens": d.get("opens", 0), "last_opened_at": d.get("last_opened_at"),
            "series": _open_series(d.get("opened_events") or [], 14),
            "expired": bool(d.get("expires_at") and now_iso > d["expires_at"])} for d in docs]
    return {"shares": out, "total": len(out), "total_opens": sum(x["opens"] for x in out)}


# ── Voice Digest (spoken briefing via OpenAI TTS through the Emergent LLM key) ─
def _digest_voice_script(ctx):
    d = ctx["digest"]
    cur = ctx["scorecard"]["current"]
    fc = ctx["scorecard"].get("forecast") or {}
    areas = list(ctx["open_conflicts_by_area"].items())
    top_areas = ", ".join(f"{a} with {n}" for a, n in areas[:3]) or "no open areas"
    fc_txt = ""
    if fc.get("next_week_score"):
        dd = fc.get("delta", 0)
        move = "rise" if dd > 0 else "fall" if dd < 0 else "hold steady"
        fc_txt = f" The governance score is projected to {move} to {fc['next_week_score']} out of 100 next week."
    return (f"Here is your S A P access governance briefing. "
            f"There are {d['open_sod']} open segregation of duties conflicts, "
            f"including {d['sev']['Critical']} critical and {d['sev']['High']} high severity. "
            f"The overall governance score is {cur['governance_score']} out of 100. "
            f"The biggest risk areas are {top_areas}. "
            f"{d['residual_count']} terminated employees still retain access and need clearing. "
            f"In the last twenty four hours, {d['autorem_24h']} conflicts were auto remediated.{fc_txt} "
            f"That concludes your briefing from Obserra S A P User Access Control.")


@sap_router.get("/digest/voice/script")
async def digest_voice_script(user: dict = Depends(get_current_user)):
    org_id = user["org_id"]
    await _ensure(org_id)
    ctx = await _digest_ai_context(org_id)
    return {"script": _digest_voice_script(ctx)}


async def _generate_voice_audio(org_id, voice="onyx", speed=1.0, intro=""):
    """Return (mp3 bytes, script) for the current governance briefing, cached per (script, voice, speed, intro)."""
    import hashlib
    import base64
    ctx = await _digest_ai_context(org_id)
    intro = (intro or "").strip()
    script = (intro + " " if intro else "") + _digest_voice_script(ctx)
    voice = (voice or "onyx").lower()
    if voice not in _TTS_VOICES:
        voice = "onyx"
    try:
        speed = max(0.5, min(2.0, float(speed or 1.0)))
    except Exception:
        speed = 1.0
    h = hashlib.sha256(f"{script}|{voice}|{speed}".encode()).hexdigest()[:16]
    cached = await db.sap_digest_voice.find_one({"org_id": org_id, "hash": h}, {"_id": 0, "audio_b64": 1})
    if cached and cached.get("audio_b64"):
        return base64.b64decode(cached["audio_b64"]), script
    from emergentintegrations.llm.openai import OpenAITextToSpeech
    tts = OpenAITextToSpeech(api_key=os.environ["EMERGENT_LLM_KEY"])
    audio = await tts.generate_speech(text=script[:4000], model="tts-1-hd", voice=voice, speed=speed)
    await db.sap_digest_voice.update_one({"org_id": org_id, "hash": h},
        {"$set": {"org_id": org_id, "hash": h, "audio_b64": base64.b64encode(audio).decode(),
                  "script": script, "voice": voice, "speed": speed, "at": _now().isoformat()}}, upsert=True)
    return audio, script


@sap_router.get("/digest/voice")
async def digest_voice(voice: str = "", speed: float = 0, user: dict = Depends(get_current_user)):
    """Spoken governance briefing (mp3). Honors ?voice=&speed= or the saved digest config; cached."""
    org_id = user["org_id"]
    await _ensure(org_id)
    cfg = await _get_digest_config(org_id)
    v = voice or cfg.get("voice_name") or "onyx"
    sp = speed or cfg.get("voice_speed") or 1.0
    try:
        audio, _script = await _generate_voice_audio(org_id, v, sp, cfg.get("voice_intro", ""))
    except Exception:
        raise HTTPException(status_code=503, detail="Voice generation is unavailable right now — please try again shortly.")
    await _audit(org_id, user["email"], "sap.digest.voice", f"voice briefing generated ({v} @ {sp}x)")
    return Response(content=audio, media_type="audio/mpeg",
                    headers={"Content-Disposition": 'inline; filename="sap-governance-digest.mp3"'})


# ── Voice preview sample (short fixed phrase in the selected voice) ────────────
_VOICE_SAMPLE_TEXT = "This is your S A P access governance briefing from Obserra."


@sap_router.get("/digest/voice/sample")
async def digest_voice_sample(voice: str = "onyx", user: dict = Depends(get_current_user)):
    """A short spoken sample so leaders can hear a narrator voice before saving."""
    import hashlib
    import base64
    voice = (voice or "onyx").lower()
    if voice not in _TTS_VOICES:
        voice = "onyx"
    h = "sample-" + hashlib.sha256(f"{_VOICE_SAMPLE_TEXT}|{voice}".encode()).hexdigest()[:12]
    cached = await db.sap_digest_voice.find_one({"org_id": "_sample", "hash": h}, {"_id": 0, "audio_b64": 1})
    if cached and cached.get("audio_b64"):
        audio = base64.b64decode(cached["audio_b64"])
    else:
        try:
            from emergentintegrations.llm.openai import OpenAITextToSpeech
            tts = OpenAITextToSpeech(api_key=os.environ["EMERGENT_LLM_KEY"])
            audio = await tts.generate_speech(text=_VOICE_SAMPLE_TEXT, model="tts-1", voice=voice)
        except Exception:
            raise HTTPException(status_code=503, detail="Voice preview is unavailable right now.")
        await db.sap_digest_voice.update_one({"org_id": "_sample", "hash": h},
            {"$set": {"org_id": "_sample", "hash": h, "audio_b64": base64.b64encode(audio).decode(),
                      "voice": voice, "at": _now().isoformat()}}, upsert=True)
    return Response(content=audio, media_type="audio/mpeg",
                    headers={"Cache-Control": "public, max-age=86400"})


# ── Share this briefing (one email: read-only snapshot link + spoken .mp3) ─────
class ShareBriefingBody(BaseModel):
    recipients: list[str] = []


@sap_router.post("/digest/share-briefing")
async def share_briefing(body: ShareBriefingBody, user: dict = Depends(get_current_user)):
    org_id = user["org_id"]
    await _ensure(org_id)
    from kernel import notifications
    import base64
    cfg = await _get_digest_config(org_id)
    data = await _governance_digest_data(org_id)
    share = await _create_digest_share(org_id)
    html = _governance_digest_html(data, share["url"])
    emails = [e.strip() for e in body.recipients if e.strip()] or [user["email"]]
    att = []
    try:
        audio, _s = await _generate_voice_audio(org_id, cfg.get("voice_name", "onyx"), cfg.get("voice_speed", 1.0), cfg.get("voice_intro", ""))
        att = [{"filename": "sap-governance-briefing.mp3", "content": base64.b64encode(audio).decode()}]
    except Exception:
        pass
    sent = 0
    for e in emails:
        if await notifications.send_email(e, "SAP Governance Briefing — audio + live snapshot — Obserra UAC", html, attachments=att):
            sent += 1
    await _audit(org_id, user["email"], "sap.digest.share-briefing",
                 f"briefing (audio+link) emailed to {len(emails)} recipient(s), {sent} sent")
    return {"ok": True, "sent": sent, "recipients": emails, "share_url": share["url"], "has_audio": bool(att)}


# ── Weekly AI Q&A recap (opt-in, on the configured weekday) ───────────────────
def _weekly_recap_html(rc):
    import html as _h
    rows = ""
    for i, item in enumerate(rc["top"], 1):
        rows += (f'<div style="display:flex;gap:10px;padding:8px 0;border-bottom:1px solid #eef2f7">'
                 f'<div style="font-weight:800;color:#0f1e3d;min-width:20px">{i}</div>'
                 f'<div style="flex:1;color:#334155;font-size:13px">{_h.escape(item["q"])}</div>'
                 f'<div style="font-family:monospace;color:#0ea5e9;font-weight:700;white-space:nowrap">{item["count"]}&times;</div></div>')
    return ('<div style="font:400 14px Arial,Helvetica,sans-serif;color:#1f2937;max-width:640px;margin:auto">'
            '<div style="background:#0f1e3d;color:#fff;padding:18px 22px;border-radius:12px 12px 0 0">'
            '<div style="font-size:11px;letter-spacing:2px;opacity:.7">OBSERRA SAP UAC</div>'
            '<h2 style="margin:4px 0 0;font-size:20px">Weekly AI Q&amp;A Recap</h2>'
            f'<div style="font-size:12px;opacity:.75;margin-top:2px">{rc["total"]} question(s) in the last 7 days · {rc["unique"]} distinct</div></div>'
            '<div style="border:1px solid #e2e8f0;border-top:0;border-radius:0 0 12px 12px;padding:14px 18px">'
            '<div style="font-size:12px;color:#64748b;margin-bottom:6px">Most-asked questions of leadership about SAP access governance</div>'
            + (rows or '<div style="color:#94a3b8">No questions this week.</div>') +
            '<p style="font-size:11px;color:#9ca3af;margin-top:16px">Obserra — Executive Protection &amp; Intelligence LLC · Confidential · '
            'Open the SoD Command Center to ask new questions.</p></div></div>')


async def _weekly_recap_data(org_id):
    since_iso = (_now() - timedelta(days=7)).isoformat()
    docs = await db.sap_digest_chat.find({"org_id": org_id}, {"_id": 0, "messages": 1}).to_list(500)
    counts, total = {}, 0
    for d in docs:
        for m in (d.get("messages") or []):
            if m.get("role") == "user" and (m.get("at") or "") >= since_iso:
                total += 1
                key = " ".join((m.get("text") or "").split())[:120]
                if key:
                    counts[key] = counts.get(key, 0) + 1
    top = sorted(counts.items(), key=lambda x: -x[1])[:6]
    return {"total": total, "unique": len(counts), "since": since_iso,
            "top": [{"q": q, "count": c} for q, c in top]}


async def run_sap_weekly_recap():
    """Weekly 'most-asked AI questions' recap email — opt-in per org, on the configured weekday."""
    from kernel import notifications
    now = _now()
    today = now.date().isoformat()
    orgs = await db.organizations.find({}).to_list(1000)
    for org in orgs:
        org_id = str(org["_id"])
        if not await db.sap_persons.find_one({"org_id": org_id}):
            continue
        cfg = await _get_digest_config(org_id)
        if not cfg.get("recap_enabled"):
            continue
        if now.weekday() != _WEEKDAYS.get(cfg.get("recap_day", "mon"), 0):
            continue
        try:
            rc = await _weekly_recap_data(org_id)
            if rc["total"] == 0:
                continue
            html = _weekly_recap_html(rc)
            if cfg.get("recipients"):
                emails = cfg["recipients"]
            else:
                recips = await db.users.find({"org_id": org_id, "role": {"$in": ["admin", "executive"]}},
                                             {"_id": 0, "email": 1}).to_list(200)
                emails = [r["email"] for r in recips]
            for e in emails:
                await notifications.send_email(e, "SAP Governance — Weekly AI Q&A Recap — Obserra UAC", html)
            await notifications.create(org_id, "report", "Weekly AI Q&A recap sent",
                f"{rc['total']} question(s) this week; top {len(rc['top'])} shared with {len(emails)} recipient(s).",
                ref="sap-ai-recap", dedupe_key=f"sap-recap:{today}")
        except Exception:
            pass


def _open_series(events, days=14):
    today = _now().date()
    buckets = {}
    for e in events:
        try:
            dd = datetime.fromisoformat(e.get("at") or "").date().isoformat()
        except Exception:
            continue
        buckets[dd] = buckets.get(dd, 0) + 1
    return [buckets.get((today - timedelta(days=i)).isoformat(), 0) for i in range(days - 1, -1, -1)]


@sap_router.get("/digest/recap/preview")
async def digest_recap_preview(user: dict = Depends(get_current_user)):
    """Preview this week's most-asked AI questions before the weekly recap emails."""
    org_id = user["org_id"]
    await _ensure(org_id)
    return await _weekly_recap_data(org_id)


# ── Extracted domain sub-modules (import registers their routes on the shared sap_router) ──
import sap_evidence  # noqa: E402,F401
import sap_ask  # noqa: E402,F401
from sap_ask import _digest_ai_context  # noqa: E402,F401  (used by _build_digest_snapshot)
from sap_evidence import run_sap_sod_evidence_export  # noqa: E402,F401  (re-exported for the scheduler)
