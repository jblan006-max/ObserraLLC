"""Web Push (VAPID) — home-screen / desktop push alerts for high-severity events."""
import os
import json
import base64
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import serialization
from pywebpush import webpush, WebPushException

from db import db
from auth import get_current_user

logger = logging.getLogger(__name__)
push_router = APIRouter(prefix="/api/push")
VAPID_SUBJECT = os.environ.get("VAPID_SUBJECT", "mailto:security@obserrallc.com")


async def _vapid():
    doc = await db.settings.find_one({"_id": "push_vapid"})
    if doc:
        return doc["private_pem"], doc["app_server_key"]
    priv = ec.generate_private_key(ec.SECP256R1())
    private_pem = priv.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption()).decode()
    pub = priv.public_key().public_bytes(
        serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
    app_server_key = base64.urlsafe_b64encode(pub).rstrip(b"=").decode()
    await db.settings.insert_one({"_id": "push_vapid", "private_pem": private_pem, "app_server_key": app_server_key})
    return private_pem, app_server_key


@push_router.get("/vapid-public-key")
async def vapid_public_key(user: dict = Depends(get_current_user)):
    _, key = await _vapid()
    return {"key": key}


@push_router.post("/subscribe")
async def subscribe(request: Request, user: dict = Depends(get_current_user)):
    sub = await request.json()
    ep = sub.get("endpoint")
    if not ep:
        return {"ok": False}
    await db.push_subscriptions.update_one(
        {"endpoint": ep},
        {"$set": {"endpoint": ep, "subscription": sub, "org_id": user["org_id"],
                  "user_id": user.get("id"), "email": user.get("email"),
                  "created_at": datetime.now(timezone.utc).isoformat()}}, upsert=True)
    return {"ok": True}


async def push_to_org(org_id, title, body, url="/app"):
    private_pem, _ = await _vapid()
    subs = await db.push_subscriptions.find({"org_id": org_id}).to_list(500)
    payload = json.dumps({"title": title, "body": body, "url": url})
    for s in subs:
        try:
            webpush(subscription_info=s["subscription"], data=payload,
                    vapid_private_key=private_pem, vapid_claims={"sub": VAPID_SUBJECT})
        except WebPushException as e:
            if getattr(e.response, "status_code", None) in (404, 410):
                await db.push_subscriptions.delete_one({"endpoint": s["endpoint"]})
            else:
                logger.warning(f"push failed: {e}")
        except Exception as e:
            logger.warning(f"push error: {e}")


@push_router.post("/test")
async def push_test(user: dict = Depends(get_current_user)):
    await push_to_org(user["org_id"], "Obserra alerts enabled",
                      "You'll now get a notification the instant posture drops or a critical risk opens.", "/app")
    return {"ok": True}
