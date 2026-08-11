"""Obserra Control Intelligence — composed on the existing control feed.

Adds three capabilities without introducing any new control data source:
  * daily control-effectiveness snapshot + trend history
  * control-owner remediation nudges (email)
  * one-tap / scheduled Executive Assurance Brief email (PDF)

Everything derives from the existing `/controls` feed and reuses the existing
managed-Resend email sender and PDF builder.
"""
import os
import base64
import logging
from datetime import datetime, timezone

from typing import List, Optional

from bson import ObjectId
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from db import db
from auth import get_current_user, require_roles
from kernel import notifications
from reports import _build_pdf, _report_html, _resolve_brand

logger = logging.getLogger(__name__)
ci_router = APIRouter(prefix="/api/control-intelligence")


async def _ci_aggregate(org_id):
    """Live per-org control aggregate, reusing the exact control-status logic."""
    from routes import _control_status, _ensure_controls
    await _ensure_controls(org_id)
    existing = await db.controls.find({"org_id": org_id}, {"_id": 0}).to_list(500)
    statuses = [_control_status(c) for c in existing]
    total = len(statuses)
    passing = sum(1 for c in statuses if c["status"] == "Passing")
    avg_eff = round(sum(c["effectiveness"] for c in statuses) / total) if total else 0
    avg_maturity = round(sum(c.get("maturity", 0) for c in statuses) / total, 1) if total else 0
    stale = sum(1 for c in statuses if c.get("stale"))
    agg = {}
    for c in statuses:
        for fw in (c.get("frameworks") or {}):
            e = agg.setdefault(fw, {"framework": fw, "controls": 0, "passing": 0, "eff_sum": 0})
            e["controls"] += 1
            e["eff_sum"] += c["effectiveness"]
            if c["status"] == "Passing":
                e["passing"] += 1
    frameworks = [{"framework": fw, "controls": e["controls"], "passing": e["passing"],
                   "coverage": round(e["eff_sum"] / e["controls"]) if e["controls"] else 0}
                  for fw, e in agg.items()]
    coverage = round(sum(f["coverage"] for f in frameworks) / len(frameworks)) if frameworks else 0
    health = round(min(100, max(0,
        avg_eff * 0.5 + (passing / total) * 100 * 0.25
        + ((total - stale) / total) * 100 * 0.15 + (avg_maturity / 5) * 100 * 0.1))) if total else 0
    return {"statuses": statuses, "total": total, "passing": passing, "avg_eff": avg_eff,
            "avg_maturity": avg_maturity, "stale": stale, "coverage": coverage,
            "health": health, "frameworks": frameworks}


async def _snapshot_org(org_id):
    a = await _ci_aggregate(org_id)
    today = datetime.now(timezone.utc).date().isoformat()
    await db.control_eff_history.update_one(
        {"org_id": org_id, "date": today},
        {"$set": {"org_id": org_id, "date": today,
                  "avg_effectiveness": a["avg_eff"], "passing": a["passing"],
                  "total": a["total"], "coverage": a["coverage"], "health_score": a["health"],
                  "ts": datetime.now(timezone.utc).isoformat()}}, upsert=True)
    return a


async def _run_ci_effectiveness_snapshot():
    orgs = await db.organizations.find({}, {"_id": 1}).to_list(1000)
    n = 0
    for org in orgs:
        try:
            await _snapshot_org(str(org["_id"]))
            n += 1
        except Exception as e:
            logger.warning(f"CI effectiveness snapshot failed for org {org['_id']}: {e}")
    logger.info(f"CI effectiveness snapshot recorded for {n} org(s)")


def _at_risk(statuses):
    return [c for c in statuses
            if c["status"] != "Passing" or c.get("days_to_expiry", 999) <= 14 or c.get("drift")]


def _group_at_risk(at_risk):
    by_owner = {}
    for c in at_risk:
        by_owner.setdefault(c.get("owner") or "Unassigned", []).append(c)
    return by_owner


