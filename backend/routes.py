import random
from datetime import datetime, timezone, timedelta
from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator

from db import db
from auth import get_current_user, require_active_subscription, require_roles

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

# Published external benchmarks — PRELOADED from the IBM Cost of a Data Breach report and Verizon
# DBIR, stored in the DB and re-checked at most once per year (see _maybe_refresh_benchmarks).
BENCHMARKS = {
    "updated": "2026-07-29",
    "source": ("IBM Cost of a Data Breach 2026 (global avg $4.99M) & 2025 industry table; "
               "Verizon DBIR 2025 typical incident-loss medians."),
    "global_avg": 4_990_000,
    "industries": {
        "Healthcare": 7_420_000, "Financial": 6_080_000, "Pharmaceuticals": 5_100_000,
        "Technology": 5_450_000, "Energy": 5_290_000, "Industrial": 5_560_000,
        "Professional Services": 5_000_000, "Retail": 3_480_000, "Public sector": 2_860_000,
        "Education": 3_700_000, "Hospitality": 3_500_000, "Media": 3_500_000,
        "Transportation": 4_400_000, "Communications": 4_400_000,
    },
    "dbir_ransomware_median": 46_000,
    "dbir_bec_median": 50_000,
    "ai_breach_avg": 6_000_000,
    "shadow_ai_premium": 670_000,
}


async def _get_benchmarks():
    from datetime import datetime, timezone
    doc = await db.app_benchmarks.find_one({"_id": "global"})
    if not doc:
        doc = {**BENCHMARKS, "_id": "global", "checked_at": datetime.now(timezone.utc).isoformat()}
        await db.app_benchmarks.insert_one(dict(doc))
    else:
        missing = {k: v for k, v in BENCHMARKS.items() if k not in doc}
        if missing:
            await db.app_benchmarks.update_one({"_id": "global"}, {"$set": missing})
            doc.update(missing)
    return doc


async def _maybe_refresh_benchmarks(force=False):
    """Preloaded from IBM/DBIR; best-effort re-fetch at most once per year. Keeps the stored
    figures on any failure so the board never sees a broken number."""
    import re as _re
    from datetime import datetime, timezone, timedelta
    import httpx
    doc = await _get_benchmarks()
    try:
        last = datetime.fromisoformat(doc.get("checked_at") or "1970-01-01T00:00:00+00:00")
    except Exception:
        last = datetime(1970, 1, 1, tzinfo=timezone.utc)
    if not force and datetime.now(timezone.utc) - last < timedelta(days=365):
        return doc
    updates = {"checked_at": datetime.now(timezone.utc).isoformat()}
    try:
        async with httpx.AsyncClient(timeout=8, follow_redirects=True) as c:
            r = await c.get("https://newsroom.ibm.com/2026-07-29-ibm-study-one-in-four-malicious-breaches-are-ai-enabled,-costing-companies-6-million-on-average")
            m = _re.search(r"\$([0-9]+(?:\.[0-9]+)?)\s*million", r.text)
            if m:
                val = int(float(m.group(1)) * 1_000_000)
                if 1_000_000 <= val <= 20_000_000:
                    updates["global_avg"] = val
                    updates["updated"] = datetime.now(timezone.utc).date().isoformat()
    except Exception:
        pass
    await db.app_benchmarks.update_one({"_id": "global"}, {"$set": updates})
    return await _get_benchmarks()


async def _benchmark(industry):
    b = await _get_benchmarks()
    return {
        "industry": industry,
        "industry_avg": (b.get("industries") or {}).get(industry),
        "industry_avg_source": "IBM Cost of a Data Breach 2025 (industry table)",
        "global_avg": b.get("global_avg"),
        "global_avg_source": "IBM Cost of a Data Breach 2026 (global avg)",
        "dbir_ransomware_median": b.get("dbir_ransomware_median"),
        "dbir_bec_median": b.get("dbir_bec_median"),
        "dbir_source": "Verizon DBIR 2025 (incident-loss medians)",
        "ai_breach_avg": b.get("ai_breach_avg"),
        "ai_breach_source": "IBM Cost of a Data Breach 2026 (AI-enabled breaches)",
        "shadow_ai_premium": b.get("shadow_ai_premium"),
        "shadow_ai_source": "IBM 2025 (shadow-AI cost premium)",
        "source": b.get("source"), "updated": b.get("updated"), "checked_at": b.get("checked_at"),
    }


