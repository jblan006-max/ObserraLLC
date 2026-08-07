import os
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


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


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
        return _public_user(user)
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


async def _log_audit(org_id, actor, action, detail=""):
    await db.audit_logs.insert_one({
        "org_id": org_id, "actor": actor, "action": action, "detail": detail,
        "ts": datetime.now(timezone.utc).isoformat(),
    })


@auth_router.post("/register")
async def register(body: RegisterBody, response: Response):
    email = body.email.lower()
    if await db.users.find_one({"email": email}):
        raise HTTPException(status_code=400, detail="Email already registered")
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


class ChangePasswordBody(BaseModel):
    current_password: str
    new_password: str


class PreferencesBody(BaseModel):
    digest_cadence: str


@auth_router.get("/team/members")
async def team_members(admin: dict = Depends(require_roles("admin"))):
    members = await db.users.find({"org_id": admin["org_id"]}).sort("created_at", 1).to_list(500)
    return [{"id": str(m["_id"]), "email": m["email"], "name": m.get("name"),
             "role": m.get("role"), "created_at": m.get("created_at"),
             "invited_by": m.get("invited_by")} for m in members]


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
    res = await db.users.insert_one(doc)
    await _log_audit(admin["org_id"], admin["email"], "team.invite", f"Invited {email} as {body.role}")
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
    if len(body.new_password) < 8:
        raise HTTPException(status_code=400, detail="New password must be at least 8 characters")
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
