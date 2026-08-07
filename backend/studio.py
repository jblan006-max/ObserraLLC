"""Studio — custom dashboard builder + report builder (composed on kernel data)."""
import os
from datetime import datetime, timezone

from bson import ObjectId
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from emergentintegrations.llm.chat import LlmChat, UserMessage, TextDelta, StreamDone

from auth import get_current_user, require_roles
from db import db
from reports import _build_pdf, _report_html, EMAIL_BASE_URL
from fastapi.responses import StreamingResponse
from fastapi import HTTPException
import httpx

studio_router = APIRouter(prefix="/api/studio")


class ReportExportBody(BaseModel):
    title: str = "Custom Report"
    ai_narrative: str = ""
    blocks: list[dict] = []


def _report_markdown(body: ReportExportBody) -> str:
    md = []
    if body.ai_narrative:
        md += ["## Executive Narrative", body.ai_narrative, ""]
    for b in body.blocks:
        md.append(f"## {b.get('heading', '')}")
        for ln in b.get("lines", []):
            md.append(ln)
        md.append("")
    return "\n".join(md)


@studio_router.post("/report/pdf")
async def report_pdf(body: ReportExportBody, user: dict = Depends(get_current_user)):
    buf = _build_pdf(_report_markdown(body), body.title)
    fname = body.title.lower().replace(" ", "-")[:40] or "studio-report"
    return StreamingResponse(buf, media_type="application/pdf",
                             headers={"Content-Disposition": f'attachment; filename="{fname}.pdf"'})


@studio_router.post("/report/email")
async def report_email(body: ReportExportBody, admin: dict = Depends(require_roles("admin"))):
    board = await db.users.find({"org_id": admin["org_id"], "role": {"$in": ["admin", "executive"]}}, {"_id": 0, "email": 1}).to_list(100)
    recipients = sorted({u["email"] for u in board} | {admin["email"]})
    payload = {"to": recipients, "subject": f"{body.title} — Obserra EIOS Board Report",
               "html": _report_html(_report_markdown(body), body.title), "from_name": os.environ["EMAIL_FROM_NAME"]}
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(f"{EMAIL_BASE_URL}/api/v1/email/send",
                                     headers={"X-Email-Key": os.environ["EMERGENT_EMAIL_KEY"]}, json=payload)
        resp.raise_for_status()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to send email: {e}")
    return {"status": "sent", "to": recipients}


async def _ai_narrative(org_id: str, title: str, blocks: list[dict]) -> str:
    context = "\n".join(f"{b['heading']}:\n" + "\n".join(f"  - {ln}" for ln in b["lines"]) for b in blocks)
    chat = LlmChat(
        api_key=os.environ["EMERGENT_LLM_KEY"],
        session_id=f"studio-report-{org_id}",
        system_message="You are a chief risk officer writing a concise executive narrative for a custom risk & AI governance report. Ground every statement strictly in the provided report data. Cite refs in square brackets when present. Do not invent facts.",
    ).with_model("anthropic", "claude-opus-4-8")
    prompt = (f"REPORT TITLE: {title}\n\nREPORT DATA:\n{context}\n\n"
              "Write a single-paragraph executive narrative (<130 words) summarizing the posture, "
              "the most important risk signals, and one clear recommended action. Plain prose, no headings.")
    collected = []
    try:
        async for ev in chat.stream_message(UserMessage(text=prompt)):
            if isinstance(ev, TextDelta):
                collected.append(ev.content)
            elif isinstance(ev, StreamDone):
                break
    except Exception as e:
        collected.append(f"[narrative generation error: {e}]")
    return "".join(collected).strip()


async def _metrics(org_id):
    risks = await db.risks.find({"org_id": org_id}, {"_id": 0}).to_list(500)
    controls = await db.controls.find({"org_id": org_id}, {"_id": 0}).to_list(500)
    agents = await db.ai_agents.find({"org_id": org_id}, {"_id": 0}).to_list(500)
    vendors = await db.vendors.find({"org_id": org_id}, {"_id": 0}).to_list(500)
    open_rem = await db.workflows.count_documents({"org_id": org_id, "type": "remediation", "status": {"$ne": "resolved"}})
    unread = await db.notifications.count_documents({"org_id": org_id, "read": False})
    eff = round(sum(c.get("effectiveness", 0) for c in controls) / len(controls)) if controls else 0
    return {
        "open_risks": sum(1 for r in risks if r.get("status") == "Open"),
        "control_effectiveness": eff,
        "ai_sanctioned": round(sum(1 for a in agents if a.get("status") == "sanctioned") / len(agents) * 100) if agents else 0,
        "high_risk_vendors": sum(1 for v in vendors if v.get("risk_tier") in ("High", "Critical")),
        "open_remediations": open_rem,
        "unread_alerts": unread,
    }


