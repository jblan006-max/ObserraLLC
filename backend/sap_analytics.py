"""Obserra SAP UAC — Analytics & SoD Risk Watchlist.

Peeled out of sap_uac.py to keep that module from growing. Attaches to the shared sap_router.
Owns: /analytics (+ region/department slice filters), /analytics/export (branded CSV/PDF of the
current slice), and the per-auditor SoD Risk Watchlist (pin/unpin, Critical-threshold nudge alerts,
and one-tap "assign owner + open ServiceNow remediation ticket")."""
import io
import csv
import logging

from fastapi import Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel

from db import db
from auth import get_current_user
from sap_data import SOD_RULES, ROLE_BY_REF
from sap_engine import _now, _correlate, _ensure, _account_flags
from sap_uac import (sap_router, _audit, _ticket_public, _snow_generic,
                     _activation_status, _license_type, _month_labels)

logger = logging.getLogger(__name__)


# ── Analytics ────────────────────────────────────────────────────────────────
async def _analytics_data(org_id, region="", department=""):
    """Aggregate SAP access analytics; optional region/department filters scope every metric."""
    await _ensure(org_id)
    persons, accounts, conflicts, pmap = await _correlate(org_id)
    overrides = {o["person_ref"]: o for o in await db.sap_activation.find({"org_id": org_id}, {"_id": 0}).to_list(5000)}
    all_regions = sorted({p["region"] for p in persons})
    all_departments = sorted({p["department"] for p in persons})
    region, department = (region or "").strip(), (department or "").strip()
    if region:
        persons = [p for p in persons if p["region"] == region]
    if department:
        persons = [p for p in persons if p["department"] == department]
    if region or department:
        keep = {p["ref"] for p in persons}
        accounts = [a for a in accounts if a.get("person_ref") in keep]
        acc_refs = {a["ref"] for a in accounts}
        conflicts = [c for c in conflicts if c.get("account_ref") in acc_refs]
    open_conf = [c for c in conflicts if c.get("status") == "Open"]
    acc_by_person = {}
    for a in accounts:
        if a.get("person_ref"):
            acc_by_person.setdefault(a["person_ref"], []).append(a)
    activated = 0
    lic_map, dept, region_agg, le_map = {}, {}, {}, {}
    saml_mapped = 0
    for p in persons:
        st = _activation_status(p, overrides.get(p["ref"]))
        if st == "Activated":
            activated += 1
        paccs = acc_by_person.get(p["ref"], [])
        primary = next((a for a in paccs if a.get("lock_state") == "unlocked"), paccs[0] if paccs else None)
        lic = _license_type(primary, _account_flags(primary, p)) if primary else "Employee"
        lic_map[lic] = lic_map.get(lic, 0) + 1
        dept[p["department"]] = dept.get(p["department"], 0) + 1
        region_agg[p["region"]] = region_agg.get(p["region"], 0) + 1
        le_map[p["legal_entity"]] = le_map.get(p["legal_entity"], 0) + 1
        if p.get("email"):
            saml_mapped += 1
    total = len(persons)
    usage = {}
    for a in accounts:
        for r in a.get("roles", []):
            usage[r] = usage.get(r, 0) + 1
    top_roles = sorted(({"name": ROLE_BY_REF.get(r, {}).get("name", r), "value": v, "privileged": bool(ROLE_BY_REF.get(r, {}).get("privileged"))}
                        for r, v in usage.items()), key=lambda x: -x["value"])[:10]
    sod_area = {}
    for c in open_conf:
        sod_area[c["area"]] = sod_area.get(c["area"], 0) + 1
    events = await db.sap_activation_events.find({"org_id": org_id}, {"_id": 0}).to_list(5000)
    trend = []
    for key, label in _month_labels(6):
        act = sum(1 for p in persons if (p.get("hire_date") or "").startswith(key)) + sum(1 for e in events if e.get("action") == "activate" and (e.get("at") or "").startswith(key))
        deact = sum(1 for p in persons if (p.get("termination_date") or "").startswith(key)) + sum(1 for e in events if e.get("action") == "deactivate" and (e.get("at") or "").startswith(key))
        trend.append({"month": label, "activated": act, "deactivated": deact})
    top_risk = sorted(persons, key=lambda p: -p["risk"]["score"])[:8]
    return {
        "kpis": {
            "identities": total, "accounts": len(accounts), "activated": activated,
            "deactivated": total - activated, "license_usage_pct": round(activated / total * 100) if total else 0,
            "avg_risk": round(sum(p["risk"]["score"] for p in persons) / total) if total else 0,
            "open_sod": len(open_conf), "critical_sod": sum(1 for c in open_conf if c["severity"] == "Critical"),
            "privileged": sum(1 for a in accounts if a["flags"]["privileged"]),
            "sap_all": sum(1 for a in accounts if a["flags"]["sap_all"]),
            "dormant": sum(1 for a in accounts if a["flags"]["dormant"]),
            "orphan": sum(1 for a in accounts if a["flags"]["orphan"]),
            "terminated_residual": sum(1 for p in persons if p["status"] == "Terminated" and any(x.get("lock_state") == "unlocked" for x in acc_by_person.get(p["ref"], []))),
            "saml_coverage_pct": round(saml_mapped / total * 100) if total else 0,
        },
        "license_breakdown": sorted(({"name": k, "value": v} for k, v in lic_map.items()), key=lambda x: -x["value"]),
        "by_department": sorted(({"name": k, "value": v} for k, v in dept.items()), key=lambda x: -x["value"]),
        "by_region": [{"name": k, "value": v} for k, v in region_agg.items()],
        "by_legal_entity": sorted(({"name": k, "value": v} for k, v in le_map.items()), key=lambda x: -x["value"]),
        "top_roles": top_roles, "sod_by_area": sorted(({"name": k, "value": v} for k, v in sod_area.items()), key=lambda x: -x["value"]),
        "trend": trend, "risk_distribution": {r: sum(1 for p in persons if p["risk"]["rating"] == r) for r in ["Critical", "High", "Medium", "Low"]},
        "top_risk": [{"ref": p["ref"], "name": p["name"], "department": p["department"], "score": p["risk"]["score"], "rating": p["risk"]["rating"]} for p in top_risk],
        "filters": {"regions": all_regions, "departments": all_departments, "region": region, "department": department},
        "generated_at": _now().isoformat(),
    }


