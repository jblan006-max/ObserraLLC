import random
from datetime import datetime, timezone, timedelta
from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator

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


AI_STATUS = {"sanctioned", "shadow", "killed", "restricted", "decommissioned"}
AI_RISK_CLASS = {"Low", "Medium", "High", "Critical"}


class AISystemUpdate(BaseModel):
    status: str | None = None
    risk_class: str | None = None

    @field_validator("status")
    @classmethod
    def _v_status(cls, v):
        if v is not None and v not in AI_STATUS:
            raise ValueError(f"Invalid status. Allowed: {sorted(AI_STATUS)}")
        return v

    @field_validator("risk_class")
    @classmethod
    def _v_risk_class(cls, v):
        if v is not None and v not in AI_RISK_CLASS:
            raise ValueError(f"Invalid risk_class. Allowed: {sorted(AI_RISK_CLASS)}")
        return v


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
    counter = await db.counters.find_one_and_update(
        {"_id": f"decisions:{user['org_id']}"}, {"$inc": {"seq": 1}},
        upsert=True, return_document=True)
    dref = f"DEC-{str(counter['seq']).zfill(3)}"
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
    from auth import subscription_active, is_owner, ALL_ENTITLEMENTS
    org = await db.organizations.find_one({"_id": ObjectId(user["org_id"])})
    if is_owner(user):
        return {"plan": "enterprise", "status": "active", "active": True, "trial_end": None,
                "current_period_end": None, "billing_interval": "year",
                "entitlements": ALL_ENTITLEMENTS, "restricted": False, "org_name": org.get("name")}
    plan = org.get("plan")
    org_ents = ALL_ENTITLEMENTS if plan == "enterprise" else list(org.get("entitlements", []))
    ma = user.get("module_access")
    ents, restricted = org_ents, False
    if user.get("role") != "admin" and isinstance(ma, list):
        ents = [e for e in org_ents if e in ma]
        restricted = True
    return {"plan": plan, "status": org.get("subscription_status"),
            "active": subscription_active(org), "trial_end": org.get("trial_end"),
            "current_period_end": org.get("current_period_end"),
            "billing_interval": org.get("billing_interval"),
            "entitlements": ents, "restricted": restricted, "org_name": org.get("name")}


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


# ---------- Financial quantification (FAIR-style) ----------
SLE_BY_IMPACT = {5: 8_000_000, 4: 3_000_000, 3: 1_000_000, 2: 300_000, 1: 75_000}


def _fin(r):
    sle = SLE_BY_IMPACT.get(r.get("impact", 3), 1_000_000)
    aro = r.get("likelihood", 3) / 5
    inherent = max(1, r.get("inherent", 10))
    residual = r.get("residual", inherent)
    inherent_ale = sle * aro
    residual_ale = inherent_ale * (residual / inherent)
    return {
        "sle": sle, "aro": round(aro, 2),
        "inherent_ale": round(inherent_ale), "residual_ale": round(residual_ale),
        "risk_adjusted": round(residual_ale * r.get("confidence", 0.7)),
    }


@api.get("/financials")
async def financials(user: dict = Depends(get_current_user)):
    risks = await db.risks.find({"org_id": user["org_id"]}, {"_id": 0}).to_list(500)
    items = [{"ref": r["ref"], "title": r["title"], "category": r["category"],
              "residual": r["residual"], "inherent": r["inherent"], **_fin(r)} for r in risks]
    items.sort(key=lambda x: x["residual_ale"], reverse=True)
    total_residual = sum(i["residual_ale"] for i in items)
    total_inherent = sum(i["inherent_ale"] for i in items)
    total_adj = sum(i["risk_adjusted"] for i in items)
    return {"items": items, "total_residual_ale": total_residual, "total_inherent_ale": total_inherent,
            "total_risk_adjusted": total_adj, "avoided": total_inherent - total_residual}


