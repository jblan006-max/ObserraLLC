"""Notification Engine — in-app alerts + transactional email via managed Resend."""
import os
import logging
import httpx
from datetime import datetime, timezone

from db import db

logger = logging.getLogger(__name__)
EMAIL_BASE_URL = "https://integrations.emergentagent.com"


class NotificationEngine:
    async def create(self, org_id, kind, title, body, ref=None, dedupe_key=None):
        now = datetime.now(timezone.utc).isoformat()
        doc = {"org_id": org_id, "kind": kind, "title": title, "body": body,
               "ref": ref, "read": False, "created_at": now}
        if dedupe_key:
            doc["dedupe_key"] = dedupe_key
            await db.notifications.update_one(
                {"org_id": org_id, "dedupe_key": dedupe_key},
                {"$setOnInsert": doc}, upsert=True)
            return
        await db.notifications.insert_one(doc)

    async def list(self, org_id, limit=50):
        items = await db.notifications.find({"org_id": org_id}).sort("created_at", -1).to_list(limit)
        for i in items:
            i["id"] = str(i.pop("_id"))
        return items

    async def get(self, org_id, notif_id):
        from bson import ObjectId
        n = await db.notifications.find_one({"_id": ObjectId(notif_id), "org_id": org_id})
        if n:
            n["id"] = str(n.pop("_id"))
        return n

    async def unread_count(self, org_id):
        return await db.notifications.count_documents({"org_id": org_id, "read": False})

    async def mark_read(self, org_id, notif_id):
        from bson import ObjectId
        await db.notifications.update_one({"_id": ObjectId(notif_id), "org_id": org_id}, {"$set": {"read": True}})

    async def mark_all_read(self, org_id):
        await db.notifications.update_many({"org_id": org_id, "read": False}, {"$set": {"read": True}})

    async def send_email(self, to_email, subject, html):
        key = os.environ.get("EMERGENT_EMAIL_KEY")
        if not key:
            logger.warning("EMERGENT_EMAIL_KEY missing — skipping email send")
            return None
        payload = {"to": [to_email], "subject": subject, "html": html,
                   "from_name": os.environ.get("EMAIL_FROM_NAME", "Obserra EIOS")}
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(f"{EMAIL_BASE_URL}/api/v1/email/send",
                                         headers={"X-Email-Key": key}, json=payload)
            resp.raise_for_status()
            return resp.json().get("id")
        except Exception as e:
            logger.error(f"Notification email failed: {e}")
            return None
