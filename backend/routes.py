from datetime import datetime, timezone
from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from db import db
from auth import get_current_user

api = APIRouter(prefix="/api")


async def _audit(org_id, actor, action, detail=""):
    await db.audit_logs.insert_one({
        "org_id": org_id, "actor": actor, "action": action, "detail": detail,
        "ts": datetime.now(timezone.utc).isoformat()})


@api.get("/")
async def root():
    return {"service": "Obserra EIOS", "status": "ok"}


@api.get("/overview")
async def overview(user: dict = Depends(get_current_user)):
    org_id = user["org_id"]
    org = await db.organizations.find_one({"_id": ObjectId(org_id)})
    health = await db.health_index.find_one({"org_id": org_id}, {"_id": 0})
    risks = await db.risks.find({"org_id": org_id}, {"_id": 0}).to_list(200)
    ai_systems = await db.ai_systems.find({"org_id": org_id}, {"_id": 0}).to_list(200)
    incidents = await db.ai_incidents.find({"org_id": org_id}, {"_id": 0}).to_list(200)
    recs = await db.recommendations.find({"org_id": org_id}, {"_id": 0}).to_list(200)
    connector = await db.connectors.find_one({"org_id": org_id}, {"_id": 0})
    open_risks = [r for r in risks if r["status"] != "Remediated"]
    top_risks = sorted(risks, key=lambda r: r["residual"], reverse=True)[:5]
    return {
        "org": {"name": org["name"], "plan": org.get("plan"), "entitlements": org.get("entitlements", [])},
        "health": health,
        "kpis": {
            "total_risks": len(risks), "open_risks": len(open_risks),
            "critical_risks": len([r for r in risks if r["residual"] >= 16]),
            "ai_systems": len(ai_systems), "shadow_ai": len([a for a in ai_systems if a["status"] == "shadow"]),
            "open_incidents": len([i for i in incidents if i["status"] != "Resolved"]),
            "pending_recs": len([r for r in recs if r["status"] == "Pending"]),
        },
        "top_risks": top_risks,
        "recommendations": recs,
        "connector": connector,
    }


@api.get("/risks")
async def list_risks(user: dict = Depends(get_current_user)):
    return await db.risks.find({"org_id": user["org_id"]}, {"_id": 0}).sort("residual", -1).to_list(500)


class RiskUpdate(BaseModel):
    status: str | None = None
    treatment: str | None = None
    residual: int | None = None
    owner: str | None = None


@api.patch("/risks/{ref}")
async def update_risk(ref: str, body: RiskUpdate, user: dict = Depends(get_current_user)):
    changes = {k: v for k, v in body.model_dump().items() if v is not None}
    if not changes:
        raise HTTPException(400, "No changes")
    changes["updated_at"] = datetime.now(timezone.utc).isoformat()
    res = await db.risks.update_one({"org_id": user["org_id"], "ref": ref}, {"$set": changes})
    if res.matched_count == 0:
        raise HTTPException(404, "Risk not found")
    await _audit(user["org_id"], user["email"], "risk.update", f"{ref}: {changes}")
    return await db.risks.find_one({"org_id": user["org_id"], "ref": ref}, {"_id": 0})


@api.get("/ai-systems")
async def list_ai_systems(user: dict = Depends(get_current_user)):
    return await db.ai_systems.find({"org_id": user["org_id"]}, {"_id": 0}).to_list(500)


class AISystemUpdate(BaseModel):
    status: str | None = None
    risk_class: str | None = None


@api.patch("/ai-systems/{ref}")
async def update_ai_system(ref: str, body: AISystemUpdate, user: dict = Depends(get_current_user)):
    changes = {k: v for k, v in body.model_dump().items() if v is not None}
    if not changes:
        raise HTTPException(400, "No changes")
    res = await db.ai_systems.update_one({"org_id": user["org_id"], "ref": ref}, {"$set": changes})
    if res.matched_count == 0:
        raise HTTPException(404, "Not found")
    await _audit(user["org_id"], user["email"], "ai_system.update", f"{ref}: {changes}")
    return await db.ai_systems.find_one({"org_id": user["org_id"], "ref": ref}, {"_id": 0})


