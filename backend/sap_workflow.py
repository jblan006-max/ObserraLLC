"""Obserra SAP UAC — ServiceNow workflow activity stream + evidence export (attached to the shared sap_router)."""
import os
import io
import csv
from datetime import timedelta

from fastapi import Depends, HTTPException
from fastapi.responses import Response

from db import db
from auth import get_current_user
from sap_engine import _now, _ensure
from sap_uac import sap_router


@sap_router.get("/workflow/activity")
async def workflow_activity(q: str = "", prefix: str = "", system: str = "",
                            action: str = "", days: int = 0, user: dict = Depends(get_current_user)):
    """Live, filterable stream of every ServiceNow ticket the platform opened & auto-closed."""
    org_id = user["org_id"]
    await _ensure(org_id)
    tickets = await db.sap_snow_tickets.find({"org_id": org_id}, {"_id": 0}).sort("opened_at", -1).to_list(1000)
    by_prefix, by_system, by_type = {}, {}, {}
    for t in tickets:
        pf = (t.get("number") or "REQ")[:3]
        by_prefix[pf] = by_prefix.get(pf, 0) + 1
        by_type[t["type"]] = by_type.get(t["type"], 0) + 1
        for s in t.get("systems_touched", []):
            by_system[s] = by_system.get(s, 0) + 1
    ql = q.lower().strip()
    cutoff = (_now() - timedelta(days=days)).isoformat() if days and days > 0 else None
    day_ago = (_now() - timedelta(days=1)).isoformat()
    rows = []
    for t in tickets:
        if prefix and (t.get("number") or "")[:3] != prefix:
            continue
        if system and system not in t.get("systems_touched", []):
            continue
        if action and t.get("action") != action:
            continue
        if cutoff and (t.get("opened_at") or "") < cutoff:
            continue
        if ql and ql not in (f"{t.get('number','')} {t.get('type','')} {t.get('person_name') or ''} "
                             f"{t.get('requested_by') or ''} {t.get('reason') or ''}").lower():
            continue
        rows.append(t)
    return {
        "tickets": rows[:400], "total": len(rows), "all_total": len(tickets),
        "summary": {
            "total": len(tickets),
            "closed": sum(1 for t in tickets if t.get("state") == "Closed"),
            "open": sum(1 for t in tickets if t.get("state") != "Closed"),
            "last_24h": sum(1 for t in tickets if (t.get("opened_at") or "") >= day_ago),
            "auto_closed": sum(1 for t in tickets if t.get("auto_closed")),
            "avg_duration_sec": round(sum(t.get("duration_sec", 0) for t in tickets) / len(tickets), 1) if tickets else 0,
        },
        "by_prefix": by_prefix,
        "by_system": sorted(({"name": k, "value": v} for k, v in by_system.items()), key=lambda x: -x["value"]),
        "by_type": sorted(({"name": k, "value": v} for k, v in by_type.items()), key=lambda x: -x["value"])[:12],
        "systems": sorted(by_system.keys()),
        "actions": sorted({t.get("action") for t in tickets if t.get("action")}),
        "generated_at": _now().isoformat(),
    }


def _filter_workflow(tickets, q, prefix, system, action, days):
    ql = (q or "").lower().strip()
    cutoff = (_now() - timedelta(days=days)).isoformat() if days and days > 0 else None
    rows = []
    for t in tickets:
        if prefix and (t.get("number") or "")[:3] != prefix:
            continue
        if system and system not in t.get("systems_touched", []):
            continue
        if action and t.get("action") != action:
            continue
        if cutoff and (t.get("opened_at") or "") < cutoff:
            continue
        if ql and ql not in (f"{t.get('number','')} {t.get('type','')} {t.get('person_name') or ''} "
                             f"{t.get('requested_by') or ''} {t.get('reason') or ''}").lower():
            continue
        rows.append(t)
    return rows


def _workflow_evidence_pdf(rows):
    """Branded SOX-grade PDF evidence pack of ServiceNow workflows (open→auto-close)."""
    from reportlab.lib.pagesizes import LETTER, landscape
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage
    pw, ph = landscape(LETTER)
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=(pw, ph), topMargin=0.7 * inch, bottomMargin=0.7 * inch,
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
    flow.append(Paragraph("SAP Access Governance — Workflow Evidence Pack", title_st))
    flow.append(Paragraph(f"ServiceNow automated remediation & access workflows · {len(rows)} record(s) · "
                          f"Generated {_now().strftime('%B %d, %Y %H:%M UTC')}", sub_st))
    flow.append(Spacer(1, 10))
    data = [[Paragraph(h, head) for h in ["Ticket", "Workflow", "Action", "Systems Touched", "Subject", "Opened", "State"]]]
    for t in rows[:600]:
        data.append([
            Paragraph(t.get("number", ""), cell),
            Paragraph(t.get("type", ""), cell),
            Paragraph(t.get("action", "") or "—", cell),
            Paragraph(" · ".join(t.get("systems_touched", [])) or "—", cell),
            Paragraph((t.get("person_name") or t.get("reason") or "—"), cell),
            Paragraph((t.get("opened_at") or "")[:19].replace("T", " "), cell),
            Paragraph(t.get("state", ""), cell),
        ])
    tbl = Table(data, colWidths=[0.85 * inch, 1.9 * inch, 1.15 * inch, 2.25 * inch, 1.9 * inch, 1.25 * inch, 0.75 * inch], repeatRows=1)
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
                          "Every workflow is a real ServiceNow-orchestrated action recorded end-to-end.", sub_st))
    doc.build(flow)
    buf.seek(0)
    return buf


@sap_router.get("/workflow/activity/export")
async def workflow_activity_export(format: str = "csv", q: str = "", prefix: str = "", system: str = "",
                                   action: str = "", days: int = 0, user: dict = Depends(get_current_user)):
    """Export the filtered ServiceNow workflow stream as a CSV or branded PDF SOX evidence pack."""
    org_id = user["org_id"]
    await _ensure(org_id)
    if format not in ("csv", "pdf"):
        raise HTTPException(status_code=400, detail="format must be csv or pdf")
    tickets = await db.sap_snow_tickets.find({"org_id": org_id}, {"_id": 0}).sort("opened_at", -1).to_list(2000)
    rows = _filter_workflow(tickets, q, prefix, system, action, days)
    fname = f"sap-workflow-evidence-{_now().strftime('%Y%m%d-%H%M')}"
    if format == "csv":
        sio = io.StringIO()
        w = csv.writer(sio)
        w.writerow(["Ticket", "Workflow", "Action", "State", "Systems Touched", "Subject",
                    "Requested By", "Reason", "Opened", "Closed", "Duration (s)", "Auto-closed"])
        for t in rows:
            w.writerow([t.get("number", ""), t.get("type", ""), t.get("action", ""), t.get("state", ""),
                        " · ".join(t.get("systems_touched", [])), t.get("person_name") or "",
                        t.get("requested_by") or "", t.get("reason") or "", t.get("opened_at") or "",
                        t.get("closed_at") or "", t.get("duration_sec", 0), "yes" if t.get("auto_closed") else "no"])
        return Response(content=sio.getvalue(), media_type="text/csv",
                        headers={"Content-Disposition": f'attachment; filename="{fname}.csv"'})
    pdf = _workflow_evidence_pdf(rows)
    return Response(content=pdf.getvalue(), media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="{fname}.pdf"'})
