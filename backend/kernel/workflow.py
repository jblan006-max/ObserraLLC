"""Workflow Engine — multi-step workflows (onboarding, remediation, decisions)."""
from datetime import datetime, timezone

from db import db


class WorkflowEngine:
    async def start(self, org_id, wf_type, subject, steps, first_done=None):
        now = datetime.now(timezone.utc).isoformat()
        step_docs = [{"key": k, "label": lbl, "done": (k == first_done), "at": now if k == first_done else None}
                     for k, lbl in steps]
        doc = {"org_id": org_id, "type": wf_type, "subject": subject, "steps": step_docs,
               "status": "active", "created_at": now, "updated_at": now}
        res = await db.workflows.insert_one(doc)
        return str(res.inserted_id)

    async def advance(self, org_id, wf_type, subject, step_key):
        now = datetime.now(timezone.utc).isoformat()
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


ONBOARDING_STEPS = [("invited", "Invitation sent"), ("password_set", "Password set on first login"), ("active", "Fully active")]
