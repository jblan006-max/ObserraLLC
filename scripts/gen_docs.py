#!/usr/bin/env python3
"""Generate the Obserra Install & User Guide as both PDF and Word (.docx).

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

# (heading, level, [paragraphs], screenshot_filename_or_None)
SECTIONS = [
    ("Obserra EIOS — Install & User Guide", 0, [
        "Executive Protection & Intelligence LLC",
        "A continuous AI control plane for enterprise cyber risk, AI governance and "
        "board-ready executive intelligence. This guide covers installation (cloud, "
        "mobile and on-premise) and a full walkthrough of every dashboard.",
    ], None),

    ("1. About Obserra", 1, [
        "Obserra presents one evidence-grounded platform at two altitudes: an Executive "
        "view (financial exposure, risk reduction, decisions required) and an Operational "
        "view (AI usage, patching, incidents and remediation). Every metric carries its "
        "source, freshness and confidence.",
        "The platform is delivered as an installable Progressive Web App (PWA) and can also "
        "be self-hosted on-premise with Docker.",
    ], None),

    ("2. Installing the App (One-Click PWA)", 1, [
        "Obserra installs like a native app straight from the browser — no app store required. "
        "It works across desktop, tablet and mobile.",
        "Desktop (Chrome / Edge): open the site and click the Install icon in the address bar, "
        "or use the in-app 'Install Obserra' banner.",
        "Android (Chrome): tap the 'Install Obserra' banner, or use menu -> Add to Home screen.",
        "iPhone / iPad (Safari): tap Share -> Add to Home Screen.",
        "Once installed, Obserra launches full-screen and can receive push notifications.",
    ], None),

    ("3. On-Premise Installation (Docker)", 1, [
        "For fully self-hosted deployments, download the on-premise package from "
        "Settings -> Deployment & Documentation. No install script is required; an optional "
        "install.sh is included for convenience.",
        "Prerequisites: Docker 24+ and Docker Compose v2, 2 vCPU / 4 GB RAM (8 GB recommended).",
        "Steps: (1) place the backend/ and frontend/ source next to the deploy/ folder; "
        "(2) copy .env.example to .env and set JWT_SECRET, EMERGENT_LLM_KEY and PUBLIC_URL; "
        "(3) run: docker compose -f deploy/docker-compose.yml --env-file deploy/.env up -d --build; "
        "(4) open http://<machine-ip>:8080.",
        "MongoDB data persists in a Docker volume across restarts. For production, terminate "
        "TLS with a reverse proxy in front of port 8080. Full details are in the bundled INSTALL.md.",
    ], None),

    ("4. Signing In", 1, [
        "Open the app and sign in with your work email and password. Enterprise SSO, Apple "
        "and Google sign-in, and passwordless QR login are also available. Passwords follow "
        "NIST 800-63B (>=12 chars with upper/lower/number/symbol).",
    ], "01_login.jpg"),

    ("5. Executive Overview", 1, [
        "The Executive view opens on strategic, board-ready intelligence: the Posture Trend, "
        "the Enterprise Health Index, Top Risks by Business Impact and Decisions Required. "
        "Use 'Generate Board Report' to produce a branded PDF at any time.",
    ], "02_exec_overview.jpg"),

    ("6. Operational Command", 1, [
        "Toggle to Operational mode (top-right) for the working view: NIST control maturity, "
        "third-party vendor risk, phishing click-rate, patching coverage, the risk heatmap and "
        "remediation workflows.",
    ], "03_operational_overview.jpg"),

    ("7. Risk Register", 1, [
        "The Risk Register lists every tracked risk with inherent vs residual scoring, financial "
        "exposure (FAIR-style annualized loss expectancy) and evidence links for board defensibility.",
    ], "04_risk_register.jpg"),

    ("7b. Risk (FAIR) Quantification", 1, [
        "The Risk workspace quantifies exposure using Factor Analysis of Information Risk (FAIR). "
        "It surfaces board KPIs — $ at Risk (residual ALE), worst-case P90, remediation ROI and "
        "accepted (unremediated) exposure — plus a per-area exposure breakdown showing the dominant "
        "driver of each risk (loss magnitude, threat frequency or control weakness), a loss-exceedance "
        "curve, and plain-English FAIR-based deductions. Auto-updating IBM/DBIR benchmark feeds carry "
        "last-pull timestamps and sources, and a 'Why these KPIs' panel cites Gartner, NACD, the FAIR "
        "Institute and the WEF so every board metric is defensible.",
    ], "04b_risk_fair.jpg"),

    ("8. AI Governance Suite", 1, [
        "Inventory of AI systems with NIST AI RMF mapping, model cards (bias, safety, security, "
        "explainability), drift and hallucination indicators, shadow-AI discovery and incident "
        "management. Bring shadow tools under governance in one click.",
    ], "05_ai_governance.jpg"),

    ("9. Control Monitoring", 1, [
        "Continuously monitor control health and drift. Open alerts can be summarized to you on a "
        "daily or weekly digest cadence (configurable in Settings).",
    ], "06_control_monitoring.jpg"),

    ("10. Compliance Posture", 1, [
        "Track compliance posture across frameworks with evidence freshness so every figure stays "
        "audit-ready.",
    ], "07_compliance.jpg"),

    ("11. Evidence & Reporting", 1, [
        "Generate board-ready packets tied to evidence. 'New Board Report' synthesizes a report and "
        "shows a live branded cover preview. Export as a vertical PDF or a landscape Quarterly Deck, "
        "toggle a light/dark cover theme, email it, or share to Microsoft Teams. A monthly job also "
        "emails the branded PDF to chosen recipients automatically.",
    ], "08_reporting.jpg"),

    ("12. Settings, Branding & Deployment", 1, [
        "Personal preferences (digest cadence, replay the guided tour) plus admin controls: board-report "
        "recipients, custom report branding (company name, logo, accent colour) with a live cover preview, "
        "a 'Send me a test now' button, and the Deployment & Documentation downloads (on-premise package, "
        "this guide in PDF and Word).",
    ], "09_settings.jpg"),

    ("13. Obserra Advisor", 1, [
        "The floating Advisor (bottom-right) answers board-level questions grounded on your live posture — "
        "financial exposure, top risks and the decisions that need sign-off. It can also execute recommended "
        "actions and, for admins, reports its own usage and spend.",
    ], None),

    ("14. Support", 1, [
        "For assistance contact your Obserra administrator. Risk scores and AI evaluations are decision-support "
        "estimates and do not constitute legal, financial, regulatory or security guarantees.",
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
                            title="Obserra EIOS — Install & User Guide", author="Obserra")
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
                                 "Obserra — Executive Protection & Intelligence LLC  ·  Confidential")
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
