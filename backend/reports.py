import os
import io
import re
import logging
import httpx
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable, Image as RLImage, PageBreak

from db import db
from auth import get_current_user

logger = logging.getLogger(__name__)
reports_router = APIRouter()
EMAIL_BASE_URL = "https://integrations.emergentagent.com"
_ASSETS = os.path.join(os.path.dirname(__file__), "assets")
_BADGE = os.path.join(_ASSETS, "brand-badge.png")
_WATERMARK = os.path.join(_ASSETS, "brand-watermark.png")
_LOCKUP = os.path.join(_ASSETS, "brand-lockup.png")
_LOCKUP_DARK = os.path.join(_ASSETS, "brand-lockup-dark.png")
BRAND_IMG_URL = "https://customer-assets-39nsmqrw.emergentagent.net/job_cyber-dashboard-48/artifacts/5h8fj2gx_image.png"


class ReportBody(BaseModel):
    report: str
    title: str = "Executive Board Report"
    theme: str = "dark"


def _trend_drawing(series):
    """Line chart of portfolio residual exposure ($M) over recent months."""
    try:
        from reportlab.graphics.shapes import Drawing, String
        from reportlab.graphics.charts.linecharts import HorizontalLineChart
        pts = [round(p.get("exposure", 0) / 1e6, 2) for p in series][-6:]
        labels = [str(p.get("month", "")) for p in series][-6:]
        if len(pts) < 2:
            return None
        d = Drawing(460, 170)
        d.add(String(38, 152, "Portfolio Residual Exposure ($M)", fontName="Helvetica-Bold",
                     fontSize=9, fillColor=colors.HexColor("#0f1e3d")))
        lc = HorizontalLineChart()
        lc.x = 40; lc.y = 24; lc.width = 400; lc.height = 116
        lc.data = [pts]
        lc.categoryAxis.categoryNames = labels
        lc.categoryAxis.labels.fontSize = 7
        lc.valueAxis.valueMin = 0
        lc.valueAxis.labelTextFormat = "$%0.1fM"
        lc.valueAxis.labels.fontSize = 7
        lc.lines[0].strokeColor = colors.HexColor("#d9663a")
        lc.lines[0].strokeWidth = 2.2
        d.add(lc)
        return d
    except Exception as e:
        logger.warning(f"trend chart skipped: {e}")
        return None


def _risk_bar_drawing(bars):
    """Bar chart of top risks by residual score (0-25)."""
    try:
        from reportlab.graphics.shapes import Drawing, String
        from reportlab.graphics.charts.barcharts import VerticalBarChart
        bars = [b for b in (bars or []) if b.get("value")][:5]
        if not bars:
            return None
        d = Drawing(460, 175)
        d.add(String(38, 158, "Top Risks by Residual Score (/25)", fontName="Helvetica-Bold",
                     fontSize=9, fillColor=colors.HexColor("#0f1e3d")))
        bc = VerticalBarChart()
        bc.x = 40; bc.y = 28; bc.width = 400; bc.height = 112
        bc.data = [[b["value"] for b in bars]]
        bc.categoryAxis.categoryNames = [b["label"] for b in bars]
        bc.categoryAxis.labels.fontSize = 7
        bc.valueAxis.valueMin = 0
        bc.valueAxis.valueMax = 25
        bc.valueAxis.valueStep = 5
        bc.valueAxis.labels.fontSize = 7
        bc.bars[0].fillColor = colors.HexColor("#1b6fb3")
        bc.barWidth = 8
        d.add(bc)
        return d
    except Exception as e:
        logger.warning(f"risk bar chart skipped: {e}")
        return None


