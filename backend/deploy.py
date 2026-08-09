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


@deploy_router.post("/reset-demo")
async def reset_demo(user: dict = Depends(get_current_user)):
    """Wipe this org's SAP + demo collections and reseed a clean populated instance
    (admin) — handy for restoring a pristine demo/trial environment."""
    if user.get("role") != "admin":
        raise HTTPException(403, "Only admins can reset the demo data")
    from db import db
    from seed_data import seed_org
    from sap_engine import seed_sap_uac
    org_id = user["org_id"]
    names = await db.list_collection_names()
    targets = {n for n in names if n.startswith("sap_")}
    targets.update(["risks", "health_index", "ai_systems", "ai_incidents",
                    "recommendations", "decisions", "connectors"])
    for n in targets:
        await db[n].delete_many({"org_id": org_id})
    await seed_org(org_id)
    await seed_sap_uac(org_id)
    persons = await db.sap_persons.count_documents({"org_id": org_id})
    accounts = await db.sap_accounts.count_documents({"org_id": org_id})
    return {"ok": True, "reset": True, "persons": persons, "accounts": accounts}


def _now_iso():
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


async def _set_upgrade_status(org_id, state, stage=None, line=None):
    from db import db
    upd = {"state": state, "updated_at": _now_iso()}
    if stage:
        upd["stage"] = stage
    op = {"$set": upd}
    if line:
        op["$push"] = {"lines": {"$each": [line], "$slice": -60}}
    await db.deploy_status.update_one({"_id": f"upgrade:{org_id}"}, op, upsert=True)


async def _upgrade_job(org_id: str, compose: str):
    import asyncio
    import subprocess
    from starlette.concurrency import run_in_threadpool
    from db import db
    await db.deploy_status.update_one({"_id": f"upgrade:{org_id}"},
                                      {"$set": {"lines": [], "started_at": _now_iso()}}, upsert=True)
    await _set_upgrade_status(org_id, "running", "Starting", "Preparing to pull the latest images…")
    await asyncio.sleep(1.0)
    try:
        await _set_upgrade_status(org_id, "running", "Pulling images", f"$ docker compose -f {compose} pull")
        r = await run_in_threadpool(lambda: subprocess.run(
            ["docker", "compose", "-f", compose, "pull"], capture_output=True, text=True, timeout=900))
        for ln in (r.stderr or r.stdout or "").splitlines()[-8:]:
            if ln.strip():
                await _set_upgrade_status(org_id, "running", "Pulling images", ln.strip())
        if r.returncode != 0:
            raise RuntimeError(f"pull failed (exit {r.returncode})")
        await _set_upgrade_status(org_id, "running", "Recreating containers",
                                  "$ docker compose up -d  (the app will briefly restart)")
        subprocess.Popen(["docker", "compose", "-f", compose, "up", "-d"])
        await _set_upgrade_status(org_id, "done", "Upgrade applied",
                                  "New containers are starting — this view will reconnect shortly.")
    except Exception as e:
        await _set_upgrade_status(org_id, "error", "Upgrade failed", str(e)[:300])


@deploy_router.get("/upgrade/status")
async def upgrade_status(user: dict = Depends(get_current_user)):
    from db import db
    doc = await db.deploy_status.find_one({"_id": f"upgrade:{user['org_id']}"})
    if not doc:
        return {"state": "idle", "lines": []}
    doc.pop("_id", None)
    return doc


@deploy_router.post("/upgrade")
async def upgrade(background_tasks: BackgroundTasks, user: dict = Depends(get_current_user)):
    """One-click 'pull latest & restart' for GHCR/compose self-hosted deployments.
    Opt-in via ONPREM_UPGRADE=1 and requires the Docker socket + compose file mounted into
    the backend container. Inert (400) in the hosted deployment."""
    if user.get("role") != "admin":
        raise HTTPException(403, "Only admins can trigger an upgrade")
    import shutil
    if os.environ.get("ONPREM_UPGRADE") != "1" or not shutil.which("docker"):
        raise HTTPException(400, "Automatic upgrade isn't enabled on this deployment. Enable it with "
                                 "ONPREM_UPGRADE=1 and mount the Docker socket + compose file, or run "
                                 "'docker compose -f deploy/docker-compose.ghcr.yml pull && up -d'.")
    compose = os.environ.get("ONPREM_COMPOSE", "/deploy/docker-compose.ghcr.yml")
    background_tasks.add_task(_upgrade_job, user["org_id"], compose)
    return {"ok": True, "status": "upgrading", "compose": compose}


