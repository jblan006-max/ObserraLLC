"""Control Intelligence — auditor-link, brief-delivery & nudge-preference endpoints.

Split out of control_intelligence.py (routes only; shared helpers stay there and are
imported here). server.py imports this module so its routes register on ci_router.
"""
import logging
import os
from datetime import datetime, timezone
from typing import Optional

from bson import ObjectId
from fastapi import Depends
from pydantic import BaseModel

from db import db
from auth import get_current_user, require_roles
from kernel import notifications
from reports import _build_pdf, _resolve_brand
from control_intelligence import (
    ci_router,
    _ensure_ci_auditor_link,
    _ci_aggregate,
    _ci_brief_markdown,
    _run_ci_brief_email,
    _brief_role_map,
    _engagement_section,
    _auditor_engagement,
)

logger = logging.getLogger(__name__)


class AuditorLinkBody(BaseModel):
    days: Optional[int] = None
    reissue: Optional[bool] = None


@ci_router.get("/auditor-link")
async def get_auditor_link(admin: dict = Depends(require_roles("admin"))):
    now = datetime.now(timezone.utc)
    doc = await db.ci_auditor_links.find_one(
        {"org_id": admin["org_id"], "revoked": {"$ne": True}, "expires_at": {"$gt": now.isoformat()}})
    if not doc:
        return {"active": False}
    base = os.environ.get("FRONTEND_URL", "").rstrip("/")
    return {"active": True, "token": doc["token"], "url": f"{base}/ci-audit/{doc['token']}",
            "expires_at": doc["expires_at"]}


@ci_router.post("/auditor-link")
async def create_auditor_link(body: AuditorLinkBody = None, admin: dict = Depends(require_roles("admin"))):
    body = body or AuditorLinkBody()
    return await _ensure_ci_auditor_link(admin["org_id"], days=body.days or 90, reissue=bool(body.reissue))


@ci_router.post("/auditor-link/revoke")
async def revoke_auditor_link(admin: dict = Depends(require_roles("admin"))):
    r = await db.ci_auditor_links.update_many(
        {"org_id": admin["org_id"], "revoked": {"$ne": True}}, {"$set": {"revoked": True}})
    return {"active": False, "revoked": r.modified_count}


@ci_router.get("/public/auditor-link/{token}")
async def public_auditor_link(token: str, who: str = ""):
    from fastapi import HTTPException
    now = datetime.now(timezone.utc)
    doc = await db.ci_auditor_links.find_one({"token": token})
    if not doc or doc.get("revoked") or doc.get("expires_at", "") <= now.isoformat():
        raise HTTPException(status_code=404, detail="This auditor link is invalid or has expired.")
    org_id = doc["org_id"]
    a = await _ci_aggregate(org_id)
    org = await db.organizations.find_one({"_id": ObjectId(org_id)}, {"name": 1})
    weak = sorted(a["statuses"], key=lambda c: c["effectiveness"])[:8]
    viewer = (who or "").strip()[:120]
    try:
        await db.ci_auditor_access.insert_one({"token": token, "org_id": org_id, "kind": "view",
                                               "who": viewer, "at": now.isoformat()})
        await _maybe_alert_auditor_access(doc, "view", viewer)
    except Exception:
        pass
    return {
        "org_name": (org or {}).get("name") or "Organization",
        "generated_at": now.isoformat(), "expires_at": doc["expires_at"],
        "health": a["health"], "coverage": a["coverage"], "total": a["total"],
        "passing": a["passing"], "avg_eff": a["avg_eff"], "avg_maturity": a["avg_maturity"],
        "frameworks": sorted(a["frameworks"], key=lambda x: -x["coverage"]),
        "weak_controls": [{"control_id": c["control_id"], "name": c["name"], "status": c["status"],
                           "effectiveness": c["effectiveness"], "criticality": c.get("criticality")}
                          for c in weak],
    }


