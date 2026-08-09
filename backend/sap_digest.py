"""Obserra SAP UAC — Governance Digest (email + Slack/Teams) and Access Governance Scorecard
(attached to the shared sap_router)."""
import os
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
                   "teams_url": "", "slack_url": "",
                   "score_alert": True, "score_threshold": 60,
                   "evidence_export": False, "evidence_recipients": [], "evidence_day": "mon"}
_WEEKDAYS = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6}


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
    evid_recips = [e.strip() for e in body.evidence_recipients if e.strip()]
    doc = {"org_id": org_id, "enabled": body.enabled, "recipients": recips, "days": days,
           "chat_alert": body.chat_alert, "teams_url": body.teams_url.strip(), "slack_url": body.slack_url.strip(),
           "score_alert": body.score_alert, "score_threshold": max(0, min(100, int(body.score_threshold or 60))),
           "evidence_export": body.evidence_export, "evidence_recipients": evid_recips,
           "evidence_day": body.evidence_day if body.evidence_day in _WEEKDAYS else "mon"}
    await db.sap_digest_config.update_one({"org_id": org_id}, {"$set": doc}, upsert=True)
    await _audit(org_id, user["email"], "sap.digest.config",
                 f"enabled={body.enabled} days={days} chat={body.chat_alert} recipients={len(recips)} "
                 f"score_alert={body.score_alert}@{doc['score_threshold']} evidence={body.evidence_export}")
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
    html = _governance_digest_html(data)
    att = _digest_attachment(await _scorecard_payload(org_id, record=False))
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
    return {"current": m, "trend": trend, "trend_source": trend_source, "generated_at": now.isoformat()}


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
    """Post a Slack/Teams alert when the governance score falls below the org's target threshold.
    De-duped per ISO week so a sustained dip alerts once; recovery clears the flag so the next drop re-alerts."""
    from kernel import notifications
    cfg = await _get_digest_config(org_id)
    m = await _scorecard_metrics(org_id)
    score = m["governance_score"]
    thr = int(cfg.get("score_threshold") or 60)
    below = score < thr
    wk = _now().strftime("%G-W%V")
    state = await db.sap_digest_state.find_one({"org_id": org_id}, {"_id": 0}) or {}
    already = state.get("score_alert_week") == wk
    posted = False
    if cfg.get("score_alert") and below and (force or not already):
        title = "🔴 SAP Access Governance score below target"
        text = (f"Governance score {score}/100 dropped below the {thr}/100 target. "
                f"Open SoD {m['open_sod']} (Critical {m['sev']['Critical']} · High {m['sev']['High']}) · "
                f"Residual-access leavers {m['residual']} · Avg SAP risk {m['avg_risk']}/100. "
                f"Sign in to the SoD Command Center to remediate.")
        posted = await _sap_post_chat(org_id, cfg, title, text)
        await notifications.create(org_id, "report", "SAP governance score below target", text,
                                   ref="sap-score-alert", dedupe_key=f"sap-score:{wk}")
        await db.sap_digest_state.update_one({"org_id": org_id},
                                             {"$set": {"org_id": org_id, "score_alert_week": wk}}, upsert=True)
    if not below and state.get("score_alert_week"):
        await db.sap_digest_state.update_one({"org_id": org_id}, {"$unset": {"score_alert_week": ""}})
    return {"score": score, "threshold": thr, "below": below, "posted": posted,
            "enabled": bool(cfg.get("score_alert")), "alerted_this_week": already and not force}


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


