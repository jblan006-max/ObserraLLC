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
    recap_enabled: Optional[bool] = None
    recap_weekday: Optional[int] = None


_BRIEF_CADENCES = {"monthly", "quarterly"}


async def _ci_settings(org_id):
    org = await db.organizations.find_one(
        {"_id": ObjectId(org_id)},
        {"ci_brief_recipients": 1, "ci_brief_send_day": 1, "ci_brief_enabled": 1, "ci_brief_cadence": 1,
         "ci_nudge_drop_days": 1, "ci_auditor_ask_name": 1, "ci_recap_enabled": 1, "ci_recap_weekday": 1}) or {}
    cadence = org.get("ci_brief_cadence")
    return {"recipients": _norm_recipients(org.get("ci_brief_recipients")),
            "send_day": max(1, min(28, int(org.get("ci_brief_send_day") or 1))),
            "enabled": bool(org.get("ci_brief_enabled", False)),
            "cadence": cadence if cadence in _BRIEF_CADENCES else "monthly",
            "drop_days": 3 if int(org.get("ci_nudge_drop_days") or 2) == 3 else 2,
            "ask_name": bool(org.get("ci_auditor_ask_name", False)),
            "recap_enabled": bool(org.get("ci_recap_enabled", False)),
            "recap_weekday": max(0, min(6, int(org.get("ci_recap_weekday") or 0)))}


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
    if body.recap_enabled is not None:
        update["ci_recap_enabled"] = bool(body.recap_enabled)
    if body.recap_weekday is not None:
        update["ci_recap_weekday"] = max(0, min(6, int(body.recap_weekday)))
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
