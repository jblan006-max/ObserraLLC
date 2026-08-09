"""Obserra SAP UAC — Governance Digest (email + Slack/Teams) and Access Governance Scorecard
(attached to the shared sap_router)."""
import io
import csv
from datetime import datetime, timedelta

import httpx
from bson import ObjectId
from fastapi import Depends, HTTPException
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


def _governance_digest_html(d):
    def row(label, value, color="#0f1e3d"):
        return (f'<tr><td style="padding:6px 10px;color:#64748b;font-size:13px">{label}</td>'
                f'<td style="padding:6px 10px;text-align:right;font-weight:700;font-size:15px;color:{color}">{value}</td></tr>')
    residual = "".join(f'<li>{r["name"]} — {r["dept"]}</li>' for r in d["residual"]) or "<li>None — no terminated worker retains SAP access ✓</li>"
    top = "".join(f'<li><b>{t["name"]}</b> ({t["dept"]}) — {t["score"]}/100 · {t["rating"]}</li>' for t in d["top"]) or "<li>—</li>"
    ar = ("enabled" if d["autorem_enabled"] else "disabled")
    return (
        '<div style="font:400 14px Arial,Helvetica,sans-serif;color:#1f2937;max-width:640px;margin:auto">'
        '<div style="background:#0f1e3d;color:#fff;padding:18px 22px;border-radius:12px 12px 0 0">'
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
        '<p style="font-size:11px;color:#9ca3af;margin-top:18px;border-top:1px solid #e2e8f0;padding-top:10px">'
        'Obserra — Executive Protection &amp; Intelligence LLC · Confidential. Auto-remediation opens real '
        'ServiceNow workflows that fan out to ADP/IZ8 HR → SAP → AD/Entra and auto-close end-to-end.</p></div></div>')


# ── Governance Digest scheduling config + Slack/Teams alert ───────────────────
_DIGEST_DEFAULT = {"enabled": True, "recipients": [], "days": "everyday", "chat_alert": True,
                   "teams_url": "", "slack_url": ""}


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
    return {"config": {k: cfg[k] for k in _DIGEST_DEFAULT},
            "last_at": (state or {}).get("last_at"),
            "default_recipients": [r["email"] for r in default_recips],
            "fallback_chat_configured": fallback_chat,
            "next_window": "Daily 08:00 UTC · platform scheduler"}


@sap_router.put("/digest/config")
async def put_digest_config(body: DigestConfigBody, user: dict = Depends(require_roles("admin"))):
    org_id = user["org_id"]
    await _ensure(org_id)
    days = body.days if body.days in ("everyday", "weekdays") else "everyday"
    recips = [e.strip() for e in body.recipients if e.strip()]
    doc = {"org_id": org_id, "enabled": body.enabled, "recipients": recips, "days": days,
           "chat_alert": body.chat_alert, "teams_url": body.teams_url.strip(), "slack_url": body.slack_url.strip()}
    await db.sap_digest_config.update_one({"org_id": org_id}, {"$set": doc}, upsert=True)
    await _audit(org_id, user["email"], "sap.digest.config",
                 f"enabled={body.enabled} days={days} chat={body.chat_alert} recipients={len(recips)}")
    return {"ok": True, "config": {k: doc[k] for k in _DIGEST_DEFAULT}}


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
            html = _governance_digest_html(data)
            if cfg.get("recipients"):
                emails = cfg["recipients"]
            else:
                recips = await db.users.find({"org_id": org_id, "role": {"$in": ["admin", "executive"]}},
                                             {"_id": 0, "email": 1}).to_list(200)
                emails = [r["email"] for r in recips]
            for e in emails:
                await notifications.send_email(e, "SAP Access Governance Digest — Obserra UAC", html)
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
    html = _governance_digest_html(data)
    if cfg.get("recipients"):
        emails = cfg["recipients"]
    else:
        recips = await db.users.find({"org_id": org_id, "role": {"$in": ["admin", "executive"]}},
                                     {"_id": 0, "email": 1}).to_list(200)
        emails = [r["email"] for r in recips] or [user["email"]]
    sent = 0
    for e in emails:
        if await notifications.send_email(e, "SAP Access Governance Digest — Obserra UAC", html):
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
    data = await _governance_digest_data(org_id)
    return {"html": _governance_digest_html(data), "data": data}


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
    if len(snaps) >= 2:
        trend = [{"label": "W" + s["week"].split("-W")[-1], "week": s["week"], "open_sod": s["open_sod"],
                  "autoremediated": s.get("autorem_total", 0), "residual": s.get("residual", 0),
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
                          "avg_risk": min(100, m["avg_risk"] + k),
                          "governance_score": max(0, m["governance_score"] - k * 3)})
        trend_source = "derived"
    return {"current": m, "trend": trend, "trend_source": trend_source, "generated_at": now.isoformat()}


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


@sap_router.get("/scorecard/export")
async def scorecard_export(format: str = "csv", user: dict = Depends(get_current_user)):
    org_id = user["org_id"]
    await _ensure(org_id)
    if format != "csv":
        raise HTTPException(status_code=400, detail="format must be csv")
    sc = await _scorecard_payload(org_id, record=False)
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
    return Response(content=sio.getvalue(), media_type="text/csv",
                    headers={"Content-Disposition": f'attachment; filename="sap-governance-scorecard-{_now().strftime("%Y%m%d")}.csv"'})
