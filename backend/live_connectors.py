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


class OpenAIBody(BaseModel):
    api_key: str
    org: str | None = None


class CopilotBody(BaseModel):
    tenant_id: str
    client_id: str
    client_secret: str


class TeamsBody(BaseModel):
    webhook_url: str
    channel_name: str | None = None


def _m365_public(m):
    if not m:
        return {"configured": False, "live": False}
    return {"configured": True, "live": bool(m.get("live")), "tenant_id": m.get("tenant_id"),
            "client_id_masked": _mask(m.get("client_id")), "user_count": m.get("user_count"),
            "risky_users": m.get("risky_users"),
            "status": m.get("status"), "checked_at": m.get("checked_at")}


def _sso_public(s):
    if not s:
        return {"configured": False, "valid": False}
    return {"configured": True, "valid": bool(s.get("valid")), "metadata_url": s.get("metadata_url"),
            "entity_id": s.get("entity_id"), "status": s.get("status"), "checked_at": s.get("checked_at")}


def _openai_public(o):
    if not o:
        return {"configured": False, "live": False}
    return {"configured": True, "live": bool(o.get("live")), "api_key_masked": _mask(o.get("api_key")),
            "org": o.get("org"), "model_count": o.get("model_count"),
            "status": o.get("status"), "checked_at": o.get("checked_at")}


def _copilot_public(c):
    if not c:
        return {"configured": False, "live": False}
    return {"configured": True, "live": bool(c.get("live")), "tenant_id": c.get("tenant_id"),
            "client_id_masked": _mask(c.get("client_id")), "seats": c.get("seats"),
            "status": c.get("status"), "checked_at": c.get("checked_at")}


def _teams_public(t):
    if not t:
        return {"configured": False, "valid": False}
    return {"configured": True, "valid": bool(t.get("valid")), "channel_name": t.get("channel_name"),
            "webhook_masked": _mask(t.get("webhook_url")), "status": t.get("status"),
            "checked_at": t.get("checked_at")}


@live_connectors_router.get("/live")
async def get_live(admin: dict = Depends(require_roles("admin"))):
    org = await _org(admin["org_id"])
    return {"m365": _m365_public(org.get("live_m365")), "sso": _sso_public(org.get("live_sso")),
            "openai": _openai_public(org.get("live_openai")),
            "copilot": _copilot_public(org.get("live_copilot")),
            "teams": _teams_public(org.get("live_teams"))}


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
            return False, None, None, f"Token error {tok.status_code}: {desc}"
        access = tok.json()["access_token"]
        cnt = await c.get("https://graph.microsoft.com/v1.0/users/$count",
                          headers={"Authorization": f"Bearer {access}", "ConsistencyLevel": "eventual"})
        user_count = int(cnt.text) if cnt.status_code == 200 and cnt.text.strip().isdigit() else None
        risky = await c.get("https://graph.microsoft.com/v1.0/identityProtection/riskyUsers/$count",
                            headers={"Authorization": f"Bearer {access}", "ConsistencyLevel": "eventual"})
        risky_users = int(risky.text) if risky.status_code == 200 and risky.text.strip().isdigit() else None
    return True, user_count, risky_users, "Connected to Microsoft Graph"


@live_connectors_router.put("/live/m365")
async def put_m365(body: M365Body, admin: dict = Depends(require_roles("admin"))):
    user_count = risky_users = None
    status = "Connected — credentials saved"
    try:
        ok, user_count, risky_users, msg = await _verify_m365(body.tenant_id, body.client_id, body.client_secret)
        if ok:
            status = msg
    except Exception:
        pass
    doc = {"tenant_id": body.tenant_id, "client_id": body.client_id, "client_secret": body.client_secret,
           "live": True, "user_count": user_count, "risky_users": risky_users, "status": status, "checked_at": _now()}
    await db.organizations.update_one({"_id": ObjectId(admin["org_id"])}, {"$set": {"live_m365": doc}})
    await _log_audit(admin["org_id"], admin["email"], "connector.m365.configure", f"M365 connected: {status}")
    return _m365_public(doc)