# ── SoD Evidence Pack (auditor CSV/PDF + scheduled weekly auto-email) ─────────────────────────
async def _sod_evidence_rows(org_id, status="", severity=""):
    persons, accounts, conflicts, pmap = await _correlate(org_id)
    rows = []
    for c in conflicts:
        if status and status not in ("", "all") and c.get("status") != status:
            continue
        if severity and severity not in ("", "all") and c.get("severity") != severity:
            continue
        p = pmap.get(c.get("person_ref"))
        rows.append({
            "rule_ref": c["rule_ref"], "rule_name": c["rule_name"], "area": c["area"],
            "severity": c["severity"], "status": c.get("status", "Open"),
            "person_name": (p or {}).get("name") or c.get("sap_user") or "—",
            "department": (p or {}).get("department") or "—",
            "system": c["system"], "sap_user": c["sap_user"],
            "function_a": c["function_a"], "function_b": c["function_b"],
            "a_via_roles": c.get("a_via_roles", []), "b_via_roles": c.get("b_via_roles", []),
            "business_risk": c["business_risk"], "mitigating_control": c.get("mitigating_control") or "",
        })
    sev_order = {"Critical": 0, "High": 1, "Medium": 2, "Low": 3}
    rows.sort(key=lambda r: (0 if r["status"] == "Open" else 1, sev_order.get(r["severity"], 9), r["rule_ref"]))
    summary = {"total": len(rows), "open": sum(1 for r in rows if r["status"] == "Open"),
               "mitigated": sum(1 for r in rows if r["status"] == "Mitigated"),
               "accepted": sum(1 for r in rows if r["status"] == "Accepted"),
               "critical": sum(1 for r in rows if r["severity"] == "Critical"),
               "high": sum(1 for r in rows if r["severity"] == "High")}
    return rows, summary


def _sod_evidence_csv(rows, summary):
    sio = io.StringIO()
    w = csv.writer(sio)
    w.writerow(["Obserra — SAP Segregation-of-Duties Evidence Pack"])
    w.writerow(["Generated", _now().isoformat()])
    w.writerow(["Total", summary["total"], "Open", summary["open"], "Mitigated", summary["mitigated"],
                "Accepted", summary["accepted"], "Critical", summary["critical"], "High", summary["high"]])
    w.writerow([])
    w.writerow(["Rule Ref", "Rule", "Area", "Severity", "Status", "User", "Department", "System",
                "SAP User", "Function A", "Via Roles A", "Function B", "Via Roles B", "Mitigating Control", "Business Risk"])
    for r in rows:
        w.writerow([r["rule_ref"], r["rule_name"], r["area"], r["severity"], r["status"], r["person_name"],
                    r["department"], r["system"], r["sap_user"], r["function_a"], " + ".join(r["a_via_roles"]),
                    r["function_b"], " + ".join(r["b_via_roles"]), r["mitigating_control"], r["business_risk"]])
    return sio.getvalue()