def _nudge_html(at_risk, by_owner):
    rows = ""
    for owner, ctrls in sorted(by_owner.items()):
        items = "".join(
            f"<li><strong>{c['control_id']}</strong> {c['name']} — {c['status']}, "
            f"effectiveness {c['effectiveness']}%"
            + (f", evidence expires in {c['days_to_expiry']}d" if c.get('days_to_expiry') is not None else "")
            + "</li>" for c in ctrls)
        rows += f"<h3 style='margin:14px 0 4px'>{owner} — {len(ctrls)} control(s)</h3><ul>{items}</ul>"
    return (f"<div style='font:400 14px Arial;color:#1f2937;max-width:640px;margin:auto'>"
            f"<h2 style='color:#0f1e3d'>Control remediation reminder</h2>"
            f"<p>{len(at_risk)} control(s) need attention. Please pick up remediation for the controls you own.</p>"
            f"{rows}"
            f"<p style='font-size:11px;color:#9ca3af'>Obserra Control Intelligence — automated remediation nudge.</p></div>")


async def _admin_exec_emails(org_id):
    recips = await db.users.find(
        {"org_id": org_id, "role": {"$in": ["admin", "executive"]}}, {"_id": 0, "email": 1}).to_list(200)
    return {r["email"] for r in recips if r.get("email")}


async def _owner_email_map(org_id, by_owner):
    owner_names = {(o or "").strip().lower() for o in by_owner if o and o.lower() != "unassigned"}
    mp = {}
    if owner_names:
        allusers = await db.users.find({"org_id": org_id}, {"_id": 0, "email": 1, "name": 1}).to_list(500)
        for u in allusers:
            nm = (u.get("name") or "").strip().lower()
            if nm in owner_names and u.get("email") and nm not in mp:
                mp[nm] = u["email"]
    return mp


def _nudge_owner_html(owner, ctrls):
    items = "".join(
        f"<li><strong>{c['control_id']}</strong> {c['name']} — {c['status']}, "
        f"effectiveness {c['effectiveness']}%"
        + (f", evidence expires in {c['days_to_expiry']}d" if c.get('days_to_expiry') is not None else "")
        + "</li>" for c in ctrls)
    return (f"<div style='font:400 14px Arial;color:#1f2937;max-width:640px;margin:auto'>"
            f"<h2 style='color:#0f1e3d'>Your controls need attention</h2>"
            f"<p>Hi {owner}, {len(ctrls)} control(s) you own need remediation. Here is exactly what to pick up:</p>"
            f"<ul>{items}</ul>"
            f"<p style='font-size:11px;color:#9ca3af'>Obserra Control Intelligence — personalized remediation nudge.</p></div>")


def _nudge_groups(by_owner, owner_map=None, muted=None):
    owner_map = owner_map or {}
    muted = muted or set()
    out = []
    for o, ctrls in sorted(by_owner.items()):
        em = owner_map.get((o or "").strip().lower())
        out.append({"owner": o, "count": len(ctrls), "email": em,
                    "muted": bool(em and em in muted),
                    "controls": [{"control_id": c["control_id"], "name": c["name"], "status": c["status"],
                                  "effectiveness": c["effectiveness"], "days_to_expiry": c.get("days_to_expiry")}
                                 for c in ctrls]})
    return out


async def _run_ci_owner_nudges(org_id, actor="scheduler@obserra"):
    a = await _ci_aggregate(org_id)
    at_risk = _at_risk(a["statuses"])
    if not at_risk:
        return {"at_risk": 0, "emailed": [], "owners": 0, "personalized": 0}
    by_owner = _group_at_risk(at_risk)
    owner_map = await _owner_email_map(org_id, by_owner)
    muted = await _muted_emails(org_id)
    personalized = set()
    for owner, ctrls in by_owner.items():
        em = owner_map.get((owner or "").strip().lower())
        if em and em not in muted:
            await notifications.send_email(
                em, "Your controls need remediation — Obserra Control Intelligence",
                _nudge_owner_html(owner, ctrls))
            personalized.add(em)
    rollup = (await _admin_exec_emails(org_id)) - personalized
    if rollup:
        html = _nudge_html(at_risk, by_owner)
        for em in sorted(rollup):
            await notifications.send_email(em, "Controls need remediation — Obserra Control Intelligence", html)
    emailed = sorted(personalized | rollup)
    try:
        await notifications.create(org_id, "control", "Control remediation reminder sent",
                                   f"{len(at_risk)} at-risk control(s) across {len(by_owner)} owner(s) — "
                                   f"{len(personalized)} owner-specific + rollup to {len(rollup)} recipient(s).",
                                   ref="control-intelligence")
    except Exception:
        pass
    return {"at_risk": len(at_risk), "emailed": emailed, "owners": len(by_owner), "personalized": len(personalized)}


