"""Obserra SAP UAC — SoD Evidence Pack (auditor CSV/PDF + scheduled weekly auto-email).
Attached to the shared sap_router. Extracted from sap_digest.py for maintainability."""
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
from sap_digest import _get_digest_config


# ── SoD Evidence Pack (auditor CSV/PDF + scheduled weekly auto-email) ─────────────────────────
def _summarize(rows):
    return {"total": len(rows), "open": sum(1 for r in rows if r["status"] == "Open"),
            "mitigated": sum(1 for r in rows if r["status"] == "Mitigated"),
            "accepted": sum(1 for r in rows if r["status"] == "Accepted"),
            "critical": sum(1 for r in rows if r["severity"] == "Critical"),
            "high": sum(1 for r in rows if r["severity"] == "High")}


def _scope_rows(rows, areas=None, systems=None):
    a = {x.lower() for x in (areas or [])}
    s = {x.lower() for x in (systems or [])}
    if not a and not s:
        return rows
    return [r for r in rows if (not a or r["area"].lower() in a) and (not s or r["system"].lower() in s)]


async def _sod_evidence_rows(org_id, status="", severity="", areas=None, systems=None):
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
    rows = _scope_rows(rows, areas, systems)
    return rows, _summarize(rows)


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


def _sod_evidence_pdf(rows, summary, prepared_by="", approved_by="", approved_at=""):
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
    flow.append(Spacer(1, 10))
    approved = bool(approved_by)
    box_color = colors.HexColor("#16a34a") if approved else (colors.HexColor("#d97706") if prepared_by else colors.HexColor("#94a3b8"))
    box_bg = colors.HexColor("#dcfce7") if approved else (colors.HexColor("#fef3c7") if prepared_by else colors.white)
    prep_line = (f"Prepared by: <b>{prepared_by}</b> · {_now().strftime('%B %d, %Y')}"
                 if prepared_by else "Prepared by: ____________________     Date: ____________")
    if approved:
        appr_line = f"Approved by: <b>{approved_by}</b> · {(approved_at or '')[:10]}"
    elif prepared_by:
        appr_line = "Approved by: <b>PENDING APPROVAL</b>     Signature: ____________________     Date: ____________"
    else:
        appr_line = "Approved by: ____________________     Signature: ____________________     Date: ____________"
    stamp_hdr = "REVIEWED &amp; APPROVED" if approved else ("REVIEWED — PENDING APPROVAL" if prepared_by else "SIGNOFF")
    sign_hd = ParagraphStyle("sgh", parent=ss["Normal"], fontSize=8, textColor=box_color, fontName="Helvetica-Bold", spaceAfter=3)
    sign_st = ParagraphStyle("sg", parent=ss["Normal"], fontSize=9.5, leading=13,
                             textColor=(colors.HexColor("#166534") if approved else navy))
    sign_tbl = Table([[Paragraph(stamp_hdr, sign_hd)], [Paragraph(prep_line, sign_st)], [Paragraph(appr_line, sign_st)]],
                     colWidths=[9.0 * inch])
    sign_tbl.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 1.2, box_color),
        ("BACKGROUND", (0, 0), (-1, -1), box_bg),
        ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 12), ("RIGHTPADDING", (0, 0), (-1, -1), 12),
    ]))
    flow.append(sign_tbl)
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


def _sod_evidence_attachment(rows, summary, prepared_by="", approved_by="", approved_at=""):
    import base64
    pdf = _sod_evidence_pdf(rows, summary, prepared_by, approved_by, approved_at)
    return [{"filename": f"sap-sod-evidence-{_now().strftime('%Y%m%d')}.pdf",
             "content": base64.b64encode(pdf.getvalue()).decode()}]


class SodEvidenceBody(BaseModel):
    prepared_by: str = ""


class SodApproveBody(BaseModel):
    approved_by: str = ""