# ---------- Decision simulation (what-if) ----------
_POINT_COST = {"Identity & Access": 42000, "Vulnerability Mgmt": 55000, "AI Governance": 60000,
               "Third Party": 30000, "Resilience": 38000, "Data Protection": 48000}


class SimulateBody(BaseModel):
    risk_ref: str
    target_residual: int


@api.post("/simulate")
async def simulate(body: SimulateBody, user: dict = Depends(get_current_user)):
    r = await db.risks.find_one({"org_id": user["org_id"], "ref": body.risk_ref}, {"_id": 0})
    if not r:
        raise HTTPException(404, "Risk not found")
    target = max(1, min(r["inherent"], body.target_residual))
    before = _fin(r)
    after = _fin({**r, "residual": target})
    reduction = before["residual_ale"] - after["residual_ale"]
    points = max(0, r["residual"] - target)
    cost = points * _POINT_COST.get(r["category"], 45000)
    roi = round(reduction / cost, 2) if cost else None
    return {
        "risk_ref": body.risk_ref, "current_residual": r["residual"], "target_residual": target,
        "exposure_before": before["residual_ale"], "exposure_after": after["residual_ale"],
        "expected_reduction": reduction, "estimated_cost": cost, "roi": roi,
        "health_delta": min(6, points), "payback_months": (round(cost / (reduction / 12)) if reduction else None),
    }


# ---------- Evidence drill-down ----------
_FW_BY_CAT = {"Identity & Access": ["NIST CSF 2.0", "NIST SP 800-53", "SOC 2", "ISO/IEC 27001"],
              "Vulnerability Mgmt": ["NIST SP 800-53", "NIST SSDF", "ISO/IEC 27001", "SOC 2"],
              "AI Governance": ["NIST AI RMF", "EU AI Act", "ISO/IEC 42001", "NIST SSDF"],
              "Third Party": ["SOC 2", "ISO/IEC 27001", "GDPR"], "Resilience": ["ISO/IEC 27001", "NIST CSF 2.0", "SOC 2"],
              "Data Protection": ["GDPR", "ISO/IEC 27001", "SOC 2", "NIST SP 800-53"]}
_CTRL_BY_CAT = {"Identity & Access": "IAM-3 Privileged Access Management",
                "Vulnerability Mgmt": "VM-2 Timely Remediation", "AI Governance": "AIG-1 AI Use Governance",
                "Third Party": "TPR-4 Vendor Attestation", "Resilience": "BCP-2 DR Testing",
                "Data Protection": "DP-1 Data Minimization"}


