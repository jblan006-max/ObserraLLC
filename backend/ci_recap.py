"""Control Intelligence — engagement follow-ups, weekly assurance recap & reviewer timeline.

Split out of control_intelligence.py (routes + their private helpers). Shared aggregate/
brief helpers stay in control_intelligence.py and are imported here. server.py imports this
module so its routes register on ci_router; scheduled.py imports the _run_* crons from here.
"""
import logging
import os
import base64
import app_meta
from datetime import datetime, timezone

from bson import ObjectId
from fastapi import Depends
from pydantic import BaseModel

from db import db
from auth import get_current_user, require_roles
from kernel import notifications
from reports import _build_pdf, _resolve_brand
from control_intelligence import (
    ci_router,
    _auditor_engagement,
    _brief_role_map,
    _muted_emails,
    _owner_email_map,
    _ci_aggregate,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------- engagement follow-ups

def _ci_link_url(token):
    base = os.environ.get("FRONTEND_URL", "").rstrip("/")
    return f"{base}/ci-audit/{token}"


class FollowUpBody(BaseModel):
    token: str


@ci_router.post("/auditor-link/follow-up")
async def auditor_link_follow_up(body: FollowUpBody, admin: dict = Depends(require_roles("admin"))):
    from fastapi import HTTPException
    org_id = admin["org_id"]
    doc = await db.ci_auditor_links.find_one({"token": body.token, "org_id": org_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Auditor link not found.")
    role_map = await _brief_role_map(org_id)
    recipients = sorted(role_map["auditor"])
    if not recipients:
        return {"sent": 0, "to": [],
                "note": "No auditor-role recipients configured. Add one in the brief settings to enable follow-ups."}
    org = await db.organizations.find_one({"_id": ObjectId(org_id)}, {"name": 1})
    org_name = (org or {}).get("name") or "Organization"
    url = _ci_link_url(body.token)
    html = (f"<div style='font:400 14px Arial;color:#1f2937;max-width:620px;margin:auto'>"
            f"<h2 style='color:#0f1e3d'>A quick follow-up on your {org_name} assurance review</h2>"
            f"<p>Our records show the read-only assurance portal was opened but the signed evidence PDF "
            f"hasn't been downloaded yet. When you have a moment, please pull the sealed brief for your file:</p>"
            f"<p><a href='{url}' style='color:#12b4d6'>{url}</a></p>"
            f"<p style='font-size:11px;color:#9ca3af'>Obserra Control Intelligence \u2014 auditor follow-up.</p></div>")
    sent = 0
    for em in recipients:
        try:
            await notifications.send_email(em, f"Follow-up: download your {org_name} assurance evidence", html)
            sent += 1
        except Exception:
            pass
    return {"sent": sent, "to": recipients}


def _declining_run(points, days=2):
    if len(points) < days + 1:
        return False
    window = [p["avg_eff"] for p in points[-(days + 1):]]
    return all(window[i] > window[i + 1] for i in range(len(window) - 1))


def _engagement_nudge_html(owner, points, days=2):
    latest, prior = points[-1]["avg_eff"], points[0]["avg_eff"]
    drop = prior - latest
    return (f"<div style='font:400 14px Arial;color:#1f2937;max-width:620px;margin:auto'>"
            f"<h2 style='color:#b91c1c'>Your control readiness is trending down</h2>"
            f"<p>Hi {owner}, the average effectiveness of the controls you own has fallen for {days} days "
            f"running \u2014 from {prior}% to {latest}% (down {drop} pts). Please review your controls "
            f"before it slips further.</p>"
            f"<p style='font-size:11px;color:#9ca3af'>Obserra Control Intelligence \u2014 proactive readiness nudge.</p></div>")


async def _run_ci_engagement_nudges(org_id):
    today = datetime.now(timezone.utc).date().isoformat()
    org = await db.organizations.find_one({"_id": ObjectId(org_id)}, {"ci_nudge_drop_days": 1})
    drop_days = 3 if int((org or {}).get("ci_nudge_drop_days") or 2) == 3 else 2
    owners = await db.ci_owner_eff_history.distinct("owner", {"org_id": org_id})
    muted = await _muted_emails(org_id)
    nudged = 0
    for owner in owners:
        if not owner or owner == "Unassigned":
            continue
        pts = await db.ci_owner_eff_history.find(
            {"org_id": org_id, "owner": owner}, {"_id": 0, "date": 1, "avg_eff": 1}).sort("date", 1).to_list(400)
        if not _declining_run(pts, drop_days):
            continue
        marker = f"ci-engage-drop:{org_id}:{owner}:{today}"
        if await db.ci_sent_markers.find_one({"marker": marker}):
            continue
        em = (await _owner_email_map(org_id, {owner: []})).get((owner or "").strip().lower())
        if not em or em in muted:
            continue
        try:
            await notifications.send_email(
                em, "Your control readiness is declining \u2014 Obserra Control Intelligence",
                _engagement_nudge_html(owner, pts[-(drop_days + 1):], drop_days))
            await db.ci_sent_markers.insert_one({"marker": marker, "at": datetime.now(timezone.utc).isoformat()})
            nudged += 1
        except Exception:
            pass
    return {"nudged": nudged}


async def _run_ci_engagement_nudges_all():
    orgs = await db.organizations.find({}, {"_id": 1}).to_list(1000)
    for org in orgs:
        try:
            await _run_ci_engagement_nudges(str(org["_id"]))
        except Exception as e:
            logger.warning(f"CI engagement nudges failed for org {org['_id']}: {e}")


async def _auditor_recap_payload(org_id, days=7):
    from datetime import timedelta
    now = datetime.now(timezone.utc)
    since = (now - timedelta(days=days)).isoformat()
    rows = await db.ci_auditor_access.find(
        {"org_id": org_id, "at": {"$gt": since}}, {"_id": 0, "kind": 1, "who": 1, "token": 1}).to_list(5000)
    views = sum(1 for r in rows if r.get("kind") == "view")
    downloads = sum(1 for r in rows if r.get("kind") == "download")
    reviewers = sorted({(r.get("who") or "").strip() for r in rows
                        if r.get("kind") == "download" and (r.get("who") or "").strip()})
    per = {}
    for r in rows:
        t = r.get("token")
        if not t:
            continue
        p = per.setdefault(t, {"views": 0, "downloads": 0, "viewers": set()})
        if r.get("kind") == "view":
            p["views"] += 1
            w = (r.get("who") or "").strip()
            if w:
                p["viewers"].add(w)
        elif r.get("kind") == "download":
            p["downloads"] += 1
    active = {d["token"] for d in await db.ci_auditor_links.find(
        {"org_id": org_id, "revoked": {"$ne": True}, "expires_at": {"$gt": now.isoformat()}},
        {"_id": 0, "token": 1}).to_list(500)}
    awaiting = [{"token": t, "url": _ci_link_url(t), "viewers": sorted(p["viewers"])}
                for t, p in per.items() if t in active and p["views"] > 0 and p["downloads"] == 0]
    prefix = f"ci-engage-drop:{org_id}:"
    marks = await db.ci_sent_markers.find(
        {"marker": {"$regex": f"^{prefix}"}, "at": {"$gt": since}}, {"_id": 0, "marker": 1}).to_list(500)
    nudged_owners = sorted({m["marker"][len(prefix):].rsplit(":", 1)[0]
                            for m in marks if m["marker"].startswith(prefix)})
    return {"views": views, "downloads": downloads, "reviewers": reviewers, "days": days,
            "events": len(rows), "awaiting": awaiting, "nudged_owners": nudged_owners}


@ci_router.get("/auditor-link/recap/preview")
async def auditor_recap_preview(days: int = 7, admin: dict = Depends(require_roles("admin"))):
    days = max(1, min(90, int(days or 7)))
    return await _auditor_recap_payload(admin["org_id"], days)


def _recap_html(org_name, rec, auditor_recipients=None):
    from urllib.parse import quote
    rv = rec["reviewers"]
    parts = [f"<div style='font:400 14px Arial;color:#1f2937;max-width:620px;margin:auto'>",
             f"<h2 style='color:#0f1e3d'>Weekly assurance recap \u2014 {org_name}</h2>",
             f"<p>External auditor engagement over the last {rec['days']} days:</p>",
             f"<ul><li><strong>{rec['views']}</strong> portal view(s)</li>",
             f"<li><strong>{rec['downloads']}</strong> signed-PDF download(s)</li>",
             f"<li><strong>{len(rv)}</strong> named reviewer(s){(': ' + ', '.join(rv)) if rv else ''}</li></ul>"]
    aw = rec.get("awaiting") or []
    if aw:
        to = ",".join(auditor_recipients or [])
        parts.append("<h3 style='color:#b45309;margin:14px 0 4px'>Viewed but not downloaded \u2014 chase these</h3><ul>")
        for a in aw:
            who = f" (viewed by {', '.join(a['viewers'])})" if a.get("viewers") else ""
            subject = quote(f"Please download your {org_name} assurance evidence")
            body = quote(f"Hi,\n\nOur read-only assurance portal was opened but the signed evidence PDF "
                         f"has not been downloaded yet. Please pull the sealed brief here:\n{a['url']}\n\nThank you.")
            mailto = f"mailto:{to}?subject={subject}&body={body}"
            parts.append(f"<li><a href='{a['url']}' style='color:#12b4d6'>{a['url']}</a>{who} "
                         f"\u2014 <a href='{mailto}' style='color:#0f1e3d;font-weight:bold'>Nudge auditor</a></li>")
        parts.append("</ul>")
    no = rec.get("nudged_owners") or []
    if no:
        parts.append(f"<h3 style='color:#0f1e3d;margin:14px 0 4px'>Readiness nudges sent this week</h3>"
                     f"<p>{len(no)} owner(s) were auto-nudged for declining control readiness: "
                     f"{', '.join(no)}.</p>")
    parts.append("<p style='font-size:11px;color:#9ca3af'>Obserra Control Intelligence \u2014 weekly assurance recap.</p></div>")
    return "".join(parts)


def _recap_markdown(org_name, rec):
    rv = rec["reviewers"]
    lines = [f"## Weekly Assurance Recap \u2014 {org_name}",
             f"External auditor engagement over the last {rec['days']} days.",
             "", "## Engagement",
             f"- Portal views: {rec['views']}",
             f"- Signed-PDF downloads: {rec['downloads']}",
             f"- Named reviewers: {len(rv)}" + (f" ({', '.join(rv)})" if rv else "")]
    aw = rec.get("awaiting") or []
    if aw:
        lines += ["", "## Viewed but not downloaded \u2014 chase these"]
        for a in aw:
            who = f" (viewed by {', '.join(a['viewers'])})" if a.get("viewers") else ""
            lines.append(f"- {a['url']}{who}")
    no = rec.get("nudged_owners") or []
    if no:
        lines += ["", "## Readiness nudges sent this week", f"- {', '.join(no)}"]
    lines += ["", "## Defensibility",
              "- Views/downloads/reviewers are FACT values from the auditor access log.",
              "- Obserra Control Intelligence \u2014 weekly assurance recap."]
    return "\n".join(lines)


def _app_version_label():
    try:
        import onprem_pack
        v = str(onprem_pack.read_version() or "").lstrip("v")
        return f"v{v}" if v else "v1.0.0"
    except Exception:
        return "v1.0.0"


def _recap_pdf(org_name, rec, brand):
    import hashlib
    md = _recap_markdown(org_name, rec)
    raw = _build_pdf(md, "Weekly Assurance Recap", cover=True, org_name=org_name, brand=brand,
                     version=_app_version_label()).getvalue()
    try:
        from agent_reports import _stamp_verified_seal
        raw = _stamp_verified_seal(raw, hashlib.sha256(md.encode()).hexdigest())
    except Exception as e:
        logger.warning(f"CI recap seal failed: {e}")
    return raw


def _recap_attachments(org, rec):
    try:
        org_name = (org or {}).get("name") or "Organization"
        raw = _recap_pdf(org_name, rec, _resolve_brand(org))
        return [{"filename": "obserra-weekly-assurance-recap.pdf", "content": base64.b64encode(raw).decode()}]
    except Exception as e:
        logger.warning(f"CI recap PDF build failed: {e}")
        return []


async def _run_ci_weekly_assurance_recap_all():
    now = datetime.now(timezone.utc)
    week = now.strftime("%Y-%W")
    weekday = now.weekday()
    orgs = await db.organizations.find(
        {}, {"_id": 1, "name": 1, "ci_recap_enabled": 1, "ci_recap_weekday": 1, "report_branding": 1}).to_list(1000)
    for org in orgs:
        org_id = str(org["_id"])
        try:
            if not org.get("ci_recap_enabled"):
                continue
            if int(org.get("ci_recap_weekday") or 0) != weekday:
                continue
            rec = await _auditor_recap_payload(org_id, 7)
            if not (rec["views"] or rec["downloads"] or rec["nudged_owners"]):
                continue
            marker = f"ci-recap:{org_id}:{week}"
            if await db.ci_sent_markers.find_one({"marker": marker}):
                continue
            role_map = await _brief_role_map(org_id)
            emails = sorted(role_map["board"] | role_map["auditor"])
            if not emails:
                continue
            org_name = org.get("name") or "Organization"
            html = _recap_html(org_name, rec, sorted(role_map["auditor"]))
            attachments = _recap_attachments(org, rec)
            for em in emails:
                try:
                    await notifications.send_email(em, f"Weekly assurance recap \u2014 {org_name}", html,
                                                   attachments=attachments)
                except Exception:
                    pass
            await db.ci_sent_markers.insert_one({"marker": marker, "at": now.isoformat()})
        except Exception as e:
            logger.warning(f"CI weekly recap failed for org {org_id}: {e}")


@ci_router.get("/public/auditor-link/{token}/meta")
async def public_auditor_link_meta(token: str):
    now = datetime.now(timezone.utc)
    doc = await db.ci_auditor_links.find_one(
        {"token": token}, {"_id": 0, "org_id": 1, "revoked": 1, "expires_at": 1})
    if not doc or doc.get("revoked") or doc.get("expires_at", "") <= now.isoformat():
        return {"valid": False}
    org = await db.organizations.find_one({"_id": ObjectId(doc["org_id"])}, {"name": 1, "ci_auditor_ask_name": 1})
    return {"valid": True, "org_name": (org or {}).get("name") or "Organization",
            "ask_name": bool((org or {}).get("ci_auditor_ask_name", False))}


@ci_router.post("/auditor-link/recap/send")
async def auditor_recap_send(days: int = 7, admin: dict = Depends(require_roles("admin"))):
    from fastapi import HTTPException
    days = max(1, min(90, int(days or 7)))
    org_id = admin["org_id"]
    rec = await _auditor_recap_payload(org_id, days)
    org = await db.organizations.find_one({"_id": ObjectId(org_id)}, {"name": 1, "report_branding": 1})
    org_name = (org or {}).get("name") or "Organization"
    role_map = await _brief_role_map(org_id)
    emails = sorted(role_map["board"] | role_map["auditor"])
    if not emails:
        raise HTTPException(status_code=400, detail="No recipients configured to send to.")
    html = _recap_html(org_name, rec, sorted(role_map["auditor"]))
    attachments = _recap_attachments(org, rec)
    sent = 0
    for em in emails:
        try:
            await notifications.send_email(em, f"Assurance recap ({days}d) \u2014 {org_name}", html,
                                           attachments=attachments)
            sent += 1
        except Exception:
            pass
    await _log_recap(org_id, rec, emails, "manual")
    return {"sent": sent, "to": emails, "recap": rec}


@ci_router.post("/auditor-link/recap/test")
async def auditor_recap_test(days: int = 7, admin: dict = Depends(require_roles("admin"))):
    """Send the exact recap only to the requesting admin's own inbox (test copy, not logged)."""
    days = max(1, min(90, int(days or 7)))
    org_id = admin["org_id"]
    rec = await _auditor_recap_payload(org_id, days)
    org = await db.organizations.find_one({"_id": ObjectId(org_id)}, {"name": 1, "report_branding": 1})
    org_name = (org or {}).get("name") or "Organization"
    role_map = await _brief_role_map(org_id)
    to = admin["email"]
    html = _recap_html(org_name, rec, sorted(role_map["auditor"]))
    attachments = _recap_attachments(org, rec)
    sent = 0
    try:
        await notifications.send_email(to, f"[Test copy] Assurance recap ({days}d) \u2014 {org_name}", html,
                                       attachments=attachments)
        sent = 1
    except Exception:
        pass
    return {"sent": sent, "to": [to], "recap": rec}


@ci_router.get("/auditor-link/activity")
async def auditor_activity(days: int = 30, user: dict = Depends(require_roles("admin", "executive"))):
    days = max(1, min(90, int(days or 30)))
    rec = await _auditor_engagement(user["org_id"], days)
    return {"views": rec["views"], "downloads": rec["downloads"],
            "reviewers": len(rec["reviewers"]), "days": days}


async def _auditor_timeline_data(org_id, version=None):
    q = {"org_id": org_id}
    if version:
        q["app_version"] = version
    rows = await db.ci_auditor_access.find(
        q, {"_id": 0, "kind": 1, "who": 1, "at": 1, "app_version": 1, "token": 1}).sort("at", 1).to_list(5000)
    people = {}
    for r in rows:
        who = (r.get("who") or "").strip() or "Anonymous"
        p = people.setdefault(who, {"who": who, "events": [], "first_view": None, "first_download": None,
                                    "views": 0, "downloads": 0, "token": None})
        if r.get("token"):
            p["token"] = r.get("token")
        p["events"].append({"kind": r.get("kind"), "at": r.get("at"), "version": r.get("app_version")})
        if r.get("kind") == "view":
            p["views"] += 1
            if not p["first_view"]:
                p["first_view"] = r.get("at")
        if r.get("kind") == "download":
            p["downloads"] += 1
            if not p["first_download"]:
                p["first_download"] = r.get("at")
    out = []
    for p in people.values():
        secs = None
        if p["first_view"] and p["first_download"] and p["first_download"] >= p["first_view"]:
            try:
                secs = int((datetime.fromisoformat(p["first_download"])
                            - datetime.fromisoformat(p["first_view"])).total_seconds())
            except Exception:
                secs = None
        p["review_seconds"] = secs
        p["stalled"] = p["views"] >= 2 and p["downloads"] == 0 and p["who"] != "Anonymous"
        p["last_at"] = p["events"][-1]["at"] if p["events"] else None
        out.append(p)
    out.sort(key=lambda x: x["last_at"] or "", reverse=True)
    out.sort(key=lambda x: 0 if x["stalled"] else 1)
    return out


async def _auditor_versions(org_id):
    vs = await db.ci_auditor_access.distinct("app_version", {"org_id": org_id})
    return sorted([v for v in vs if v], reverse=True)


@ci_router.get("/auditor-link/timeline")
async def auditor_timeline(version: str = "", admin: dict = Depends(require_roles("admin"))):
    org_id = admin["org_id"]
    return {"people": await _auditor_timeline_data(org_id, version or None),
            "versions": await _auditor_versions(org_id)}


async def _version_engagement(org_id):
    rows = await db.ci_auditor_access.find(
        {"org_id": org_id}, {"_id": 0, "kind": 1, "who": 1, "app_version": 1}).to_list(5000)
    by = {}
    for r in rows:
        v = r.get("app_version")
        if not v:
            continue
        b = by.setdefault(v, {"version": v, "views": 0, "downloads": 0, "reviewers": set()})
        if r.get("kind") == "view":
            b["views"] += 1
        elif r.get("kind") == "download":
            b["downloads"] += 1
            who = (r.get("who") or "").strip()
            if who:
                b["reviewers"].add(who)
    out = []
    for b in by.values():
        b["reviewers"] = sorted(b["reviewers"])
        b["reviewer_count"] = len(b["reviewers"])
        out.append(b)
    out.sort(key=lambda x: x["version"], reverse=True)
    return out


@ci_router.get("/auditor-link/version-engagement")
async def auditor_version_engagement(admin: dict = Depends(require_roles("admin"))):
    return {"versions": await _version_engagement(admin["org_id"])}


def _fmt_secs(s):
    if s is None:
        return "n/a"
    if s >= 3600:
        return f"{s // 3600}h {(s % 3600) // 60}m"
    if s >= 60:
        return f"{s // 60}m {s % 60}s"
    return f"{s}s"


async def _log_recap(org_id, rec, to, trigger):
    try:
        await db.ci_recap_log.insert_one({
            "org_id": org_id, "at": datetime.now(timezone.utc).isoformat(), "trigger": trigger,
            "to": to, "days": rec["days"], "views": rec["views"], "downloads": rec["downloads"],
            "reviewers": rec["reviewers"], "awaiting": len(rec.get("awaiting") or []),
            "nudged_owners": rec.get("nudged_owners") or []})
    except Exception:
        pass


@ci_router.get("/auditor-link/recap/history")
async def auditor_recap_history(limit: int = 20, admin: dict = Depends(require_roles("admin"))):
    limit = max(1, min(100, int(limit or 20)))
    rows = await db.ci_recap_log.find(
        {"org_id": admin["org_id"]}, {"_id": 0, "org_id": 0}).sort("at", -1).to_list(limit)
    return {"history": rows}


@ci_router.get("/auditor-link/timeline.pdf")
async def auditor_timeline_pdf(version: str = "", admin: dict = Depends(require_roles("admin"))):
    from fastapi.responses import StreamingResponse
    import io
    org_id = admin["org_id"]
    people = await _auditor_timeline_data(org_id, version or None)
    org = await db.organizations.find_one({"_id": ObjectId(org_id)}, {"name": 1, "report_branding": 1})
    org_name = (org or {}).get("name") or "Organization"
    lines = ["# Reviewer Access Timeline", "",
             "Chain-of-custody record of external auditor access to the sealed assurance evidence.", ""]
    if version:
        lines.append(f"_Filtered to evidence produced by app version {version}._")
        lines.append("")
    if not people:
        lines.append("- No auditor access recorded yet.")
    for p in people:
        dur = ("view\u2192download in " + _fmt_secs(p["review_seconds"])) if p["review_seconds"] is not None \
            else ("downloaded" if p["downloads"] else "not downloaded")
        flag = " [STALLED]" if p["stalled"] else ""
        lines.append(f"## {p['who']}{flag}")
        lines.append(f"- {p['views']} view(s), {p['downloads']} download(s) \u2014 {dur}")
        for ev in p["events"]:
            vtag = f" \u00b7 {ev['version']}" if ev.get("version") else ""
            lines.append(f"- {(ev['kind'] or '').upper()} \u2014 {ev['at']}{vtag}")
        lines.append("")
    md = "\n".join(lines)
    pdf = _build_pdf(md, "Reviewer Access Timeline", cover=True, org_name=org_name, brand=_resolve_brand(org),
                     version=_app_version_label())
    return StreamingResponse(io.BytesIO(pdf.getvalue()), media_type="application/pdf",
                             headers={"Content-Disposition": 'attachment; filename="obserra-reviewer-timeline.pdf"'})



# ---------------------------------------------------------------- manual readiness nudge fire

@ci_router.post("/engagement-nudges")
async def engagement_nudges(admin: dict = Depends(require_roles("admin"))):
    """Admin: fire the declining-readiness owner nudges on demand (normally cron-driven)."""
    return await _run_ci_engagement_nudges(admin["org_id"])


# ---------------------------------------------------------------- monthly assurance digest

async def _ci_eff_delta(org_id, days=30):
    from datetime import timedelta
    since = (datetime.now(timezone.utc) - timedelta(days=days)).date().isoformat()
    rows = await db.control_eff_history.find(
        {"org_id": org_id, "date": {"$gte": since}},
        {"_id": 0, "date": 1, "avg_effectiveness": 1, "health_score": 1}).sort("date", 1).to_list(400)
    if not rows:
        return {"points": 0, "eff_delta": None, "health_delta": None}
    first, last = rows[0], rows[-1]
    return {"points": len(rows),
            "eff_delta": int(last.get("avg_effectiveness", 0) - first.get("avg_effectiveness", 0)),
            "health_delta": int(last.get("health_score", 0) - first.get("health_score", 0))}


async def _assurance_digest_payload(org_id, days=30):
    a = await _ci_aggregate(org_id)
    eng = await _auditor_engagement(org_id, days)
    delta = await _ci_eff_delta(org_id, days)
    frameworks = sorted(a["frameworks"], key=lambda x: -x["coverage"])[:8]
    at_risk = [c for c in a["statuses"]
               if c["status"] != "Passing" or c.get("days_to_expiry", 999) <= 14 or c.get("drift")]
    weak = sorted(a["statuses"], key=lambda c: c["effectiveness"])[:5]
    return {"days": days, "health": a["health"], "total": a["total"], "passing": a["passing"],
            "avg_eff": a["avg_eff"], "avg_maturity": a["avg_maturity"], "coverage": a["coverage"],
            "at_risk": len(at_risk), "frameworks": frameworks,
            "weak": [{"control_id": c["control_id"], "name": c["name"], "status": c["status"],
                      "effectiveness": c["effectiveness"]} for c in weak],
            "engagement": eng, "trend": delta}


def _assurance_digest_html(org_name, p):
    def delta_str(d):
        if d is None:
            return ""
        color = "#15803d" if d > 0 else ("#b91c1c" if d < 0 else "#6b7280")
        arrow = "\u25b2" if d > 0 else ("\u25bc" if d < 0 else "\u25ac")
        return f" <span style='color:{color};font-size:13px'>{arrow} {d:+d} pts / {p['days']}d</span>"
    fw = "".join(f"<li>{f['framework']}: {f['coverage']}% coverage, {f['passing']}/{f['controls']} passing</li>"
                 for f in p["frameworks"]) or "<li>No framework coverage returned.</li>"
    weak = "".join(f"<li><strong>{c['control_id']}</strong> {c['name']} \u2014 {c['status']}, {c['effectiveness']}%</li>"
                   for c in p["weak"]) or "<li>All controls passing.</li>"
    eng = p["engagement"]
    rv = eng["reviewers"]
    eng_line = (f"{eng['views']} portal view(s) \u00b7 {eng['downloads']} signed-PDF download(s)"
                + (f" by {len(rv)} named reviewer(s): {', '.join(rv)}" if rv else " \u00b7 no named downloads yet"))
    trend = p["trend"]
    trend_note = (f"Effectiveness{delta_str(trend['eff_delta'])} \u00b7 Health{delta_str(trend['health_delta'])}"
                  if trend.get("points") else "Trend builds daily \u2014 more history accrues over time.")

    def kv(k, v):
        return (f"<tr><td style='padding:3px 14px 3px 0;color:#6b7280'>{k}</td>"
                f"<td style='padding:3px 0'><strong>{v}</strong></td></tr>")

    wn = app_meta.current_changelog()
    wn_html = (f"<h3 style='color:#0f1e3d;margin:14px 0 4px'>What's new in {app_meta.APP_VERSION_LABEL}</h3>"
               f"<ul>{''.join('<li>' + i + '</li>' for i in wn)}</ul>") if wn else ""

    return (f"<div style='font:400 14px Arial;color:#1f2937;max-width:640px;margin:auto'>"
            f"<h2 style='color:#0f1e3d'>Monthly Assurance Digest \u2014 {org_name}</h2>"
            f"<p style='color:#6b7280'>A board-ready rollup of the last {p['days']} days of control "
            f"effectiveness and external assurance activity.</p>"
            f"<table style='border-collapse:collapse;margin:8px 0 14px'>"
            + kv("Control health", f"{p['health']}/100")
            + kv("Controls passing", f"{p['passing']}/{p['total']}")
            + kv("Avg effectiveness", f"{p['avg_eff']}%")
            + kv("Coverage", f"{p['coverage']}%")
            + kv("At-risk now", p['at_risk'])
            + "</table>"
            f"<p style='margin:0 0 4px'><strong>{p['days']}-day trend:</strong> {trend_note}</p>"
            f"<h3 style='color:#0f1e3d;margin:14px 0 4px'>Framework readiness</h3><ul>{fw}</ul>"
            f"<h3 style='color:#0f1e3d;margin:14px 0 4px'>Highest-priority control gaps</h3><ul>{weak}</ul>"
            f"<h3 style='color:#0f1e3d;margin:14px 0 4px'>External assurance activity ({p['days']}d)</h3><p>{eng_line}</p>"
            + wn_html
            + f"<p style='font-size:11px;color:#9ca3af'>Obserra Control Intelligence \u2014 monthly assurance digest.</p></div>")


def _assurance_digest_markdown(org_name, p):
    eng = p["engagement"]
    rv = eng["reviewers"]
    trend = p["trend"]
    lines = [f"## Monthly Assurance Digest \u2014 {org_name}",
             f"A board-ready rollup of the last {p['days']} days of control effectiveness and external assurance activity.",
             "", "## Control Posture",
             f"- Control health score: {p['health']}/100",
             f"- Controls passing: {p['passing']}/{p['total']}",
             f"- Average effectiveness: {p['avg_eff']}%",
             f"- Average maturity: {p['avg_maturity']}/5",
             f"- Coverage: {p['coverage']}%",
             f"- At-risk now: {p['at_risk']}"]
    if trend.get("points"):
        lines.append(f"- {p['days']}-day trend: effectiveness {trend['eff_delta']:+d} pts, "
                     f"health {trend['health_delta']:+d} pts")
    lines += ["", "## Framework Readiness"]
    if p["frameworks"]:
        for f in p["frameworks"]:
            lines.append(f"- {f['framework']}: {f['coverage']}% coverage, {f['passing']}/{f['controls']} passing")
    else:
        lines.append("- No framework coverage returned.")
    lines += ["", "## Highest-Priority Control Gaps"]
    if p["weak"]:
        for c in p["weak"]:
            lines.append(f"- [{c['control_id']}] {c['name']}: {c['status']}, effectiveness {c['effectiveness']}%")
    else:
        lines.append("- All controls passing.")
    lines += ["", f"## External Assurance Activity ({p['days']}d)",
              f"- Portal views: {eng['views']}",
              f"- Signed-PDF downloads: {eng['downloads']}"
              + (f" by {len(rv)} named reviewer(s)" if rv else "")]
    if rv:
        lines.append(f"- Named reviewers: {', '.join(rv)}")
    wn = app_meta.current_changelog()
    if wn:
        lines += ["", f"## What's New in {app_meta.APP_VERSION_LABEL}"]
        for i in wn:
            lines.append(f"- {i}")
    lines += ["", "## Defensibility",
              "- Control status, effectiveness, maturity and framework coverage are FACT values from the live control feed.",
              "- Health, coverage and trend roll-ups are MODELLED calculations."]
    return "\n".join(lines)


def _assurance_digest_pdf(org_name, p, brand):
    import hashlib
    md = _assurance_digest_markdown(org_name, p)
    raw = _build_pdf(md, "Monthly Assurance Digest", cover=True, org_name=org_name, brand=brand,
                     version=_app_version_label()).getvalue()
    try:
        from agent_reports import _stamp_verified_seal
        raw = _stamp_verified_seal(raw, hashlib.sha256(md.encode()).hexdigest())
    except Exception as e:
        logger.warning(f"CI digest seal failed: {e}")
    return raw


async def _run_ci_assurance_digest(org_id, trigger="scheduled"):
    p = await _assurance_digest_payload(org_id, 30)
    org = await db.organizations.find_one(
        {"_id": ObjectId(org_id)}, {"name": 1, "report_branding": 1})
    org_name = (org or {}).get("name") or "Organization"
    role_map = await _brief_role_map(org_id)
    emails = sorted(role_map["board"] | role_map["auditor"])
    if not emails:
        return {"sent": 0, "to": [], "digest": p}
    html = _assurance_digest_html(org_name, p)
    attachments = []
    try:
        pdf_raw = _assurance_digest_pdf(org_name, p, _resolve_brand(org))
        attachments = [{"filename": "obserra-monthly-assurance-digest.pdf",
                        "content": base64.b64encode(pdf_raw).decode()}]
    except Exception as e:
        logger.warning(f"CI digest PDF build failed: {e}")
    sent = 0
    for em in emails:
        try:
            await notifications.send_email(em, f"Monthly Assurance Digest \u2014 {org_name}", html,
                                           attachments=attachments)
            sent += 1
        except Exception:
            pass
    try:
        await db.ci_digest_log.insert_one({
            "org_id": org_id, "at": datetime.now(timezone.utc).isoformat(), "trigger": trigger,
            "to": emails, "health": p["health"], "avg_eff": p["avg_eff"], "at_risk": p["at_risk"]})
    except Exception:
        pass
    return {"sent": sent, "to": emails, "digest": p}


async def _run_ci_assurance_digest_all():
    now = datetime.now(timezone.utc)
    month = now.strftime("%Y-%m")
    orgs = await db.organizations.find(
        {}, {"_id": 1, "ci_digest_enabled": 1, "ci_digest_day": 1, "ci_digest_cadence": 1}).to_list(1000)
    for org in orgs:
        org_id = str(org["_id"])
        try:
            if not org.get("ci_digest_enabled"):
                continue
            cadence = org.get("ci_digest_cadence") or "monthly"
            if cadence == "quarterly" and now.month not in (1, 4, 7, 10):
                continue
            if now.day != max(1, min(28, int(org.get("ci_digest_day") or 1))):
                continue
            marker = f"ci-digest:{org_id}:{month}"
            if await db.ci_sent_markers.find_one({"marker": marker}):
                continue
            res = await _run_ci_assurance_digest(org_id, trigger="scheduled")
            if res.get("sent"):
                await db.ci_sent_markers.insert_one({"marker": marker, "at": now.isoformat()})
        except Exception as e:
            logger.warning(f"CI assurance digest failed for org {org_id}: {e}")


@ci_router.get("/assurance-digest/preview")
async def assurance_digest_preview(admin: dict = Depends(require_roles("admin"))):
    return await _assurance_digest_payload(admin["org_id"], 30)


@ci_router.post("/assurance-digest/send")
async def assurance_digest_send(admin: dict = Depends(require_roles("admin"))):
    from fastapi import HTTPException
    res = await _run_ci_assurance_digest(admin["org_id"], trigger="manual")
    if not res["to"]:
        raise HTTPException(status_code=400, detail="No recipients configured to send to.")
    return res


@ci_router.get("/assurance-digest/history")
async def assurance_digest_history(limit: int = 10, admin: dict = Depends(require_roles("admin"))):
    limit = max(1, min(100, int(limit or 10)))
    rows = await db.ci_digest_log.find(
        {"org_id": admin["org_id"]}, {"_id": 0, "org_id": 0}).sort("at", -1).to_list(limit)
    return {"history": rows}


@ci_router.post("/assurance-digest/test")
async def assurance_digest_test(admin: dict = Depends(require_roles("admin"))):
    """Send the exact monthly digest (with sealed PDF) only to the requesting admin's inbox (test copy, not logged)."""
    org_id = admin["org_id"]
    p = await _assurance_digest_payload(org_id, 30)
    org = await db.organizations.find_one({"_id": ObjectId(org_id)}, {"name": 1, "report_branding": 1})
    org_name = (org or {}).get("name") or "Organization"
    to = admin["email"]
    html = _assurance_digest_html(org_name, p)
    attachments = []
    try:
        pdf_raw = _assurance_digest_pdf(org_name, p, _resolve_brand(org))
        attachments = [{"filename": "obserra-monthly-assurance-digest.pdf",
                        "content": base64.b64encode(pdf_raw).decode()}]
    except Exception as e:
        logger.warning(f"CI digest test PDF build failed: {e}")
    sent = 0
    try:
        await notifications.send_email(to, f"[Test copy] Monthly Assurance Digest \u2014 {org_name}", html,
                                       attachments=attachments)
        sent = 1
    except Exception:
        pass
    return {"sent": sent, "to": [to], "digest": p}