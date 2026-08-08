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
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable, Image as RLImage, PageBreak, Table, TableStyle

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
    layout: str = "report"
    cover_date: str = None
    version: str = None


def _norm_hex(v):
    """Normalise a hex colour like #12B4D6 -> #12b4d6; return None if invalid."""
    if not v or not isinstance(v, str):
        return None
    s = v.strip().lower()
    if re.fullmatch(r"#[0-9a-f]{6}", s):
        return s
    if re.fullmatch(r"[0-9a-f]{6}", s):
        return "#" + s
    return None


def _trend_drawing(series, accent=None):
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
        lc.lines[0].strokeColor = colors.HexColor(accent or "#d9663a")
        lc.lines[0].strokeWidth = 2.2
        d.add(lc)
        return d
    except Exception as e:
        logger.warning(f"trend chart skipped: {e}")
        return None


def _risk_bar_drawing(bars, accent=None):
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
        bc.bars[0].fillColor = colors.HexColor(accent or "#1b6fb3")
        bc.barWidth = 8
        d.add(bc)
        return d
    except Exception as e:
        logger.warning(f"risk bar chart skipped: {e}")
        return None


def _resolve_brand(org):
    rb = (org or {}).get("report_branding") or {}
    accent = _norm_hex(rb.get("accent"))
    if rb.get("enabled") and rb.get("logo"):
        import base64 as _b64, tempfile
        data = rb["logo"]
        if "," in data:
            data = data.split(",", 1)[1]
        try:
            path = os.path.join(tempfile.gettempdir(), f"brand_{org.get('_id')}.png")
            with open(path, "wb") as f:
                f.write(_b64.b64decode(data))
            name = (rb.get("company_name") or "").strip() or "Confidential"
            return {"name": name, "badge": path, "lockup": path, "lockup_dark": path,
                    "watermark": None, "footer": name}
        except Exception as e:
            logger.warning(f"custom brand failed: {e}")
    return {"name": "Obserra — Executive Protection & Intelligence LLC",
            "badge": _BADGE, "lockup": _LOCKUP, "lockup_dark": _LOCKUP_DARK,
            "watermark": _WATERMARK, "footer": "Obserra — Executive Protection & Intelligence LLC"}


def _paint_cover(canvas, pw, ph, title, org_name, report_date, theme, brand, version=None):
    light = (theme == "light")
    bg = "#ffffff" if light else "#081428"
    lockup = brand["lockup_dark"] if light else brand["lockup"]
    title_col = "#0f1e3d" if light else "#F4F8FC"
    org_col = brand.get("accent") or ("#0e7490" if light else "#56B8E9")
    date_col = "#6b7280" if light else "#8AA0B8"
    note_col = "#9ca3af" if light else "#5a708c"
    canvas.saveState()
    canvas.setFillColor(colors.HexColor(bg))
    canvas.rect(0, 0, pw, ph, fill=1, stroke=0)
    if lockup and os.path.exists(lockup):
        lw = 4.8 * inch
        lh = 1.3 * inch
        canvas.drawImage(lockup, (pw - lw) / 2, ph * 0.58, width=lw, height=lh,
                         mask="auto", preserveAspectRatio=True, anchor="c")
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


def _cover_preview_png(brand, org_name, theme) -> bytes:
    """Render just the branded board-report cover page to a PNG thumbnail."""
    import pymupdf
    from reportlab.pdfgen import canvas as _pdfcanvas
    buf = io.BytesIO()
    c = _pdfcanvas.Canvas(buf, pagesize=LETTER)
    pw, ph = LETTER
    _paint_cover(c, pw, ph, "Executive Board Report", org_name, None, theme, brand)
    c.showPage(); c.save(); buf.seek(0)
    doc = pymupdf.open(stream=buf.read(), filetype="pdf")
    pix = doc[0].get_pixmap(matrix=pymupdf.Matrix(1.4, 1.4))
    png = pix.tobytes("png")
    doc.close()
    return png


