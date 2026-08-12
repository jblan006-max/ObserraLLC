from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from pymongo import ASCENDING, DESCENDING, ReturnDocument

from auth import get_current_user
from db import db


api = APIRouter(prefix="/api/crisis", tags=["Cyber Crisis Commander"])
_indexes_ready = False


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _actor(user: dict) -> str:
    return user.get("email") or user.get("name") or user.get("sub") or "unknown"


def _require_operator(user: dict) -> None:
    if str(user.get("role", "")).lower() not in {"admin", "executive", "owner"}:
        raise HTTPException(status_code=403, detail="Administrator or executive role required")


async def _ensure_indexes() -> None:
    global _indexes_ready
    if _indexes_ready:
        return

    await db.crisis_cases.create_index(
        [("org_id", ASCENDING), ("ref", ASCENDING)],
        unique=True,
        name="crisis_case_org_ref",
    )
    await db.crisis_cases.create_index(
        [("org_id", ASCENDING), ("updated_at", DESCENDING)],
        name="crisis_case_org_updated",
    )
    await db.crisis_events.create_index(
        [("org_id", ASCENDING), ("case_ref", ASCENDING), ("occurred_at", ASCENDING)],
        name="crisis_event_timeline",
    )
    await db.crisis_actions.create_index(
        [("org_id", ASCENDING), ("case_ref", ASCENDING), ("status", ASCENDING)],
        name="crisis_action_case_status",
    )
    await db.crisis_connector_health.create_index(
        [("org_id", ASCENDING), ("vendor", ASCENDING)],
        name="crisis_connector_health_unique", unique=True,
    )
    _indexes_ready = True


async def _audit(org_id: str, actor: str, action: str, detail: str = "") -> None:
    await db.audit_logs.insert_one(
        {
            "org_id": org_id,
            "actor": actor,
            "action": action,
            "detail": detail,
            "ts": _now(),
        }
    )


async def _next_ref(org_id: str, name: str, prefix: str) -> str:
    result = await db.counters.find_one_and_update(
        {"_id": f"{name}:{org_id}"},
        {"$inc": {"seq": 1}},
        upsert=True,
        return_document=ReturnDocument.AFTER,
    )
    return f"{prefix}-{int(result['seq']):04d}"


class CrisisCaseCreate(BaseModel):
    title: str = Field(min_length=3, max_length=180)
    severity: Literal["Low", "Medium", "High", "Critical"] = "High"
    summary: str = Field(default="", max_length=5000)
    incident_refs: list[str] = Field(default_factory=list)
    risk_refs: list[str] = Field(default_factory=list)
    business_services: list[str] = Field(default_factory=list)
    incident_commander: str = Field(default="", max_length=160)
    executive_sponsor: str = Field(default="", max_length=160)


class CrisisCaseUpdate(BaseModel):
    status: Literal["Open", "Contained", "Recovering", "Monitoring", "Closed"] | None = None
    severity: Literal["Low", "Medium", "High", "Critical"] | None = None
    phase: Literal[
        "Detection",
        "Triage",
        "Containment",
        "Eradication",
        "Recovery",
        "Post Incident",
    ] | None = None
    summary: str | None = Field(default=None, max_length=5000)
    incident_commander: str | None = Field(default=None, max_length=160)
    executive_sponsor: str | None = Field(default=None, max_length=160)
    next_update_at: str | None = None
    business_services: list[str] | None = None
    incident_refs: list[str] | None = None
    risk_refs: list[str] | None = None
    brief_schedule_hours: int | None = Field(default=None, ge=0, le=168)
    sitrep_schedule_hours: int | None = Field(default=None, ge=0, le=168)
    sitrep_note: str | None = Field(default=None, max_length=500)


class CrisisEventCreate(BaseModel):
    kind: Literal[
        "Detection",
        "Threat",
        "Containment",
        "Decision",
        "Communication",
        "Recovery",
        "Business Impact",
        "Legal",
        "Evidence",
        "Note",
    ] = "Note"
    title: str = Field(min_length=2, max_length=220)
    detail: str = Field(default="", max_length=6000)
    source: str = Field(default="Manual", max_length=120)
    severity: Literal["Info", "Low", "Medium", "High", "Critical"] = "Info"
    occurred_at: str | None = None


class CrisisActionCreate(BaseModel):
    title: str = Field(min_length=2, max_length=220)
    owner: str = Field(default="", max_length=160)
    priority: Literal["Low", "Medium", "High", "Critical"] = "High"
    status: Literal[
        "Open",
        "Awaiting Approval",
        "Approved",
        "Executing",
        "Verified",
        "Blocked",
        "Failed",
        "Complete",
    ] = "Open"
    action_type: Literal[
        "Containment",
        "Recovery",
        "Decision",
        "Communication",
        "Legal",
        "Investigation",
    ] = "Containment"
    due_at: str | None = None
    decision_required: bool = False
    decision_owner: str = Field(default="", max_length=160)
    business_impact: str = Field(default="", max_length=2000)
    technical_impact: str = Field(default="", max_length=2000)


class CrisisActionUpdate(BaseModel):
    owner: str | None = Field(default=None, max_length=160)
    priority: Literal["Low", "Medium", "High", "Critical"] | None = None
    status: Literal[
        "Open",
        "Awaiting Approval",
        "Approved",
        "Executing",
        "Verified",
        "Blocked",
        "Failed",
        "Complete",
    ] | None = None
    due_at: str | None = None
    decision_owner: str | None = Field(default=None, max_length=160)
    outcome: str | None = Field(default=None, max_length=4000)
    approved_by: str | None = Field(default=None, max_length=160)


async def _get_case(org_id: str, ref: str) -> dict:
    await _ensure_indexes()
    case = await db.crisis_cases.find_one(
        {"org_id": org_id, "ref": ref},
        {"_id": 0},
    )
    if not case:
        raise HTTPException(status_code=404, detail="Crisis case not found")
    return case


@api.get("/cases")
async def list_cases(user: dict = Depends(get_current_user)):
    await _ensure_indexes()
    return await db.crisis_cases.find(
        {"org_id": user["org_id"]},
        {"_id": 0},
    ).sort("updated_at", DESCENDING).to_list(200)


@api.post("/cases")
async def create_case(body: CrisisCaseCreate, user: dict = Depends(get_current_user)):
    _require_operator(user)
    await _ensure_indexes()
    org_id = user["org_id"]
    now = _now()
    ref = await _next_ref(org_id, "crisis_cases", "CRISIS")

    record = {
        "ref": ref,
        "org_id": org_id,
        "title": body.title,
        "severity": body.severity,
        "summary": body.summary,
        "incident_refs": body.incident_refs,
        "risk_refs": body.risk_refs,
        "business_services": body.business_services,
        "incident_commander": body.incident_commander,
        "executive_sponsor": body.executive_sponsor,
        "status": "Open",
        "phase": "Triage",
        "started_at": now,
        "updated_at": now,
        "next_update_at": None,
        "created_by": _actor(user),
    }
    await db.crisis_cases.insert_one(record.copy())

    event = {
        "org_id": org_id,
        "case_ref": ref,
        "event_id": await _next_ref(org_id, "crisis_events", "EVT"),
        "kind": "Detection",
        "title": "Crisis case opened",
        "detail": body.summary,
        "source": "Obserra",
        "severity": body.severity,
        "occurred_at": now,
        "created_at": now,
        "created_by": _actor(user),
    }
    await db.crisis_events.insert_one(event)
    await _audit(org_id, _actor(user), "crisis.case.create", ref)
    return record


@api.get("/cases/{ref}")
async def get_case(ref: str, user: dict = Depends(get_current_user)):
    org_id = user["org_id"]
    case = await _get_case(org_id, ref)
    actions = await db.crisis_actions.find(
        {"org_id": org_id, "case_ref": ref},
        {"_id": 0},
    ).sort("created_at", ASCENDING).to_list(500)
    events = await db.crisis_events.find(
        {"org_id": org_id, "case_ref": ref},
        {"_id": 0},
    ).sort("occurred_at", ASCENDING).to_list(1000)
    participants = await db.crisis_participants.find(
        {"org_id": org_id, "case_ref": ref}, {"_id": 0},
    ).sort("created_at", ASCENDING).to_list(200)
    recovery = await db.crisis_recovery.find(
        {"org_id": org_id, "case_ref": ref}, {"_id": 0},
    ).sort("created_at", ASCENDING).to_list(500)
    obligations = await db.crisis_obligations.find(
        {"org_id": org_id, "case_ref": ref}, {"_id": 0},
    ).sort("deadline_at", ASCENDING).to_list(500)
    return {"case": case, "actions": actions, "events": events,
            "participants": participants, "recovery": recovery, "obligations": obligations}


@api.patch("/cases/{ref}")
async def update_case(
    ref: str,
    body: CrisisCaseUpdate,
    user: dict = Depends(get_current_user),
):
    _require_operator(user)
    org_id = user["org_id"]
    existing = await _get_case(org_id, ref)
    changes = {key: value for key, value in body.model_dump().items() if value is not None}
    if not changes:
        raise HTTPException(status_code=400, detail="No changes")

    now = _now()
    escalated = False
    if changes.get("severity") == "Critical" and existing.get("severity") != "Critical":
        current_cadence = int(existing.get("brief_schedule_hours") or 0)
        if "brief_schedule_hours" not in changes and (current_cadence == 0 or current_cadence > 4):
            changes["brief_schedule_hours"] = 4
            escalated = True
    changes["updated_at"] = now
    await db.crisis_cases.update_one(
        {"org_id": org_id, "ref": ref},
        {"$set": changes},
    )
    if escalated:
        await db.crisis_events.insert_one({
            "org_id": org_id, "case_ref": ref,
            "event_id": await _next_ref(org_id, "crisis_events", "EVT"),
            "kind": "Communication",
            "title": "Board-brief cadence auto-escalated to every 4h (severity → Critical)",
            "detail": f"{ref} escalated to Critical; leadership will now receive the crisis brief every 4 hours.",
            "source": "Auto-Escalation", "severity": "High",
            "occurred_at": now, "created_at": now, "created_by": "Obserra Auto-Escalation"})
    if changes.get("status") == "Closed" and existing.get("status") != "Closed" and not existing.get("demo"):
        try:
            await _auto_present_board(org_id, ref, _actor(user))
        except Exception as exc:
            import logging
            logging.getLogger("crisis").exception("Board auto-present failed for %s: %s", ref, exc)
    await _audit(org_id, _actor(user), "crisis.case.update", f"{ref}: {changes}")
    return await db.crisis_cases.find_one(
        {"org_id": org_id, "ref": ref},
        {"_id": 0},
    )


@api.post("/cases/{ref}/events")
async def add_event(
    ref: str,
    body: CrisisEventCreate,
    user: dict = Depends(get_current_user),
):
    _require_operator(user)
    org_id = user["org_id"]
    await _get_case(org_id, ref)
    now = _now()
    event = {
        "org_id": org_id,
        "case_ref": ref,
        "event_id": await _next_ref(org_id, "crisis_events", "EVT"),
        "kind": body.kind,
        "title": body.title,
        "detail": body.detail,
        "source": body.source,
        "severity": body.severity,
        "occurred_at": body.occurred_at or now,
        "created_at": now,
        "created_by": _actor(user),
    }
    await db.crisis_events.insert_one(event.copy())
    await db.crisis_cases.update_one(
        {"org_id": org_id, "ref": ref},
        {"$set": {"updated_at": now}},
    )
    await _audit(org_id, _actor(user), "crisis.event.create", f"{ref}: {event['event_id']}")
    return event


_SLA_HOURS = {"Critical": 1, "High": 2, "Medium": 4, "Low": 8}


def _sla_due(priority, base_iso):
    from datetime import timedelta
    base = _parse_iso(base_iso) or datetime.now(timezone.utc)
    return (base + timedelta(hours=_SLA_HOURS.get(priority or "High", 2))).isoformat()


@api.post("/cases/{ref}/actions")
async def add_action(
    ref: str,
    body: CrisisActionCreate,
    user: dict = Depends(get_current_user),
):
    _require_operator(user)
    org_id = user["org_id"]
    await _get_case(org_id, ref)
    now = _now()
    action = {
        "org_id": org_id,
        "case_ref": ref,
        "action_id": await _next_ref(org_id, "crisis_actions", "ACT"),
        **body.model_dump(),
        "outcome": "",
        "approved_by": "",
        "created_at": now,
        "updated_at": now,
        "created_by": _actor(user),
    }
    if action["decision_required"] and action["status"] == "Open":
        action["status"] = "Awaiting Approval"
    if action["decision_required"] and not action.get("decision_due_at"):
        action["decision_due_at"] = _sla_due(action.get("priority"), now)

    await db.crisis_actions.insert_one(action.copy())
    await db.crisis_cases.update_one(
        {"org_id": org_id, "ref": ref},
        {"$set": {"updated_at": now}},
    )
    await _audit(org_id, _actor(user), "crisis.action.create", f"{ref}: {action['action_id']}")
    return action


@api.patch("/cases/{ref}/actions/{action_id}")
async def update_action(
    ref: str,
    action_id: str,
    body: CrisisActionUpdate,
    user: dict = Depends(get_current_user),
):
    _require_operator(user)
    org_id = user["org_id"]
    await _get_case(org_id, ref)
    existing = await db.crisis_actions.find_one(
        {"org_id": org_id, "case_ref": ref, "action_id": action_id}
    )
    if not existing:
        raise HTTPException(status_code=404, detail="Crisis action not found")

    changes = {key: value for key, value in body.model_dump().items() if value is not None}
    if not changes:
        raise HTTPException(status_code=400, detail="No changes")

    now = _now()
    changes["updated_at"] = now
    await db.crisis_actions.update_one(
        {"org_id": org_id, "case_ref": ref, "action_id": action_id},
        {"$set": changes},
    )

    if changes.get("status") and changes["status"] != existing.get("status"):
        event = {
            "org_id": org_id,
            "case_ref": ref,
            "event_id": await _next_ref(org_id, "crisis_events", "EVT"),
            "kind": "Decision"
            if changes["status"] in {"Approved", "Awaiting Approval"}
            else "Containment",
            "title": f"{action_id} status changed to {changes['status']}",
            "detail": changes.get("outcome", ""),
            "source": "Obserra",
            "severity": existing.get("priority", "Medium"),
            "occurred_at": now,
            "created_at": now,
            "created_by": _actor(user),
        }
        await db.crisis_events.insert_one(event)

    await db.crisis_cases.update_one(
        {"org_id": org_id, "ref": ref},
        {"$set": {"updated_at": now}},
    )
    await _audit(org_id, _actor(user), "crisis.action.update", f"{ref}: {action_id} {changes}")
    return await db.crisis_actions.find_one(
        {"org_id": org_id, "case_ref": ref, "action_id": action_id},
        {"_id": 0},
    )


@api.get("/cases/{ref}/timeline")
async def get_timeline(ref: str, user: dict = Depends(get_current_user)):
    org_id = user["org_id"]
    await _get_case(org_id, ref)
    return await db.crisis_events.find(
        {"org_id": org_id, "case_ref": ref},
        {"_id": 0},
    ).sort("occurred_at", ASCENDING).to_list(1000)


# ---------------------------------------------------------------------------
# War Room participants
# ---------------------------------------------------------------------------
class CrisisParticipantCreate(BaseModel):
    role: str = Field(min_length=2, max_length=120)
    name: str = Field(default="", max_length=160)
    contact: str = Field(default="", max_length=200)
    responsibility: str = Field(default="", max_length=400)
    status: Literal["Standby", "Engaged", "Stood Down"] = "Engaged"


@api.post("/cases/{ref}/participants")
async def add_participant(ref: str, body: CrisisParticipantCreate, user: dict = Depends(get_current_user)):
    _require_operator(user)
    org_id = user["org_id"]
    await _get_case(org_id, ref)
    now = _now()
    participant = {
        "org_id": org_id,
        "case_ref": ref,
        "participant_id": await _next_ref(org_id, "crisis_participants", "WAR"),
        **body.model_dump(),
        "created_at": now,
        "created_by": _actor(user),
    }
    await db.crisis_participants.insert_one(participant.copy())
    await db.crisis_cases.update_one({"org_id": org_id, "ref": ref}, {"$set": {"updated_at": now}})
    await _audit(org_id, _actor(user), "crisis.participant.add", f"{ref}: {participant['role']}")
    return participant


@api.delete("/cases/{ref}/participants/{participant_id}")
async def remove_participant(ref: str, participant_id: str, user: dict = Depends(get_current_user)):
    _require_operator(user)
    org_id = user["org_id"]
    await _get_case(org_id, ref)
    result = await db.crisis_participants.delete_one(
        {"org_id": org_id, "case_ref": ref, "participant_id": participant_id}
    )
    if not result.deleted_count:
        raise HTTPException(status_code=404, detail="Participant not found")
    await _audit(org_id, _actor(user), "crisis.participant.remove", f"{ref}: {participant_id}")
    return {"ok": True}


# ---------------------------------------------------------------------------
# Recovery Command
# ---------------------------------------------------------------------------
_RECOVERY_PCT = {"Down": 0, "Restoring": 50, "Validated": 80, "Operational": 100}


