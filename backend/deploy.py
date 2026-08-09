import io
import os
import sys
import zipfile

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import StreamingResponse, FileResponse
from pydantic import BaseModel

from auth import get_current_user
from db import db

deploy_router = APIRouter(prefix="/api/deploy")
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_ONPREM = os.path.join(_ROOT, "deploy", "onprem")
_DOCS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "docs")
_GUIDE_PDF = os.path.join(_DOCS, "Obserra-Install-and-User-Guide.pdf")
_GUIDE_DOCX = os.path.join(_DOCS, "Obserra-Install-and-User-Guide.docx")
_GUIDE_EXEC_PDF = os.path.join(_DOCS, "Obserra-SAP-UAC-Executive-Guide.pdf")
_GUIDE_EXEC_DOCX = os.path.join(_DOCS, "Obserra-SAP-UAC-Executive-Guide.docx")
_GUIDE_ADMIN_PDF = os.path.join(_DOCS, "Obserra-SAP-UAC-Admin-Operator-Guide.pdf")
_GUIDE_ADMIN_DOCX = os.path.join(_DOCS, "Obserra-SAP-UAC-Admin-Operator-Guide.docx")
_PDF_MT = "application/pdf"
_DOCX_MT = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

_PKG = "obserra-sap-uac"
import importlib.util as _ilu
_pack_spec = _ilu.spec_from_file_location("onprem_pack", os.path.join(_ROOT, "scripts", "onprem_pack.py"))
onprem_pack = _ilu.module_from_spec(_pack_spec)
_pack_spec.loader.exec_module(onprem_pack)


def _serve_guide(path, media, fname):
    if not os.path.exists(path):
        raise HTTPException(404, "Guide not generated yet")
    return FileResponse(path, media_type=media, filename=fname)


@deploy_router.get("/onprem-package")
async def onprem_package(user: dict = Depends(get_current_user)):
    """Stream a zip of the on-premise deployment package (docker-compose, Dockerfiles, docs)."""
    if user.get("role") != "admin":
        raise HTTPException(403, "Only admins can download the on-premise deployment package")
    if not os.path.isdir(_ONPREM):
        raise HTTPException(404, "Deployment package not available")
    return StreamingResponse(
        io.BytesIO(_build_onprem_zip()),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{onprem_pack.zip_name()}"'},
    )


@deploy_router.get("/guide.pdf")
async def guide_pdf(user: dict = Depends(get_current_user)):
    if user.get("role") != "admin":
        raise HTTPException(403, "Only admins can download the guide")
    if not os.path.exists(_GUIDE_PDF):
        raise HTTPException(404, "Guide not generated yet")
    return FileResponse(_GUIDE_PDF, media_type="application/pdf",
                        filename="Obserra-SAP-UAC-Install-and-User-Guide.pdf")


@deploy_router.get("/guide.docx")
async def guide_docx(user: dict = Depends(get_current_user)):
    if user.get("role") != "admin":
        raise HTTPException(403, "Only admins can download the guide")
    if not os.path.exists(_GUIDE_DOCX):
        raise HTTPException(404, "Guide not generated yet")
    return FileResponse(
        _GUIDE_DOCX,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename="Obserra-SAP-UAC-Install-and-User-Guide.docx")


@deploy_router.get("/guide-exec.pdf")
async def guide_exec_pdf(user: dict = Depends(get_current_user)):
    if user.get("role") != "admin":
        raise HTTPException(403, "Only admins can download the guide")
    return _serve_guide(_GUIDE_EXEC_PDF, _PDF_MT, "Obserra-SAP-UAC-Executive-Guide.pdf")


@deploy_router.get("/guide-exec.docx")
async def guide_exec_docx(user: dict = Depends(get_current_user)):
    if user.get("role") != "admin":
        raise HTTPException(403, "Only admins can download the guide")
    return _serve_guide(_GUIDE_EXEC_DOCX, _DOCX_MT, "Obserra-SAP-UAC-Executive-Guide.docx")


@deploy_router.get("/guide-admin.pdf")
async def guide_admin_pdf(user: dict = Depends(get_current_user)):
    if user.get("role") != "admin":
        raise HTTPException(403, "Only admins can download the guide")
    return _serve_guide(_GUIDE_ADMIN_PDF, _PDF_MT, "Obserra-SAP-UAC-Admin-Operator-Guide.pdf")


@deploy_router.get("/guide-admin.docx")
async def guide_admin_docx(user: dict = Depends(get_current_user)):
    if user.get("role") != "admin":
        raise HTTPException(403, "Only admins can download the guide")
    return _serve_guide(_GUIDE_ADMIN_DOCX, _DOCX_MT, "Obserra-SAP-UAC-Admin-Operator-Guide.docx")


def _build_onprem_zip() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for src, arc in onprem_pack.iter_files():
            z.write(src, f"{onprem_pack.PKG}/{arc}")
        z.writestr(f"{onprem_pack.PKG}/.dockerignore", onprem_pack.DOCKERIGNORE)
        z.writestr(f"{onprem_pack.PKG}/VERSION", onprem_pack.read_version() + "\n")
        z.writestr(f"{onprem_pack.PKG}/BUILD_INFO", onprem_pack.build_info())
    return buf.getvalue()