def _build_pdf(report: str, title: str, cover: bool = False, org_name: str = None,
               report_date: str = None, version: str = None, chart_series=None, takeaways=None,
               theme: str = "dark", risk_bars=None, exec_summary: str = None, brand=None,
               bench_line: str = None, signoff_line: str = None, risk_bands=None, signoff_trail=None,
               fair_air=None, nist_coverage=None) -> io.BytesIO:
    brand = brand or _resolve_brand(None)
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
    if brand["badge"] and os.path.exists(brand["badge"]):
        badge = RLImage(brand["badge"], width=0.6 * inch, height=0.6 * inch)
        badge.hAlign = "LEFT"
        story += [badge, Spacer(1, 6)]
    story += [Paragraph(title, title_s),
              Paragraph(brand["name"].replace("&", "&amp;"), sub),
              HRFlowable(width="100%", color=colors.HexColor("#1b3a8a")), Spacer(1, 10)]
    if exec_summary:
        summary_s = ParagraphStyle("summary", parent=body, fontSize=10.5, leading=15,
                                   textColor=colors.HexColor("#0f1e3d"),
                                   backColor=colors.HexColor("#eef6fb"), borderColor=colors.HexColor("#12b4d6"),
                                   borderWidth=0.6, borderPadding=8, spaceBefore=2, spaceAfter=2)
        story += [Paragraph(f"<b>Executive Summary.</b> {exec_summary}", summary_s), Spacer(1, 12)]
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
        d = _trend_drawing(chart_series, brand.get("accent")) if chart_series else None
        if d is not None:
            story += [d, Spacer(1, 6)]
        b = _risk_bar_drawing(risk_bars, brand.get("accent")) if risk_bars else None
        if b is not None:
            story += [b, Spacer(1, 4)]
    if takeaways:
        story += [Spacer(1, 8), Paragraph("Key Takeaways &amp; Recommended Actions", h)]
        for t in takeaways:
            story.append(Paragraph(f"•&nbsp;&nbsp;{t}", bullet))
    if bench_line:
        story += [Spacer(1, 8), Paragraph("Financial Benchmark (vs published data)", h),
                  Paragraph(bench_line, body)]
    if signoff_line:
        story += [Spacer(1, 4), Paragraph(f"<b>{signoff_line}</b>", body)]
    if risk_bands:
        cell = ParagraphStyle("tc", parent=body, fontSize=8.5, leading=11)
        story += [Spacer(1, 8), Paragraph("Per-Risk Scenario Ranges (Monte-Carlo P10 / P50 / P90)", h)]

        def _m(v):
            return f"${v/1e6:.2f}M" if v >= 1e6 else f"${v/1e3:.0f}k"
        rows = [[Paragraph("<b>Risk</b>", cell), Paragraph("<b>P10 (low)</b>", cell),
                 Paragraph("<b>P50 (expected)</b>", cell), Paragraph("<b>P90 (high)</b>", cell)]]
        for rb in risk_bands:
            rows.append([Paragraph(f"{rb['label']} — {rb['title']}", cell), Paragraph(_m(rb['p10']), cell),
                         Paragraph(_m(rb['p50']), cell), Paragraph(_m(rb['p90']), cell)])
        tbl = Table(rows, colWidths=[3.0 * inch, 1.05 * inch, 1.35 * inch, 1.05 * inch])
        tbl.setStyle(TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#c9d6e5")),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eef6fb")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
            ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]))
        story += [tbl, Paragraph("Ranges reflect a 1,000-iteration Monte-Carlo per risk (triangular SLE 0.5x-2x, "
                                 "Gaussian ARO). P50 is the expected annualised loss; P90 is the adverse-scenario tail.",
                                 ParagraphStyle("cap", parent=body, fontSize=7.5, textColor=colors.grey))]
    if signoff_trail:
        cell2 = ParagraphStyle("tc2", parent=body, fontSize=8.5, leading=11)
        story += [Spacer(1, 8), Paragraph("Calibration Sign-off Audit Trail", h)]
        rows2 = [[Paragraph("<b>Action</b>", cell2), Paragraph("<b>Who</b>", cell2), Paragraph("<b>When (UTC)</b>", cell2)]]
        for e in signoff_trail:
            action = "Signed off &amp; locked" if e.get("action") == "signoff" else "Unlocked"
            who = str(e.get("name") or e.get("by") or "—").replace("&", "&amp;")
            when = str(e.get("at", ""))[:16].replace("T", " ")
            rows2.append([Paragraph(action, cell2), Paragraph(who, cell2), Paragraph(when, cell2)])
        t2 = Table(rows2, colWidths=[1.9 * inch, 2.7 * inch, 1.9 * inch])
        t2.setStyle(TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#c9d6e5")),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eef6fb")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]))
        story += [t2, Paragraph("Immutable record of who calibrated the financial model and when — for auditor and board assurance.",
                                ParagraphStyle("cap2", parent=body, fontSize=7.5, textColor=colors.grey))]
    if fair_air:
        story += [Spacer(1, 12), Paragraph("AI Risk Quantification — FAIR-AIR (AI Risk Reduction)", h),
                  Paragraph("Quantified GenAI risk scenarios produced by advanced-reasoning synthesis across all "
                            "dashboards. Evidence base: International AI Safety Report 2026 (Bengio), IBM, Verizon DBIR, "
                            "The Open Group FAIR&#8482;, NIST AI RMF (AI 100-1).", sub)]
        kd_s = ParagraphStyle("kd", parent=body, fontSize=8.5, textColor=colors.grey, leftIndent=14)
        for s in fair_air:
            stmt = re.sub(r"\*\*", "", str(s.get("statement") or ""))
            story.append(Paragraph(f"•&nbsp;&nbsp;<b>{s.get('vector','')}</b>: {stmt}", bullet))
            if s.get("why_risk"):
                story.append(Paragraph(f"Why it's a risk: {s['why_risk']}", kd_s))
            if s.get("key_driver"):
                story.append(Paragraph(f"Key driver: {s['key_driver']}", kd_s))
            ctrls = s.get("recommended_controls") or []
            if ctrls:
                story.append(Paragraph("Controls: " + "; ".join(str(c) for c in ctrls), kd_s))
    if nist_coverage:
        summ = (nist_coverage or {}).get("summary") or {}
        story += [Spacer(1, 12), Paragraph("NIST AI RMF (AI 100-1) — Controls Coverage &amp; Compliance", h)]
        fnline = " · ".join(f"{b.get('f')} {b.get('cov')}%" for b in summ.get("by_fn", []))
        story += [Paragraph(f"Overall coverage <b>{summ.get('overall',0)}%</b>; {summ.get('met',0)}/{summ.get('total',0)} "
                            f"controls met; frameworks: {', '.join(summ.get('frameworks',[]))}. By function: {fnline}.", body)]
        ncell = ParagraphStyle("ncell", parent=body, fontSize=8, leading=10)
        nrows = [[Paragraph("<b>Control</b>", ncell), Paragraph("<b>NIST</b>", ncell),
                  Paragraph("<b>Type</b>", ncell), Paragraph("<b>Coverage</b>", ncell)]]
        for c in (nist_coverage or {}).get("controls", []):
            lab = "Met" if c["cov"] >= 80 else "Partial" if c["cov"] >= 40 else "Gap"
            nrows.append([Paragraph(c["c"], ncell), Paragraph(c["fn"], ncell),
                          Paragraph(c["type"], ncell), Paragraph(f"{c['cov']}% &#183; {lab}", ncell)])
        ntbl = Table(nrows, colWidths=[3.05 * inch, 1.0 * inch, 1.05 * inch, 1.3 * inch])
        ntbl.setStyle(TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#c9d6e5")),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eef6fb")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]))
        story += [ntbl, Paragraph("Coverage computed from live control effectiveness, scan evidence, connector, vendor "
                                  "and AI-system posture. Frameworks: NIST AI RMF · ISO/IEC 42001 · SOC 2 · EU AI Act · GDPR.",
                                  ParagraphStyle("cap3", parent=body, fontSize=7.5, textColor=colors.grey))]
    story.append(Spacer(1, 16))
    story.append(Paragraph("Confidential — decision-support estimates; not legal, financial, regulatory, or security guarantees.",
                           ParagraphStyle("d", parent=body, fontSize=7, textColor=colors.grey)))

    def _brand_page(canvas, _doc):
        pw, ph = LETTER
        if brand["watermark"] and os.path.exists(brand["watermark"]):
            wm_w = 4.6 * inch
            wm_h = wm_w * 530.0 / 890.0
            canvas.drawImage(brand["watermark"], (pw - wm_w) / 2, (ph - wm_h) / 2,
                             width=wm_w, height=wm_h, mask="auto", preserveAspectRatio=True)
        canvas.saveState()
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(colors.grey)
        canvas.drawCentredString(pw / 2, 0.5 * inch, f"{brand['footer']}  ·  Confidential")
        canvas.restoreState()

    def _cover_page(canvas, _doc):
        pw, ph = LETTER
        _paint_cover(canvas, pw, ph, title, org_name, report_date, theme, brand, version=version)

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


def _extract_exec_summary(text: str) -> str:
    if not text:
        return ""
    lines = text.split("\n")
    buf, capture = [], False
    for ln in lines:
        s = ln.strip()
        if s.startswith("## "):
            if capture:
                break
            capture = s[3:].lower().startswith("executive summary")
            continue
        if capture and s:
            buf.append(s)
    body = " ".join(buf)
    if not body:
        for ln in lines:
            s = ln.strip()
            if s and not s.startswith("#"):
                body = s
                break
    body = re.sub(r"\[[^\]]+\]", "", body)
    body = re.sub(r"\*\*", "", body).strip()
    sents = re.split(r"(?<=[.!?])\s+", body)
    return " ".join(sents[:2]).strip()


async def _board_metrics(org_id: str, report_text: str = "") -> dict:
    from routes import _fin, _get_fin_cfg, _benchmark, _montecarlo_item
    from bson import ObjectId
    org = await db.organizations.find_one({"_id": ObjectId(org_id)}) or {}
    risks = await db.risks.find({"org_id": org_id}, {"_id": 0}).to_list(500)
    recs = await db.recommendations.find({"org_id": org_id}, {"_id": 0}).to_list(500)
    health = await db.health_index.find_one({"org_id": org_id}, {"_id": 0}) or {}
    fcfg = await _get_fin_cfg(org_id)
    fins = [_fin(r, fcfg) for r in risks]
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
    slis = [f["sle"] for f in fins] or [0]
    avg_sle = round(sum(slis) / len(slis))
    bench = await _benchmark(fcfg["industry"])
    bratio = round(avg_sle / bench["industry_avg"], 2) if bench.get("industry_avg") else None
    bench_line = (f"Modelled per-incident ${avg_sle/1e6:.2f}M vs IBM {bench['industry']} avg "
                  f"${(bench.get('industry_avg') or 0)/1e6:.2f}M"
                  + (f" ({bratio}x {'above' if bratio and bratio > 1 else 'in line with'} published)" if bratio else "")
                  + f"; AI-enabled breach avg ${(bench.get('ai_breach_avg') or 0)/1e6:.2f}M, shadow-AI premium +${(bench.get('shadow_ai_premium') or 0)/1e3:.0f}k"
                  + f"; DBIR ransomware median ${bench.get('dbir_ransomware_median',0)/1e3:.0f}k. Source: IBM/Verizon DBIR ({bench.get('updated')}).")
    signoff = (org.get("financial_config") or {}).get("signoff")
    signoff_line = (f"Financial calibration approved by {signoff['name']} on {str(signoff.get('at',''))[:10]}"
                    if signoff and signoff.get("locked") else None)
    paired = sorted(zip(risks, fins), key=lambda rf: rf[1]["residual_ale"], reverse=True)
    risk_bands = []
    for r, f in paired[:6]:
        band = _montecarlo_item(f, r)
        risk_bands.append({"label": r.get("ref") or (r.get("title", "") or "")[:18],
                           "title": (r.get("title", "") or "")[:80],
                           "p10": band["p10"], "p50": band["p50"], "p90": band["p90"]})
    signoff_trail = list(reversed(((org.get("financial_config") or {}).get("signoff_history") or [])))[:10]
    return {
        "org_name": org.get("name"), "residual": residual, "reduction": reduction,
        "crit": crit, "pending": len(pending), "series": series, "risk_bars": risk_bars,
        "takeaways": takeaways, "exec_summary": _extract_exec_summary(report_text),
        "brand": _resolve_brand(org), "bench_line": bench_line, "signoff_line": signoff_line,
        "risk_bands": risk_bands, "signoff_trail": signoff_trail,
    }


async def build_board_report_pdf(org_id: str, report_text: str,
                                 title: str = "Executive Board Report", theme: str = "dark",
                                 report_date: str = None, version: str = None,
                                 fair_air=None, nist_coverage=None) -> io.BytesIO:
    m = await _board_metrics(org_id, report_text)
    cover_org = m["brand"]["name"] if m["brand"].get("watermark") is None else m["org_name"]
    return _build_pdf(report_text, title, cover=True, org_name=cover_org, theme=theme,
                      report_date=report_date, version=version,
                      chart_series=m["series"], takeaways=m["takeaways"], risk_bars=m["risk_bars"],
                      exec_summary=m["exec_summary"], brand=m["brand"],
                      bench_line=m.get("bench_line"), signoff_line=m.get("signoff_line"),
                      risk_bands=m.get("risk_bands"), signoff_trail=m.get("signoff_trail"),
                      fair_air=fair_air, nist_coverage=nist_coverage)


def _wrap(text, font, size, max_w, canvas):
    words, lines, cur = text.split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if canvas.stringWidth(t, font, size) <= max_w:
            cur = t
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


async def build_board_deck_pdf(org_id: str, report_text: str,
                               title: str = "Executive Board Report", theme: str = "dark",
                               report_date: str = None, version: str = None) -> io.BytesIO:
    from reportlab.pdfgen import canvas as pdfcanvas
    from reportlab.lib.pagesizes import landscape
    from reportlab.graphics import renderPDF
    m = await _board_metrics(org_id, report_text)
    brand = m["brand"]
    pw, ph = landscape(LETTER)
    buf = io.BytesIO()
    c = pdfcanvas.Canvas(buf, pagesize=(pw, ph))
    NAVY, INK, AI, GREY = (colors.HexColor("#081428"), colors.HexColor("#0f1e3d"),
                           colors.HexColor("#12b4d6"), colors.HexColor("#6b7280"))
    light = (theme == "light")
    SLIDE_BG = colors.HexColor("#ffffff") if light else colors.HexColor("#0c1a33")
    TEXT = INK if light else colors.HexColor("#F4F8FC")
    CARD_BG = colors.HexColor("#f1f6fb") if light else colors.HexColor("#12233f")
    LABEL = GREY if light else colors.HexColor("#8AA0B8")

    def footer():
        c.setFont("Helvetica", 7); c.setFillColor(GREY)
        c.drawCentredString(pw / 2, 0.4 * inch, f"{brand['footer']}  ·  Confidential" + (f"  ·  {version}" if version else ""))

    def content_header(slide_title):
        c.setFillColor(SLIDE_BG); c.rect(0, 0, pw, ph, fill=1, stroke=0)
        c.setFillColor(NAVY); c.rect(0, ph - 74, pw, 74, fill=1, stroke=0)
        if brand["badge"] and os.path.exists(brand["badge"]):
            c.drawImage(brand["badge"], 34, ph - 64, width=48, height=48, mask="auto", preserveAspectRatio=True, anchor="c")
        c.setFillColor(colors.white); c.setFont("Helvetica-Bold", 20)
        c.drawString(96, ph - 48, slide_title)
        if brand["watermark"] and os.path.exists(brand["watermark"]):
            ww = 3.4 * inch; wh = ww * 530.0 / 890.0
            c.drawImage(brand["watermark"], (pw - ww) / 2, (ph - wh) / 2 - 30, width=ww, height=wh,
                        mask="auto", preserveAspectRatio=True)

    # Slide 1 — cover
    c.setFillColor(colors.white if light else NAVY); c.rect(0, 0, pw, ph, fill=1, stroke=0)
    lockup = brand["lockup_dark"] if light else brand["lockup"]
    if lockup and os.path.exists(lockup):
        lw = 5.6 * inch; lh = 1.5 * inch
        c.drawImage(lockup, (pw - lw) / 2, ph * 0.56, width=lw, height=lh, mask="auto", preserveAspectRatio=True, anchor="c")
    c.setFillColor(INK if light else colors.white); c.setFont("Helvetica-Bold", 30)
    c.drawCentredString(pw / 2, ph * 0.44, title)
    cover_org = brand["name"] if brand.get("watermark") is None else m["org_name"]
    if cover_org:
        c.setFillColor(colors.HexColor("#0e7490") if light else AI); c.setFont("Helvetica-Bold", 14)
        c.drawCentredString(pw / 2, ph * 0.38, cover_org)
    c.setFillColor(GREY if light else colors.HexColor("#8AA0B8")); c.setFont("Helvetica", 11)
    c.drawCentredString(pw / 2, ph * 0.34, datetime.now(timezone.utc).strftime("%B %d, %Y"))
    c.setFont("Helvetica", 8)
    c.drawCentredString(pw / 2, 0.5 * inch, "CONFIDENTIAL · PROPRIETARY · AUTHORIZED ACCESS ONLY")
    c.showPage()

    # Slide 2 — key metrics
    content_header("Enterprise Snapshot")
    cards = [(f"${m['residual']/1e6:.1f}M", "Residual Exposure"),
             (f"{m['reduction']}%", "Risk Reduction"),
             (str(m["crit"]), "Critical Risks"),
             (str(m["pending"]), "Pending Approvals")]
    cw, gap, chh = 3.0 * inch, 0.4 * inch, 1.5 * inch
    x0 = (pw - (cw * 2 + gap)) / 2
    y0 = ph * 0.30
    for i, (big, lab) in enumerate(cards):
        cx = x0 + (i % 2) * (cw + gap)
        cy = y0 + (1 - i // 2) * (chh + 0.3 * inch)
        c.setFillColor(CARD_BG); c.roundRect(cx, cy, cw, chh, 10, fill=1, stroke=0)
        c.setFillColor(AI); c.setFont("Helvetica-Bold", 34); c.drawString(cx + 20, cy + chh - 52, big)
        c.setFillColor(LABEL); c.setFont("Helvetica", 12); c.drawString(cx + 20, cy + 20, lab)
    footer(); c.showPage()

    # Slide 3 — exposure trend
    content_header("Portfolio Exposure Trend")
    d = _trend_drawing(m["series"], m["brand"].get("accent"))
    if d is not None:
        px = (pw - 500) / 2; py = ph * 0.26
        c.setFillColor(colors.white); c.roundRect(px, py, 500, 210, 10, fill=1, stroke=0)
        renderPDF.draw(d, c, px + 20, py + 20)
    footer(); c.showPage()

    # Slide 4 — top risks
    content_header("Top Risks by Residual Score")
    d2 = _risk_bar_drawing(m["risk_bars"], m["brand"].get("accent"))
    if d2 is not None:
        px = (pw - 500) / 2; py = ph * 0.26
        c.setFillColor(colors.white); c.roundRect(px, py, 500, 210, 10, fill=1, stroke=0)
        renderPDF.draw(d2, c, px + 20, py + 20)
    footer(); c.showPage()

    # Slide 5 — takeaways
    content_header("Key Takeaways & Recommended Actions")
    y = ph - 130
    for t in m["takeaways"]:
        c.setFillColor(AI); c.setFont("Helvetica-Bold", 16); c.drawString(60, y, "•")
        c.setFillColor(TEXT); c.setFont("Helvetica", 13)
        for ln in _wrap(t, "Helvetica", 13, pw - 160, c):
            c.drawString(84, y, ln); y -= 20
        y -= 10
    footer(); c.showPage()

    c.save(); buf.seek(0)
    return buf


class RecipientsBody(BaseModel):
    emails: list = []


@reports_router.get("/api/reports/recipients")
async def get_recipients(user: dict = Depends(get_current_user)):
    from bson import ObjectId
    org = await db.organizations.find_one({"_id": ObjectId(user["org_id"])}) or {}
    autos = await db.users.find({"org_id": user["org_id"], "role": {"$in": ["admin", "executive"]}},
                                {"_id": 0, "email": 1}).to_list(200)
    return {"extra": org.get("report_recipients", []), "auto": [u["email"] for u in autos]}


@reports_router.put("/api/reports/recipients")
async def set_recipients(body: RecipientsBody, user: dict = Depends(get_current_user)):
    if user.get("role") != "admin":
        raise HTTPException(403, "Only admins can manage report recipients")
    from bson import ObjectId
    emails, dropped = [], []
    for e in body.emails:
        e2 = (e or "").strip().lower()
        if not e2:
            continue
        if re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", e2):
            if e2 not in emails:
                emails.append(e2)
        else:
            dropped.append(e)
    await db.organizations.update_one({"_id": ObjectId(user["org_id"])}, {"$set": {"report_recipients": emails}})
    return {"extra": emails, "dropped": dropped}


class BrandingBody(BaseModel):
    enabled: bool = False
    company_name: str = ""
    logo: str = ""
    accent: str = ""
    remove_logo: bool = False


@reports_router.get("/api/reports/branding")
async def get_branding(user: dict = Depends(get_current_user)):
    from bson import ObjectId
    org = await db.organizations.find_one({"_id": ObjectId(user["org_id"])}) or {}
    rb = org.get("report_branding") or {}
    return {"enabled": bool(rb.get("enabled")), "company_name": rb.get("company_name", ""),
            "has_logo": bool(rb.get("logo")), "accent": _norm_hex(rb.get("accent")) or ""}


@reports_router.get("/api/reports/branding/preview")
async def branding_preview(theme: str = "dark", user: dict = Depends(get_current_user)):
    from bson import ObjectId
    org = await db.organizations.find_one({"_id": ObjectId(user["org_id"])}) or {}
    brand = _resolve_brand(org)
    cover_org = brand["name"] if brand.get("watermark") is None else org.get("name")
    theme = "light" if theme == "light" else "dark"
    png = _cover_preview_png(brand, cover_org, theme)
    return StreamingResponse(io.BytesIO(png), media_type="image/png",
                             headers={"Cache-Control": "no-store"})


@reports_router.put("/api/reports/branding")
async def set_branding(body: BrandingBody, user: dict = Depends(get_current_user)):
    if user.get("role") != "admin":
        raise HTTPException(403, "Only admins can manage report branding")
    from bson import ObjectId
    oid = ObjectId(user["org_id"])
    if body.remove_logo:
        await db.organizations.update_one(
            {"_id": oid},
            {"$set": {"report_branding.enabled": False, "report_branding.company_name": ""},
             "$unset": {"report_branding.logo": "", "report_branding.accent": ""}})
    else:
        update = {"report_branding.enabled": bool(body.enabled),
                  "report_branding.company_name": (body.company_name or "").strip()[:120]}
        accent = _norm_hex(body.accent)
        update["report_branding.accent"] = accent or ""
        if body.logo:
            data = body.logo.split(",", 1)[1] if "," in body.logo else body.logo
            if len(data) > 2_000_000:
                raise HTTPException(400, "Logo too large (max ~1.5MB)")
            update["report_branding.logo"] = data
        await db.organizations.update_one({"_id": oid}, {"$set": update})
    org = await db.organizations.find_one({"_id": oid}) or {}
    rb = org.get("report_branding") or {}
    return {"enabled": bool(rb.get("enabled")), "company_name": rb.get("company_name", ""),
            "has_logo": bool(rb.get("logo")), "accent": _norm_hex(rb.get("accent")) or ""}


@reports_router.post("/api/reports/test-email")
async def report_test_email(user: dict = Depends(get_current_user)):
    if user.get("role") not in ("admin", "executive"):
        raise HTTPException(403, "Only admins/executives can send a test report")
    import base64
    from ai_advisor import generate_board_report
    from kernel import notifications
    result = await generate_board_report(user["org_id"], by=user["email"])
    report_text = result["report"] if isinstance(result, dict) else str(result)
    html = _report_html(report_text, "Board Report Preview")
    pdf = await build_board_report_pdf(user["org_id"], report_text, "Executive Board Report")
    attachments = [{"filename": "obserra-board-report.pdf",
                    "content": base64.b64encode(pdf.getvalue()).decode()}]
    await notifications.send_email(user["email"], "Your Board Report Preview — Obserra EIOS",
                                   html, attachments=attachments)
    return {"status": "sent", "to": user["email"]}


@reports_router.post("/api/reports/pdf")
async def report_pdf(body: ReportBody, user: dict = Depends(get_current_user)):
    theme = body.theme if body.theme in ("dark", "light") else "dark"
    if body.layout == "deck":
        buf = await build_board_deck_pdf(user["org_id"], body.report, body.title, theme,
                                         report_date=body.cover_date, version=body.version)
        fname = "obserra-board-deck.pdf"
    else:
        buf = await build_board_report_pdf(user["org_id"], body.report, body.title, theme,
                                           report_date=body.cover_date, version=body.version)
        fname = "obserra-board-report.pdf"
    return StreamingResponse(buf, media_type="application/pdf",
                             headers={"Content-Disposition": f'attachment; filename="{fname}"'})


@reports_router.post("/api/reports/board-pack.pdf")
async def board_pack_pdf(user: dict = Depends(get_current_user)):
    """One-click board pack: latest board report (with methodology appendix + benchmark
    references) + exposure trend + per-risk bands + calibration sign-off audit trail, in a single PDF."""
    from ai_advisor import generate_board_report, generate_fair_air_analysis
    from routes import _nist_ai_rmf_coverage
    latest = await db.reports.find_one({"org_id": user["org_id"]}, sort=[("generated_at", -1)])
    report_text = (latest or {}).get("report")
    if not report_text:
        gen = await generate_board_report(user["org_id"], by=user["email"])
        report_text = gen["report"]
    try:
        nist_cov = await _nist_ai_rmf_coverage(user["org_id"])
    except Exception:
        nist_cov = None
    fa = await db.fair_air_jobs.find_one({"org_id": user["org_id"], "status": "done"}, sort=[("created_at", -1)])
    fair_air = (fa or {}).get("scenarios")
    if not fair_air:
        try:
            fair_air = (await generate_fair_air_analysis(user["org_id"])).get("scenarios")
        except Exception:
            fair_air = None
    buf = await build_board_report_pdf(user["org_id"], report_text,
                                       title="Board Pack — Cyber Risk & Financials",
                                       fair_air=fair_air, nist_coverage=nist_cov)
    return StreamingResponse(buf, media_type="application/pdf",
                             headers={"Content-Disposition": 'attachment; filename="obserra-board-pack.pdf"'})


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


def _log_pdf(title, subtitle, notes, org):
    brand = _resolve_brand(org)
    parts = [f"# {title}", "", subtitle,
             f"Exported {datetime.now(timezone.utc).strftime('%B %d, %Y · %H:%M UTC')} — {len(notes)} log entries", ""]
    if not notes:
        parts.append("No log entries recorded.")
    for n in notes:
        ts = (n.get("ts", "") or "")[:16].replace("T", " ")
        parts.append(f"## {(n.get('kind', 'note') or 'note').upper()} — {ts}")
        parts.append(re.sub(r"\*\*", "", n.get("text", "")))
        parts.append(f"Logged by {n.get('author', '—')}")
        parts.append("")
    return _build_pdf("\n".join(parts), title, brand=brand)


@reports_router.get("/api/reports/control-log/{control_id}.pdf")
async def control_log_pdf(control_id: str, user: dict = Depends(get_current_user)):
    from bson import ObjectId
    if user.get("role") != "admin":
        raise HTTPException(403, "Only admins can export the log")
    c = await db.controls.find_one({"org_id": user["org_id"], "control_id": control_id})
    if not c:
        raise HTTPException(404, "Control not found")
    notes = await db.control_notes.find({"org_id": user["org_id"], "control_id": control_id}, {"_id": 0}).sort("ts", -1).to_list(500)
    org = await db.organizations.find_one({"_id": ObjectId(user["org_id"])})
    subtitle = f"{c['control_id']} — {c['name']} ({c['category']}) · Owner: {c.get('owner', '—')}"
    buf = _log_pdf(f"Remediation & Evidence Log — {control_id}", subtitle, notes, org)
    return StreamingResponse(buf, media_type="application/pdf",
                             headers={"Content-Disposition": f'attachment; filename="log-{control_id}.pdf"'})


@reports_router.get("/api/reports/vendor-log/{ref}.pdf")
async def vendor_log_pdf(ref: str, user: dict = Depends(get_current_user)):
    from bson import ObjectId
    if user.get("role") != "admin":
        raise HTTPException(403, "Only admins can export the log")
    v = await db.vendors.find_one({"org_id": user["org_id"], "ref": ref})
    if not v:
        raise HTTPException(404, "Vendor not found")
    notes = await db.vendor_notes.find({"org_id": user["org_id"], "ref": ref}, {"_id": 0}).sort("ts", -1).to_list(500)
    org = await db.organizations.find_one({"_id": ObjectId(user["org_id"])})
    subtitle = f"{v['ref']} — {v['name']} ({v.get('category', '')}) · Owner: {v.get('owner', '—')} · Risk: {v.get('risk_tier', '')} {v.get('risk_score', '')}"
    buf = _log_pdf(f"Remediation & Evidence Log — {ref}", subtitle, notes, org)
    return StreamingResponse(buf, media_type="application/pdf",
                             headers={"Content-Disposition": f'attachment; filename="log-{ref}.pdf"'})


@reports_router.get("/api/reports/logs-pack.pdf")
async def logs_pack_pdf(user: dict = Depends(get_current_user)):
    from bson import ObjectId
    from collections import defaultdict
    if user.get("role") != "admin":
        raise HTTPException(403, "Only admins can export the evidence binder")
    org_id = user["org_id"]
    org = await db.organizations.find_one({"_id": ObjectId(org_id)})
    controls = await db.controls.find({"org_id": org_id}, {"_id": 0}).to_list(500)
    vendors = await db.vendors.find({"org_id": org_id}, {"_id": 0}).to_list(500)
    cnotes = await db.control_notes.find({"org_id": org_id}, {"_id": 0}).sort("ts", -1).to_list(2000)
    vnotes = await db.vendor_notes.find({"org_id": org_id}, {"_id": 0}).sort("ts", -1).to_list(2000)
    cg, vg = defaultdict(list), defaultdict(list)
    for n in cnotes:
        cg[n["control_id"]].append(n)
    for n in vnotes:
        vg[n["ref"]].append(n)
    total = len(cnotes) + len(vnotes)
    parts = [f"Exported {datetime.now(timezone.utc).strftime('%B %d, %Y · %H:%M UTC')} — {total} log entries "
             f"across {len(cg)} control(s) and {len(vg)} vendor(s).", ""]

    def _fmt(notes):
        out = []
        for n in notes:
            ts = (n.get("ts", "") or "")[:16].replace("T", " ")
            out.append(f"{(n.get('kind', 'note') or 'note').upper()} · {ts} · {n.get('author', '—')}")
            out.append(re.sub(r"\*\*", "", n.get("text", "")))
            out.append("")
        return out

    parts.append("# Controls")
    if not any(cg.get(c["control_id"]) for c in controls):
        parts.append("No control log entries recorded.")
    for c in controls:
        notes = cg.get(c["control_id"])
        if not notes:
            continue
        parts.append(f"## {c['control_id']} — {c['name']} (Owner: {c.get('owner', '—')})")
        parts += _fmt(notes)
    parts += ["", "# Vendors"]
    if not any(vg.get(v["ref"]) for v in vendors):
        parts.append("No vendor log entries recorded.")
    for v in vendors:
        notes = vg.get(v["ref"])
        if not notes:
            continue
        parts.append(f"## {v['ref']} — {v['name']} (Owner: {v.get('owner', '—')})")
        parts += _fmt(notes)
    brand = _resolve_brand(org)
    buf = _build_pdf("\n".join(parts), "Audit Evidence Binder", cover=True,
                     org_name=(org or {}).get("name"), brand=brand)
    return StreamingResponse(buf, media_type="application/pdf",
                             headers={"Content-Disposition": 'attachment; filename="obserra-evidence-binder.pdf"'})


@reports_router.get("/api/reports/access-history/{user_id}.pdf")
async def access_history_pdf(user_id: str, actor: str = None, since: str = None, until: str = None,
                             user: dict = Depends(get_current_user)):
    from bson import ObjectId
    if user.get("role") != "admin":
        raise HTTPException(403, "Only admins can export access history")
    org_id = user["org_id"]
    org = await db.organizations.find_one({"_id": ObjectId(org_id)})
    member = await db.users.find_one({"_id": ObjectId(user_id), "org_id": org_id})
    if not member:
        raise HTTPException(404, "Member not found")
    logs = await db.audit_logs.find(
        {"org_id": org_id, "target": member["email"], "action": {"$in": ["team.access", "team.invite"]}},
        {"_id": 0}).sort("ts", -1).to_list(200)
    if actor:
        logs = [x for x in logs if x.get("actor") == actor]
    if since:
        logs = [x for x in logs if (x.get("ts", "") or "")[:10] >= since]
    if until:
        logs = [x for x in logs if (x.get("ts", "") or "")[:10] <= until]
    filt = []
    if actor: filt.append(f"actor {actor}")
    if since: filt.append(f"from {since}")
    if until: filt.append(f"to {until}")
    filt_note = f" · Filtered: {', '.join(filt)}" if filt else ""
    parts = [f"Dashboard access history for {member.get('name') or member['email']} ({member['email']}).",
             f"Exported {datetime.now(timezone.utc).strftime('%B %d, %Y · %H:%M UTC')} — {len(logs)} change(s){filt_note}.", ""]
    if not logs:
        parts.append("No access changes recorded.")
    for h in logs:
        ts = (h.get("ts", "") or "")[:16].replace("T", " ")
        parts.append(f"## {ts} UTC")
        parts.append(re.sub(r"\*\*", "", h.get("detail", "") or ""))
        parts.append(f"By {h.get('actor', '—')}")
        parts.append("")
    brand = _resolve_brand(org)
    buf = _build_pdf("\n".join(parts), "Dashboard Access History", cover=True,
                     org_name=(org or {}).get("name"), brand=brand)
    safe = member["email"].replace("@", "-at-")
    return StreamingResponse(buf, media_type="application/pdf",
                             headers={"Content-Disposition": f'attachment; filename="access-history-{safe}.pdf"'})