class CrisisRecoveryCreate(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    category: Literal["System", "Application", "Business Service", "Region", "Business Unit"] = "System"
    status: Literal["Down", "Restoring", "Validated", "Operational"] = "Down"
    owner: str = Field(default="", max_length=160)
    note: str = Field(default="", max_length=1000)


class CrisisRecoveryUpdate(BaseModel):
    status: Literal["Down", "Restoring", "Validated", "Operational"] | None = None
    owner: str | None = Field(default=None, max_length=160)
    note: str | None = Field(default=None, max_length=1000)


@api.post("/cases/{ref}/recovery")
async def add_recovery(ref: str, body: CrisisRecoveryCreate, user: dict = Depends(get_current_user)):
    _require_operator(user)
    org_id = user["org_id"]
    await _get_case(org_id, ref)
    now = _now()
    item = {
        "org_id": org_id,
        "case_ref": ref,
        "recovery_id": await _next_ref(org_id, "crisis_recovery", "REC"),
        **body.model_dump(),
        "pct": _RECOVERY_PCT[body.status],
        "created_at": now,
        "updated_at": now,
        "created_by": _actor(user),
    }
    await db.crisis_recovery.insert_one(item.copy())
    await db.crisis_cases.update_one({"org_id": org_id, "ref": ref}, {"$set": {"updated_at": now}})
    await _audit(org_id, _actor(user), "crisis.recovery.add", f"{ref}: {item['recovery_id']}")
    return item


@api.patch("/cases/{ref}/recovery/{recovery_id}")
async def update_recovery(ref: str, recovery_id: str, body: CrisisRecoveryUpdate, user: dict = Depends(get_current_user)):
    _require_operator(user)
    org_id = user["org_id"]
    await _get_case(org_id, ref)
    existing = await db.crisis_recovery.find_one({"org_id": org_id, "case_ref": ref, "recovery_id": recovery_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Recovery item not found")
    changes = {key: value for key, value in body.model_dump().items() if value is not None}
    if not changes:
        raise HTTPException(status_code=400, detail="No changes")
    if changes.get("status"):
        changes["pct"] = _RECOVERY_PCT[changes["status"]]
    changes["updated_at"] = _now()
    await db.crisis_recovery.update_one(
        {"org_id": org_id, "case_ref": ref, "recovery_id": recovery_id}, {"$set": changes}
    )
    await _audit(org_id, _actor(user), "crisis.recovery.update", f"{ref}: {recovery_id} {changes}")
    return await db.crisis_recovery.find_one(
        {"org_id": org_id, "case_ref": ref, "recovery_id": recovery_id}, {"_id": 0}
    )


# ---------------------------------------------------------------------------
# Regulatory & Legal obligations (evidence-only; legal confirms obligation)
# ---------------------------------------------------------------------------
class CrisisObligationCreate(BaseModel):
    jurisdiction: str = Field(min_length=2, max_length=160)
    regulation: str = Field(min_length=2, max_length=200)
    trigger: str = Field(default="", max_length=600)
    deadline_at: str
    responsible: str = Field(default="", max_length=160)
    evidence_required: str = Field(default="", max_length=1000)
    status: Literal["Assessing", "Notification Required", "Not Applicable", "Notified", "On Hold"] = "Assessing"
    notification_decision: str = Field(default="", max_length=1000)
    notify_within_hours: int = Field(default=24, ge=1, le=720)


class CrisisObligationUpdate(BaseModel):
    status: Literal["Assessing", "Notification Required", "Not Applicable", "Notified", "On Hold"] | None = None
    responsible: str | None = Field(default=None, max_length=160)
    notification_decision: str | None = Field(default=None, max_length=1000)
    deadline_at: str | None = None
    notify_within_hours: int | None = Field(default=None, ge=1, le=720)


@api.post("/cases/{ref}/obligations")
async def add_obligation(ref: str, body: CrisisObligationCreate, user: dict = Depends(get_current_user)):
    _require_operator(user)
    org_id = user["org_id"]
    await _get_case(org_id, ref)
    now = _now()
    obligation = {
        "org_id": org_id,
        "case_ref": ref,
        "obligation_id": await _next_ref(org_id, "crisis_obligations", "REG"),
        **body.model_dump(),
        "alert_state": "",
        "created_at": now,
        "updated_at": now,
        "created_by": _actor(user),
    }
    await db.crisis_obligations.insert_one(obligation.copy())
    await db.crisis_cases.update_one({"org_id": org_id, "ref": ref}, {"$set": {"updated_at": now}})
    await _audit(org_id, _actor(user), "crisis.obligation.add", f"{ref}: {obligation['obligation_id']}")
    return obligation


@api.patch("/cases/{ref}/obligations/{obligation_id}")
async def update_obligation(ref: str, obligation_id: str, body: CrisisObligationUpdate, user: dict = Depends(get_current_user)):
    _require_operator(user)
    org_id = user["org_id"]
    await _get_case(org_id, ref)
    existing = await db.crisis_obligations.find_one({"org_id": org_id, "case_ref": ref, "obligation_id": obligation_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Obligation not found")
    changes = {key: value for key, value in body.model_dump().items() if value is not None}
    if not changes:
        raise HTTPException(status_code=400, detail="No changes")
    if "deadline_at" in changes and changes.get("deadline_at") != existing.get("deadline_at"):
        changes["alert_state"] = ""  # deadline moved — re-arm the regulatory-clock alert
    changes["updated_at"] = _now()
    await db.crisis_obligations.update_one(
        {"org_id": org_id, "case_ref": ref, "obligation_id": obligation_id}, {"$set": changes}
    )
    await _audit(org_id, _actor(user), "crisis.obligation.update", f"{ref}: {obligation_id} {changes}")
    return await db.crisis_obligations.find_one(
        {"org_id": org_id, "case_ref": ref, "obligation_id": obligation_id}, {"_id": 0}
    )


# ---------------------------------------------------------------------------
# Demo Mode (staged ransomware scenario, clearly flagged, one-click clear)
# ---------------------------------------------------------------------------
async def _demo_clear(org_id: str) -> dict:
    from bson import ObjectId
    await db.crisis_scenario.delete_many({"org_id": org_id})
    try:
        await db.organizations.update_one({"_id": ObjectId(org_id)}, {"$set": {"ci_demo_active": False}})
    except Exception:
        pass
    return {
        "cases": (await db.crisis_cases.delete_many({"org_id": org_id, "demo": True})).deleted_count,
        "actions": (await db.crisis_actions.delete_many({"org_id": org_id, "demo": True})).deleted_count,
        "events": (await db.crisis_events.delete_many({"org_id": org_id, "demo": True})).deleted_count,
        "participants": (await db.crisis_participants.delete_many({"org_id": org_id, "demo": True})).deleted_count,
        "recovery": (await db.crisis_recovery.delete_many({"org_id": org_id, "demo": True})).deleted_count,
        "obligations": (await db.crisis_obligations.delete_many({"org_id": org_id, "demo": True})).deleted_count,
    }


@api.get("/demo/status")
async def demo_status(user: dict = Depends(get_current_user)):
    active = await db.crisis_cases.count_documents({"org_id": user["org_id"], "demo": True}) > 0
    return {"active": active}


@api.post("/demo/clear")
async def demo_clear(user: dict = Depends(get_current_user)):
    _require_operator(user)
    counts = await _demo_clear(user["org_id"])
    await _audit(user["org_id"], _actor(user), "crisis.demo.clear", str(counts))
    return {"cleared": True, **counts}


@api.post("/demo/seed")
async def demo_seed(user: dict = Depends(get_current_user)):
    from datetime import timedelta
    _require_operator(user)
    await _ensure_indexes()
    org_id = user["org_id"]
    await _demo_clear(org_id)
    from bson import ObjectId
    await db.organizations.update_one({"_id": ObjectId(org_id)}, {"$set": {"ci_demo_active": True}})
    now = datetime.now(timezone.utc)

    def iso(minutes_ago):
        return (now - timedelta(minutes=minutes_ago)).isoformat()

    def iso_future(hours):
        return (now + timedelta(hours=hours)).isoformat()

    actor = _actor(user)
    ref = await _next_ref(org_id, "crisis_cases", "CRISIS")
    case = {
        "ref": ref, "org_id": org_id, "demo": True,
        "title": "Ransomware — North American Order Fulfillment",
        "severity": "Critical",
        "summary": "Ransomware encryption activity across seven production systems supporting North American order fulfillment. Identity compromise unresolved for three privileged users. Containment in progress.",
        "incident_refs": [], "risk_refs": [],
        "business_services": ["Order Management", "North American Sales", "Customer Fulfillment", "Payment Processing"],
        "incident_commander": "A. Rivera (SecOps Lead)",
        "executive_sponsor": "CISO",
        "status": "Recovering", "phase": "Containment",
        "started_at": iso(180), "updated_at": now.isoformat(), "next_update_at": iso_future(1),
        "created_by": actor,
    }
    await db.crisis_cases.insert_one(case.copy())

    events = [
        ("Detection", "Suspicious authentication detected", "SIEM", "High", 178),
        ("Threat", "Privileged account compromised", "Identity", "Critical", 173),
        ("Containment", "Endpoint isolation initiated", "EDR", "High", 169),
        ("Threat", "SAP production access detected from isolated host", "SAP", "Critical", 164),
        ("Detection", "Critical incident declared", "Obserra", "Critical", 158),
        ("Communication", "CISO and executive sponsor notified", "Obserra", "High", 153),
        ("Decision", "Incident commander assigned", "Obserra", "High", 149),
        ("Containment", "Production segment isolation approved", "Obserra", "High", 142),
        ("Business Impact", "Order fulfillment degraded for North American region", "ServiceNow", "High", 130),
        ("Recovery", "Backup validation started for order management", "Obserra", "Medium", 60),
    ]
    for kind, title, source, sev, mins in events:
        await db.crisis_events.insert_one({
            "org_id": org_id, "case_ref": ref, "demo": True,
            "event_id": await _next_ref(org_id, "crisis_events", "EVT"),
            "kind": kind, "title": title, "detail": "", "source": source, "severity": sev,
            "occurred_at": iso(mins), "created_at": now.isoformat(), "created_by": actor,
        })

    actions = [
        ("Isolate production SAP order-processing segment?", "Decision", "Critical", "Awaiting Approval", True, "CIO", "$1.8M/hr revenue impact", "Halts NA order processing"),
        ("Revoke privileged accounts for 3 compromised identities", "Decision", "Critical", "Awaiting Approval", True, "CISO", "Prevents further lateral movement", "Locks out 3 admins pending re-issue"),
        ("Engage cyber insurer and outside counsel", "Decision", "High", "Awaiting Approval", True, "General Counsel", "Preserves coverage & privilege", "None"),
        ("Isolate 7 encrypted production endpoints", "Containment", "Critical", "Verified", False, "", "Stops encryption spread", "7 hosts offline"),
        ("Rotate domain admin credentials", "Containment", "High", "Executing", False, "", "Removes attacker persistence", "Brief admin disruption"),
        ("Restore order management from validated backup", "Recovery", "High", "Executing", False, "", "Restores NA fulfillment", "Requires backup validation"),
        ("Draft customer holding statement", "Communication", "Medium", "Open", False, "", "Manages customer trust", "None"),
    ]
    for title, atype, prio, status, dec, downer, bimp, timp in actions:
        await db.crisis_actions.insert_one({
            "org_id": org_id, "case_ref": ref, "demo": True,
            "action_id": await _next_ref(org_id, "crisis_actions", "ACT"),
            "title": title, "owner": "", "priority": prio, "status": status,
            "action_type": atype, "due_at": None, "decision_required": dec, "decision_owner": downer,
            "decision_due_at": _sla_due(prio, now.isoformat()) if (dec and status == "Awaiting Approval") else None,
            "business_impact": bimp, "technical_impact": timp,
            "outcome": "", "approved_by": "", "created_at": now.isoformat(), "updated_at": now.isoformat(), "created_by": actor,
        })

    participants = [
        ("Incident Commander", "A. Rivera", "SecOps", "Engaged"),
        ("CISO", "Executive Sponsor", "Security leadership", "Engaged"),
        ("CIO", "Infrastructure", "Production systems", "Engaged"),
        ("Legal / Privacy", "General Counsel", "Regulatory & privilege", "Engaged"),
        ("Communications", "Comms Lead", "Customer & press", "Standby"),
        ("Finance", "CFO office", "Financial exposure", "Standby"),
        ("Business Continuity", "BC Lead", "Recovery coordination", "Engaged"),
        ("Cyber Insurance", "Broker", "Claim & coverage", "Standby"),
    ]
    for role, name, resp, pstatus in participants:
        await db.crisis_participants.insert_one({
            "org_id": org_id, "case_ref": ref, "demo": True,
            "participant_id": await _next_ref(org_id, "crisis_participants", "WAR"),
            "role": role, "name": name, "contact": "", "responsibility": resp, "status": pstatus,
            "created_at": now.isoformat(), "created_by": actor,
        })

    recovery = [
        ("Order Management System", "System", "Restoring"),
        ("SAP ERP Production", "System", "Down"),
        ("Identity Platform", "System", "Validated"),
        ("Customer Portal", "Application", "Operational"),
        ("Payment Gateway", "Application", "Restoring"),
        ("Order Fulfillment", "Business Service", "Restoring"),
        ("North American Sales", "Business Service", "Down"),
        ("Payment Processing", "Business Service", "Validated"),
    ]
    for name, cat, rstatus in recovery:
        await db.crisis_recovery.insert_one({
            "org_id": org_id, "case_ref": ref, "demo": True,
            "recovery_id": await _next_ref(org_id, "crisis_recovery", "REC"),
            "name": name, "category": cat, "status": rstatus, "owner": "", "note": "",
            "pct": _RECOVERY_PCT[rstatus],
            "created_at": now.isoformat(), "updated_at": now.isoformat(), "created_by": actor,
        })

    obligations = [
        ("EU (GDPR)", "GDPR Art. 33 personal data breach", "Possible exposure of EU customer PII", 66, "General Counsel", "Assessing", "Scope of affected EU data records"),
        ("United States (SEC)", "SEC cyber incident disclosure (Item 1.05)", "Potential material cyber incident", 90, "Securities Counsel", "Assessing", "Materiality determination"),
        ("California (CCPA)", "CCPA consumer breach notification", "Possible CA resident PII exposure", 42, "Privacy Counsel", "Notification Required", "Affected CA resident count"),
        ("Customer Contracts", "Enterprise SLA breach notification", "Order fulfillment SLA breach", 4, "Commercial Counsel", "Assessing", "Impacted contract list"),
    ]
    for jur, reg, trig, hours, resp, ostatus, evid in obligations:
        await db.crisis_obligations.insert_one({
            "org_id": org_id, "case_ref": ref, "demo": True,
            "obligation_id": await _next_ref(org_id, "crisis_obligations", "REG"),
            "jurisdiction": jur, "regulation": reg, "trigger": trig,
            "deadline_at": iso_future(hours), "responsible": resp,
            "evidence_required": evid, "status": ostatus, "notification_decision": "",
            "created_at": now.isoformat(), "updated_at": now.isoformat(), "created_by": actor,
        })

    await _audit(org_id, actor, "crisis.demo.seed", ref)
    return {"seeded": True, "ref": ref, "events": len(events), "actions": len(actions),
            "participants": len(participants), "recovery": len(recovery), "obligations": len(obligations)}


# ---------------------------------------------------------------------------
# Crisis-grounded AI Analyst — grounds ONLY on the live crisis case + its
# events, actions, decisions, recovery and regulatory obligations. It never
# reads the SAP access model / Control-Intelligence posture.
# ---------------------------------------------------------------------------
_CRISIS_INSIGHT_CACHE: dict = {}


def _parse_iso(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except Exception:
        return None


async def _crisis_insight_context(org_id: str, ref: str | None = None) -> dict | None:
    if ref:
        case = await db.crisis_cases.find_one({"org_id": org_id, "ref": ref}, {"_id": 0})
    else:
        case = await db.crisis_cases.find_one(
            {"org_id": org_id}, {"_id": 0}, sort=[("updated_at", DESCENDING)]
        )
    if not case:
        return None
    ref = case["ref"]
    events = await db.crisis_events.find(
        {"org_id": org_id, "case_ref": ref}, {"_id": 0}
    ).sort("occurred_at", DESCENDING).to_list(60)
    actions = await db.crisis_actions.find({"org_id": org_id, "case_ref": ref}, {"_id": 0}).to_list(300)
    recovery = await db.crisis_recovery.find({"org_id": org_id, "case_ref": ref}, {"_id": 0}).to_list(300)
    obligations = await db.crisis_obligations.find({"org_id": org_id, "case_ref": ref}, {"_id": 0}).to_list(300)
    participants = await db.crisis_participants.find({"org_id": org_id, "case_ref": ref}, {"_id": 0}).to_list(300)

    now = datetime.now(timezone.utc)
    awaiting = [a for a in actions if a.get("status") == "Awaiting Approval" or a.get("decision_required")]
    verified = [a for a in actions if a.get("status") in ("Verified", "Complete")]
    down = [r for r in recovery if r.get("status") == "Down"]
    overall_pct = round(sum(int(r.get("pct", 0)) for r in recovery) / len(recovery)) if recovery else None

    obl_deadlines = []
    for o in obligations:
        dl = _parse_iso(o.get("deadline_at"))
        if dl and o.get("status") not in ("Not Applicable", "Notified"):
            hrs = round((dl - now).total_seconds() / 3600, 1)
            obl_deadlines.append({"jurisdiction": o.get("jurisdiction"), "regulation": o.get("regulation"),
                                  "status": o.get("status"), "hours_remaining": hrs})
    obl_deadlines.sort(key=lambda x: x["hours_remaining"])

    return {
        "case": {"ref": ref, "title": case.get("title"), "severity": case.get("severity"),
                 "status": case.get("status"), "phase": case.get("phase"),
                 "summary": case.get("summary"), "incident_commander": case.get("incident_commander"),
                 "executive_sponsor": case.get("executive_sponsor"),
                 "business_services": case.get("business_services", []),
                 "started_at": case.get("started_at"), "next_update_at": case.get("next_update_at")},
        "counts": {"events": len(events), "actions": len(actions), "awaiting_approval": len(awaiting),
                   "verified_or_complete": len(verified), "recovery_items": len(recovery),
                   "systems_down": len(down), "participants_engaged": len(participants),
                   "regulatory_obligations": len(obligations)},
        "response_progress_pct": round(len(verified) / len(actions) * 100) if actions else 0,
        "recovery_overall_pct": overall_pct,
        "systems_down": [r.get("name") for r in down][:10],
        "pending_decisions": [{"action_id": a.get("action_id"), "title": a.get("title"),
                               "owner": a.get("decision_owner"), "priority": a.get("priority")} for a in awaiting][:10],
        "regulatory_deadlines": obl_deadlines[:8],
        "recent_events": [{"kind": e.get("kind"), "title": e.get("title"), "severity": e.get("severity"),
                           "source": e.get("source"), "occurred_at": e.get("occurred_at")} for e in events[:20]],
    }


def _crisis_insight_fallback(ctx: dict) -> dict:
    c = ctx["case"]
    counts = ctx["counts"]
    insights = []
    insights.append({"text": f"{c['ref']} '{c.get('title') or 'crisis case'}' is {c.get('severity')} severity, "
                             f"status {c.get('status')} in the {c.get('phase')} phase, "
                             f"led by {c.get('incident_commander') or 'an unassigned commander'}.", "kind": "fact"})
    if counts["awaiting_approval"]:
        pend = ", ".join(d["title"] for d in ctx["pending_decisions"][:3])
        insights.append({"text": f"{counts['awaiting_approval']} executive decision(s) await approval: {pend}.", "kind": "risk"})
    if ctx.get("recovery_overall_pct") is not None:
        insights.append({"text": f"Recovery is at {ctx['recovery_overall_pct']}% overall across "
                                 f"{counts['recovery_items']} tracked systems; {counts['systems_down']} still down"
                                 + (f" ({', '.join(ctx['systems_down'][:4])})" if ctx['systems_down'] else "") + ".",
                         "kind": "estimate"})
    if ctx["regulatory_deadlines"]:
        d0 = ctx["regulatory_deadlines"][0]
        insights.append({"text": f"Nearest regulatory clock: {d0['regulation']} ({d0['jurisdiction']}) with "
                                 f"{d0['hours_remaining']}h remaining — status {d0['status']}.", "kind": "risk"})
    insights.append({"text": f"Response progress {ctx['response_progress_pct']}% "
                             f"({counts['verified_or_complete']}/{counts['actions']} actions verified/complete), "
                             f"{counts['participants_engaged']} responders engaged.", "kind": "fact"})
    actions = []
    if counts["awaiting_approval"]:
        actions.append("Convene the war room to clear pending executive decisions before the next update.")
    if ctx["regulatory_deadlines"]:
        actions.append("Confirm the nearest regulatory notification decision with legal counsel.")
    if ctx["systems_down"]:
        actions.append(f"Prioritise restoration of down systems: {', '.join(ctx['systems_down'][:3])}.")
    actions.append("Publish an executive brief from the current, audit-logged crisis record.")
    return {"headline": f"{c.get('severity')} crisis {c['ref']} in {c.get('phase')} — "
                        f"{counts['awaiting_approval']} decision(s) pending, recovery "
                        f"{ctx.get('recovery_overall_pct', 0)}%.",
            "insights": insights[:5], "actions": actions[:4],
            "model": "obserra/crisis-grounded", "generated_at": datetime.now(timezone.utc).isoformat()}


async def _compute_crisis_insight(org_id: str, ref: str | None = None):
    """Board-grade AI briefing grounded ONLY in the live crisis case (case, events, actions,
    decisions, recovery, regulatory obligations). Cached 120s per org+case."""
    import os, json, asyncio, re
    ctx = await _crisis_insight_context(org_id, ref)
    if not ctx:
        return {"headline": "No active crisis case", "insights": [
            {"text": "No crisis case exists yet. Open a case or start Demo Mode to populate the command centre.", "kind": "fact"}],
            "actions": ["Open a new crisis case from Incident Command.", "Enable Demo Mode for a staged walkthrough."],
            "model": "obserra/crisis-grounded", "generated_at": datetime.now(timezone.utc).isoformat()}
    ck = (org_id, ctx["case"]["ref"], ctx["counts"]["events"], ctx["counts"]["actions"],
          ctx["counts"]["recovery_items"], ctx["counts"]["systems_down"],
          ctx["counts"]["regulatory_obligations"], ctx["counts"]["awaiting_approval"])
    hit = _CRISIS_INSIGHT_CACHE.get(ck)
    if hit and (datetime.now(timezone.utc) - hit["ts"]).total_seconds() < 120:
        return hit["data"]
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage, TextDelta, StreamDone
        system = (
            "You are the Obserra Cyber Crisis Commander AI Analyst. Read the LIVE crisis-case JSON and return a "
            "concise, executive incident briefing STRICTLY as JSON: {\"headline\": str, \"insights\": "
            "[{\"text\": str, \"kind\": one of \"fact\"|\"estimate\"|\"risk\"}], \"actions\": [str]}. "
            "3-5 insights, 2-4 actions. Ground EVERY statement in the crisis data — cite the case ref, decision "
            "titles, recovery percentages, systems still down and regulatory deadlines. This is a cyber incident "
            "command briefing: NEVER mention SAP access posture, SoD conflicts, or unrelated governance data. "
            "Return ONLY the JSON object.")
        chat = LlmChat(api_key=os.environ["EMERGENT_LLM_KEY"], session_id=f"crisis-insight-{org_id}-{ctx['case']['ref']}",
                       system_message=system).with_model("openai", "gpt-5.4")
        prompt = f"LIVE CRISIS CASE CONTEXT (JSON):\n{json.dumps(ctx, default=str)[:9000]}"
        collected = []

        async def _run():
            async for ev in chat.stream_message(UserMessage(text=prompt)):
                if isinstance(ev, TextDelta):
                    collected.append(ev.content)
                elif isinstance(ev, StreamDone):
                    break
        await asyncio.wait_for(_run(), timeout=16)
        raw = "".join(collected).strip()
        m = re.search(r"\{.*\}", raw, re.S)
        parsed = json.loads(m.group(0)) if m else None
        if not parsed or not parsed.get("insights"):
            data = _crisis_insight_fallback(ctx)
        else:
            parsed.setdefault("actions", [])
            parsed["model"] = "openai/gpt-5.4"
            parsed["generated_at"] = datetime.now(timezone.utc).isoformat()
            data = parsed
    except Exception:
        data = _crisis_insight_fallback(ctx)
    _CRISIS_INSIGHT_CACHE[ck] = {"ts": datetime.now(timezone.utc), "data": data}
    return data


@api.get("/insight")
async def crisis_insight(ref: str | None = None, user: dict = Depends(get_current_user)):
    return await _compute_crisis_insight(user["org_id"], ref)


# ---------------------------------------------------------------------------
# Email the grounded crisis brief to the board (Resend via kernel.notifications)
# ---------------------------------------------------------------------------
def _brief_html(insight: dict, case: dict) -> str:
    kind_color = {"fact": "#0ea5e9", "estimate": "#f59e0b", "risk": "#ef4444"}
    items = "".join(
        f'<li style="margin:6px 0"><span style="font:11px monospace;text-transform:uppercase;'
        f'color:{kind_color.get(i.get("kind"), "#64748b")}">{i.get("kind", "")}</span><br/>{i.get("text", "")}</li>'
        for i in insight.get("insights", []))
    actions = "".join(f"<li style='margin:4px 0'>{a}</li>" for a in insight.get("actions", []))
    return (
        f'<div style="font-family:Arial,Helvetica,sans-serif;max-width:640px;margin:auto;color:#0f172a">'
        f'<div style="background:#0b1220;color:#fff;padding:18px 22px;border-radius:12px 12px 0 0">'
        f'<div style="font-size:11px;letter-spacing:2px;color:#f87171">OBSERRA · CYBER CRISIS COMMANDER</div>'
        f'<div style="font-size:20px;font-weight:800;margin-top:4px">Executive Crisis Brief — {case.get("ref", "")}</div>'
        f'<div style="font-size:12px;color:#94a3b8;margin-top:4px">{case.get("title", "")} · {case.get("severity", "")} · '
        f'{case.get("status", "")} / {case.get("phase", "")}</div></div>'
        f'<div style="border:1px solid #e2e8f0;border-top:0;border-radius:0 0 12px 12px;padding:20px 22px">'
        f'<p style="font-size:15px;font-weight:700;line-height:1.4">{insight.get("headline", "")}</p>'
        f'<ul style="padding-left:18px;font-size:13px;line-height:1.5">{items}</ul>'
        f'<div style="font-size:12px;font-weight:700;text-transform:uppercase;color:#64748b;margin-top:14px">Recommended actions</div>'
        f'<ol style="padding-left:18px;font-size:13px;line-height:1.5">{actions}</ol>'
        f'<p style="font-size:11px;color:#94a3b8;margin-top:16px">Grounded in the live crisis case, decisions, recovery and '
        f'regulatory clocks. Generated by Obserra Cyber Crisis Commander · {insight.get("model", "")} · {insight.get("generated_at", "")}.</p>'
        f'</div></div>')


@api.post("/cases/{ref}/email-brief")
async def email_crisis_brief(ref: str, user: dict = Depends(get_current_user)):
    _require_operator(user)
    org_id = user["org_id"]
    case = await _get_case(org_id, ref)
    insight = await _compute_crisis_insight(org_id, ref)
    html = _brief_html(insight, case)
    recipients = await db.users.find(
        {"org_id": org_id, "role": {"$in": ["admin", "executive", "owner"]}},
        {"_id": 0, "email": 1}).to_list(200)
    emails = [r["email"] for r in recipients if r.get("email")]
    if not emails:
        raise HTTPException(status_code=400, detail="No admin/executive recipients found for this organisation.")
    from kernel import notifications
    sent = 0
    for em in emails:
        try:
            await notifications.send_email(em, f"Executive Crisis Brief — {ref}", html)
            sent += 1
        except Exception:
            pass
    await _audit(org_id, _actor(user), "crisis.brief.email", f"{ref} -> {sent}/{len(emails)} recipients")
    return {"sent": sent, "recipients": emails}


# ---------------------------------------------------------------------------
# Regulatory clock auto-alerts — Slack/Teams ping when a notification deadline
# nears or passes. Runs hourly (folded into the platform hourly cron) and can
# be triggered on demand. Dedupes per obligation via alert_state escalation.
# ---------------------------------------------------------------------------
async def run_regulatory_clock_alerts(org_id: str | None = None) -> int:
    from self_scan import _post_chat_alert
    now = datetime.now(timezone.utc)
    active = {"Assessing", "Notification Required", "On Hold"}
    query: dict = {"status": {"$in": list(active)}}
    if org_id:
        query["org_id"] = org_id
    sent = 0
    async for o in db.crisis_obligations.find(query):
        dl = _parse_iso(o.get("deadline_at"))
        if not dl:
            continue
        hrs = (dl - now).total_seconds() / 3600
        within = int(o.get("notify_within_hours") or 24)
        if hrs <= 0:
            new_state = "overdue"
        elif hrs <= within:
            new_state = "approaching"
        else:
            continue
        prev = o.get("alert_state") or ""
        if prev == new_state or (prev == "overdue" and new_state == "approaching"):
            continue
        overdue = new_state == "overdue"
        title = (f"{'🔴 OVERDUE' if overdue else '⚠️ Approaching'} regulatory deadline — "
                 f"{o.get('regulation')} ({o.get('jurisdiction')})")
        text = (f"Crisis {o.get('case_ref')}: {o.get('regulation')} in {o.get('jurisdiction')} is "
                + (f"OVERDUE by {round(abs(hrs), 1)}h" if overdue else f"{round(hrs, 1)}h from its notification deadline")
                + f". Status: {o.get('status')}. Responsible: {o.get('responsible') or 'unassigned'}. "
                  f"Evidence-only — legal confirms obligation.")
        try:
            await _post_chat_alert(o["org_id"], title, text)
        except Exception:
            pass
        await db.crisis_obligations.update_one(
            {"org_id": o["org_id"], "case_ref": o["case_ref"], "obligation_id": o["obligation_id"]},
            {"$set": {"alert_state": new_state, "alert_sent_at": now.isoformat()}})
        try:
            await db.crisis_events.insert_one({
                "org_id": o["org_id"], "case_ref": o["case_ref"],
                "event_id": await _next_ref(o["org_id"], "crisis_events", "EVT"),
                "kind": "Legal", "title": title, "detail": text, "source": "Regulatory Timer",
                "severity": "Critical" if overdue else "High",
                "occurred_at": now.isoformat(), "created_at": now.isoformat(),
                "created_by": "Obserra Regulatory Timer"})
        except Exception:
            pass
        sent += 1
    return sent


@api.post("/regulatory/scan")
async def regulatory_scan(user: dict = Depends(get_current_user)):
    _require_operator(user)
    sent = await run_regulatory_clock_alerts(org_id=user["org_id"])
    return {"alerts_sent": sent}


# ---------------------------------------------------------------------------
# ServiceNow SecOps ingestion — pull live security incidents from a CONNECTED
# ServiceNow instance and open crisis cases from them (deduped by external ref).
# ---------------------------------------------------------------------------
_SN_SEVERITY = {"1": "Critical", "2": "High", "3": "Medium", "4": "Low", "5": "Low"}


async def _ingest_servicenow(org_id: str, actor: str = "ServiceNow SecOps"):
    import httpx
    st = await db.connector_state.find_one({"org_id": org_id, "cid": "servicenow"}, {"_id": 0})
    creds = (st or {}).get("creds") or {}
    base = (creds.get("base") or "").rstrip("/")
    token = creds.get("token")
    if not base or not token:
        raise HTTPException(
            status_code=400,
            detail="ServiceNow is not connected. Connect it in Connector Health (Enterprise Connectors) first.")
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    params = {"sysparm_limit": "25", "sysparm_display_value": "true",
              "sysparm_query": "active=true^ORDERBYDESCsys_created_on"}
    used_table = "sn_si_incident"
    async with httpx.AsyncClient(timeout=20, follow_redirects=True) as c:
        try:
            r = await c.get(f"{base}/api/now/table/sn_si_incident", headers=headers, params=params)
            if r.status_code == 404:
                used_table = "incident"
                r = await c.get(f"{base}/api/now/table/incident", headers=headers, params=params)
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"ServiceNow unreachable: {str(e)[:160]}")
    if r.status_code in (401, 403):
        raise HTTPException(status_code=502,
                            detail=f"ServiceNow rejected the credential ({r.status_code}). Re-connect it in Connector Health.")
    if r.status_code >= 400:
        raise HTTPException(status_code=502, detail=f"ServiceNow returned {r.status_code}.")
    records = (r.json() or {}).get("result", [])
    ingested, skipped, refs = 0, 0, []
    now = _now()
    for rec in records:
        sys_id = rec.get("sys_id") or rec.get("number")
        if not sys_id:
            continue
        external_ref = f"servicenow:{sys_id}"
        if await db.crisis_cases.find_one({"org_id": org_id, "external_ref": external_ref}, {"_id": 1}):
            skipped += 1
            continue
        sev = _SN_SEVERITY.get(str(rec.get("severity") or rec.get("priority") or "3").strip()[:1], "High")
        title = (rec.get("short_description") or rec.get("number") or "ServiceNow security incident")[:180]
        ref = await _next_ref(org_id, "crisis_cases", "CRISIS")
        record = {
            "ref": ref, "org_id": org_id, "title": title, "severity": sev,
            "summary": (rec.get("description") or "")[:5000],
            "incident_refs": [rec.get("number")] if rec.get("number") else [],
            "risk_refs": [], "business_services": [],
            "incident_commander": "", "executive_sponsor": "",
            "status": "Open", "phase": "Triage", "started_at": now, "updated_at": now,
            "next_update_at": None, "created_by": "ServiceNow SecOps",
            "source": "ServiceNow SecOps", "external_ref": external_ref}
        await db.crisis_cases.insert_one(record.copy())
        await db.crisis_events.insert_one({
            "org_id": org_id, "case_ref": ref,
            "event_id": await _next_ref(org_id, "crisis_events", "EVT"),
            "kind": "Detection", "title": f"Ingested from ServiceNow ({rec.get('number', '')})",
            "detail": title, "source": "ServiceNow SecOps", "severity": sev,
            "occurred_at": now, "created_at": now, "created_by": "ServiceNow SecOps"})
        ingested += 1
        refs.append(ref)
    await _audit(org_id, actor, "crisis.ingest.servicenow",
                 f"{ingested} ingested, {skipped} skipped from {used_table}")
    return {"ingested": ingested, "skipped": skipped, "source_table": used_table, "refs": refs}


@api.post("/ingest/servicenow")
async def ingest_servicenow(user: dict = Depends(get_current_user)):
    _require_operator(user)
    return await _ingest_servicenow(user["org_id"], _actor(user))


async def run_servicenow_auto_ingest(org_id: str | None = None) -> dict:
    """Cron: auto-open crisis cases from any org with a CONNECTED ServiceNow connector."""
    query = {"cid": "servicenow", "state": "connected"}
    if org_id:
        query["org_id"] = org_id
    total_orgs, total_ingested = 0, 0
    async for st in db.connector_state.find(query, {"_id": 0, "org_id": 1}):
        total_orgs += 1
        try:
            res = await _ingest_servicenow(st["org_id"], "ServiceNow Auto-Ingest")
            total_ingested += res.get("ingested", 0)
        except Exception:
            pass
    return {"orgs": total_orgs, "ingested": total_ingested}


# ---------------------------------------------------------------------------
# Scheduled Board Brief — auto-email the grounded crisis brief on a per-case
# cadence while the crisis is active. Folded into the hourly platform cron.
# ---------------------------------------------------------------------------
async def run_scheduled_briefs(org_id: str | None = None) -> int:
    from kernel import notifications
    now = datetime.now(timezone.utc)
    query: dict = {"status": {"$ne": "Closed"}, "brief_schedule_hours": {"$gt": 0}}
    if org_id:
        query["org_id"] = org_id
    sent_cases = 0
    async for case in db.crisis_cases.find(query, {"_id": 0}):
        hours = int(case.get("brief_schedule_hours") or 0)
        if hours <= 0:
            continue
        last = _parse_iso(case.get("brief_last_sent_at"))
        if last and (now - last).total_seconds() < hours * 3600:
            continue
        oid = case["org_id"]
        recipients = await db.users.find(
            {"org_id": oid, "role": {"$in": ["admin", "executive", "owner"]}},
            {"_id": 0, "email": 1}).to_list(200)
        emails = [r["email"] for r in recipients if r.get("email")]
        if not emails:
            continue
        insight = await _compute_crisis_insight(oid, case["ref"])
        html = _brief_html(insight, case)
        for em in emails:
            try:
                await notifications.send_email(em, f"Scheduled Crisis Brief — {case['ref']}", html)
            except Exception:
                pass
        await db.crisis_cases.update_one(
            {"org_id": oid, "ref": case["ref"]}, {"$set": {"brief_last_sent_at": now.isoformat()}})
        await db.crisis_events.insert_one({
            "org_id": oid, "case_ref": case["ref"],
            "event_id": await _next_ref(oid, "crisis_events", "EVT"),
            "kind": "Communication", "title": f"Scheduled board brief emailed to {len(emails)} recipient(s)",
            "detail": insight.get("headline", ""), "source": "Scheduled Brief", "severity": "Info",
            "occurred_at": now.isoformat(), "created_at": now.isoformat(), "created_by": "Obserra Scheduled Brief"})
        sent_cases += 1
    return sent_cases


# ---------------------------------------------------------------------------
# War Room Live Chat — an in-room message thread per crisis case.
# ---------------------------------------------------------------------------
class CrisisMessage(BaseModel):
    text: str = Field(min_length=1, max_length=2000)


@api.get("/cases/{ref}/messages")
async def list_messages(ref: str, user: dict = Depends(get_current_user)):
    org_id = user["org_id"]
    await _get_case(org_id, ref)
    return await db.crisis_messages.find(
        {"org_id": org_id, "case_ref": ref}, {"_id": 0}).sort("created_at", ASCENDING).to_list(500)


@api.post("/cases/{ref}/messages")
async def post_message(ref: str, body: CrisisMessage, user: dict = Depends(get_current_user)):
    from self_scan import _post_chat_alert
    org_id = user["org_id"]
    case = await _get_case(org_id, ref)
    now = _now()
    text = body.text.strip()
    author = user.get("name") or user.get("email") or "Responder"
    participants = await db.crisis_participants.find(
        {"org_id": org_id, "case_ref": ref}, {"_id": 0}).to_list(300)
    lowered = text.lower()
    mentions, seen = [], set()
    for p in participants:
        for token in (p.get("role"), p.get("name")):
            if token and f"@{token.lower()}" in lowered:
                key = (p.get("name"), p.get("role"))
                if key in seen:
                    continue
                seen.add(key)
                mentions.append({"name": p.get("name"), "role": p.get("role"), "contact": p.get("contact")})
                break
    msg = {
        "org_id": org_id, "case_ref": ref,
        "message_id": await _next_ref(org_id, "crisis_messages", "MSG"),
        "author": author,
        "role": user.get("role") or "responder",
        "text": text,
        "mentions": mentions,
        "created_at": now}
    await db.crisis_messages.insert_one(msg.copy())
    if mentions:
        who = ", ".join(f"{m['role']} ({m['name']})" for m in mentions)
        try:
            await _post_chat_alert(
                org_id,
                f"🔔 War room mention — {case.get('ref')} ({(case.get('title') or '')[:60]})",
                f"{author} mentioned {who} in the war room:\n\"{text}\"")
        except Exception:
            pass
    return msg


@api.post("/cases/{ref}/messages/{message_id}/to-action")
async def message_to_action(ref: str, message_id: str, user: dict = Depends(get_current_user)):
    _require_operator(user)
    org_id = user["org_id"]
    await _get_case(org_id, ref)
    msg = await db.crisis_messages.find_one(
        {"org_id": org_id, "case_ref": ref, "message_id": message_id}, {"_id": 0})
    if not msg:
        raise HTTPException(status_code=404, detail="Message not found")
    if msg.get("converted_action_id"):
        raise HTTPException(status_code=400, detail=f"Already tracked as {msg['converted_action_id']}")
    now = _now()
    action = {
        "org_id": org_id, "case_ref": ref,
        "action_id": await _next_ref(org_id, "crisis_actions", "ACT"),
        "title": (msg.get("text") or "War room decision")[:220],
        "owner": msg.get("author", ""),
        "priority": "High",
        "status": "Awaiting Approval",
        "action_type": "Decision",
        "due_at": None,
        "decision_required": True,
        "decision_owner": msg.get("author", ""),
        "decision_due_at": _sla_due("High", now),
        "business_impact": "", "technical_impact": "",
        "outcome": "", "approved_by": "",
        "source": "War Room Chat", "source_message_id": message_id,
        "created_at": now, "updated_at": now, "created_by": _actor(user)}
    await db.crisis_actions.insert_one(action.copy())
    await db.crisis_messages.update_one(
        {"org_id": org_id, "case_ref": ref, "message_id": message_id},
        {"$set": {"converted_action_id": action["action_id"]}})
    await db.crisis_events.insert_one({
        "org_id": org_id, "case_ref": ref,
        "event_id": await _next_ref(org_id, "crisis_events", "EVT"),
        "kind": "Decision",
        "title": f"War room message escalated to decision {action['action_id']}",
        "detail": action["title"], "source": "War Room Chat", "severity": "High",
        "occurred_at": now, "created_at": now, "created_by": _actor(user)})
    await db.crisis_cases.update_one({"org_id": org_id, "ref": ref}, {"$set": {"updated_at": now}})
    await _audit(org_id, _actor(user), "crisis.message.to_action", f"{ref}: {message_id} -> {action['action_id']}")
    return action


# ---------------------------------------------------------------------------
# Post-Crisis Report Pack — one downloadable PDF: timeline, decisions, response
# actions, recovery, regulatory record, war-room roster and chat log.
# ---------------------------------------------------------------------------
@api.get("/cases/{ref}/report-pack.pdf")
async def crisis_report_pack(ref: str, user: dict = Depends(get_current_user)):
    _require_operator(user)
    from studio import ReportExportBody, _report_markdown
    from reports import _build_pdf, _resolve_brand
    from fastapi.responses import StreamingResponse
    from bson import ObjectId
    org_id = user["org_id"]
    case = await _get_case(org_id, ref)
    org = await db.organizations.find_one({"_id": ObjectId(org_id)}) or {}
    events = await db.crisis_events.find({"org_id": org_id, "case_ref": ref}, {"_id": 0}).sort("occurred_at", ASCENDING).to_list(500)
    actions = await db.crisis_actions.find({"org_id": org_id, "case_ref": ref}, {"_id": 0}).to_list(500)
    obligations = await db.crisis_obligations.find({"org_id": org_id, "case_ref": ref}, {"_id": 0}).to_list(500)
    messages = await db.crisis_messages.find({"org_id": org_id, "case_ref": ref}, {"_id": 0}).sort("created_at", ASCENDING).to_list(1000)
    participants = await db.crisis_participants.find({"org_id": org_id, "case_ref": ref}, {"_id": 0}).to_list(500)
    recovery = await db.crisis_recovery.find({"org_id": org_id, "case_ref": ref}, {"_id": 0}).to_list(500)
    decisions = [a for a in actions if a.get("action_type") == "Decision" or a.get("decision_required")]
    dec_ids = {a["action_id"] for a in decisions}
    responses = [a for a in actions if a["action_id"] not in dec_ids]

    def _fmt(ts):
        return str(ts).replace("T", " ")[:19] if ts else "-"

    blocks = [
        {"heading": f"Crisis Report Pack — {case.get('title', '')}", "lines": [
            f"Case: {case.get('ref')}",
            f"Severity: {case.get('severity')} · Status: {case.get('status')} / {case.get('phase')}",
            f"Incident commander: {case.get('incident_commander') or 'Unassigned'}",
            f"Executive sponsor: {case.get('executive_sponsor') or 'Unassigned'}",
            f"Opened: {_fmt(case.get('started_at'))} · Last update: {_fmt(case.get('updated_at'))}",
            f"Business services: {', '.join(case.get('business_services') or []) or '-'}",
            f"Summary: {case.get('summary') or '-'}"]},
        {"heading": f"Incident Timeline ({len(events)} events)", "lines": [
            f"{_fmt(e.get('occurred_at'))} — [{e.get('kind')}/{e.get('severity')}] {e.get('title')} ({e.get('source') or 'manual'})" for e in events] or ["No timeline events recorded."]},
        {"heading": f"Executive Decisions ({len(decisions)})", "lines": [
            f"{d.get('action_id')} — {d.get('title')} — {d.get('status')} — owner {d.get('decision_owner') or d.get('owner') or '-'}" for d in decisions] or ["No executive decisions recorded."]},
        {"heading": f"Response Actions ({len(responses)})", "lines": [
            f"{a.get('action_id')} — {a.get('title')} — {a.get('status')} — {a.get('action_type')}" for a in responses] or ["No response actions recorded."]},
        {"heading": f"Recovery Status ({len(recovery)})", "lines": [
            f"{r.get('name')} — {r.get('status')} — {r.get('pct', 0)}% ({r.get('category') or '-'})" for r in recovery] or ["No recovery items tracked."]},
        {"heading": f"Regulatory Record ({len(obligations)})", "lines": [
            f"{o.get('jurisdiction')} — {o.get('regulation')} — {o.get('status')} — deadline {_fmt(o.get('deadline_at'))}" for o in obligations] or ["No regulatory obligations recorded."]},
        {"heading": f"War Room Roster ({len(participants)})", "lines": [
            f"{p.get('role')} — {p.get('name')} ({p.get('status')}) — {p.get('responsibility') or '-'}" for p in participants] or ["No participants recorded."]},
        {"heading": f"War Room Chat Log ({len(messages)} messages)", "lines": [
            f"{_fmt(m.get('created_at'))} {m.get('author')} ({m.get('role')}): {m.get('text')}" for m in messages] or ["No chat messages recorded."]},
    ]
    title = f"Crisis Report Pack {ref}"
    body = ReportExportBody(
        title=title,
        ai_narrative=(f"Consolidated post-crisis record for {ref}, assembled from the live, audit-logged crisis case: "
                      f"timeline, executive decisions, response actions, recovery, regulatory obligations, war-room "
                      f"roster and full chat log."),
        blocks=blocks)
    buf = _build_pdf(_report_markdown(body), title, cover=True,
                     org_name=(org.get("name") or None), brand=_resolve_brand(org))
    _slug = f"crisis-report-pack-{ref}".lower()
    fname = "".join(c for c in _slug if c.isascii() and (c.isalnum() or c == "-")) or "crisis-report-pack"
    await _audit(org_id, _actor(user), "crisis.report_pack", ref)
    return StreamingResponse(buf, media_type="application/pdf",
                             headers={"Content-Disposition": f'attachment; filename="{fname}.pdf"'})


# ---------------------------------------------------------------------------
# Identity containment via Microsoft Entra (LIVE Microsoft Graph) — list users
# and disable an account + revoke its sign-in sessions during a crisis.
# ---------------------------------------------------------------------------
async def _entra_creds(org_id: str):
    st = await db.connector_state.find_one(
        {"org_id": org_id, "cid": "entra", "state": "connected"}, {"_id": 0})
    return (st or {}).get("creds")


@api.get("/entra/users")
async def entra_users(q: str = "", user: dict = Depends(get_current_user)):
    _require_operator(user)
    import httpx
    from connectors_catalog import _entra_token
    creds = await _entra_creds(user["org_id"])
    if not creds:
        raise HTTPException(status_code=400, detail="Microsoft Entra is not connected. Connect it in Connector Health (Enterprise Connectors) first.")
    token, err = await _entra_token(creds)
    if err:
        raise HTTPException(status_code=502, detail=err[3])
    params = {"$top": "25", "$select": "id,displayName,userPrincipalName,mail,accountEnabled"}
    if q:
        safe = q.replace("'", "''")
        params["$filter"] = f"startswith(displayName,'{safe}') or startswith(userPrincipalName,'{safe}')"
    async with httpx.AsyncClient(timeout=20) as c:
        r = await c.get("https://graph.microsoft.com/v1.0/users", headers={"Authorization": f"Bearer {token}"}, params=params)
    if r.status_code >= 400:
        raise HTTPException(status_code=502, detail=f"Microsoft Graph returned {r.status_code}: {r.text[:160]}")
    return (r.json() or {}).get("value", [])


class ContainIdentity(BaseModel):
    user_id: str
    upn: str = ""


@api.post("/cases/{ref}/contain-identity")
async def contain_identity(ref: str, body: ContainIdentity, user: dict = Depends(get_current_user)):
    _require_operator(user)
    import httpx
    from connectors_catalog import _entra_token
    org_id = user["org_id"]
    await _get_case(org_id, ref)
    creds = await _entra_creds(org_id)
    if not creds:
        raise HTTPException(status_code=400, detail="Microsoft Entra is not connected. Connect it in Connector Health first.")
    token, err = await _entra_token(creds)
    if err:
        raise HTTPException(status_code=502, detail=err[3])
    headers = {"Authorization": f"Bearer {token}"}
    uid = body.user_id
    async with httpx.AsyncClient(timeout=20) as c:
        disable = await c.patch(f"https://graph.microsoft.com/v1.0/users/{uid}",
                                headers={**headers, "Content-Type": "application/json"}, json={"accountEnabled": False})
        if disable.status_code >= 400:
            raise HTTPException(status_code=502, detail=f"Disable failed ({disable.status_code}): {disable.text[:160]}")
        revoke = await c.post(f"https://graph.microsoft.com/v1.0/users/{uid}/revokeSignInSessions", headers=headers)
    revoked = revoke.status_code in (200, 204)
    now = _now()
    label = body.upn or uid
    await db.crisis_events.insert_one({
        "org_id": org_id, "case_ref": ref,
        "event_id": await _next_ref(org_id, "crisis_events", "EVT"),
        "kind": "Containment", "title": f"Identity contained via Microsoft Entra — {label}",
        "detail": f"Account disabled{' and sign-in sessions revoked' if revoked else ''} (live Microsoft Graph).",
        "source": "Microsoft Entra", "severity": "Critical",
        "occurred_at": now, "created_at": now, "created_by": _actor(user)})
    await db.crisis_actions.insert_one({
        "org_id": org_id, "case_ref": ref,
        "action_id": await _next_ref(org_id, "crisis_actions", "ACT"),
        "title": f"Contain identity {label} (disable + revoke sessions)", "owner": _actor(user),
        "priority": "Critical", "status": "Verified", "action_type": "Containment", "due_at": None,
        "decision_required": False, "decision_owner": "", "business_impact": "",
        "technical_impact": "Account disabled; sessions revoked",
        "outcome": "Executed via Microsoft Entra (Graph)", "approved_by": _actor(user),
        "source": "Microsoft Entra", "created_at": now, "updated_at": now, "created_by": _actor(user)})
    await db.crisis_cases.update_one({"org_id": org_id, "ref": ref}, {"$set": {"updated_at": now}})
    await _audit(org_id, _actor(user), "crisis.contain_identity",
                 f"{ref}: {label} disabled={disable.status_code} revoked={revoked}")
    return {"user_id": uid, "disabled": True, "sessions_revoked": revoked}


# ---------------------------------------------------------------------------
# Entra Risky Users — live Identity Protection signals surfaced into the crisis.
# ---------------------------------------------------------------------------
@api.get("/entra/risky-users")
async def entra_risky_users(user: dict = Depends(get_current_user)):
    _require_operator(user)
    import httpx
    from connectors_catalog import _entra_token
    creds = await _entra_creds(user["org_id"])
    if not creds:
        raise HTTPException(status_code=400, detail="Microsoft Entra is not connected. Connect it in Connector Health first.")
    token, err = await _entra_token(creds)
    if err:
        raise HTTPException(status_code=502, detail=err[3])
    ep = "https://graph.microsoft.com/v1.0/identityProtection/riskyUsers"
    params = {"$top": "25",
              "$filter": "riskState ne 'dismissed' and riskState ne 'remediated'",
              "$orderby": "riskLastUpdatedDateTime desc"}
    async with httpx.AsyncClient(timeout=20) as c:
        r = await c.get(ep, headers={"Authorization": f"Bearer {token}"}, params=params)
    if r.status_code in (401, 403):
        raise HTTPException(status_code=502, detail=f"Microsoft Graph denied risky-users ({r.status_code}). Grant IdentityRiskyUser.Read.All (needs Entra ID P2) + admin consent.")
    if r.status_code >= 400:
        raise HTTPException(status_code=502, detail=f"Microsoft Graph returned {r.status_code}: {r.text[:160]}")
    return [{"id": u.get("id"), "userPrincipalName": u.get("userPrincipalName"),
             "displayName": u.get("userDisplayName"), "riskLevel": u.get("riskLevel"),
             "riskState": u.get("riskState"), "riskDetail": u.get("riskDetail"),
             "lastUpdated": u.get("riskLastUpdatedDateTime")} for u in (r.json() or {}).get("value", [])]


# ---------------------------------------------------------------------------
# Decision SLA breach alerts — ping Teams/Slack when a pending decision blows
# its approval SLA. Runs hourly (folded into the platform cron) + on demand.
# ---------------------------------------------------------------------------
async def run_decision_sla_alerts(org_id: str | None = None) -> int:
    from self_scan import _post_chat_alert
    now = datetime.now(timezone.utc)
    query: dict = {"status": "Awaiting Approval", "decision_due_at": {"$ne": None}, "sla_alerted": {"$ne": True}}
    if org_id:
        query["org_id"] = org_id
    sent = 0
    async for a in db.crisis_actions.find(query):
        due = _parse_iso(a.get("decision_due_at"))
        if not due or due > now:
            continue
        overdue_h = round((now - due).total_seconds() / 3600, 1)
        title = f"⏰ Decision SLA breached — {a.get('case_ref')} {a.get('action_id')}"
        text = (f"'{a.get('title')}' has blown its approval SLA by {overdue_h}h "
                f"(owner: {a.get('decision_owner') or 'unassigned'}, priority {a.get('priority')}). "
                f"Approve or escalate in the Decision Room.")
        try:
            await _post_chat_alert(a["org_id"], title, text)
        except Exception:
            pass
        await db.crisis_actions.update_one(
            {"org_id": a["org_id"], "case_ref": a["case_ref"], "action_id": a["action_id"]},
            {"$set": {"sla_alerted": True}})
        await db.crisis_events.insert_one({
            "org_id": a["org_id"], "case_ref": a["case_ref"],
            "event_id": await _next_ref(a["org_id"], "crisis_events", "EVT"),
            "kind": "Decision", "title": title, "detail": text, "source": "SLA Monitor", "severity": "High",
            "occurred_at": now.isoformat(), "created_at": now.isoformat(), "created_by": "Obserra SLA Monitor"})
        sent += 1
    return sent


@api.post("/decisions/sla-scan")
async def decisions_sla_scan(user: dict = Depends(get_current_user)):
    _require_operator(user)
    sent = await run_decision_sla_alerts(org_id=user["org_id"])
    return {"alerts_sent": sent}


# ---------------------------------------------------------------------------
# Containment Playbook — one-click bundle: disable the account, revoke all its
# sign-in sessions, and notify the war room + Teams/Slack in a single action.
# ---------------------------------------------------------------------------
class ContainPlaybook(BaseModel):
    user_id: str
    upn: str = ""
    notify: bool = True


@api.post("/cases/{ref}/contain-playbook")
async def contain_playbook(ref: str, body: ContainPlaybook, user: dict = Depends(get_current_user)):
    _require_operator(user)
    import httpx
    from connectors_catalog import _entra_token
    from self_scan import _post_chat_alert
    org_id = user["org_id"]
    case = await _get_case(org_id, ref)
    creds = await _entra_creds(org_id)
    if not creds:
        raise HTTPException(status_code=400, detail="Microsoft Entra is not connected. Connect it in Connector Health first.")
    token, err = await _entra_token(creds)
    if err:
        raise HTTPException(status_code=502, detail=err[3])
    headers = {"Authorization": f"Bearer {token}"}
    uid = body.user_id
    label = body.upn or uid
    async with httpx.AsyncClient(timeout=20) as c:
        disable = await c.patch(f"https://graph.microsoft.com/v1.0/users/{uid}",
                                headers={**headers, "Content-Type": "application/json"}, json={"accountEnabled": False})
        if disable.status_code >= 400:
            raise HTTPException(status_code=502, detail=f"Disable failed ({disable.status_code}): {disable.text[:160]}")
        revoke = await c.post(f"https://graph.microsoft.com/v1.0/users/{uid}/revokeSignInSessions", headers=headers)
    revoked = revoke.status_code in (200, 204)
    now = _now()
    actor = _actor(user)
    steps = ["Account disabled", "Sign-in sessions revoked" if revoked else "Session revoke not confirmed"]
    detail = f"Containment playbook executed for {label}: {', '.join(steps)} (live Microsoft Graph)."
    await db.crisis_events.insert_one({
        "org_id": org_id, "case_ref": ref,
        "event_id": await _next_ref(org_id, "crisis_events", "EVT"),
        "kind": "Containment", "title": f"Containment playbook — {label}",
        "detail": detail, "source": "Microsoft Entra", "severity": "Critical",
        "occurred_at": now, "created_at": now, "created_by": actor})
    await db.crisis_actions.insert_one({
        "org_id": org_id, "case_ref": ref,
        "action_id": await _next_ref(org_id, "crisis_actions", "ACT"),
        "title": f"Containment playbook: {label} (disable + revoke + notify)", "owner": actor,
        "priority": "Critical", "status": "Verified", "action_type": "Containment", "due_at": None,
        "decision_required": False, "decision_owner": "", "business_impact": "",
        "technical_impact": ", ".join(steps),
        "outcome": "Executed via Microsoft Entra (Graph)", "approved_by": actor,
        "source": "Containment Playbook", "created_at": now, "updated_at": now, "created_by": actor})
    notified = False
    if body.notify:
        chat_text = f"🛡️ Containment playbook executed by {actor} on {label}: {', '.join(steps)}."
        try:
            await db.crisis_messages.insert_one({
                "org_id": org_id, "case_ref": ref,
                "message_id": await _next_ref(org_id, "crisis_messages", "MSG"),
                "author": "Obserra Containment Playbook", "role": "system",
                "text": chat_text, "mentions": [], "created_at": now})
        except Exception:
            pass
        try:
            await _post_chat_alert(org_id,
                                   f"🛡️ Containment playbook — {case.get('ref')} {(case.get('title') or '')[:60]}",
                                   chat_text)
            notified = True
        except Exception:
            pass
    await db.crisis_cases.update_one({"org_id": org_id, "ref": ref}, {"$set": {"updated_at": now}})
    await _audit(org_id, actor, "crisis.contain_playbook",
                 f"{ref}: {label} disabled={disable.status_code} revoked={revoked} notified={notified}")
    return {"user_id": uid, "disabled": True, "sessions_revoked": revoked, "notified": notified, "steps": steps}


# ===========================================================================
# Live Incident Feed — generic inbound webhook. Any SIEM/EDR/SOAR/ServiceNow
# can PUSH incidents + containment steps onto the live timeline in real time,
# authenticated solely by a rotatable per-org secret.
# ===========================================================================
async def _webhook_secret(org_id: str, create: bool = False):
    from bson import ObjectId
    import secrets as _s
    org = await db.organizations.find_one({"_id": ObjectId(org_id)}, {"crisis_webhook_secret": 1}) or {}
    sec = org.get("crisis_webhook_secret")
    if not sec and create:
        sec = "whk_" + _s.token_urlsafe(24)
        await db.organizations.update_one({"_id": ObjectId(org_id)}, {"$set": {"crisis_webhook_secret": sec}})
    return sec


@api.get("/webhook/config")
async def webhook_config(user: dict = Depends(get_current_user)):
    _require_operator(user)
    org_id = user["org_id"]
    secret = await _webhook_secret(org_id, create=True)
    recent = await db.crisis_events.find(
        {"org_id": org_id, "via": "webhook"}, {"_id": 0}
    ).sort("created_at", DESCENDING).to_list(15)
    total = await db.crisis_events.count_documents({"org_id": org_id, "via": "webhook"})
    return {"secret": secret, "path": "/api/crisis/ingest/webhook", "recent": recent, "count": total}


@api.post("/webhook/rotate")
async def webhook_rotate(user: dict = Depends(get_current_user)):
    _require_operator(user)
    from bson import ObjectId
    import secrets as _s
    sec = "whk_" + _s.token_urlsafe(24)
    await db.organizations.update_one({"_id": ObjectId(user["org_id"])}, {"$set": {"crisis_webhook_secret": sec}})
    await _audit(user["org_id"], _actor(user), "crisis.webhook.rotate", "rotated")
    return {"secret": sec}


# --- Vendor payload mapping — map any SIEM/EDR/SOAR native JSON to our shape --
_SEV_EXACT = {"5": "Critical", "sev1": "Critical", "p1": "Critical",
              "4": "High", "sev2": "High", "p2": "High",
              "3": "Medium", "sev3": "Medium", "p3": "Medium",
              "2": "Low", "1": "Low", "sev4": "Low", "sev5": "Low", "p4": "Low", "p5": "Low"}
_SEV_WORDS = [("critical", "Critical"), ("crit", "Critical"), ("emergency", "Critical"), ("fatal", "Critical"),
              ("high", "High"), ("error", "High"),
              ("medium", "Medium"), ("moderate", "Medium"), ("warn", "Medium"),
              ("low", "Low"), ("info", "Low")]


def _severity_norm(val) -> str:
    if val is None:
        return "High"
    s = str(val).strip().lower()
    if not s:
        return "High"
    if s in _SEV_EXACT:
        return _SEV_EXACT[s]
    for word, out in _SEV_WORDS:
        if word in s:
            return out
    return "Medium"


def _dig(obj, path):
    cur = obj
    for part in path.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return None
    return cur


def _first(payload, paths):
    for p in paths:
        v = _dig(payload, p)
        if v not in (None, "", []):
            return v
    return None


_VENDOR_MAPS = {
    "generic": {"title": ["title", "name", "message", "summary", "rule", "alert", "displayName", "short_description"],
                "detail": ["detail", "description", "message", "info", "body"],
                "severity": ["severity", "priority", "level", "urgency", "risk"],
                "source": ["source", "vendor", "product", "tool"], "kind": ["kind", "type", "category", "class"],
                "occurred_at": ["occurred_at", "timestamp", "time", "@timestamp", "createdAt", "eventTime"],
                "default_source": "External", "default_kind": "Detection"},
    "crowdstrike": {"title": ["detection_name", "name", "DetectName", "metadata.eventType", "pattern_disposition_description"],
                    "detail": ["description", "technique", "tactic", "filename", "cmdline"],
                    "severity": ["severity_name", "SeverityName", "max_severity", "severity"],
                    "source": [], "kind": [], "occurred_at": ["timestamp", "created_timestamp", "ProcessStartTime"],
                    "default_source": "CrowdStrike", "default_kind": "Threat"},
    "splunk": {"title": ["search_name", "result.signature", "result.rule_title", "result.source", "name"],
               "detail": ["result._raw", "result.description", "result.message"],
               "severity": ["result.urgency", "result.severity", "urgency", "severity"],
               "source": [], "kind": [], "occurred_at": ["result._time", "result.timestamp"],
               "default_source": "Splunk", "default_kind": "Detection"},
    "sentinel": {"title": ["properties.alertDisplayName", "AlertName", "DisplayName", "properties.displayName"],
                 "detail": ["properties.description", "Description", "properties.remediationSteps"],
                 "severity": ["properties.severity", "Severity", "AlertSeverity"],
                 "source": [], "kind": [], "occurred_at": ["properties.timeGenerated", "TimeGenerated", "properties.startTimeUtc"],
                 "default_source": "Microsoft Sentinel", "default_kind": "Detection"},
    "servicenow": {"title": ["short_description", "number", "u_short_description"],
                   "detail": ["description", "comments", "work_notes"],
                   "severity": ["severity", "priority", "urgency", "impact"],
                   "source": [], "kind": [], "occurred_at": ["opened_at", "sys_created_on"],
                   "default_source": "ServiceNow", "default_kind": "Incident"},
}


def _map_vendor_event(fmt: str, payload: dict) -> dict:
    m = _VENDOR_MAPS.get((fmt or "generic").lower(), _VENDOR_MAPS["generic"])
    return {
        "kind": str(_first(payload, m["kind"]) or m["default_kind"])[:40],
        "title": str(_first(payload, m["title"]) or "Security event")[:200],
        "detail": str(_first(payload, m["detail"]) or "")[:1000],
        "source": str(_first(payload, m["source"]) or m["default_source"])[:60],
        "severity": _severity_norm(_first(payload, m["severity"])),
        "occurred_at": (str(_first(payload, m["occurred_at"])) if _first(payload, m["occurred_at"]) else None),
    }


class WebhookEvent(BaseModel):
    kind: str = "Detection"
    title: str
    detail: str = ""
    source: str = "External"
    severity: str = "High"
    occurred_at: str | None = None


class WebhookIngest(BaseModel):
    secret: str
    case_ref: str | None = None
    open_case: bool = False
    case_title: str | None = None
    severity: str | None = None
    events: list[WebhookEvent] = []
    format: str | None = None
    payload: dict | None = None
    payloads: list[dict] | None = None


class TestMap(BaseModel):
    format: str = "generic"
    payload: dict = {}


@api.post("/webhook/test-map")
async def webhook_test_map(body: TestMap, user: dict = Depends(get_current_user)):
    _require_operator(user)
    return {"format": body.format, "mapped": _map_vendor_event(body.format, body.payload or {}),
            "formats": list(_VENDOR_MAPS.keys())}


@api.post("/ingest/webhook")
async def ingest_webhook(body: WebhookIngest):
    """PUBLIC endpoint — authenticated solely by the per-org webhook secret."""
    if not body.secret:
        raise HTTPException(status_code=401, detail="Missing webhook secret.")
    org = await db.organizations.find_one({"crisis_webhook_secret": body.secret}, {"_id": 1})
    if not org:
        raise HTTPException(status_code=401, detail="Invalid webhook secret.")
    org_id = str(org["_id"])
    raw_events = [e.model_dump() for e in body.events]
    if not raw_events and body.format:
        vend = body.payloads if body.payloads is not None else ([body.payload] if body.payload else [])
        raw_events = [_map_vendor_event(body.format, p) for p in vend if isinstance(p, dict)]
    if not raw_events:
        raise HTTPException(status_code=400, detail="No events provided. Send 'events', or a 'format' + 'payload'.")
    if len(raw_events) > 50:
        raise HTTPException(status_code=413, detail="Too many events in one call (max 50).")
    now = _now()
    ref = body.case_ref
    if ref:
        case = await db.crisis_cases.find_one({"org_id": org_id, "ref": ref}, {"_id": 0, "ref": 1})
        if not case:
            raise HTTPException(status_code=404, detail=f"Case {ref} not found.")
    else:
        case = await db.crisis_cases.find_one(
            {"org_id": org_id, "status": {"$ne": "Closed"}}, {"_id": 0, "ref": 1},
            sort=[("updated_at", DESCENDING)])
        if case:
            ref = case["ref"]
        elif body.open_case or body.case_title:
            ref = await _next_ref(org_id, "crisis_cases", "CRISIS")
            await db.crisis_cases.insert_one({
                "ref": ref, "org_id": org_id, "via": "webhook",
                "title": body.case_title or "Incident opened from inbound webhook",
                "severity": body.severity or "High",
                "summary": "Opened automatically from an inbound security webhook.",
                "incident_refs": [], "risk_refs": [], "business_services": [],
                "incident_commander": "", "executive_sponsor": "",
                "status": "Active", "phase": "Detection",
                "started_at": now, "updated_at": now, "next_update_at": None,
                "created_by": "Inbound Webhook"})
        else:
            raise HTTPException(status_code=409,
                detail="No open crisis case to attach events to. Provide case_ref or set open_case=true.")
    ingested = 0
    for ev in raw_events:
        await db.crisis_events.insert_one({
            "org_id": org_id, "case_ref": ref, "via": "webhook",
            "event_id": await _next_ref(org_id, "crisis_events", "EVT"),
            "kind": ev.get("kind") or "Detection", "title": (ev.get("title") or "Security event")[:200],
            "detail": (ev.get("detail") or "")[:1000], "source": ev.get("source") or "External",
            "severity": ev.get("severity") or "High", "occurred_at": ev.get("occurred_at") or now,
            "created_at": now, "created_by": "Inbound Webhook"})
        ingested += 1
    await db.crisis_cases.update_one({"org_id": org_id, "ref": ref}, {"$set": {"updated_at": now}})
    await _record_connector_health(org_id, body.format or "generic", raw_events[0].get("title") if raw_events else "")
    return {"ok": True, "case_ref": ref, "ingested": ingested}


# ===========================================================================
# Board Snapshot Link — one-tap, mobile-friendly, public read-only crisis
# snapshot behind an unguessable token, auto-expiring and revocable.
# ===========================================================================
class SnapshotCreate(BaseModel):
    expires_days: int = 7


@api.post("/cases/{ref}/snapshot")
async def create_snapshot(ref: str, body: SnapshotCreate, user: dict = Depends(get_current_user)):
    _require_operator(user)
    from datetime import timedelta
    import secrets as _s
    org_id = user["org_id"]
    await _get_case(org_id, ref)
    days = max(1, min(90, body.expires_days or 7))
    now_dt = datetime.now(timezone.utc)
    token = _s.token_urlsafe(18)
    doc = {"token": token, "org_id": org_id, "case_ref": ref, "created_by": _actor(user),
           "created_at": now_dt.isoformat(), "expires_at": (now_dt + timedelta(days=days)).isoformat(),
           "revoked": False}
    await db.crisis_snapshots.update_many(
        {"org_id": org_id, "case_ref": ref, "revoked": False}, {"$set": {"revoked": True}})
    await db.crisis_snapshots.insert_one(doc.copy())
    await _audit(org_id, _actor(user), "crisis.snapshot.create", f"{ref} exp {days}d")
    return {"token": token, "path": f"/crisis-snapshot/{token}", "expires_at": doc["expires_at"]}


@api.get("/cases/{ref}/snapshot")
async def get_snapshot_link(ref: str, user: dict = Depends(get_current_user)):
    _require_operator(user)
    doc = await db.crisis_snapshots.find_one(
        {"org_id": user["org_id"], "case_ref": ref, "revoked": False}, {"_id": 0})
    if not doc:
        return {"active": False}
    return {"active": True, "token": doc["token"], "path": f"/crisis-snapshot/{doc['token']}",
            "expires_at": doc["expires_at"]}


@api.post("/cases/{ref}/snapshot/revoke")
async def revoke_snapshot(ref: str, user: dict = Depends(get_current_user)):
    _require_operator(user)
    res = await db.crisis_snapshots.update_many(
        {"org_id": user["org_id"], "case_ref": ref, "revoked": False}, {"$set": {"revoked": True}})
    await _audit(user["org_id"], _actor(user), "crisis.snapshot.revoke", ref)
    return {"revoked": res.modified_count}


async def _resolve_snapshot_doc(token: str) -> dict:
    doc = await db.crisis_snapshots.find_one({"token": token}, {"_id": 0})
    if not doc or doc.get("revoked"):
        raise HTTPException(status_code=404, detail="This snapshot link is invalid or has been revoked.")
    exp = _parse_iso(doc.get("expires_at"))
    if exp and datetime.now(timezone.utc) > exp:
        raise HTTPException(status_code=410, detail="This snapshot link has expired.")
    return doc


async def _build_snapshot(doc: dict) -> dict:
    from bson import ObjectId
    org_id, ref = doc["org_id"], doc["case_ref"]
    case = await db.crisis_cases.find_one({"org_id": org_id, "ref": ref}, {"_id": 0})
    if not case:
        raise HTTPException(status_code=404, detail="This crisis case is no longer available.")
    org = await db.organizations.find_one({"_id": ObjectId(org_id)}, {"name": 1}) or {}
    actions = await db.crisis_actions.find({"org_id": org_id, "case_ref": ref}, {"_id": 0}).to_list(500)
    events = await db.crisis_events.find(
        {"org_id": org_id, "case_ref": ref}, {"_id": 0}).sort("occurred_at", DESCENDING).to_list(12)
    obligations = await db.crisis_obligations.find({"org_id": org_id, "case_ref": ref}, {"_id": 0}).to_list(50)
    _done = ("Verified", "Executed", "Complete", "Closed", "Resolved")
    pending = [a for a in actions if a.get("decision_required") and a.get("status") == "Awaiting Approval"]
    cont = [a for a in actions if a.get("action_type") == "Containment"]
    contained = round(sum(1 for a in cont if a.get("status") in _done) / len(cont) * 100) if cont else 0
    return {
        "org_name": org.get("name") or "Organization",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "expires_at": doc.get("expires_at"),
        "case": {"ref": case.get("ref"), "title": case.get("title"), "severity": case.get("severity"),
                 "status": case.get("status"), "phase": case.get("phase"),
                 "started_at": case.get("started_at"), "updated_at": case.get("updated_at"),
                 "incident_commander": case.get("incident_commander"),
                 "executive_sponsor": case.get("executive_sponsor"), "summary": case.get("summary"),
                 "business_services": case.get("business_services", []),
                 "financial_exposure": case.get("financial_exposure")},
        "contained_pct": contained,
        "counts": {"open_actions": sum(1 for a in actions if a.get("status") not in _done),
                   "pending_decisions": len(pending)},
        "pending_decisions": [{"title": a.get("title"), "owner": a.get("decision_owner"),
                               "priority": a.get("priority"), "due_at": a.get("decision_due_at"),
                               "business_impact": a.get("business_impact")} for a in pending],
        "timeline": [{"kind": e.get("kind"), "title": e.get("title"), "source": e.get("source"),
                      "severity": e.get("severity"), "occurred_at": e.get("occurred_at")} for e in events],
        "regulatory": [{"jurisdiction": o.get("jurisdiction"), "regulation": o.get("regulation"),
                        "deadline_at": o.get("deadline_at"), "status": o.get("status")} for o in obligations],
    }


@api.get("/public/snapshot/{token}")
async def public_snapshot(token: str):
    """PUBLIC — read-only board snapshot resolved by share token."""
    return await _build_snapshot(await _resolve_snapshot_doc(token))


@api.get("/public/snapshot/{token}/stream")
async def public_snapshot_stream(token: str):
    """PUBLIC — Server-Sent Events: pushes a fresh snapshot whenever the incident
    changes, so board members see updates the instant they happen."""
    import asyncio
    import json as _json
    from starlette.responses import StreamingResponse

    async def gen():
        last_sig = None
        for _ in range(200):  # ~10 min, then client auto-reconnects
            try:
                snap = await _build_snapshot(await _resolve_snapshot_doc(token))
            except HTTPException as exc:
                yield f"event: closed\ndata: {_json.dumps({'detail': exc.detail})}\n\n"
                return
            sig = f"{snap['case'].get('updated_at')}|{len(snap['timeline'])}|{snap['contained_pct']}|{snap['counts']['pending_decisions']}"
            if sig != last_sig:
                last_sig = sig
                yield f"data: {_json.dumps(snap)}\n\n"
            else:
                yield ": keep-alive\n\n"
            await asyncio.sleep(3)

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache, no-transform",
                                      "X-Accel-Buffering": "no", "Connection": "keep-alive"})


# ===========================================================================
# Sample-Breach scenario — a scripted, auto-advancing walkthrough that surfaces
# timeline events + executive decisions in sequence (detection -> recovery),
# so prospect demos play like a real incident with zero setup. Uses the demo
# flag so the DEMO ribbon shows and one-click clear removes everything.
# ===========================================================================
_SCENARIOS = {
    "ransomware": {
        "label": "Ransomware — Order Fulfillment",
        "title": "Ransomware — North American Order Fulfillment (Sample Breach)",
        "description": "Encryptor loose in NA fulfillment with SAP at risk — isolate, insurer and restore decisions.",
        "severity": "High", "phase": "Detection",
        "services": ["Order Management", "North American Sales", "Customer Fulfillment", "Payment Processing"],
        "commander": "A. Rivera (SecOps Lead)", "sponsor": "CISO",
        "seed": ("Detection", "SIEM flags anomalous authentication spike on VPN concentrator",
                 "Impossible-travel + brute-force pattern from a single source ASN.", "Splunk SIEM", "High"),
        "beats": [
            {"phase": "Triage", "severity": "Critical",
             "events": [("Threat", "EDR confirms credential-theft malware on 3 endpoints",
                         "Malicious binary matches a known ransomware loader.", "CrowdStrike EDR", "Critical")],
             "participants": [("Incident Commander", "A. Rivera", "SecOps", "Engaged"),
                              ("CISO", "Executive Sponsor", "Security leadership", "Engaged")]},
            {"events": [("Threat", "Privileged account used to reach SAP production",
                         "A compromised admin session pivoted to the ERP estate.", "Microsoft Entra", "Critical")],
             "actions": [("Isolate SAP order-processing segment?", "Decision", "Critical", "Awaiting Approval",
                          True, "CIO", "$1.8M/hr revenue impact", "Halts NA order processing")]},
            {"phase": "Containment",
             "events": [("Containment", "7 endpoints isolated via EDR",
                         "Automated network containment applied to affected hosts.", "CrowdStrike EDR", "High")],
             "actions": [("Revoke 3 compromised privileged identities", "Containment", "Critical", "Executing",
                          False, "", "Stops lateral movement", "Locks out 3 admins pending re-issue")]},
            {"events": [("Business Impact", "North American order fulfillment degraded",
                         "Order-intake queue is backing up across NA.", "ServiceNow", "High")],
             "actions": [("Engage cyber insurer and outside counsel", "Decision", "High", "Awaiting Approval",
                          True, "General Counsel", "Preserves coverage & privilege", "None")]},
            {"events": [("Communication", "CISO briefs executive team; holding statement drafted",
                         "Board notified; customer comms staged for approval.", "Obserra", "Medium")],
             "obligations": [("EU (GDPR)", "GDPR Art. 33 personal data breach", "Possible EU customer PII exposure",
                              66, "General Counsel", "Assessing", "Scope of affected EU records")]},
            {"status": "Recovering",
             "events": [("Containment", "Attacker persistence removed; domain admin credentials rotated",
                         "Golden-ticket risk mitigated across the domain.", "Microsoft Entra", "High")]},
            {"phase": "Recovery",
             "events": [("Recovery", "Order management restored from validated backup",
                         "Clean restore verified against a known-good snapshot.", "Obserra", "High")],
             "recovery": [("Order Management System", "System", "Validated"),
                          ("SAP ERP Production", "System", "Restoring")]},
            {"phase": "Post-Incident", "status": "Closed",
             "events": [("Recovery", "All services verified; heightened monitoring in place",
                         "Incident closed; post-incident review scheduled.", "Obserra", "Medium")]},
        ],
    },
    "insider": {
        "label": "Insider Threat — IP Exfiltration",
        "title": "Insider Data Exfiltration — Departing Engineer (Sample Breach)",
        "description": "A departing engineer exfiltrates source code — suspend access, preserve evidence, protect IP.",
        "severity": "High", "phase": "Detection",
        "services": ["Source Control", "Product Engineering", "Intellectual Property"],
        "commander": "M. Osei (Insider Risk Lead)", "sponsor": "CISO",
        "seed": ("Detection", "DLP flags a 4.2 GB source-code upload to a personal cloud account",
                 "Departing engineer uploaded repositories minutes before end of shift.", "Microsoft Purview DLP", "High"),
        "beats": [
            {"phase": "Triage", "severity": "Critical",
             "events": [("Threat", "UEBA confirms mass repository cloning from one workstation",
                         "38 private repos cloned in 12 minutes.", "Splunk UEBA", "Critical")],
             "participants": [("Incident Commander", "M. Osei", "Insider Risk", "Engaged"),
                              ("CISO", "Executive Sponsor", "Security leadership", "Engaged")]},
            {"events": [("Threat", "Exfil destination is a personal, unmanaged cloud account",
                         "Data has left the managed perimeter.", "Netskope CASB", "Critical")],
             "actions": [("Suspend the employee's accounts and revoke access now?", "Decision", "Critical",
                          "Awaiting Approval", True, "CHRO + CISO", "Prevents further exfil; HR/legal sensitivity",
                          "Locks out the employee")]},
            {"phase": "Containment",
             "events": [("Containment", "Accounts disabled; sessions and tokens revoked",
                         "Endpoint quarantined and egress blocked.", "Microsoft Entra", "High")],
             "actions": [("Preserve a forensic image of the workstation", "Containment", "High", "Executing",
                          False, "", "Chain of custody for potential litigation", "Read-only image")]},
            {"events": [("Business Impact", "Exposed repos include the unreleased pricing engine IP",
                         "Competitive and trade-secret exposure under review.", "Obserra", "High")],
             "actions": [("Engage outside counsel and notify insurer", "Decision", "High", "Awaiting Approval",
                          True, "General Counsel", "Trade-secret protection & privilege", "None")]},
            {"events": [("Communication", "Legal issues litigation hold; HR briefed",
                         "Evidence preserved; comms restricted to need-to-know.", "Obserra", "Medium")],
             "obligations": [("US (Trade Secrets)", "DTSA misappropriation assessment",
                              "Potential IP theft by an insider", 70, "General Counsel", "Assessing",
                              "Repository and access logs")]},
            {"status": "Recovering",
             "events": [("Containment", "Cloud provider honored takedown; copies confirmed deleted",
                         "Third-party deletion attestation received.", "Netskope CASB", "High")]},
            {"phase": "Recovery",
             "events": [("Recovery", "Access model tightened; least-privilege re-baselined",
                         "Repo access scoped to active projects only.", "Obserra", "High")],
             "recovery": [("Source Control Access", "Policy", "Validated"),
                          ("Insider Risk Controls", "Policy", "Restoring")]},
            {"phase": "Post-Incident", "status": "Closed",
             "events": [("Recovery", "Case closed; insider-risk program review scheduled",
                         "PIR and control updates queued.", "Obserra", "Medium")]},
        ],
    },
    "third_party": {
        "label": "Third-Party Breach — CRM Vendor",
        "title": "Third-Party SaaS Breach — CRM Vendor Compromise (Sample Breach)",
        "description": "A CRM vendor is breached with our customer data in scope — sever tokens, notify, re-onboard.",
        "severity": "High", "phase": "Detection",
        "services": ["CRM Integration", "Revenue Operations", "Customer Notifications"],
        "commander": "D. Kaur (Vendor Risk Lead)", "sponsor": "CISO",
        "seed": ("Detection", "CRM vendor discloses a breach of their production tenant",
                 "Vendor bulletin: attacker accessed customer databases.", "Vendor Advisory", "High"),
        "beats": [
            {"phase": "Triage", "severity": "Critical",
             "events": [("Threat", "Our customer records confirmed in the affected vendor tenant",
                         "2.1M contact records with emails and phone numbers.", "Obserra", "Critical")],
             "participants": [("Incident Commander", "D. Kaur", "Vendor Risk", "Engaged"),
                              ("CISO", "Executive Sponsor", "Security leadership", "Engaged")]},
            {"events": [("Threat", "Shared vendor API tokens may be compromised",
                         "Integration tokens are in scope of the breach.", "Obserra", "High")],
             "actions": [("Rotate all vendor API tokens and sever the integration?", "Decision", "Critical",
                          "Awaiting Approval", True, "CIO", "Breaks CRM sync temporarily", "Halts vendor data flow")]},
            {"phase": "Containment",
             "events": [("Containment", "Vendor integration tokens rotated; connector paused",
                         "Data flow to and from the vendor suspended.", "Obserra", "High")],
             "actions": [("Force password reset for exposed customer accounts", "Containment", "High", "Executing",
                          False, "", "Limits account takeover", "Mass credential reset")]},
            {"events": [("Business Impact", "Sales pipeline visibility degraded during the CRM pause",
                         "Revenue ops working from cached exports.", "ServiceNow", "Medium")],
             "actions": [("Notify affected customers and regulators", "Decision", "High", "Awaiting Approval",
                          True, "General Counsel", "Regulatory clocks are running", "None")]},
            {"events": [("Communication", "Customer notification and FAQ drafted with legal",
                         "Comms staged across regions.", "Obserra", "Medium")],
             "obligations": [("EU (GDPR)", "GDPR Art. 33 processor breach", "Vendor acts as a data processor",
                              60, "DPO", "Assessing", "Vendor DPA & affected records"),
                             ("US (State)", "US state breach notifications", "PII of US residents exposed",
                              70, "General Counsel", "Assessing", "Per-state resident counts")]},
            {"status": "Recovering",
             "events": [("Containment", "Vendor confirms containment; independent IR report received",
                         "Root cause fixed by the vendor.", "Vendor Advisory", "High")]},
            {"phase": "Recovery",
             "events": [("Recovery", "Integration re-enabled with scoped tokens and monitoring",
                         "Least-privilege tokens; anomaly alerts enabled.", "Obserra", "High")],
             "recovery": [("CRM Integration", "System", "Validated"),
                          ("Customer Notifications", "Process", "Restoring")]},
            {"phase": "Post-Incident", "status": "Closed",
             "events": [("Recovery", "Case closed; vendor re-scored and contract reviewed",
                         "Breach SLAs added to the vendor contract.", "Obserra", "Medium")]},
        ],
    },
    "ddos": {
        "label": "DDoS Extortion — Customer Portal",
        "title": "DDoS Extortion — Customer Portal (Sample Breach)",
        "description": "A ransom DDoS saturates the portal — scrub traffic, hold the line, don't pay.",
        "severity": "High", "phase": "Detection",
        "services": ["Customer Portal", "Checkout / Payments", "Public Website"],
        "commander": "R. Vance (NetSec Lead)", "sponsor": "CISO",
        "seed": ("Detection", "Volumetric traffic spike saturates the customer portal edge",
                 "450 Gbps multi-vector flood; portal latency climbing.", "Cloudflare", "High"),
        "beats": [
            {"phase": "Triage", "severity": "Critical",
             "events": [("Threat", "Ransom DDoS note received demanding crypto payment",
                         "Attacker threatens a sustained attack unless paid.", "Email", "Critical")],
             "participants": [("Incident Commander", "R. Vance", "Network Security", "Engaged"),
                              ("CISO", "Executive Sponsor", "Security leadership", "Engaged")]},
            {"events": [("Business Impact", "Customer portal and checkout intermittently unavailable",
                         "Conversion dropping; support volume spiking.", "ServiceNow", "High")],
             "actions": [("Do NOT pay the ransom — engage scrubbing and law enforcement?", "Decision", "Critical",
                          "Awaiting Approval", True, "CEO + General Counsel", "Sets precedent; policy decision", "None")]},
            {"phase": "Containment",
             "events": [("Containment", "Always-on DDoS scrubbing engaged; rate-limits applied",
                         "Traffic rerouted through the mitigation provider.", "Cloudflare", "High")],
             "actions": [("Enable geo/ASN filtering on attack sources", "Containment", "High", "Executing",
                          False, "", "Cuts malicious volume", "May affect some legitimate users")]},
            {"events": [("Threat", "Attack shifts to Layer-7 application floods",
                         "Adaptive attacker targeting login and search.", "Cloudflare", "High")],
             "actions": [("Shift the portal behind challenge / JS-challenge mode", "Decision", "Medium",
                          "Awaiting Approval", True, "CIO", "Adds friction for users", "Bot mitigation on")]},
            {"events": [("Communication", "Status page updated; customers and SOC briefed",
                         "Holding statement published.", "Obserra", "Medium")],
             "obligations": [("Contractual (SLA)", "Customer SLA breach notifications",
                              "Portal availability SLA at risk", 24, "Customer Success", "Assessing",
                              "Downtime minutes per customer")]},
            {"status": "Recovering",
             "events": [("Containment", "Attack volume subsides; mitigation holding",
                         "Traffic normalizing behind scrubbing.", "Cloudflare", "High")]},
            {"phase": "Recovery",
             "events": [("Recovery", "Portal performance restored; challenge mode relaxed",
                         "Latency back to baseline.", "Obserra", "High")],
             "recovery": [("Customer Portal", "System", "Validated"),
                          ("Checkout / Payments", "System", "Restoring")]},
            {"phase": "Post-Incident", "status": "Closed",
             "events": [("Recovery", "Case closed; always-on protections and runbook updated",
                         "Permanent scrubbing tier enabled.", "Obserra", "Medium")]},
        ],
    },
}
_SCENARIO_DEFAULT = "ransomware"
_SCENARIO_BEATS = _SCENARIOS[_SCENARIO_DEFAULT]["beats"]  # back-compat alias


async def _apply_beat(org_id: str, ref: str, beat: dict, now_iso: str, actor: str) -> list:
    from datetime import timedelta
    revealed = []
    cupd = {k: beat[k] for k in ("phase", "severity", "status") if beat.get(k)}
    cupd["updated_at"] = now_iso
    if beat.get("status") == "Closed":
        cupd["closed_at"] = now_iso
    await db.crisis_cases.update_one({"org_id": org_id, "ref": ref}, {"$set": cupd})
    for kind, title, detail, source, sev in beat.get("events", []):
        await db.crisis_events.insert_one({
            "org_id": org_id, "case_ref": ref, "demo": True,
            "event_id": await _next_ref(org_id, "crisis_events", "EVT"),
            "kind": kind, "title": title, "detail": detail, "source": source, "severity": sev,
            "occurred_at": now_iso, "created_at": now_iso, "created_by": actor})
        revealed.append(title)
    for title, atype, prio, status, dec, downer, bimp, timp in beat.get("actions", []):
        await db.crisis_actions.insert_one({
            "org_id": org_id, "case_ref": ref, "demo": True,
            "action_id": await _next_ref(org_id, "crisis_actions", "ACT"),
            "title": title, "owner": "", "priority": prio, "status": status,
            "action_type": atype, "due_at": None, "decision_required": dec, "decision_owner": downer,
            "decision_due_at": _sla_due(prio, now_iso) if (dec and status == "Awaiting Approval") else None,
            "business_impact": bimp, "technical_impact": timp, "outcome": "", "approved_by": "",
            "created_at": now_iso, "updated_at": now_iso, "created_by": actor})
        revealed.append(title)
    for role, name, resp, pstatus in beat.get("participants", []):
        await db.crisis_participants.insert_one({
            "org_id": org_id, "case_ref": ref, "demo": True,
            "participant_id": await _next_ref(org_id, "crisis_participants", "WAR"),
            "role": role, "name": name, "contact": "", "responsibility": resp, "status": pstatus,
            "created_at": now_iso, "created_by": actor})
    for name, cat, rstatus in beat.get("recovery", []):
        await db.crisis_recovery.insert_one({
            "org_id": org_id, "case_ref": ref, "demo": True,
            "recovery_id": await _next_ref(org_id, "crisis_recovery", "REC"),
            "name": name, "category": cat, "status": rstatus, "owner": "", "note": "",
            "pct": _RECOVERY_PCT.get(rstatus, 0),
            "created_at": now_iso, "updated_at": now_iso, "created_by": actor})
    for jur, reg, trig, hours, resp, ostatus, evid in beat.get("obligations", []):
        await db.crisis_obligations.insert_one({
            "org_id": org_id, "case_ref": ref, "demo": True,
            "obligation_id": await _next_ref(org_id, "crisis_obligations", "REG"),
            "jurisdiction": jur, "regulation": reg, "trigger": trig,
            "deadline_at": (datetime.now(timezone.utc) + timedelta(hours=hours)).isoformat(),
            "responsible": resp, "evidence_required": evid, "status": ostatus,
            "notification_decision": "", "created_at": now_iso, "updated_at": now_iso, "created_by": actor})
    return revealed


class ScenarioStart(BaseModel):
    key: str = "ransomware"


@api.get("/scenario/library")
async def scenario_library(user: dict = Depends(get_current_user)):
    _require_operator(user)
    return {"scenarios": [{"key": k, "label": v["label"], "title": v["title"],
                           "description": v["description"], "steps": len(v["beats"]) + 1}
                          for k, v in _SCENARIOS.items()]}


@api.post("/scenario/start")
async def scenario_start(body: ScenarioStart = ScenarioStart(), user: dict = Depends(get_current_user)):
    _require_operator(user)
    await _ensure_indexes()
    org_id = user["org_id"]
    actor = _actor(user)
    key = body.key if body.key in _SCENARIOS else _SCENARIO_DEFAULT
    story = _SCENARIOS[key]
    await _demo_clear(org_id)
    await db.crisis_scenario.delete_many({"org_id": org_id})
    from bson import ObjectId
    await db.organizations.update_one({"_id": ObjectId(org_id)}, {"$set": {"ci_demo_active": True}})
    now_iso = datetime.now(timezone.utc).isoformat()
    ref = await _next_ref(org_id, "crisis_cases", "CRISIS")
    await db.crisis_cases.insert_one({
        "ref": ref, "org_id": org_id, "demo": True,
        "title": story["title"], "severity": story["severity"],
        "summary": "Live sample-breach walkthrough. Events and executive decisions surface in sequence, "
                   "from first detection through containment and recovery.",
        "incident_refs": [], "risk_refs": [], "business_services": story["services"],
        "incident_commander": story["commander"], "executive_sponsor": story["sponsor"],
        "status": "Active", "phase": story["phase"],
        "started_at": now_iso, "updated_at": now_iso, "next_update_at": None, "created_by": actor})
    sk, st, sd, ss, sv = story["seed"]
    await db.crisis_events.insert_one({
        "org_id": org_id, "case_ref": ref, "demo": True,
        "event_id": await _next_ref(org_id, "crisis_events", "EVT"),
        "kind": sk, "title": st, "detail": sd, "source": ss, "severity": sv,
        "occurred_at": now_iso, "created_at": now_iso, "created_by": actor})
    total = len(story["beats"]) + 1
    await db.crisis_scenario.insert_one({"org_id": org_id, "ref": ref, "key": key, "cursor": 0,
                                         "total": total, "created_at": now_iso})
    await _audit(org_id, actor, "crisis.scenario.start", f"{key} {ref}")
    return {"ref": ref, "key": key, "label": story["label"], "step": 1, "total": total, "done": False}


@api.post("/scenario/advance")
async def scenario_advance(user: dict = Depends(get_current_user)):
    _require_operator(user)
    org_id = user["org_id"]
    actor = _actor(user)
    state = await db.crisis_scenario.find_one({"org_id": org_id})
    if not state:
        raise HTTPException(status_code=409, detail="No sample-breach scenario is running. Start it first.")
    beats = _SCENARIOS.get(state.get("key", _SCENARIO_DEFAULT), _SCENARIOS[_SCENARIO_DEFAULT])["beats"]
    cursor = state.get("cursor", 0)
    total = state.get("total", len(beats) + 1)
    if cursor >= len(beats):
        return {"step": total, "total": total, "done": True, "revealed": []}
    now_iso = datetime.now(timezone.utc).isoformat()
    revealed = await _apply_beat(org_id, state["ref"], beats[cursor], now_iso, actor)
    cursor += 1
    await db.crisis_scenario.update_one({"org_id": org_id}, {"$set": {"cursor": cursor}})
    return {"step": cursor + 1, "total": total, "done": cursor >= len(beats), "revealed": revealed}


@api.get("/scenario/status")
async def scenario_status(user: dict = Depends(get_current_user)):
    state = await db.crisis_scenario.find_one({"org_id": user["org_id"]}, {"_id": 0})
    if not state:
        return {"active": False}
    key = state.get("key", _SCENARIO_DEFAULT)
    story = _SCENARIOS.get(key, _SCENARIOS[_SCENARIO_DEFAULT])
    return {"active": True, "ref": state["ref"], "key": key, "label": story["label"],
            "step": state.get("cursor", 0) + 1, "total": state.get("total", len(story["beats"]) + 1),
            "done": state.get("cursor", 0) >= len(story["beats"])}


@api.post("/scenario/stop")
async def scenario_stop(user: dict = Depends(get_current_user)):
    _require_operator(user)
    org_id = user["org_id"]
    counts = await _demo_clear(org_id)
    await db.crisis_scenario.delete_many({"org_id": org_id})
    await _audit(org_id, _actor(user), "crisis.scenario.stop", str(counts))
    return {"stopped": True, **counts}



# ===========================================================================
# Native SIEM/EDR/SOAR connectors — first-class per-vendor push endpoints so
# onboarding a tool is one paste (the URL embeds the vendor format + per-org
# secret). The tool's RAW native JSON is mapped onto the crisis timeline via
# _map_vendor_event — zero pre-formatting required on the customer side.
# ===========================================================================
from fastapi import Request as _Request

_NATIVE_VENDORS = {
    "crowdstrike": {"label": "CrowdStrike Falcon", "note": "Falcon Fusion SOAR → add a 'Send to webhook' action and POST the detection object here."},
    "splunk": {"label": "Splunk Enterprise Security", "note": "Alert action → Webhook; point it at this URL (posts the alert result payload)."},
    "sentinel": {"label": "Microsoft Sentinel", "note": "Analytics rule → Automation → Logic App / Playbook with an HTTP action posting the alert JSON."},
    "servicenow": {"label": "ServiceNow SecOps", "note": "Flow Designer / Business Rule REST step posting the security incident record."},
    "generic": {"label": "Generic HTTP (any tool)", "note": "POST the tool's native JSON; common fields are auto-detected."},
}


def _extract_native_payloads(body):
    """Pull one or many event dicts out of a vendor's native webhook body."""
    if body is None:
        return []
    if isinstance(body, list):
        return [x for x in body if isinstance(x, dict)]
    if isinstance(body, dict):
        for key in ("events", "alerts", "records", "resources", "data", "result", "results", "incidents"):
            v = body.get(key)
            if isinstance(v, list) and v:
                return [x for x in v if isinstance(x, dict)]
            if isinstance(v, dict):
                return [v]
        return [body]
    return []


@api.get("/connectors/native")
async def native_connectors(user: dict = Depends(get_current_user)):
    _require_operator(user)
    org_id = user["org_id"]
    secret = await _webhook_secret(org_id, create=True)
    health = await _connector_health_map(org_id)
    out = [{
        "vendor": vend, "label": meta["label"], "note": meta["note"],
        "path": f"/api/crisis/ingest/native/{vend}?secret={secret}",
        "header": "X-Obserra-Secret",
        "last_received": (health.get(vend) or {}).get("last_received"),
        "count": (health.get(vend) or {}).get("count", 0),
    } for vend, meta in _NATIVE_VENDORS.items()]
    return {"secret": secret, "connectors": out}


@api.post("/ingest/native/{vendor}")
async def ingest_native(vendor: str, request: _Request, secret: str = ""):
    """PUBLIC per-vendor push endpoint. Accepts the tool's RAW native JSON and
    maps it onto the live crisis timeline. Authenticated by the per-org secret
    (query ?secret= or an X-Obserra-Secret header)."""
    sec = secret or request.headers.get("x-obserra-secret") or ""
    if not sec:
        raise HTTPException(status_code=401, detail="Missing webhook secret.")
    org = await db.organizations.find_one({"crisis_webhook_secret": sec}, {"_id": 1})
    if not org:
        raise HTTPException(status_code=401, detail="Invalid webhook secret.")
    org_id = str(org["_id"])
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Request body must be valid JSON.")
    fmt = vendor if vendor in _VENDOR_MAPS else "generic"
    raw_events = [_map_vendor_event(fmt, p) for p in _extract_native_payloads(payload)]
    if not raw_events:
        raise HTTPException(status_code=400, detail="No event object found in the payload.")
    raw_events = raw_events[:50]
    now = _now()
    case = await db.crisis_cases.find_one(
        {"org_id": org_id, "status": {"$ne": "Closed"}}, {"_id": 0, "ref": 1},
        sort=[("updated_at", DESCENDING)])
    if case:
        ref = case["ref"]
    else:
        ref = await _next_ref(org_id, "crisis_cases", "CRISIS")
        top = raw_events[0]
        await db.crisis_cases.insert_one({
            "ref": ref, "org_id": org_id, "via": "webhook",
            "title": f"{_NATIVE_VENDORS.get(fmt, {}).get('label', 'Security tool')}: {top.get('title')}"[:200],
            "severity": top.get("severity") or "High",
            "summary": f"Opened automatically from an inbound {fmt} security webhook.",
            "incident_refs": [], "risk_refs": [], "business_services": [],
            "incident_commander": "", "executive_sponsor": "",
            "status": "Active", "phase": "Detection",
            "started_at": now, "updated_at": now, "next_update_at": None,
            "created_by": f"{fmt} connector"})
    ingested = 0
    for ev in raw_events:
        await db.crisis_events.insert_one({
            "org_id": org_id, "case_ref": ref, "via": "webhook",
            "event_id": await _next_ref(org_id, "crisis_events", "EVT"),
            "kind": ev.get("kind") or "Detection", "title": (ev.get("title") or "Security event")[:200],
            "detail": (ev.get("detail") or "")[:1000], "source": ev.get("source") or "External",
            "severity": ev.get("severity") or "High", "occurred_at": ev.get("occurred_at") or now,
            "created_at": now, "created_by": f"{fmt} connector"})
        ingested += 1
    await db.crisis_cases.update_one({"org_id": org_id, "ref": ref}, {"$set": {"updated_at": now}})
    await _record_connector_health(org_id, fmt, raw_events[0].get("title") if raw_events else "")
    return {"ok": True, "vendor": fmt, "case_ref": ref, "ingested": ingested}


# ===========================================================================
# Digital War Room — broadcast a situation report (SITREP) to the org's Teams
# and/or Slack channels, and report which channels are wired so leadership
# knows the blast radius. Always writes a Communication timeline event.
# ===========================================================================
async def _chat_channels(org_id: str) -> dict:
    from bson import ObjectId
    org = await db.organizations.find_one({"_id": ObjectId(org_id)}) or {}
    alerts = org.get("scan_alerts") or {}
    teams = bool(alerts.get("teams_url") or (org.get("live_teams") or {}).get("webhook_url"))
    slack = bool(alerts.get("slack_url"))
    return {"teams": teams, "slack": slack}


@api.get("/broadcast/status")
async def broadcast_status(user: dict = Depends(get_current_user)):
    _require_operator(user)
    return await _chat_channels(user["org_id"])


class BroadcastBody(BaseModel):
    message: str = ""


@api.post("/cases/{ref}/broadcast")
async def broadcast_sitrep(ref: str, body: BroadcastBody, user: dict = Depends(get_current_user)):
    from self_scan import _post_chat_alert
    _require_operator(user)
    org_id = user["org_id"]
    case = await _get_case(org_id, ref)
    channels = await _chat_channels(org_id)
    snap = await _build_snapshot({"org_id": org_id, "case_ref": ref, "expires_at": None})
    now = _now()
    actor = _actor(user)
    custom = (body.message or "").strip()
    title = f"SITREP — {(case.get('title') or '')[:70]} ({ref})"
    lines = [
        f"Severity {case.get('severity')} · Phase {case.get('phase')} · Status {case.get('status')}",
        f"Contained ~{snap['contained_pct']}% · {snap['counts']['pending_decisions']} executive decision(s) pending · {snap['counts']['open_actions']} open action(s)",
        f"Incident commander: {case.get('incident_commander') or 'Unassigned'}",
    ]
    if custom:
        lines.append(f"Update from {actor}: {custom}")
    text = "\n".join(lines)
    posted = False
    if channels["teams"] or channels["slack"]:
        try:
            await _post_chat_alert(org_id, f"🚨 {title}", text)
            posted = True
        except Exception:
            posted = False
    await db.crisis_events.insert_one({
        "org_id": org_id, "case_ref": ref,
        "event_id": await _next_ref(org_id, "crisis_events", "EVT"),
        "kind": "Communication", "title": "War room SITREP broadcast",
        "detail": (custom or "Situation report issued to leadership chat.")[:1000],
        "source": "War Room", "severity": "Info",
        "occurred_at": now, "created_at": now, "created_by": actor})
    await db.crisis_cases.update_one({"org_id": org_id, "ref": ref}, {"$set": {"updated_at": now}})
    await _audit(org_id, actor, "crisis.broadcast",
                 f"{ref} teams={channels['teams']} slack={channels['slack']} posted={posted}")
    return {"posted": posted, **channels}


# ===========================================================================
# Board Crisis Dashboard — a director-focused, read-only crisis view (exposure,
# decisions pending, regulatory clocks, containment) reusing the snapshot data.
# ===========================================================================
@api.get("/cases/{ref}/board")
async def board_view(ref: str, user: dict = Depends(get_current_user)):
    _require_operator(user)
    org_id = user["org_id"]
    await _get_case(org_id, ref)
    snap = await _build_snapshot({"org_id": org_id, "case_ref": ref, "expires_at": None})
    recovery = await db.crisis_recovery.find({"org_id": org_id, "case_ref": ref}, {"_id": 0}).to_list(500)
    _rmap = {"Down": 0, "Restoring": 50, "Validated": 80, "Operational": 100}
    vals = [r["pct"] if isinstance(r.get("pct"), (int, float)) else _rmap.get(r.get("status"), 0) for r in recovery]
    snap["recovery_overall"] = round(sum(vals) / len(vals)) if vals else 0
    snap["recovery_items"] = len(recovery)
    return snap


# ===========================================================================
# Present to Board — one tap prepares a shareable board snapshot link (reused
# if still valid) plus a one-page, board-ready PDF of the current crisis.
# ===========================================================================
@api.post("/cases/{ref}/present-board")
async def present_board(ref: str, body: SnapshotCreate = SnapshotCreate(), user: dict = Depends(get_current_user)):
    from datetime import timedelta
    import secrets as _s
    _require_operator(user)
    org_id = user["org_id"]
    await _get_case(org_id, ref)
    now_dt = datetime.now(timezone.utc)
    existing = await db.crisis_snapshots.find_one(
        {"org_id": org_id, "case_ref": ref, "revoked": False}, {"_id": 0})
    valid = False
    if existing:
        exp = _parse_iso(existing.get("expires_at"))
        valid = (not exp) or now_dt <= exp
    if valid:
        token, expires_at = existing["token"], existing["expires_at"]
    else:
        days = max(1, min(90, body.expires_days or 7))
        token = _s.token_urlsafe(18)
        expires_at = (now_dt + timedelta(days=days)).isoformat()
        await db.crisis_snapshots.update_many(
            {"org_id": org_id, "case_ref": ref, "revoked": False}, {"$set": {"revoked": True}})
        await db.crisis_snapshots.insert_one({
            "token": token, "org_id": org_id, "case_ref": ref, "created_by": _actor(user),
            "created_at": now_dt.isoformat(), "expires_at": expires_at, "revoked": False})
        await _audit(org_id, _actor(user), "crisis.present_board", f"{ref} exp {days}d")
    return {"token": token, "snapshot_path": f"/crisis-snapshot/{token}",
            "onepager_path": f"/api/crisis/cases/{ref}/board-onepager.pdf", "expires_at": expires_at}


@api.get("/cases/{ref}/board-onepager.pdf")
async def board_onepager_pdf(ref: str, user: dict = Depends(get_current_user)):
    _require_operator(user)
    from studio import ReportExportBody, _report_markdown
    from reports import _build_pdf, _resolve_brand
    from fastapi.responses import StreamingResponse
    from bson import ObjectId
    org_id = user["org_id"]
    case = await _get_case(org_id, ref)
    org = await db.organizations.find_one({"_id": ObjectId(org_id)}) or {}
    snap = await _build_snapshot({"org_id": org_id, "case_ref": ref, "expires_at": None})

    def _fmt(ts):
        return str(ts).replace("T", " ")[:16] if ts else "-"

    fin = case.get("financial_exposure")
    pend = snap.get("pending_decisions", [])[:5]
    regs = snap.get("regulatory", [])[:5]
    tl = snap.get("timeline", [])[:6]
    blocks = [
        {"heading": f"{case.get('title', 'Crisis')} — Board Snapshot", "lines": [
            f"Case {case.get('ref')} · Severity {case.get('severity')} · Phase {case.get('phase')} · Status {case.get('status')}",
            f"Contained ~{snap.get('contained_pct', 0)}%  ·  {snap['counts']['pending_decisions']} decision(s) pending  ·  {snap['counts']['open_actions']} open action(s)",
            f"Financial exposure: {('$' + format(int(fin), ',')) if isinstance(fin, (int, float)) else 'Not quantified'}",
            f"Incident commander: {case.get('incident_commander') or 'Unassigned'} · Executive sponsor: {case.get('executive_sponsor') or 'Unassigned'}",
            f"Business services: {', '.join(case.get('business_services') or []) or '-'}"]},
        {"heading": "Decisions awaiting the board", "lines": [
            f"{d.get('title')} — owner {d.get('owner') or '-'} · due {_fmt(d.get('due_at'))}" for d in pend] or ["No executive decisions pending."]},
        {"heading": "Regulatory clocks", "lines": [
            f"{o.get('jurisdiction')} — {o.get('regulation')} — {o.get('status')} — deadline {_fmt(o.get('deadline_at'))}" for o in regs] or ["No regulatory obligations tracked."]},
        {"heading": "Latest timeline", "lines": [
            f"{_fmt(e.get('occurred_at'))} — [{e.get('severity')}] {e.get('title')}" for e in tl] or ["No timeline events."]},
    ]
    title = f"Board Snapshot {ref}"
    export = ReportExportBody(
        title=title,
        ai_narrative=(f"One-page board snapshot for {ref} — severity, containment, decisions pending, "
                      f"regulatory clocks and the latest timeline, drawn from the live crisis record."),
        blocks=blocks)
    buf = _build_pdf(_report_markdown(export), title, cover=False,
                     org_name=(org.get("name") or None), brand=_resolve_brand(org))
    fname = "".join(c for c in f"board-snapshot-{ref}".lower() if c.isascii() and (c.isalnum() or c == "-")) or "board-snapshot"
    await _audit(org_id, _actor(user), "crisis.board_onepager", ref)
    return StreamingResponse(buf, media_type="application/pdf",
                             headers={"Content-Disposition": f'attachment; filename="{fname}.pdf"'})



# ===========================================================================
# Connector health — record the last time each SIEM/EDR connector delivered an
# event so teams can confirm a tool is actually wired (live "last received").
# ===========================================================================
async def _record_connector_health(org_id: str, vendor: str, title: str = ""):
    now = _now()
    await db.crisis_connector_health.update_one(
        {"org_id": org_id, "vendor": vendor},
        {"$set": {"last_received": now, "last_title": (title or "")[:160], "quiet_alerted_at": None}, "$inc": {"count": 1}},
        upsert=True)


async def _connector_health_map(org_id: str) -> dict:
    rows = await db.crisis_connector_health.find({"org_id": org_id}, {"_id": 0}).to_list(50)
    return {r["vendor"]: {"last_received": r.get("last_received"), "count": r.get("count", 0),
                          "last_title": r.get("last_title", "")} for r in rows}


@api.get("/connectors/health")
async def connectors_health(user: dict = Depends(get_current_user)):
    _require_operator(user)
    return {"health": await _connector_health_map(user["org_id"])}


# ===========================================================================
# Auto-SITREP — while a crisis is active, post a fresh containment SITREP to the
# org's Teams/Slack channels on a per-case cadence. Folded into the hourly cron.
# ===========================================================================
async def run_scheduled_sitreps(org_id: str | None = None) -> int:
    from self_scan import _post_chat_alert
    now = datetime.now(timezone.utc)
    query: dict = {"status": {"$ne": "Closed"}, "sitrep_schedule_hours": {"$gt": 0}}
    if org_id:
        query["org_id"] = org_id
    sent_cases = 0
    async for case in db.crisis_cases.find(query, {"_id": 0}):
        hours = int(case.get("sitrep_schedule_hours") or 0)
        if hours <= 0:
            continue
        last = _parse_iso(case.get("sitrep_last_sent_at"))
        if last and (now - last).total_seconds() < hours * 3600:
            continue
        oid = case["org_id"]
        channels = await _chat_channels(oid)
        if not (channels["teams"] or channels["slack"]):
            continue
        ref = case["ref"]
        snap = await _build_snapshot({"org_id": oid, "case_ref": ref, "expires_at": None})
        title, text = _compose_sitrep(case, snap, case.get("sitrep_note") or "")
        posted = True
        try:
            await _post_chat_alert(oid, title, text)
        except Exception:
            posted = False
        if not posted:
            continue
        await db.crisis_cases.update_one(
            {"org_id": oid, "ref": ref}, {"$set": {"sitrep_last_sent_at": now.isoformat()}})
        await db.crisis_events.insert_one({
            "org_id": oid, "case_ref": ref,
            "event_id": await _next_ref(oid, "crisis_events", "EVT"),
            "kind": "Communication", "title": f"Auto-SITREP posted to leadership chat (every {hours}h)",
            "detail": f"Containment ~{snap['contained_pct']}% · {snap['counts']['pending_decisions']} decision(s) pending.",
            "source": "Auto-SITREP", "severity": "Info",
            "occurred_at": now.isoformat(), "created_at": now.isoformat(), "created_by": "Obserra Auto-SITREP"})
        sent_cases += 1
    return sent_cases


# ===========================================================================
# Board Auto-Present — when a real (non-demo) crisis is closed, prepare a board
# snapshot link and email the directors so leadership gets the final picture.
# ===========================================================================
async def _auto_present_board(org_id: str, ref: str, actor: str) -> dict:
    import os
    from datetime import timedelta
    import secrets as _s
    now_dt = datetime.now(timezone.utc)
    existing = await db.crisis_snapshots.find_one(
        {"org_id": org_id, "case_ref": ref, "revoked": False}, {"_id": 0})
    valid = False
    if existing:
        exp = _parse_iso(existing.get("expires_at"))
        valid = (not exp) or now_dt <= exp
    if valid:
        token, expires_at = existing["token"], existing["expires_at"]
    else:
        token = _s.token_urlsafe(18)
        expires_at = (now_dt + timedelta(days=30)).isoformat()
        await db.crisis_snapshots.update_many(
            {"org_id": org_id, "case_ref": ref, "revoked": False}, {"$set": {"revoked": True}})
        await db.crisis_snapshots.insert_one({
            "token": token, "org_id": org_id, "case_ref": ref, "created_by": actor,
            "created_at": now_dt.isoformat(), "expires_at": expires_at, "revoked": False})
    base = (os.environ.get("FRONTEND_URL") or "").rstrip("/")
    link_path = f"/crisis-snapshot/{token}"
    link = f"{base}{link_path}" if base else link_path
    case = await db.crisis_cases.find_one({"org_id": org_id, "ref": ref}, {"_id": 0}) or {}
    recipients = await db.users.find(
        {"org_id": org_id, "role": {"$in": ["admin", "executive", "owner"]}},
        {"_id": 0, "email": 1}).to_list(200)
    emails = [r["email"] for r in recipients if r.get("email")]
    sent = 0
    if emails:
        from kernel import notifications
        html = (
            f'<div style="font-family:Arial,Helvetica,sans-serif;max-width:640px;margin:auto;color:#0f172a">'
            f'<div style="background:#0b1220;color:#fff;padding:18px 22px;border-radius:12px 12px 0 0">'
            f'<div style="font-size:11px;letter-spacing:2px;color:#f87171">OBSERRA · CYBER CRISIS COMMANDER</div>'
            f'<div style="font-size:20px;font-weight:800;margin-top:4px">Crisis Closed — Board Snapshot Ready</div>'
            f'<div style="font-size:12px;color:#94a3b8;margin-top:4px">{case.get("title", "")} · {ref} · '
            f'{case.get("severity", "")} / {case.get("phase", "")}</div></div>'
            f'<div style="border:1px solid #e2e8f0;border-top:0;border-radius:0 0 12px 12px;padding:20px 22px">'
            f'<p style="font-size:14px;line-height:1.5">This crisis has been closed. A live, read-only board '
            f'snapshot has been prepared for your review.</p>'
            f'<p style="margin:18px 0"><a href="{link}" style="background:#0ea5e9;color:#fff;text-decoration:none;'
            f'padding:11px 20px;border-radius:8px;font-weight:700">Open the board snapshot</a></p>'
            f'<p style="font-size:12px;color:#64748b;word-break:break-all">{link}</p>'
            f'<p style="font-size:11px;color:#94a3b8;margin-top:16px">A one-page board PDF is also available inside '
            f'the Board View. Link expires {str(expires_at)[:10]}.</p></div></div>')
        for em in emails:
            try:
                await notifications.send_email(em, f"Crisis Closed — Board Snapshot for {ref}", html)
                sent += 1
            except Exception:
                pass
    now = _now()
    await db.crisis_events.insert_one({
        "org_id": org_id, "case_ref": ref,
        "event_id": await _next_ref(org_id, "crisis_events", "EVT"),
        "kind": "Communication", "title": f"Board snapshot auto-prepared on close; emailed to {sent} director(s)",
        "detail": f"Read-only board snapshot link generated automatically when {ref} was closed.",
        "source": "Auto-Present", "severity": "Info",
        "occurred_at": now, "created_at": now, "created_by": actor})
    await _audit(org_id, actor, "crisis.auto_present", f"{ref} -> {sent}/{len(emails)} directors")
    return {"token": token, "snapshot_path": link_path, "emailed": sent}



# ===========================================================================
# Crisis org settings (director digest + connector-quiet monitoring toggles).
# ===========================================================================
class CrisisSettingsBody(BaseModel):
    director_digest: bool | None = None
    director_digest_weekday: int | None = Field(default=None, ge=0, le=6)
    director_digest_hour: int | None = Field(default=None, ge=0, le=23)
    connector_quiet: bool | None = None
    connector_quiet_hours: int | None = Field(default=None, ge=1, le=72)


async def _crisis_settings(org_id: str) -> dict:
    from bson import ObjectId
    org = await db.organizations.find_one({"_id": ObjectId(org_id)}, {"crisis_settings": 1}) or {}
    s = org.get("crisis_settings") or {}
    return {"director_digest": bool(s.get("director_digest")),
            "director_digest_weekday": int(s.get("director_digest_weekday") if s.get("director_digest_weekday") is not None else 0),
            "director_digest_hour": int(s.get("director_digest_hour") if s.get("director_digest_hour") is not None else 8),
            "connector_quiet": bool(s.get("connector_quiet")),
            "connector_quiet_hours": int(s.get("connector_quiet_hours") or 6)}


@api.get("/settings")
async def get_crisis_settings(user: dict = Depends(get_current_user)):
    _require_operator(user)
    return await _crisis_settings(user["org_id"])


@api.post("/settings")
async def set_crisis_settings(body: CrisisSettingsBody, user: dict = Depends(get_current_user)):
    from bson import ObjectId
    _require_operator(user)
    org_id = user["org_id"]
    upd = {}
    if body.director_digest is not None:
        upd["crisis_settings.director_digest"] = body.director_digest
    if body.director_digest_weekday is not None:
        upd["crisis_settings.director_digest_weekday"] = body.director_digest_weekday
    if body.director_digest_hour is not None:
        upd["crisis_settings.director_digest_hour"] = body.director_digest_hour
    if body.connector_quiet is not None:
        upd["crisis_settings.connector_quiet"] = body.connector_quiet
    if body.connector_quiet_hours is not None:
        upd["crisis_settings.connector_quiet_hours"] = body.connector_quiet_hours
    if upd:
        await db.organizations.update_one({"_id": ObjectId(org_id)}, {"$set": upd})
        await _audit(org_id, _actor(user), "crisis.settings", str(upd))
    return await _crisis_settings(org_id)


# ===========================================================================
# Connector Test Ping — send a synthetic event through a vendor's mapping to
# confirm wiring end-to-end in one click (updates health; no case created).
# ===========================================================================
_TEST_PAYLOADS = {
    "crowdstrike": {"detection_name": "Obserra connection test", "SeverityName": "Low", "description": "Synthetic CrowdStrike test event to confirm the connector is wired."},
    "splunk": {"search_name": "Obserra connection test", "urgency": "low", "signature": "Synthetic Splunk test event.", "_raw": "connection test"},
    "sentinel": {"DisplayName": "Obserra connection test", "AlertSeverity": "Low", "Description": "Synthetic Microsoft Sentinel test event."},
    "servicenow": {"short_description": "Obserra connection test", "priority": "4", "description": "Synthetic ServiceNow SecOps test event."},
    "generic": {"title": "Obserra connection test", "severity": "Low", "detail": "Synthetic test event."},
}


@api.post("/connectors/{vendor}/test")
async def connector_test_ping(vendor: str, user: dict = Depends(get_current_user)):
    _require_operator(user)
    org_id = user["org_id"]
    fmt = vendor if vendor in _VENDOR_MAPS else "generic"
    mapped = _map_vendor_event(fmt, _TEST_PAYLOADS.get(fmt, _TEST_PAYLOADS["generic"]))
    await _record_connector_health(org_id, fmt, "Connection test")
    await _audit(org_id, _actor(user), "crisis.connector_test", fmt)
    return {"ok": True, "vendor": fmt, "mapped": mapped, "tested_at": _now()}


# ===========================================================================
# SITREP composition + preview + send-now (tweak the auto-SITREP before it
# goes out on a schedule).
# ===========================================================================
def _compose_sitrep(case: dict, snap: dict, note: str = "") -> tuple:
    ref = case.get("ref")
    title = f"🚨 SITREP — {(case.get('title') or '')[:70]} ({ref})"
    lines = [
        f"Severity {case.get('severity')} · Phase {case.get('phase')} · Status {case.get('status')}",
        f"Contained ~{snap['contained_pct']}% · {snap['counts']['pending_decisions']} decision(s) pending · {snap['counts']['open_actions']} open action(s)",
        f"Incident commander: {case.get('incident_commander') or 'Unassigned'}",
    ]
    if (note or "").strip():
        lines.append(note.strip())
    return title, "\n".join(lines)


@api.get("/cases/{ref}/sitrep/preview")
async def sitrep_preview(ref: str, user: dict = Depends(get_current_user)):
    _require_operator(user)
    org_id = user["org_id"]
    case = await _get_case(org_id, ref)
    snap = await _build_snapshot({"org_id": org_id, "case_ref": ref, "expires_at": None})
    note = case.get("sitrep_note") or ""
    title, text = _compose_sitrep(case, snap, note)
    return {"title": title, "text": text, "note": note,
            "cadence_hours": int(case.get("sitrep_schedule_hours") or 0)}


@api.post("/cases/{ref}/sitrep/send-now")
async def sitrep_send_now(ref: str, user: dict = Depends(get_current_user)):
    from self_scan import _post_chat_alert
    _require_operator(user)
    org_id = user["org_id"]
    case = await _get_case(org_id, ref)
    channels = await _chat_channels(org_id)
    snap = await _build_snapshot({"org_id": org_id, "case_ref": ref, "expires_at": None})
    title, text = _compose_sitrep(case, snap, case.get("sitrep_note") or "")
    posted = False
    if channels["teams"] or channels["slack"]:
        try:
            await _post_chat_alert(org_id, title, text)
            posted = True
        except Exception:
            posted = False
    now = _now()
    actor = _actor(user)
    await db.crisis_events.insert_one({
        "org_id": org_id, "case_ref": ref,
        "event_id": await _next_ref(org_id, "crisis_events", "EVT"),
        "kind": "Communication", "title": "Manual SITREP sent to leadership chat" if posted else "Manual SITREP attempted (no chat channel wired)",
        "detail": (case.get("sitrep_note") or "Situation report issued from the SITREP console.")[:1000],
        "source": "SITREP Console", "severity": "Info",
        "occurred_at": now, "created_at": now, "created_by": actor})
    await db.crisis_cases.update_one({"org_id": org_id, "ref": ref}, {"$set": {"updated_at": now}})
    await _audit(org_id, actor, "crisis.sitrep_send_now", f"{ref} posted={posted}")
    return {"posted": posted, **channels}


# ===========================================================================
# Weekly Director Digest — email board members a rollup of every open crisis.
# Folded into the weekly-drift-digest cron. Opt-in per org.
# ===========================================================================
async def _build_director_digest(org_id: str):
    open_cases = await db.crisis_cases.find(
        {"org_id": org_id, "status": {"$ne": "Closed"}, "demo": {"$ne": True}},
        {"_id": 0}).to_list(200)
    if not open_cases:
        return None, 0
    rows = []
    for case in open_cases:
        snap = await _build_snapshot({"org_id": org_id, "case_ref": case["ref"], "expires_at": None})
        fin = case.get("financial_exposure")
        fin_s = ("$" + format(int(fin), ",")) if isinstance(fin, (int, float)) else "—"
        sev = case.get("severity", "")
        sev_color = {"Critical": "#dc2626", "High": "#ea580c", "Medium": "#d97706", "Low": "#16a34a"}.get(sev, "#64748b")
        rows.append(
            f'<tr style="border-bottom:1px solid #e2e8f0">'
            f'<td style="padding:10px 8px"><b>{case.get("ref")}</b><br><span style="font-size:12px;color:#64748b">{(case.get("title") or "")[:60]}</span></td>'
            f'<td style="padding:10px 8px"><span style="color:{sev_color};font-weight:700">{sev}</span><br><span style="font-size:11px;color:#94a3b8">{case.get("phase","")}</span></td>'
            f'<td style="padding:10px 8px;text-align:center">{snap.get("contained_pct", 0)}%</td>'
            f'<td style="padding:10px 8px;text-align:center">{snap["counts"]["pending_decisions"]}</td>'
            f'<td style="padding:10px 8px;text-align:right">{fin_s}</td></tr>')
    html = (
        f'<div style="font-family:Arial,Helvetica,sans-serif;max-width:720px;margin:auto;color:#0f172a">'
        f'<div style="background:#0b1220;color:#fff;padding:18px 22px;border-radius:12px 12px 0 0">'
        f'<div style="font-size:11px;letter-spacing:2px;color:#f87171">OBSERRA · CYBER CRISIS COMMANDER</div>'
        f'<div style="font-size:20px;font-weight:800;margin-top:4px">Weekly Crisis Digest</div>'
        f'<div style="font-size:12px;color:#94a3b8;margin-top:4px">{len(open_cases)} open crisis(es) as of {_now()[:10]}</div></div>'
        f'<div style="border:1px solid #e2e8f0;border-top:0;border-radius:0 0 12px 12px;padding:16px 22px">'
        f'<table style="width:100%;border-collapse:collapse;font-size:13px">'
        f'<thead><tr style="text-align:left;color:#64748b;font-size:11px;text-transform:uppercase;letter-spacing:1px">'
        f'<th style="padding:6px 8px">Crisis</th><th style="padding:6px 8px">Severity</th>'
        f'<th style="padding:6px 8px;text-align:center">Contained</th><th style="padding:6px 8px;text-align:center">Decisions</th>'
        f'<th style="padding:6px 8px;text-align:right">Exposure</th></tr></thead>'
        f'<tbody>{"".join(rows)}</tbody></table>'
        f'<p style="font-size:11px;color:#94a3b8;margin-top:16px">Open the Cyber Crisis Commander for full board views, timelines and decisions.</p></div></div>')
    return html, len(open_cases)


async def _send_director_digest(org_id: str) -> tuple:
    from kernel import notifications
    html, n = await _build_director_digest(org_id)
    if not html:
        return 0, 0
    recipients = await db.users.find(
        {"org_id": org_id, "role": {"$in": ["admin", "executive", "owner"]}},
        {"_id": 0, "email": 1}).to_list(200)
    sent = 0
    for r in recipients:
        if r.get("email"):
            try:
                await notifications.send_email(r["email"], f"Weekly Crisis Digest — {n} open crisis(es)", html)
                sent += 1
            except Exception as exc:
                import logging
                logging.getLogger("crisis").warning("Director digest email to %s failed: %s", r.get("email"), exc)
    return sent, n


@api.post("/director-digest/send-now")
async def director_digest_send_now(user: dict = Depends(get_current_user)):
    _require_operator(user)
    org_id = user["org_id"]
    sent, n = await _send_director_digest(org_id)
    await _audit(org_id, _actor(user), "crisis.director_digest_now", f"sent={sent} crises={n}")
    if not n:
        return {"sent": 0, "crises": 0, "message": "No open crises to report."}
    return {"sent": sent, "crises": n}


async def run_weekly_director_digest(org_id: str | None = None) -> int:
    from bson import ObjectId
    orgs_q: dict = {"crisis_settings.director_digest": True}
    if org_id:
        orgs_q["_id"] = ObjectId(org_id)
    total = 0
    async for org in db.organizations.find(orgs_q, {"_id": 1}):
        sent, _n = await _send_director_digest(str(org["_id"]))
        total += sent
    return total


# ===========================================================================
# Connector "went quiet" alerts — if a wired connector stops delivering for
# longer than a threshold during business hours, ping the security channel.
# Folded into the hourly cron. Opt-in per org.
# ===========================================================================
def _within_business_hours() -> bool:
    now = datetime.now(timezone.utc)
    return now.weekday() < 5 and 8 <= now.hour < 18


async def _connector_quiet_scan(org_id: str, threshold_hours: int, post: bool = True) -> list:
    from self_scan import _post_chat_alert
    now = datetime.now(timezone.utc)
    quiet = []
    async for row in db.crisis_connector_health.find({"org_id": org_id}):
        lr = _parse_iso(row.get("last_received"))
        if not lr:
            continue
        hrs = (now - lr).total_seconds() / 3600
        if hrs < threshold_hours:
            continue
        if row.get("last_title") == "Connection test":
            continue
        vendor = row.get("vendor")
        quiet.append({"vendor": vendor, "hours": round(hrs, 1), "last_received": row.get("last_received")})
        if post and not row.get("quiet_alerted_at"):
            channels = await _chat_channels(org_id)
            if channels["teams"] or channels["slack"]:
                try:
                    await _post_chat_alert(
                        org_id, f"⚠️ Connector quiet — {vendor}",
                        f"The {vendor} connector has not delivered an event for ~{round(hrs)}h "
                        f"(last {row.get('last_received')}). Confirm the integration is still wired.")
                except Exception:
                    pass
            await db.crisis_connector_health.update_one(
                {"_id": row["_id"]}, {"$set": {"quiet_alerted_at": now.isoformat()}})
    return quiet


async def run_connector_quiet_alerts(org_id: str | None = None) -> int:
    from bson import ObjectId
    if not _within_business_hours():
        return 0
    orgs_q: dict = {"crisis_settings.connector_quiet": True}
    if org_id:
        orgs_q["_id"] = ObjectId(org_id)
    alerted = 0
    async for org in db.organizations.find(orgs_q, {"_id": 1, "crisis_settings": 1}):
        thr = int((org.get("crisis_settings") or {}).get("connector_quiet_hours") or 6)
        quiet = await _connector_quiet_scan(str(org["_id"]), thr, post=True)
        alerted += len(quiet)
    return alerted


@api.get("/connectors/quiet-check")
async def connector_quiet_check(user: dict = Depends(get_current_user)):
    _require_operator(user)
    org_id = user["org_id"]
    s = await _crisis_settings(org_id)
    quiet = await _connector_quiet_scan(org_id, s["connector_quiet_hours"], post=False)
    return {"threshold_hours": s["connector_quiet_hours"],
            "business_hours": _within_business_hours(),
            "enabled": s["connector_quiet"], "quiet": quiet}
