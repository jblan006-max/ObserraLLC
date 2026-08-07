"""Third-Party / Vendor Risk — the second standalone app composed on the kernel.

Composes: Asset Model (vendor inventory) · Risk Engine (scoring) · Policy Engine
· Workflow Engine (remediation) · Notification Engine · Audit Ledger · Evidence Store.
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from auth import get_current_user, require_roles, _log_audit
from db import db
from kernel import notifications, workflows

tpr_router = APIRouter(prefix="/api/vendors")

COMPOSITION = ["Asset Model", "Risk Engine", "Policy Engine", "Workflow Engine",
               "Notification Engine", "Audit Ledger", "Evidence Store"]

SEED = [
    {"ref": "VND-001", "name": "Cloudflare", "category": "CDN / Edge", "criticality": "High",
     "data_access": "None", "attestation": 96, "incidents": 0, "contract_end": "2027-03-01", "status": "active"},
    {"ref": "VND-002", "name": "Datavault Analytics", "category": "Data Processor", "criticality": "Critical",
     "data_access": "PII / Confidential", "attestation": 48, "incidents": 2, "contract_end": "2026-09-15", "status": "review"},
    {"ref": "VND-003", "name": "Zendesk", "category": "Support SaaS", "criticality": "Medium",
     "data_access": "Customer contact", "attestation": 82, "incidents": 0, "contract_end": "2026-12-01", "status": "active"},
    {"ref": "VND-004", "name": "LegacyPay Gateway", "category": "Payments", "criticality": "Critical",
     "data_access": "Cardholder data", "attestation": 61, "incidents": 1, "contract_end": "2026-07-30", "status": "review"},
]

CRIT_W = {"Critical": 40, "High": 28, "Medium": 15, "Low": 6}
DATA_W = {"Cardholder data": 30, "PII / Confidential": 28, "Customer contact": 14, "None": 0}


def _score(v):
    s = CRIT_W.get(v["criticality"], 10)
    s += DATA_W.get(v["data_access"], 12)
    s += max(0, (100 - v["attestation"])) * 0.25
    s += v["incidents"] * 8
    score = min(100, round(s))
    tier = "Critical" if score >= 75 else "High" if score >= 55 else "Medium" if score >= 35 else "Low"
    return score, tier


async def _seed(org_id):
    if await db.vendors.count_documents({"org_id": org_id}) == 0:
        docs = []
        for v in SEED:
            sc, tier = _score(v)
            docs.append({**v, "org_id": org_id, "risk_score": sc, "risk_tier": tier, "last_assessed": None})
        await db.vendors.insert_many(docs)


@tpr_router.get("")
async def list_vendors(user: dict = Depends(get_current_user)):
    await _seed(user["org_id"])
    vendors = await db.vendors.find({"org_id": user["org_id"]}, {"_id": 0}).sort("risk_score", -1).to_list(200)
    portfolio = round(sum(v["risk_score"] for v in vendors) / len(vendors)) if vendors else 0
    return {"composition": COMPOSITION, "vendors": vendors, "portfolio_risk": portfolio,
            "high_risk": sum(1 for v in vendors if v["risk_tier"] in ("High", "Critical"))}


class VendorCreate(BaseModel):
    name: str
    category: str
    criticality: str = "Medium"
    data_access: str = "None"
    attestation: int = 80
    incidents: int = 0
    contract_end: str = ""


@tpr_router.post("")
async def create_vendor(body: VendorCreate, admin: dict = Depends(require_roles("admin"))):
    existing = await db.vendors.find({"org_id": admin["org_id"]}, {"ref": 1, "_id": 0}).to_list(500)
    n = max((int(v["ref"].split("-")[1]) for v in existing if v.get("ref", "").startswith("VND-")), default=0) + 1
    v = {"ref": f"VND-{n:03d}", **body.model_dump(), "status": "review"}
    sc, tier = _score(v)
    doc = {**v, "org_id": admin["org_id"], "risk_score": sc, "risk_tier": tier, "last_assessed": None}
    await db.vendors.insert_one(doc)
    await _log_audit(admin["org_id"], admin["email"], "vendor.register", f"Registered {doc['ref']} {body.name}")
    doc.pop("_id", None)
    return doc


@tpr_router.post("/{ref}/assess")
async def assess_vendor(ref: str, admin: dict = Depends(require_roles("admin"))):
    v = await db.vendors.find_one({"org_id": admin["org_id"], "ref": ref})
    if not v:
        raise HTTPException(404, "Vendor not found")
    sc, tier = _score(v)
    await db.vendors.update_one({"_id": v["_id"]},
                                {"$set": {"risk_score": sc, "risk_tier": tier, "last_assessed": datetime.now(timezone.utc).isoformat()}})
    await _log_audit(admin["org_id"], admin["email"], "vendor.assess", f"{ref} scored {sc} ({tier})")
    if tier in ("High", "Critical"):
        await workflows.start_remediation(admin["org_id"], ref, f"Remediate vendor risk — {v['name']} ({ref})")
        await notifications.create(
            admin["org_id"], "vendor_risk", f"Vendor {ref} is {tier} risk",
            f"{v['name']} scored {sc}/100 — {v['data_access']} access, {v['attestation']}% attested, {v['incidents']} incident(s).",
            ref=ref, dedupe_key=f"vendor:{ref}:{sc}")
    return {"ref": ref, "risk_score": sc, "risk_tier": tier}