@ci_router.post("/email-brief")
async def email_brief(admin: dict = Depends(require_roles("admin"))):
    return await _run_ci_brief_email(admin["org_id"], actor=admin["email"])


@ci_router.get("/brief/recipients")
async def brief_recipients(admin: dict = Depends(require_roles("admin"))):
    role_map = await _brief_role_map(admin["org_id"])
    board = sorted(role_map["board"])
    auditor = sorted(role_map["auditor"])
    return {"board": len(board), "auditor": len(auditor), "total": len(board) + len(auditor),
            "board_emails": board, "auditor_emails": auditor,
            "recap_recipients": sorted(set(board) | set(auditor))}


class NudgePref(BaseModel):
    muted: Optional[bool] = None
    snooze_days: Optional[int] = None


def _nudge_pref_view(u):
    u = u or {}
    now = datetime.now(timezone.utc).isoformat()
    muted = bool(u.get("ci_nudge_muted", False))
    until = u.get("ci_nudge_muted_until")
    snoozed = bool(until and until > now)
    return {"muted": muted, "muted_until": until if snoozed else None, "active": muted or snoozed}


@ci_router.get("/my-nudge-pref")
async def get_my_nudge_pref(user: dict = Depends(get_current_user)):
    u = await db.users.find_one({"org_id": user["org_id"], "email": user["email"]},
                                {"ci_nudge_muted": 1, "ci_nudge_muted_until": 1})
    return _nudge_pref_view(u)


@ci_router.put("/my-nudge-pref")
async def set_my_nudge_pref(body: NudgePref, user: dict = Depends(get_current_user)):
    from datetime import timedelta
    q = {"org_id": user["org_id"], "email": user["email"]}
    if body.snooze_days and body.snooze_days > 0:
        until = (datetime.now(timezone.utc) + timedelta(days=min(365, int(body.snooze_days)))).isoformat()
        await db.users.update_one(q, {"$set": {"ci_nudge_muted": False, "ci_nudge_muted_until": until}})
    elif body.muted:
        await db.users.update_one(q, {"$set": {"ci_nudge_muted": True, "ci_nudge_muted_until": None}})
    else:
        await db.users.update_one(q, {"$set": {"ci_nudge_muted": False, "ci_nudge_muted_until": None}})
    u = await db.users.find_one(q, {"ci_nudge_muted": 1, "ci_nudge_muted_until": 1})
    return _nudge_pref_view(u)


@ci_router.get("/public/auditor-link/{token}/brief.pdf")
async def public_auditor_brief_pdf(token: str, who: str = ""):
    from fastapi import HTTPException
    from fastapi.responses import StreamingResponse
    from agent_reports import _brand_watermark_pdf, _stamp_verified_seal
    import io
    import hashlib
    now = datetime.now(timezone.utc)
    doc = await db.ci_auditor_links.find_one({"token": token})
    if not doc or doc.get("revoked") or doc.get("expires_at", "") <= now.isoformat():
        raise HTTPException(status_code=404, detail="This auditor link is invalid or has expired.")
    org_id = doc["org_id"]
    a = await _ci_aggregate(org_id)
    org = await db.organizations.find_one({"_id": ObjectId(org_id)}, {"name": 1, "report_branding": 1})
    org_name = (org or {}).get("name") or "Organization"
    md = _ci_brief_markdown(a)
    title = "Control Intelligence Assurance Brief"
    raw = _build_pdf(md, title, cover=True, org_name=org_name, brand=_resolve_brand(org)).getvalue()
    seal = hashlib.sha256(md.encode()).hexdigest()
    auditor = (who or "").strip()[:120] or "External auditor"
    try:
        access = now.strftime("%Y-%m-%d %H:%M UTC")
        base = os.environ.get("FRONTEND_URL", "").rstrip("/")
        raw = await _brand_watermark_pdf(
            raw, org_id=org_id, room_url=f"{base}/ci-audit/{token}",
            subtext=f"Downloaded by {auditor} \u00b7 {access} \u00b7 link expires {(doc.get('expires_at') or '')[:10]}")
        raw = _stamp_verified_seal(raw, seal)
    except Exception as e:
        logger.warning(f"CI auditor PDF stamp failed: {e}")
    try:
        await db.ci_auditor_links.update_one(
            {"token": token}, {"$inc": {"downloads": 1},
                               "$set": {"last_downloaded_at": now.isoformat(), "last_downloaded_by": auditor}})
        await db.ci_auditor_access.insert_one({"token": token, "org_id": org_id, "kind": "download",
                                               "who": auditor, "at": now.isoformat()})
        await _maybe_alert_auditor_access(doc, "download", auditor)
    except Exception:
        pass
    return StreamingResponse(io.BytesIO(raw), media_type="application/pdf",
                             headers={"Content-Disposition": 'attachment; filename="obserra-control-assurance-brief.pdf"'})