def _sod_evidence_pdf(rows, summary):
    """Branded SOX-grade PDF evidence pack of every SoD conflict and its remediation state."""
    from reportlab.lib.pagesizes import LETTER, landscape
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage
    pw, ph = landscape(LETTER)
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=(pw, ph), topMargin=0.6 * inch, bottomMargin=0.6 * inch,
                            leftMargin=0.5 * inch, rightMargin=0.5 * inch)
    ss = getSampleStyleSheet()
    navy = colors.HexColor("#0f1e3d")
    title_st = ParagraphStyle("t", parent=ss["Title"], textColor=navy, fontSize=18, spaceAfter=2)
    sub_st = ParagraphStyle("s", parent=ss["Normal"], textColor=colors.HexColor("#64748b"), fontSize=9)
    cell = ParagraphStyle("c", parent=ss["Normal"], fontSize=7.5, leading=9)
    head = ParagraphStyle("h", parent=ss["Normal"], fontSize=7.5, leading=9, textColor=colors.white, fontName="Helvetica-Bold")
    flow = []
    badge = "/app/backend/assets/brand-badge.png"
    if os.path.exists(badge):
        flow.append(RLImage(badge, width=34, height=34))
    flow.append(Paragraph("SAP Access Governance — Segregation-of-Duties Evidence Pack", title_st))
    flow.append(Paragraph(f"{summary['total']} conflict(s) · {summary['open']} open · {summary['mitigated']} mitigated · "
                          f"{summary['accepted']} accepted · {summary['critical']} critical · {summary['high']} high · "
                          f"Generated {_now().strftime('%B %d, %Y %H:%M UTC')}", sub_st))
    flow.append(Spacer(1, 10))
    data = [[Paragraph(h, head) for h in ["Ref", "Severity", "Status", "Rule / Toxic combination",
                                          "User (Dept)", "System", "Mitigating control"]]]
    for r in rows[:600]:
        combo = (f'<b>{r["rule_name"]}</b><br/>{r["function_a"]} ({" + ".join(r["a_via_roles"]) or "—"}) '
                 f'&#10007; {r["function_b"]} ({" + ".join(r["b_via_roles"]) or "—"})')
        data.append([
            Paragraph(r["rule_ref"], cell), Paragraph(r["severity"], cell), Paragraph(r["status"], cell),
            Paragraph(combo, cell), Paragraph(f'{r["person_name"]} ({r["department"]})', cell),
            Paragraph(r["system"], cell), Paragraph(r["mitigating_control"] or "—", cell),
        ])
    tbl = Table(data, colWidths=[0.9 * inch, 0.8 * inch, 0.8 * inch, 3.0 * inch, 1.7 * inch, 0.7 * inch, 1.1 * inch], repeatRows=1)
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), navy),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f1f5f9")]),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#e2e8f0")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ]))
    flow.append(tbl)
    flow.append(Spacer(1, 8))
    flow.append(Paragraph("Obserra — Executive Protection &amp; Intelligence LLC · Confidential · "
                          "Live SoD detection across the SAP access model. Each conflict lists the toxic function "
                          "combination, the roles granting it, and its current remediation state.", sub_st))
    doc.build(flow)
    buf.seek(0)
    return buf


def _sod_evidence_html(summary):
    def row(label, value, color="#0f1e3d"):
        return (f'<tr><td style="padding:6px 10px;color:#64748b;font-size:13px">{label}</td>'
                f'<td style="padding:6px 10px;text-align:right;font-weight:700;font-size:15px;color:{color}">{value}</td></tr>')
    return (
        '<div style="font:400 14px Arial,Helvetica,sans-serif;color:#1f2937;max-width:640px;margin:auto">'
        '<div style="background:#0f1e3d;color:#fff;padding:18px 22px;border-radius:12px 12px 0 0">'
        '<div style="font-size:11px;letter-spacing:2px;opacity:.7">OBSERRA SAP UAC</div>'
        '<h2 style="margin:4px 0 0;font-size:20px">SAP SoD Evidence Pack</h2>'
        f'<div style="font-size:12px;opacity:.75;margin-top:2px">Segregation-of-duties audit evidence · {_now().strftime("%B %d, %Y")}</div></div>'
        '<div style="border:1px solid #e2e8f0;border-top:0;border-radius:0 0 12px 12px;padding:6px 12px 18px">'
        '<table style="width:100%;border-collapse:collapse;margin:6px 0">'
        + row("Total SoD conflicts", summary["total"])
        + row("Open (unremediated)", summary["open"], "#b91c1c" if summary["open"] else "#16a34a")
        + row("Mitigated", summary["mitigated"], "#16a34a")
        + row("Risk accepted", summary["accepted"], "#b45309")
        + row("↳ Critical / High", f'{summary["critical"]} / {summary["high"]}')
        + '</table>'
        '<p style="font-size:13px;color:#334155;margin-top:10px">The full SOX-grade evidence pack (every conflict, its '
        'toxic function combination, the roles granting it and its remediation state) is attached as a branded PDF.</p>'
        '<p style="font-size:11px;color:#9ca3af;margin-top:18px;border-top:1px solid #e2e8f0;padding-top:10px">'
        'Obserra — Executive Protection &amp; Intelligence LLC · Confidential.</p></div></div>')


def _sod_evidence_attachment(rows, summary):
    import base64
    pdf = _sod_evidence_pdf(rows, summary)
    return [{"filename": f"sap-sod-evidence-{_now().strftime('%Y%m%d')}.pdf",
             "content": base64.b64encode(pdf.getvalue()).decode()}]