def _build_pdf(report: str, title: str, cover: bool = False, org_name: str = None,
               report_date: str = None, chart_series=None, takeaways=None,
               theme: str = "dark", risk_bars=None) -> io.BytesIO:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=LETTER, topMargin=0.9 * inch, bottomMargin=0.8 * inch)
    styles = getSampleStyleSheet()
    h = ParagraphStyle("h", parent=styles["Heading2"], textColor=colors.HexColor("#12b4d6"), spaceBefore=12, spaceAfter=4)
    body = ParagraphStyle("b", parent=styles["BodyText"], fontSize=10, leading=15)
    title_s = ParagraphStyle("t", parent=styles["Title"], fontSize=18, textColor=colors.HexColor("#0f1e3d"))
    sub = ParagraphStyle("sub", parent=body, textColor=colors.grey)
    bullet = ParagraphStyle("bl", parent=body, leftIndent=12, spaceAfter=4)
    story = []
    if cover:
        story.append(PageBreak())  # page 1 is painted by _cover_page
    if os.path.exists(_BADGE):
        badge = RLImage(_BADGE, width=0.6 * inch, height=0.6 * inch)
        badge.hAlign = "LEFT"
        story += [badge, Spacer(1, 6)]
    story += [Paragraph(title, title_s),
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
    if chart_series or risk_bars:
        story += [Spacer(1, 10), Paragraph("Portfolio Trends", h)]
        d = _trend_drawing(chart_series) if chart_series else None
        if d is not None:
            story += [d, Spacer(1, 6)]
        b = _risk_bar_drawing(risk_bars) if risk_bars else None
        if b is not None:
            story += [b, Spacer(1, 4)]
    if takeaways:
        story += [Spacer(1, 8), Paragraph("Key Takeaways &amp; Recommended Actions", h)]
        for t in takeaways:
            story.append(Paragraph(f"•&nbsp;&nbsp;{t}", bullet))
    story.append(Spacer(1, 16))
    story.append(Paragraph("Confidential — decision-support estimates; not legal, financial, regulatory, or security guarantees.",
                           ParagraphStyle("d", parent=body, fontSize=7, textColor=colors.grey)))

    def _brand_page(canvas, _doc):
        pw, ph = LETTER
        if os.path.exists(_WATERMARK):
            wm_w = 4.6 * inch
            wm_h = wm_w * 530.0 / 890.0
            canvas.drawImage(_WATERMARK, (pw - wm_w) / 2, (ph - wm_h) / 2,
                             width=wm_w, height=wm_h, mask="auto", preserveAspectRatio=True)
        canvas.saveState()
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(colors.grey)
        canvas.drawCentredString(pw / 2, 0.5 * inch, "Obserra — Executive Protection & Intelligence LLC  ·  Confidential")
        canvas.restoreState()

    def _cover_page(canvas, _doc):
        pw, ph = LETTER
        light = (theme == "light")
        bg = "#ffffff" if light else "#081428"
        lockup = _LOCKUP_DARK if light else _LOCKUP
        title_col = "#0f1e3d" if light else "#F4F8FC"
        org_col = "#0e7490" if light else "#56B8E9"
        date_col = "#6b7280" if light else "#8AA0B8"
        note_col = "#9ca3af" if light else "#5a708c"
        canvas.saveState()
        canvas.setFillColor(colors.HexColor(bg))
        canvas.rect(0, 0, pw, ph, fill=1, stroke=0)
        if os.path.exists(lockup):
            lw = 4.8 * inch
            lh = lw * 287.0 / 1698.0
            canvas.drawImage(lockup, (pw - lw) / 2, ph * 0.60, width=lw, height=lh,
                             mask="auto", preserveAspectRatio=True)
        canvas.setFillColor(colors.HexColor(title_col)); canvas.setFont("Helvetica-Bold", 24)
        canvas.drawCentredString(pw / 2, ph * 0.50, title)
        if org_name:
            canvas.setFillColor(colors.HexColor(org_col)); canvas.setFont("Helvetica-Bold", 12)
            canvas.drawCentredString(pw / 2, ph * 0.46, org_name)
        canvas.setFillColor(colors.HexColor(date_col)); canvas.setFont("Helvetica", 10)
        canvas.drawCentredString(pw / 2, ph * 0.43, report_date or datetime.now(timezone.utc).strftime("%B %d, %Y"))
        canvas.setFillColor(colors.HexColor(note_col)); canvas.setFont("Helvetica", 8)
        canvas.drawCentredString(pw / 2, 0.6 * inch, "CONFIDENTIAL · PROPRIETARY · AUTHORIZED ACCESS ONLY")
        canvas.restoreState()

    doc.build(story, onFirstPage=(_cover_page if cover else _brand_page), onLaterPages=_brand_page)
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
            f'<img src="{BRAND_IMG_URL}" width="48" height="48" alt="Obserra" style="display:block;border-radius:10px;margin-bottom:10px" />'
            f'<div style="font:800 20px Arial;color:#0f1e3d">{title}</div>'
            f'<div style="font:400 12px Arial;color:#6b7280;margin-bottom:12px">Obserra — Executive Protection &amp; Intelligence LLC</div>'
            f'<table width="100%">{inner}</table>'
            f'<div style="border-top:1px solid #e5e7eb;margin-top:18px;padding-top:10px;font:400 10px Arial;color:#9ca3af">'
            f'Confidential — decision-support estimates; not legal, financial, regulatory, or security guarantees.</div>'
            f'</td></tr></table>')