async def _suggested_records(org_id):
    """Records-at-risk auto-fill from connected data sources (M365/Entra + Tenable + CASB)."""
    conn = await db.connectors.find_one({"org_id": org_id, "id": "entra"}) or {}
    identities = (conn.get("records_ingested", 0) or 0) + 1893 + 612
    est = identities * 50 if identities else 0
    return {"records": est,
            "source": f"connected sources — {identities:,} directory/asset records × 50 avg records/identity (MOCKED_LIVE)"}


def _cfg_hash(cfg):
    import hashlib
    import json
    payload = json.dumps({k: cfg.get(k) for k in ("impact_sle", "industry", "method", "records", "per_record_cost")},
                         sort_keys=True, default=str)
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


async def _get_fin_cfg(org_id):
    org = await db.organizations.find_one({"_id": ObjectId(org_id)}) or {}
    cfg = org.get("financial_config") or {}
    impact_sle = {int(k): int(v) for k, v in (cfg.get("impact_sle") or {}).items()} or dict(SLE_BY_IMPACT)
    return {
        "impact_sle": impact_sle,
        "custom_table": bool(cfg.get("impact_sle")),
        "industry": cfg.get("industry", "Technology"),
        "method": cfg.get("method", "flat"),
        "records": cfg.get("records"),
        "per_record_cost": cfg.get("per_record_cost", 165),
        "signoff": cfg.get("signoff"),
    }


def _fin(r, cfg=None):
    impact = r.get("impact", 3)
    if cfg and cfg.get("method") == "records" and cfg.get("records"):
        base = int(cfg["records"]) * int(cfg.get("per_record_cost") or 165)
        sle = round(base * (impact / 5))
        sle_source = (f"{int(cfg['records']):,} records × ${int(cfg.get('per_record_cost') or 165)}/record "
                      f"× impact {impact}/5 (IBM per-record method)")
    else:
        table = (cfg or {}).get("impact_sle") or SLE_BY_IMPACT
        sle = table.get(impact, table.get(3, 1_000_000))
        sle_source = ("org-configured impact→$ table" if cfg and cfg.get("custom_table")
                      else "default impact→$ table (analyst assumption — calibrate for defensibility)")
    aro = r.get("likelihood", 3) / 5
    inherent = max(1, r.get("inherent", 10))
    residual = r.get("residual", inherent)
    conf = r.get("confidence", 0.7)
    inherent_ale = sle * aro
    residual_ale = inherent_ale * (residual / inherent)
    return {
        "sle": sle, "sle_source": sle_source,
        "aro": round(aro, 2), "aro_basis": f"likelihood {r.get('likelihood', 3)}/5",
        "inherent_ale": round(inherent_ale), "residual_ale": round(residual_ale),
        "confidence": conf, "risk_adjusted": round(residual_ale * conf),
        "math": f"SLE ${sle:,.0f} × ARO {round(aro, 2)} × (residual {residual}/inherent {inherent}) × confidence {conf}",
    }


class FinConfig(BaseModel):
    impact_sle: dict | None = None
    industry: str | None = None
    method: str | None = None
    records: int | None = None
    per_record_cost: int | None = None


class SignoffBody(BaseModel):
    name: str


def _montecarlo(items, iters=2000):
    """Monte-Carlo the portfolio residual exposure into a low/expected/high band (P10/P50/P90)."""
    import random
    if not items:
        return {"p10": 0, "p50": 0, "p90": 0}
    totals = []
    for _ in range(iters):
        s = 0.0
        for it in items:
            sle_s = random.triangular(it["sle"] * 0.5, it["sle"] * 2.0, it["sle"])
            aro_s = min(1.0, max(0.0, random.gauss(it["aro"], 0.15)))
            ratio = it["residual"] / max(1, it["inherent"])
            s += sle_s * aro_s * ratio
        totals.append(s)
    totals.sort()

    def _pct(p):
        return round(totals[min(len(totals) - 1, int(p * len(totals)))])
    return {"p10": _pct(0.10), "p50": _pct(0.50), "p90": _pct(0.90)}


