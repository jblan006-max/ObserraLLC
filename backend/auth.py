import os
import re
import jwt
import bcrypt
import secrets
import hashlib
from pymongo import ReturnDocument
from datetime import datetime, timezone, timedelta
from bson import ObjectId
from fastapi import APIRouter, HTTPException, Request, Response, Depends

from db import db

JWT_ALGORITHM = "HS256"
auth_router = APIRouter(prefix="/api/auth")

# Owner accounts get permanent, all-access entitlements with no payment required.
OWNER_EMAILS = {e.strip().lower() for e in os.environ.get("OWNER_EMAILS", "jblan2026@gmail.com").split(",") if e.strip()}
ALL_ENTITLEMENTS = ["ai_governance", "cyber_risk", "third_party_risk", "asset_intelligence", "audit_evidence", "reporting_board", "risk_register"]


def is_owner(user: dict) -> bool:
    return bool(user) and str(user.get("email", "")).lower() in OWNER_EMAILS


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


# Password policy — NIST 800-63B / ISO 27001 A.5.17 / SOC 2 CC6.1 alignment.
PASSWORD_POLICY_MSG = "at least 15 characters and include an uppercase letter, a lowercase letter, a number and a symbol"


def validate_password_policy(pw: str):
    if (len(pw) < 15 or not re.search(r"[A-Z]", pw) or not re.search(r"[a-z]", pw)
            or not re.search(r"\d", pw) or not re.search(r"[^A-Za-z0-9]", pw)):
        raise HTTPException(status_code=400, detail=f"Password must be {PASSWORD_POLICY_MSG}.")


def get_jwt_secret() -> str:
    return os.environ["JWT_SECRET"]


def create_access_token(user_id: str, email: str) -> str:
    payload = {"sub": user_id, "email": email,
               "exp": datetime.now(timezone.utc) + timedelta(hours=12), "type": "access"}
    return jwt.encode(payload, get_jwt_secret(), algorithm=JWT_ALGORITHM)


def create_refresh_token(user_id: str) -> str:
    payload = {"sub": user_id, "exp": datetime.now(timezone.utc) + timedelta(days=7), "type": "refresh"}
    return jwt.encode(payload, get_jwt_secret(), algorithm=JWT_ALGORITHM)


def set_auth_cookies(response: Response, access: str, refresh: str):
    response.set_cookie("access_token", access, httponly=True, secure=True, samesite="none", max_age=43200, path="/")
    response.set_cookie("refresh_token", refresh, httponly=True, secure=True, samesite="none", max_age=604800, path="/")


def _public_user(user: dict) -> dict:
    user["id"] = str(user["_id"])
    user.pop("_id", None)
    user.pop("password_hash", None)
    return user


async def get_current_user(request: Request) -> dict:
    token = request.cookies.get("access_token")
    if not token:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = jwt.decode(token, get_jwt_secret(), algorithms=[JWT_ALGORITHM])
        if payload.get("type") != "access":
            raise HTTPException(status_code=401, detail="Invalid token type")
        user = await db.users.find_one({"_id": ObjectId(payload["sub"])})
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        pub = _public_user(user)
        if is_owner(pub):
            pub["role"] = "admin"
        return pub
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


def require_roles(*roles):
    async def checker(user: dict = Depends(get_current_user)):
        if user.get("role") not in roles:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return user
    return checker


def subscription_active(org: dict) -> bool:
    if not org:
        return False
    status = org.get("subscription_status")
    plan = org.get("plan")
    if plan in ("team", "enterprise") and status == "active":
        cpe = org.get("current_period_end")
        if not cpe:
            return True
        try:
            return datetime.fromisoformat(cpe) > datetime.now(timezone.utc)
        except Exception:
            return True
    if plan == "trial" or status == "trialing":
        te = org.get("trial_end")
        try:
            return bool(te) and datetime.fromisoformat(te) > datetime.now(timezone.utc)
        except Exception:
            return False
    return False


