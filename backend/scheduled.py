"""Scheduled tasks — platform cron webhook endpoints.

Cron endpoints must ack 2xx immediately; enqueue/background the actual work.
"""
import os
import io
import sys
import csv
import uuid
import base64
import hmac
import logging

import httpx
from fastapi import APIRouter, Request, BackgroundTasks, HTTPException

from db import db
from kernel import notifications
from ai_advisor import generate_board_report, spend_rows
from studio import _compose_report
from reports import _report_html, build_board_report_pdf

logger = logging.getLogger(__name__)
scheduled_router = APIRouter(prefix="/api")


def _authorized(request: Request) -> bool:
    secret = os.environ.get("WEBHOOK_CRON_SECRET", "")
    header = request.headers.get("Authorization", "")
    token = header[7:] if header.startswith("Bearer ") else ""
    return bool(secret) and hmac.compare_digest(token, secret)


async def _run_monthly_board_reports():
    orgs = await db.organizations.find({}).to_list(1000)
    for org in orgs:
        org_id = str(org["_id"])
        try:
            result = await generate_board_report(org_id, by="scheduler@obserra")
            recipients = await db.users.find(
                {"org_id": org_id, "role": {"$in": ["admin", "executive"]}}).to_list(200)
            emails = {r["email"] for r in recipients}
            emails |= {e for e in (org.get("report_recipients") or []) if e}
            html = _report_html(result["report"], "Monthly Executive Board Report")
            pdf = await build_board_report_pdf(org_id, result["report"], "Monthly Executive Board Report")
            attachments = [{"filename": "obserra-board-report.pdf",
                            "content": base64.b64encode(pdf.getvalue()).decode()}]
            for email in emails:
                await notifications.send_email(email, "Monthly Board Report — Obserra EIOS", html, attachments=attachments)
            await notifications.create(
                org_id, "report", "Monthly board report delivered",
                f"Branded PDF (cover + charts) emailed to {len(emails)} recipient(s).", ref="board-report")
            logger.info(f"Monthly board report sent for org {org_id} to {len(recipients)} recipients")
        except Exception as e:
            logger.error(f"Monthly board report failed for org {org_id}: {e}")


async def _run_access_expiry():
    from auth import _notify_access_change, _log_audit, _access_summary_text
    from datetime import datetime, timezone
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    users = await db.users.find({"access_expiry": {"$lte": today}}).to_list(1000)
    for u in users:
        old = u.get("module_access")
        revert = u.get("access_expiry_revert")
        await db.users.update_one({"_id": u["_id"]},
                                  {"$set": {"module_access": revert},
                                   "$unset": {"access_expiry": "", "access_expiry_revert": "", "preset_pin": ""}})
        try:
            await _log_audit(u["org_id"], "scheduler@obserra", "team.access",
                             f"Access grant expired → reverted to {_access_summary_text(revert)}", target=u["email"])
            await _notify_access_change(u["org_id"], u, revert, "scheduler@obserra", old_ma=old)
        except Exception as e:
            logger.error(f"access expiry notify failed: {e}")


async def _run_access_review():
    from auth import CATEGORY_NAMES, CATEGORY_IDS
    orgs = await db.organizations.find({}).to_list(1000)
    for org in orgs:
        org_id = str(org["_id"])
        try:
            enterprise = org.get("plan") == "enterprise"
            ents = set(org.get("entitlements", []))
            members = await db.users.find({"org_id": org_id}).to_list(500)
            rows = ""
            for c in CATEGORY_IDS:
                if not (enterprise or c in ents):
                    continue
                seats = [m for m in members if m.get("role") == "admin" or m.get("module_access") is None or c in (m.get("module_access") or [])]
                rows += (f'<tr><td style="padding:6px 8px;border-bottom:1px solid #eee">{CATEGORY_NAMES[c]}</td>'
                         f'<td style="padding:6px 8px;border-bottom:1px solid #eee;text-align:right">{len(seats)} of {len(members)}</td></tr>')
            if not rows:
                continue
            html = ('<table width="100%" cellpadding="0" cellspacing="0" style="max-width:560px;margin:auto;background:#fff"><tr><td style="padding:26px 24px">'
                    '<div style="font:800 20px Arial;color:#0f1e3d">Monthly Access Review</div>'
                    '<div style="font:400 13px Arial;color:#374151;margin:10px 0 14px">Snapshot of who can reach each paid pack — review for audit hygiene.</div>'
                    f'<table style="width:100%;border-collapse:collapse;font:400 13px Arial;color:#1f2937">{rows}</table>'
                    '</td></tr></table>')
            admins = await db.users.find({"org_id": org_id, "role": {"$in": ["admin", "executive"]}}).to_list(200)
            for a in admins:
                await notifications.send_email(a["email"], "Monthly Access Review — Obserra EIOS", html)
            await notifications.create(org_id, "team", "Access review sent",
                                       f"Monthly access snapshot emailed to {len(admins)} admin(s).", ref="access-review")
        except Exception as e:
            logger.error(f"access review failed for org {org_id}: {e}")


