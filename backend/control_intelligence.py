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
    now_iso = datetime.now(timezone.utc).isoformat()
    owners = {(c.get("owner") or "Unassigned") for c in a["statuses"]}
    for owner in owners:
        sc = _owner_scorecard(a["statuses"], owner)
        await db.ci_owner_eff_history.update_one(
            {"org_id": org_id, "owner": owner, "date": today},
            {"$set": {"org_id": org_id, "owner": owner, "date": today, "avg_eff": sc["avg_eff"],
                      "total": sc["total"], "passing": sc["passing"], "at_risk": sc["at_risk"],
                      "ts": now_iso}}, upsert=True)
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


def _nudge_owner_html(owner, ctrls, scorecard_html=""):
    items = "".join(
        f"<li><strong>{c['control_id']}</strong> {c['name']} — {c['status']}, "
        f"effectiveness {c['effectiveness']}%"
        + (f", evidence expires in {c['days_to_expiry']}d" if c.get('days_to_expiry') is not None else "")
        + "</li>" for c in ctrls)
    return (f"<div style='font:400 14px Arial;color:#1f2937;max-width:640px;margin:auto'>"
            f"<h2 style='color:#0f1e3d'>Your controls need attention</h2>"
            f"<p>Hi {owner}, {len(ctrls)} control(s) you own need remediation. Here is exactly what to pick up:</p>"
            f"{scorecard_html}"
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
            sc = _owner_scorecard(a["statuses"], owner)
            trend = await _owner_trend(org_id, owner)
            await notifications.send_email(
                em, "Your controls need remediation — Obserra Control Intelligence",
                _nudge_owner_html(owner, ctrls, _scorecard_html(sc, trend)))
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


def _owner_scorecard(statuses, owner):
    own = [c for c in statuses if (c.get("owner") or "Unassigned") == owner]
    total = len(own)
    passing = sum(1 for c in own if c["status"] == "Passing")
    avg_eff = round(sum(c["effectiveness"] for c in own) / total) if total else 0
    at_risk = len([c for c in own
                   if c["status"] != "Passing" or c.get("days_to_expiry", 999) <= 14 or c.get("drift")])
    return {"total": total, "passing": passing, "avg_eff": avg_eff, "at_risk": at_risk}


def _sparkline(values):
    if not values:
        return ""
    blocks = "\u2581\u2582\u2583\u2584\u2585\u2586\u2587\u2588"
    lo, hi = min(values), max(values)
    rng = (hi - lo) or 1
    return "".join(blocks[min(7, int((v - lo) / rng * 7))] for v in values)


async def _owner_trend(org_id, owner, days=14):
    rows = await db.ci_owner_eff_history.find(
        {"org_id": org_id, "owner": owner}, {"_id": 0, "date": 1, "avg_eff": 1}).sort("date", 1).to_list(400)
    return rows[-days:]


def _scorecard_html(sc, trend):
    if trend and len(trend) >= 2:
        spark = _sparkline([r["avg_eff"] for r in trend])
        d = int(trend[-1]["avg_eff"] - trend[0]["avg_eff"])
        color = "#15803d" if d > 0 else ("#b91c1c" if d < 0 else "#6b7280")
        arrow = "\u25b2" if d > 0 else ("\u25bc" if d < 0 else "\u25ac")
        trend_cell = (f"<span style='font-size:15px;letter-spacing:1px'>{spark}</span> "
                      f"<span style='color:{color}'>{arrow} {d:+d} pts over {len(trend)} days</span>")
    else:
        trend_cell = "<span style='color:#9ca3af'>builds daily \u2014 check back tomorrow</span>"

    def row(k, v):
        return (f"<tr><td style='padding:3px 12px 3px 0;color:#6b7280'>{k}</td>"
                f"<td style='padding:3px 0'><strong>{v}</strong></td></tr>")

    return ("<table style='border-collapse:collapse;margin:6px 0 14px;font:400 13px Arial'>"
            + row("Your controls", sc["total"])
            + row("Passing", f"{sc['passing']}/{sc['total']}")
            + row("Avg effectiveness", f"{sc['avg_eff']}%")
            + row("At-risk now", sc["at_risk"])
            + "<tr><td style='padding:3px 12px 3px 0;color:#6b7280'>Effectiveness trend</td>"
              f"<td style='padding:3px 0'>{trend_cell}</td></tr>"
            + "</table>")


async def _auditor_engagement(org_id, days=30):
    from datetime import timedelta
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    rows = await db.ci_auditor_access.find(
        {"org_id": org_id, "at": {"$gt": since}}, {"_id": 0, "kind": 1, "who": 1}).to_list(5000)
    views = sum(1 for r in rows if r.get("kind") == "view")
    downloads = sum(1 for r in rows if r.get("kind") == "download")
    reviewers = sorted({(r.get("who") or "").strip() for r in rows
                        if r.get("kind") == "download" and (r.get("who") or "").strip()})
    return {"views": views, "downloads": downloads, "reviewers": reviewers, "days": days}


def _engagement_section(eng):
    days = (eng or {}).get("days", 30)
    if not eng or (not eng["views"] and not eng["downloads"]):
        return f"\n\n## External Assurance Activity\n- No external auditor engagement recorded in the last {days} days."
    rv = eng["reviewers"]
    lines = ["", "", "## External Assurance Activity",
             f"- Auditor portal views (last {days}d): {eng['views']}",
             f"- Signed-PDF downloads (last {days}d): {eng['downloads']}"
             + (f" by {len(rv)} named reviewer(s)" if rv else "")]
    if rv:
        lines.append(f"- Named reviewers: {', '.join(rv)}")
    return "\n".join(lines)



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
    md += _engagement_section(await _auditor_engagement(org_id))
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
    drop_days: Optional[int] = None
    ask_name: Optional[bool] = None


_BRIEF_CADENCES = {"monthly", "quarterly"}


async def _ci_settings(org_id):
    org = await db.organizations.find_one(
        {"_id": ObjectId(org_id)},
        {"ci_brief_recipients": 1, "ci_brief_send_day": 1, "ci_brief_enabled": 1, "ci_brief_cadence": 1,
         "ci_nudge_drop_days": 1, "ci_auditor_ask_name": 1}) or {}
    cadence = org.get("ci_brief_cadence")
    return {"recipients": _norm_recipients(org.get("ci_brief_recipients")),
            "send_day": max(1, min(28, int(org.get("ci_brief_send_day") or 1))),
            "enabled": bool(org.get("ci_brief_enabled", False)),
            "cadence": cadence if cadence in _BRIEF_CADENCES else "monthly",
            "drop_days": 3 if int(org.get("ci_nudge_drop_days") or 2) == 3 else 2,
            "ask_name": bool(org.get("ci_auditor_ask_name", False))}


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
    if body.drop_days is not None:
        update["ci_nudge_drop_days"] = 3 if int(body.drop_days) == 3 else 2
    if body.ask_name is not None:
        update["ci_auditor_ask_name"] = bool(body.ask_name)
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
    md = _ci_brief_markdown(a) + _engagement_section(await _auditor_engagement(admin["org_id"]))
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
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    rows = await db.ci_auditor_access.find(
        {"org_id": org_id, "at": {"$gt": since}}, {"_id": 0, "kind": 1, "who": 1}).to_list(5000)
    views = sum(1 for r in rows if r.get("kind") == "view")
    downloads = sum(1 for r in rows if r.get("kind") == "download")
    reviewers = sorted({(r.get("who") or "").strip() for r in rows
                        if r.get("kind") == "download" and (r.get("who") or "").strip()})
    return {"views": views, "downloads": downloads, "reviewers": reviewers, "days": days, "events": len(rows)}


@ci_router.get("/auditor-link/recap/preview")
async def auditor_recap_preview(days: int = 7, admin: dict = Depends(require_roles("admin"))):
    days = max(1, min(90, int(days or 7)))
    return await _auditor_recap_payload(admin["org_id"], days)


def _recap_html(org_name, rec):
    rv = rec["reviewers"]
    return (f"<div style='font:400 14px Arial;color:#1f2937;max-width:620px;margin:auto'>"
            f"<h2 style='color:#0f1e3d'>Weekly assurance recap \u2014 {org_name}</h2>"
            f"<p>External auditor engagement over the last {rec['days']} days:</p>"
            f"<ul><li><strong>{rec['views']}</strong> portal view(s)</li>"
            f"<li><strong>{rec['downloads']}</strong> signed-PDF download(s)</li>"
            f"<li><strong>{len(rv)}</strong> named reviewer(s){(': ' + ', '.join(rv)) if rv else ''}</li></ul>"
            f"<p style='font-size:11px;color:#9ca3af'>Obserra Control Intelligence \u2014 weekly assurance recap.</p></div>")


async def _run_ci_weekly_assurance_recap_all():
    now = datetime.now(timezone.utc)
    week = now.strftime("%Y-%W")
    orgs = await db.organizations.find({}, {"_id": 1, "name": 1}).to_list(1000)
    for org in orgs:
        org_id = str(org["_id"])
        try:
            rec = await _auditor_recap_payload(org_id, 7)
            if not (rec["views"] or rec["downloads"]):
                continue
            marker = f"ci-recap:{org_id}:{week}"
            if await db.ci_sent_markers.find_one({"marker": marker}):
                continue
            emails = sorted(await _admin_exec_emails(org_id))
            if not emails:
                continue
            html = _recap_html(org.get("name") or "Organization", rec)
            for em in emails:
                try:
                    await notifications.send_email(em, f"Weekly assurance recap \u2014 {org.get('name') or 'Organization'}", html)
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
    org = await db.organizations.find_one({"_id": ObjectId(org_id)}, {"name": 1})
    org_name = (org or {}).get("name") or "Organization"
    emails = sorted(await _admin_exec_emails(org_id))
    if not emails:
        raise HTTPException(status_code=400, detail="No admin/executive recipients to send to.")
    html = _recap_html(org_name, rec)
    sent = 0
    for em in emails:
        try:
            await notifications.send_email(em, f"Assurance recap ({days}d) \u2014 {org_name}", html)
            sent += 1
        except Exception:
            pass
    return {"sent": sent, "to": emails, "recap": rec}


@ci_router.get("/auditor-link/activity")
async def auditor_activity(days: int = 30, user: dict = Depends(require_roles("admin", "executive"))):
    days = max(1, min(90, int(days or 30)))
    rec = await _auditor_engagement(user["org_id"], days)
    return {"views": rec["views"], "downloads": rec["downloads"],
            "reviewers": len(rec["reviewers"]), "days": days}
