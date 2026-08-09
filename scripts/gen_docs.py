#!/usr/bin/env python3
"""Generate the Obserra SAP UAC Install & User Guide as both PDF and Word (.docx).

Screenshots are read from /app/scripts/shots and embedded. Output is written to
/app/backend/assets/docs so the backend can serve them for download.
"""
import os

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHOTS = os.path.join(BASE, "scripts", "shots")
OUT = os.path.join(BASE, "backend", "assets", "docs")
os.makedirs(OUT, exist_ok=True)

NAVY = "#0f1e3d"
AI = "#12b4d6"

GUIDE_TITLE = "Obserra SAP UAC — Install & User Guide"

# (heading, level, [paragraphs], screenshot_filename_or_None)
SECTIONS = [
    (GUIDE_TITLE, 0, [
        "Executive Protection & Intelligence LLC",
        "Obserra SAP UAC is an enterprise SAP User Access Control and Access Intelligence "
        "platform. It unifies canonical HR identity, real-time Segregation-of-Duties (SoD), "
        "privileged access management (PAM) and ServiceNow-driven remediation into one "
        "evidence-grounded control plane. This guide covers installation (cloud, mobile and "
        "on-premise) and a full walkthrough of every dashboard.",
    ], None),

    ("1. About Obserra SAP UAC", 1, [
        "Obserra SAP UAC gives access, audit and GRC teams a single live view of who can do "
        "what across the SAP landscape — and the tooling to fix it. It reconciles HR against "
        "SAP accounts, detects SoD conflicts and privileged exposure in real time, and turns "
        "every finding into an actionable, auditable ServiceNow change.",
        "Every number is computed LIVE from the underlying records on each request (No-Mock): "
        "the shipped dataset is a realistic, fully sourced snapshot, and real SAP / ServiceNow "
        "connectors slot in later without changing the API contract. Every metric carries its "
        "source and freshness so findings are audit-defensible.",
        "The platform is delivered as an installable Progressive Web App (PWA) and can also be "
        "self-hosted on-premise with Docker.",
    ], None),

    ("2. Installing the App (One-Click PWA)", 1, [
        "Obserra SAP UAC installs like a native app straight from the browser — no app store "
        "required. It works across desktop, tablet and mobile.",
        "Desktop (Chrome / Edge): open the site and click the Install icon in the address bar, "
        "or use the in-app 'Install' banner.",
        "Android (Chrome): tap the 'Install' banner, or use menu -> Add to Home screen.",
        "iPhone / iPad (Safari): tap Share -> Add to Home Screen.",
        "Once installed, the app launches full-screen and can receive push notifications for "
        "access alerts and SoD threshold breaches.",
    ], None),

    ("3. On-Premise Installation (Docker)", 1, [
        "For fully self-hosted deployments, download the on-premise package from "
        "Settings -> Deployment & Documentation. An optional install.sh is included for convenience.",
        "Prerequisites: Docker 24+ and Docker Compose v2, 2 vCPU / 4 GB RAM (8 GB recommended).",
        "Steps: (1) place the backend/ and frontend/ source next to the deploy/ folder; "
        "(2) copy .env.example to .env and set JWT_SECRET, EMERGENT_LLM_KEY and PUBLIC_URL; "
        "(3) run: docker compose -f deploy/docker-compose.yml --env-file deploy/.env up -d --build; "
        "(4) open http://<machine-ip>:8080.",
        "MongoDB data persists in a Docker volume across restarts. For production, terminate TLS "
        "with a reverse proxy in front of port 8080. Full details are in the bundled INSTALL.md.",
    ], None),

    ("4. Signing In", 1, [
        "Open the app and sign in with your work email and password. Passwords follow "
        "NIST 800-63B (>=12 chars with upper/lower/number/symbol). Roles determine what you see: "
        "admins get full governance controls, executives get the board view.",
    ], "01_login.jpg"),

    ("5. Executive Overview", 1, [
        "The landing dashboard opens on board-ready SAP access posture: the auto-running AI "
        "Analyst headline, key KPIs (identities, accounts, open SoD, average risk, license "
        "usage), top exposures and the decisions that need attention. Switch altitude between "
        "Executive and Operational from the toggle in the top bar.",
    ], "02_exec_overview.jpg"),

    ("6. SAP Analytics", 1, [
        "A deep analytics workspace over the whole SAP estate: identities, accounts, SoD by "
        "business area, license utilisation and risk distribution, with drill-downs on every "
        "chart. Export any view as a branded PDF or CSV for auditors and steering committees.",
    ], "03_sap_analytics.jpg"),

    ("7. SoD Command Center", 1, [
        "The heart of the platform. An AI insight card summarises the live SoD picture, followed "
        "by severity KPIs, the Access Governance Scorecard (with an 8-week trend and 'why the "
        "score moved'), the SoD -> ServiceNow Auto-Remediation rule engine, the Governance Digest "
        "schedule (email + Slack/Teams + voice briefing + evidence pack), a pre-assignment risk "
        "simulator, the SoD rule library and the full detected-conflicts table with severity, "
        "area and status filters. Every row opens a detail view with an AI risk rating and "
        "concrete 'how to fix' steps.",
    ], "04_sod_command_center.jpg"),

    ("8. Risk Watchlist, Owner Leaderboard & Board Pack", 1, [
        "Pin the SoD business areas you own to the Risk Watchlist so their hot spots surface "
        "every login; flip the 'Assigned to me' lens to see only your areas, set a bell alert "
        "threshold, and open a one-tap ServiceNow remediation ticket. Click any ticket badge to "
        "view its full ServiceNow change timeline, which auto-refreshes while open.",
        "The Owner Accountability Leaderboard ranks who carries the most open Critical SoD across "
        "regions, flags unowned hot spots, lets admins assign an owner in place, and can 'nudge "
        "all owners' — emailing each owner their assigned hot spots on demand.",
        "The Board Pack card previews this month's executive access-governance pack (posture "
        "summary, hottest areas, risk movers and 30-day remediation wins) with the analytics PDF "
        "attached; admins can send it immediately or schedule the monthly auto-send day and "
        "recipients inline.",
    ], "05_sod_watchlist_leaderboard.jpg"),

    ("9. Privileged Access (PAM)", 1, [
        "Track SAP privileged and emergency (firefighter) access: who holds elevated roles, how "
        "long, and whether usage is justified. Revoke privileged access, lock accounts or trigger "
        "recertification in one click, each stamped to the audit trail and a ServiceNow change.",
    ], "06_privileged_access.jpg"),

    ("10. Access Monitoring", 1, [
        "Continuous monitoring of access signals — anomalous logons, dormant-but-entitled "
        "accounts, terminated identities with residual access and connector health — so drift is "
        "caught the moment it appears.",
    ], "07_access_monitoring.jpg"),

    ("11. Identities", 1, [
        "The canonical identity register reconciled from HR: each person with their SAP accounts, "
        "roles, risk score and lifecycle state. Open any identity for the full access footprint, "
        "an AI risk rating and lifecycle actions (activate, suspend, resume, deactivate).",
    ], "08_identities.jpg"),

    ("12. Joiner / Mover / Leaver", 1, [
        "Automate the identity lifecycle. New joiners get provisioned to role templates, movers "
        "are re-evaluated for SoD as they change departments, and leavers are deprovisioned with "
        "residual-access checks — every step orchestrated through ServiceNow.",
    ], "09_lifecycle.jpg"),

    ("13. HR Reconciliation", 1, [
        "Reconcile SAP accounts against the HR source of truth to surface orphaned accounts, "
        "missing owners and identity mismatches, with one-tap remediation for each exception.",
    ], "10_hr_reconciliation.jpg"),

    ("14. Role Intelligence", 1, [
        "Analyse the role model: composite vs single roles, over-provisioning, redundant "
        "assignments and role-level SoD risk — with recommendations to right-size access before "
        "it becomes an audit finding.",
    ], "11_role_intelligence.jpg"),

    ("15. Access Requests", 1, [
        "A self-service access request and approval workflow with automatic pre-assignment SoD "
        "simulation, so risky combinations are flagged before they are ever granted.",
    ], "12_access_requests.jpg"),

    ("16. Certifications", 1, [
        "Run periodic access certification (attestation) campaigns: reviewers confirm or revoke "
        "entitlements, with progress tracking and an auditable record of every decision.",
    ], "13_certifications.jpg"),

    ("17. Settings, Branding & Deployment", 1, [
        "Personal preferences (digest cadence, replay the guided tour) plus admin controls: "
        "governance-digest and board-pack recipients, custom branding (company name, logo, accent "
        "colour), a 'send me a test now' button, and the Deployment & Documentation downloads "
        "(on-premise package and this guide in PDF and Word).",
    ], "14_settings.jpg"),

    ("18. Obserra Advisor", 1, [
        "The floating Advisor (top bar) answers access-governance questions grounded on your live "
        "SAP posture — open SoD, privileged exposure and the remediations that need sign-off. It "
        "can execute recommended actions and, for admins, reports its own usage and spend.",
    ], None),

    ("19. Support", 1, [
        "For assistance contact your Obserra administrator. Risk scores and AI evaluations are "
        "decision-support estimates and do not constitute legal, financial, regulatory or security "
        "guarantees.",
    ], None),
]


