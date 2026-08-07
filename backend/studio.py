"""Studio — custom dashboard builder + report builder (composed on kernel data)."""
from datetime import datetime, timezone

from bson import ObjectId
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from auth import get_current_user
from db import db

studio_router = APIRouter(prefix="/api/studio")


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


@studio_router.post("/report/compose")
async def compose_report(body: ReportBody, user: dict = Depends(get_current_user)):
    org_id = user["org_id"]
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
    blocks = [{"heading": builders[s][0], "lines": builders[s][1]} for s in body.sections if s in builders]
    return {"title": body.title, "generated_at": datetime.now(timezone.utc).isoformat(), "blocks": blocks}