# --- Backups (org-scoped Mongo export/restore; runs nightly from the daily cron) ---
_BACKUP_DIR = os.environ.get("BACKUP_DIR", os.path.join(_ROOT, "backups"))

_DEFAULT_BACKUP_CFG = {"enabled": True, "frequency": "daily", "keep": 14}
_DEFAULT_ALERT_CFG = {
    "db": {"slack": True, "teams": True, "email": True},
    "connector": {"slack": True, "teams": True, "email": False},
    "scheduler": {"slack": True, "teams": True, "email": True},
}


def _backup_cfg(org):
    c = ((org or {}).get("system_health") or {}).get("backup") or {}
    freq = c.get("frequency", "daily")
    return {"enabled": bool(c.get("enabled", True)),
            "frequency": freq if freq in ("daily", "weekly") else "daily",
            "keep": max(1, min(90, int(c.get("keep") or 14)))}


def _alert_cfg(org):
    saved = ((org or {}).get("system_health") or {}).get("alerts") or {}
    out = {}
    for k, d in _DEFAULT_ALERT_CFG.items():
        s = saved.get(k) or {}
        out[k] = {ch: bool(s.get(ch, d[ch])) for ch in ("slack", "teams", "email")}
    return out


def _safe_backup_path(filename: str) -> str:
    name = os.path.basename(filename or "")
    if not name.endswith(".json.gz") or name != (filename or ""):
        raise HTTPException(400, "Invalid backup filename")
    return os.path.join(_BACKUP_DIR, name)


def _meta_path(fname: str) -> str:
    return os.path.join(_BACKUP_DIR, os.path.basename(fname) + ".meta.json")


def _iso_from_mtime(fp):
    from datetime import datetime, timezone
    return datetime.fromtimestamp(os.path.getmtime(fp), tz=timezone.utc).isoformat()


async def backup_org(org_id: str, tag: str = "manual") -> dict:
    import gzip
    import json
    from bson import json_util, ObjectId
    from db import db
    os.makedirs(_BACKUP_DIR, exist_ok=True)
    org = await db.organizations.find_one({"_id": ObjectId(org_id)}) or {}
    org_name = org.get("name") or org_id
    names = [n for n in await db.list_collection_names() if not n.startswith("system.")]
    data, total = {}, 0
    for n in names:
        docs = await db[n].find({"org_id": org_id}).to_list(100000)
        if docs:
            data[n] = docs
            total += len(docs)
    import uuid
    stamp = _now_iso().replace(":", "").replace("-", "").replace("T", "").replace(".", "").replace("+", "")[:20]
    fname = f"obserra-backup-{org_id}-{stamp}-{uuid.uuid4().hex[:6]}.json.gz"
    meta = {"org_id": org_id, "org_name": org_name, "created_at": _now_iso(),
            "collections": len(data), "docs": total, "tag": tag}
    payload = {"_meta": meta, "collections": data}
    fp = os.path.join(_BACKUP_DIR, fname)
    with gzip.open(fp, "wt", encoding="utf-8") as f:
        f.write(json_util.dumps(payload))
    with open(_meta_path(fname), "w", encoding="utf-8") as f:
        json.dump({**meta, "size": os.path.getsize(fp), "file": fname}, f)
    return {"file": fname, "size": os.path.getsize(fp), "collections": len(data),
            "docs": total, "org_name": org_name, "tag": tag, "created_at": meta["created_at"]}


def _list_backup_files(org_id: str):
    import json
    if not os.path.isdir(_BACKUP_DIR):
        return []
    out = []
    for fn in os.listdir(_BACKUP_DIR):
        if fn.startswith(f"obserra-backup-{org_id}-") and fn.endswith(".json.gz"):
            fp = os.path.join(_BACKUP_DIR, fn)
            info = {"file": fn, "size": os.path.getsize(fp), "created_at": _iso_from_mtime(fp),
                    "collections": None, "docs": None, "org_name": None, "tag": None}
            mp = _meta_path(fn)
            if os.path.exists(mp):
                try:
                    with open(mp, encoding="utf-8") as f:
                        m = json.load(f)
                    info.update(collections=m.get("collections"), docs=m.get("docs"),
                                org_name=m.get("org_name"), tag=m.get("tag"))
                except Exception:
                    pass
            out.append(info)
    return sorted(out, key=lambda x: x["file"], reverse=True)