@sap_router.get("/analytics")
async def analytics(region: str = "", department: str = "", user: dict = Depends(get_current_user)):
    """SAP access analytics / metrics — aggregated live, optionally scoped to a region/department slice."""
    return await _analytics_data(user["org_id"], region, department)


# ── Analytics export (branded CSV / PDF of the current slice) ─────────────────
def _analytics_csv(d, slice_label):
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["Obserra SAP UAC — Access Analytics Export"])
    w.writerow(["Slice", slice_label])
    w.writerow(["Generated", d["generated_at"]])
    w.writerow([])
    w.writerow(["KPI", "Value"])
    for k, v in d["kpis"].items():
        w.writerow([k.replace("_", " ").title(), v])
    for title, key in [("License breakdown", "license_breakdown"), ("By department", "by_department"),
                       ("By region", "by_region"), ("By legal entity", "by_legal_entity"),
                       ("Top roles", "top_roles"), ("Open SoD by area", "sod_by_area")]:
        w.writerow([])
        w.writerow([title, "Count"])
        for row in d[key]:
            w.writerow([row["name"], row["value"]])
    w.writerow([])
    w.writerow(["Top risk identities", "Department", "Risk score", "Rating"])
    for r in d["top_risk"]:
        w.writerow([r["name"], r["department"], r["score"], r["rating"]])
    return buf.getvalue().encode()