async def _run_ci_owner_nudges_all():
    orgs = await db.organizations.find({}, {"_id": 1}).to_list(1000)
    for org in orgs:
        try:
            await _run_ci_owner_nudges(str(org["_id"]))
        except Exception as e:
            logger.warning(f"CI owner nudges failed for org {org['_id']}: {e}")


def _ci_brief_markdown(a):
    weak = sorted(a["statuses"], key=lambda c: c["effectiveness"])[:10]
    lines = ["## Executive Control Intelligence",
             f"- Control health score: {a['health']}/100",
             f"- Controls: {a['total']}",
             f"- Passing: {a['passing']}",
             f"- Average effectiveness: {a['avg_eff']}%",
             f"- Average maturity: {a['avg_maturity']}/5",
             f"- Control coverage: {a['coverage']}%",
             "", "## Framework Readiness"]
    if a["frameworks"]:
        for f in sorted(a["frameworks"], key=lambda x: -x["coverage"]):
            lines.append(f"- {f['framework']}: {f['coverage']}% coverage, {f['passing']}/{f['controls']} passing")
    else:
        lines.append("- No framework coverage returned.")
    lines += ["", "## Highest Priority Control Gaps"]
    gaps = [c for c in weak if c["status"] != "Passing"] or weak[:5]
    for c in gaps:
        lines.append(f"- [{c['control_id']}] {c['name']}: effectiveness {c['effectiveness']}%, status {c['status']}")
    lines += ["", "## Defensibility",
              "- Control status, effectiveness, maturity, evidence and framework coverage are FACT values from the live Obserra control feed.",
              "- Control health score and coverage roll-ups are MODELLED calculations."]
    return "\n".join(lines)


_BRIEF_ROLES = {"board", "auditor"}
_ROLE_INTRO = {
    "board": "Prepared for the Board — a concise executive view of control assurance, effectiveness and defensibility for this period.",
    "auditor": "Prepared for Audit — control effectiveness, evidence freshness and framework coverage, with FACT and MODELLED source classifications for independent review.",
}
_ROLE_LABEL = {"board": "Board", "auditor": "Auditor"}


def _norm_recipients(raw):
    out, seen = [], set()
    for item in raw or []:
        if isinstance(item, str):
            email, role = item, "board"
        elif isinstance(item, dict):
            email, role = item.get("email", ""), item.get("role", "board")
        else:
            continue
        email = (email or "").strip().lower()
        role = role if role in _BRIEF_ROLES else "board"
        if "@" in email and email not in seen:
            seen.add(email)
            out.append({"email": email, "role": role})
    return out[:50]


async def _muted_emails(org_id):
    now = datetime.now(timezone.utc).isoformat()
    rows = await db.users.find(
        {"org_id": org_id, "$or": [{"ci_nudge_muted": True}, {"ci_nudge_muted_until": {"$gt": now}}]},
        {"_id": 0, "email": 1}).to_list(500)
    return {r["email"] for r in rows if r.get("email")}


async def _brief_role_map(org_id, extra_recipients=None):
    org = await db.organizations.find_one({"_id": ObjectId(org_id)}, {"ci_brief_recipients": 1})
    admins = await db.users.find(
        {"org_id": org_id, "role": {"$in": ["admin", "executive"]}}, {"_id": 0, "email": 1}).to_list(200)
    role_map = {"board": set(), "auditor": set()}
    for r in admins:
        if r.get("email"):
            role_map["board"].add(r["email"])
    for rec in _norm_recipients((org or {}).get("ci_brief_recipients")):
        role_map[rec["role"]].add(rec["email"])
    for e in (extra_recipients or []):
        if e and "@" in e:
            role_map["board"].add(e.strip().lower())
    role_map["auditor"] -= role_map["board"]  # board takes precedence on overlap
    return role_map


