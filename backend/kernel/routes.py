"""Kernel API surface — manifest, policies, workflows, notifications."""
from fastapi import APIRouter, Depends

from auth import get_current_user, require_roles
from kernel import SUBSYSTEMS, notifications, policies, workflows

kernel_router = APIRouter(prefix="/api")


@kernel_router.get("/kernel/manifest")
async def kernel_manifest(user: dict = Depends(get_current_user)):
    return {"name": "Obserra Cybersecurity Kernel", "subsystems": SUBSYSTEMS,
            "count": len(SUBSYSTEMS)}


@kernel_router.get("/policies")
async def list_policies(user: dict = Depends(get_current_user)):
    return await policies.list(user["org_id"])


@kernel_router.get("/workflows")
async def list_workflows(user: dict = Depends(get_current_user)):
    return await workflows.list(user["org_id"])


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
