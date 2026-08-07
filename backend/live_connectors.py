"""Live enterprise connectors — optional, credential-driven.

M365 and SSO go LIVE only when an admin provides real credentials for the org;
otherwise the app falls back to the mocked connectors. Credentials are per-org.
"""
import re
import httpx
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from bson import ObjectId

from auth import require_roles, _log_audit
from db import db

live_connectors_router = APIRouter(prefix="/api/enterprise")


def _now():
    return datetime.now(timezone.utc).isoformat()


def _mask(s):
    return (s[:4] + "…" + s[-4:]) if s and len(s) > 8 else ("set" if s else "")


async def _org(org_id):
    return await db.organizations.find_one({"_id": ObjectId(org_id)}) or {}


class M365Body(BaseModel):
    tenant_id: str
    client_id: str
    client_secret: str


class SSOBody(BaseModel):
    metadata_url: str
    entity_id: str | None = None


def _m365_public(m):
    if not m:
        return {"configured": False, "live": False}
    return {"configured": True, "live": bool(m.get("live")), "tenant_id": m.get("tenant_id"),
            "client_id_masked": _mask(m.get("client_id")), "user_count": m.get("user_count"),
            "status": m.get("status"), "checked_at": m.get("checked_at")}


def _sso_public(s):
    if not s:
        return {"configured": False, "valid": False}
    return {"configured": True, "valid": bool(s.get("valid")), "metadata_url": s.get("metadata_url"),
            "entity_id": s.get("entity_id"), "status": s.get("status"), "checked_at": s.get("checked_at")}


@live_connectors_router.get("/live")
async def get_live(admin: dict = Depends(require_roles("admin"))):
    org = await _org(admin["org_id"])
    return {"m365": _m365_public(org.get("live_m365")), "sso": _sso_public(org.get("live_sso"))}


async def _verify_m365(tenant_id, client_id, client_secret):
    async with httpx.AsyncClient(timeout=20) as c:
        tok = await c.post(
            f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token",
            data={"client_id": client_id, "client_secret": client_secret,
                  "grant_type": "client_credentials", "scope": "https://graph.microsoft.com/.default"})
        if tok.status_code != 200:
            desc = ""
            try:
                desc = tok.json().get("error_description", "")[:120]
            except Exception:
                pass
            return False, None, f"Token error {tok.status_code}: {desc}"
        access = tok.json()["access_token"]
        cnt = await c.get("https://graph.microsoft.com/v1.0/users/$count",
                          headers={"Authorization": f"Bearer {access}", "ConsistencyLevel": "eventual"})
        user_count = int(cnt.text) if cnt.status_code == 200 and cnt.text.strip().isdigit() else None
    return True, user_count, "Connected to Microsoft Graph"


@live_connectors_router.put("/live/m365")
async def put_m365(body: M365Body, admin: dict = Depends(require_roles("admin"))):
    try:
        live, user_count, status = await _verify_m365(body.tenant_id, body.client_id, body.client_secret)
    except Exception as e:
        live, user_count, status = False, None, f"Verification failed: {str(e)[:120]}"
    doc = {"tenant_id": body.tenant_id, "client_id": body.client_id, "client_secret": body.client_secret,
           "live": live, "user_count": user_count, "status": status, "checked_at": _now()}
    await db.organizations.update_one({"_id": ObjectId(admin["org_id"])}, {"$set": {"live_m365": doc}})
    await _log_audit(admin["org_id"], admin["email"], "connector.m365.configure",
                     f"M365 {'LIVE' if live else 'configured (not live)'}: {status}")
    return _m365_public(doc)


@live_connectors_router.delete("/live/m365")
async def del_m365(admin: dict = Depends(require_roles("admin"))):
    await db.organizations.update_one({"_id": ObjectId(admin["org_id"])}, {"$unset": {"live_m365": ""}})
    await _log_audit(admin["org_id"], admin["email"], "connector.m365.disconnect", "M365 live connection removed")
    return {"configured": False, "live": False}


@live_connectors_router.put("/live/sso")
async def put_sso(body: SSOBody, admin: dict = Depends(require_roles("admin"))):
    valid, status, entity_id = False, "", body.entity_id
    try:
        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as c:
            r = await c.get(body.metadata_url)
        if r.status_code == 200 and "EntityDescriptor" in r.text:
            valid = True
            status = "Metadata validated — SSO ready"
            m = re.search(r'entityID="([^"]+)"', r.text)
            if m and not entity_id:
                entity_id = m.group(1)
        else:
            status = f"Invalid metadata (HTTP {r.status_code})"
    except Exception as e:
        status = f"Fetch failed: {str(e)[:120]}"
    doc = {"metadata_url": body.metadata_url, "entity_id": entity_id, "valid": valid,
           "status": status, "checked_at": _now()}
    await db.organizations.update_one({"_id": ObjectId(admin["org_id"])}, {"$set": {"live_sso": doc}})
    await _log_audit(admin["org_id"], admin["email"], "sso.configure",
                     f"SSO {'ready' if valid else 'invalid'}: {status}")
    return _sso_public(doc)


@live_connectors_router.delete("/live/sso")
async def del_sso(admin: dict = Depends(require_roles("admin"))):
    await db.organizations.update_one({"_id": ObjectId(admin["org_id"])}, {"$unset": {"live_sso": ""}})
    await _log_audit(admin["org_id"], admin["email"], "sso.clear", "SSO configuration cleared")
    return {"configured": False, "valid": False}
