#!/usr/bin/env python3
"""Generate the Obserra SAP UAC guides as PDF and Word (.docx).

Produces three role-targeted guides from ONE set of sections + screenshots:
  - Install & User Guide  (full)      -> Obserra-Install-and-User-Guide.{pdf,docx}
  - Executive Guide       (short)     -> Obserra-SAP-UAC-Executive-Guide.{pdf,docx}
  - Admin & Operator Guide(deep)      -> Obserra-SAP-UAC-Admin-Operator-Guide.{pdf,docx}

Every guide opens with a branded cover (logo) + a numbered Contents page. Screenshots
are read from /app/scripts/shots and embedded.
"""
import os
from datetime import datetime

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHOTS = os.path.join(BASE, "scripts", "shots")
PUBLIC = os.path.join(BASE, "frontend", "public")
OUT = os.path.join(BASE, "backend", "assets", "docs")
os.makedirs(OUT, exist_ok=True)

NAVY = "#0f1e3d"
AI = "#12b4d6"
BRAND = "Obserra SAP UAC"
TAGLINE = "Enterprise SAP User Access Control & Access Intelligence"

E, A = "exec", "admin"      # audience tags
ALL = (E, A)

# (heading, [paragraphs], screenshot_or_None, audiences)
SECTIONS = [
    ("About Obserra SAP UAC", [
        "Obserra SAP UAC gives access, audit and GRC teams a single live view of who can do "
        "what across the SAP landscape — and the tooling to fix it. It reconciles HR against "
        "SAP accounts, detects Segregation-of-Duties (SoD) conflicts and privileged exposure in "
        "real time, and turns every finding into an actionable, auditable ServiceNow change.",
        "Every number is computed LIVE from the underlying records on each request (No-Mock): "
        "the shipped dataset is a realistic, fully sourced snapshot, and real SAP / ServiceNow "
        "connectors slot in later without changing the API contract. Every metric carries its "
        "source and freshness so findings are audit-defensible.",
    ], None, ALL),

    ("Installing the App (One-Click PWA)", [
        "Obserra SAP UAC installs like a native app straight from the browser — no app store "
        "required — and works across desktop, tablet and mobile.",
        "Desktop (Chrome / Edge): click the Install icon in the address bar, or use the in-app "
        "'Install' banner. Android (Chrome): tap the 'Install' banner or menu -> Add to Home "
        "screen. iPhone / iPad (Safari): tap Share -> Add to Home Screen.",
        "Once installed, the app launches full-screen and can receive push notifications for "
        "access alerts and SoD threshold breaches.",
    ], None, ALL),

    ("On-Premise Installation (Docker)", [
        "For fully self-hosted deployments, download the on-premise package from "
        "Settings -> Deployment & Documentation. An optional install.sh is included.",
        "Prerequisites: Docker 24+ and Docker Compose v2, 2 vCPU / 4 GB RAM (8 GB recommended).",
        "Steps: (1) place backend/ and frontend/ next to the deploy/ folder; (2) copy "
        ".env.example to .env and set JWT_SECRET, EMERGENT_LLM_KEY and PUBLIC_URL; (3) run "
        "docker compose -f deploy/docker-compose.yml --env-file deploy/.env up -d --build; "
        "(4) open http://<machine-ip>:8080. Full details are in the bundled INSTALL.md.",
    ], None, (A,)),

    ("Signing In", [
        "Open the app and sign in with your work email and password. Passwords follow "
        "NIST 800-63B (>=12 chars with upper/lower/number/symbol). Roles determine what you see: "
        "admins get full governance controls, executives get the board view.",
    ], "01_login.jpg", ALL),

    ("Executive Overview", [
        "The landing dashboard opens on board-ready SAP access posture: the auto-running AI "
        "Analyst headline, key KPIs (identities, accounts, open SoD, average risk, license "
        "usage), top exposures and the decisions that need attention. Switch altitude between "
        "Executive and Operational from the toggle in the top bar.",
    ], "02_exec_overview.jpg", ALL),

    ("SAP Analytics", [
        "A deep analytics workspace over the whole SAP estate: identities, accounts, SoD by "
        "business area, license utilisation and risk distribution, with drill-downs on every "
        "chart. Export any view as a branded PDF or CSV for auditors and steering committees.",
    ], "03_sap_analytics.jpg", ALL),

    ("SoD Command Center", [
        "The heart of the platform. An AI insight card summarises the live SoD picture, followed "
        "by severity KPIs, the Access Governance Scorecard (with an 8-week trend and 'why the "
        "score moved'), the SoD -> ServiceNow Auto-Remediation rule engine, the Governance Digest "
        "schedule (email + Slack/Teams + voice briefing + evidence pack), a pre-assignment risk "
        "simulator, the SoD rule library and the full detected-conflicts table with severity, "
        "area and status filters. Every row opens a detail view with an AI risk rating and "
        "concrete 'how to fix' steps.",
    ], "04_sod_command_center.jpg", ALL),

    ("Risk Watchlist, Owner Leaderboard & Board Pack", [
        "Pin the SoD business areas you own to the Risk Watchlist so their hot spots surface "
        "every login; flip the 'Assigned to me' lens, set a bell alert threshold, and open a "
        "one-tap ServiceNow remediation ticket. Click any ticket badge to view its full "
        "ServiceNow change timeline, which auto-refreshes while open.",
        "The Owner Accountability Leaderboard ranks who carries the most open Critical SoD across "
        "regions, flags unowned hot spots, lets admins assign an owner in place, and can 'nudge "
        "all owners' — emailing each owner their assigned hot spots on demand.",
        "The Board Pack card previews this month's executive access-governance pack with the "
        "analytics PDF attached; admins can send it immediately or schedule the monthly auto-send "
        "day and recipients inline.",
    ], "05_sod_watchlist_leaderboard.jpg", ALL),

    ("Privileged Access (PAM)", [
        "Track SAP privileged and emergency (firefighter) access: who holds elevated roles, how "
        "long, and whether usage is justified. Revoke privileged access, lock accounts or trigger "
        "recertification in one click, each stamped to the audit trail and a ServiceNow change.",
    ], "06_privileged_access.jpg", (A,)),

    ("Access Monitoring", [
        "Continuous monitoring of access signals — anomalous logons, dormant-but-entitled "
        "accounts, terminated identities with residual access and connector health — so drift is "
        "caught the moment it appears.",
    ], "07_access_monitoring.jpg", (A,)),

    ("Identities", [
        "The canonical identity register reconciled from HR: each person with their SAP accounts, "
        "roles, risk score and lifecycle state. Open any identity for the full access footprint, "
        "an AI risk rating and lifecycle actions (activate, suspend, resume, deactivate).",
    ], "08_identities.jpg", (A,)),

    ("Joiner / Mover / Leaver", [
        "Automate the identity lifecycle. Joiners are provisioned to role templates, movers are "
        "re-evaluated for SoD as they change departments, and leavers are deprovisioned with "
        "residual-access checks — every step orchestrated through ServiceNow.",
    ], "09_lifecycle.jpg", (A,)),

    ("HR Reconciliation", [
        "Reconcile SAP accounts against the HR source of truth to surface orphaned accounts, "
        "missing owners and identity mismatches, with one-tap remediation for each exception.",
    ], "10_hr_reconciliation.jpg", (A,)),

    ("Role Intelligence", [
        "Analyse the role model: composite vs single roles, over-provisioning, redundant "
        "assignments and role-level SoD risk — with recommendations to right-size access before "
        "it becomes an audit finding.",
    ], "11_role_intelligence.jpg", (A,)),

    ("Access Requests", [
        "A self-service access request and approval workflow with automatic pre-assignment SoD "
        "simulation, so risky combinations are flagged before they are ever granted.",
    ], "12_access_requests.jpg", (A,)),

    ("Certifications", [
        "Run periodic access certification (attestation) campaigns: reviewers confirm or revoke "
        "entitlements, with progress tracking and an auditable record of every decision.",
    ], "13_certifications.jpg", (A,)),

    ("Settings, Branding & Deployment", [
        "Personal preferences (digest cadence, replay the guided tour) plus admin controls: "
        "governance-digest and board-pack recipients, custom branding (company name, logo, accent "
        "colour), a 'send me a test now' button, and the Deployment & Documentation downloads "
        "(on-premise package and these guides in PDF and Word).",
    ], "14_settings.jpg", (A,)),

    ("Obserra Advisor", [
        "The floating Advisor (top bar) answers access-governance questions grounded on your live "
        "SAP posture — open SoD, privileged exposure and the remediations that need sign-off. It "
        "can execute recommended actions and, for admins, reports its own usage and spend.",
    ], None, ALL),

    ("Support", [
        "For assistance contact your Obserra administrator. Risk scores and AI evaluations are "
        "decision-support estimates and do not constitute legal, financial, regulatory or security "
        "guarantees.",
    ], None, ALL),
]


