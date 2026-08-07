"""Kernel Health — real per-subsystem telemetry (records, last-run, error-rate)."""
from bson import ObjectId

from db import db


async def _count(coll, org_id):
    return await db[coll].count_documents({"org_id": org_id})


async def _latest(coll, org_id, field):
    doc = await db[coll].find_one({"org_id": org_id}, sort=[(field, -1)])
    return doc.get(field) if doc else None


async def compute_health(org_id):
    graph_nodes = 0
    try:
        from routes import _build_graph
        g = await _build_graph(org_id)
        graph_nodes = len(g.get("nodes", []))
    except Exception:
        graph_nodes = 0

    adv_total = await _count("advisor_logs", org_id)
    adv_err = await db.advisor_logs.count_documents(
        {"org_id": org_id, "response": {"$regex": "error", "$options": "i"}})
    adv_rate = round(adv_err / adv_total, 3) if adv_total else 0.0

    controls = await db.controls.find({"org_id": org_id}, {"_id": 0}).to_list(500)
    org = await db.organizations.find_one({"_id": ObjectId(org_id)}) or {}

    m = {
        "tenant": {"records": 1, "last_run": org.get("created_at"), "error_rate": 0.0},
        "identity": {"records": await _count("users", org_id), "last_run": await _latest("audit_logs", org_id, "ts"), "error_rate": 0.0},
        "asset_model": {"records": await _count("assets", org_id), "last_run": "live", "error_rate": 0.0},
        "knowledge_graph": {"records": graph_nodes, "last_run": "live", "error_rate": 0.0},
        "evidence_store": {"records": await _count("audit_logs", org_id), "last_run": await _latest("audit_logs", org_id, "ts"), "error_rate": 0.0},
        "risk_engine": {"records": await _count("risks", org_id), "last_run": "live", "error_rate": 0.0},
        "control_engine": {"records": len(controls), "last_run": "live", "error_rate": 0.0,
                           "flagged": sum(1 for c in controls if c.get("effectiveness", 100) < 55)},
        "policy_engine": {"records": await _count("policies", org_id), "last_run": "live", "error_rate": 0.0},
        "workflow_engine": {"records": await _count("workflows", org_id), "last_run": await _latest("workflows", org_id, "updated_at"), "error_rate": 0.0,
                            "active": await db.workflows.count_documents({"org_id": org_id, "status": {"$in": ["active", "open", "in_progress"]}})},
        "connector_framework": {"records": (await db.connectors.find_one({"org_id": org_id}) or {}).get("records_ingested", 0),
                                "last_run": await _latest("connectors", org_id, "last_sync"), "error_rate": 0.0},
        "ai_context_engine": {"records": adv_total, "last_run": await _latest("advisor_logs", org_id, "ts"), "error_rate": adv_rate},
        "audit_ledger": {"records": await _count("audit_logs", org_id), "last_run": await _latest("audit_logs", org_id, "ts"), "error_rate": 0.0},
        "reporting_engine": {"records": await _count("reports", org_id), "last_run": await _latest("reports", org_id, "generated_at"), "error_rate": 0.0},
        "notification_engine": {"records": await _count("notifications", org_id), "last_run": await _latest("notifications", org_id, "created_at"), "error_rate": 0.0,
                               "unread": await db.notifications.count_documents({"org_id": org_id, "read": False})},
        "obserrian_ai": {"records": adv_total, "last_run": await _latest("advisor_logs", org_id, "ts"), "error_rate": adv_rate},
    }
    for v in m.values():
        v["status"] = "degraded" if v["error_rate"] > 0.2 else ("idle" if v["records"] == 0 else "operational")
    return m
