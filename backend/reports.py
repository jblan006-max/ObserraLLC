import os
import io
import re
import logging
import httpx
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable

from db import db
from auth import get_current_user

logger = logging.getLogger(__name__)
reports_router = APIRouter()
EMAIL_BASE_URL = "https://integrations.emergentagent.com"


class ReportBody(BaseModel):
    report: str
    title: str = "Executive Board Report"


def _build_pdf(report: str, title: str) -> io.BytesIO:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=LETTER, topMargin=0.9 * inch, bottomMargin=0.8 * inch)
    styles = getSampleStyleSheet()
    h = ParagraphStyle("h", parent=styles["Heading2"], textColor=colors.HexColor("#12b4d6"), spaceBefore=12, spaceAfter=4)
    body = ParagraphStyle("b", parent=styles["BodyText"], fontSize=10, leading=15)
    title_s = ParagraphStyle("t", parent=styles["Title"], fontSize=18, textColor=colors.HexColor("#0f1e3d"))
    sub = ParagraphStyle("sub", parent=body, textColor=colors.grey)
    story = [Paragraph(title, title_s),
             Paragraph("Obserra — Executive Protection &amp; Intelligence LLC", sub),
             HRFlowable(width="100%", color=colors.HexColor("#1b3a8a")), Spacer(1, 10)]
    for line in report.split("\n"):
        line = line.strip()
        if not line:
            story.append(Spacer(1, 6)); continue
        if line.startswith("## "):
            story.append(Paragraph(line[3:], h))
        elif line.startswith("# "):
            story.append(Paragraph(line[2:], h))
        else:
            story.append(Paragraph(re.sub(r"\*\*", "", line), body))
    story.append(Spacer(1, 16))
    story.append(Paragraph("Confidential — decision-support estimates; not legal, financial, regulatory, or security guarantees.",
                           ParagraphStyle("d", parent=body, fontSize=7, textColor=colors.grey)))
    doc.build(story)
    buf.seek(0)
    return buf


def _report_html(report: str, title: str) -> str:
    rows = []
    for line in report.split("\n"):
        line = line.strip()
        if not line:
            continue
        if line.startswith("## "):
            rows.append(f'<tr><td style="padding:14px 0 4px;font:600 15px Arial;color:#0e7490">{line[3:]}</td></tr>')
        elif line.startswith("# "):
            rows.append(f'<tr><td style="padding:8px 0;font:700 18px Arial;color:#0f1e3d">{line[2:]}</td></tr>')
        else:
            rows.append(f'<tr><td style="padding:3px 0;font:400 13px Arial;color:#1f2937;line-height:1.5">{line.replace("**", "")}</td></tr>')
    inner = "".join(rows)
    return (f'<table width="100%" cellpadding="0" cellspacing="0" style="max-width:640px;margin:auto;background:#ffffff">'
            f'<tr><td style="padding:24px">'
            f'<div style="font:800 20px Arial;color:#0f1e3d">{title}</div>'
            f'<div style="font:400 12px Arial;color:#6b7280;margin-bottom:12px">Obserra — Executive Protection &amp; Intelligence LLC</div>'
            f'<table width="100%">{inner}</table>'
            f'<div style="border-top:1px solid #e5e7eb;margin-top:18px;padding-top:10px;font:400 10px Arial;color:#9ca3af">'
            f'Confidential — decision-support estimates; not legal, financial, regulatory, or security guarantees.</div>'
            f'</td></tr></table>')


@reports_router.post("/api/reports/pdf")
async def report_pdf(body: ReportBody, user: dict = Depends(get_current_user)):
    buf = _build_pdf(body.report, body.title)
    return StreamingResponse(buf, media_type="application/pdf",
                             headers={"Content-Disposition": 'attachment; filename="obserra-board-report.pdf"'})


@reports_router.post("/api/reports/email")
async def report_email(body: ReportBody, user: dict = Depends(get_current_user)):
    payload = {"to": [user["email"]], "subject": f"{body.title} — Obserra EIOS",
               "html": _report_html(body.report, body.title), "from_name": os.environ["EMAIL_FROM_NAME"]}
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(f"{EMAIL_BASE_URL}/api/v1/email/send",
                                     headers={"X-Email-Key": os.environ["EMERGENT_EMAIL_KEY"]}, json=payload)
        resp.raise_for_status()
    except Exception as e:
        logger.error(f"Email send error: {e}")
        raise HTTPException(status_code=502, detail="Failed to send email")
    return {"status": "sent", "to": user["email"]}


@reports_router.get("/api/reports")
async def list_reports(user: dict = Depends(get_current_user)):
    return await db.reports.find({"org_id": user["org_id"]}, {"_id": 0}).sort("generated_at", -1).to_list(50)
