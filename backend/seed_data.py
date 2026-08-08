from datetime import datetime, timezone, timedelta
from db import db


def _iso(days_ago=0, hours_ago=0):
    return (datetime.now(timezone.utc) - timedelta(days=days_ago, hours=hours_ago)).isoformat()


async def seed_org(org_id: str):
    """Idempotently seed rich demo data scoped to an organization."""
    from bson import ObjectId
    org = await db.organizations.find_one({"_id": ObjectId(org_id)}, {"live_only": 1})
    if org and org.get("live_only"):
        return
    if await db.risks.find_one({"org_id": org_id}):
        return

    connector = {
        "org_id": org_id, "name": "Microsoft Entra ID", "type": "identity",
        "status": "connected", "sync_mode": "MOCKED_LIVE", "last_sync": _iso(hours_ago=1),
        "records_ingested": 4821, "freshness": "live",
    }
    await db.connectors.insert_one(connector)

    risks = [
        {"ref": "CR-001", "title": "Unmanaged privileged access in Entra ID", "category": "Identity & Access",
         "inherent": 20, "residual": 12, "likelihood": 4, "impact": 5, "owner": "Dana Ops",
         "treatment": "Mitigate", "status": "Open", "kri": "Privileged accounts w/o PIM: 37",
         "source": "Microsoft Entra ID", "freshness": "live", "confidence": 0.92, "data_type": "fact",
         "business_impact": "$4.2M potential breach exposure", "trend": "up"},
        {"ref": "CR-002", "title": "Unpatched critical CVEs on internet-facing assets", "category": "Vulnerability Mgmt",
         "inherent": 25, "residual": 15, "likelihood": 5, "impact": 5, "owner": "Sam Vuln",
         "treatment": "Mitigate", "status": "In Progress", "kri": "Critical CVEs > 30d: 14",
         "source": "Tenable (mock)", "freshness": "stale", "confidence": 0.78, "data_type": "fact",
         "business_impact": "$6.8M ransomware scenario", "trend": "down"},
        {"ref": "CR-003", "title": "Third-party data processor lacks SOC 2", "category": "Third Party",
         "inherent": 16, "residual": 9, "likelihood": 3, "impact": 4, "owner": "Priya GRC",
         "treatment": "Transfer", "status": "Open", "kri": "Vendors w/o attestation: 6",
         "source": "Vendor Registry", "freshness": "live", "confidence": 0.65, "data_type": "estimate",
         "business_impact": "Regulatory + reputational", "trend": "flat"},
        {"ref": "CR-004", "title": "Shadow AI tools processing customer PII", "category": "AI Governance",
         "inherent": 20, "residual": 16, "likelihood": 4, "impact": 5, "owner": "Dana Ops",
         "treatment": "Mitigate", "status": "Open", "kri": "Unsanctioned AI apps: 9",
         "source": "CASB Discovery (mock)", "freshness": "live", "confidence": 0.71, "data_type": "estimate",
         "business_impact": "GDPR / data leakage", "trend": "up"},
        {"ref": "CR-005", "title": "Incomplete MFA coverage for remote workforce", "category": "Identity & Access",
         "inherent": 15, "residual": 6, "likelihood": 3, "impact": 4, "owner": "Dana Ops",
         "treatment": "Mitigate", "status": "Remediated", "kri": "Users w/o MFA: 112",
         "source": "Microsoft Entra ID", "freshness": "live", "confidence": 0.95, "data_type": "fact",
         "business_impact": "Account takeover risk", "trend": "down"},
        {"ref": "CR-006", "title": "Backup restoration untested for 180 days", "category": "Resilience",
         "inherent": 12, "residual": 10, "likelihood": 3, "impact": 4, "owner": "Ops Team",
         "treatment": "Accept", "status": "Open", "kri": "Days since DR test: 182",
         "source": "Ops Runbook", "freshness": "stale", "confidence": 0.6, "data_type": "estimate",
         "business_impact": "RTO uncertainty", "trend": "flat"},
    ]
    for r in risks:
        r["org_id"] = org_id
        r["created_at"] = _iso(days_ago=20)
        r["updated_at"] = _iso(days_ago=2)
    await db.risks.insert_many(risks)

    health_components = [
        {"name": "Identity & Access", "score": 74, "weight": 0.25, "trend": "up", "confidence": 0.9},
        {"name": "Vulnerability Mgmt", "score": 58, "weight": 0.2, "trend": "down", "confidence": 0.82},
        {"name": "Data Protection", "score": 81, "weight": 0.2, "trend": "flat", "confidence": 0.88},
        {"name": "AI Governance", "score": 63, "weight": 0.15, "trend": "up", "confidence": 0.7},
        {"name": "Resilience", "score": 69, "weight": 0.1, "trend": "flat", "confidence": 0.75},
        {"name": "Third Party", "score": 66, "weight": 0.1, "trend": "up", "confidence": 0.68},
    ]
    await db.health_index.insert_one({
        "org_id": org_id, "score": 69, "grade": "B-", "components": health_components,
        "computed_at": _iso(hours_ago=1), "freshness": "live",
        "history": [{"month": m, "score": s} for m, s in
                    [("Jan", 61), ("Feb", 63), ("Mar", 60), ("Apr", 65), ("May", 67), ("Jun", 69)]],
    })

    ai_systems = [
        {"ref": "AI-001", "name": "Customer Support Copilot", "type": "GenAI Assistant", "provider": "OpenAI GPT-5.6",
         "status": "sanctioned", "risk_class": "High", "nist_profile": "GenAI Profile",
         "use_case": "Customer support response drafting", "owner": "Support Eng",
         "eval": {"bias": 82, "safety": 88, "security": 79, "explainability": 71},
         "drift": "stable", "hallucination_rate": 3.2, "data_type": "fact", "confidence": 0.86, "freshness": "live"},
        {"ref": "AI-002", "name": "Credit Decisioning Model", "type": "ML Model", "provider": "In-house XGBoost",
         "status": "sanctioned", "risk_class": "Critical", "nist_profile": "NIST AI RMF",
         "use_case": "Loan approval scoring", "owner": "Data Science",
         "eval": {"bias": 64, "safety": 90, "security": 85, "explainability": 58},
         "drift": "warning", "hallucination_rate": 0.0, "data_type": "fact", "confidence": 0.79, "freshness": "live"},
        {"ref": "AI-003", "name": "Unknown Marketing GPT", "type": "Shadow AI", "provider": "Unknown SaaS",
         "status": "shadow", "risk_class": "High", "nist_profile": "Unmapped",
         "use_case": "Content generation (undocumented)", "owner": "Unassigned",
         "eval": {"bias": 0, "safety": 0, "security": 0, "explainability": 0},
         "drift": "unknown", "hallucination_rate": None, "data_type": "estimate", "confidence": 0.45, "freshness": "live"},
        {"ref": "AI-004", "name": "Doc Intelligence Agent", "type": "Agentic", "provider": "Claude Sonnet 5",
         "status": "sanctioned", "risk_class": "Medium", "nist_profile": "GenAI Profile",
         "use_case": "Contract clause extraction", "owner": "Legal Ops",
         "eval": {"bias": 86, "safety": 91, "security": 88, "explainability": 80},
         "drift": "stable", "hallucination_rate": 1.1, "data_type": "fact", "confidence": 0.9, "freshness": "live"},
    ]
    for a in ai_systems:
        a["org_id"] = org_id
        a["created_at"] = _iso(days_ago=30)
    await db.ai_systems.insert_many(ai_systems)

    incidents = [
        {"ref": "AII-001", "title": "Credit model bias drift beyond threshold", "severity": "High",
         "system": "Credit Decisioning Model", "status": "Investigating", "mode": "warn",
         "opened": _iso(days_ago=3), "org_id": org_id, "confidence": 0.8},
        {"ref": "AII-002", "title": "Shadow AI tool detected processing PII", "severity": "Critical",
         "system": "Unknown Marketing GPT", "status": "Contained", "mode": "block",
         "opened": _iso(days_ago=1), "org_id": org_id, "confidence": 0.72},
    ]
    await db.ai_incidents.insert_many(incidents)

    recommendations = [
        {"ref": "REC-001", "org_id": org_id, "title": "Enforce PIM for all privileged Entra roles",
         "risk_ref": "CR-001", "confidence": 0.88, "predicted_impact": "-8 residual points, $3.1M exposure reduction",
         "required_authority": "CISO", "evidence": ["Entra ID role assignments", "37 standing privileged accounts"],
         "data_type": "ai_recommendation", "status": "Pending", "freshness": "live"},
        {"ref": "REC-002", "org_id": org_id, "title": "Quarantine and assess shadow AI tools",
         "risk_ref": "CR-004", "confidence": 0.74, "predicted_impact": "Eliminate 9 unsanctioned PII flows",
         "required_authority": "AI Governance Board", "evidence": ["CASB discovery logs", "9 unsanctioned apps"],
         "data_type": "ai_recommendation", "status": "Pending", "freshness": "live"},
    ]
    await db.recommendations.insert_many(recommendations)

    decisions = [
        {"ref": "DEC-001", "org_id": org_id, "title": "Adopt PIM rollout for privileged access",
         "options": ["Full PIM rollout", "Phased rollout", "Accept risk"], "chosen": "Phased rollout",
         "rationale": "Balances risk reduction with operational disruption", "approver": "CISO",
         "status": "Approved", "outcome": "Phase 1 complete — 22/37 accounts migrated",
         "linked_rec": "REC-001", "decided_at": _iso(days_ago=5)},
    ]
    await db.decisions.insert_many(decisions)

    await db.audit_logs.insert_one({
        "org_id": org_id, "actor": "system", "action": "org.seeded",
        "detail": "Demo dataset provisioned (Entra ID connector, 6 risks, 4 AI systems)",
        "ts": _iso(hours_ago=1),
    })