async def require_active_subscription(user: dict = Depends(get_current_user)):
    if is_owner(user):
        return user
    org = await db.organizations.find_one({"_id": ObjectId(user["org_id"])})
    if not subscription_active(org):
        raise HTTPException(status_code=402, detail="Subscription required")
    return user


from pydantic import BaseModel, EmailStr


class RegisterBody(BaseModel):
    email: EmailStr
    password: str
    name: str
    org_name: str | None = None


class LoginBody(BaseModel):
    email: EmailStr
    password: str


async def _log_audit(org_id, actor, action, detail="", target=None):
    await db.audit_logs.insert_one({
        "org_id": org_id, "actor": actor, "action": action, "detail": detail,
        "target": target,
        "ts": datetime.now(timezone.utc).isoformat(),
    })


EMERGENT_SESSION_URL = "https://demobackend.emergentagent.com/auth/v1/env/oauth/session-data"


@auth_router.post("/google/session")
async def google_session(request: Request, response: Response):
    # Emergent-managed Google OAuth: exchange session_id for profile, map to an existing
    # invited Obserra user, then issue our normal JWT session. Keeps multi-tenant clean.
    import httpx
    sid = request.headers.get("X-Session-ID")
    if not sid:
        raise HTTPException(status_code=400, detail="Missing session id")
    try:
        async with httpx.AsyncClient(timeout=20) as c:
            r = await c.get(EMERGENT_SESSION_URL, headers={"X-Session-ID": sid})
    except Exception:
        raise HTTPException(status_code=502, detail="Auth provider unreachable")
    if r.status_code != 200:
        raise HTTPException(status_code=401, detail="Google authentication failed")
    email = (r.json().get("email") or "").lower()
    user = await db.users.find_one({"email": email})
    if not user:
        raise HTTPException(status_code=403, detail="No Obserra account for this Google email. Ask your admin to invite you.")
    uid = str(user["_id"])
    set_auth_cookies(response, create_access_token(uid, email), create_refresh_token(uid))
    await _log_audit(user["org_id"], email, "auth.google_login", "Signed in with Google")
    return _public_user(user)