async def restore_org(org_id: str, filename: str, auto_backup: bool = True) -> dict:
    import gzip
    from bson import json_util
    from db import db
    fp = _safe_backup_path(filename)
    if not os.path.exists(fp) or f"-{org_id}-" not in filename:
        raise HTTPException(404, "Backup not found")
    with gzip.open(fp, "rt", encoding="utf-8") as f:
        payload = json_util.loads(f.read())
    if payload.get("_meta", {}).get("org_id") != org_id:
        raise HTTPException(400, "Backup belongs to a different organization")
    # Snapshot the CURRENT state first so a restore can never lose live data.
    pre = None
    if auto_backup:
        pre = await backup_org(org_id, tag="pre-restore")
        _prune_backups(org_id)
    cols = payload.get("collections", {})
    restored = 0
    for name, docs in cols.items():
        await db[name].delete_many({"org_id": org_id})
        if docs:
            await db[name].insert_many(docs)
            restored += len(docs)
    return {"ok": True, "restored_docs": restored, "collections": len(cols),
            "pre_restore_backup": (pre or {}).get("file")}


def _prune_backups(org_id: str, keep: int = 14):
    for old in _list_backup_files(org_id)[keep:]:
        for p in (os.path.join(_BACKUP_DIR, old["file"]), _meta_path(old["file"])):
            try:
                os.remove(p)
            except Exception:
                pass


async def backup_all_orgs():
    """Nightly backup of every org (invoked from the daily cron); honours each org's schedule
    config (enabled, daily/weekly frequency, snapshots to keep). Best-effort."""
    import logging
    from datetime import datetime, timezone, timedelta
    from db import db
    orgs = await db.organizations.find({}).to_list(1000)
    for o in orgs:
        oid = str(o["_id"])
        cfg = _backup_cfg(o)
        if not cfg["enabled"]:
            continue
        try:
            if cfg["frequency"] == "weekly":
                existing = _list_backup_files(oid)
                if existing:
                    la = datetime.fromisoformat(existing[0]["created_at"])
                    if la.tzinfo is None:
                        la = la.replace(tzinfo=timezone.utc)
                    if datetime.now(timezone.utc) - la < timedelta(days=6, hours=12):
                        continue
            await backup_org(oid, tag="nightly")
            _prune_backups(oid, keep=cfg["keep"])
        except Exception as e:
            logging.getLogger("deploy").warning(f"nightly backup failed for org {oid}: {e}")


@deploy_router.post("/backup")
async def backup_now(user: dict = Depends(get_current_user)):
    if user.get("role") != "admin":
        raise HTTPException(403, "Only admins can create backups")
    from bson import ObjectId
    org = await db.organizations.find_one({"_id": ObjectId(user["org_id"])}) or {}
    res = await backup_org(user["org_id"])
    _prune_backups(user["org_id"], keep=_backup_cfg(org)["keep"])
    return res


class BackupConfig(BaseModel):
    enabled: bool = True
    frequency: str = "daily"
    keep: int = 14


@deploy_router.get("/backup-config")
async def get_backup_config(user: dict = Depends(get_current_user)):
    from bson import ObjectId
    org = await db.organizations.find_one({"_id": ObjectId(user["org_id"])}) or {}
    return _backup_cfg(org)


@deploy_router.put("/backup-config")
async def put_backup_config(body: BackupConfig, user: dict = Depends(get_current_user)):
    if user.get("role") != "admin":
        raise HTTPException(403, "Admins only")
    from bson import ObjectId
    if body.frequency not in ("daily", "weekly"):
        raise HTTPException(400, "frequency must be 'daily' or 'weekly'")
    cfg = {"enabled": bool(body.enabled), "frequency": body.frequency,
           "keep": max(1, min(90, int(body.keep)))}
    await db.organizations.update_one({"_id": ObjectId(user["org_id"])},
                                      {"$set": {"system_health.backup": cfg}})
    return cfg


@deploy_router.get("/backups")
async def list_backups(user: dict = Depends(get_current_user)):
    if user.get("role") != "admin":
        raise HTTPException(403, "Only admins can view backups")
    return {"backups": _list_backup_files(user["org_id"]), "dir": _BACKUP_DIR}


@deploy_router.post("/restore")
async def restore_backup(body: dict, user: dict = Depends(get_current_user)):
    if user.get("role") != "admin":
        raise HTTPException(403, "Only admins can restore backups")
    if (body.get("confirm") or "").strip().upper() != "RESTORE":
        raise HTTPException(400, "Type RESTORE to confirm — restoring replaces the current data "
                                 "(a pre-restore backup is taken automatically first).")
    return await restore_org(user["org_id"], body.get("file", ""))