@ci_router.get("/auditor-link/access")
async def auditor_link_access(limit: int = 25, admin: dict = Depends(require_roles("admin"))):
    limit = max(1, min(200, int(limit or 25)))
    rows = await db.ci_auditor_access.find({"org_id": admin["org_id"]}, {"_id": 0}).sort("at", -1).to_list(limit)
    return {"events": rows}


async def _maybe_alert_auditor_access(doc, kind, who):
    if doc.get("alerted"):
        return
    now = datetime.now(timezone.utc)
    res = await db.ci_auditor_links.update_one(
        {"token": doc["token"], "alerted": {"$ne": True}},
        {"$set": {"alerted": True, "alerted_at": now.isoformat()}})
    if res.modified_count == 0:
        return
    org_id = doc["org_id"]
    admins = await db.users.find(
        {"org_id": org_id, "role": {"$in": ["admin", "executive"]}}, {"_id": 0, "email": 1}).to_list(200)
    emails = sorted({a["email"] for a in admins if a.get("email")})
    if not emails:
        return
    org = await db.organizations.find_one({"_id": ObjectId(org_id)}, {"name": 1})
    org_name = (org or {}).get("name") or "Organization"
    label = "downloaded the assurance PDF" if kind == "download" else "opened the read-only auditor portal"
    body = (f"<div style='font:400 14px Arial;color:#1f2937;max-width:620px;margin:auto'>"
            f"<h2 style='color:#0f1e3d'>An auditor engaged your {org_name} assurance link</h2>"
            f"<p>An external auditor{(' (' + who + ')') if who else ''} just {label}.</p>"
            f"<p style='font-size:11px;color:#9ca3af'>You are notified once, on first engagement with this link. "
            f"Full open/download history is in the Defensibility tab of Control Intelligence.</p></div>")
    for em in emails:
        try:
            await notifications.send_email(em, f"Auditor engaged — {org_name} Control Intelligence", body)
        except Exception:
            pass
    try:
        org2 = await db.organizations.find_one({"_id": ObjectId(org_id)}, {"alert_channel_webhook": 1})
        wh = ((org2 or {}).get("alert_channel_webhook") or "").strip()
        chat_title = f"Auditor engaged — {org_name} Control Intelligence"
        chat_text = (f"An external auditor{(' (' + who + ')') if who else ''} {label}. "
                     f"First engagement — full open/download history is in the Defensibility tab.")
        if wh:
            from agents import _post_to_webhook
            await _post_to_webhook(wh, chat_title, chat_text)
        else:
            from self_scan import _post_chat_alert
            await _post_chat_alert(org_id, chat_title, chat_text)
    except Exception:
        pass