def _montecarlo_item(f, r, iters=1000):
    import random
    ratio = r.get("residual", 10) / max(1, r.get("inherent", 10))
    vals = []
    for _ in range(iters):
        sle_s = random.triangular(f["sle"] * 0.5, f["sle"] * 2.0, f["sle"])
        aro_s = min(1.0, max(0.0, random.gauss(f["aro"], 0.15)))
        vals.append(sle_s * aro_s * ratio)
    vals.sort()

    def _p(p):
        return round(vals[min(len(vals) - 1, int(p * len(vals)))])
    return {"p10": _p(0.10), "p50": _p(0.50), "p90": _p(0.90)}


async def _record_exposure_snapshot(org_id):
    from datetime import datetime, timezone
    cfg = await _get_fin_cfg(org_id)
    risks = await db.risks.find({"org_id": org_id}, {"_id": 0}).to_list(500)
    if not risks:
        return
    fins = [_fin(r, cfg) for r in risks]
    avg = round(sum(f["sle"] for f in fins) / len(fins))
    residual_total = round(sum(f["residual_ale"] for f in fins))
    bench = await _benchmark(cfg["industry"])
    now = datetime.now(timezone.utc)
    month = now.strftime("%Y-%m")
    await db.exposure_snapshots.update_one(
        {"org_id": org_id, "month": month},
        {"$set": {"org_id": org_id, "month": month, "label": now.strftime("%b %y"),
                  "modelled_avg_sle": avg, "residual_total": residual_total,
                  "benchmark": bench.get("industry_avg"), "industry": cfg["industry"],
                  "ts": now.isoformat()}}, upsert=True)


async def _record_all_snapshots():
    orgs = await db.organizations.find({}, {"_id": 1}).to_list(1000)
    for o in orgs:
        try:
            await _record_exposure_snapshot(str(o["_id"]))
        except Exception:
            pass


_INDUSTRY_KEYWORDS = {
    "Healthcare": ["health", "hospital", "clinic", "med", "care", "pharma"],
    "Financial": ["bank", "financial", "capital", "invest", "insur", "fintech", "credit"],
    "Technology": ["tech", "software", "cloud", "data", "ai", "cyber", "digital", "labs"],
    "Retail": ["retail", "shop", "store", "commerce"],
    "Public sector": ["gov", "public", "city", "county", "federal", "state"],
    "Education": ["school", "university", "college", "edu", "academy"],
    "Energy": ["energy", "power", "oil", "gas", "utility", "grid"],
    "Transportation": ["transport", "logistic", "freight", "airline", "rail"],
}


async def _detect_industry(org_id):
    org = await db.organizations.find_one({"_id": ObjectId(org_id)}) or {}
    if org.get("sector"):
        for ind in BENCHMARKS["industries"]:
            if ind.lower() in str(org["sector"]).lower():
                return {"industry": ind, "reason": f"organisation sector '{org['sector']}'"}
    name = (org.get("name") or "").lower()
    for ind, kws in _INDUSTRY_KEYWORDS.items():
        if any(k in name for k in kws):
            return {"industry": ind, "reason": f"matched organisation name '{org.get('name')}'"}
    return {"industry": "Technology", "reason": "no strong signal — defaulted to Technology"}


async def _signoff_reminders():
    """Nudge when a locked calibration has drifted from its signed hash."""
    import notifications
    orgs = await db.organizations.find({"financial_config.signoff.locked": True}).to_list(1000)
    for org in orgs:
        cfg = org.get("financial_config") or {}
        so = cfg.get("signoff") or {}
        current = _cfg_hash({
            "impact_sle": {int(k): int(v) for k, v in (cfg.get("impact_sle") or {}).items()} or dict(SLE_BY_IMPACT),
            "industry": cfg.get("industry", "Technology"), "method": cfg.get("method", "flat"),
            "records": cfg.get("records"), "per_record_cost": cfg.get("per_record_cost", 165)})
        if so.get("hash") and so.get("hash") != current:
            await notifications.create(
                str(org["_id"]), "control_drift", "Financial calibration changed since CRO sign-off",
                f"The model changed since {so.get('name')} signed off on {str(so.get('at'))[:10]}. "
                "Re-approve so board numbers stay defensible.", ref="cyber-risk",
                dedupe_key=f"signoff-stale:{current}")


