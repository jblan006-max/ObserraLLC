"""Insights — tenant white-label branding + peer benchmarking."""
from bson import ObjectId
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from auth import get_current_user, require_roles, _log_audit
from db import db

insights_router = APIRouter(prefix="/api")

DEFAULT_BRANDING = {"display_name": "Obserra — Executive Protection & Intelligence LLC",
                    "accent": "#12b4d6", "logo_url": "/logo.png"}


class Branding(BaseModel):
    display_name: str
    accent: str
    logo_url: str = "/logo.png"


@insights_router.get("/branding")
async def get_branding(user: dict = Depends(get_current_user)):
    org = await db.organizations.find_one({"_id": ObjectId(user["org_id"])}) or {}
    return {**DEFAULT_BRANDING, **(org.get("branding") or {})}


@insights_router.put("/branding")
async def put_branding(body: Branding, admin: dict = Depends(require_roles("admin"))):
    await db.organizations.update_one({"_id": ObjectId(admin["org_id"])}, {"$set": {"branding": body.model_dump()}})
    await _log_audit(admin["org_id"], admin["email"], "branding.update", body.display_name)
    return body.model_dump()


@insights_router.get("/benchmark")
async def benchmark(user: dict = Depends(get_current_user)):
    org_id = user["org_id"]
    controls = await db.controls.find({"org_id": org_id}, {"_id": 0}).to_list(500)
    agents = await db.ai_agents.find({"org_id": org_id}, {"_id": 0}).to_list(500)
    eff = round(sum(c.get("effectiveness", 0) for c in controls) / len(controls)) if controls else 0
    fresh = round(sum(1 for c in controls if c.get("effectiveness", 0) >= 55) / len(controls) * 100) if controls else 0
    ai_cov = round(sum(1 for a in agents if a.get("status") == "sanctioned") / len(agents) * 100) if agents else 0

    def pct(you, med):
        return min(99, max(1, round(50 + (you - med) * 0.8)))

    metrics = [
        {"name": "Control Effectiveness", "you": eff, "peer_median": 68, "top_quartile": 84, "percentile": pct(eff, 68)},
        {"name": "Evidence Freshness", "you": fresh, "peer_median": 72, "top_quartile": 90, "percentile": pct(fresh, 72)},
        {"name": "AI Governance Coverage", "you": ai_cov, "peer_median": 55, "top_quartile": 80, "percentile": pct(ai_cov, 55)},
    ]
    return {"industry": "Financial Services", "peer_set": 240, "metrics": metrics}