def build_pdf(path):
    from reportlab.lib.pagesizes import LETTER
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.lib import colors
    from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Image as RLImage,
                                    HRFlowable, PageBreak)
    styles = getSampleStyleSheet()
    h0 = ParagraphStyle("h0", parent=styles["Title"], fontSize=26, leading=30,
                        textColor=colors.HexColor(NAVY))
    h1 = ParagraphStyle("h1", parent=styles["Heading1"], fontSize=15, leading=19,
                        textColor=colors.HexColor(AI), spaceBefore=16, spaceAfter=6)
    body = ParagraphStyle("body", parent=styles["BodyText"], fontSize=10.5, leading=15, spaceAfter=6)
    cap = ParagraphStyle("cap", parent=body, fontSize=8, textColor=colors.grey)
    doc = SimpleDocTemplate(path, pagesize=LETTER, topMargin=0.85 * inch, bottomMargin=0.8 * inch,
                            title=GUIDE_TITLE, author="Obserra")
    story = []
    for i, (head, lvl, paras, shot) in enumerate(SECTIONS):
        if lvl == 0:
            story += [Spacer(1, 60), Paragraph(head, h0), Spacer(1, 8),
                      HRFlowable(width="60%", color=colors.HexColor(AI)), Spacer(1, 14)]
            for p in paras:
                story.append(Paragraph(p, body))
            story.append(PageBreak())
            continue
        story.append(Paragraph(head, h1))
        for p in paras:
            story.append(Paragraph(p, body))
        if shot:
            fp = os.path.join(SHOTS, shot)
            if os.path.exists(fp):
                iw = 6.4 * inch
                ih = iw * 900.0 / 1440.0
                img = RLImage(fp, width=iw, height=ih)
                story += [Spacer(1, 4), img, Paragraph(f"Figure: {head}", cap), Spacer(1, 6)]

    def footer(canvas, _doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 7); canvas.setFillColor(colors.grey)
        canvas.drawCentredString(LETTER[0] / 2, 0.5 * inch,
                                 "Obserra SAP UAC — Executive Protection & Intelligence LLC  ·  Confidential")
        canvas.restoreState()

    doc.build(story, onFirstPage=footer, onLaterPages=footer)