@deploy_router.get("/backup/download")
async def download_backup(file: str, user: dict = Depends(get_current_user)):
    if user.get("role") != "admin":
        raise HTTPException(403, "Only admins can download backups")
    fp = _safe_backup_path(file)
    if not os.path.exists(fp) or f"-{user['org_id']}-" not in file:
        raise HTTPException(404, "Backup not found")
    with open(fp, "rb") as f:
        content = f.read()
    return StreamingResponse(io.BytesIO(content), media_type="application/gzip",
                             headers={"Content-Disposition": f'attachment; filename="{os.path.basename(fp)}"'})


# --- Deep system-health evaluation + Slack/Teams degraded alerts ---
async def evaluate_org_health(org_id: str) -> dict:
    """Per-org system-health snapshot (DB, scheduler, connectors) for the header pill + alerts."""
    import time
    from db import db
    issue_types = []
    t0 = time.perf_counter()
    db_ok = True
    try:
        await db.command("ping")
    except Exception:
        db_ok = False
    latency = round((time.perf_counter() - t0) * 1000, 1)
    if not db_ok:
        issue_types.append(("db", "Database is not responding"))
    cron_ok = bool(os.environ.get("WEBHOOK_CRON_SECRET"))
    if not cron_ok:
        issue_types.append(("scheduler", "Scheduler is not armed"))
    degraded, degraded_detail = [], []
    try:
        from connectors_catalog import CATALOG
        names = {e["id"]: e["name"] for e in CATALOG}
        states = await db.connector_state.find({"org_id": org_id}).to_list(500)
        for st in states:
            if st.get("state") in ("degraded", "unreachable", "error", "auth_failed"):
                cid = st.get("cid") or "connector"
                degraded.append(cid)
                degraded_detail.append({"cid": cid, "name": names.get(cid, cid), "state": st.get("state"),
                                        "detail": st.get("detail") or "", "checked_at": st.get("checked_at")})
    except Exception:
        pass
    if degraded:
        issue_types.append(("connector", f"{len(degraded)} connector(s) degraded: {', '.join(degraded[:5])}"))
    issues = [m for _, m in issue_types]
    status = "down" if not db_ok else ("degraded" if issue_types else "ok")
    return {"status": status, "db": db_ok, "db_latency_ms": latency, "scheduler_armed": cron_ok,
            "degraded_connectors": degraded, "degraded_detail": degraded_detail,
            "issues": issues, "issue_types": issue_types, "healthy": not issue_types}


async def _route_alert(org, channels, title, body):
    """Post a health alert to only the channels enabled for this event type."""
    import httpx
    from kernel import notifications
    org_id = str(org["_id"])
    alerts = org.get("scan_alerts") or {}
    teams_url = alerts.get("teams_url") or (org.get("live_teams") or {}).get("webhook_url")
    slack_url = alerts.get("slack_url")
    async with httpx.AsyncClient(timeout=15) as c:
        if channels.get("teams") and teams_url:
            try:
                await c.post(teams_url, json={"@type": "MessageCard", "@context": "https://schema.org/extensions",
                                              "summary": title, "themeColor": "b45309", "title": title, "text": body})
            except Exception:
                pass
        if channels.get("slack") and slack_url:
            try:
                await c.post(slack_url, json={"text": f"*{title}*\n{body}"})
            except Exception:
                pass
    if channels.get("email"):
        recips = await db.users.find({"org_id": org_id, "role": {"$in": ["admin", "executive"]}},
                                     {"_id": 0, "email": 1}).to_list(200)
        html = (f"<div style='font:400 14px Arial;color:#1f2937;max-width:560px;margin:auto'>"
                f"<h2 style='color:#b45309'>{title}</h2><p>{body}</p>"
                f"<p style='font-size:11px;color:#9ca3af'>Obserra SAP UAC — System Health</p></div>")
        for r in recips:
            try:
                await notifications.send_email(r["email"], title, html)
            except Exception:
                pass


async def _record_health(org_id, h, min_gap_min=12):
    """Append a throttled health sample to db.health_history for the 24h uptime strip."""
    from datetime import datetime, timezone, timedelta
    now = datetime.now(timezone.utc)
    last = await db.health_history.find_one({"org_id": org_id}, sort=[("at", -1)])
    if last:
        try:
            la = datetime.fromisoformat(last["at"])
            if la.tzinfo is None:
                la = la.replace(tzinfo=timezone.utc)
            if now - la < timedelta(minutes=min_gap_min):
                return
        except Exception:
            pass
    await db.health_history.insert_one({
        "org_id": org_id, "at": now.isoformat(), "status": h.get("status"),
        "healthy": h.get("healthy"), "db_ok": h.get("db"),
        "scheduler_armed": h.get("scheduler_armed"),
        "degraded_count": len(h.get("degraded_connectors") or [])})
    cutoff = (now - timedelta(days=7)).isoformat()
    await db.health_history.delete_many({"org_id": org_id, "at": {"$lt": cutoff}})