def _img_size(path):
    try:
        from PIL import Image
        with Image.open(path) as im:
            return im.size
    except Exception:
        return (890, 267)


def _logo_path():
    for name in ("brand-lockup.png", "brand-wordmark.png", "brand-mark.png"):
        p = os.path.join(PUBLIC, name)
        if os.path.exists(p):
            return p
    return None


def build_pdf(path, sections, guide_title):
    from reportlab.lib.pagesizes import LETTER
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.lib import colors
    from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Image as RLImage,
                                    HRFlowable, PageBreak)
    styles = getSampleStyleSheet()
    ctitle = ParagraphStyle("ctitle", parent=styles["Title"], fontSize=30, leading=34,
                            textColor=colors.HexColor(NAVY), alignment=1)
    cbrand = ParagraphStyle("cbrand", parent=styles["Title"], fontSize=13, leading=16,
                            textColor=colors.HexColor(AI), alignment=1, spaceAfter=2)
    csub = ParagraphStyle("csub", parent=styles["Normal"], fontSize=11.5, leading=15,
                          textColor=colors.HexColor(NAVY), alignment=1)
    cmeta = ParagraphStyle("cmeta", parent=styles["Normal"], fontSize=9, leading=13,
                           textColor=colors.grey, alignment=1)
    h1 = ParagraphStyle("h1", parent=styles["Heading1"], fontSize=15, leading=19,
                        textColor=colors.HexColor(AI), spaceBefore=16, spaceAfter=6)
    body = ParagraphStyle("body", parent=styles["BodyText"], fontSize=10.5, leading=15, spaceAfter=6)
    toc = ParagraphStyle("toc", parent=body, fontSize=11, leading=20, textColor=colors.HexColor(NAVY))
    cap = ParagraphStyle("cap", parent=body, fontSize=8, textColor=colors.grey)

    doc = SimpleDocTemplate(path, pagesize=LETTER, topMargin=0.85 * inch, bottomMargin=0.8 * inch,
                            title=f"{BRAND} — {guide_title}", author="Obserra")
    story = []
    # ---- Cover ----
    story.append(Spacer(1, 130))
    lp = _logo_path()
    if lp:
        iw, ih = _img_size(lp)
        w = 3.6 * inch
        img = RLImage(lp, width=w, height=w * ih / iw); img.hAlign = "CENTER"
        story += [img, Spacer(1, 34)]
    story += [Paragraph(BRAND, cbrand), Paragraph(guide_title, ctitle), Spacer(1, 12),
              Paragraph(TAGLINE, csub), Spacer(1, 26),
              HRFlowable(width="38%", color=colors.HexColor(AI), hAlign="CENTER"), Spacer(1, 16),
              Paragraph(datetime.now().strftime("%B %Y"), cmeta),
              Paragraph("Confidential — prepared for internal use.", cmeta), PageBreak()]
    # ---- Contents ----
    story += [Paragraph("Contents", h1), Spacer(1, 4)]
    for i, (head, _p, _s, _a) in enumerate(sections, 1):
        story.append(Paragraph(f"{i}.&nbsp;&nbsp;{head}", toc))
    story.append(PageBreak())
    # ---- Body ----
    for i, (head, paras, shot, _a) in enumerate(sections, 1):
        story.append(Paragraph(f"{i}. {head}", h1))
        for p in paras:
            story.append(Paragraph(p, body))
        if shot:
            fp = os.path.join(SHOTS, shot)
            if os.path.exists(fp):
                iw = 6.4 * inch
                img = RLImage(fp, width=iw, height=iw * 900.0 / 1440.0)
                story += [Spacer(1, 4), img, Paragraph(f"Figure: {head}", cap), Spacer(1, 6)]

    def footer(canvas, _doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 7); canvas.setFillColor(colors.grey)
        canvas.drawCentredString(LETTER[0] / 2, 0.5 * inch,
                                 f"{BRAND} — {guide_title}  ·  Executive Protection & Intelligence LLC  ·  Confidential")
        if _doc.page > 1:
            canvas.drawRightString(LETTER[0] - 0.7 * inch, 0.5 * inch, str(_doc.page))
        canvas.restoreState()

    doc.build(story, onFirstPage=footer, onLaterPages=footer)


