import os
import httpx
from datetime import datetime, timezone
from bson import ObjectId

from fastapi import APIRouter, Depends, HTTPException

from auth import require_roles, get_current_user, _log_audit
from db import db

verifiers_router = APIRouter(prefix="/api/verifiers")


def _now():
    return datetime.now(timezone.utc).isoformat()


async def _get_org_m365(org_id: str):
    org = await db.organizations.find_one({"_id": ObjectId(org_id)}) or {}
    m = org.get("live_m365")
    if m and m.get("tenant_id") and m.get("client_id") and m.get("client_secret"):
        return m
    # fallback: look for a connector record
    c = await db.connectors.find_one({"org_id": org_id, "type": "identity"})
    if c and c.get("tenant_id"):
        return c
    return None


async def verify_entra_connector(org_id: str, tenant_id: str, client_id: str, client_secret: str):
    """Run deterministic checks against Microsoft Graph and return evidence dict.
    Non-destructive; requires Graph application permissions for some checks."
    evidence = {"ok": False, "details": [], "checked_at": _now()}
    try:
        async with httpx.AsyncClient(timeout=30) as c:
            tok = await c.post(f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token",
                                data={"client_id": client_id, "client_secret": client_secret,
                                      "grant_type": "client_credentials", "scope": "https://graph.microsoft.com/.default"})
            if tok.status_code != 200:
                desc = ""
                try:
                    desc = tok.json().get("error_description", "")
                except Exception:
                    pass
                evidence["details"].append({"check": "token", "ok": False, "note": f"token error {tok.status_code}: {desc}"})
                return evidence
            access = tok.json().get("access_token")
            headers = {"Authorization": f"Bearer {access}", "ConsistencyLevel": "eventual"}

            # user count
            try:
                cnt = await c.get("https://graph.microsoft.com/v1.0/users/$count", headers=headers)
                user_count = int(cnt.text) if cnt.status_code == 200 and cnt.text.strip().isdigit() else None
                evidence["details"].append({"check": "user_count", "ok": bool(user_count is not None), "value": user_count})
            except Exception as e:
                evidence["details"].append({"check": "user_count", "ok": False, "note": str(e)})

            # risky users count
            try:
                risky = await c.get("https://graph.microsoft.com/v1.0/identityProtection/riskyUsers/$count", headers=headers)
                risky_users = int(risky.text) if risky.status_code == 200 and risky.text.strip().isdigit() else None
                evidence["details"].append({"check": "risky_users", "ok": True, "value": risky_users})
            except Exception:
                evidence["details"].append({"check": "risky_users", "ok": False})

            # conditional access policies
            try:
                pol = await c.get("https://graph.microsoft.com/v1.0/identity/conditionalAccess/policies", headers=headers)
                if pol.status_code == 200:
                    data = pol.json()
                    policies = data.get("value") or []
                    evidence["details"].append({"check": "conditional_access_policies", "ok": True, "count": len(policies)})
                else:
                    evidence["details"].append({"check": "conditional_access_policies", "ok": False, "status": pol.status_code})
            except Exception as e:
                evidence["details"].append({"check": "conditional_access_policies", "ok": False, "note": str(e)})

            evidence["ok"] = True
            evidence["summary"] = {
                "user_count": user_count,
                "risky_users": risky_users,
                "conditional_policies_count": next((d.get("count") for d in evidence["details"] if d.get("check") == "conditional_access_policies"), None)
            }
    except Exception as e:
        evidence["details"].append({"check": "exception", "ok": False, "note": str(e)})
    return evidence


@verifiers_router.post("/m365/run/{connector_id}")
async def run_m365(connector_id: str, admin: dict = Depends(require_roles("admin"))):
    """Run verifier for a given connector id (org's live m365 or connector doc)."""
    # find connector in organizations by id or in connectors collection
    org_id = admin["org_id"]
    # try org live_m365
    org = await db.organizations.find_one({"_id": ObjectId(org_id)}) or {}
    m = org.get("live_m365")
    if m and (m.get("tenant_id") or m.get("client_id")):
        tenant_id = m.get("tenant_id")
        client_id = m.get("client_id")
        client_secret = m.get("client_secret")
    else:
        # connector lookup
        conn = await db.connectors.find_one({"org_id": org_id, "_id": ObjectId(connector_id)})
        if not conn:
            raise HTTPException(status_code=404, detail="Connector not found")
        tenant_id = conn.get("tenant_id")
        client_id = conn.get("client_id")
        client_secret = conn.get("client_secret")

    if not (tenant_id and client_id and client_secret):
        raise HTTPException(status_code=400, detail="M365 credentials not configured for this organization/connector")

    evidence = await verify_entra_connector(org_id, tenant_id, client_id, client_secret)
    # persist evidence
    await db.connector_evidence.insert_one({"org_id": org_id, "connector": "m365", "connector_id": connector_id, "evidence": evidence, "ts": _now()})
    await _log_audit(admin["org_id"], admin["email"], "verifier.m365.run", f"Ran M365 verifier; ok={evidence.get('ok')}")
    return {"ok": True, "evidence": evidence}