@api.get("/evidence/{kind}/{ref}")
async def evidence(kind: str, ref: str, user: dict = Depends(get_current_user)):
    org_id = user["org_id"]
    if kind == "risk":
        r = await db.risks.find_one({"org_id": org_id, "ref": ref}, {"_id": 0})
        if not r:
            raise HTTPException(404, "Not found")
        rec = await db.recommendations.find_one({"org_id": org_id, "risk_ref": ref}, {"_id": 0})
        live = r["freshness"] == "live"
        return {
            "metric": f"Residual Risk — {ref}", "value": r["residual"],
            "calculation": f"likelihood({r['likelihood']}) × impact({r['impact']}) = inherent {r['inherent']}; residual after controls = {r['residual']}",
            "methodology": "FAIR-aligned inherent × residual with control-effectiveness ratio",
            "source_system": r["source"], "source_record": ref,
            "evidence": [r.get("kri", ""), f"Owner attestation — {r['owner']}", f"Treatment: {r['treatment']}"],
            "evidence_owner": r["owner"], "collected": r.get("created_at"), "last_verified": r.get("updated_at"),
            "freshness": r["freshness"], "confidence": r["confidence"],
            "completeness": 0.92 if r["data_type"] == "fact" else 0.72,
            "reliability": 0.88 if live else 0.6, "data_type": r["data_type"],
            "related_controls": [_CTRL_BY_CAT.get(r["category"], "GEN-1 General Control")],
            "related_risks": [ref], "frameworks": _FW_BY_CAT.get(r["category"], ["NIST CSF 2.0"]),
            "historical": [{"label": "Inherent", "value": r["inherent"]}, {"label": "Residual", "value": r["residual"]}],
            "ai_reasoning": rec["predicted_impact"] if rec else "No active recommendation.",
            "human_validation": "Validated" if r["status"] != "Open" else "Pending review",
            "financial": _fin(r),
        }
    if kind == "health":
        h = await db.health_index.find_one({"org_id": org_id}, {"_id": 0})
        comp = next((c for c in h["components"] if c["name"] == ref), None)
        if not comp:
            raise HTTPException(404, "Not found")
        return {
            "metric": f"Health Component — {ref}", "value": comp["score"],
            "calculation": f"weighted contribution {int(comp['weight']*100)}% of Enterprise Health Index ({h['score']})",
            "methodology": "Weighted control-effectiveness rollup across connected sources",
            "source_system": "Aggregated (Entra ID · Tenable · CASB)", "source_record": ref,
            "evidence": ["Continuous control monitoring", "Connector telemetry"],
            "evidence_owner": "Security Operations", "collected": h.get("computed_at"), "last_verified": h.get("computed_at"),
            "freshness": h.get("freshness", "live"), "confidence": comp.get("confidence", 0.8),
            "completeness": 0.9, "reliability": 0.85, "data_type": "fact",
            "related_controls": [_CTRL_BY_CAT.get(ref, "GEN-1 General Control")],
            "related_risks": [], "frameworks": _FW_BY_CAT.get(ref, ["NIST CSF 2.0"]),
            "historical": h.get("history", []), "ai_reasoning": "Trend derived from control telemetry.",
            "human_validation": "Validated",
        }
    raise HTTPException(400, "Unknown evidence kind")


# ---------- Enterprise Knowledge Graph ----------
async def _build_graph(org_id):
    ai = await db.ai_systems.find({"org_id": org_id}, {"_id": 0}).to_list(100)
    risks = await db.risks.find({"org_id": org_id}, {"_id": 0}).to_list(200)
    nodes, edges = [], []

    def add(nid, label, ntype, meta=None):
        nodes.append({"id": nid, "label": label, "type": ntype, "meta": meta or {}})

    for d, lbl in [("D-CONF", "Confidential PII"), ("D-FIN", "Financial Data"), ("D-PUB", "Public Data")]:
        add(d, lbl, "data")
    vendors = {"V-OPENAI": ("OpenAI", "high"), "V-ANTHROPIC": ("Anthropic", "low"),
               "V-INHOUSE": ("In-house", "low"), "V-UNKNOWN": ("Unknown SaaS", "critical")}
    for vid, (lbl, rl) in vendors.items():
        add(vid, lbl, "vendor", {"risk_level": rl})
    prov_map = {"AI-001": "V-OPENAI", "AI-002": "V-INHOUSE", "AI-003": "V-UNKNOWN", "AI-004": "V-ANTHROPIC"}
    data_map = {"AI-001": ["D-CONF"], "AI-002": ["D-CONF", "D-FIN"], "AI-003": ["D-CONF"], "AI-004": ["D-CONF"]}
    for a in ai:
        add(a["ref"], a["name"], "ai", {"status": a["status"], "risk_class": a["risk_class"]})
        v = prov_map.get(a["ref"], "V-OPENAI")
        edges.append({"source": a["ref"], "target": v, "label": "depends_on"})
        for d in data_map.get(a["ref"], ["D-PUB"]):
            edges.append({"source": a["ref"], "target": d, "label": "processes"})
    for r in risks:
        add(r["ref"], r["title"][:26], "risk", {"residual": r["residual"], "status": r["status"], "category": r["category"]})
    # vendor -> risk links
    edges.append({"source": "V-UNKNOWN", "target": "CR-004", "label": "has_risk"})
    edges.append({"source": "V-OPENAI", "target": "CR-004", "label": "has_risk"})
    for bu in ["Corporate", "Engineering", "Finance", "Customer Ops"]:
        add(f"BU-{bu}", bu, "bu")
    for reg in ["EU AI Act", "NIST AI RMF", "GDPR", "PCI DSS"]:
        add(f"REG-{reg}", reg, "regulation")
    return {"nodes": nodes, "edges": edges}