def build_docx(path, sections, guide_title):
    from docx import Document
    from docx.shared import Inches, Pt, RGBColor
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    d = Document()
    # ---- Cover ----
    lp = _logo_path()
    if lp:
        p = d.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.add_run().add_picture(lp, width=Inches(3.6))
    b = d.add_paragraph(); b.alignment = WD_ALIGN_PARAGRAPH.CENTER
    rb = b.add_run(BRAND); rb.bold = True; rb.font.size = Pt(13); rb.font.color.rgb = RGBColor(0x12, 0xb4, 0xd6)
    t = d.add_heading(guide_title, level=0); t.alignment = WD_ALIGN_PARAGRAPH.CENTER
    sub = d.add_paragraph(TAGLINE); sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
    meta = d.add_paragraph(f"{datetime.now().strftime('%B %Y')}  ·  Confidential — prepared for internal use.")
    meta.alignment = WD_ALIGN_PARAGRAPH.CENTER
    for r in meta.runs:
        r.font.size = Pt(9); r.font.color.rgb = RGBColor(0x80, 0x80, 0x80)
    d.add_page_break()
    # ---- Contents ----
    d.add_heading("Contents", level=1)
    for i, (head, _p, _s, _a) in enumerate(sections, 1):
        d.add_paragraph(f"{i}.  {head}")
    d.add_page_break()
    # ---- Body ----
    for i, (head, paras, shot, _a) in enumerate(sections, 1):
        hd = d.add_heading(f"{i}. {head}", level=1)
        for run in hd.runs:
            run.font.color.rgb = RGBColor(0x0f, 0x1e, 0x3d)
        for p in paras:
            d.add_paragraph(p)
        if shot:
            fp = os.path.join(SHOTS, shot)
            if os.path.exists(fp):
                d.add_picture(fp, width=Inches(6.2))
                capp = d.add_paragraph(f"Figure: {head}"); capp.alignment = WD_ALIGN_PARAGRAPH.CENTER
                for r in capp.runs:
                    r.font.size = Pt(8); r.font.color.rgb = RGBColor(0x80, 0x80, 0x80)
    d.save(path)


