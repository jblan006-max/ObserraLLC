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
    await _get_case(org_id, ref)
    changes = {key: value for key, value in body.model_dump().items() if value is not None}
    if not changes:
        raise HTTPException(status_code=400, detail="No changes")

    changes["updated_at"] = _now()
    await db.crisis_cases.update_one(
        {"org_id": org_id, "ref": ref},
        {"$set": changes},
    )
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


class CrisisObligationUpdate(BaseModel):
    status: Literal["Assessing", "Notification Required", "Not Applicable", "Notified", "On Hold"] | None = None
    responsible: str | None = Field(default=None, max_length=160)
    notification_decision: str | None = Field(default=None, max_length=1000)
    deadline_at: str | None = None


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


@api.get("/insight")
async def crisis_insight(ref: str | None = None, user: dict = Depends(get_current_user)):
    """Board-grade AI briefing grounded ONLY in the live crisis case (case, events, actions,
    decisions, recovery, regulatory obligations). Cached 120s per org+case."""
    import os, json, asyncio, re
    org_id = user["org_id"]
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
