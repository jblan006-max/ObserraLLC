"""Workflow Engine — onboarding + remediation workflows."""
from datetime import datetime, timezone, timedelta

from bson import ObjectId

from db import db

ONBOARDING_STEPS = [("invited", "Invitation sent"), ("password_set", "Password set on first login"), ("active", "Fully active")]
REMEDIATION_STEPS = [("acknowledged", "Acknowledged"), ("assigned", "Owner assigned"), ("resolved", "Resolved")]


def _now():
    return datetime.now(timezone.utc).isoformat()


class WorkflowEngine:
    async def start(self, org_id, wf_type, subject, steps, first_done=None):
        now = _now()
        step_docs = [{"key": k, "label": lbl, "done": (k == first_done), "at": now if k == first_done else None}
                     for k, lbl in steps]
        doc = {"org_id": org_id, "type": wf_type, "subject": subject, "steps": step_docs,
               "status": "active", "created_at": now, "updated_at": now}
        res = await db.workflows.insert_one(doc)
        return str(res.inserted_id)

    async def advance(self, org_id, wf_type, subject, step_key):
        now = _now()
        wf = await db.workflows.find_one({"org_id": org_id, "type": wf_type, "subject": subject, "status": "active"})
        if not wf:
            return
        steps = wf["steps"]
        for s in steps:
            if s["key"] == step_key and not s["done"]:
                s["done"] = True
                s["at"] = now
        status = "complete" if all(s["done"] for s in steps) else "active"
        await db.workflows.update_one({"_id": wf["_id"]},
                                      {"$set": {"steps": steps, "status": status, "updated_at": now}})

    async def list(self, org_id, limit=50):
        items = await db.workflows.find({"org_id": org_id}).sort("updated_at", -1).to_list(limit)
        for i in items:
            i["id"] = str(i.pop("_id"))
        return items

    async def get(self, org_id, wf_id):
        wf = await db.workflows.find_one({"_id": ObjectId(wf_id), "org_id": org_id})
        if wf:
            wf["id"] = str(wf.pop("_id"))
        return wf

    async def start_remediation(self, org_id, control_id, title, source_notification=None):
        existing = await db.workflows.find_one(
            {"org_id": org_id, "type": "remediation", "subject": control_id, "status": {"$ne": "resolved"}})
        if existing:
            existing["id"] = str(existing.pop("_id"))
            return existing
        now = _now()
        due = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
        steps = [{"key": k, "label": lbl, "done": False, "at": None} for k, lbl in REMEDIATION_STEPS]
        doc = {"org_id": org_id, "type": "remediation", "subject": control_id, "title": title,
               "steps": steps, "status": "open", "assignee": None, "notes": [], "due_at": due,
               "source_notification": source_notification, "created_at": now, "updated_at": now}
        res = await db.workflows.insert_one(doc)
        doc["id"] = str(res.inserted_id)
        doc.pop("_id", None)
        return doc

    async def act(self, org_id, wf_id, action, assignee=None, note=None):
        wf = await db.workflows.find_one({"_id": ObjectId(wf_id), "org_id": org_id})
        if not wf:
            return None
        now = _now()
        steps = wf["steps"]

        def mark(key):
            for s in steps:
                if s["key"] == key and not s["done"]:
                    s["done"] = True
                    s["at"] = now

        status = wf.get("status")
        assignee_val = wf.get("assignee")
        if action == "accept":
            mark("acknowledged")
            status = "in_progress"
        elif action == "assign":
            assignee_val = assignee or assignee_val
            mark("acknowledged")
            mark("assigned")
            status = "in_progress"
        elif action == "resolve":
            mark("acknowledged")
            mark("assigned")
            mark("resolved")
            status = "resolved"
        notes = wf.get("notes", [])
        if note:
            notes.append({"note": note, "at": now})
        await db.workflows.update_one({"_id": wf["_id"]},
                                      {"$set": {"steps": steps, "status": status, "assignee": assignee_val,
                                                "notes": notes, "updated_at": now}})
        if status == "resolved":
            await db.notifications.update_many(
                {"org_id": org_id, "kind": "control_drift", "ref": wf["subject"]},
                {"$set": {"resolved": True, "read": True}})
        updated = await db.workflows.find_one({"_id": wf["_id"]})
        updated["id"] = str(updated.pop("_id"))
        return updated
