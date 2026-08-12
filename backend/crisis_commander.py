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
    return {"case": case, "actions": actions, "events": events}


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