def _analytics_pdf(d, slice_label, actor):
    from reportlab.lib.pagesizes import LETTER
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=LETTER, topMargin=42, bottomMargin=40, leftMargin=42, rightMargin=42,
                            title="SAP Access Analytics")
    ss = getSampleStyleSheet()
    navy = colors.HexColor("#0f1e3d")
    h1 = ParagraphStyle("h1", parent=ss["Title"], fontSize=18, textColor=colors.white, spaceAfter=2)
    sub = ParagraphStyle("sub", parent=ss["Normal"], fontSize=9, textColor=colors.HexColor("#c7d2fe"))
    sec = ParagraphStyle("sec", parent=ss["Heading2"], fontSize=12, textColor=navy, spaceBefore=14, spaceAfter=6)
    small = ParagraphStyle("small", parent=ss["Normal"], fontSize=9, textColor=colors.HexColor("#6b7280"))

    header = Table([[Paragraph("OBSERRA — SAP Access Analytics", h1)],
                    [Paragraph(f"Slice: {slice_label}  ·  Generated {d['generated_at'][:19].replace('T', ' ')} UTC  ·  by {actor}", sub)]],
                   colWidths=[doc.width])
    header.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), navy), ("LEFTPADDING", (0, 0), (-1, -1), 14),
                                ("RIGHTPADDING", (0, 0), (-1, -1), 14), ("TOPPADDING", (0, 0), (0, 0), 12),
                                ("BOTTOMPADDING", (-1, -1), (-1, -1), 12)]))
    elems = [header, Spacer(1, 14)]

    kpi = d["kpis"]
    kpi_rows = [("Identities", kpi["identities"]), ("Accounts", kpi["accounts"]), ("Activated", kpi["activated"]),
                ("License usage %", kpi["license_usage_pct"]), ("Avg risk score", kpi["avg_risk"]),
                ("Open SoD", kpi["open_sod"]), ("Critical SoD", kpi["critical_sod"]), ("Privileged", kpi["privileged"]),
                ("SAP_ALL holders", kpi["sap_all"]), ("Dormant", kpi["dormant"]), ("Orphan", kpi["orphan"]),
                ("Terminated w/ access", kpi["terminated_residual"])]
    grid = [[Paragraph(f"<b>{v}</b>", ss["Normal"]), Paragraph(lbl, small)] for lbl, v in kpi_rows]
    packed = [grid[i] + (grid[i + 1] if i + 1 < len(grid) else ["", ""]) for i in range(0, len(grid), 2)]
    t = Table(packed, colWidths=[doc.width * 0.12, doc.width * 0.38, doc.width * 0.12, doc.width * 0.38])
    t.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#e5e7eb")),
                           ("INNERGRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#eef0f4")),
                           ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("TOPPADDING", (0, 0), (-1, -1), 6),
                           ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]))
    elems += [Paragraph("Key metrics", sec), t]

    def _tbl(title, rows, headers):
        if not rows:
            return
        elems.append(Paragraph(title, sec))
        data = [headers] + rows
        tt = Table(data, colWidths=[doc.width * (0.55 if len(headers) == 2 else 0.4)] + [doc.width * (0.45 / (len(headers) - 1))] * (len(headers) - 1))
        tt.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), navy), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                                ("FONTSIZE", (0, 0), (-1, -1), 9), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                                ("TOPPADDING", (0, 0), (-1, -1), 5),
                                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f7f8fa")]),
                                ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#e5e7eb"))]))
        elems.append(tt)

    _tbl("Open SoD conflicts by area", [[r["name"], r["value"]] for r in d["sod_by_area"]], ["Business area", "Open"])
    _tbl("Identities by department", [[r["name"], r["value"]] for r in d["by_department"]], ["Department", "Identities"])
    _tbl("Identities by region", [[r["name"], r["value"]] for r in d["by_region"]], ["Region", "Identities"])
    _tbl("Top roles by usage", [[r["name"], r["value"]] for r in d["top_roles"]], ["Role", "Assignments"])
    _tbl("Highest-risk identities", [[r["name"], r["department"], r["score"], r["rating"]] for r in d["top_risk"]],
         ["Identity", "Department", "Score", "Rating"])
    elems += [Spacer(1, 16), Paragraph("Obserra SAP UAC — SAP User Access Control & Access Intelligence. "
                                       "Figures reflect the live access model at generation time.", small)]
    doc.build(elems)
    return buf.getvalue()


@sap_router.get("/analytics/export")
async def analytics_export(region: str = "", department: str = "", format: str = "csv",
                           user: dict = Depends(get_current_user)):
    """Download the currently-filtered analytics slice as a branded CSV or PDF review pack."""
    org_id = user["org_id"]
    d = await _analytics_data(org_id, region, department)
    slice_label = " · ".join([x for x in [region.strip(), department.strip()] if x]) or "All regions & departments"
    ts = _now().strftime("%Y%m%d-%H%M")
    if format == "pdf":
        content = _analytics_pdf(d, slice_label, user["email"])
        await _audit(org_id, user["email"], "sap.analytics.export", f"PDF · {slice_label}")
        return Response(content=content, media_type="application/pdf",
                        headers={"Content-Disposition": f'attachment; filename="sap-analytics-{ts}.pdf"'})
    content = _analytics_csv(d, slice_label)
    await _audit(org_id, user["email"], "sap.analytics.export", f"CSV · {slice_label}")
    return Response(content=content, media_type="text/csv",
                    headers={"Content-Disposition": f'attachment; filename="sap-analytics-{ts}.csv"'})


# ── SoD Risk Watchlist (per-user pinned business areas — hot spots first) ─────
_SOD_AREAS = sorted({r["area"] for r in SOD_RULES})


def _wl_key(user):
    return user.get("email") or user.get("id") or "anon"