@api.get("/knowledge-graph")
async def knowledge_graph(user: dict = Depends(get_current_user)):
    return await _build_graph(user["org_id"])


class GraphQuery(BaseModel):
    preset: str


@api.post("/knowledge-graph/query")
async def knowledge_graph_query(body: GraphQuery, user: dict = Depends(get_current_user)):
    g = await _build_graph(user["org_id"])
    nodes = {n["id"]: n for n in g["nodes"]}
    edges = g["edges"]
    highlight, matches = set(), []
    if body.preset == "conf_risky_vendor":
        risky_vendors = {n["id"] for n in g["nodes"] if n["type"] == "vendor" and n["meta"].get("risk_level") in ("critical", "high")}
        for n in g["nodes"]:
            if n["type"] != "ai":
                continue
            proc_conf = any(e for e in edges if e["source"] == n["id"] and e["target"] == "D-CONF")
            vend = next((e["target"] for e in edges if e["source"] == n["id"] and e["label"] == "depends_on"), None)
            if proc_conf and vend in risky_vendors:
                matches.append(n["id"]); highlight.update([n["id"], "D-CONF", vend])
        explanation = f"{len(matches)} AI system(s) process Confidential PII AND depend on a high/critical-risk vendor: {', '.join(matches) or 'none'}."
    elif body.preset == "shadow_exposure":
        for n in g["nodes"]:
            if n["type"] == "ai" and n["meta"].get("status") == "shadow":
                matches.append(n["id"]); highlight.add(n["id"])
                for e in edges:
                    if e["source"] == n["id"]:
                        highlight.add(e["target"])
        explanation = f"{len(matches)} shadow AI system(s) discovered with active data/vendor dependencies."
    elif body.preset == "critical_risks":
        for n in g["nodes"]:
            if n["type"] == "risk" and n["meta"].get("residual", 0) >= 16:
                matches.append(n["id"]); highlight.add(n["id"])
        explanation = f"{len(matches)} critical residual risk(s) (score ≥ 16)."
    else:
        raise HTTPException(400, "Unknown preset")
    return {"highlight": list(highlight), "matches": matches, "explanation": explanation}


# ---------- Continuous Control Monitoring ----------
def _d(n):
    return (datetime.now(timezone.utc) + timedelta(days=n)).isoformat()


_CONTROL_SEED = [
    {"control_id": "IAM-3", "name": "Privileged Access Management", "category": "Identity & Access", "framework": "NIST CSF 2.0", "effectiveness": 78, "maturity": 3, "owner": "Dana Ops", "last_tested": _d(-12), "evidence_expires": _d(20), "related_risk": "CR-001", "baseline": 82},
    {"control_id": "VM-2", "name": "Timely Vulnerability Remediation", "category": "Vulnerability Mgmt", "framework": "NIST SP 800-53", "effectiveness": 61, "maturity": 2, "owner": "Sam Vuln", "last_tested": _d(-40), "evidence_expires": _d(-5), "related_risk": "CR-002", "baseline": 72},
    {"control_id": "AIG-1", "name": "AI Use Governance", "category": "AI Governance", "framework": "NIST AI RMF", "effectiveness": 66, "maturity": 2, "owner": "AI Gov Board", "last_tested": _d(-8), "evidence_expires": _d(35), "related_risk": "CR-004", "baseline": 64},
    {"control_id": "DP-1", "name": "Data Minimization", "category": "Data Protection", "framework": "GDPR", "effectiveness": 81, "maturity": 3, "owner": "Priya GRC", "last_tested": _d(-20), "evidence_expires": _d(60), "related_risk": None, "baseline": 80},
    {"control_id": "BCP-2", "name": "DR / Backup Restoration Testing", "category": "Resilience", "framework": "ISO/IEC 27001", "effectiveness": 52, "maturity": 2, "owner": "Ops Team", "last_tested": _d(-182), "evidence_expires": _d(-30), "related_risk": "CR-006", "baseline": 69},
    {"control_id": "TPR-4", "name": "Vendor Attestation Review", "category": "Third Party", "framework": "SOC 2", "effectiveness": 70, "maturity": 3, "owner": "Priya GRC", "last_tested": _d(-25), "evidence_expires": _d(10), "related_risk": "CR-003", "baseline": 74},
]


