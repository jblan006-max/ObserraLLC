"""Control Intelligence — demo auditor-journey routes (admin, labelled DEMO, reversible).

Split out of control_intelligence.py to keep the showcase logic isolated from live
evidence handling. Routes attach to the shared ci_router; server.py imports this
module so the routes register on that router.
"""
from datetime import datetime, timezone

from bson import ObjectId
from fastapi import Depends

from db import db
from auth import get_current_user, require_roles
from control_intelligence import ci_router


@ci_router.get("/auditor-link/demo/status")
async def auditor_demo_status(admin: dict = Depends(require_roles("admin"))):
    org_id = admin["org_id"]
    events = await db.ci_auditor_access.count_documents({"org_id": org_id, "demo": True})
    links = await db.ci_auditor_links.count_documents({"org_id": org_id, "demo": True})
    recaps = await db.ci_recap_log.count_documents({"org_id": org_id, "demo": True})
    return {"active": (events + links + recaps) > 0, "events": events, "links": links, "recaps": recaps}


@ci_router.get("/demo/state")
async def demo_state(user: dict = Depends(get_current_user)):
    org_id = user["org_id"]
    org = await db.organizations.find_one({"_id": ObjectId(org_id)}, {"ci_demo_active": 1})
    if (org or {}).get("ci_demo_active"):
        return {"active": True}
    events = await db.ci_auditor_access.count_documents({"org_id": org_id, "demo": True})
    return {"active": events > 0}


@ci_router.post("/auditor-link/demo/seed")
async def auditor_demo_seed(admin: dict = Depends(require_roles("admin"))):
    import uuid
    from datetime import timedelta
    org_id = admin["org_id"]
    now = datetime.now(timezone.utc)
    # idempotent: clear any prior demo rows first
    await db.ci_auditor_access.delete_many({"org_id": org_id, "demo": True})
    await db.ci_auditor_links.delete_many({"org_id": org_id, "demo": True})
    await db.ci_recap_log.delete_many({"org_id": org_id, "demo": True})

    def _link():
        return {"org_id": org_id, "token": uuid.uuid4().hex, "created_at": now.isoformat(),
                "expires_at": (now + timedelta(days=90)).isoformat(), "revoked": False,
                "demo": True, "downloads": 0}

    link_a, link_b = _link(), _link()
    await db.ci_auditor_links.insert_many([dict(link_a), dict(link_b)])

    def _acc(token, kind, who, dt):
        return {"token": token, "org_id": org_id, "kind": kind, "who": who,
                "at": dt.isoformat(), "demo": True}

    rows = [
        _acc(link_a["token"], "view", "Priya Nair \u2014 KPMG", now - timedelta(days=3, hours=5)),
        _acc(link_a["token"], "download", "Priya Nair \u2014 KPMG", now - timedelta(days=3, hours=4, minutes=56)),
        _acc(link_a["token"], "view", "Elena Rossi \u2014 EY", now - timedelta(days=1, hours=3)),
        _acc(link_a["token"], "download", "Elena Rossi \u2014 EY", now - timedelta(days=1, hours=2, minutes=58)),
        _acc(link_b["token"], "view", "Marcus Webb \u2014 Deloitte", now - timedelta(days=2, hours=6)),
        _acc(link_b["token"], "view", "Marcus Webb \u2014 Deloitte", now - timedelta(days=2, hours=5, minutes=52)),
    ]
    await db.ci_auditor_access.insert_many(rows)
    await db.ci_auditor_links.update_one(
        {"token": link_a["token"]},
        {"$set": {"downloads": 2,
                  "last_downloaded_at": (now - timedelta(days=1, hours=2, minutes=58)).isoformat(),
                  "last_downloaded_by": "Elena Rossi \u2014 EY"}})
    await db.ci_recap_log.insert_one({
        "org_id": org_id, "at": now.isoformat(), "trigger": "demo", "to": [admin.get("email")],
        "days": 7, "views": 3, "downloads": 2,
        "reviewers": ["Priya Nair \u2014 KPMG", "Elena Rossi \u2014 EY"], "awaiting": 1,
        "nudged_owners": ["Dana Ops"], "demo": True})
    # stage a readiness-nudge marker so the recap "readiness nudges this week" section lights up
    today = now.date().isoformat()
    marker = f"ci-engage-drop:{org_id}:Dana Ops:{today}"
    await db.ci_sent_markers.update_one(
        {"marker": marker}, {"$set": {"marker": marker, "at": now.isoformat(), "demo": True}}, upsert=True)
    # flag the org so the whole CI walkthrough (at-risk KPIs, remediation, header ribbon) lights up together
    await db.organizations.update_one({"_id": ObjectId(org_id)}, {"$set": {"ci_demo_active": True}})
    return {"seeded": True, "events": len(rows), "links": 2, "reviewers": 2,
            "note": "Demo auditor journey seeded (labelled DEMO). Clear it before relying on live evidence."}


@ci_router.post("/auditor-link/demo/clear")
async def auditor_demo_clear(admin: dict = Depends(require_roles("admin"))):
    org_id = admin["org_id"]
    a = await db.ci_auditor_access.delete_many({"org_id": org_id, "demo": True})
    l = await db.ci_auditor_links.delete_many({"org_id": org_id, "demo": True})
    r = await db.ci_recap_log.delete_many({"org_id": org_id, "demo": True})
    m = await db.ci_sent_markers.delete_many(
        {"demo": True, "marker": {"$regex": f"^ci-engage-drop:{org_id}:"}})
    await db.organizations.update_one({"_id": ObjectId(org_id)}, {"$set": {"ci_demo_active": False}})
    return {"cleared": True, "events": a.deleted_count, "links": l.deleted_count,
            "recaps": r.deleted_count, "markers": m.deleted_count}