@scheduled_router.post("/cron/monthly-board-report")
async def monthly_board_report(request: Request, background_tasks: BackgroundTasks):
    # Cron endpoints must ack 2xx immediately; enqueue/background the actual work.
    if not _authorized(request):
        raise HTTPException(status_code=401, detail="Unauthorized")
    background_tasks.add_task(_run_monthly_board_reports)
    background_tasks.add_task(_run_access_review)
    from deploy import _run_monthly_evidence_email
    background_tasks.add_task(_run_monthly_evidence_email)
    from deploy import _run_quarterly_evidence_pack
    background_tasks.add_task(_run_quarterly_evidence_pack)
    from sap_uac import run_sap_board_pack
    background_tasks.add_task(run_sap_board_pack)
    return {"status": "accepted"}


async def _refresh_guides():
    # Offload to a fully detached OS process so the heavy Playwright capture never
    # blocks the FastAPI event loop / worker threadpool.
    try:
        import subprocess
        env = {**os.environ, "PLAYWRIGHT_BROWSERS_PATH": os.environ.get("PLAYWRIGHT_BROWSERS_PATH", "/pw-browsers")}
        subprocess.Popen(
            [sys.executable, "-c",
             "import sys; sys.path.insert(0, '/app/backend'); from deploy import regenerate_guides; regenerate_guides(capture=True)"],
            env=env, cwd="/app/backend",
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        logger.info("Weekly guide refresh launched (detached)")
    except Exception as e:
        logger.error(f"Weekly guide refresh failed to launch: {e}")


@scheduled_router.post("/cron/weekly-guide-refresh")
async def weekly_guide_refresh(request: Request, background_tasks: BackgroundTasks):
    # Cron endpoints must ack 2xx immediately; enqueue/background the actual work.
    if not _authorized(request):
        raise HTTPException(status_code=401, detail="Unauthorized")
    background_tasks.add_task(_refresh_guides)
    return {"status": "accepted"}


def _digest_html(alerts):
    rows = "".join(
        f'<tr><td style="padding:8px 0;border-bottom:1px solid #eee;font:400 13px Arial;color:#1f2937">'
        f'<b>{a["title"]}</b><br><span style="color:#6b7280;font-size:12px">{a["body"]}</span></td></tr>'
        for a in alerts)
    return (
        '<table width="100%" cellpadding="0" cellspacing="0" style="max-width:600px;margin:auto;background:#fff">'
        '<tr><td style="padding:24px">'
        '<div style="font:800 18px Arial;color:#0f1e3d">Weekly Control Drift Digest</div>'
        '<div style="font:400 12px Arial;color:#6b7280;margin-bottom:14px">Obserra — Executive Protection &amp; Intelligence LLC</div>'
        f'<div style="font:600 13px Arial;color:#b45309;margin-bottom:8px">{len(alerts)} open control alert(s) need attention</div>'
        f'<table width="100%">{rows}</table>'
        '<div style="border-top:1px solid #e5e7eb;margin-top:16px;padding-top:10px;font:400 10px Arial;color:#9ca3af">'
        'Sign in to Obserra EIOS to acknowledge, assign, and resolve each alert.</div>'
        '</td></tr></table>')


async def _run_drift_digest(cadences, label):
    orgs = await db.organizations.find({}).to_list(1000)
    for org in orgs:
        org_id = str(org["_id"])
        try:
            alerts = await db.notifications.find(
                {"org_id": org_id, "kind": "control_drift", "resolved": {"$ne": True}}
            ).sort("created_at", -1).to_list(100)
            if not alerts:
                continue
            recipients = await db.users.find(
                {"org_id": org_id, "role": {"$in": ["admin", "executive"]}}).to_list(200)
            # respect each recipient's digest cadence (missing -> weekly default)
            recipients = [r for r in recipients if r.get("digest_cadence", "weekly") in cadences]
            if not recipients:
                continue
            html = _digest_html(alerts)
            for r in recipients:
                await notifications.send_email(r["email"], f"{label} Drift Digest — {len(alerts)} open alert(s)", html)
            await notifications.create(
                org_id, "report", f"{label} drift digest sent",
                f"Emailed {len(alerts)} open control alert(s) to {len(recipients)} recipient(s).", ref="digest")
            logger.info(f"{label} drift digest sent for org {org_id}: {len(alerts)} alerts")
        except Exception as e:
            logger.error(f"{label} drift digest failed for org {org_id}: {e}")


def _momentum_html(x, y, arrow, m):
    color = "#16a34a" if y > x else "#dc2626" if y < x else "#6b7280"
    return (
        '<table width="100%" cellpadding="0" cellspacing="0" style="max-width:600px;margin:auto;background:#fff">'
        '<tr><td style="padding:24px">'
        '<div style="font:800 18px Arial;color:#0f1e3d">Weekly Remediation Momentum</div>'
        '<div style="font:400 12px Arial;color:#6b7280;margin-bottom:14px">Obserra — Executive Protection &amp; Intelligence LLC</div>'
        f'<div style="font:700 22px Arial;color:{color};margin-bottom:6px">Risk-reduction score moved {x} {arrow} {y} '
        '<span style="font-size:13px;color:#6b7280">/100 this week</span></div>'
        f'<div style="font:400 13px Arial;color:#1f2937">{m["remediation_count"]} remediation(s) and {m["evidence_count"]} '
        f'evidence item(s) logged in the last {m["window_days"]} days · {m["applied_recommendations"]} recommendation(s) applied.</div>'
        '<div style="border-top:1px solid #e5e7eb;margin-top:16px;padding-top:10px;font:400 10px Arial;color:#9ca3af">'
        'Sign in to Obserra EIOS → Executive Overview for the full trajectory.</div>'
        '</td></tr></table>')


async def _run_momentum_digest():
    from routes import compute_momentum
    orgs = await db.organizations.find({}).to_list(1000)
    for org in orgs:
        org_id = str(org["_id"])
        try:
            m = await compute_momentum(org_id)
            y, x = m["score"], m.get("prev_score", m["score"])
            arrow = "&#9650;" if y > x else "&#9660;" if y < x else "&#8594;"
            recipients = await db.users.find(
                {"org_id": org_id, "role": {"$in": ["admin", "executive"]}}, {"_id": 0, "email": 1}).to_list(200)
            if not recipients:
                continue
            html = _momentum_html(x, y, arrow, m)
            for r in recipients:
                await notifications.send_email(r["email"], f"Risk-reduction score moved {x} to {y} this week", html)
            await notifications.create(
                org_id, "report", "Weekly momentum digest sent",
                f"Risk-reduction score {x} to {y} emailed to {len(recipients)} exec(s)/admin(s).", ref="momentum-digest")
            logger.info(f"Momentum digest sent for org {org_id}: {x}->{y}")
        except Exception as e:
            logger.error(f"Momentum digest failed for org {org_id}: {e}")


def _ask_recap_html(total, by_source, top_q, top_u, samples):
    def esc(s):
        return (s or "").replace("<", "&lt;").replace(">", "&gt;")
    srcline = " · ".join(f"{v} {k}" for k, v in by_source.items()) or "—"
    ql = "".join(
        f'<tr><td style="padding:6px 0;border-bottom:1px solid #eee;font:400 13px Arial;color:#1f2937">'
        f'<b style="color:#0f1e3d">{n}&times;</b> {esc(q)}</td></tr>' for q, n in top_q
    ) or '<tr><td style="font:400 13px Arial;color:#6b7280">No questions this week</td></tr>'
    ul = " · ".join(f"{esc(u)} ({n})" for u, n in top_u) or "—"
    sl = "".join(
        f'<tr><td style="padding:8px 0;border-bottom:1px solid #f1f1f1;font:400 12px Arial;color:#374151">'
        f'<b>Q:</b> {esc(q)}<br><span style="color:#6b7280"><b>A:</b> {esc(a)}</span></td></tr>' for q, a in samples)
    return (
        '<table width="100%" cellpadding="0" cellspacing="0" style="max-width:600px;margin:auto;background:#fff">'
        '<tr><td style="padding:24px">'
        '<div style="font:800 18px Arial;color:#0f1e3d">Weekly Ask-the-Digest Recap</div>'
        '<div style="font:400 12px Arial;color:#6b7280;margin-bottom:14px">Obserra SAP UAC — SAP Access Governance</div>'
        f'<div style="font:700 15px Arial;color:#0f1e3d;margin-bottom:2px">{total} question(s) asked from Slack / Teams this week</div>'
        f'<div style="font:400 12px Arial;color:#6b7280;margin-bottom:14px">{srcline} · Busiest: {ul}</div>'
        '<div style="font:700 13px Arial;color:#0f1e3d;margin-bottom:4px">Most-asked</div>'
        f'<table width="100%">{ql}</table>'
        + ('<div style="font:700 13px Arial;color:#0f1e3d;margin:14px 0 4px">Recent answers</div>'
           f'<table width="100%">{sl}</table>' if samples else '')
        + '<div style="border-top:1px solid #e5e7eb;margin-top:16px;padding-top:10px;font:400 10px Arial;color:#9ca3af">'
        'Sign in to Obserra SAP UAC &rarr; Workflow Activity for the full Ask log and analytics.</div>'
        '</td></tr></table>')


async def _run_ask_recap_digest():
    import datetime as _dt
    cutoff = (_dt.datetime.now(_dt.timezone.utc) - _dt.timedelta(days=7)).isoformat()
    orgs = await db.organizations.find({}).to_list(1000)
    for org in orgs:
        org_id = str(org["_id"])
        try:
            rows = await db.sap_ask_log.find(
                {"org_id": org_id, "at": {"$gte": cutoff}}, {"_id": 0}).sort("at", -1).to_list(1000)
            if not rows:
                continue
            by_source, qc, uc = {}, {}, {}
            for r in rows:
                src = r.get("source", "?")
                by_source[src] = by_source.get(src, 0) + 1
                qk = (r.get("question") or "").strip().lower()
                if qk not in qc:
                    qc[qk] = [0, r.get("question", "")]
                qc[qk][0] += 1
                un = r.get("user_name", "leader")
                uc[un] = uc.get(un, 0) + 1
            top_q = [(v[1], v[0]) for v in sorted(qc.values(), key=lambda x: -x[0])[:6]]
            top_u = sorted(uc.items(), key=lambda x: -x[1])[:5]
            samples = [(r.get("question", ""), (r.get("answer", "") or "")[:220]) for r in rows[:4]]
            recipients = await db.users.find(
                {"org_id": org_id, "role": {"$in": ["admin", "executive"]}}, {"_id": 0, "email": 1}).to_list(200)
            if not recipients:
                continue
            html = _ask_recap_html(len(rows), by_source, top_q, top_u, samples)
            for r in recipients:
                await notifications.send_email(r["email"], f"Weekly Ask recap — {len(rows)} SAP governance question(s)", html)
            await notifications.create(
                org_id, "report", "Weekly Ask-the-Digest recap sent",
                f"Emailed {len(rows)} Slack/Teams question(s) to {len(recipients)} recipient(s).", ref="ask-recap")
            logger.info(f"Ask recap sent for org {org_id}: {len(rows)} questions")
        except Exception as e:
            logger.error(f"Ask recap failed for org {org_id}: {e}")


@scheduled_router.post("/cron/weekly-drift-digest")
async def weekly_drift_digest(request: Request, background_tasks: BackgroundTasks):
    # Cron endpoints must ack 2xx immediately; enqueue/background the actual work.
    if not _authorized(request):
        raise HTTPException(status_code=401, detail="Unauthorized")
    background_tasks.add_task(_run_drift_digest, {"weekly"}, "Weekly")
    background_tasks.add_task(_run_ask_recap_digest)
    background_tasks.add_task(_run_teams_digest)
    background_tasks.add_task(_run_momentum_digest)
    background_tasks.add_task(_run_connector_digest)
    from sap_uac import run_sap_owner_digest
    background_tasks.add_task(run_sap_owner_digest)
    from ai_advisor import _run_weekly_fair_air_refresh
    background_tasks.add_task(_run_weekly_fair_air_refresh)
    return {"status": "accepted"}


async def _run_teams_digest():
    orgs = await db.organizations.find({"live_teams.valid": True}).to_list(1000)
    for org in orgs:
        org_id = str(org["_id"])
        t = org.get("live_teams") or {}
        url = t.get("webhook_url")
        if not url:
            continue
        try:
            health = await db.health_index.find_one({"org_id": org_id}) or {}
            risks = await db.risks.find({"org_id": org_id}).to_list(500)
            open_r = [r for r in risks if r.get("status") != "Remediated"]
            crit = [r for r in risks if r.get("residual", 0) >= 16]
            top = sorted(risks, key=lambda r: r.get("residual", 0), reverse=True)[:3]
            top_lines = "\n\n".join(
                f"- **{r['ref']}** {r['title']} — residual {r.get('residual')}/25"
                + (f" ({r['business_impact']})" if r.get("business_impact") else "") for r in top)
            text = (f"**Enterprise health:** {health.get('score', '—')} ({health.get('grade', '—')})\n\n"
                    f"**Open risks:** {len(open_r)} &nbsp;·&nbsp; **Critical:** {len(crit)}\n\n"
                    f"**Top risks this week:**\n\n{top_lines}")
            card = {"@type": "MessageCard", "@context": "https://schema.org/extensions",
                    "summary": "Weekly Risk Summary", "themeColor": "0f1e3d",
                    "title": "Obserra — Weekly Risk Summary", "text": text}
            async with httpx.AsyncClient(timeout=20) as c:
                r = await c.post(url, json=card)
            if r.status_code in (200, 202):
                await notifications.create(
                    org_id, "report", "Weekly Teams digest posted",
                    f"Risk summary posted to Teams — {len(open_r)} open, {len(crit)} critical.", ref="teams-digest")
                logger.info(f"Teams digest posted for org {org_id}")
            else:
                logger.warning(f"Teams digest for org {org_id} returned {r.status_code}")
        except Exception as e:
            logger.error(f"Teams digest failed for org {org_id}: {e}")


@scheduled_router.post("/cron/weekly-teams-digest")
async def weekly_teams_digest(request: Request, background_tasks: BackgroundTasks):
    # Cron endpoints must ack 2xx immediately; enqueue/background the actual work.
    if not _authorized(request):
        raise HTTPException(status_code=401, detail="Unauthorized")
    background_tasks.add_task(_run_teams_digest)
    return {"status": "accepted"}


@scheduled_router.post("/cron/daily-drift-digest")
async def daily_drift_digest(request: Request, background_tasks: BackgroundTasks):
    # Cron endpoints must ack 2xx immediately; enqueue/background the actual work.
    if not _authorized(request):
        raise HTTPException(status_code=401, detail="Unauthorized")
    background_tasks.add_task(_run_drift_digest, {"daily"}, "Daily")
    background_tasks.add_task(_run_access_expiry)
    background_tasks.add_task(_run_connector_health)
    from sap_uac import (run_sap_autoremediation_all, run_sap_governance_digest,
                         run_sap_mover_autostrip_all, record_sap_scorecard_all, run_sap_weekly_scorecard,
                         run_sap_scorecard_alerts, run_sap_sod_evidence_export, run_sap_weekly_recap,
                         run_sap_watchlist_alerts)
    background_tasks.add_task(run_sap_autoremediation_all)
    background_tasks.add_task(run_sap_mover_autostrip_all)
    background_tasks.add_task(record_sap_scorecard_all)
    background_tasks.add_task(run_sap_scorecard_alerts)
    background_tasks.add_task(run_sap_sod_evidence_export)
    background_tasks.add_task(run_sap_weekly_scorecard)
    background_tasks.add_task(run_sap_governance_digest)
    background_tasks.add_task(run_sap_weekly_recap)
    background_tasks.add_task(run_sap_watchlist_alerts)
    from self_scan import _run_autonomous_all, _sync_intel, _run_kev_digest, _run_upgrade_digest
    background_tasks.add_task(_sync_intel, True)
    background_tasks.add_task(_run_autonomous_all, "schedule")
    background_tasks.add_task(_run_kev_digest)
    background_tasks.add_task(_run_upgrade_digest)
    from routes import _maybe_refresh_benchmarks, _signoff_reminders, _record_all_snapshots
    background_tasks.add_task(_maybe_refresh_benchmarks)
    background_tasks.add_task(_signoff_reminders)
    background_tasks.add_task(_record_all_snapshots)
    from deploy import backup_all_orgs, run_health_alerts
    background_tasks.add_task(backup_all_orgs)
    background_tasks.add_task(run_health_alerts)
    from deploy import _run_audit_room_expiry_reminders
    background_tasks.add_task(_run_audit_room_expiry_reminders)
    return {"status": "accepted"}


def _studio_markdown(report: dict) -> str:
    lines = []
    if report.get("ai_narrative"):
        lines += ["## Executive Narrative", report["ai_narrative"], ""]
    for b in report.get("blocks", []):
        lines.append(f"## {b['heading']}")
        lines += b.get("lines", [])
        lines.append("")
    return "\n".join(lines)


async def _run_studio_reports(cadences):
    orgs = await db.organizations.find({"studio_schedule.enabled": True}).to_list(1000)
    for org in orgs:
        org_id = str(org["_id"])
        sch = org.get("studio_schedule") or {}
        if (sch.get("cadence") or "monthly") not in cadences:
            continue
        sections = sch.get("sections") or []
        if not sections:
            continue
        title = sch.get("title") or "Scheduled Report"
        try:
            report = await _compose_report(org_id, title, sections)
            html = _report_html(_studio_markdown(report), title)
            recipients = await db.users.find(
                {"org_id": org_id, "role": {"$in": ["admin", "executive"]}}).to_list(200)
            for r in recipients:
                await notifications.send_email(r["email"], f"{title} — Obserra EIOS", html)
            await notifications.create(
                org_id, "report", "Scheduled Studio report delivered",
                f"'{title}' emailed to {len(recipients)} executive(s)/admin(s).", ref="studio-report")
            logger.info(f"Studio report ({','.join(cadences)}) sent for org {org_id} to {len(recipients)} recipients")
        except Exception as e:
            logger.error(f"Scheduled studio report failed for org {org_id}: {e}")


@scheduled_router.post("/cron/monthly-studio-report")
async def monthly_studio_report(request: Request, background_tasks: BackgroundTasks):
    # Cron endpoints must ack 2xx immediately; enqueue/background the actual work.
    if not _authorized(request):
        raise HTTPException(status_code=401, detail="Unauthorized")
    from datetime import datetime, timezone
    cadences = {"monthly"}
    if datetime.now(timezone.utc).month in (1, 4, 7, 10):
        cadences.add("quarterly")
    background_tasks.add_task(_run_studio_reports, cadences)
    return {"status": "accepted"}


@scheduled_router.post("/cron/weekly-studio-report")
async def weekly_studio_report(request: Request, background_tasks: BackgroundTasks):
    # Cron endpoints must ack 2xx immediately; enqueue/background the actual work.
    if not _authorized(request):
        raise HTTPException(status_code=401, detail="Unauthorized")
    background_tasks.add_task(_run_studio_reports, {"weekly"})
    return {"status": "accepted"}


def _degraded_email_html(label, detail):
    return ("<div style=\"font:400 14px Arial;color:#1f2937;max-width:560px;margin:auto\">"
            f"<h2 style=\"color:#0f1e3d\">{label} connector degraded</h2>"
            f"<p>The live {label} connection stopped responding on the daily health check — the "
            "credential/secret may have expired or permissions changed. The connector is still "
            "enabled but is no longer returning live data.</p>"
            f"<p style=\"font-family:monospace;color:#b91c1c\">{detail}</p>"
            "<p>Update the credentials in Available Connectors to restore the live sync.</p>"
            "<p style=\"font-size:11px;color:#9ca3af\">Obserra — Executive Protection &amp; Intelligence LLC</p></div>")


async def _run_connector_health():
    """Zero-touch daily connector health check + live asset discovery.

    Re-verifies every LIVE credential connector (M365/Copilot/ChatGPT) AND re-probes every
    catalog connector (36-provider) that has saved credentials. Connectors stay live (auto-connect
    model); this refreshes state/metrics, flips a silently-expired connector to degraded, posts a
    Slack/Teams alert (+ email + in-app) once, and re-maps live devices/users/connectors into the
    Risk Engine as assets so their IP/MAC/site + compliance/role posture affect ALE."""
    from datetime import datetime, timezone
    from live_connectors import _verify_m365, _verify_copilot, _verify_openai
    from self_scan import _post_chat_alert
    from asset_discovery import discover_and_map_assets
    from connectors_catalog import CATALOG, _probe, _persist
    now = datetime.now(timezone.utc).isoformat()
    today = datetime.now(timezone.utc).date().isoformat()
    cat_by_id = {e["id"]: e for e in CATALOG}
    orgs = await db.organizations.find({}).to_list(1000)

    async def _alert(org_id, label, detail, ref, dedupe):
        recips = await db.users.find(
            {"org_id": org_id, "role": {"$in": ["admin", "executive"]}}, {"_id": 0, "email": 1}).to_list(200)
        for r in recips:
            await notifications.send_email(r["email"], f"{label} connector degraded", _degraded_email_html(label, detail))
        await notifications.create(org_id, "connector", f"{label} connector degraded",
                                   detail, ref=ref, dedupe_key=dedupe)
        await _post_chat_alert(org_id, f"⚠ {label} connector degraded",
                               f"{detail} Update the credentials in Available Connectors to restore the live connection.")
        logger.warning(f"{label} connector degraded for org {org_id}: {detail}")

    for org in orgs:
        org_id = str(org["_id"])
        degraded = []
        # ---- Legacy live credential connectors (M365 / Copilot / ChatGPT) ----
        for kind, label in (("m365", "Microsoft 365"), ("copilot", "Microsoft Copilot"), ("openai", "ChatGPT (OpenAI)")):
            d = org.get(f"live_{kind}")
            if not d:
                continue
            had_sync = bool(d.get("synced_at"))
            ok, status = False, ""
            try:
                if kind == "m365":
                    ok, uc, ru, status = await _verify_m365(d["tenant_id"], d["client_id"], d["client_secret"])
                    if ok:
                        if uc is not None:
                            d["user_count"] = uc
                        if ru is not None:
                            d["risky_users"] = ru
                elif kind == "copilot":
                    ok, seats, status = await _verify_copilot(d["tenant_id"], d["client_id"], d["client_secret"])
                    if ok and seats is not None:
                        d["seats"] = seats
                else:
                    ok, mc, status = await _verify_openai(d["api_key"], d.get("org"))
                    if ok and mc is not None:
                        d["model_count"] = mc
            except Exception as e:
                ok, status = False, f"Re-verify failed: {str(e)[:120]}"
            d["checked_at"] = now
            if status:
                d["status"] = status
            if ok:
                d["synced_at"] = now
            await db.organizations.update_one({"_id": org["_id"]}, {"$set": {f"live_{kind}": d}})
            if had_sync and not ok:
                degraded.append(label)
                await _alert(org_id, label, f"Live {label} re-verification failed: {status}",
                             ref=f"live-{kind}", dedupe=f"{kind}-degraded:{today}")

        # ---- Catalog connectors (36-provider) — re-probe every provider with saved credentials ----
        states = await db.connector_state.find({"org_id": org_id}).to_list(200)
        for st in states:
            cid = st.get("cid")
            entry = cat_by_id.get(cid)
            saved = st.get("creds")
            if not entry or not saved:
                continue
            was_connected = st.get("state") == "connected"
            try:
                state, code, ep, detail, source = await _probe(entry, saved)
            except Exception as e:
                state, code, ep, detail, source = "unreachable", None, cid, f"Re-probe error: {str(e)[:120]}", "saved"
            await _persist(org_id, entry, state, code, ep, detail, source or "saved", creds=saved)
            if was_connected and state != "connected":
                degraded.append(entry["name"])
                await _alert(org_id, entry["name"], f"Daily re-probe returned '{state}': {detail}",
                             ref=f"cx-{cid}", dedupe=f"cx-degraded:{cid}:{today}")

        # ---- Zero-touch discovery: re-map live devices/users/connectors into the Risk Engine ----
        try:
            mapped = await discover_and_map_assets(org_id)
            if any(mapped.get(k) for k in ("devices", "users", "connectors")):
                logger.info(f"Zero-touch mapped assets for org {org_id}: {mapped}")
        except Exception as e:
            logger.error(f"Asset discovery failed for org {org_id}: {e}")

        # ---- Defensibility Ledger record of the sweep ----
        try:
            await db.remediation_ledger.insert_one({
                "org_id": org_id, "id": uuid.uuid4().hex, "action": "connector-health", "by": "cron:daily",
                "provider": "catalog+live", "verified": not degraded,
                "status": (f"{len(degraded)} degraded" if degraded else "all healthy"),
                "message": ("Daily zero-touch health check re-probed connectors and re-mapped live assets. "
                            + ("Degraded: " + ", ".join(degraded) if degraded else "All connectors healthy.")),
                "started_at": now, "finished_at": datetime.now(timezone.utc).isoformat()})
        except Exception as e:
            logger.error(f"Health ledger write failed for org {org_id}: {e}")


def _connector_digest_html(rows):
    trs = "".join(
        f'<tr><td style="padding:7px 8px;border-bottom:1px solid #eee;font:400 13px Arial;color:#1f2937">{name}</td>'
        f'<td style="padding:7px 8px;border-bottom:1px solid #eee;font:700 12px Arial;color:{color}">{state}</td>'
        f'<td style="padding:7px 8px;border-bottom:1px solid #eee;font:400 12px Arial;color:#6b7280;text-align:right">{detail}</td></tr>'
        for name, state, color, detail in rows)
    return ('<table width="100%" cellpadding="0" cellspacing="0" style="max-width:600px;margin:auto;background:#fff"><tr><td style="padding:24px">'
            '<div style="font:800 18px Arial;color:#0f1e3d">Weekly Connector Health Digest</div>'
            '<div style="font:400 12px Arial;color:#6b7280;margin-bottom:14px">Obserra — Executive Protection &amp; Intelligence LLC</div>'
            f'<table style="width:100%;border-collapse:collapse">{trs}</table>'
            '<div style="border-top:1px solid #e5e7eb;margin-top:16px;padding-top:10px;font:400 10px Arial;color:#9ca3af">'
            'Sign in → Available Connectors to manage credentials and re-check any degraded source.</div>'
            '</td></tr></table>')


async def _run_connector_digest():
    orgs = await db.organizations.find({}).to_list(1000)
    for org in orgs:
        org_id = str(org["_id"])
        try:
            rows = []
            live_specs = (("live_m365", "Microsoft 365", "user_count", "users"),
                          ("live_copilot", "Microsoft Copilot", "seats", "seats"),
                          ("live_openai", "ChatGPT (OpenAI)", "model_count", "models"),
                          ("live_sso", "SSO / SAML", None, None),
                          ("live_teams", "Microsoft Teams", None, None))
            for key, name, metric, unit in live_specs:
                d = org.get(key)
                if not d:
                    continue
                on = bool(d.get("live") or d.get("valid"))
                synced = d.get("synced_at")
                if metric and d.get(metric) is not None:
                    detail = f"{d[metric]} {unit} · synced" if synced else f"{d[metric]} {unit}"
                else:
                    detail = "syncing" if synced else "awaiting first sync"
                rows.append((name, "LIVE" if on else "degraded", "#16a34a" if on else "#dc2626", detail))
            cats = await db.enterprise_connectors.find({"org_id": org_id, "status": "connected"}).to_list(50)
            for c in cats:
                rows.append((c["name"], "connected", "#16a34a", c.get("category", "")))
            if not rows:
                continue
            html = _connector_digest_html(rows)
            recips = await db.users.find(
                {"org_id": org_id, "role": {"$in": ["admin", "executive"]}}, {"_id": 0, "email": 1}).to_list(200)
            if not recips:
                continue
            live_n = sum(1 for r in rows if r[1] in ("LIVE", "connected"))
            for r in recips:
                await notifications.send_email(r["email"], f"Weekly Connector Digest — {live_n} live source(s)", html)
            await notifications.create(
                org_id, "connector", "Weekly connector digest sent",
                f"Summary of {len(rows)} connector(s) ({live_n} live) emailed to {len(recips)} admin(s)/exec(s).",
                ref="connector-digest")
            logger.info(f"Connector digest sent for org {org_id}: {len(rows)} connectors")
        except Exception as e:
            logger.error(f"Connector digest failed for org {org_id}: {e}")


@scheduled_router.post("/cron/connector-health")
async def connector_health(request: Request, background_tasks: BackgroundTasks):
    # Cron endpoints must ack 2xx immediately; enqueue/background the actual work.
    if not _authorized(request):
        raise HTTPException(status_code=401, detail="Unauthorized")
    background_tasks.add_task(_run_connector_health)
    return {"status": "accepted"}


def _spend_report_html(rows):
    trs = "".join(
        f"<tr><td style='padding:6px;border-bottom:1px solid #eee'>{r['month']}</td>"
        f"<td style='padding:6px;border-bottom:1px solid #eee'>{r['user']}</td>"
        f"<td style='padding:6px;border-bottom:1px solid #eee;text-align:right'>{r['queries']}</td>"
        f"<td style='padding:6px;border-bottom:1px solid #eee;text-align:right'>{r['tokens']}</td>"
        f"<td style='padding:6px;border-bottom:1px solid #eee;text-align:right'>${r['cost_usd']:.4f}</td></tr>"
        for r in rows)
    total = sum(r["cost_usd"] for r in rows)
    return ("<div style=\"font:400 14px Arial;color:#1f2937;max-width:680px;margin:auto\">"
            "<h2 style=\"color:#0f1e3d\">AI Advisor — Monthly Spend Report</h2>"
            f"<p>Full advisor spend per teammate. Total to date: <b>${total:.4f}</b>.</p>"
            "<table style=\"border-collapse:collapse;width:100%;font-size:13px\">"
            "<thead><tr style=\"background:#0f1e3d;color:#fff\">"
            "<th style='padding:6px;text-align:left'>Month</th><th style='padding:6px;text-align:left'>Teammate</th>"
            "<th style='padding:6px;text-align:right'>Queries</th><th style='padding:6px;text-align:right'>Tokens</th>"
            "<th style='padding:6px;text-align:right'>Cost</th></tr></thead>"
            f"<tbody>{trs}</tbody></table>"
            "<p style=\"font-size:11px;color:#9ca3af\">Obserra — Executive Protection &amp; Intelligence LLC</p></div>")


def _spend_csv_b64(rows):
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["Month", "Teammate", "Queries", "Tokens", "Cost (USD)"])
    for r in rows:
        w.writerow([r["month"], r["user"], r["queries"], r["tokens"], f"{r['cost_usd']:.4f}"])
    w.writerow(["ALL", "TOTAL", sum(r["queries"] for r in rows),
                sum(r["tokens"] for r in rows), f"{sum(r['cost_usd'] for r in rows):.4f}"])
    return base64.b64encode(buf.getvalue().encode()).decode()


