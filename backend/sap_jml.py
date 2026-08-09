"""Obserra SAP UAC — Joiner/Mover/Leaver lifecycle + Mover Auto-Strip rule (attached to the shared sap_router)."""
from datetime import datetime, timedelta

from fastapi import Depends, HTTPException
from pydantic import BaseModel

from db import db
from auth import get_current_user, require_roles
from sap_data import ROLE_CATALOG, ROLE_BY_REF
from sap_engine import _now, _correlate, _ensure, _hr_conflicts_for
from sap_uac import sap_router, _snow_generic, _audit, _ticket_public


@sap_router.get("/jml")
async def jml(user: dict = Depends(get_current_user)):
    org_id = user["org_id"]
    await _ensure(org_id)
    if (await _get_mover_rule(org_id))["enabled"]:
        await _run_mover_autostrip(org_id, "auto-rule")
    persons, accounts, conflicts, pmap = await _correlate(org_id)
    joiners, movers, leavers = [], [], []
    for p in persons:
        try:
            hired_days = (_now() - datetime.fromisoformat(p["hire_date"])).days
        except Exception:
            hired_days = 999
        unlocked = [a for a in p["accounts"] if a.get("lock_state") == "unlocked"]
        if p["status"] == "Active" and hired_days <= 21:
            joiners.append({"ref": p["ref"], "name": p["name"], "department": p["department"],
                            "hire_date": p["hire_date"], "accounts": len(p["accounts"]),
                            "provisioned": len(p["accounts"]) > 0, "hr_authority": p["hr_authority"]})
        if p["status"] == "Terminated" and unlocked:
            leavers.append({"ref": p["ref"], "name": p["name"], "department": p["department"],
                            "termination_date": p.get("termination_date"),
                            "residual_accounts": len(unlocked), "ad_enabled": p.get("ad_enabled"),
                            "score": p["risk"]["score"], "rating": p["risk"]["rating"],
                            "severity": "Critical"})
        if p["status"] == "Active":
            transfers = [c for c in _hr_conflicts_for(p)
                         if c["field"] in ("legal_entity", "manager", "job_title", "worker_type")]
            if transfers:
                acct_roles = sorted({r for a in p["accounts"] for r in a.get("roles", [])})
                birthright = {rc["ref"] for rc in ROLE_CATALOG if rc.get("dept") == p["department"]}
                current_roles = [{"ref": r, "name": ROLE_BY_REF.get(r, {}).get("name", r)} for r in acct_roles]
                carried_over = [cr for cr in current_roles if cr["ref"] not in birthright]
                movers.append({"ref": p["ref"], "name": p["name"], "department": p["department"],
                               "hr_authority": p["hr_authority"], "accounts": len(p["accounts"]),
                               "roles": sum(len(a.get("roles", [])) for a in p["accounts"]),
                               "score": p["risk"]["score"], "rating": p["risk"]["rating"],
                               "changes": [{"field": c["field"], "from": c["adp_value"], "to": c["iz8_value"],
                                            "authoritative": c["authoritative_value"]} for c in transfers],
                               "current_roles": current_roles,
                               "birthright_roles": [{"ref": rc["ref"], "name": rc["name"]} for rc in ROLE_CATALOG if rc.get("dept") == p["department"]],
                               "carried_over": carried_over, "carried_over_count": len(carried_over)})
    leavers.sort(key=lambda x: -x["score"])
    movers.sort(key=lambda x: -x["score"])
    return {"joiners": joiners, "movers": movers, "leavers": leavers,
            "counts": {"joiners": len(joiners), "movers": len(movers), "leavers": len(leavers)}}


class MoverStripBody(BaseModel):
    reason: str = ""


async def _strip_carried_over(org_id, p, by, reason=""):
    """Strip every non-birthright (carried-over) role from a mover's accounts and open a
    ServiceNow -> HR -> SAP least-privilege change. Returns None when there's nothing to strip."""
    birthright = {rc["ref"] for rc in ROLE_CATALOG if rc.get("dept") == p["department"]}
    acct_roles = sorted({r for a in p["accounts"] for r in a.get("roles", [])})
    carried = [r for r in acct_roles if r not in birthright]
    if not carried:
        return None
    for a in p["accounts"]:
        await db.sap_accounts.update_one({"org_id": org_id, "ref": a["ref"]}, {"$pull": {"roles": {"$in": carried}}})
    hr = p.get("hr_authority", "ADP")
    names = [ROLE_BY_REF.get(r, {}).get("name", r) for r in carried]
    steps = [
        ("ServiceNow", f"Mover access-cleanup change opened for {p['name']}"),
        ("ServiceNow", f"Auto-approved (least privilege / transfer) - {by}"),
        (hr, "Recording transfer & access change against worker record"),
        ("SAP", f"Stripping carried-over roles: {', '.join(names)}"),
        ("ServiceNow", "Carried-over access removed; SoD re-evaluated; change closed"),
    ]
    ticket = await _snow_generic(org_id, "SAP Mover Access Cleanup", "mover_strip", steps, by, prefix="CHG",
                                 person_ref=p["ref"], person_name=p["name"], email=p.get("email"),
                                 hr_system=hr, reason=f"Strip {len(carried)} carried-over role(s) from {p['name']}",
                                 work_note=reason)
    await _audit(org_id, by, "sap.mover.strip_carried_over", f"{p['ref']} - stripped {', '.join(carried)} - {ticket['number']}")
    return {"stripped": carried, "stripped_names": names, "stripped_count": len(carried), "ticket": ticket}