WIDGETS = [
    {"id": "open_risks", "title": "Open Cyber Risks", "unit": ""},
    {"id": "control_effectiveness", "title": "Avg Control Effectiveness", "unit": "%"},
    {"id": "ai_sanctioned", "title": "AI Agents Sanctioned", "unit": "%"},
    {"id": "high_risk_vendors", "title": "High-Risk Vendors", "unit": ""},
    {"id": "open_remediations", "title": "Open Remediations", "unit": ""},
    {"id": "unread_alerts", "title": "Unread Alerts", "unit": ""},
]
DEFAULT_SELECTED = ["open_risks", "control_effectiveness", "ai_sanctioned", "open_remediations"]


@studio_router.get("/dashboard")
async def get_dashboard(user: dict = Depends(get_current_user)):
    m = await _metrics(user["org_id"])
    doc = await db.users.find_one({"_id": ObjectId(user["id"])})
    selected = doc.get("dashboard_widgets") or DEFAULT_SELECTED
    available = [{**w, "value": m.get(w["id"], 0)} for w in WIDGETS]
    return {"available": available, "selected": selected}


class DashboardBody(BaseModel):
    selected: list[str]


@studio_router.put("/dashboard")
async def put_dashboard(body: DashboardBody, user: dict = Depends(get_current_user)):
    await db.users.update_one({"_id": ObjectId(user["id"])}, {"$set": {"dashboard_widgets": body.selected}})
    return {"selected": body.selected}


REPORT_SECTIONS = [
    {"id": "exec_summary", "title": "Executive Summary"},
    {"id": "top_risks", "title": "Top Cyber Risks"},
    {"id": "ai_governance", "title": "AI Governance"},
    {"id": "vendor_risk", "title": "Third-Party Risk"},
    {"id": "controls", "title": "Control Posture"},
]


@studio_router.get("/report/sections")
async def report_sections(user: dict = Depends(get_current_user)):
    return REPORT_SECTIONS


class ReportBody(BaseModel):
    title: str = "Custom Report"
    sections: list[str]


async def _compose_report(org_id: str, title: str, sections: list[str]):
    m = await _metrics(org_id)
    risks = await db.risks.find({"org_id": org_id}, {"_id": 0}).to_list(500)
    vendors = await db.vendors.find({"org_id": org_id}, {"_id": 0}).to_list(500)
    top = sorted(risks, key=lambda r: r.get("residual", 0), reverse=True)[:3]
    hv = [v for v in vendors if v.get("risk_tier") in ("High", "Critical")]
    builders = {
        "exec_summary": ("Executive Summary", [
            f"Open cyber risks: {m['open_risks']}", f"Average control effectiveness: {m['control_effectiveness']}%",
            f"AI agents sanctioned: {m['ai_sanctioned']}%", f"High-risk vendors: {m['high_risk_vendors']}",
            f"Open remediations: {m['open_remediations']}"]),
        "top_risks": ("Top Cyber Risks", [f"[{r['ref']}] {r['title']} — residual {r.get('residual')}/25 ({r.get('status')})" for r in top] or ["No risks recorded."]),
        "ai_governance": ("AI Governance", [f"{m['ai_sanctioned']}% of AI agents sanctioned.", "Red-team & tool/permission governance active via AI Agent Governance app."]),
        "vendor_risk": ("Third-Party Risk", [f"[{v['ref']}] {v['name']} — {v['risk_tier']} ({v['risk_score']}/100)" for v in hv] or ["No high-risk vendors."]),
        "controls": ("Control Posture", [f"Average control effectiveness: {m['control_effectiveness']}%", f"Open remediations: {m['open_remediations']}"]),
    }
    blocks = [{"heading": builders[s][0], "lines": builders[s][1]} for s in sections if s in builders]
    narrative = await _ai_narrative(org_id, title, blocks) if blocks else ""
    return {"title": title, "generated_at": datetime.now(timezone.utc).isoformat(),
            "ai_narrative": narrative, "model": "claude-opus-4-8", "blocks": blocks}


@studio_router.post("/report/compose")
async def compose_report(body: ReportBody, user: dict = Depends(get_current_user)):
    return await _compose_report(user["org_id"], body.title, body.sections)


class ScheduleBody(BaseModel):
    enabled: bool = False
    title: str = "Monthly Board Report"
    sections: list[str] = []
    cadence: str = "monthly"


@studio_router.get("/schedule")
async def get_schedule(admin: dict = Depends(require_roles("admin"))):
    org = await db.organizations.find_one({"_id": ObjectId(admin["org_id"])})
    return (org or {}).get("studio_schedule") or {
        "enabled": False, "title": "Monthly Board Report", "cadence": "monthly",
        "sections": [s["id"] for s in REPORT_SECTIONS]}


@studio_router.put("/schedule")
async def put_schedule(body: ScheduleBody, admin: dict = Depends(require_roles("admin"))):
    sch = body.model_dump()
    await db.organizations.update_one({"_id": ObjectId(admin["org_id"])}, {"$set": {"studio_schedule": sch}})
    return sch
