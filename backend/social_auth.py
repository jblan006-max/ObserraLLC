"""Social / enterprise sign-in — Apple + generic enterprise OIDC (Okta/Azure/Google Workspace).

Wired end-to-end: routes exist and go LIVE automatically once the provider env vars are set.
GET /api/auth/providers reports which are configured so the UI enables the buttons.
No provider secrets ever touch the frontend; FastAPI does all token exchange/validation and
then issues the app's existing httpOnly-cookie session, matching the Google flow.
"""
import os
import time
import json
import secrets
from datetime import datetime, timezone
from urllib.parse import urlencode

import httpx
import jwt
from jwt import PyJWKClient
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import RedirectResponse

from db import db
from auth import create_access_token, create_refresh_token, set_auth_cookies, _log_audit

social_router = APIRouter(prefix="/api/auth")

FRONTEND = os.environ.get("FRONTEND_URL", "http://localhost:3000")
APP_BASE = os.environ.get("APP_BASE_URL", "")


def apple_configured():
    return all(os.environ.get(k) for k in ("APPLE_TEAM_ID", "APPLE_SERVICE_ID", "APPLE_KEY_ID", "APPLE_PRIVATE_KEY_P8"))


def oidc_configured():
    return bool(os.environ.get("OIDC_DISCOVERY_URL") and os.environ.get("OIDC_CLIENT_ID") and os.environ.get("OIDC_CLIENT_SECRET"))


async def _jit_provision(provider, email, name, subject):
    """First-time enterprise SSO user auto-joins their company org (matched by email domain)."""
    domain = email.split("@")[-1].lower()
    org = await db.organizations.find_one({"sso_domains": domain})
    if not org:
        import re as _re
        from bson import ObjectId
        peer = await db.users.find_one({"email": {"$regex": f"@{_re.escape(domain)}$"}})
        if peer:
            org = await db.organizations.find_one({"_id": ObjectId(peer["org_id"])})
    if not org:
        return None
    doc = {"email": email.lower(), "name": name or email.split("@")[0], "role": "operational",
           "org_id": str(org["_id"]), "created_at": datetime.now(timezone.utc).isoformat(),
           "provisioned_via": provider, "identities": {provider: subject} if subject else {}}
    res = await db.users.insert_one(doc)
    await _log_audit(str(org["_id"]), email.lower(), "user.jit_provision", f"Auto-provisioned via {provider} SSO")
    return await db.users.find_one({"_id": res.inserted_id})


async def _finish(provider, subject, email, name=None, jit=False):
    """Map the verified external identity to an Obserra user (JIT-provision on enterprise SSO), then issue our session."""
    user = None
    if email:
        user = await db.users.find_one({"email": email.lower()})
    if not user and subject:
        user = await db.users.find_one({f"identities.{provider}": subject})
    if not user and jit and email:
        user = await _jit_provision(provider, email, name, subject)
    if not user:
        return RedirectResponse(f"{FRONTEND}/?sso_error=no_account")
    if subject:
        await db.users.update_one({"_id": user["_id"]}, {"$set": {f"identities.{provider}": subject}})
    uid = str(user["_id"])
    resp = RedirectResponse(f"{FRONTEND}/app")
    set_auth_cookies(resp, create_access_token(uid, user["email"]), create_refresh_token(uid))
    await _log_audit(user.get("org_id"), user["email"], f"auth.{provider}_login", f"Signed in via {provider}")
    return resp


# ---------- Sign in with Apple (web) ----------
def _apple_client_secret():
    key = os.environ["APPLE_PRIVATE_KEY_P8"].replace("\\n", "\n")
    now = int(time.time())
    return jwt.encode(
        {"iss": os.environ["APPLE_TEAM_ID"], "iat": now, "exp": now + 15552000,
         "aud": "https://appleid.apple.com", "sub": os.environ["APPLE_SERVICE_ID"]},
        key, algorithm="ES256", headers={"kid": os.environ["APPLE_KEY_ID"]})


def _apple_redirect():
    return os.environ.get("APPLE_REDIRECT_URI") or f"{APP_BASE}/api/auth/apple/callback"


@social_router.get("/apple")
async def apple_start(request: Request):
    if not apple_configured():
        raise HTTPException(404, "Apple Sign In is not configured")
    state, nonce = secrets.token_urlsafe(24), secrets.token_urlsafe(24)
    request.session["apple_state"] = state
    request.session["apple_nonce"] = nonce
    q = {"response_type": "code id_token", "response_mode": "form_post",
         "client_id": os.environ["APPLE_SERVICE_ID"], "redirect_uri": _apple_redirect(),
         "scope": "name email", "state": state, "nonce": nonce}
    return RedirectResponse("https://appleid.apple.com/auth/authorize?" + urlencode(q))


@social_router.post("/apple/callback")
async def apple_callback(request: Request):
    form = await request.form()
    if not secrets.compare_digest(str(form.get("state", "")), request.session.pop("apple_state", "")):
        return RedirectResponse(f"{FRONTEND}/?sso_error=state")
    raw_id = form.get("id_token")
    if not raw_id:
        return RedirectResponse(f"{FRONTEND}/?sso_error=apple")
    try:
        signing = PyJWKClient("https://appleid.apple.com/auth/keys").get_signing_key_from_jwt(raw_id).key
        claims = jwt.decode(raw_id, signing, algorithms=["RS256"],
                            audience=os.environ["APPLE_SERVICE_ID"], issuer="https://appleid.apple.com")
    except Exception:
        return RedirectResponse(f"{FRONTEND}/?sso_error=apple_verify")
    if claims.get("nonce") != request.session.pop("apple_nonce", None):
        return RedirectResponse(f"{FRONTEND}/?sso_error=nonce")
    name = None
    try:
        name = (json.loads(form.get("user", "{}")).get("name") or {}).get("firstName")
    except Exception:
        pass
    return await _finish("apple", claims["sub"], claims.get("email"), name)


# ---------- Enterprise SSO (generic OIDC — Okta / Azure AD / Google Workspace) ----------
_oauth = None


def _get_oauth():
    global _oauth
    if _oauth is None:
        from authlib.integrations.starlette_client import OAuth
        _oauth = OAuth()
        _oauth.register(
            "sso", client_id=os.environ["OIDC_CLIENT_ID"], client_secret=os.environ["OIDC_CLIENT_SECRET"],
            server_metadata_url=os.environ["OIDC_DISCOVERY_URL"],
            client_kwargs={"scope": "openid email profile"})
    return _oauth


def _oidc_redirect():
    return os.environ.get("OIDC_REDIRECT_URI") or f"{APP_BASE}/api/auth/sso/callback"


@social_router.get("/sso")
async def sso_start(request: Request):
    if not oidc_configured():
        raise HTTPException(404, "Enterprise SSO is not configured")
    return await _get_oauth().sso.authorize_redirect(request, _oidc_redirect())


@social_router.get("/sso/callback")
async def sso_callback(request: Request):
    if not oidc_configured():
        raise HTTPException(404, "Enterprise SSO is not configured")
    try:
        token = await _get_oauth().sso.authorize_access_token(request)
    except Exception:
        return RedirectResponse(f"{FRONTEND}/?sso_error=sso")
    claims = token.get("userinfo") or {}
    return await _finish("oidc", claims.get("sub"), claims.get("email"), claims.get("name"), jit=True)