def _build(sections, title, pdf_name, docx_name):
    pdf = os.path.join(OUT, pdf_name); docx = os.path.join(OUT, docx_name)
    build_pdf(pdf, sections, title)
    build_docx(docx, sections, title)
    return pdf, docx


def generate_all():
    """Regenerate all role guides. Keeps pdf/docx/pdf_size/docx_size = the full guide."""
    exec_secs = [s for s in SECTIONS if E in s[3]]
    full_pdf, full_docx = _build(SECTIONS, "Install & User Guide",
                                 "Obserra-Install-and-User-Guide.pdf", "Obserra-Install-and-User-Guide.docx")
    exec_pdf, exec_docx = _build(exec_secs, "Executive Guide",
                                 "Obserra-SAP-UAC-Executive-Guide.pdf", "Obserra-SAP-UAC-Executive-Guide.docx")
    admin_pdf, admin_docx = _build(SECTIONS, "Admin & Operator Guide",
                                   "Obserra-SAP-UAC-Admin-Operator-Guide.pdf", "Obserra-SAP-UAC-Admin-Operator-Guide.docx")
    return {"pdf": full_pdf, "docx": full_docx,
            "pdf_size": os.path.getsize(full_pdf), "docx_size": os.path.getsize(full_docx),
            "exec_pdf": exec_pdf, "exec_docx": exec_docx,
            "admin_pdf": admin_pdf, "admin_docx": admin_docx}


if __name__ == "__main__":
    r = generate_all()
    for k in ("pdf", "exec_pdf", "admin_pdf", "docx", "exec_docx", "admin_docx"):
        print(k, os.path.getsize(r[k]), r[k])
