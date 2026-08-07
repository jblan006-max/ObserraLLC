"""Cyber Risk — kernel-native app (control-centric cyber risk posture)."""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException

from auth import get_current_user, require_roles, _log_audit
from db import db
from bson import ObjectId
from kernel import notifications, workflows

cyber_router = APIRouter(prefix="/api/cyber")
COMPOSITION = ["Asset Model", "Risk Engine", "Control Engine", "Policy Engine",
               "Workflow Engine", "Notification Engine", "Obserrian AI"]


@cyber_router.get("/overview")
async def overview(user: dict = Depends(get_current_user)):
    risks = await db.risks.find({"org_id": user["org_id"]}, {"_id": 0}).to_list(500)
    controls = await db.controls.find({"org_id": user["org_id"]}, {"_id": 0}).to_list(500)
    if risks:
        avg_res = sum(min(r.get("residual", 0), 25) for r in risks) / len(risks)
        avg_inh = sum(min(r.get("inherent", 0), 25) for r in risks) / len(risks)
        posture = round(100 - avg_res / 25 * 100)
        mitigation = round((avg_inh - avg_res) / max(avg_inh, 1) * 100)
    else:
        posture, mitigation = 100, 0
    coverage = round(sum(c.get("effectiveness", 0) for c in controls) / len(controls)) if controls else 0
    open_risks = sum(1 for r in risks if r.get("status") == "Open")
    top = sorted(risks, key=lambda r: r.get("residual", 0), reverse=True)[:5]
    org = await db.organizations.find_one({"_id": ObjectId(user["org_id"])}) or {}
    m365 = org.get("live_m365") or {}
    live_users = m365.get("user_count") if m365.get("live") else None
    live_risky = m365.get("risky_users") if m365.get("live") else None
    return {"composition": COMPOSITION, "posture_score": posture, "mitigation_pct": mitigation,
            "control_coverage": coverage, "open_risks": open_risks, "total_risks": len(risks),
            "live_m365_users": live_users, "live_m365_risky": live_risky, "risks": top}


@cyber_router.post("/risks/{ref}/treat")
async def treat_risk(ref: str, admin: dict = Depends(require_roles("admin"))):
    r = await db.risks.find_one({"org_id": admin["org_id"], "ref": ref})
    if not r:
        raise HTTPException(404, "Risk not found")
    await workflows.start_remediation(admin["org_id"], ref, f"Treat cyber risk — {r['title']} ({ref})")
    await notifications.create(
        admin["org_id"], "cyber_risk", f"Treatment started for {ref}",
        f"{r['title']} — residual {r.get('residual')}/25, owner {r.get('owner')}.",
        ref=ref, dedupe_key=f"cyber:{ref}:{r.get('residual')}")
    await _log_audit(admin["org_id"], admin["email"], "cyber.treat", f"Opened treatment for {ref}")
    return {"ok": True, "ref": ref}