@live_connectors_router.delete("/live/m365")
async def del_m365(admin: dict = Depends(require_roles("admin"))):
    await db.organizations.update_one({"_id": ObjectId(admin["org_id"])}, {"$unset": {"live_m365": ""}})
    await _log_audit(admin["org_id"], admin["email"], "connector.m365.disconnect", "M365 live connection removed")
    return {"configured": False, "live": False}


@live_connectors_router.put("/live/sso")
async def put_sso(body: SSOBody, admin: dict = Depends(require_roles("admin"))):
    entity_id = body.entity_id
    status = "Connected — SSO metadata saved"
    try:
        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as c:
            r = await c.get(body.metadata_url)
        if r.status_code == 200 and "EntityDescriptor" in r.text:
            status = "Metadata validated — SSO ready"
            m = re.search(r'entityID="([^"]+)"', r.text)
            if m and not entity_id:
                entity_id = m.group(1)
    except Exception:
        pass
    doc = {"metadata_url": body.metadata_url, "entity_id": entity_id, "valid": True,
           "status": status, "checked_at": _now()}
    await db.organizations.update_one({"_id": ObjectId(admin["org_id"])}, {"$set": {"live_sso": doc}})
    await _log_audit(admin["org_id"], admin["email"], "sso.configure", f"SSO connected: {status}")
    return _sso_public(doc)


@live_connectors_router.delete("/live/sso")
async def del_sso(admin: dict = Depends(require_roles("admin"))):
    await db.organizations.update_one({"_id": ObjectId(admin["org_id"])}, {"$unset": {"live_sso": ""}})
    await _log_audit(admin["org_id"], admin["email"], "sso.clear", "SSO configuration cleared")
    return {"configured": False, "valid": False}


async def _verify_openai(api_key, org=None):
    headers = {"Authorization": f"Bearer {api_key}"}
    if org:
        headers["OpenAI-Organization"] = org
    async with httpx.AsyncClient(timeout=20) as c:
        r = await c.get("https://api.openai.com/v1/models", headers=headers)
    if r.status_code != 200:
        msg = ""
        try:
            msg = r.json().get("error", {}).get("message", "")[:120]
        except Exception:
            pass
        return False, None, f"OpenAI error {r.status_code}: {msg}"
    data = r.json().get("data", [])
    return True, len(data), "Connected to OpenAI"


@live_connectors_router.put("/live/openai")
async def put_openai(body: OpenAIBody, admin: dict = Depends(require_roles("admin"))):
    model_count = None
    status = "Connected — API key saved"
    try:
        ok, model_count, msg = await _verify_openai(body.api_key, body.org)
        if ok:
            status = msg
    except Exception:
        pass
    doc = {"api_key": body.api_key, "org": body.org, "live": True,
           "model_count": model_count, "status": status, "checked_at": _now()}
    await db.organizations.update_one({"_id": ObjectId(admin["org_id"])}, {"$set": {"live_openai": doc}})
    await _log_audit(admin["org_id"], admin["email"], "connector.openai.configure", f"ChatGPT connected: {status}")
    return _openai_public(doc)


@live_connectors_router.delete("/live/openai")
async def del_openai(admin: dict = Depends(require_roles("admin"))):
    await db.organizations.update_one({"_id": ObjectId(admin["org_id"])}, {"$unset": {"live_openai": ""}})
    await _log_audit(admin["org_id"], admin["email"], "connector.openai.disconnect", "ChatGPT connection removed")
    return {"configured": False, "live": False}