@ci_router.get("/brief.pdf")
async def brief_pdf(admin: dict = Depends(require_roles("admin"))):
    from fastapi.responses import StreamingResponse
    import io
    a = await _ci_aggregate(admin["org_id"])
    org = await db.organizations.find_one({"_id": ObjectId(admin["org_id"])}, {"name": 1, "report_branding": 1})
    org_name = (org or {}).get("name") or "Organization"
    md = _ci_brief_markdown(a)
    md += _engagement_section(await _auditor_engagement(admin["org_id"]))
    title = "Control Intelligence Executive Assurance Brief"
    pdf = _build_pdf(md, title, cover=True, org_name=org_name, brand=_resolve_brand(org))
    return StreamingResponse(io.BytesIO(pdf.getvalue()), media_type="application/pdf",
                             headers={"Content-Disposition": 'inline; filename="obserra-brief-preview.pdf"'})


@ci_router.get("/muted-owners")
async def muted_owners(admin: dict = Depends(require_roles("admin"))):
    now = datetime.now(timezone.utc).isoformat()
    rows = await db.users.find(
        {"org_id": admin["org_id"], "$or": [{"ci_nudge_muted": True}, {"ci_nudge_muted_until": {"$gt": now}}]},
        {"_id": 0, "name": 1, "email": 1, "ci_nudge_muted": 1, "ci_nudge_muted_until": 1}).to_list(500)
    out = []
    for u in rows:
        indefinite = bool(u.get("ci_nudge_muted"))
        out.append({"name": u.get("name") or u.get("email"), "email": u.get("email"),
                    "indefinite": indefinite, "until": None if indefinite else u.get("ci_nudge_muted_until")})
    return {"owners": out}


@ci_router.get("/auditor-link/analytics")
async def auditor_link_analytics(admin: dict = Depends(require_roles("admin"))):
    org_id = admin["org_id"]
    rows = await db.ci_auditor_access.find({"org_id": org_id}, {"_id": 0}).to_list(5000)
    links, reviewers = {}, {}
    for r in rows:
        t = r.get("token")
        if not t:
            continue
        k = r.get("kind")
        who = (r.get("who") or "").strip()
        at = r.get("at") or ""
        lk = links.setdefault(t, {"token": t, "short": t[:8], "views": 0, "downloads": 0, "last_at": "", "viewers": set()})
        if k == "view":
            lk["views"] += 1
            if who:
                lk["viewers"].add(who)
        elif k == "download":
            lk["downloads"] += 1
        if at > lk["last_at"]:
            lk["last_at"] = at
        if k == "download" and who:
            rv = reviewers.setdefault(who, {"who": who, "downloads": 0, "last_at": ""})
            rv["downloads"] += 1
            if at > rv["last_at"]:
                rv["last_at"] = at
    now = datetime.now(timezone.utc).isoformat()
    link_docs = await db.ci_auditor_links.find(
        {"org_id": org_id}, {"_id": 0, "token": 1, "revoked": 1, "expires_at": 1}).to_list(500)
    status_map = {}
    for d in link_docs:
        if d.get("revoked"):
            status_map[d["token"]] = "revoked"
        elif (d.get("expires_at") or "") <= now:
            status_map[d["token"]] = "expired"
        else:
            status_map[d["token"]] = "active"
    out_links = sorted(links.values(), key=lambda x: x["last_at"], reverse=True)
    for lk in out_links:
        lk["status"] = status_map.get(lk["token"], "unknown")
        lk["awaiting_download"] = lk["views"] > 0 and lk["downloads"] == 0
        lk["viewers"] = sorted(lk.pop("viewers", set()))
    out_reviewers = sorted(reviewers.values(), key=lambda x: (-x["downloads"], x["who"]))
    totals = {"views": sum(lk["views"] for lk in out_links),
              "downloads": sum(lk["downloads"] for lk in out_links),
              "reviewers": len(out_reviewers), "links": len(out_links),
              "awaiting_download": sum(1 for lk in out_links if lk["awaiting_download"])}
    return {"links": out_links, "reviewers": out_reviewers, "totals": totals}
