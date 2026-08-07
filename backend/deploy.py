import io
import os
import sys
import zipfile

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse, FileResponse
from pydantic import BaseModel

from auth import get_current_user

deploy_router = APIRouter(prefix="/api/deploy")
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_ONPREM = os.path.join(_ROOT, "deploy", "onprem")
_DOCS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "docs")
_GUIDE_PDF = os.path.join(_DOCS, "Obserra-Install-and-User-Guide.pdf")
_GUIDE_DOCX = os.path.join(_DOCS, "Obserra-Install-and-User-Guide.docx")


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
        headers={"Content-Disposition": 'attachment; filename="obserra-onprem-deploy.zip"'},
    )


@deploy_router.get("/guide.pdf")
async def guide_pdf(user: dict = Depends(get_current_user)):
    if user.get("role") != "admin":
        raise HTTPException(403, "Only admins can download the guide")
    if not os.path.exists(_GUIDE_PDF):
        raise HTTPException(404, "Guide not generated yet")
    return FileResponse(_GUIDE_PDF, media_type="application/pdf",
                        filename="Obserra-Install-and-User-Guide.pdf")


@deploy_router.get("/guide.docx")
async def guide_docx(user: dict = Depends(get_current_user)):
    if user.get("role") != "admin":
        raise HTTPException(403, "Only admins can download the guide")
    if not os.path.exists(_GUIDE_DOCX):
        raise HTTPException(404, "Guide not generated yet")
    return FileResponse(
        _GUIDE_DOCX,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename="Obserra-Install-and-User-Guide.docx")


def _build_onprem_zip() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for root, _dirs, files in os.walk(_ONPREM):
            for fn in files:
                fp = os.path.join(root, fn)
                z.write(fp, os.path.join("obserra-onprem", os.path.relpath(fp, _ONPREM)))
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


class EmailDocsBody(BaseModel):
    to: str


@deploy_router.post("/email-docs")
async def email_docs(body: EmailDocsBody, user: dict = Depends(get_current_user)):
    if user.get("role") != "admin":
        raise HTTPException(403, "Only admins can email the deployment docs")
    import base64
    import re
    to = (body.to or "").strip()
    if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", to):
        raise HTTPException(400, "Enter a valid email address")
    from kernel import notifications
    attachments = []
    if os.path.exists(_GUIDE_PDF):
        with open(_GUIDE_PDF, "rb") as f:
            attachments.append({"filename": "Obserra-Install-and-User-Guide.pdf",
                                "content": base64.b64encode(f.read()).decode()})
    if os.path.isdir(_ONPREM):
        attachments.append({"filename": "obserra-onprem-deploy.zip",
                            "content": base64.b64encode(_build_onprem_zip()).decode()})
    html = ("<div style='font:400 14px Arial;color:#0f1e3d'>"
            "<h2 style='font:800 20px Arial;color:#0f1e3d'>Obserra EIOS — Install &amp; Deployment</h2>"
            "<p>Attached you'll find the <b>Install &amp; User Guide</b> (PDF) and the "
            "<b>on-premise deployment package</b> (zip).</p>"
            "<ul><li>Self-host with Docker: unzip and follow <code>INSTALL.md</code>.</li>"
            "<li>Install the app on any device straight from the browser (PWA) — no app store needed.</li></ul>"
            f"<p style='color:#6b7280'>Sent by {user['email']} via Obserra EIOS.</p></div>")
    await notifications.send_email(to, "Obserra EIOS — Install Guide & Deployment Package",
                                   html, attachments=attachments)
    return {"status": "sent", "to": to}