async def _area_stats(org_id):
    """Live open-SoD-conflict counts (with severity split) per business area."""
    _, _, conflicts, _ = await _correlate(org_id)
    stats = {a: {"area": a, "open": 0, "Critical": 0, "High": 0, "Medium": 0, "Low": 0} for a in _SOD_AREAS}
    for c in conflicts:
        if c.get("status") != "Open":
            continue
        s = stats.setdefault(c["area"], {"area": c["area"], "open": 0, "Critical": 0, "High": 0, "Medium": 0, "Low": 0})
        s["open"] += 1
        s[c["severity"]] = s.get(c["severity"], 0) + 1
    return stats


@sap_router.get("/watchlist")
async def get_watchlist(user: dict = Depends(get_current_user)):
    """The signed-in auditor's pinned SoD areas (hottest first, with alert/owner/ticket metadata) +
    all available areas to pin."""
    org_id = user["org_id"]
    await _ensure(org_id)
    stats = await _area_stats(org_id)
    docs = await db.sap_watchlist.find({"org_id": org_id, "user": _wl_key(user)}, {"_id": 0}).to_list(100)
    dmap = {d["area"]: d for d in docs}
    pinned = []
    for area, doc in dmap.items():
        s = stats.get(area)
        if not s:
            continue
        pinned.append({**s, "alert": bool(doc.get("alert")), "threshold": int(doc.get("threshold", 1) or 1),
                       "owner": doc.get("owner", ""), "ticket": doc.get("ticket")})
    pinned.sort(key=lambda s: (-s["Critical"], -s["open"], s["area"]))
    available = sorted(stats.values(), key=lambda s: (-s["open"], s["area"]))
    return {"pinned": pinned, "available": [{**s, "pinned": s["area"] in dmap} for s in available]}


class WatchlistBody(BaseModel):
    area: str


@sap_router.post("/watchlist")
async def pin_watchlist(body: WatchlistBody, user: dict = Depends(get_current_user)):
    area = body.area.strip()
    if area not in _SOD_AREAS:
        raise HTTPException(status_code=404, detail="Unknown SoD area")
    key = _wl_key(user)
    await db.sap_watchlist.update_one(
        {"org_id": user["org_id"], "user": key, "area": area},
        {"$setOnInsert": {"org_id": user["org_id"], "user": key, "area": area},
         "$set": {"at": _now().isoformat()}}, upsert=True)
    return await get_watchlist(user)


@sap_router.delete("/watchlist")
async def unpin_watchlist(area: str, user: dict = Depends(get_current_user)):
    await db.sap_watchlist.delete_one({"org_id": user["org_id"], "user": _wl_key(user), "area": area.strip()})
    return await get_watchlist(user)


# ── Watchlist Critical-threshold nudge alerts ─────────────────────────────────
class WatchlistAlertBody(BaseModel):
    area: str
    alert: bool
    threshold: int = 1


@sap_router.post("/watchlist/alert")
async def set_watchlist_alert(body: WatchlistAlertBody, user: dict = Depends(get_current_user)):
    """Enable/disable a nudge to the area owner when open Critical conflicts reach the threshold.
    Enabling also pins the area."""
    area = body.area.strip()
    if area not in _SOD_AREAS:
        raise HTTPException(status_code=404, detail="Unknown SoD area")
    key = _wl_key(user)
    await db.sap_watchlist.update_one(
        {"org_id": user["org_id"], "user": key, "area": area},
        {"$setOnInsert": {"org_id": user["org_id"], "user": key, "area": area},
         "$set": {"alert": bool(body.alert), "threshold": max(1, int(body.threshold or 1)), "at": _now().isoformat()},
         "$unset": {"alert_week": ""}}, upsert=True)
    return await get_watchlist(user)


def _watchlist_alert_html(area, s, thr, owner):
    chips = " ".join(f'<b style="color:#b91c1c">{s[k]}</b> {k}' for k in ("Critical", "High", "Medium", "Low") if s[k])
    return (
        '<table width="100%" cellpadding="0" cellspacing="0" style="max-width:600px;margin:auto;background:#fff">'
        '<tr><td style="padding:24px">'
        '<div style="font:800 18px Arial;color:#0f1e3d">SAP SoD hot spot on your watchlist</div>'
        '<div style="font:400 12px Arial;color:#6b7280;margin-bottom:14px">Obserra SAP UAC — SAP Access Governance</div>'
        f'<div style="font:700 15px Arial;color:#b91c1c;margin-bottom:6px">{area} — {s["Critical"]} open Critical SoD conflict(s)</div>'
        f'<div style="font:400 13px Arial;color:#1f2937;margin-bottom:8px">This crossed your alert threshold of {thr} Critical. '
        f'Total open conflicts in this area: <b>{s["open"]}</b>. Breakdown: {chips or "—"}.</div>'
        f'<div style="font:400 12px Arial;color:#6b7280">Owner: {owner or "unassigned"}.</div>'
        '<div style="border-top:1px solid #e5e7eb;margin-top:16px;padding-top:10px;font:400 10px Arial;color:#9ca3af">'
        'Sign in to Obserra SAP UAC → SoD Command Center to assign an owner and open a remediation ticket.</div>'
        '</td></tr></table>')


