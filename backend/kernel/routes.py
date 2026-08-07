"""Kernel API surface — manifest, health, policies, workflows, notifications, remediation."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from auth import get_current_user, require_roles
from kernel import SUBSYSTEMS, notifications, policies, workflows
from kernel.health import compute_health

kernel_router = APIRouter(prefix="/api")


@kernel_router.get("/kernel/manifest")
async def kernel_manifest(user: dict = Depends(get_current_user)):
    return {"name": "Obserra Cybersecurity Kernel", "subsystems": SUBSYSTEMS, "count": len(SUBSYSTEMS)}


@kernel_router.get("/kernel/health")
async def kernel_health(user: dict = Depends(get_current_user)):
    return await compute_health(user["org_id"])


# ---------- Policy Engine ----------
@kernel_router.get("/policies")
async def list_policies(user: dict = Depends(get_current_user)):
    return await policies.list(user["org_id"])


class PolicyCreate(BaseModel):
    name: str
    statement: str
    framework: str = "Custom"
    severity: str = "Medium"
    enforced: bool = True
    threshold: int | None = None


class PolicyUpdate(BaseModel):
    name: str | None = None
    statement: str | None = None
    framework: str | None = None
    severity: str | None = None
    enforced: bool | None = None
    threshold: int | None = None


@kernel_router.post("/policies")
async def create_policy(body: PolicyCreate, admin: dict = Depends(require_roles("admin"))):
    return await policies.create(admin["org_id"], body.model_dump())


@kernel_router.patch("/policies/{policy_id}")
async def update_policy(policy_id: str, body: PolicyUpdate, admin: dict = Depends(require_roles("admin"))):
    updated = await policies.update(admin["org_id"], policy_id, body.model_dump(exclude_unset=True))
    if updated is None:
        raise HTTPException(404, "Policy not found or no changes")
    return updated


# ---------- Workflow Engine ----------
@kernel_router.get("/workflows")
async def list_workflows(user: dict = Depends(get_current_user)):
    return await workflows.list(user["org_id"])


@kernel_router.get("/workflows/{wf_id}")
async def get_workflow(wf_id: str, user: dict = Depends(get_current_user)):
    wf = await workflows.get(user["org_id"], wf_id)
    if not wf:
        raise HTTPException(404, "Workflow not found")
    return wf


class WorkflowAction(BaseModel):
    action: str  # accept | assign | resolve
    assignee: str | None = None
    note: str | None = None


@kernel_router.post("/workflows/{wf_id}/action")
async def act_workflow(wf_id: str, body: WorkflowAction, user: dict = Depends(get_current_user)):
    if body.action not in ("accept", "assign", "resolve"):
        raise HTTPException(400, "Invalid action")
    wf = await workflows.act(user["org_id"], wf_id, body.action, body.assignee, body.note)
    if not wf:
        raise HTTPException(404, "Workflow not found")
    from auth import _log_audit
    await _log_audit(user["org_id"], user["email"], f"remediation.{body.action}",
                     f"{wf.get('subject')} → {wf.get('status')}")
    return wf


# ---------- Notification Engine ----------
@kernel_router.get("/notifications")
async def list_notifications(user: dict = Depends(get_current_user)):
    items = await notifications.list(user["org_id"])
    unread = await notifications.unread_count(user["org_id"])
    return {"items": items, "unread": unread}


@kernel_router.post("/notifications/{notif_id}/read")
async def read_notification(notif_id: str, user: dict = Depends(get_current_user)):
    await notifications.mark_read(user["org_id"], notif_id)
    return {"ok": True}


@kernel_router.post("/notifications/read-all")
async def read_all_notifications(user: dict = Depends(get_current_user)):
    await notifications.mark_all_read(user["org_id"])
    return {"ok": True}


@kernel_router.post("/notifications/{notif_id}/remediate")
async def remediate(notif_id: str, user: dict = Depends(get_current_user)):
    n = await notifications.get(user["org_id"], notif_id)
    if not n:
        raise HTTPException(404, "Notification not found")
    control_id = n.get("ref") or "control"
    wf = await workflows.start_remediation(user["org_id"], control_id, f"Remediate {control_id}", source_notification=notif_id)
    await notifications.mark_read(user["org_id"], notif_id)
    return wf