_CONTROL_FRAMEWORKS = {
    "IAM-3": {"NIST CSF 2.0": ["PR.AA-01", "PR.AA-05"], "NIST 800-53": ["AC-2", "AC-6"], "ISO 27001": ["A.5.15", "A.8.2"], "SOC 2": ["CC6.1", "CC6.3"], "CISA CPG": ["2.A", "2.E"]},
    "VM-2": {"NIST CSF 2.0": ["ID.RA-01", "PR.PS-02"], "NIST 800-53": ["RA-5", "SI-2"], "ISO 27001": ["A.8.8"], "SOC 2": ["CC7.1"], "CISA CPG": ["1.E", "4.C"]},
    "AIG-1": {"NIST CSF 2.0": ["GV.OC-01"], "NIST 800-53": ["PM-9", "SA-8"], "ISO 27001": ["A.5.1"], "SOC 2": ["CC1.2"], "CISA CPG": ["2.K"]},
    "DP-1": {"NIST CSF 2.0": ["PR.DS-01"], "NIST 800-53": ["SC-28", "PL-8"], "ISO 27001": ["A.8.11", "A.5.34"], "SOC 2": ["CC6.7"], "CISA CPG": ["2.K"]},
    "BCP-2": {"NIST CSF 2.0": ["RC.RP-01", "PR.IP-04"], "NIST 800-53": ["CP-9", "CP-10"], "ISO 27001": ["A.8.13", "A.5.29"], "SOC 2": ["A1.2", "A1.3"], "CISA CPG": ["5.A"]},
    "TPR-4": {"NIST CSF 2.0": ["GV.SC-01", "ID.SC-04"], "NIST 800-53": ["SR-3", "SR-6"], "ISO 27001": ["A.5.19", "A.5.20"], "SOC 2": ["CC9.2"], "CISA CPG": ["4.C"]},
}


def _control_status(c):
    now = datetime.now(timezone.utc)
    exp = datetime.fromisoformat(c["evidence_expires"])
    days_to_expiry = (exp - now).days
    stale = days_to_expiry < 0
    drift = c["effectiveness"] < c.get("baseline", c["effectiveness"]) - 5
    if stale:
        status = "Evidence Stale"
    elif c["effectiveness"] < 55:
        status = "Failing"
    elif drift:
        status = "Drifting"
    else:
        status = "Passing"
    return {**{k: v for k, v in c.items() if k != "org_id"}, "days_to_expiry": days_to_expiry,
            "stale": stale, "drift": drift, "status": status,
            "frameworks": _CONTROL_FRAMEWORKS.get(c["control_id"], {}),
            "drift_delta": c["effectiveness"] - c.get("baseline", c["effectiveness"])}


@api.get("/controls")
async def controls(user: dict = Depends(get_current_user)):
    org_id = user["org_id"]
    existing = await db.controls.find({"org_id": org_id}, {"_id": 0}).to_list(500)
    if not existing:
        await db.controls.insert_many([{**c, "org_id": org_id} for c in _CONTROL_SEED])
        existing = await db.controls.find({"org_id": org_id}, {"_id": 0}).to_list(500)
    statuses = [_control_status(c) for c in existing]
    await _emit_drift_alerts(org_id, statuses)
    return statuses


