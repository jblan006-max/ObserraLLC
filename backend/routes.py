import random
from datetime import datetime, timezone
from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from db import db
from auth import get_current_user, require_active_subscription

api = APIRouter(prefix="/api")


async def _audit(org_id, actor, action, detail=""):
    await db.audit_logs.insert_one({
        "org_id": org_id, "actor": actor, "action": action, "detail": detail,
        "ts": datetime.now(timezone.utc).isoformat()})


@api.get("/")
async def root():
    return {"service": "Obserra EIOS", "status": "ok"}


@api.get("/overview")
async def overview(user: dict = Depends(require_active_subscription)):
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
async def list_risks(user: dict = Depends(require_active_subscription)):
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
async def list_ai_systems(user: dict = Depends(require_active_subscription)):
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


class GovernBody(BaseModel):
    action: str


@api.post("/ai-systems/{ref}/govern")
async def govern_ai_system(ref: str, body: GovernBody, user: dict = Depends(get_current_user)):
    sys = await db.ai_systems.find_one({"org_id": user["org_id"], "ref": ref})
    if not sys:
        raise HTTPException(404, "Not found")
    mapping = {
        "kill": {"status": "killed", "mode": "block", "msg": f"Kill switch engaged for {sys['name']} — all traffic blocked."},
        "restrict": {"status": "restricted", "mode": "restrict", "msg": f"{sys['name']} restricted — human approval required per request."},
        "sanction": {"status": "sanctioned", "mode": "observe", "msg": f"{sys['name']} sanctioned and brought under governance."},
        "rollback": {"status": sys.get("status", "sanctioned"), "mode": "warn", "msg": f"{sys['name']} rolled back to previous approved model version."},
    }
    m = mapping.get(body.action)
    if not m:
        raise HTTPException(400, "Unknown governance action")
    await db.ai_systems.update_one({"org_id": user["org_id"], "ref": ref},
        {"$set": {"status": m["status"], "governance_mode": m["mode"]}})
    await _audit(user["org_id"], user["email"], "ai.govern", m["msg"])
    updated = await db.ai_systems.find_one({"org_id": user["org_id"], "ref": ref}, {"_id": 0})
    return {"message": m["msg"], "system": updated}


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


@api.get("/analytics")
async def analytics(user: dict = Depends(get_current_user)):
    org_id = user["org_id"]
    risks = await db.risks.find({"org_id": org_id}, {"_id": 0}).to_list(500)
    by_category, by_status, matrix = {}, {}, {}
    for r in risks:
        by_category[r["category"]] = by_category.get(r["category"], 0) + 1
        by_status[r["status"]] = by_status.get(r["status"], 0) + 1
        key = f"{r['likelihood']}-{r['impact']}"
        matrix.setdefault(key, []).append({"ref": r["ref"], "residual": r["residual"], "title": r["title"]})
    matrix_list = []
    for key, v in matrix.items():
        l, i = map(int, key.split("-"))
        top = max(v, key=lambda x: x["residual"])
        matrix_list.append({"likelihood": l, "impact": i, "count": len(v),
                            "refs": [x["ref"] for x in v], "top": top["ref"], "sev": l * i})
    kris = [{"ref": r["ref"], "title": r["title"], "kri": r.get("kri"),
             "residual": r["residual"], "owner": r["owner"], "trend": r.get("trend", "flat")}
            for r in risks if r.get("kri")]
    return {
        "by_category": [{"name": k, "value": v} for k, v in by_category.items()],
        "by_status": [{"name": k, "value": v} for k, v in by_status.items()],
        "matrix": matrix_list,
        "kris": sorted(kris, key=lambda x: x["residual"], reverse=True),
    }


@api.post("/connectors/sync")
async def sync_connector(user: dict = Depends(get_current_user)):
    org_id = user["org_id"]
    conn = await db.connectors.find_one({"org_id": org_id})
    if not conn:
        raise HTTPException(404, "No connector configured")
    added = random.randint(6, 84)
    new_total = conn.get("records_ingested", 0) + added
    now = datetime.now(timezone.utc).isoformat()
    await db.connectors.update_one({"org_id": org_id},
        {"$set": {"last_sync": now, "records_ingested": new_total, "freshness": "live"}})
    await _audit(org_id, user["email"], "connector.sync", f"{conn['name']} synced (+{added} records)")
    return await db.connectors.find_one({"org_id": org_id}, {"_id": 0})


