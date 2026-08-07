"""Enterprise Access — governed connectors, SSO/SAML, SCIM, ABAC.

NOTE: External integrations here are MOCKED (demo-grade). No real IdP/cloud
credentials are used — 'connect'/'sync'/'provision' simulate governed behavior
so the control plane can be demonstrated end-to-end.
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from auth import get_current_user, require_roles, _log_audit
from db import db

enterprise_router = APIRouter(prefix="/api/enterprise")

CONNECTOR_CATALOG = [
    {"cid": "m365", "name": "Microsoft 365", "category": "Productivity"},
    {"cid": "azure", "name": "Microsoft Azure", "category": "Cloud"},
    {"cid": "aws", "name": "Amazon Web Services", "category": "Cloud"},
    {"cid": "okta", "name": "Okta", "category": "Identity"},
    {"cid": "crowdstrike", "name": "CrowdStrike Falcon", "category": "Endpoint"},
    {"cid": "splunk", "name": "Splunk", "category": "SIEM"},
    {"cid": "servicenow", "name": "ServiceNow", "category": "ITSM"},
    {"cid": "wiz", "name": "Wiz", "category": "CSPM"},
]


def _now():
    return datetime.now(timezone.utc).isoformat()


async def _seed_connectors(org_id):
    if await db.enterprise_connectors.count_documents({"org_id": org_id}) == 0:
        await db.enterprise_connectors.insert_many([
            {**c, "org_id": org_id, "status": "available", "records_ingested": 0, "last_sync": None}
            for c in CONNECTOR_CATALOG])


@enterprise_router.get("/connectors")
async def list_connectors(user: dict = Depends(get_current_user)):
    await _seed_connectors(user["org_id"])
    return await db.enterprise_connectors.find({"org_id": user["org_id"]}, {"_id": 0}).to_list(50)


@enterprise_router.post("/connectors/{cid}/connect")
async def connect_connector(cid: str, admin: dict = Depends(require_roles("admin"))):
    seed = 1200 + sum(ord(ch) for ch in cid) * 7
    r = await db.enterprise_connectors.update_one(
        {"org_id": admin["org_id"], "cid": cid},
        {"$set": {"status": "connected", "records_ingested": seed, "last_sync": _now()}})
    if r.matched_count == 0:
        raise HTTPException(404, "Connector not found")
    await _log_audit(admin["org_id"], admin["email"], "connector.connect", f"Connected {cid} (MOCKED)")
    return await db.enterprise_connectors.find_one({"org_id": admin["org_id"], "cid": cid}, {"_id": 0})


@enterprise_router.post("/connectors/{cid}/sync")
async def sync_connector(cid: str, admin: dict = Depends(require_roles("admin"))):
    c = await db.enterprise_connectors.find_one({"org_id": admin["org_id"], "cid": cid})
    if not c or c["status"] != "connected":
        raise HTTPException(400, "Connector not connected")
    await db.enterprise_connectors.update_one(
        {"_id": c["_id"]}, {"$inc": {"records_ingested": 137}, "$set": {"last_sync": _now()}})
    return await db.enterprise_connectors.find_one({"_id": c["_id"]}, {"_id": 0})


@enterprise_router.post("/connectors/{cid}/disconnect")
async def disconnect_connector(cid: str, admin: dict = Depends(require_roles("admin"))):
    await db.enterprise_connectors.update_one(
        {"org_id": admin["org_id"], "cid": cid},
        {"$set": {"status": "available", "records_ingested": 0, "last_sync": None}})
    await _log_audit(admin["org_id"], admin["email"], "connector.disconnect", f"Disconnected {cid}")
    return {"ok": True}


# ---------- SSO / SAML + SCIM (MOCKED config) ----------
async def _config(org_id):
    cfg = await db.enterprise_config.find_one({"org_id": org_id})
    if not cfg:
        cfg = {"org_id": org_id,
               "sso": {"enabled": False, "provider": "SAML 2.0", "entity_id": "", "sso_url": "", "certificate": ""},
               "scim": {"enabled": False, "base_url": f"/api/scim/v2/{org_id}", "token": "", "last_provisioned": 0},
               "abac": {"enforce": False}}
        await db.enterprise_config.insert_one(cfg)
    cfg.setdefault("abac", {"enforce": False})
    cfg.pop("_id", None)
    return cfg


async def abac_decision(org_id, resource, attrs):
    rules = await db.abac_rules.find({"org_id": org_id, "resource": resource}).to_list(200)
    decision, matched = "allow", None
    for r in rules:
        val = str(attrs.get(r["attribute"], ""))
        op, target = r["operator"], r["value"]
        hit = (op == "equals" and val == target) or (op == "not_equals" and val != target) \
            or (op == "in" and val in [t.strip() for t in target.split(",")])
        if hit and r["effect"] == "deny":
            return {"decision": "deny", "matched": r["rule_id"]}
        if hit and r["effect"] == "allow":
            matched = r["rule_id"]
    return {"decision": decision, "matched": matched}


async def abac_enforced(org_id):
    return (await _config(org_id)).get("abac", {}).get("enforce", False)


class SSOBody(BaseModel):
    enabled: bool
    provider: str = "SAML 2.0"
    entity_id: str = ""
    sso_url: str = ""
    certificate: str = ""


@enterprise_router.get("/config")
async def get_config(user: dict = Depends(get_current_user)):
    return await _config(user["org_id"])


@enterprise_router.put("/sso")
async def update_sso(body: SSOBody, admin: dict = Depends(require_roles("admin"))):
    await _config(admin["org_id"])
    await db.enterprise_config.update_one({"org_id": admin["org_id"]}, {"$set": {"sso": body.model_dump()}})
    await _log_audit(admin["org_id"], admin["email"], "sso.update", f"SSO {'enabled' if body.enabled else 'disabled'} (MOCKED)")
    return (await _config(admin["org_id"]))["sso"]


@enterprise_router.post("/scim/toggle")
async def toggle_scim(admin: dict = Depends(require_roles("admin"))):
    cfg = await _config(admin["org_id"])
    import secrets
    scim = cfg["scim"]
    scim["enabled"] = not scim["enabled"]
    scim["token"] = secrets.token_urlsafe(18) if scim["enabled"] else ""
    scim["last_provisioned"] = 42 if scim["enabled"] else 0
    await db.enterprise_config.update_one({"org_id": admin["org_id"]}, {"$set": {"scim": scim}})
    await _log_audit(admin["org_id"], admin["email"], "scim.toggle", f"SCIM {'enabled' if scim['enabled'] else 'disabled'} (MOCKED)")
    return scim


# ---------- ABAC ----------
class ABACRule(BaseModel):
    attribute: str
    operator: str
    value: str
    resource: str
    effect: str  # allow | deny


@enterprise_router.get("/abac")
async def list_abac(user: dict = Depends(get_current_user)):
    return await db.abac_rules.find({"org_id": user["org_id"]}, {"_id": 0}).to_list(200)


@enterprise_router.post("/abac")
async def create_abac(body: ABACRule, admin: dict = Depends(require_roles("admin"))):
    counter = await db.counters.find_one_and_update(
        {"_id": f"abac:{admin['org_id']}"}, {"$inc": {"seq": 1}}, upsert=True, return_document=True)
    doc = {"org_id": admin["org_id"], "rule_id": f"ABAC-{counter['seq']:03d}", **body.model_dump(), "created_at": _now()}
    await db.abac_rules.insert_one(doc)
    doc.pop("_id", None)
    await _log_audit(admin["org_id"], admin["email"], "abac.create", f"{doc['rule_id']}: {body.effect} {body.resource}")
    return doc


@enterprise_router.delete("/abac/{rule_id}")
async def delete_abac(rule_id: str, admin: dict = Depends(require_roles("admin"))):
    await db.abac_rules.delete_one({"org_id": admin["org_id"], "rule_id": rule_id})
    return {"ok": True}


class EnforceBody(BaseModel):
    enforce: bool


@enterprise_router.post("/abac/enforce")
async def set_enforce(body: EnforceBody, admin: dict = Depends(require_roles("admin"))):
    await _config(admin["org_id"])
    await db.enterprise_config.update_one({"org_id": admin["org_id"]}, {"$set": {"abac.enforce": body.enforce}})
    await _log_audit(admin["org_id"], admin["email"], "abac.enforce", f"ABAC enforcement {'ON' if body.enforce else 'OFF'}")
    return {"enforce": body.enforce}


class EvalBody(BaseModel):
    resource: str
    attributes: dict = {}


@enterprise_router.post("/abac/evaluate")
async def evaluate_abac(body: EvalBody, user: dict = Depends(get_current_user)):
    enforced = await abac_enforced(user["org_id"])
    d = await abac_decision(user["org_id"], body.resource, body.attributes)
    return {**d, "enforced": enforced}


@enterprise_router.get("/abac/protected-demo")
async def abac_protected_demo(user: dict = Depends(get_current_user)):
    # Demonstrates request-path enforcement: denied if an ABAC deny rule matches the caller.
    if await abac_enforced(user["org_id"]):
        d = await abac_decision(user["org_id"], "demo.resource", {"role": user.get("role"), "email": user["email"]})
        if d["decision"] == "deny":
            raise HTTPException(403, detail=f"Denied by ABAC rule {d['matched']}")
    return {"ok": True, "message": "Access granted"}