@sap_router.get("/sod-evidence/export")
async def sod_evidence_export(format: str = "pdf", status: str = "", severity: str = "", prepared_by: str = "",
                              user: dict = Depends(get_current_user)):
    """Download the SoD evidence pack (branded PDF or auditor CSV), optionally filtered + with signoff."""
    org_id = user["org_id"]
    await _ensure(org_id)
    if format not in ("csv", "pdf"):
        raise HTTPException(status_code=400, detail="format must be csv or pdf")
    cfg = await _get_digest_config(org_id)
    rows, summary = await _sod_evidence_rows(org_id, status, severity)
    fname = f"sap-sod-evidence-{_now().strftime('%Y%m%d-%H%M')}"
    if format == "csv":
        return Response(content=_sod_evidence_csv(rows, summary), media_type="text/csv",
                        headers={"Content-Disposition": f'attachment; filename="{fname}.csv"'})
    prep = (prepared_by or cfg.get("evidence_prepared_by") or "").strip()[:120]
    pdf = _sod_evidence_pdf(rows, summary, prep, cfg.get("evidence_approved_by", ""), cfg.get("evidence_approved_at", ""))
    return Response(content=pdf.getvalue(), media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="{fname}.pdf"'})


@sap_router.get("/sod-evidence/preview")
async def sod_evidence_preview(user: dict = Depends(get_current_user)):
    """Live preview of exactly what the weekly auto-emailed SoD evidence pack will contain (per recipient scope)."""
    org_id = user["org_id"]
    await _ensure(org_id)
    cfg = await _get_digest_config(org_id)
    rows, summary = await _sod_evidence_rows(org_id)
    emails = cfg.get("evidence_recipients") or [r["email"] for r in await db.users.find(
        {"org_id": org_id, "role": {"$in": ["admin", "executive"]}}, {"_id": 0, "email": 1}).to_list(200)]
    scopes = {s["email"].lower(): s for s in (cfg.get("auditor_scopes") or [])}
    recips_detail = []
    for e in emails:
        sc = scopes.get(e.lower())
        rws = _scope_rows(rows, sc.get("areas"), sc.get("systems")) if sc else rows
        recips_detail.append({"email": e, "conflicts": len(rws), "scoped": bool(sc),
                              "areas": sc.get("areas") if sc else [], "systems": sc.get("systems") if sc else []})
    return {"html": _sod_evidence_html(summary), "summary": summary, "rows": rows[:25],
            "recipients": emails, "recipients_detail": recips_detail, "evidence_day": cfg.get("evidence_day", "mon"),
            "prepared_by": cfg.get("evidence_prepared_by", ""), "approved_by": cfg.get("evidence_approved_by", ""),
            "approved_at": cfg.get("evidence_approved_at", ""), "enabled": bool(cfg.get("evidence_export"))}


@sap_router.post("/sod-evidence/approve")
async def sod_evidence_approve(body: SodApproveBody, user: dict = Depends(require_roles("admin"))):
    """Step 2 of the signoff — record the approver + timestamp stamped on the evidence pack."""
    org_id = user["org_id"]
    await _ensure(org_id)
    cfg = await _get_digest_config(org_id)
    if not cfg.get("evidence_prepared_by"):
        raise HTTPException(status_code=400, detail="Set a 'Prepared by' name and save before approving.")
    approver = (body.approved_by or user.get("name") or user["email"]).strip()[:120]
    at = _now().isoformat()
    await db.sap_digest_config.update_one({"org_id": org_id},
        {"$set": {"evidence_approved_by": approver, "evidence_approved_at": at}}, upsert=True)
    await _audit(org_id, user["email"], "sap.sod.evidence.approve", f"approved by {approver}")
    return {"ok": True, "approved_by": approver, "approved_at": at}


@sap_router.post("/sod-evidence/unapprove")
async def sod_evidence_unapprove(user: dict = Depends(require_roles("admin"))):
    org_id = user["org_id"]
    await _ensure(org_id)
    await db.sap_digest_config.update_one({"org_id": org_id},
        {"$set": {"evidence_approved_by": "", "evidence_approved_at": ""}})
    await _audit(org_id, user["email"], "sap.sod.evidence.unapprove", "approval revoked")
    return {"ok": True}


@sap_router.post("/sod-evidence/send")
async def sod_evidence_send(body: SodEvidenceBody, user: dict = Depends(require_roles("admin"))):
    """Email the SoD evidence pack now — each auditor gets a pack scoped to their assigned areas/systems."""
    org_id = user["org_id"]
    await _ensure(org_id)
    from kernel import notifications
    cfg = await _get_digest_config(org_id)
    rows, summary = await _sod_evidence_rows(org_id)
    prepared = (body.prepared_by or cfg.get("evidence_prepared_by") or user.get("name") or user["email"]).strip()[:120]
    approved = cfg.get("evidence_approved_by", "")
    approved_at = cfg.get("evidence_approved_at", "")
    emails = cfg.get("evidence_recipients") or [r["email"] for r in await db.users.find(
        {"org_id": org_id, "role": {"$in": ["admin", "executive"]}}, {"_id": 0, "email": 1}).to_list(200)] or [user["email"]]
    scopes = {s["email"].lower(): s for s in (cfg.get("auditor_scopes") or [])}
    sent = 0
    detail = []
    for e in emails:
        sc = scopes.get(e.lower())
        rws = _scope_rows(rows, sc.get("areas"), sc.get("systems")) if sc else rows
        smy = _summarize(rws)
        att = _sod_evidence_attachment(rws, smy, prepared, approved, approved_at)
        html = _sod_evidence_html(smy)
        if await notifications.send_email(e, "SAP SoD Evidence Pack — Obserra UAC", html, attachments=att):
            sent += 1
        detail.append({"email": e, "conflicts": smy["total"], "scoped": bool(sc)})
    await _audit(org_id, user["email"], "sap.sod.evidence.send",
                 f"evidence pack emailed to {len(emails)}, {sent} sent, prepared_by={prepared}, approved_by={approved or 'pending'}")
    return {"ok": True, "sent": sent, "recipients": emails, "conflicts": summary["total"],
            "prepared_by": prepared, "approved_by": approved, "detail": detail, "summary": summary}


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
            prepared = cfg.get("evidence_prepared_by", "")
            approved = cfg.get("evidence_approved_by", "")
            approved_at = cfg.get("evidence_approved_at", "")
            emails = cfg.get("evidence_recipients") or [r["email"] for r in await db.users.find(
                {"org_id": org_id, "role": {"$in": ["admin", "executive"]}}, {"_id": 0, "email": 1}).to_list(200)]
            scopes = {s["email"].lower(): s for s in (cfg.get("auditor_scopes") or [])}
            for e in emails:
                sc = scopes.get(e.lower())
                rws = _scope_rows(rows, sc.get("areas"), sc.get("systems")) if sc else rows
                smy = _summarize(rws)
                att = _sod_evidence_attachment(rws, smy, prepared, approved, approved_at)
                html = _sod_evidence_html(smy)
                await notifications.send_email(e, "Weekly SAP SoD Evidence Pack — Obserra UAC", html, attachments=att)
            await notifications.create(
                org_id, "report", "Weekly SoD evidence pack delivered",
                f"{summary['total']} conflict(s) ({summary['open']} open) documented — PDF emailed to {len(emails)} recipient(s).",
                ref="sap-sod-evidence", dedupe_key=f"sap-sod-evidence:{now.date().isoformat()}")
        except Exception:
            pass