# ---- Integrated remediation actions (Entra ID / Tenable / CASB) ----

def _integrations_catalog(conn):
    entra_records = conn.get("records_ingested", 0) if conn else 0
    entra_sync = conn.get("last_sync") if conn else None
    return [
        {"id": "entra", "name": "Microsoft Entra ID", "category": "Identity & Access", "icon": "identity",
         "status": "connected", "sync_mode": "MOCKED_LIVE", "records": entra_records, "last_sync": entra_sync,
         "actions": [
             {"id": "entra_enforce_pim", "label": "Enforce PIM", "risk": "CR-001", "authority": "CISO", "impact": "−4 residual · 37 roles"},
             {"id": "entra_enforce_mfa", "label": "Deploy MFA policy", "risk": "CR-005", "authority": "IT Security", "impact": "−3 residual · 112 users"},
             {"id": "entra_sync", "label": "Sync now", "risk": None, "authority": None, "impact": "Refresh directory"},
         ]},
        {"id": "tenable", "name": "Tenable Vuln Mgmt", "category": "Vulnerability Mgmt", "icon": "vuln",
         "status": "connected", "sync_mode": "MOCKED_LIVE", "records": 1893, "last_sync": conn.get("last_sync") if conn else None,
         "actions": [
             {"id": "tenable_patch_critical", "label": "Orchestrate patching", "risk": "CR-002", "authority": "Ops Lead", "impact": "−5 residual · 14 CVEs"},
         ]},
        {"id": "casb", "name": "Defender for Cloud Apps", "category": "AI Governance", "icon": "shadow",
         "status": "connected", "sync_mode": "MOCKED_LIVE", "records": 612, "last_sync": conn.get("last_sync") if conn else None,
         "actions": [
             {"id": "casb_quarantine_shadow", "label": "Quarantine shadow AI", "risk": "CR-004", "authority": "AI Gov Board", "impact": "−6 residual · 9 apps"},
         ]},
    ]


@api.get("/integrations")
async def integrations(user: dict = Depends(get_current_user)):
    conn = await db.connectors.find_one({"org_id": user["org_id"]}, {"_id": 0})
    return _integrations_catalog(conn)


_ACTION_EFFECTS = {
    "entra_enforce_pim": {"risk": "CR-001", "delta": 4, "status": "In Progress",
                          "msg": "Entra ID → Privileged Identity Management enforced on 37 standing roles. Just-in-time elevation now required."},
    "entra_enforce_mfa": {"risk": "CR-005", "delta": 3, "status": "Remediated",
                          "msg": "Entra ID → Conditional Access MFA policy applied to 112 remote users."},
    "tenable_patch_critical": {"risk": "CR-002", "delta": 5, "status": "In Progress",
                               "msg": "Tenable → Patch orchestration triggered for 14 critical CVEs on internet-facing assets."},
    "casb_quarantine_shadow": {"risk": "CR-004", "delta": 6, "status": "In Progress",
                               "msg": "Defender for Cloud Apps → 9 shadow-AI apps quarantined; PII egress blocked.",
                               "ai_system": "AI-003", "ai_status": "sanctioned"},
}

_CATEGORY_TO_COMPONENT = {
    "Identity & Access": "Identity & Access", "Vulnerability Mgmt": "Vulnerability Mgmt",
    "AI Governance": "AI Governance", "Third Party": "Third Party", "Resilience": "Resilience",
}


class ActionRun(BaseModel):
    action_id: str