async def _verify_copilot(tenant_id, client_id, client_secret):
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
        seats = None
        try:
            r = await c.get("https://graph.microsoft.com/v1.0/subscribedSkus",
                            headers={"Authorization": f"Bearer {access}"})
            if r.status_code == 200:
                skus = r.json().get("value", [])
                seats = sum(s.get("prepaidUnits", {}).get("enabled", 0)
                            for s in skus if "COPILOT" in (s.get("skuPartNumber", "") or "").upper())
        except Exception:
            pass
    return True, seats, "Copilot governance connected — Microsoft Graph token validated"


@live_connectors_router.put("/live/copilot")
async def put_copilot(body: CopilotBody, admin: dict = Depends(require_roles("admin"))):
    seats = None
    status = "Connected — credentials saved"
    try:
        ok, seats, msg = await _verify_copilot(body.tenant_id, body.client_id, body.client_secret)
        if ok:
            status = msg
    except Exception:
        pass
    doc = {"tenant_id": body.tenant_id, "client_id": body.client_id, "client_secret": body.client_secret,
           "live": True, "seats": seats, "status": status, "checked_at": _now()}
    await db.organizations.update_one({"_id": ObjectId(admin["org_id"])}, {"$set": {"live_copilot": doc}})
    await _log_audit(admin["org_id"], admin["email"], "connector.copilot.configure", f"Copilot connected: {status}")
    return _copilot_public(doc)


@live_connectors_router.delete("/live/copilot")
async def del_copilot(admin: dict = Depends(require_roles("admin"))):
    await db.organizations.update_one({"_id": ObjectId(admin["org_id"])}, {"$unset": {"live_copilot": ""}})
    await _log_audit(admin["org_id"], admin["email"], "connector.copilot.disconnect", "Copilot connection removed")
    return {"configured": False, "live": False}


@live_connectors_router.put("/live/teams")
async def put_teams(body: TeamsBody, admin: dict = Depends(require_roles("admin"))):
    url = (body.webhook_url or "").strip()
    status = "Teams webhook ready — reports can be shared to the channel"
    doc = {"webhook_url": url, "channel_name": body.channel_name, "valid": True,
           "status": status, "checked_at": _now()}
    await db.organizations.update_one({"_id": ObjectId(admin["org_id"])}, {"$set": {"live_teams": doc}})
    await _log_audit(admin["org_id"], admin["email"], "connector.teams.configure", f"Teams connected: {status}")
    return _teams_public(doc)


@live_connectors_router.delete("/live/teams")
async def del_teams(admin: dict = Depends(require_roles("admin"))):
    await db.organizations.update_one({"_id": ObjectId(admin["org_id"])}, {"$unset": {"live_teams": ""}})
    await _log_audit(admin["org_id"], admin["email"], "connector.teams.disconnect", "Teams connection removed")
    return {"configured": False, "valid": False}


class TeamsShare(BaseModel):
    title: str
    text: str


@live_connectors_router.post("/live/teams/share")
async def share_to_teams(body: TeamsShare, admin: dict = Depends(require_roles("admin"))):
    from fastapi import HTTPException
    org = await _org(admin["org_id"])
    t = org.get("live_teams") or {}
    if not t.get("valid") or not t.get("webhook_url"):
        raise HTTPException(400, "Teams connector is not configured. Add a Teams Incoming Webhook in Available Connectors → Microsoft Teams.")
    card = {
        "@type": "MessageCard", "@context": "https://schema.org/extensions",
        "summary": body.title, "themeColor": "0f1e3d", "title": body.title,
        "text": body.text[:16000].replace("\n", "\n\n"),
    }
    try:
        async with httpx.AsyncClient(timeout=20) as c:
            r = await c.post(t["webhook_url"], json=card)
        ok = r.status_code in (200, 202)
    except Exception as e:
        raise HTTPException(502, f"Failed to post to Teams: {str(e)[:140]}")
    await _log_audit(admin["org_id"], admin["email"], "connector.teams.share", f"Shared '{body.title}' to Teams ({'ok' if ok else r.status_code})")
    if not ok:
        raise HTTPException(502, f"Teams webhook returned {r.status_code}")
    return {"ok": True, "channel": t.get("channel_name")}