@api.get("/controls/compliance")
async def controls_compliance(user: dict = Depends(get_current_user)):
    org_id = user["org_id"]
    existing = await db.controls.find({"org_id": org_id}, {"_id": 0}).to_list(500)
    if not existing:
        await db.controls.insert_many([{**c, "org_id": org_id} for c in _CONTROL_SEED])
        existing = await db.controls.find({"org_id": org_id}, {"_id": 0}).to_list(500)
    statuses = [_control_status(c) for c in existing]
    agg = {}
    for c in statuses:
        for fw, refs in (c.get("frameworks") or {}).items():
            e = agg.setdefault(fw, {"framework": fw, "controls": 0, "passing": 0, "eff_sum": 0, "refs": set()})
            e["controls"] += 1
            e["eff_sum"] += c["effectiveness"]
            if c["status"] == "Passing":
                e["passing"] += 1
            e["refs"].update(refs)
    out = [{"framework": fw, "controls": e["controls"], "passing": e["passing"],
            "coverage": round(e["eff_sum"] / e["controls"]) if e["controls"] else 0,
            "mapped_refs": sorted(e["refs"])} for fw, e in agg.items()]
    out.sort(key=lambda x: x["framework"])
    overall = round(sum(f["coverage"] for f in out) / len(out)) if out else 0
    _RECS = {"Failing": "Effectiveness below threshold — prioritize remediation and re-test the control.",
             "Evidence Stale": "Evidence has expired — collect fresh evidence and re-attest.",
             "Drifting": "Effectiveness declined vs baseline — investigate the drift and restore controls."}
    _SEV = {"Failing": 0, "Evidence Stale": 1, "Drifting": 2}
    gaps = [{"control_id": c["control_id"], "name": c["name"], "status": c["status"],
             "effectiveness": c["effectiveness"], "owner": c.get("owner"),
             "frameworks": list((c.get("frameworks") or {}).keys()),
             "recommendation": _RECS.get(c["status"], "Review this control.")}
            for c in statuses if c["status"] != "Passing"]
    gaps.sort(key=lambda g: (_SEV.get(g["status"], 3), g["effectiveness"]))
    return {"frameworks": out, "overall": overall, "gaps": gaps,
            "total_controls": len(statuses), "passing": sum(1 for c in statuses if c["status"] == "Passing")}


async def _emit_drift_alerts(org_id, statuses):
    from kernel import notifications, policies
    thresholds = await policies.thresholds(org_id)
    for c in statuses:
        violations = policies.evaluate_control(c, thresholds)
        if not violations:
            continue
        reasons = "; ".join(f"{r} ({pid})" for pid, r in violations)
        await notifications.create(
            org_id, "control_drift",
            f"Control {c['control_id']} needs attention",
            f"{c['name']} — owner {c['owner']}. {reasons}.",
            ref=c["control_id"],
            dedupe_key=f"drift:{c['control_id']}:{c['evidence_expires'][:10]}:{c['effectiveness']}")


async def _nudge_owner(org_id, owner_name, entity_label, note_text, actor):
    """Email + in-app nudge to the control/vendor owner (or org admins/execs) when a remediation is logged."""
    import re as _re
    from kernel import notifications
    title = f"Remediation logged — {entity_label}"
    body = f"{actor} logged a remediation action on {entity_label}: {note_text[:180]}"
    await notifications.create(org_id, "risk_critical", title, body, ref=entity_label)
    recipients = []
    org = await db.organizations.find_one({"_id": ObjectId(org_id)}, {"owner_directory": 1}) or {}
    directory = org.get("owner_directory") or {}
    if owner_name:
        email = directory.get(owner_name.strip().lower())
        if email:
            recipients.append(email)
        else:
            u = await db.users.find_one({"org_id": org_id, "name": {"$regex": f"^{_re.escape(owner_name)}$", "$options": "i"}})
            if u and u.get("email"):
                recipients.append(u["email"])
    if not recipients:
        admins = await db.users.find({"org_id": org_id, "role": {"$in": ["admin", "executive"]}}).to_list(20)
        recipients = [a["email"] for a in admins if a.get("email")]
    html = (f"<div style='font:400 14px Arial;color:#0f1e3d'>"
            f"<h2 style='font:800 18px Arial;color:#0f1e3d'>{title}</h2><p>{body}</p>"
            f"<p style='color:#6b7280'>Owner: {owner_name or 'unassigned'} · via Obserra EIOS.</p></div>")
    for to in recipients:
        try:
            await notifications.send_email(to, title, html)
        except Exception:
            pass