async def _run_spend_report():
    orgs = await db.organizations.find({}).to_list(1000)
    for org in orgs:
        org_id = str(org["_id"])
        rows = await spend_rows(org_id, "all")
        if not rows:
            continue
        html = _spend_report_html(rows)
        attachments = [{"filename": "advisor-spend-all.csv", "content": _spend_csv_b64(rows)}]
        recips = await db.users.find(
            {"org_id": org_id, "role": {"$in": ["admin", "executive"]}}, {"_id": 0, "email": 1}).to_list(200)
        for r in recips:
            await notifications.send_email(r["email"], "Monthly AI Advisor Spend Report", html, attachments=attachments)
        await notifications.create(
            org_id, "report", "Advisor spend report emailed",
            f"Full advisor spend (with CSV attachment) emailed to {len(recips)} admin(s)/exec(s).", ref="advisor-spend")
        logger.info(f"Advisor spend report emailed for org {org_id} to {len(recips)} recipients")


@scheduled_router.post("/cron/monthly-spend-report")
async def monthly_spend_report(request: Request, background_tasks: BackgroundTasks):
    # Cron endpoints must ack 2xx immediately; enqueue/background the actual work.
    if not _authorized(request):
        raise HTTPException(status_code=401, detail="Unauthorized")
    background_tasks.add_task(_run_spend_report)
    return {"status": "accepted"}