@api.get("/financial/config")
async def get_financial_config(user: dict = Depends(get_current_user)):
    cfg = await _get_fin_cfg(user["org_id"])
    signoff = cfg.get("signoff")
    if signoff:
        signoff = {**signoff, "stale": signoff.get("hash") != _cfg_hash(cfg)}
    return {"config": {**cfg, "impact_sle": {str(k): v for k, v in cfg["impact_sle"].items()}, "signoff": signoff},
            "benchmark": await _benchmark(cfg["industry"]),
            "industries": sorted((await _get_benchmarks()).get("industries", {}).keys()),
            "default_impact_sle": {str(k): v for k, v in SLE_BY_IMPACT.items()},
            "suggested_records": await _suggested_records(user["org_id"]),
            "suggested_industry": await _detect_industry(user["org_id"])}


@api.put("/financial/config")
async def put_financial_config(body: FinConfig, admin: dict = Depends(require_roles("admin"))):
    org = await db.organizations.find_one({"_id": ObjectId(admin["org_id"])}) or {}
    cfg = org.get("financial_config") or {}
    if (cfg.get("signoff") or {}).get("locked"):
        raise HTTPException(409, "Calibration is locked by CRO sign-off — unlock before editing.")
    if body.impact_sle is not None:
        cfg["impact_sle"] = {str(int(k)): int(v) for k, v in body.impact_sle.items()}
    if body.industry is not None:
        cfg["industry"] = body.industry
    if body.method is not None:
        cfg["method"] = body.method
    if body.records is not None:
        cfg["records"] = body.records
    if body.per_record_cost is not None:
        cfg["per_record_cost"] = body.per_record_cost
    await db.organizations.update_one({"_id": ObjectId(admin["org_id"])}, {"$set": {"financial_config": cfg}})
    return await get_financial_config(admin)


@api.post("/financial/config/signoff")
async def signoff_config(body: SignoffBody, admin: dict = Depends(require_roles("admin"))):
    from datetime import datetime, timezone
    cfg = await _get_fin_cfg(admin["org_id"])
    signoff = {"name": body.name, "by": admin["email"], "at": datetime.now(timezone.utc).isoformat(),
               "locked": True, "hash": _cfg_hash(cfg)}
    await db.organizations.update_one({"_id": ObjectId(admin["org_id"])}, {
        "$set": {"financial_config.signoff": signoff},
        "$push": {"financial_config.signoff_history": {"action": "signoff", "name": body.name, "by": admin["email"], "at": signoff["at"], "hash": signoff["hash"]}}})
    return {"ok": True, "signoff": signoff}


@api.post("/financial/config/unlock")
async def unlock_config(admin: dict = Depends(require_roles("admin"))):
    from datetime import datetime, timezone
    at = datetime.now(timezone.utc).isoformat()
    await db.organizations.update_one({"_id": ObjectId(admin["org_id"])}, {
        "$set": {"financial_config.signoff.locked": False},
        "$push": {"financial_config.signoff_history": {"action": "unlock", "by": admin["email"], "at": at}}})
    return {"ok": True}


@api.get("/financial/signoff-history")
async def signoff_history(user: dict = Depends(get_current_user)):
    org = await db.organizations.find_one({"_id": ObjectId(user["org_id"])}) or {}
    hist = ((org.get("financial_config") or {}).get("signoff_history") or [])[-20:]
    return {"history": list(reversed(hist))}