@sap_router.post("/jml/{person_ref}/strip-carried-over")
async def strip_carried_over(person_ref: str, body: MoverStripBody, user: dict = Depends(get_current_user)):
    """Mover access-accumulation cleanup: strip carried-over roles and open a ServiceNow -> HR -> SAP change."""
    org_id = user["org_id"]
    await _ensure(org_id)
    persons, accounts, conflicts, pmap = await _correlate(org_id)
    p = pmap.get(person_ref)
    if not p:
        raise HTTPException(status_code=404, detail="Identity not found")
    res = await _strip_carried_over(org_id, p, user["email"], body.reason)
    if not res:
        raise HTTPException(status_code=400, detail="No carried-over roles to strip — access already matches the current role's birthright set")
    return {"ok": True, "stripped": res["stripped"], "stripped_names": res["stripped_names"],
            "stripped_count": res["stripped_count"], "ticket": _ticket_public(res["ticket"])}


# ── Mover Auto-Strip Rule Engine ──────────────────────────────────────────────
def _is_mover(p):
    return p["status"] == "Active" and any(
        c["field"] in ("legal_entity", "manager", "job_title", "worker_type") for c in _hr_conflicts_for(p))


async def _get_mover_rule(org_id):
    cfg = await db.sap_mover_rule.find_one({"org_id": org_id}, {"_id": 0}) or {}
    return {"enabled": bool(cfg.get("enabled")),
            "last_cron_at": cfg.get("last_cron_at"), "last_cron_count": cfg.get("last_cron_count")}


async def _run_mover_autostrip(org_id, by, persons=None):
    """Auto-strip carried-over access for every in-flight mover (idempotent — a no-op once clean)."""
    if persons is None:
        persons, _, _, _ = await _correlate(org_id)
    created = []
    for p in persons:
        if not _is_mover(p):
            continue
        res = await _strip_carried_over(org_id, p, by, "Auto-strip rule — mover access-accumulation cleanup")
        if res:
            entry = {"org_id": org_id, "person_ref": p["ref"], "name": p["name"], "department": p["department"],
                     "stripped": res["stripped"], "stripped_names": res["stripped_names"],
                     "ticket_number": res["ticket"]["number"], "by": by, "at": _now().isoformat()}
            await db.sap_mover_autostrip_log.insert_one(entry)
            entry.pop("_id", None)
            created.append(entry)
    return created


async def run_sap_mover_autostrip_all():
    """Unattended mover auto-strip sweep across every org that enabled the rule (folded into daily cron)."""
    orgs = await db.sap_mover_rule.find({"enabled": True}, {"_id": 0, "org_id": 1}).to_list(1000)
    for o in orgs:
        org_id = o["org_id"]
        try:
            created = await _run_mover_autostrip(org_id, "cron:daily")
            await db.sap_mover_rule.update_one(
                {"org_id": org_id},
                {"$set": {"last_cron_at": _now().isoformat(), "last_cron_count": len(created)}})
        except Exception:
            pass


class MoverRuleBody(BaseModel):
    enabled: bool


@sap_router.get("/mover-rule")
async def get_mover_rule(q: str = "", days: int = 0, user: dict = Depends(get_current_user)):
    org_id = user["org_id"]
    await _ensure(org_id)
    cfg = await _get_mover_rule(org_id)
    persons, _, _, _ = await _correlate(org_id)
    movers = [p for p in persons if _is_mover(p)]
    candidates = 0
    for p in movers:
        birthright = {rc["ref"] for rc in ROLE_CATALOG if rc.get("dept") == p["department"]}
        if any(r not in birthright for a in p["accounts"] for r in a.get("roles", [])):
            candidates += 1
    query = {"org_id": org_id}
    if days and days > 0:
        query["at"] = {"$gte": (_now() - timedelta(days=days)).isoformat()}
    log = await db.sap_mover_autostrip_log.find(query, {"_id": 0}).sort("at", -1).to_list(500)
    if q:
        ql = q.lower()
        log = [l for l in log if ql in (f"{l.get('name','')} {l.get('department','')} {l.get('ticket_number','')} "
                                        f"{' '.join(l.get('stripped_names', []))}").lower()]
    return {"config": cfg, "movers": len(movers), "candidates": candidates,
            "log": log[:200], "filtered": len(log),
            "stripped_total": await db.sap_mover_autostrip_log.count_documents({"org_id": org_id})}


@sap_router.put("/mover-rule")
async def put_mover_rule(body: MoverRuleBody, user: dict = Depends(require_roles("admin"))):
    org_id = user["org_id"]
    await _ensure(org_id)
    await db.sap_mover_rule.update_one({"org_id": org_id},
                                       {"$set": {"org_id": org_id, "enabled": body.enabled}}, upsert=True)
    await _audit(org_id, user["email"], "sap.mover_rule.config", f"enabled={body.enabled}")
    created = await _run_mover_autostrip(org_id, user["email"]) if body.enabled else []
    return {"ok": True, "config": await _get_mover_rule(org_id), "stripped": len(created)}


@sap_router.post("/mover-rule/run")
async def run_mover_rule(user: dict = Depends(get_current_user)):
    org_id = user["org_id"]
    await _ensure(org_id)
    created = await _run_mover_autostrip(org_id, user["email"])
    return {"ok": True, "stripped": len(created), "created": created}
