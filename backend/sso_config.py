"""Self-service Apple + Enterprise SSO (OIDC/SAML) configuration.

Admins enter credentials in the Settings UI; they are encrypted at rest in Mongo
(app_config/_id="sso") and loaded dynamically at auth time. Environment variables
remain as a read-only fallback so nothing breaks before an admin configures it.
"""
import os
import httpx
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from db import db
from auth import require_roles, _log_audit
from security import encrypt_secret, decrypt_secret

sso_config_router = APIRouter(prefix="/api/admin/sso")
CFG_ID = "sso"

APPLE_ENV_KEYS = ("APPLE_TEAM_ID", "APPLE_SERVICE_ID", "APPLE_KEY_ID", "APPLE_PRIVATE_KEY_P8")


class AppleInput(BaseModel):
    team_id: str
    service_id: str
    key_id: str
    private_key_p8: str


class OIDCInput(BaseModel):
    discovery_url: str
    client_id: str
    client_secret: str
    issuer: str | None = None


class SSOInput(BaseModel):
    apple: AppleInput | None = None
    oidc: OIDCInput | None = None
    saml_metadata_url: str | None = None
    clear_apple: bool = False
    clear_oidc: bool = False


async def _raw() -> dict:
    return await db.app_config.find_one({"_id": CFG_ID}) or {}


def _env_apple_ready() -> bool:
    return all(os.environ.get(k) for k in APPLE_ENV_KEYS)


def _env_oidc_ready() -> bool:
    return bool(os.environ.get("OIDC_DISCOVERY_URL") and os.environ.get("OIDC_CLIENT_ID") and os.environ.get("OIDC_CLIENT_SECRET"))


async def resolve_apple() -> dict | None:
    """Decrypted Apple config from DB, else env fallback, else None."""
    a = (await _raw()).get("apple")
    if a:
        return {"team_id": a["team_id"], "service_id": a["service_id"],
                "key_id": a["key_id"], "p8": decrypt_secret(a["p8_enc"])}
    if _env_apple_ready():
        return {"team_id": os.environ["APPLE_TEAM_ID"], "service_id": os.environ["APPLE_SERVICE_ID"],
                "key_id": os.environ["APPLE_KEY_ID"], "p8": os.environ["APPLE_PRIVATE_KEY_P8"]}
    return None


async def resolve_oidc() -> dict | None:
    o = (await _raw()).get("oidc")
    if o:
        return {"client_id": o["client_id"], "client_secret": decrypt_secret(o["secret_enc"]),
                "discovery_url": o["discovery_url"]}
    if _env_oidc_ready():
        return {"client_id": os.environ["OIDC_CLIENT_ID"], "client_secret": os.environ["OIDC_CLIENT_SECRET"],
                "discovery_url": os.environ["OIDC_DISCOVERY_URL"]}
    return None


@sso_config_router.get("")
async def get_sso(admin: dict = Depends(require_roles("admin"))):
    d = await _raw()
    a = d.get("apple") or {}
    o = d.get("oidc") or {}
    return {
        "apple_configured": bool(d.get("apple")),
        "apple": {"team_id": a.get("team_id", ""), "service_id": a.get("service_id", ""), "key_id": a.get("key_id", "")},
        "oidc_configured": bool(d.get("oidc")),
        "oidc": {"discovery_url": o.get("discovery_url", ""), "client_id": o.get("client_id", ""), "issuer": o.get("issuer", "")},
        "saml_metadata_url": (d.get("saml") or {}).get("metadata_url", ""),
        "env_apple": _env_apple_ready(),
        "env_oidc": _env_oidc_ready(),
    }


@sso_config_router.put("")
async def put_sso(body: SSOInput, admin: dict = Depends(require_roles("admin"))):
    upd = {"updated_at": datetime.now(timezone.utc).isoformat(), "updated_by": admin["email"]}
    unset = {}
    if body.apple:
        a = body.apple
        upd["apple"] = {"team_id": a.team_id.strip(), "service_id": a.service_id.strip(),
                        "key_id": a.key_id.strip(), "p8_enc": encrypt_secret(a.private_key_p8.strip())}
    elif body.clear_apple:
        unset["apple"] = ""
    if body.oidc:
        o = body.oidc
        upd["oidc"] = {"discovery_url": o.discovery_url.strip(), "client_id": o.client_id.strip(),
                       "secret_enc": encrypt_secret(o.client_secret.strip()), "issuer": (o.issuer or "").strip()}
    elif body.clear_oidc:
        unset["oidc"] = ""
    if body.saml_metadata_url is not None:
        if body.saml_metadata_url.strip():
            upd["saml"] = {"metadata_url": body.saml_metadata_url.strip()}
        else:
            unset["saml"] = ""
    op = {"$set": upd}
    if unset:
        op["$unset"] = unset
    await db.app_config.update_one({"_id": CFG_ID}, op, upsert=True)
    await _log_audit(admin["org_id"], admin["email"], "sso.config", "Updated Apple / Enterprise SSO configuration")
    return {"ok": True}


class SSOTestInput(BaseModel):
    provider: str
    discovery_url: str | None = None
    apple: AppleInput | None = None


@sso_config_router.post("/test")
async def test_sso(body: SSOTestInput, admin: dict = Depends(require_roles("admin"))):
    """Validate an OIDC discovery URL or Apple key before saving, so admins catch typos instantly."""
    if body.provider == "oidc":
        url = (body.discovery_url or "").strip()
        if not url:
            saved = await resolve_oidc()
            url = saved["discovery_url"] if saved else ""
        if not url:
            raise HTTPException(status_code=400, detail="Enter a discovery URL first")
        try:
            async with httpx.AsyncClient(timeout=8) as c:
                r = await c.get(url)
                r.raise_for_status()
                meta = r.json()
        except Exception:
            return {"ok": False, "message": "Could not reach that discovery URL — check the address."}
        missing = [k for k in ("authorization_endpoint", "token_endpoint", "jwks_uri") if not meta.get(k)]
        if missing:
            return {"ok": False, "message": f"Not a valid OIDC provider (missing: {', '.join(missing)})."}
        return {"ok": True, "message": f"Valid OIDC provider · issuer {meta.get('issuer', 'unknown')}"}
    if body.provider == "apple":
        if body.apple and body.apple.private_key_p8.strip():
            a = body.apple
            cfg = {"team_id": a.team_id, "service_id": a.service_id, "key_id": a.key_id, "p8": a.private_key_p8}
        else:
            cfg = await resolve_apple()
        if not cfg or not cfg.get("p8"):
            raise HTTPException(status_code=400, detail="Enter Apple Team/Service/Key IDs and the .p8 key first")
        try:
            from social_auth import _apple_client_secret
            _apple_client_secret(cfg)
        except Exception:
            return {"ok": False, "message": "Apple key invalid — check the .p8 contents and IDs."}
        return {"ok": True, "message": "Apple configuration valid — client secret generated successfully."}
    raise HTTPException(status_code=400, detail="Unknown provider")