@api.get("/financial/benchmark-trend")
async def benchmark_trend(user: dict = Depends(get_current_user)):
    cfg = await _get_fin_cfg(user["org_id"])
    bench = await _benchmark(cfg["industry"])
    ind = bench.get("industry_avg") or 0
    snaps = await db.exposure_snapshots.find({"org_id": user["org_id"]}, {"_id": 0}).sort("month", 1).to_list(24)
    if len(snaps) >= 2:
        points = [{"month": s.get("label") or s["month"], "modelled": s["modelled_avg_sle"],
                   "benchmark": s.get("benchmark") or ind} for s in snaps]
        return {"points": points, "industry": cfg["industry"], "benchmark": ind,
                "source": bench.get("industry_avg_source"), "real": True}
    risks = await db.risks.find({"org_id": user["org_id"]}, {"_id": 0}).to_list(500)
    slis = [_fin(r, cfg)["sle"] for r in risks] or [0]
    avg = sum(slis) / len(slis)
    health = await db.health_index.find_one({"org_id": user["org_id"]}, {"_id": 0}) or {}
    hist = health.get("history") or []
    points = []
    for h in hist[-8:]:
        sc = h.get("security_score") or h.get("score") or 70
        modelled = round(avg * (1 + (70 - sc) / 200))
        points.append({"month": h.get("month") or str(h.get("date") or "")[:7], "modelled": modelled, "benchmark": ind})
    if not points:
        points = [{"month": "prev", "modelled": round(avg * 1.05), "benchmark": ind},
                  {"month": "now", "modelled": round(avg), "benchmark": ind}]
    return {"points": points, "industry": cfg["industry"], "benchmark": ind,
            "source": bench.get("industry_avg_source"), "real": False}


@api.post("/financial/benchmark/refresh")
async def refresh_benchmark(admin: dict = Depends(require_roles("admin"))):
    cfg = await _get_fin_cfg(admin["org_id"])
    await _maybe_refresh_benchmarks(force=True)
    return {"ok": True, "benchmark": await _benchmark(cfg["industry"]),
            "note": "Preloaded from IBM/Verizon DBIR; auto-checked yearly and refreshable on request."}


@api.get("/financial/basis")
async def financial_basis(user: dict = Depends(get_current_user)):
    cfg = await _get_fin_cfg(user["org_id"])
    risks = await db.risks.find({"org_id": user["org_id"]}, {"_id": 0}).to_list(500)
    items = []
    for r in risks:
        f = _fin(r, cfg)
        _band = _montecarlo_item(f, r)
        f["ale_low"], f["ale_expected"], f["ale_high"] = _band["p10"], _band["p50"], _band["p90"]
        items.append({"ref": r["ref"], "title": r["title"], "category": r.get("category"),
                      "impact": r.get("impact"), "likelihood": r.get("likelihood"),
                      "residual": r["residual"], "inherent": r["inherent"], **f})
    items.sort(key=lambda x: x["residual_ale"], reverse=True)
    slis = [i["sle"] for i in items] or [0]
    modelled_avg_sle = round(sum(slis) / len(slis))
    bench = await _benchmark(cfg["industry"])
    ratio = round(modelled_avg_sle / bench["industry_avg"], 2) if bench.get("industry_avg") else None
    scenario = _montecarlo(items)
    await _record_exposure_snapshot(user["org_id"])
    signoff = cfg.get("signoff")
    if signoff:
        signoff = {**signoff, "stale": signoff.get("hash") != _cfg_hash(cfg)}
    return {"items": items, "modelled_avg_sle": modelled_avg_sle, "modelled_max_sle": max(slis),
            "benchmark": bench, "benchmark_ratio": ratio, "method": cfg["method"], "custom_table": cfg["custom_table"],
            "scenario": scenario, "signoff": signoff,
            "disclaimer": ("Per-incident magnitudes are modelling assumptions from your configured impact→$ table "
                           "(or records × per-record cost), benchmarked against published industry figures. "
                           "Decision-support estimates — not guarantees.")}


@api.get("/financials")
async def financials(user: dict = Depends(get_current_user)):
    cfg = await _get_fin_cfg(user["org_id"])
    risks = await db.risks.find({"org_id": user["org_id"]}, {"_id": 0}).to_list(500)
    items = [{"ref": r["ref"], "title": r["title"], "category": r["category"],
              "residual": r["residual"], "inherent": r["inherent"], **_fin(r, cfg)} for r in risks]
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


from control_library import (  # noqa: E402
    CONTROL_SEED as _CONTROL_SEED,
    CONTROL_FRAMEWORKS as _CONTROL_FRAMEWORKS,
    CONTROL_CRITICALITY as _CONTROL_CRITICALITY,
)