def regenerate_guides(capture: bool = False):
    """(Re)build the PDF + Word guides from the current screenshots.

    When ``capture`` is set, first refresh the dashboard screenshots via Playwright
    (best-effort; falls back to the existing screenshot set on any failure)."""
    if capture:
        try:
            import subprocess
            env = {**os.environ, "PLAYWRIGHT_BROWSERS_PATH": os.environ.get("PLAYWRIGHT_BROWSERS_PATH", "/pw-browsers")}
            subprocess.run([sys.executable, os.path.join(_ROOT, "scripts", "capture_shots.py")],
                           env=env, timeout=150, check=False)
        except Exception:
            pass
    import importlib.util
    gp = os.path.join(_ROOT, "scripts", "gen_docs.py")
    spec = importlib.util.spec_from_file_location("gen_docs", gp)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.generate_all()


@deploy_router.post("/regenerate-guides")
async def regenerate(capture: bool = False, user: dict = Depends(get_current_user)):
    if user.get("role") != "admin":
        raise HTTPException(403, "Only admins can regenerate the guides")
    try:
        res = regenerate_guides(capture=capture)
        return {"ok": True, "captured": capture, "pdf_size": res["pdf_size"], "docx_size": res["docx_size"]}
    except Exception as e:
        raise HTTPException(500, f"Could not regenerate guides: {e}")


async def _refresh_visuals_job(org_id: str):
    """Background: recapture every dashboard, rebuild tour previews + guides, then notify."""
    from starlette.concurrency import run_in_threadpool
    from kernel import notifications
    try:
        res = await run_in_threadpool(regenerate_guides, True)
        await notifications.create(
            org_id, "system", "Visuals updated",
            "Tour previews and the PDF/Word guides were refreshed from the latest dashboards "
            f"(guide {round(res.get('pdf_size', 0) / 1e6, 1)} MB).")
    except Exception as e:
        await notifications.create(org_id, "system", "Visual refresh failed",
                                   f"Could not refresh visuals: {e}")


@deploy_router.post("/refresh-visuals")
async def refresh_visuals(background_tasks: BackgroundTasks, user: dict = Depends(get_current_user)):
    """Kick off a full recapture + guide rebuild in the background; the admin gets an
    in-app 'Visuals updated' notification when it finishes (no blocking request)."""
    if user.get("role") != "admin":
        raise HTTPException(403, "Only admins can refresh visuals")
    background_tasks.add_task(_refresh_visuals_job, user["org_id"])
    return {"ok": True, "status": "started"}


_UPDATE_CACHE = {"ts": 0.0, "data": None}


def _ver_tuple(v):
    import re
    p = [int(x) for x in re.findall(r"\d+", v or "")][:3]
    return tuple(p + [0] * (3 - len(p)))


async def _fetch_latest_version():
    """Best-effort: fetch {version, notes?, url?} from UPDATE_MANIFEST_URL (cached 6h).
    Unset/unreachable => None, so hosted deployments simply never show an update banner."""
    url = os.environ.get("UPDATE_MANIFEST_URL")
    if not url:
        return None
    import time
    if _UPDATE_CACHE["data"] and time.time() - _UPDATE_CACHE["ts"] < 21600:
        return _UPDATE_CACHE["data"]
    from starlette.concurrency import run_in_threadpool

    def _get():
        import json
        import urllib.request
        req = urllib.request.Request(url, headers={"User-Agent": "Obserra-SAP-UAC/update-check"})
        with urllib.request.urlopen(req, timeout=4) as r:
            return json.loads(r.read().decode())
    try:
        data = await run_in_threadpool(_get)
        _UPDATE_CACHE.update(ts=time.time(), data=data)
        return data
    except Exception:
        return None


@deploy_router.get("/version")
async def deploy_version(user: dict = Depends(get_current_user)):
    """Running version + whether a newer on-prem release is available."""
    current = onprem_pack.read_version()
    latest, notes, url = current, None, None
    manifest = await _fetch_latest_version()
    if manifest:
        latest = str(manifest.get("version") or current).lstrip("v")
        notes = manifest.get("notes")
        url = manifest.get("url")
    return {"current": current, "latest": latest,
            "update_available": _ver_tuple(latest) > _ver_tuple(current),
            "notes": notes, "url": url}


@deploy_router.post("/seed-demo")
async def seed_demo(user: dict = Depends(get_current_user)):
    """Load the realistic demo SAP dataset for this org so dashboards are populated
    (idempotent). Used by the on-prem installer and available to admins in-app."""
    if user.get("role") != "admin":
        raise HTTPException(403, "Only admins can load demo data")
    from db import db
    from seed_data import seed_org
    from sap_engine import seed_sap_uac
    org_id = user["org_id"]
    await seed_org(org_id)
    await seed_sap_uac(org_id)
    persons = await db.sap_persons.count_documents({"org_id": org_id})
    accounts = await db.sap_accounts.count_documents({"org_id": org_id})
    return {"ok": True, "persons": persons, "accounts": accounts}


