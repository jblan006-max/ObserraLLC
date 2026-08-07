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
    from bson import ObjectId
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