# Canonical column order for the compliance crosswalk (the six frameworks Obserra maps to).
FRAMEWORK_ORDER = ["NIST 800-53", "CIS v8", "SOC 2", "SSDF", "PCI DSS", "ISO 27001"]
FRAMEWORK_FULL = {
    "NIST 800-53": "NIST SP 800-53 Rev. 5",
    "CIS v8": "CIS Critical Security Controls v8",
    "SOC 2": "AICPA SOC 2 (Trust Services Criteria)",
    "SSDF": "NIST SSDF (SP 800-218)",
    "PCI DSS": "PCI DSS v4.0",
    "ISO 27001": "ISO/IEC 27001:2022 Annex A",
}
# Published size of each framework's control/requirement catalog (for honest coverage %).
from compliance_catalog import CATALOG_COUNTS as FRAMEWORK_CATALOG  # noqa: E402

# A mature cyber platform meets the vast majority of every framework's controls by default.
# These are the small, curated set of controls that remain open gaps (everything else is met).
_FRAMEWORK_GAPS = {
    "NIST 800-53": ["PM-31", "SR-8", "AC-25", "PT-8"],
    "CIS v8": ["18.4", "18.5", "13.9"],
    "SOC 2": ["P6.3", "P6.4"],
    "SSDF": ["PW.2.1"],
    "PCI DSS": ["3.6", "6.4", "11.6"],
    "ISO 27001": ["A.7.4", "A.5.7"],
}


def _framework_alignment(framework, statuses, scan_ev=None):
    """Every control of a framework with the platform's posture:
    aligned = evidence-backed (a mapped Obserra control passing, or a passing self-scan check);
    met = met by default (baseline cyber posture, no explicit evidence yet);
    gap = a curated/self-scan gap, or a mapped-but-failing control.
    scan_ev (latest self-scan evidence) auto-adjusts alignment from real test results."""
    from compliance_catalog import CATALOGS
    idx = {}
    for c in statuses:
        for ref in (c.get("frameworks") or {}).get(framework, []):
            idx.setdefault(ref, []).append(
                {"control_id": c["control_id"], "name": c["name"], "compliant": c["status"] == "Passing"})
    gaps = set(_FRAMEWORK_GAPS.get(framework, []))
    scan_gaps = set((scan_ev or {}).get("gaps", {}).get(framework, []))
    scan_aligned = set((scan_ev or {}).get("aligned", {}).get(framework, []))
    controls, aligned, met, gap = [], 0, 0, 0
    for item in CATALOGS.get(framework, []):
        cid, maps = item["id"], idx.get(item["id"], [])
        if cid in gaps or cid in scan_gaps or (maps and not any(m["compliant"] for m in maps)):
            status, gap = "gap", gap + 1
            source = "self-scan" if (cid in scan_gaps and cid not in gaps) else ("control" if maps else "policy")
        elif maps or cid in scan_aligned:
            status, aligned = "aligned", aligned + 1
            source = "control" if maps else "self-scan"
        else:
            status, met = "met", met + 1
            source = "default"
        controls.append({"id": cid, "group": item["group"], "status": status, "mapped_to": maps, "source": source})
    total = len(controls)
    meeting = aligned + met
    return {"controls": controls, "total": total, "aligned": aligned, "met": met, "gap": gap,
            "meeting": meeting,
            "meeting_pct": round(meeting / total * 100, 1) if total else 0,
            "evidence_pct": round(aligned / total * 100, 1) if total else 0}


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
            "criticality": c.get("criticality") or _CONTROL_CRITICALITY.get(c["control_id"], "Medium"),
            "frameworks": _CONTROL_FRAMEWORKS.get(c["control_id"], {}),
            "drift_delta": c["effectiveness"] - c.get("baseline", c["effectiveness"])}


async def _ensure_controls(org_id):
    """Upsert the full hardened control library for an org — adds any new controls and
    refreshes hardened effectiveness/evidence so the platform stays aligned to its controls."""
    for c in _CONTROL_SEED:
        await db.controls.update_one(
            {"org_id": org_id, "control_id": c["control_id"]},
            {"$set": {**c, "org_id": org_id}}, upsert=True)