@api.get("/ai-incidents")
async def list_incidents(user: dict = Depends(get_current_user)):
    return await db.ai_incidents.find({"org_id": user["org_id"]}, {"_id": 0}).sort("opened", -1).to_list(500)


@api.get("/recommendations")
async def list_recs(user: dict = Depends(get_current_user)):
    return await db.recommendations.find({"org_id": user["org_id"]}, {"_id": 0}).to_list(500)


class DecisionCreate(BaseModel):
    rec_ref: str
    chosen: str
    rationale: str


@api.post("/recommendations/{ref}/decide")
async def decide_rec(ref: str, body: DecisionCreate, user: dict = Depends(get_current_user)):
    rec = await db.recommendations.find_one({"org_id": user["org_id"], "ref": ref})
    if not rec:
        raise HTTPException(404, "Recommendation not found")
    await db.recommendations.update_one({"org_id": user["org_id"], "ref": ref},
                                        {"$set": {"status": "Decided"}})
    dref = f"DEC-{str(await db.decisions.count_documents({'org_id': user['org_id']}) + 1).zfill(3)}"
    decision = {
        "ref": dref, "org_id": user["org_id"], "title": rec["title"],
        "options": [rec["title"], "Defer", "Accept risk"], "chosen": body.chosen,
        "rationale": body.rationale, "approver": user["name"], "status": "Approved",
        "outcome": "Pending execution", "linked_rec": ref,
        "decided_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.decisions.insert_one(decision)
    await _audit(user["org_id"], user["email"], "decision.create", f"{dref} from {ref}")
    decision.pop("_id", None)
    return decision


@api.get("/decisions")
async def list_decisions(user: dict = Depends(get_current_user)):
    return await db.decisions.find({"org_id": user["org_id"]}, {"_id": 0}).sort("decided_at", -1).to_list(500)


@api.get("/audit-logs")
async def list_audit(user: dict = Depends(get_current_user)):
    return await db.audit_logs.find({"org_id": user["org_id"]}, {"_id": 0}).sort("ts", -1).to_list(200)


@api.get("/evidence-lineage/{risk_ref}")
async def evidence_lineage(risk_ref: str, user: dict = Depends(get_current_user)):
    risk = await db.risks.find_one({"org_id": user["org_id"], "ref": risk_ref}, {"_id": 0})
    if not risk:
        raise HTTPException(404, "Risk not found")
    rec = await db.recommendations.find_one({"org_id": user["org_id"], "risk_ref": risk_ref}, {"_id": 0})
    decision = None
    if rec:
        decision = await db.decisions.find_one({"org_id": user["org_id"], "linked_rec": rec["ref"]}, {"_id": 0})
    chain = [
        {"stage": "source", "label": risk["source"], "detail": f"Freshness: {risk['freshness']}", "type": "fact"},
        {"stage": "observation", "label": risk["title"], "detail": risk.get("kri", ""), "type": risk["data_type"]},
    ]
    if rec:
        chain.append({"stage": "recommendation", "label": rec["title"],
                      "detail": rec["predicted_impact"], "type": "ai_recommendation"})
    if decision:
        chain.append({"stage": "decision", "label": decision["chosen"],
                      "detail": decision["rationale"], "type": "fact"})
        chain.append({"stage": "action", "label": decision.get("outcome", "In progress"),
                      "detail": f"Approver: {decision['approver']}", "type": "fact"})
        chain.append({"stage": "outcome", "label": decision.get("outcome", "Pending"),
                      "detail": "Tracked to residual score", "type": "estimate"})
    return {"risk_ref": risk_ref, "chain": chain}