def build_docx(path):
    from docx import Document
    from docx.shared import Inches, Pt, RGBColor
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    d = Document()
    for head, lvl, paras, shot in SECTIONS:
        if lvl == 0:
            t = d.add_heading(head, level=0)
            t.alignment = WD_ALIGN_PARAGRAPH.CENTER
            for p in paras:
                para = d.add_paragraph(p)
                para.alignment = WD_ALIGN_PARAGRAPH.CENTER
            d.add_page_break()
            continue
        hd = d.add_heading(head, level=1)
        for run in hd.runs:
            run.font.color.rgb = RGBColor(0x0f, 0x1e, 0x3d)
        for p in paras:
            d.add_paragraph(p)
        if shot:
            fp = os.path.join(SHOTS, shot)
            if os.path.exists(fp):
                d.add_picture(fp, width=Inches(6.2))
                cap = d.add_paragraph(f"Figure: {head}")
                cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
                for r in cap.runs:
                    r.font.size = Pt(8); r.font.color.rgb = RGBColor(0x80, 0x80, 0x80)
    d.save(path)


def generate_all():
    """Regenerate both guides from the current screenshots. Returns paths + sizes."""
    pdf_path = os.path.join(OUT, "Obserra-Install-and-User-Guide.pdf")
    docx_path = os.path.join(OUT, "Obserra-Install-and-User-Guide.docx")
    build_pdf(pdf_path)
    build_docx(docx_path)
    return {"pdf": pdf_path, "docx": docx_path,
            "pdf_size": os.path.getsize(pdf_path), "docx_size": os.path.getsize(docx_path)}


if __name__ == "__main__":
    r = generate_all()
    print("PDF:", r["pdf"], os.path.getsize(r["pdf"]))
    print("DOCX:", r["docx"], os.path.getsize(r["docx"]))