async def run_health_alerts():
    """Folded into the daily cron: route Slack/Teams/email + in-app alerts per event type
    (DB / connector / scheduler) when degraded, deduped once per day; records a health sample."""
    import logging
    from datetime import datetime, timezone
    from kernel import notifications
    today = datetime.now(timezone.utc).date().isoformat()
    orgs = await db.organizations.find({}).to_list(1000)
    for org in orgs:
        oid = str(org["_id"])
        try:
            h = await evaluate_org_health(oid)
            await _record_health(oid, h)
            if h["healthy"]:
                continue
            routing = _alert_cfg(org)
            for etype, msg in h.get("issue_types", []):
                await _route_alert(org, routing.get(etype, {"slack": True, "teams": True, "email": False}),
                                   f"⚠ System health — {etype}", msg + "\n\nOpen System Health to review.")
            await notifications.create(oid, "system", "System health degraded", " · ".join(h["issues"]),
                                       ref="system-health", dedupe_key=f"health-degraded:{today}")
        except Exception as e:
            logging.getLogger("deploy").warning(f"health alert failed for org {oid}: {e}")


class HealthAlertConfig(BaseModel):
    db: dict | None = None
    connector: dict | None = None
    scheduler: dict | None = None


@deploy_router.get("/health-config")
async def get_health_config(user: dict = Depends(get_current_user)):
    from bson import ObjectId
    org = await db.organizations.find_one({"_id": ObjectId(user["org_id"])}) or {}
    return {"alerts": _alert_cfg(org)}


@deploy_router.put("/health-config")
async def put_health_config(body: HealthAlertConfig, user: dict = Depends(get_current_user)):
    if user.get("role") != "admin":
        raise HTTPException(403, "Admins only")
    from bson import ObjectId
    routing = {}
    for k in ("db", "connector", "scheduler"):
        s = getattr(body, k) or {}
        routing[k] = {ch: bool(s.get(ch, _DEFAULT_ALERT_CFG[k][ch])) for ch in ("slack", "teams", "email")}
    await db.organizations.update_one({"_id": ObjectId(user["org_id"])},
                                      {"$set": {"system_health.alerts": routing}})
    return {"alerts": routing}


@deploy_router.get("/health-history")
async def get_health_history(hours: int = 24, user: dict = Depends(get_current_user)):
    from datetime import datetime, timezone, timedelta
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=max(1, min(168, hours)))).isoformat()
    pts = await db.health_history.find({"org_id": user["org_id"], "at": {"$gte": cutoff}},
                                       {"_id": 0}).sort("at", 1).to_list(2000)
    return {"points": pts, "hours": hours}


@deploy_router.get("/health-detail")
async def health_detail(user: dict = Depends(get_current_user)):
    """Per-org deep health snapshot for the header status pill (also records a throttled sample)."""
    h = await evaluate_org_health(user["org_id"])
    try:
        await _record_health(user["org_id"], h)
    except Exception:
        pass
    return h


@deploy_router.post("/health-alert-run")
async def health_alert_run(user: dict = Depends(get_current_user)):
    """Admin: evaluate this org's health now and route alerts (per config) if degraded."""
    if user.get("role") != "admin":
        raise HTTPException(403, "Admins only")
    from bson import ObjectId
    h = await evaluate_org_health(user["org_id"])
    org = await db.organizations.find_one({"_id": ObjectId(user["org_id"])}) or {}
    alerts = org.get("scan_alerts") or {}
    has_webhook = bool(alerts.get("teams_url") or alerts.get("slack_url")
                       or (org.get("live_teams") or {}).get("webhook_url"))
    routing = _alert_cfg(org)
    alerted = False
    if not h["healthy"]:
        for etype, msg in h.get("issue_types", []):
            await _route_alert(org, routing.get(etype, {"slack": True, "teams": True, "email": False}),
                               f"⚠ System health — {etype}", msg)
        alerted = True
    return {**h, "webhook_configured": has_webhook, "alerted": alerted, "routing": routing}


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