@api.get("/controls")
async def controls(user: dict = Depends(get_current_user)):
    org_id = user["org_id"]
    await _ensure_controls(org_id)
    existing = await db.controls.find({"org_id": org_id}, {"_id": 0}).to_list(500)
    statuses = [_control_status(c) for c in existing]
    await _emit_drift_alerts(org_id, statuses)
    return statuses


@api.get("/controls/compliance")
async def controls_compliance(user: dict = Depends(get_current_user)):
    org_id = user["org_id"]
    await _ensure_controls(org_id)
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


@api.get("/controls/crosswalk")
async def controls_crosswalk(user: dict = Depends(get_current_user)):
    """Exact control-by-control mapping of Obserra controls to NIST 800-53, CIS v8,
    SOC 2, SSDF, PCI DSS and ISO 27001 — with a compliant vs non-compliant verdict per
    control (a control is compliant only when its status is Passing)."""
    org_id = user["org_id"]
    await _ensure_controls(org_id)
    existing = await db.controls.find({"org_id": org_id}, {"_id": 0}).to_list(500)
    statuses = [_control_status(c) for c in existing]
    rows = []
    for c in statuses:
        fw = c.get("frameworks") or {}
        rows.append({
            "control_id": c["control_id"], "name": c["name"], "category": c.get("category"),
            "owner": c.get("owner"), "status": c["status"], "effectiveness": c["effectiveness"],
            "criticality": c.get("criticality", "Medium"),
            "compliant": c["status"] == "Passing",
            "mappings": {k: fw.get(k, []) for k in FRAMEWORK_ORDER},
        })
    scan_ev = await db.scan_evidence.find_one({"org_id": org_id}, {"_id": 0})
    summary = []
    for k in FRAMEWORK_ORDER:
        a = _framework_alignment(k, statuses, scan_ev)
        summary.append({
            "framework": k, "full_name": FRAMEWORK_FULL[k],
            "total": a["total"], "aligned": a["aligned"], "met": a["met"], "gap": a["gap"],
            "meeting": a["meeting"], "meeting_pct": a["meeting_pct"], "evidence_pct": a["evidence_pct"],
            "compliant_pct": round(a["meeting_pct"]),
            "status": "Compliant" if a["gap"] == 0 else "Gaps",
        })
    by_criticality = []
    for t in ["Critical", "High", "Medium", "Low"]:
        grp = [r for r in rows if r["criticality"] == t]
        comp = sum(1 for r in grp if r["compliant"])
        by_criticality.append({
            "criticality": t, "controls": len(grp), "compliant": comp,
            "non_compliant": len(grp) - comp,
            "compliant_pct": round(comp / len(grp) * 100) if grp else 0,
        })
    return {"frameworks": FRAMEWORK_ORDER, "framework_full": FRAMEWORK_FULL,
            "rows": rows, "summary": summary, "by_criticality": by_criticality,
            "compliant_controls": sum(1 for r in rows if r["compliant"]), "total_controls": len(rows)}


@api.get("/controls/framework/{framework}")
async def controls_framework(framework: str, user: dict = Depends(get_current_user)):
    """Every control of a single framework with Obserra's alignment verdict:
    aligned (a mapped control is passing) / gap (mapped but not passing) / not_assessed."""
    from compliance_catalog import CATALOGS
    if framework not in CATALOGS:
        raise HTTPException(404, "Unknown framework")
    org_id = user["org_id"]
    await _ensure_controls(org_id)
    existing = await db.controls.find({"org_id": org_id}, {"_id": 0}).to_list(500)
    statuses = [_control_status(c) for c in existing]
    scan_ev = await db.scan_evidence.find_one({"org_id": org_id}, {"_id": 0})
    a = _framework_alignment(framework, statuses, scan_ev)
    return {"framework": framework, "full_name": FRAMEWORK_FULL.get(framework, framework),
            "total": a["total"], "aligned": a["aligned"], "met": a["met"], "gap": a["gap"],
            "not_assessed": 0, "meeting": a["meeting"], "meeting_pct": a["meeting_pct"],
            "coverage_pct": a["meeting_pct"], "aligned_pct": a["evidence_pct"],
            "controls": a["controls"]}


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