async def _run_ci_brief_email(org_id, actor="scheduler@obserra", extra_recipients=None):
    a = await _ci_aggregate(org_id)
    org = await db.organizations.find_one({"_id": ObjectId(org_id)}, {"name": 1, "ci_brief_recipients": 1, "report_branding": 1})
    org_name = (org or {}).get("name") or "Organization"
    md = _ci_brief_markdown(a)
    title = "Control Intelligence Executive Assurance Brief"
    pdf = _build_pdf(md, title, cover=True, org_name=org_name, brand=_resolve_brand(org))
    attachments = [{"filename": "obserra-control-intelligence-assurance-brief.pdf",
                    "content": base64.b64encode(pdf.getvalue()).decode()}]
    role_map = await _brief_role_map(org_id, extra_recipients)
    auditor_link = None
    if role_map["auditor"]:
        try:
            auditor_link = (await _ensure_ci_auditor_link(org_id))["url"]
        except Exception:
            auditor_link = None
    sent, to = 0, []
    for role in ("board", "auditor"):
        emails = role_map[role]
        if not emails:
            continue
        intro = _ROLE_INTRO[role]
        if role == "auditor" and auditor_link:
            intro += f"\n\nVerify this evidence live in Obserra (read-only): {auditor_link}"
        role_md = intro + "\n\n" + md
        html = _report_html(role_md, title)
        subject = f"{title} — Obserra ({_ROLE_LABEL[role]})"
        for em in sorted(emails):
            await notifications.send_email(em, subject, html, attachments=attachments)
            sent += 1
            to.append(em)
    try:
        await notifications.create(org_id, "report", "Executive Assurance Brief emailed",
                                   f"Control Intelligence brief (PDF) emailed to {sent} recipient(s).",
                                   ref="control-intelligence")
    except Exception:
        pass
    return {"sent": sent, "to": sorted(to)}


async def _run_ci_brief_email_all(scheduled=False):
    now = datetime.now(timezone.utc)
    orgs = await db.organizations.find({}).to_list(1000)
    for org in orgs:
        org_id = str(org["_id"])
        try:
            if scheduled:
                if not org.get("ci_brief_enabled"):
                    continue
                cadence = org.get("ci_brief_cadence") or "monthly"
                if cadence == "quarterly" and now.month not in (1, 4, 7, 10):
                    continue
                send_day = max(1, min(28, int(org.get("ci_brief_send_day") or 1)))
                if now.day != send_day:
                    continue
                marker = f"ci-brief:{org_id}:{now.strftime('%Y-%m')}"
                if await db.ci_brief_sent.find_one({"marker": marker}):
                    continue
                await db.ci_brief_sent.insert_one({"marker": marker, "at": now.isoformat()})
            await _run_ci_brief_email(org_id)
        except Exception as e:
            logger.warning(f"CI brief email failed for org {org_id}: {e}")


# ---------------------------------------------------------------- endpoints

class CIBriefSettings(BaseModel):
    recipients: Optional[list] = None
    send_day: Optional[int] = None
    enabled: Optional[bool] = None
    cadence: Optional[str] = None


_BRIEF_CADENCES = {"monthly", "quarterly"}


async def _ci_settings(org_id):
    org = await db.organizations.find_one(
        {"_id": ObjectId(org_id)},
        {"ci_brief_recipients": 1, "ci_brief_send_day": 1, "ci_brief_enabled": 1, "ci_brief_cadence": 1}) or {}
    cadence = org.get("ci_brief_cadence")
    return {"recipients": _norm_recipients(org.get("ci_brief_recipients")),
            "send_day": max(1, min(28, int(org.get("ci_brief_send_day") or 1))),
            "enabled": bool(org.get("ci_brief_enabled", False)),
            "cadence": cadence if cadence in _BRIEF_CADENCES else "monthly"}


@ci_router.get("/settings")
async def get_ci_settings(admin: dict = Depends(require_roles("admin"))):
    return await _ci_settings(admin["org_id"])


@ci_router.put("/settings")
async def set_ci_settings(body: CIBriefSettings, admin: dict = Depends(require_roles("admin"))):
    update = {}
    if body.recipients is not None:
        update["ci_brief_recipients"] = _norm_recipients(body.recipients)
    if body.send_day is not None:
        update["ci_brief_send_day"] = max(1, min(28, int(body.send_day)))
    if body.enabled is not None:
        update["ci_brief_enabled"] = bool(body.enabled)
    if body.cadence is not None:
        update["ci_brief_cadence"] = body.cadence if body.cadence in _BRIEF_CADENCES else "monthly"
    if update:
        await db.organizations.update_one({"_id": ObjectId(admin["org_id"])}, {"$set": update})
    return await _ci_settings(admin["org_id"])


@ci_router.get("/effectiveness-history")
async def effectiveness_history(days: int = 30, user: dict = Depends(get_current_user)):
    org_id = user["org_id"]
    try:
        await _snapshot_org(org_id)  # ensure today's real point exists
    except Exception as e:
        logger.warning(f"on-demand CI snapshot failed: {e}")
    rows = await db.control_eff_history.find({"org_id": org_id}, {"_id": 0}).sort("date", 1).to_list(400)
    days = max(1, min(365, int(days or 30)))
    return {"history": rows[-days:]}


