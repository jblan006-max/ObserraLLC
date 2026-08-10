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
BRAND = "Obserra Agentic AI Security"
TAGLINE = "Agentic AI Security Control & Governance — discover, understand, govern, constrain & respond to enterprise AI agents"

E, A = "exec", "admin"      # audience tags
ALL = (E, A)

# (heading, [paragraphs], screenshot_or_None, audiences)
SECTIONS = [
    ("About Obserra Agentic AI Security", [
        "Obserra Agentic AI Security Control & Governance lets you discover, understand, govern, "
        "constrain and respond to the AI agents and models operating across your enterprise — before "
        "delegated machine authority becomes enterprise risk. It gives security, GRC and executive "
        "teams a single live view of which agents exist, what tools and permissions they hold, how "
        "much autonomy they have, and where their capabilities combine into dangerous — 'toxic' — patterns.",
        "Every number is computed LIVE from the underlying agent records on each request (No-Mock): "
        "delegated authority tiers, modelled agent risk scores, guardrail coverage and the heuristic "
        "red-team baseline are all derived from real telemetry. Governance actions (sanction, "
        "restrict, suspend, kill) are written to the Defensibility Ledger so every decision is "
        "audit-defensible, and the runtime enforcement connector can push those decisions to an "
        "external agent runtime.",
    ], None, ALL),

    ("Installing the App (One-Click PWA)", [
        "Obserra installs like a native app straight from the browser — no app store required — "
        "and works across desktop, tablet and mobile.",
        "Desktop (Chrome / Edge): click the Install icon in the address bar, or use the in-app "
        "'Install' banner. Android (Chrome): tap the 'Install' banner or menu -> Add to Home "
        "screen. iPhone / iPad (Safari): tap Share -> Add to Home Screen.",
        "Once installed, the app launches full-screen and can receive push notifications for AI "
        "security alerts, shadow-AI discoveries and guardrail breaches.",
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
        "admins get full enforcement controls, executives get the board view.",
    ], "01_login.jpg", ALL),

    ("Going Live — Production Setup Checklist", [
        "Follow these steps to take Obserra from first sign-in to a fully live, audit-defensible "
        "deployment. Progress is tracked automatically by the Go-Live Readiness checklist on the "
        "Connector Health page — every check runs against real state, so the score reflects your "
        "actual production readiness (No-Mock).",
        "1) Connect your sources. Open Connector Health (Sources) and connect your identity, agent "
        "and security feeds, then use 'Re-probe all connectors' so every source reads healthy and "
        "fresh. Enterprise connectors that need customer OAuth credentials are shown honestly as "
        "'credentials required' until you supply them.",
        "2) Run the Go-Live Readiness checklist. It evaluates eight live checks: database "
        "connectivity, source-connector ingestion, data freshness, identity inventory, the "
        "correlation & risk engine, the AI advisor engine, the evidence integrity seal and the "
        "agent-runtime enforcement webhook. Each item shows Ready / Attention / Blocker with a live "
        "detail line, and the card auto-refreshes every 30 seconds.",
        "3) Wire the agent-runtime enforcement webhook. Click 'Fix' on the runtime item (or go to "
        "Settings -> Agent runtime connector) and register your signed HTTPS endpoint. Once saved, "
        "Kill / Suspend / Resume actions are dispatched (HMAC-SHA256 signed) to your external agent "
        "runtime and the checklist reaches 100% — 'Production ready'.",
        "4) Confirm readiness everywhere. A green 'Production ready' badge with a trend sparkline "
        "appears on the Executive Overview, and the readiness score is recorded automatically every "
        "day (no login required) so leadership can watch the trend climb toward 100%.",
        "5) Export the proof. Download the signed Evidence Pack — every page-one cover carries a "
        "SHA-256 'Verified by Obserra' integrity seal — and share it with auditors or fold the "
        "score into the emailed board digest.",
    ], None, ALL),

    ("Executive Overview", [
        "The landing dashboard is the complete rollup of the AI security estate: modelled agent "
        "risk, autonomous agents, toxic capability combinations, shadow-AI exposure, guardrail "
        "gaps and open AI incidents — all as one board-ready view. Every KPI and card opens a "
        "standardized deep-dive with an AI strategic brief and recommended actions, and admins can "
        "email the executive brief on demand or on a cadence from here.",
    ], "02_exec_overview.jpg", ALL),

    ("Agentic AI Security Control & Governance", [
        "The dedicated seven-tab workspace: Mission Control, Agent Inventory, Authority & Tools "
        "(with the Tool Toxicity Map), Guardrails & Red Team, Shadow AI, Incidents and "
        "Defensibility. Mission Control summarises the estate; every tile is clickable and drills "
        "into the relevant tab or agent.",
    ], None, ALL),

    ("Agent Inventory", [
        "Every registered AI agent with its owner, model, delegated tools and permissions, "
        "modelled risk score, authority tier, guardrail coverage and governance status. Search and "
        "filter by status or risk class; open any agent for full evidence and AI analysis.",
    ], None, (A,)),

    ("Tool Toxicity Map", [
        "A visual Agent -> Tool -> Permission -> Resource graph that flags toxic capability "
        "combinations — for example an action-capable tool such as shell.exec paired with write "
        "permissions and no human-in-the-loop guardrail, or a data-exfiltration-capable tool with "
        "access to sensitive resources. The heatmap makes the most dangerous agents glanceable so "
        "reviewers can neutralise them first.",
    ], None, ALL),

    ("Guardrails & Red Team", [
        "Enterprise guardrail coverage (input/output filtering, tool allowlist, human approval) "
        "across every agent, plus the heuristic red-team baseline. Admins can toggle a guardrail "
        "on an agent's governance record and run the deterministic red-team probes; results are "
        "explicitly labelled as a heuristic baseline, not live adversarial runtime testing.",
    ], None, (A,)),

    ("Shadow AI Discovery", [
        "A discovery feed that auto-populates the review queue with unsanctioned AI systems "
        "detected across the estate — common public GenAI SaaS as well as agents flagged shadow. "
        "Admins run discovery in one click and sanction each system to bring it under governance.",
    ], None, (A,)),

    ("Kill Switch & Runtime Enforcement", [
        "From any agent's detail view, admins can Suspend (restrict), Kill (block) or Resume an "
        "agent. The runtime enforcement connector flips the agent's governance status, records the "
        "action to the Defensibility Ledger, posts a Slack/Teams alert, and — when an agent-runtime "
        "webhook is configured — dispatches the enforcement command to the external execution "
        "environment. The UI honestly reflects whether enforcement was applied in the control plane "
        "only or pushed to an external runtime.",
    ], None, (A,)),

    ("AI Incidents & Workflows", [
        "AI security incident records (severity, mode, status) from the governance backend, "
        "alongside the related governance workflows. Each incident opens a deep-dive with an AI "
        "brief and recommended actions.",
    ], None, (A,)),

    ("Defensibility & Evidence", [
        "The evidence layer: live data-source status, an explicit separation of FACT vs MODELLED "
        "vs HEURISTIC BASELINE vs AI RECOMMENDATION, the runtime-enforcement boundary statement and "
        "connector health. This is what makes the whole plane audit-defensible.",
    ], None, ALL),

    ("Board Brief Scheduler", [
        "A one-click control (admin) that emails the AI Security Executive Brief — modelled agent "
        "risk, autonomous agents, toxic combinations, shadow AI and open incidents — via the "
        "managed email pipeline. Choose a weekly or monthly cadence, or send it immediately.",
    ], None, (A,)),

    ("Settings, Branding & Deployment", [
        "Personal preferences (digest cadence, replay the guided tour) plus admin controls: "
        "alert recipients, custom branding (company name, logo, accent colour), a 'send me a test "
        "now' button, and the Deployment & Documentation downloads (on-premise package and these "
        "guides in PDF and Word).",
    ], "14_settings.jpg", (A,)),

    ("Obserrian Advisor", [
        "The floating Obserrian Advisor (bottom-right, and via the top-bar ask box) answers AI "
        "security questions grounded on your LIVE agent telemetry — delegated tools, permissions, "
        "guardrail coverage, tool-governance violations and the red-team baseline. It can execute "
        "recommended actions and, for admins, reports its own usage and spend.",
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
