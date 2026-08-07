"""Scheduled tasks — platform cron webhook endpoints.

Cron endpoints must ack 2xx immediately; enqueue/background the actual work.
"""
import os
import hmac
import logging

from fastapi import APIRouter, Request, BackgroundTasks, HTTPException

from db import db
from kernel import notifications
from ai_advisor import generate_board_report
from reports import _report_html

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
            html = _report_html(result["report"], "Monthly Executive Board Report")
            for r in recipients:
                await notifications.send_email(r["email"], "Monthly Board Report — Obserra EIOS", html)
            await notifications.create(
                org_id, "report", "Monthly board report delivered",
                f"Emailed to {len(recipients)} executive(s)/admin(s).", ref="board-report")
            logger.info(f"Monthly board report sent for org {org_id} to {len(recipients)} recipients")
        except Exception as e:
            logger.error(f"Monthly board report failed for org {org_id}: {e}")


@scheduled_router.post("/cron/monthly-board-report")
async def monthly_board_report(request: Request, background_tasks: BackgroundTasks):
    # Cron endpoints must ack 2xx immediately; enqueue/background the actual work.
    if not _authorized(request):
        raise HTTPException(status_code=401, detail="Unauthorized")
    background_tasks.add_task(_run_monthly_board_reports)
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


@scheduled_router.post("/cron/weekly-drift-digest")
async def weekly_drift_digest(request: Request, background_tasks: BackgroundTasks):
    # Cron endpoints must ack 2xx immediately; enqueue/background the actual work.
    if not _authorized(request):
        raise HTTPException(status_code=401, detail="Unauthorized")
    background_tasks.add_task(_run_drift_digest, {"weekly"}, "Weekly")
    return {"status": "accepted"}


@scheduled_router.post("/cron/daily-drift-digest")
async def daily_drift_digest(request: Request, background_tasks: BackgroundTasks):
    # Cron endpoints must ack 2xx immediately; enqueue/background the actual work.
    if not _authorized(request):
        raise HTTPException(status_code=401, detail="Unauthorized")
    background_tasks.add_task(_run_drift_digest, {"daily"}, "Daily")
    return {"status": "accepted"}