class ControlNote(BaseModel):
    kind: str = "note"
    text: str


@api.get("/controls/{control_id}/history")
async def control_history(control_id: str, user: dict = Depends(get_current_user)):
    return await db.control_notes.find(
        {"org_id": user["org_id"], "control_id": control_id}, {"_id": 0}).sort("ts", -1).to_list(100)


@api.post("/controls/{control_id}/notes")
async def add_control_note(control_id: str, body: ControlNote, user: dict = Depends(get_current_user)):
    text = (body.text or "").strip()
    if not text:
        raise HTTPException(400, "Note text required")
    kind = body.kind if body.kind in ("note", "evidence", "remediation") else "note"
    doc = {"org_id": user["org_id"], "control_id": control_id, "kind": kind, "text": text,
           "author": user.get("name") or user["email"], "ts": datetime.now(timezone.utc).isoformat()}
    await db.control_notes.insert_one(doc)
    await _audit(user["org_id"], user["email"], "control.note", f"{control_id}: {kind}")
    if kind == "remediation":
        ctrl = await db.controls.find_one({"org_id": user["org_id"], "control_id": control_id}, {"_id": 0})
        await _nudge_owner(user["org_id"], (ctrl or {}).get("owner"), control_id, text, doc["author"])
    doc.pop("_id", None)
    return doc


async def compute_momentum(org_id):
    """Risk-reduction momentum score + recent activity + weekly trajectory for an org."""
    cnotes = await db.control_notes.find({"org_id": org_id}, {"_id": 0}).sort("ts", -1).to_list(200)
    vnotes = await db.vendor_notes.find({"org_id": org_id}, {"_id": 0}).sort("ts", -1).to_list(200)
    items = [{"entity": n["control_id"], "type": "control", "kind": n["kind"],
              "text": n["text"], "author": n.get("author"), "ts": n["ts"]} for n in cnotes]
    items += [{"entity": n["ref"], "type": "vendor", "kind": n["kind"],
               "text": n["text"], "author": n.get("author"), "ts": n["ts"]} for n in vnotes]
    items.sort(key=lambda x: x["ts"], reverse=True)
    cutoff = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    recent = [i for i in items if i["ts"] >= cutoff]
    rem = sum(1 for i in recent if i["kind"] == "remediation")
    evi = sum(1 for i in recent if i["kind"] == "evidence")
    applied = await db.recommendations.count_documents({"org_id": org_id, "status": "Applied"})
    score = min(100, rem * 12 + evi * 6 + applied * 8)
    now = datetime.now(timezone.utc)
    trend = []
    for w in range(7, -1, -1):
        end = now - timedelta(days=7 * w)
        start_iso = (end - timedelta(days=30)).isoformat()
        end_iso = end.isoformat()
        wr = sum(1 for i in items if i["kind"] == "remediation" and start_iso <= i["ts"] <= end_iso)
        we = sum(1 for i in items if i["kind"] == "evidence" and start_iso <= i["ts"] <= end_iso)
        trend.append({"week": end.strftime("%b %d"), "score": min(100, wr * 12 + we * 6 + applied * 8)})
    prev_score = trend[-2]["score"] if len(trend) >= 2 else score
    return {"score": score, "prev_score": prev_score, "remediation_count": rem, "evidence_count": evi,
            "applied_recommendations": applied, "activity": items[:8], "window_days": 30, "trend": trend}