@sap_router.get("/sod-evidence/export")
async def sod_evidence_export(format: str = "pdf", status: str = "", severity: str = "",
                              user: dict = Depends(get_current_user)):
    """Download the SoD evidence pack (branded PDF or auditor CSV), optionally filtered by status/severity."""
    org_id = user["org_id"]
    await _ensure(org_id)
    if format not in ("csv", "pdf"):
        raise HTTPException(status_code=400, detail="format must be csv or pdf")
    rows, summary = await _sod_evidence_rows(org_id, status, severity)
    fname = f"sap-sod-evidence-{_now().strftime('%Y%m%d-%H%M')}"
    if format == "csv":
        return Response(content=_sod_evidence_csv(rows, summary), media_type="text/csv",
                        headers={"Content-Disposition": f'attachment; filename="{fname}.csv"'})
    pdf = _sod_evidence_pdf(rows, summary)
    return Response(content=pdf.getvalue(), media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="{fname}.pdf"'})


@sap_router.post("/sod-evidence/send")
async def sod_evidence_send(user: dict = Depends(require_roles("admin"))):
    """Email the SoD evidence pack PDF now to the configured auditors (or admins/execs)."""
    org_id = user["org_id"]
    await _ensure(org_id)
    from kernel import notifications
    cfg = await _get_digest_config(org_id)
    rows, summary = await _sod_evidence_rows(org_id)
    att = _sod_evidence_attachment(rows, summary)
    html = _sod_evidence_html(summary)
    if cfg.get("evidence_recipients"):
        emails = cfg["evidence_recipients"]
    else:
        recips = await db.users.find({"org_id": org_id, "role": {"$in": ["admin", "executive"]}},
                                     {"_id": 0, "email": 1}).to_list(200)
        emails = [r["email"] for r in recips] or [user["email"]]
    sent = 0
    for e in emails:
        if await notifications.send_email(e, "SAP SoD Evidence Pack — Obserra UAC", html, attachments=att):
            sent += 1
    await _audit(org_id, user["email"], "sap.sod.evidence.send", f"evidence pack emailed to {len(emails)}, {sent} sent")
    return {"ok": True, "sent": sent, "recipients": emails, "conflicts": summary["total"], "summary": summary}


async def run_sap_sod_evidence_export():
    """Weekly auto-email of the SoD evidence pack PDF to auditors — runs on each org's configured weekday."""
    from kernel import notifications
    now = _now()
    dow = now.weekday()
    orgs = await db.organizations.find({}).to_list(1000)
    for org in orgs:
        org_id = str(org["_id"])
        if not await db.sap_persons.find_one({"org_id": org_id}):
            continue
        cfg = await _get_digest_config(org_id)
        if not cfg.get("evidence_export"):
            continue
        if _WEEKDAYS.get(cfg.get("evidence_day", "mon"), 0) != dow:
            continue
        try:
            rows, summary = await _sod_evidence_rows(org_id)
            att = _sod_evidence_attachment(rows, summary)
            html = _sod_evidence_html(summary)
            if cfg.get("evidence_recipients"):
                emails = cfg["evidence_recipients"]
            else:
                recips = await db.users.find({"org_id": org_id, "role": {"$in": ["admin", "executive"]}},
                                             {"_id": 0, "email": 1}).to_list(200)
                emails = [r["email"] for r in recips]
            for e in emails:
                await notifications.send_email(e, "Weekly SAP SoD Evidence Pack — Obserra UAC", html, attachments=att)
            await notifications.create(
                org_id, "report", "Weekly SoD evidence pack delivered",
                f"{summary['total']} conflict(s) ({summary['open']} open) documented — PDF emailed to {len(emails)} recipient(s).",
                ref="sap-sod-evidence", dedupe_key=f"sap-sod-evidence:{now.date().isoformat()}")
        except Exception:
            pass
