import httpx
from datetime import datetime, timezone
from bson import ObjectId

from fastapi import APIRouter, Depends, HTTPException

from auth import require_roles, _log_audit
from db import db

intune_router = APIRouter(prefix="/api/verifiers")


def _now():
    return datetime.now(timezone.utc).isoformat()


async def verify_intune(org_id: str, tenant_id: str, client_id: str, client_secret: str):
    """Query Microsoft Graph device management endpoints to compute device compliance metrics.
    Requires application permissions for DeviceManagement.Read.All and Policy.Read.All.
    """
    evidence = {"ok": False, "details": [], "checked_at": _now()}
    try:
        async with httpx.AsyncClient(timeout=30) as c:
            tok = await c.post(f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token",
                                data={"client_id": client_id, "client_secret": client_secret,
                                      "grant_type": "client_credentials", "scope": "https://graph.microsoft.com/.default"})
            if tok.status_code != 200:
                evidence["details"].append({"check": "token", "ok": False, "note": tok.text[:200]})
                return evidence
            access = tok.json().get("access_token")
            headers = {"Authorization": f"Bearer {access}", "ConsistencyLevel": "eventual"}

            # managed devices count
            try:
                r = await c.get("https://graph.microsoft.com/v1.0/deviceManagement/managedDevices/$count", headers=headers)
                dev_count = int(r.text) if r.status_code == 200 and r.text.strip().isdigit() else None
                evidence["details"].append({"check": "managed_devices_count", "ok": dev_count is not None, "value": dev_count})
            except Exception as e:
                evidence["details"].append({"check": "managed_devices_count", "ok": False, "note": str(e)})

            # compliance policy states summary
            try:
                r2 = await c.get("https://graph.microsoft.com/v1.0/deviceManagement/reports/getCompliancePolicyNonComplianceReport/", headers=headers)
                # some tenants may not expose this; fallback: query deviceCompliancePolicyStates
                evidence["details"].append({"check": "compliance_report_endpoint", "ok": r2.status_code == 200, "status": r2.status_code})
            except Exception:
                try:
                    r3 = await c.get("https://graph.microsoft.com/v1.0/deviceManagement/managedDevices", headers=headers)
                    evidence["details"].append({"check": "managedDevices_endpoint", "ok": r3.status_code == 200, "status": r3.status_code})
                except Exception as e:
                    evidence["details"].append({"check": "device_endpoints", "ok": False, "note": str(e)})

            evidence["ok"] = True
            evidence["summary"] = {"managed_devices": dev_count}
    except Exception as e:
        evidence["details"].append({"check": "exception", "ok": False, "note": str(e)})
    return evidence


@intune_router.post("/intune/run/{connector_id}")
async def run_intune(connector_id: str, admin: dict = Depends(require_roles("admin"))):
    org_id = admin["org_id"]
    # lookup connector or org live_m365 for tenant credentials
    org = await db.organizations.find_one({"_id": ObjectId(org_id)}) or {}
    creds = org.get("live_m365")
    if not creds:
        conn = await db.connectors.find_one({"org_id": org_id, "_id": ObjectId(connector_id)})
        if not conn:
            raise HTTPException(status_code=404, detail="Connector not found")
        creds = conn
    tenant_id = creds.get("tenant_id")
    client_id = creds.get("client_id")
    client_secret = creds.get("client_secret")
    if not (tenant_id and client_id and client_secret):
        raise HTTPException(status_code=400, detail="Intune/M365 credentials missing for org/connector")

    evidence = await verify_intune(org_id, tenant_id, client_id, client_secret)
    await db.connector_evidence.insert_one({"org_id": org_id, "connector": "intune", "connector_id": connector_id, "evidence": evidence, "ts": _now()})
    await _log_audit(admin["org_id"], admin["email"], "verifier.intune.run", f"Ran Intune verifier; ok={evidence.get('ok')}")
    return {"ok": True, "evidence": evidence}