_TOUR_DIR = os.path.join(_ROOT, "frontend", "public", "tour")
_TOUR_IMAGES = ["overview.jpg", "sod.jpg", "watchlist.jpg", "monitoring.jpg"]


def regenerate_tour_images():
    """Recapture only the in-app onboarding tour preview screenshots so they match the current UI."""
    import subprocess
    env = {**os.environ,
           "PLAYWRIGHT_BROWSERS_PATH": os.environ.get("PLAYWRIGHT_BROWSERS_PATH", "/pw-browsers"),
           "SHOT_TOUR_ONLY": "1"}
    subprocess.run([sys.executable, os.path.join(_ROOT, "scripts", "capture_shots.py")],
                   env=env, timeout=150, check=False)
    return [n for n in _TOUR_IMAGES if os.path.exists(os.path.join(_TOUR_DIR, n))]


@deploy_router.post("/regenerate-tour")
async def regenerate_tour(user: dict = Depends(get_current_user)):
    if user.get("role") != "admin":
        raise HTTPException(403, "Only admins can regenerate the tour images")
    from starlette.concurrency import run_in_threadpool
    try:
        images = await run_in_threadpool(regenerate_tour_images)
        if not images:
            raise HTTPException(500, "Capture produced no tour images")
        return {"ok": True, "images": images}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Could not regenerate tour images: {e}")


class EmailDocsBody(BaseModel):
    to: str


class RecipientsBody(BaseModel):
    recipients: list[str] = []


@deploy_router.get("/recipients")
async def get_deploy_recipients(user: dict = Depends(get_current_user)):
    if user.get("role") != "admin":
        raise HTTPException(403, "Admins only")
    from bson import ObjectId
    org = await db.organizations.find_one({"_id": ObjectId(user["org_id"])}) or {}
    return {"recipients": org.get("deploy_recipients") or []}


@deploy_router.put("/recipients")
async def set_deploy_recipients(body: RecipientsBody, user: dict = Depends(get_current_user)):
    if user.get("role") != "admin":
        raise HTTPException(403, "Admins only")
    import re
    from bson import ObjectId
    valid = []
    for e in body.recipients:
        e = (e or "").strip()
        if re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", e) and e not in valid:
            valid.append(e)
    await db.organizations.update_one({"_id": ObjectId(user["org_id"])},
                                      {"$set": {"deploy_recipients": valid}})
    return {"recipients": valid}


def _doc_attachments():
    import base64
    attachments = []
    if os.path.exists(_GUIDE_PDF):
        with open(_GUIDE_PDF, "rb") as f:
            attachments.append({"filename": "Obserra-SAP-UAC-Install-and-User-Guide.pdf",
                                "content": base64.b64encode(f.read()).decode()})
    if os.path.isdir(_ONPREM):
        attachments.append({"filename": onprem_pack.zip_name(),
                            "content": base64.b64encode(_build_onprem_zip()).decode()})
    return attachments


def _docs_html(sender_email):
    return ("<div style='font:400 14px Arial;color:#0f1e3d'>"
            "<h2 style='font:800 20px Arial;color:#0f1e3d'>Obserra SAP UAC — Install &amp; Deployment</h2>"
            "<p>Attached you'll find the <b>Install &amp; User Guide</b> (PDF) and the "
            "<b>on-premise deployment package</b> (zip).</p>"
            "<ul><li>Self-host with Docker: unzip and follow <code>INSTALL.md</code>.</li>"
            "<li>Install the app on any device straight from the browser (PWA) — no app store needed.</li></ul>"
            f"<p style='color:#6b7280'>Sent by {sender_email} via Obserra SAP UAC.</p></div>")


@deploy_router.post("/email-docs")
async def email_docs(body: EmailDocsBody, user: dict = Depends(get_current_user)):
    if user.get("role") != "admin":
        raise HTTPException(403, "Only admins can email the deployment docs")
    import re
    to = (body.to or "").strip()
    if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", to):
        raise HTTPException(400, "Enter a valid email address")
    from kernel import notifications
    await notifications.send_email(to, "Obserra SAP UAC — Install Guide & Deployment Package",
                                   _docs_html(user["email"]), attachments=_doc_attachments())
    return {"status": "sent", "to": to}


@deploy_router.post("/email-docs-all")
async def email_docs_all(user: dict = Depends(get_current_user)):
    if user.get("role") != "admin":
        raise HTTPException(403, "Only admins can email the deployment docs")
    from bson import ObjectId
    org = await db.organizations.find_one({"_id": ObjectId(user["org_id"])}) or {}
    recipients = org.get("deploy_recipients") or []
    if not recipients:
        raise HTTPException(400, "No saved IT recipients — add some to the distribution list first")
    from kernel import notifications
    attachments = _doc_attachments()
    html = _docs_html(user["email"])
    sent = []
    for to in recipients:
        try:
            await notifications.send_email(to, "Obserra SAP UAC — Install Guide & Deployment Package",
                                           html, attachments=attachments)
            sent.append(to)
        except Exception:
            pass
    return {"status": "sent", "count": len(sent), "recipients": sent}