@ci_router.post("/owner-nudges")
async def owner_nudges(admin: dict = Depends(require_roles("admin"))):
    return await _run_ci_owner_nudges(admin["org_id"], actor=admin["email"])


@ci_router.get("/owner-nudges/preview")
async def owner_nudges_preview(demo: bool = False, admin: dict = Depends(require_roles("admin"))):
    org_id = admin["org_id"]
    a = await _ci_aggregate(org_id)
    statuses = a["statuses"]
    if demo:
        from routes import _apply_demo_at_risk
        statuses = _apply_demo_at_risk(statuses)
    at_risk = _at_risk(statuses)
    by_owner = _group_at_risk(at_risk)
    owner_map = await _owner_email_map(org_id, by_owner) if at_risk else {}
    muted = await _muted_emails(org_id) if at_risk else set()
    personalized = {e for e in owner_map.values() if e not in muted}
    rollup = ((await _admin_exec_emails(org_id)) - personalized) if at_risk else set()
    return {"at_risk": len(at_risk), "owners": len(by_owner),
            "recipients": sorted(personalized | rollup),
            "personalized": sorted(personalized),
            "groups": _nudge_groups(by_owner, owner_map, muted), "demo": bool(demo)}


@ci_router.get("/brief/preview")
async def brief_preview(admin: dict = Depends(require_roles("admin"))):
    a = await _ci_aggregate(admin["org_id"])
    md = _ci_brief_markdown(a)
    title = "Control Intelligence Executive Assurance Brief"
    return {"title": title, "markdown": md, "html": _report_html(md, title)}


async def _ensure_ci_auditor_link(org_id, days=90, reissue=False):
    import uuid
    from datetime import timedelta
    now = datetime.now(timezone.utc)
    days = max(1, min(365, int(days or 90)))
    if reissue:
        await db.ci_auditor_links.update_many(
            {"org_id": org_id, "revoked": {"$ne": True}}, {"$set": {"revoked": True}})
        doc = None
    else:
        doc = await db.ci_auditor_links.find_one(
            {"org_id": org_id, "revoked": {"$ne": True}, "expires_at": {"$gt": now.isoformat()}})
    if not doc:
        doc = {"org_id": org_id, "token": uuid.uuid4().hex, "created_at": now.isoformat(),
               "expires_at": (now + timedelta(days=days)).isoformat(), "revoked": False}
        await db.ci_auditor_links.insert_one(dict(doc))
    base = os.environ.get("FRONTEND_URL", "").rstrip("/")
    return {"active": True, "token": doc["token"], "url": f"{base}/ci-audit/{doc['token']}",
            "expires_at": doc["expires_at"]}


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
async def public_auditor_link(token: str):
    from fastapi import HTTPException
    now = datetime.now(timezone.utc)
    doc = await db.ci_auditor_links.find_one({"token": token})
    if not doc or doc.get("revoked") or doc.get("expires_at", "") <= now.isoformat():
        raise HTTPException(status_code=404, detail="This auditor link is invalid or has expired.")
    org_id = doc["org_id"]
    a = await _ci_aggregate(org_id)
    org = await db.organizations.find_one({"_id": ObjectId(org_id)}, {"name": 1})
    weak = sorted(a["statuses"], key=lambda c: c["effectiveness"])[:8]
    try:
        await db.ci_auditor_access.insert_one({"token": token, "org_id": org_id, "kind": "view",
                                               "who": "", "at": now.isoformat()})
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
    return {"board": len(role_map["board"]), "auditor": len(role_map["auditor"]),
            "total": len(role_map["board"]) + len(role_map["auditor"])}


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
    except Exception:
        pass
    return StreamingResponse(io.BytesIO(raw), media_type="application/pdf",
                             headers={"Content-Disposition": 'attachment; filename="obserra-control-assurance-brief.pdf"'})


@ci_router.get("/auditor-link/access")
async def auditor_link_access(limit: int = 25, admin: dict = Depends(require_roles("admin"))):
    limit = max(1, min(200, int(limit or 25)))
    rows = await db.ci_auditor_access.find({"org_id": admin["org_id"]}, {"_id": 0}).sort("at", -1).to_list(limit)
    return {"events": rows}
