"""Obserra SAP UAC — SoD → ServiceNow auto-remediation rule engine (attached to the shared sap_router)."""
from fastapi import Depends, HTTPException
from pydantic import BaseModel

from db import db
from auth import get_current_user
from sap_data import SEV_WEIGHT
from sap_engine import _now, _correlate, _ensure
from sap_uac import sap_router, _run_account_action, _audit

_AUTOREM_DEFAULT = {"enabled": False, "severities": ["Critical"], "action": "recertify"}


async def _get_autoremediation(org_id):
    cfg = await db.sap_autoremediation.find_one({"org_id": org_id}, {"_id": 0})
    if not cfg:
        cfg = {"org_id": org_id, **_AUTOREM_DEFAULT}
    for k, v in _AUTOREM_DEFAULT.items():
        cfg.setdefault(k, v)
    return cfg


async def _autorem_candidates(org_id, conflicts, severities):
    """Accounts carrying an OPEN SoD conflict of a watched severity that haven't been auto-remediated yet."""
    done = {r["account_ref"] for r in await db.sap_autoremediation_log.find(
        {"org_id": org_id}, {"_id": 0, "account_ref": 1}).to_list(5000)}
    by_acc = {}
    for c in conflicts:
        if c.get("status") == "Open" and c["severity"] in severities and c.get("account_ref"):
            by_acc.setdefault(c["account_ref"], []).append(c)
    return {ref: cs for ref, cs in by_acc.items() if ref not in done}


async def _run_autoremediation(org_id, by, conflicts=None):
    """Open one ServiceNow workflow per account with a watched OPEN SoD conflict (deduped, idempotent)."""
    cfg = await _get_autoremediation(org_id)
    if conflicts is None:
        _, _, conflicts, _ = await _correlate(org_id)
    cand = await _autorem_candidates(org_id, conflicts, cfg.get("severities", ["Critical"]))
    action = cfg.get("action", "recertify")
    created = []
    for account_ref, cs in cand.items():
        acc = await db.sap_accounts.find_one({"org_id": org_id, "ref": account_ref})
        if not acc:
            continue
        rules = sorted({c["rule_name"] for c in cs})
        note = f"Auto-remediation rule engine: {len(cs)} open SoD conflict(s) — {', '.join(rules)}"
        ticket = await _run_account_action(org_id, acc, action, by, note)
        entry = {"org_id": org_id, "account_ref": account_ref, "sap_user": acc["sap_user"],
                 "system": acc["system"], "person_ref": acc.get("person_ref"),
                 "conflict_refs": [c["conflict_ref"] for c in cs], "rules": rules,
                 "severity": max((c["severity"] for c in cs), key=lambda s: SEV_WEIGHT.get(s, 0)),
                 "action": action, "ticket_number": ticket["number"], "ticket_type": ticket["type"],
                 "by": by, "at": _now().isoformat()}
        await db.sap_autoremediation_log.insert_one(entry)
        entry.pop("_id", None)
        created.append(entry)
    return created


class AutoRemConfig(BaseModel):
    enabled: bool
    severities: list[str] = ["Critical"]
    action: str = "recertify"


@sap_router.get("/autoremediation")
async def get_autoremediation(user: dict = Depends(get_current_user)):
    org_id = user["org_id"]
    await _ensure(org_id)
    cfg = await _get_autoremediation(org_id)
    _, _, conflicts, _ = await _correlate(org_id)
    cand = await _autorem_candidates(org_id, conflicts, cfg.get("severities", ["Critical"]))
    log = await db.sap_autoremediation_log.find({"org_id": org_id}, {"_id": 0}).sort("at", -1).to_list(100)
    open_by_sev = {}
    for c in conflicts:
        if c.get("status") == "Open":
            open_by_sev[c["severity"]] = open_by_sev.get(c["severity"], 0) + 1
    return {"config": {**{k: cfg[k] for k in ("enabled", "severities", "action")},
                       "last_cron_at": cfg.get("last_cron_at"), "last_cron_count": cfg.get("last_cron_count")},
            "candidates": len(cand),
            "candidate_accounts": [{"account_ref": r, "rules": sorted({c["rule_name"] for c in cs}), "count": len(cs)}
                                   for r, cs in list(cand.items())[:25]],
            "log": log, "remediated_total": len(log), "open_by_severity": open_by_sev}


@sap_router.put("/autoremediation")
async def put_autoremediation(body: AutoRemConfig, user: dict = Depends(get_current_user)):
    org_id = user["org_id"]
    await _ensure(org_id)
    if body.action not in ("recertify", "deactivate", "revoke_all", "lock"):
        raise HTTPException(status_code=400, detail="invalid action")
    sev = [s for s in body.severities if s in ("Critical", "High", "Medium")] or ["Critical"]
    await db.sap_autoremediation.update_one({"org_id": org_id},
        {"$set": {"org_id": org_id, "enabled": body.enabled, "severities": sev, "action": body.action}}, upsert=True)
    await _audit(org_id, user["email"], "sap.autoremediation.config",
                 f"enabled={body.enabled} severities={sev} action={body.action}")
    created = await _run_autoremediation(org_id, user["email"]) if body.enabled else []
    return {"ok": True, "config": {"enabled": body.enabled, "severities": sev, "action": body.action},
            "remediated": len(created)}


@sap_router.post("/autoremediation/run")
async def run_autoremediation(user: dict = Depends(get_current_user)):
    org_id = user["org_id"]
    await _ensure(org_id)
    created = await _run_autoremediation(org_id, user["email"])
    return {"ok": True, "remediated": len(created), "created": created}


async def run_sap_autoremediation_all():
    """Unattended SoD → ServiceNow auto-remediation sweep across every org that enabled the engine."""
    orgs = await db.sap_autoremediation.find({"enabled": True}, {"_id": 0, "org_id": 1}).to_list(1000)
    for o in orgs:
        org_id = o["org_id"]
        try:
            created = await _run_autoremediation(org_id, "cron:daily")
            await db.sap_autoremediation.update_one(
                {"org_id": org_id},
                {"$set": {"last_cron_at": _now().isoformat(), "last_cron_count": len(created)}})
        except Exception:
            pass