@api.post("/actions/run")
async def run_action(body: ActionRun, user: dict = Depends(require_active_subscription)):
    org_id = user["org_id"]
    if body.action_id == "entra_sync":
        return await sync_connector(user)
    eff = _ACTION_EFFECTS.get(body.action_id)
    if not eff:
        raise HTTPException(404, "Unknown action")
    risk = await db.risks.find_one({"org_id": org_id, "ref": eff["risk"]})
    if not risk:
        raise HTTPException(404, "Target risk not found")
    new_res = max(3, risk["residual"] - eff["delta"])
    await db.risks.update_one({"org_id": org_id, "ref": eff["risk"]},
        {"$set": {"residual": new_res, "status": eff["status"], "trend": "down",
                  "updated_at": datetime.now(timezone.utc).isoformat()}})
    # nudge health index
    health = await db.health_index.find_one({"org_id": org_id})
    if health:
        comp_name = _CATEGORY_TO_COMPONENT.get(risk["category"])
        comps = health["components"]
        for c in comps:
            if c["name"] == comp_name:
                c["score"] = min(100, c["score"] + 3)
                c["trend"] = "up"
        new_score = min(100, health["score"] + 1)
        await db.health_index.update_one({"org_id": org_id},
            {"$set": {"components": comps, "score": new_score, "computed_at": datetime.now(timezone.utc).isoformat()}})
    if eff.get("ai_system"):
        await db.ai_systems.update_one({"org_id": org_id, "ref": eff["ai_system"]},
            {"$set": {"status": eff["ai_status"], "nist_profile": "GenAI Profile"}})
    await db.recommendations.update_one({"org_id": org_id, "risk_ref": eff["risk"]},
        {"$set": {"status": "Applied"}})
    await _audit(org_id, user["email"], "action.execute", eff["msg"])
    updated = await db.risks.find_one({"org_id": org_id, "ref": eff["risk"]}, {"_id": 0})
    return {"message": eff["msg"], "risk": updated, "action_id": body.action_id}


@api.get("/subscription")
async def subscription(user: dict = Depends(get_current_user)):
    from auth import subscription_active
    org = await db.organizations.find_one({"_id": ObjectId(user["org_id"])})
    return {"plan": org.get("plan"), "status": org.get("subscription_status"),
            "active": subscription_active(org), "trial_end": org.get("trial_end"),
            "current_period_end": org.get("current_period_end"),
            "billing_interval": org.get("billing_interval"),
            "entitlements": org.get("entitlements", []), "org_name": org.get("name")}


_ASSET_SEED = [
    {"ref": "AST-001", "name": "prod-web-gateway-01", "type": "Cloud VM", "criticality": "Critical", "exposure": 88, "owner": "Platform", "source": "Microsoft Entra ID", "status": "Internet-facing", "freshness": "live"},
    {"ref": "AST-002", "name": "identity-directory", "type": "Identity Store", "criticality": "Critical", "exposure": 72, "owner": "Dana Ops", "source": "Microsoft Entra ID", "status": "Managed", "freshness": "live"},
    {"ref": "AST-003", "name": "fin-db-primary", "type": "Database", "criticality": "High", "exposure": 41, "owner": "Data", "source": "Tenable", "status": "Internal", "freshness": "stale"},
    {"ref": "AST-004", "name": "exec-laptops (fleet)", "type": "Endpoint Group", "criticality": "High", "exposure": 55, "owner": "IT", "source": "Defender", "status": "Managed", "freshness": "live"},
    {"ref": "AST-005", "name": "ml-inference-cluster", "type": "AI Workload", "criticality": "High", "exposure": 63, "owner": "Data Science", "source": "CASB", "status": "Internal", "freshness": "live"},
    {"ref": "AST-006", "name": "vendor-sftp-bridge", "type": "Integration", "criticality": "Medium", "exposure": 47, "owner": "Priya GRC", "source": "Vendor Registry", "status": "Third-party", "freshness": "stale"},
    {"ref": "AST-007", "name": "backup-vault", "type": "Storage", "criticality": "Medium", "exposure": 22, "owner": "Ops", "source": "Ops Runbook", "status": "Internal", "freshness": "stale"},
    {"ref": "AST-008", "name": "shadow-marketing-gpt", "type": "Shadow AI", "criticality": "High", "exposure": 79, "owner": "Unassigned", "source": "CASB Discovery", "status": "Unsanctioned", "freshness": "live"},
]


@api.get("/assets")
async def assets(user: dict = Depends(get_current_user)):
    org_id = user["org_id"]
    existing = await db.assets.find({"org_id": org_id}, {"_id": 0}).to_list(500)
    if existing:
        return existing
    docs = [{**a, "org_id": org_id} for a in _ASSET_SEED]
    await db.assets.insert_many([dict(d) for d in docs])
    return await db.assets.find({"org_id": org_id}, {"_id": 0}).to_list(500)

