import httpx
from datetime import datetime, timezone
from bson import ObjectId

from fastapi import APIRouter, Depends, HTTPException

from auth import require_roles, _log_audit
from db import db

tenable_router = APIRouter(prefix="/api/verifiers")


def _now():
    return datetime.now(timezone.utc).isoformat()


async def verify_tenable(org_id: str, access_key: str, secret_key: str):
    """Call Tenable.io API to collect vulnerability summary. Requires Tenable.io API keys.
    """
    evidence = {"ok": False, "details": [], "checked_at": _now()}
    try:
        base = "https://cloud.tenable.com"
        headers = {"X-ApiKeys": f"accessKey={access_key};secretKey={secret_key}", "Accept": "application/json"}
        async with httpx.AsyncClient(timeout=30) as c:
            r = await c.get(f"{base}/vulns/export", headers=headers)
            # Tenable permissions may block export; fall back to summarised endpoints
            if r.status_code == 200:
                evidence["details"].append({"check": "vuln_export", "ok": True})
            else:
                # query vulnerabilities summary
                s = await c.get(f"{base}/vulns/search", headers=headers)
                if s.status_code == 200:
                    data = s.json()
                    total = data.get("total", None)
                    evidence["details"].append({"check": "vulns_search", "ok": True, "total": total})
                else:
                    evidence["details"].append({"check": "vuln_query", "ok": False, "status": s.status_code})
            evidence["ok"] = True
    except Exception as e:
        evidence["details"].append({"check": "exception", "ok": False, "note": str(e)})
    return evidence


@tenable_router.post("/tenable/run/{connector_id}")
async def run_tenable(connector_id: str, admin: dict = Depends(require_roles("admin"))):
    org_id = admin["org_id"]
    conn = await db.connectors.find_one({"org_id": org_id, "_id": ObjectId(connector_id)})
    if not conn:
        raise HTTPException(status_code=404, detail="Connector not found")
    access = conn.get("access_key") or conn.get("api_key")
    secret = conn.get("secret_key") or conn.get("api_secret")
    if not (access and secret):
        raise HTTPException(status_code=400, detail="Tenable credentials missing for this connector")
    evidence = await verify_tenable(org_id, access, secret)
    await db.connector_evidence.insert_one({"org_id": org_id, "connector": "tenable", "connector_id": connector_id, "evidence": evidence, "ts": _now()})
    await _log_audit(admin["org_id"], admin["email"], "verifier.tenable.run", f"Ran Tenable verifier; ok={evidence.get('ok')}")
    return {"ok": True, "evidence": evidence}
