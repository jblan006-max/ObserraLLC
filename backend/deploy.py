import io
import os
import zipfile

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse, FileResponse

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
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for root, _dirs, files in os.walk(_ONPREM):
            for fn in files:
                fp = os.path.join(root, fn)
                arc = os.path.join("obserra-onprem", os.path.relpath(fp, _ONPREM))
                z.write(fp, arc)
    buf.seek(0)
    return StreamingResponse(
        io.BytesIO(buf.read()),
        media_type="application/zip",
        headers={"Content-Disposition": 'attachment; filename="obserra-onprem-deploy.zip"'},
    )


@deploy_router.get("/guide.pdf")
async def guide_pdf(user: dict = Depends(get_current_user)):
    if not os.path.exists(_GUIDE_PDF):
        raise HTTPException(404, "Guide not generated yet")
    return FileResponse(_GUIDE_PDF, media_type="application/pdf",
                        filename="Obserra-Install-and-User-Guide.pdf")


@deploy_router.get("/guide.docx")
async def guide_docx(user: dict = Depends(get_current_user)):
    if not os.path.exists(_GUIDE_DOCX):
        raise HTTPException(404, "Guide not generated yet")
    return FileResponse(
        _GUIDE_DOCX,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename="Obserra-Install-and-User-Guide.docx")