@auth_router.post("/register")
async def register(body: RegisterBody, response: Response):
    email = body.email.lower()
    if await db.users.find_one({"email": email}):
        raise HTTPException(status_code=400, detail="Email already registered")
    validate_password_policy(body.password)
    org = await db.organizations.insert_one({
        "name": body.org_name or f"{body.name}'s Organization",
        "plan": "trial", "subscription_status": "trialing",
        "trial_end": (datetime.now(timezone.utc) + timedelta(days=14)).isoformat(),
        "entitlements": ["risk_register", "ai_governance"],
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    org_id = str(org.inserted_id)
    doc = {
        "email": email, "password_hash": hash_password(body.password), "name": body.name,
        "role": "executive", "org_id": org_id, "created_at": datetime.now(timezone.utc).isoformat(),
    }
    res = await db.users.insert_one(doc)
    uid = str(res.inserted_id)
    from seed_data import seed_org
    await seed_org(org_id)
    await _log_audit(org_id, email, "user.register", "Account & organization created")
    access, refresh = create_access_token(uid, email), create_refresh_token(uid)
    set_auth_cookies(response, access, refresh)
    return _public_user(doc | {"_id": res.inserted_id})


@auth_router.post("/login")
async def login(body: LoginBody, request: Request, response: Response):
    email = body.email.lower()
    ident = f"{request.client.host}:{email}"
    attempt = await db.login_attempts.find_one({"identifier": ident})
    if attempt and attempt.get("count", 0) >= 5:
        locked_until = attempt.get("locked_until")
        if locked_until and datetime.fromisoformat(locked_until) > datetime.now(timezone.utc):
            raise HTTPException(status_code=429, detail="Too many attempts. Try again later.")
    user = await db.users.find_one({"email": email})
    if not user or not verify_password(body.password, user["password_hash"]):
        await db.login_attempts.update_one(
            {"identifier": ident},
            {"$inc": {"count": 1},
             "$set": {"locked_until": (datetime.now(timezone.utc) + timedelta(minutes=15)).isoformat()}},
            upsert=True)
        raise HTTPException(status_code=401, detail="Invalid email or password")
    await db.login_attempts.delete_one({"identifier": ident})
    uid = str(user["_id"])
    access, refresh = create_access_token(uid, email), create_refresh_token(uid)
    set_auth_cookies(response, access, refresh)
    await _log_audit(user.get("org_id"), email, "user.login", "Login successful")
    return _public_user(user)


@auth_router.post("/logout")
async def logout(response: Response):
    response.delete_cookie("access_token", path="/")
    response.delete_cookie("refresh_token", path="/")
    return {"ok": True}


@auth_router.get("/me")
async def me(user: dict = Depends(get_current_user)):
    return user


@auth_router.get("/providers")
async def auth_providers():
    """Which sign-in methods are configured (DB self-service config, env fallback)."""
    from sso_config import resolve_apple, resolve_oidc
    apple = bool(await resolve_apple())
    sso = bool(await resolve_oidc())
    cfg = await db.app_config.find_one({"_id": "auth_ui"}) or {}
    return {"google": True, "passwordless": True, "apple": apple, "sso": sso, "hide_social": bool(cfg.get("hide_social"))}


@auth_router.post("/refresh")
async def refresh_token(request: Request, response: Response):
    token = request.cookies.get("refresh_token")
    if not token:
        raise HTTPException(status_code=401, detail="No refresh token")
    try:
        payload = jwt.decode(token, get_jwt_secret(), algorithms=[JWT_ALGORITHM])
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=401, detail="Invalid token")
        user = await db.users.find_one({"_id": ObjectId(payload["sub"])})
        access = create_access_token(str(user["_id"]), user["email"])
        response.set_cookie("access_token", access, httponly=True, secure=True, samesite="none", max_age=43200, path="/")
        return {"ok": True}
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


def _qr_digest(v: str) -> str:
    return hashlib.sha256(v.encode()).hexdigest()


class QRApproveBody(BaseModel):
    qr_token: str


class QRPollBody(BaseModel):
    poll_token: str


@auth_router.post("/qr/start")
async def qr_start():
    qr = secrets.token_urlsafe(24)
    poll = secrets.token_urlsafe(24)
    created = datetime.now(timezone.utc)
    expires = created + timedelta(minutes=3)
    await db.qr_sessions.insert_one({
        "qrHash": _qr_digest(qr), "pollHash": _qr_digest(poll), "status": "pending",
        "approvedBy": None, "createdAt": created, "expireAt": expires,
    })
    frontend = os.environ["FRONTEND_URL"].rstrip("/")
    return {"qr_token": qr, "poll_token": poll, "expires_at": expires.isoformat(),
            "approve_url": f"{frontend}/qr-approve/{qr}"}


@auth_router.post("/qr/approve")
async def qr_approve(body: QRApproveBody, user: dict = Depends(get_current_user)):
    doc = await db.qr_sessions.find_one_and_update(
        {"qrHash": _qr_digest(body.qr_token), "status": "pending",
         "expireAt": {"$gt": datetime.now(timezone.utc)}},
        {"$set": {"status": "approved", "approvedBy": user["id"],
                  "approvedName": user.get("name"), "approvedAt": datetime.now(timezone.utc)}},
        return_document=ReturnDocument.AFTER)
    if not doc:
        raise HTTPException(status_code=410, detail="QR code expired, used, or invalid")
    return {"status": "approved"}


@auth_router.post("/qr/poll")
async def qr_poll(body: QRPollBody, response: Response):
    now = datetime.now(timezone.utc)
    doc = await db.qr_sessions.find_one_and_update(
        {"pollHash": _qr_digest(body.poll_token), "status": "approved", "expireAt": {"$gt": now}},
        {"$set": {"status": "claimed", "claimedAt": now}},
        return_document=ReturnDocument.AFTER)
    if doc:
        user = await db.users.find_one({"_id": ObjectId(doc["approvedBy"])})
        access = create_access_token(str(user["_id"]), user["email"])
        refresh = create_refresh_token(str(user["_id"]))
        set_auth_cookies(response, access, refresh)
        return {"status": "claimed", "user": _public_user(user)}
    pending = await db.qr_sessions.find_one(
        {"pollHash": _qr_digest(body.poll_token), "status": {"$in": ["pending", "approved"]},
         "expireAt": {"$gt": now}}, {"status": 1})
    if pending:
        return {"status": pending["status"]}
    raise HTTPException(status_code=410, detail="Session expired or invalid")


class InviteBody(BaseModel):
    email: EmailStr
    name: str
    role: str
    module_access: list[str] | None = None


class ChangePasswordBody(BaseModel):
    current_password: str
    new_password: str


class PreferencesBody(BaseModel):
    digest_cadence: str


CATEGORY_IDS = ["ai_governance", "cyber_risk", "third_party_risk", "asset_intelligence", "audit_evidence", "reporting_board"]

CATEGORY_NAMES = {
    "ai_governance": "AI Governance", "cyber_risk": "Cyber Risk",
    "third_party_risk": "Third-Party Risk", "asset_intelligence": "Asset Intelligence",
    "audit_evidence": "Audit & Evidence", "reporting_board": "Reporting & Board",
}


def _access_summary_text(ma):
    if ma is None:
        return "all access"
    if not ma:
        return "no categories"
    return ", ".join(CATEGORY_NAMES.get(c, c) for c in ma)


def _access_diff(old_ma, new_ma):
    all_ids = set(CATEGORY_IDS)
    old_set = all_ids if old_ma is None else set(old_ma or [])
    new_set = all_ids if new_ma is None else set(new_ma or [])
    added = [CATEGORY_NAMES[c] for c in CATEGORY_IDS if c in (new_set - old_set)]
    removed = [CATEGORY_NAMES[c] for c in CATEGORY_IDS if c in (old_set - new_set)]
    return added, removed


async def _notify_access_change(org_id, member, ma, actor, old_ma="__none__"):
    """Email the teammate (managed Resend) with an added-vs-removed diff when access changes."""
    try:
        from kernel import notifications
        summary = _access_summary_text(ma)
        frontend = os.environ["FRONTEND_URL"].rstrip("/")
        diff_html = ""
        if old_ma != "__none__":
            added, removed = _access_diff(old_ma, ma)
            rows = ""
            if added:
                rows += f'<div style="font:700 13px Arial;color:#15803d;margin-top:6px">&#43; Added: {", ".join(added)}</div>'
            if removed:
                rows += f'<div style="font:700 13px Arial;color:#b91c1c;margin-top:6px">&#8722; Removed: {", ".join(removed)}</div>'
            if not rows:
                rows = '<div style="font:400 13px Arial;color:#6b7280;margin-top:6px">No change to the packs you can reach.</div>'
            diff_html = f'<div style="margin-top:12px;padding:12px 14px;background:#f3f6fb;border-radius:8px">{rows}</div>'
        html = (
            '<table width="100%" cellpadding="0" cellspacing="0" style="max-width:560px;margin:auto;background:#ffffff">'
            '<tr><td style="padding:28px 24px">'
            '<div style="font:800 20px Arial;color:#0f1e3d">Obserra — Executive Protection &amp; Intelligence LLC</div>'
            f'<div style="font:400 14px Arial;color:#1f2937;margin-top:14px;line-height:1.6">Hi {member.get("name") or member["email"]},<br><br>'
            f'Your Obserra dashboard access was updated. You can now reach: <b>{summary}</b>.</div>'
            f'{diff_html}'
            f'<div style="margin:22px 0"><a href="{frontend}/app" style="background:#1b3a8a;color:#fff;font:700 14px Arial;text-decoration:none;padding:12px 22px;border-radius:8px">Open Obserra EIOS</a></div>'
            '</td></tr></table>'
        )
        await notifications.send_email(member["email"], "Your Obserra dashboard access changed", html)
        await notifications.create(org_id, "team", "Access updated",
                                   f"{member['email']} access changed by {actor} → {summary}", ref=member["email"])
    except Exception as e:
        import logging; logging.getLogger(__name__).error(f"access-change notify failed: {e}")


async def _org_preset(org_id, name):
    org = await db.organizations.find_one({"_id": ObjectId(org_id)}, {"access_presets": 1})
    for p in (org or {}).get("access_presets", []):
        if p["name"] == name:
            return p
    return None


class AccessBody(BaseModel):
    module_access: list[str] | None = None
    notify: bool = True
    pin: str | None = None
    expires_on: str | None = None


@auth_router.get("/team/members")
async def team_members(admin: dict = Depends(require_roles("admin"))):
    members = await db.users.find({"org_id": admin["org_id"]}).sort("created_at", 1).to_list(500)
    return [{"id": str(m["_id"]), "email": m["email"], "name": m.get("name"),
             "role": m.get("role"), "created_at": m.get("created_at"),
             "invited_by": m.get("invited_by"), "module_access": m.get("module_access"),
             "preset_pin": m.get("preset_pin"), "access_expiry": m.get("access_expiry")} for m in members]


@auth_router.post("/team/{user_id}/access")
async def set_member_access(user_id: str, body: AccessBody, admin: dict = Depends(require_roles("admin"))):
    """Grant access to categories (None=all). Optionally pin to a preset (auto-syncs) or set an expiry date."""
    member = await db.users.find_one({"_id": ObjectId(user_id), "org_id": admin["org_id"]})
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")
    old_ma = member.get("module_access")
    upd, unset = {}, {}
    if body.pin:
        preset = await _org_preset(admin["org_id"], body.pin)
        if not preset:
            raise HTTPException(status_code=400, detail="Preset not found")
        ma = preset.get("module_access")
        upd["preset_pin"] = body.pin
    else:
        ma = None if body.module_access is None else [c for c in body.module_access if c in CATEGORY_IDS]
        unset["preset_pin"] = ""
    upd["module_access"] = ma
    if body.expires_on:
        upd["access_expiry"] = body.expires_on
        upd["access_expiry_revert"] = old_ma
    else:
        unset["access_expiry"] = ""
        unset["access_expiry_revert"] = ""
    op = {"$set": upd}
    if unset:
        op["$unset"] = unset
    await db.users.update_one({"_id": ObjectId(user_id)}, op)
    extra = (f" (synced to preset '{body.pin}')" if body.pin else "") + (f" · expires {body.expires_on}" if body.expires_on else "")
    await _log_audit(admin["org_id"], admin["email"], "team.access",
                     f"Set dashboard access: {_access_summary_text(ma)}{extra}", target=member["email"])
    if body.notify:
        await _notify_access_change(admin["org_id"], member, ma, admin["email"], old_ma=old_ma)
    return {"ok": True, "module_access": ma}


class BulkAccessBody(BaseModel):
    user_ids: list[str]
    module_access: list[str] | None = None
    pin_preset: str | None = None
    notify: bool = True


@auth_router.post("/team/bulk-access")
async def bulk_set_access(body: BulkAccessBody, admin: dict = Depends(require_roles("admin"))):
    """Apply the same dashboard access (or pin the same preset) to several teammates at once."""
    pin = None
    if body.pin_preset:
        preset = await _org_preset(admin["org_id"], body.pin_preset)
        if not preset:
            raise HTTPException(status_code=400, detail="Preset not found")
        ma = preset.get("module_access")
        pin = body.pin_preset
    else:
        ma = None if body.module_access is None else [c for c in body.module_access if c in CATEGORY_IDS]
    updated = 0
    for uid in body.user_ids:
        try:
            oid = ObjectId(uid)
        except Exception:
            continue
        member = await db.users.find_one({"_id": oid, "org_id": admin["org_id"]})
        if not member:
            continue
        upd = {"module_access": ma}
        unset = {"access_expiry": "", "access_expiry_revert": ""}
        if pin:
            upd["preset_pin"] = pin
        else:
            unset["preset_pin"] = ""
        await db.users.update_one({"_id": oid}, {"$set": upd, "$unset": unset})
        await _log_audit(admin["org_id"], admin["email"], "team.access",
                         f"Bulk set access: {_access_summary_text(ma)}" + (f" (synced to '{pin}')" if pin else ""), target=member["email"])
        if body.notify:
            await _notify_access_change(admin["org_id"], member, ma, admin["email"], old_ma=member.get("module_access"))
        updated += 1
    return {"ok": True, "updated": updated, "module_access": ma}


@auth_router.get("/team/{user_id}/access-history")
async def access_history(user_id: str, admin: dict = Depends(require_roles("admin"))):
    member = await db.users.find_one({"_id": ObjectId(user_id), "org_id": admin["org_id"]})
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")
    return await db.audit_logs.find(
        {"org_id": admin["org_id"], "target": member["email"], "action": {"$in": ["team.access", "team.invite"]}},
        {"_id": 0}).sort("ts", -1).to_list(50)


class PresetBody(BaseModel):
    name: str
    module_access: list[str] | None = None


@auth_router.get("/access-presets")
async def list_access_presets(admin: dict = Depends(require_roles("admin"))):
    org = await db.organizations.find_one({"_id": ObjectId(admin["org_id"])}, {"access_presets": 1})
    return (org or {}).get("access_presets", [])


@auth_router.post("/access-presets")
async def save_access_preset(body: PresetBody, admin: dict = Depends(require_roles("admin"))):
    name = body.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Preset name required")
    ma = None if body.module_access is None else [c for c in body.module_access if c in CATEGORY_IDS]
    oid = ObjectId(admin["org_id"])
    await db.organizations.update_one({"_id": oid}, {"$pull": {"access_presets": {"name": name}}})
    await db.organizations.update_one({"_id": oid}, {"$push": {"access_presets": {"name": name, "module_access": ma}}})
    await _log_audit(admin["org_id"], admin["email"], "team.preset", f"Saved access preset '{name}'")
    # Sync pinned teammates so editing a preset auto-updates everyone on it
    pinned = await db.users.find({"org_id": admin["org_id"], "preset_pin": name}).to_list(500)
    for u in pinned:
        old = u.get("module_access")
        await db.users.update_one({"_id": u["_id"]}, {"$set": {"module_access": ma}})
        await _log_audit(admin["org_id"], admin["email"], "team.access",
                         f"Preset '{name}' sync: {_access_summary_text(ma)}", target=u["email"])
        await _notify_access_change(admin["org_id"], u, ma, admin["email"], old_ma=old)
    org = await db.organizations.find_one({"_id": oid}, {"access_presets": 1})
    return org.get("access_presets", [])


@auth_router.delete("/access-presets/{name}")
async def delete_access_preset(name: str, admin: dict = Depends(require_roles("admin"))):
    await db.organizations.update_one({"_id": ObjectId(admin["org_id"])}, {"$pull": {"access_presets": {"name": name}}})
    return {"ok": True}


@auth_router.post("/team/invite")
async def team_invite(body: InviteBody, admin: dict = Depends(require_roles("admin"))):
    email = body.email.lower()
    if body.role not in ("executive", "operational", "admin"):
        raise HTTPException(status_code=400, detail="Invalid role")
    if await db.users.find_one({"email": email}):
        raise HTTPException(status_code=400, detail="Email already registered")
    temp_password = secrets.token_urlsafe(9)
    doc = {
        "email": email, "password_hash": hash_password(temp_password), "name": body.name,
        "role": body.role, "org_id": admin["org_id"], "invited_by": admin["email"],
        "must_change_password": True, "created_at": datetime.now(timezone.utc).isoformat(),
    }
    if body.module_access is not None:
        doc["module_access"] = [c for c in body.module_access if c in CATEGORY_IDS]
    res = await db.users.insert_one(doc)
    await _log_audit(admin["org_id"], admin["email"], "team.invite", f"Invited {email} as {body.role}", target=email)
    # Kernel: start onboarding workflow + send welcome email (managed Resend)
    try:
        from kernel import workflows, notifications
        from kernel.workflow import ONBOARDING_STEPS
        await workflows.start(admin["org_id"], "onboarding", email, ONBOARDING_STEPS, first_done="invited")
        frontend = os.environ["FRONTEND_URL"].rstrip("/")
        html = _invite_email_html(body.name, email, temp_password, frontend)
        await notifications.send_email(email, "You've been invited to Obserra EIOS", html)
        await notifications.create(admin["org_id"], "team",
                                   f"{body.name} invited", f"{email} was invited as {body.role} and emailed a sign-in link.",
                                   ref=email)
    except Exception as e:
        import logging; logging.getLogger(__name__).error(f"invite side-effects failed: {e}")
    return {"id": str(res.inserted_id), "email": email, "name": body.name,
            "role": body.role, "temp_password": temp_password}


class ImportRow(BaseModel):
    name: str = ""
    email: str
    role: str = "operational"
    preset: str | None = None


class ImportBody(BaseModel):
    rows: list[ImportRow]


@auth_router.post("/team/import")
async def team_import(body: ImportBody, admin: dict = Depends(require_roles("admin"))):
    """Bulk-invite teammates from CSV rows, optionally applying a preset per row."""
    frontend = os.environ["FRONTEND_URL"].rstrip("/")
    results = []
    for row in body.rows:
        email = (row.email or "").strip().lower()
        role = row.role if row.role in ("executive", "operational", "admin") else "operational"
        if not email or "@" not in email:
            results.append({"email": row.email, "status": "invalid"}); continue
        if await db.users.find_one({"email": email}):
            results.append({"email": email, "status": "exists"}); continue
        ma, pin = None, None
        if row.preset:
            preset = await _org_preset(admin["org_id"], row.preset)
            if preset:
                ma, pin = preset.get("module_access"), row.preset
        temp_password = secrets.token_urlsafe(9)
        doc = {"email": email, "password_hash": hash_password(temp_password), "name": row.name or email,
               "role": role, "org_id": admin["org_id"], "invited_by": admin["email"],
               "must_change_password": True, "created_at": datetime.now(timezone.utc).isoformat()}
        if pin:
            doc["module_access"], doc["preset_pin"] = ma, pin
        await db.users.insert_one(doc)
        await _log_audit(admin["org_id"], admin["email"], "team.invite", f"Imported {email} as {role}", target=email)
        try:
            from kernel import notifications
            html = _invite_email_html(row.name or email, email, temp_password, frontend)
            await notifications.send_email(email, "You've been invited to Obserra EIOS", html)
        except Exception as e:
            import logging; logging.getLogger(__name__).error(f"import invite email failed: {e}")
        results.append({"email": email, "status": "invited", "temp_password": temp_password})
    return {"results": results, "invited": len([r for r in results if r["status"] == "invited"])}


def _invite_email_html(name, email, temp_password, frontend):
    return (
        '<table width="100%" cellpadding="0" cellspacing="0" style="max-width:560px;margin:auto;background:#ffffff">'
        '<tr><td style="padding:28px 24px">'
        '<div style="font:800 20px Arial;color:#0f1e3d">Obserra — Executive Protection &amp; Intelligence LLC</div>'
        f'<div style="font:400 14px Arial;color:#1f2937;margin-top:14px;line-height:1.6">Hi {name},<br><br>'
        'You have been invited to the Obserra EIOS enterprise intelligence platform. '
        'Use the button below to sign in, then set your own password on first login.</div>'
        f'<div style="margin:22px 0"><a href="{frontend}" style="background:#1b3a8a;color:#fff;font:700 14px Arial;text-decoration:none;padding:12px 22px;border-radius:8px">Sign in to Obserra EIOS</a></div>'
        f'<div style="font:400 13px Arial;color:#1f2937">Email: <b>{email}</b><br>Temporary password: '
        f'<code style="background:#f3f4f6;padding:2px 6px;border-radius:4px">{temp_password}</code></div>'
        '<div style="border-top:1px solid #e5e7eb;margin-top:20px;padding-top:10px;font:400 10px Arial;color:#9ca3af">'
        'You will be required to set a new password on first sign-in. Confidential — authorized personnel only.</div>'
        '</td></tr></table>')


@auth_router.post("/change-password")
async def change_password(body: ChangePasswordBody, request: Request, response: Response, user: dict = Depends(get_current_user)):
    record = await db.users.find_one({"_id": ObjectId(user["id"])})
    if not record or not verify_password(body.current_password, record["password_hash"]):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    validate_password_policy(body.new_password)
    await db.users.update_one({"_id": ObjectId(user["id"])},
                              {"$set": {"password_hash": hash_password(body.new_password), "must_change_password": False}})
    await _log_audit(user["org_id"], user["email"], "user.password_change", "Password updated")
    try:
        from kernel import workflows
        await workflows.advance(user["org_id"], "onboarding", user["email"], "password_set")
        await workflows.advance(user["org_id"], "onboarding", user["email"], "active")
    except Exception:
        pass
    access = create_access_token(user["id"], user["email"])
    response.set_cookie("access_token", access, httponly=True, secure=True, samesite="none", max_age=43200, path="/")
    return {"ok": True}


@auth_router.patch("/preferences")
async def update_preferences(body: PreferencesBody, user: dict = Depends(get_current_user)):
    if body.digest_cadence not in ("weekly", "daily", "off"):
        raise HTTPException(status_code=400, detail="Invalid cadence. Use weekly, daily, or off.")
    await db.users.update_one({"_id": ObjectId(user["id"])}, {"$set": {"digest_cadence": body.digest_cadence}})
    return {"ok": True, "digest_cadence": body.digest_cadence}


@auth_router.delete("/team/members/{member_id}")
async def remove_member(member_id: str, admin: dict = Depends(require_roles("admin"))):
    if member_id == admin["id"]:
        raise HTTPException(status_code=400, detail="You cannot remove yourself")
    res = await db.users.delete_one({"_id": ObjectId(member_id), "org_id": admin["org_id"]})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Member not found")
    await _log_audit(admin["org_id"], admin["email"], "team.remove", f"Removed member {member_id}")
    return {"ok": True}


async def seed_admin():
    email = os.environ["ADMIN_EMAIL"].lower()
    password = os.environ["ADMIN_PASSWORD"]
    existing = await db.users.find_one({"email": email})
    if existing is None:
        org = await db.organizations.insert_one({
            "name": "Obserra — Executive Protection & Intelligence LLC", "plan": "enterprise",
            "subscription_status": "active",
            "entitlements": ["risk_register", "ai_governance"],
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        org_id = str(org.inserted_id)
        await db.users.insert_one({
            "email": email, "password_hash": hash_password(password), "name": "James Blan",
            "role": "admin", "org_id": org_id, "created_at": datetime.now(timezone.utc).isoformat(),
        })
        # secondary operational demo user in same org
        await db.users.insert_one({
            "email": "analyst@obserra.demo", "password_hash": hash_password("Analyst2026!"),
            "name": "Dana Ops", "role": "operational", "org_id": org_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        from seed_data import seed_org
        await seed_org(org_id)
    elif not verify_password(password, existing["password_hash"]):
        await db.users.update_one({"email": email}, {"$set": {"password_hash": hash_password(password)}})