async def run_sap_watchlist_alerts():
    """Daily sweep: nudge pinned-area owners (email + in-app) when open Critical conflicts reach
    their threshold. One nudge per ISO week while breached; auto-resets when it clears."""
    from kernel import notifications
    week = _now().strftime("%G-W%V")
    orgs = await db.organizations.find({}).to_list(1000)
    for org in orgs:
        org_id = str(org["_id"])
        try:
            docs = await db.sap_watchlist.find({"org_id": org_id, "alert": True}).to_list(500)
            if not docs:
                continue
            stats = await _area_stats(org_id)
            for doc in docs:
                s = stats.get(doc["area"])
                if not s:
                    continue
                thr = max(1, int(doc.get("threshold", 1) or 1))
                if s["Critical"] < thr:
                    if doc.get("alert_week"):
                        await db.sap_watchlist.update_one({"_id": doc["_id"]}, {"$unset": {"alert_week": ""}})
                    continue
                if doc.get("alert_week") == week:
                    continue
                owner = (doc.get("owner") or doc.get("user") or "").strip()
                html = _watchlist_alert_html(doc["area"], s, thr, owner)
                if owner and "@" in owner:
                    await notifications.send_email(owner, f"SAP SoD hot spot — {doc['area']} ({s['Critical']} Critical)", html)
                await db.sap_watchlist.update_one(
                    {"_id": doc["_id"]}, {"$set": {"alert_week": week, "last_alert_at": _now().isoformat()}})
                await notifications.create(
                    org_id, "sap", "SoD watchlist alert",
                    f"{doc['area']}: {s['Critical']} open Critical (≥{thr}) — nudged {owner or 'owner'}.",
                    ref="sap-watchlist-alert")
            logger.info(f"Watchlist alerts swept for org {org_id}")
        except Exception as e:
            logger.error(f"Watchlist alerts failed for org {org_id}: {e}")


# ── One-tap: assign owner + open a ServiceNow remediation ticket for an area ───
class WatchlistRemediateBody(BaseModel):
    area: str
    owner: str = ""


@sap_router.post("/watchlist/remediate")
async def remediate_watchlist_area(body: WatchlistRemediateBody, user: dict = Depends(get_current_user)):
    """Assign an owner and open a ServiceNow-orchestrated remediation change for every open SoD
    conflict in the area — turning a spotted hot spot into an accountable, tracked ticket in one tap."""
    org_id = user["org_id"]
    area = body.area.strip()
    if area not in _SOD_AREAS:
        raise HTTPException(status_code=404, detail="Unknown SoD area")
    stats = await _area_stats(org_id)
    s = stats.get(area, {"area": area, "open": 0, "Critical": 0})
    owner = body.owner.strip()
    steps = [
        ("ServiceNow", f"SoD remediation change opened for business area: {area}"),
        ("ServiceNow", f"Assigned to {owner or 'SoD remediation queue'} · requested by {user['email']}"),
        ("SAP", f"Reviewing {s['open']} open SoD conflict(s) in {area} — removing one side of each toxic role pair or applying a monitored mitigating control"),
        ("ServiceNow", "Remediation task created and owner assigned; tracked until all conflicts clear"),
    ]
    ticket = await _snow_generic(
        org_id, f"SAP SoD Remediation — {area}", "sod_area_remediate", steps, user["email"], prefix="CHG",
        person_name=(owner or None), email=(owner if "@" in owner else None),
        reason=f"Remediate {s['open']} SoD conflict(s) in {area}",
        work_note=f"Owner: {owner or 'unassigned'} · {s['Critical']} Critical")
    tinfo = {"number": ticket["number"], "state": ticket["state"], "type": ticket["type"],
             "owner": owner, "at": _now().isoformat()}
    key = _wl_key(user)
    await db.sap_watchlist.update_one(
        {"org_id": org_id, "user": key, "area": area},
        {"$setOnInsert": {"org_id": org_id, "user": key, "area": area},
         "$set": {"owner": owner, "ticket": tinfo, "at": _now().isoformat()}}, upsert=True)
    await _audit(org_id, user["email"], "sap.watchlist.remediate",
                 f"{area} · {ticket['number']} · owner {owner or '—'}")
    return {"ok": True, "ticket": _ticket_public(ticket), "owner": owner, "area": area,
            "watchlist": await get_watchlist(user)}