async def build_board_report_pdf(org_id: str, report_text: str,
                                 title: str = "Executive Board Report", theme: str = "dark") -> io.BytesIO:
    from routes import _fin
    from bson import ObjectId
    org = await db.organizations.find_one({"_id": ObjectId(org_id)}) or {}
    org_name = org.get("name")
    risks = await db.risks.find({"org_id": org_id}, {"_id": 0}).to_list(500)
    recs = await db.recommendations.find({"org_id": org_id}, {"_id": 0}).to_list(500)
    health = await db.health_index.find_one({"org_id": org_id}, {"_id": 0}) or {}
    fins = [_fin(r) for r in risks]
    residual = sum(f["residual_ale"] for f in fins)
    inherent = sum(f["inherent_ale"] for f in fins)
    reduction = round((inherent - residual) / inherent * 100) if inherent else 0
    top = sorted(risks, key=lambda r: r.get("residual", 0), reverse=True)
    top_title = top[0]["title"] if top else None
    pending = [r for r in recs if r.get("status") == "Pending"]
    crit = len([r for r in risks if r.get("residual", 0) >= 16])
    cur = health.get("score", 69)
    series = [{"month": hh["month"], "exposure": round(residual * (cur / max(1, hh["score"])))}
              for hh in health.get("history", [])]
    if series:
        series[-1]["exposure"] = round(residual)
    risk_bars = [{"label": (r.get("ref") or (r.get("title", "") or "")[:14]), "value": r.get("residual", 0)}
                 for r in top[:5]]
    extra = f"; prioritise '{top_title}'" if top_title else ""
    takeaways = [
        f"Portfolio residual exposure is ${residual/1e6:.1f}M, down {reduction}% from inherent — sustain the controls driving this reduction.",
    ]
    if crit:
        takeaways.append(f"{crit} critical risk(s) remain above tolerance{extra} for board-level decision this quarter.")
    if pending:
        takeaways.append(f"{len(pending)} recommendation(s) await executive authority — approve to release the projected risk reduction.")
    takeaways.append("Maintain evidence freshness and quarterly control testing to keep every figure audit-ready and board-defensible.")
    return _build_pdf(report_text, title, cover=True, org_name=org_name, theme=theme,
                      chart_series=series, takeaways=takeaways, risk_bars=risk_bars)


@reports_router.post("/api/reports/pdf")
async def report_pdf(body: ReportBody, user: dict = Depends(get_current_user)):
    theme = body.theme if body.theme in ("dark", "light") else "dark"
    buf = await build_board_report_pdf(user["org_id"], body.report, body.title, theme)
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


class PackBody(BaseModel):
    control_id: str


@reports_router.post("/api/reports/evidence-pack")
async def evidence_pack(body: PackBody, user: dict = Depends(get_current_user)):
    from routes import _FW_BY_CAT
    c = await db.controls.find_one({"org_id": user["org_id"], "control_id": body.control_id})
    if not c:
        raise HTTPException(404, "Control not found")
    fws = _FW_BY_CAT.get(c["category"], ["NIST CSF 2.0"])
    lines = [f"# Audit Evidence Pack — {c['control_id']}", "",
             "## Control",
             f"{c['control_id']} — {c['name']} ({c['category']})",
             f"Owner: {c['owner']}",
             f"Effectiveness: {c['effectiveness']}%  ·  Maturity: {c['maturity']}/5",
             f"Last tested: {c['last_tested'][:10]}  ·  Evidence expires: {c['evidence_expires'][:10]}", "",
             "## Cross-Framework Coverage"]
    for fw in fws:
        lines.append(f"- {fw}: control {c['control_id']} satisfies the applicable requirement family; evidence attached.")
    lines += ["", "## Evidence",
              f"- Continuous control-monitoring telemetry for {c['category']}",
              f"- Owner attestation by {c['owner']}",
              f"- Linked risk: {c.get('related_risk') or 'n/a'}", "",
              "## Assurance",
              "Evidence collected from connected sources; freshness, confidence and reliability tracked in-platform. Implementing this one control cascades coverage across all frameworks listed above."]
    buf = _build_pdf("\n".join(lines), f"Audit Evidence Pack — {c['control_id']}")
    return StreamingResponse(buf, media_type="application/pdf",
                             headers={"Content-Disposition": f'attachment; filename="evidence-pack-{c["control_id"]}.pdf"'})