@api.get("/remediation/activity")
async def remediation_activity(user: dict = Depends(get_current_user)):
    """Executive rollup — recent remediation/evidence activity + a risk-reduction momentum score."""
    return await compute_momentum(user["org_id"])


class OwnerDirectoryBody(BaseModel):
    directory: dict[str, str] = {}


@api.get("/owners")
async def get_owners(user: dict = Depends(get_current_user)):
    org_id = user["org_id"]
    controls = await db.controls.find({"org_id": org_id}, {"_id": 0, "owner": 1}).to_list(500)
    vendors = await db.vendors.find({"org_id": org_id}, {"_id": 0, "owner": 1}).to_list(500)
    names = {(c.get("owner") or "").strip() for c in controls} | {(v.get("owner") or "").strip() for v in vendors}
    names = sorted(n for n in names if n)
    org = await db.organizations.find_one({"_id": ObjectId(org_id)}, {"owner_directory": 1}) or {}
    directory = org.get("owner_directory") or {}
    users = await db.users.find({"org_id": org_id}, {"_id": 0, "name": 1, "email": 1}).to_list(500)

    def _suggest(name):
        nl = (name or "").strip().lower()
        for u in users:
            if (u.get("name") or "").strip().lower() == nl and u.get("email"):
                return u["email"]
        first = nl.split()[0] if nl.split() else nl
        for u in users:
            un = (u.get("name") or "").strip().lower()
            if un and un.split() and un.split()[0] == first and u.get("email"):
                return u["email"]
        return ""

    return {"owners": [{"name": n, "email": directory.get(n.lower(), ""), "suggestion": _suggest(n)} for n in names]}


@api.put("/owners")
async def set_owners(body: OwnerDirectoryBody, user: dict = Depends(get_current_user)):
    if user.get("role") != "admin":
        raise HTTPException(403, "Admins only")
    import re as _re
    clean = {}
    for name, email in (body.directory or {}).items():
        email = (email or "").strip()
        if email and not _re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
            raise HTTPException(400, f"Invalid email for {name}")
        if email:
            clean[name.strip().lower()] = email
    await db.organizations.update_one({"_id": ObjectId(user["org_id"])}, {"$set": {"owner_directory": clean}})
    return {"ok": True, "count": len(clean)}


class AuthUIBody(BaseModel):
    hide_social: bool = False


@api.get("/settings/auth-ui")
async def get_auth_ui(user: dict = Depends(get_current_user)):
    cfg = await db.app_config.find_one({"_id": "auth_ui"}) or {}
    return {"hide_social": bool(cfg.get("hide_social"))}


@api.put("/settings/auth-ui")
async def set_auth_ui(body: AuthUIBody, user: dict = Depends(get_current_user)):
    if user.get("role") != "admin":
        raise HTTPException(403, "Admins only")
    await db.app_config.update_one({"_id": "auth_ui"}, {"$set": {"hide_social": body.hide_social}}, upsert=True)
    return {"ok": True, "hide_social": body.hide_social}


@api.get("/financials/trend")
async def financials_trend(user: dict = Depends(get_current_user)):
    risks = await db.risks.find({"org_id": user["org_id"]}, {"_id": 0}).to_list(500)
    total = sum(_fin(r)["residual_ale"] for r in risks)
    health = await db.health_index.find_one({"org_id": user["org_id"]}, {"_id": 0})
    hist = health.get("history", []) if health else []
    cur = health.get("score", 69) if health else 69
    series = []
    for h in hist:
        ratio = cur / max(1, h["score"])  # lower past health -> higher past exposure
        series.append({"month": h["month"], "exposure": round(total * ratio)})
    if series:
        series[-1]["exposure"] = round(total)
    return {"series": series, "current": round(total)}

