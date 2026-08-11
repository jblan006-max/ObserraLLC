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
_GUIDE_PDF = os.path.join(_DOCS, "Obserra-Control-Intelligence-Install-and-User-Guide.pdf")
_GUIDE_DOCX = os.path.join(_DOCS, "Obserra-Control-Intelligence-Install-and-User-Guide.docx")
_GUIDE_EXEC_PDF = os.path.join(_DOCS, "Obserra-Control-Intelligence-Executive-Guide.pdf")
_GUIDE_EXEC_DOCX = os.path.join(_DOCS, "Obserra-Control-Intelligence-Executive-Guide.docx")
_GUIDE_ADMIN_PDF = os.path.join(_DOCS, "Obserra-Control-Intelligence-Admin-Operator-Guide.pdf")
_GUIDE_ADMIN_DOCX = os.path.join(_DOCS, "Obserra-Control-Intelligence-Admin-Operator-Guide.docx")
_PDF_MT = "application/pdf"
_DOCX_MT = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

_PKG = "obserra-sap-uac"
import importlib.util as _ilu
_pack_spec = _ilu.spec_from_file_location("onprem_pack", os.path.join(_ROOT, "scripts", "onprem_pack.py"))
onprem_pack = _ilu.module_from_spec(_pack_spec)
_pack_spec.loader.exec_module(onprem_pack)


_DL_CACHE_HEADERS = {"Cache-Control": "private, max-age=300"}


def _serve_guide(path, media, fname):
    if not os.path.exists(path):
        raise HTTPException(404, "Guide not generated yet")
    # Cache-Control + FileResponse's ETag/Last-Modified let the browser 304-revalidate large
    # guides (2.6MB PDF) instead of re-transferring on every download.
    return FileResponse(path, media_type=media, filename=fname, headers=dict(_DL_CACHE_HEADERS))


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
                        filename="Obserra-Control-Intelligence-Install-and-User-Guide.pdf",
                        headers=dict(_DL_CACHE_HEADERS))


@deploy_router.get("/guide.docx")
async def guide_docx(user: dict = Depends(get_current_user)):
    if user.get("role") != "admin":
        raise HTTPException(403, "Only admins can download the guide")
    if not os.path.exists(_GUIDE_DOCX):
        raise HTTPException(404, "Guide not generated yet")
    return FileResponse(
        _GUIDE_DOCX,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename="Obserra-Control-Intelligence-Install-and-User-Guide.docx",
        headers=dict(_DL_CACHE_HEADERS))


@deploy_router.get("/guide-exec.pdf")
async def guide_exec_pdf(user: dict = Depends(get_current_user)):
    if user.get("role") != "admin":
        raise HTTPException(403, "Only admins can download the guide")
    return _serve_guide(_GUIDE_EXEC_PDF, _PDF_MT, "Obserra-Control-Intelligence-Executive-Guide.pdf")


@deploy_router.get("/guide-exec.docx")
async def guide_exec_docx(user: dict = Depends(get_current_user)):
    if user.get("role") != "admin":
        raise HTTPException(403, "Only admins can download the guide")
    return _serve_guide(_GUIDE_EXEC_DOCX, _DOCX_MT, "Obserra-Control-Intelligence-Executive-Guide.docx")


@deploy_router.get("/guide-admin.pdf")
async def guide_admin_pdf(user: dict = Depends(get_current_user)):
    if user.get("role") != "admin":
        raise HTTPException(403, "Only admins can download the guide")
    return _serve_guide(_GUIDE_ADMIN_PDF, _PDF_MT, "Obserra-Control-Intelligence-Admin-Operator-Guide.pdf")


@deploy_router.get("/guide-admin.docx")
async def guide_admin_docx(user: dict = Depends(get_current_user)):
    if user.get("role") != "admin":
        raise HTTPException(403, "Only admins can download the guide")
    return _serve_guide(_GUIDE_ADMIN_DOCX, _DOCX_MT, "Obserra-Control-Intelligence-Admin-Operator-Guide.docx")


_ONPREM_ZIP_CACHE = {"key": None, "data": None}


def _onprem_source_key() -> str:
    """Fingerprint the package sources so the 6.6MB zip is rebuilt only when something changes."""
    try:
        mt = 0.0
        for src, _arc in onprem_pack.iter_files():
            try:
                mt = max(mt, os.path.getmtime(src))
            except OSError:
                pass
        return f"{onprem_pack.read_version()}:{mt:.0f}"
    except Exception:
        return "nokey"


def _build_onprem_zip() -> bytes:
    key = _onprem_source_key()
    if _ONPREM_ZIP_CACHE["key"] == key and _ONPREM_ZIP_CACHE["data"] is not None:
        return _ONPREM_ZIP_CACHE["data"]
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for src, arc in onprem_pack.iter_files():
            z.write(src, f"{onprem_pack.PKG}/{arc}")
        z.writestr(f"{onprem_pack.PKG}/.dockerignore", onprem_pack.DOCKERIGNORE)
        z.writestr(f"{onprem_pack.PKG}/VERSION", onprem_pack.read_version() + "\n")
        z.writestr(f"{onprem_pack.PKG}/BUILD_INFO", onprem_pack.build_info())
    data = buf.getvalue()
    _ONPREM_ZIP_CACHE.update(key=key, data=data)
    return data


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


# --- Backup encryption (per-org passphrase; the data key is wrapped with a JWT_SECRET-derived
#     master so nightly backups encrypt unattended, while restore still requires the passphrase) ---
def _derive_key(passphrase: str, salt_hex: str) -> bytes:
    import hashlib
    import base64
    raw = hashlib.pbkdf2_hmac("sha256", (passphrase or "").encode("utf-8"), bytes.fromhex(salt_hex), 200000, dklen=32)
    return base64.urlsafe_b64encode(raw)


def _master_fernet():
    import hashlib
    import base64
    from cryptography.fernet import Fernet
    secret = os.environ.get("JWT_SECRET", "obserra-backup-fallback")
    raw = hashlib.pbkdf2_hmac("sha256", secret.encode("utf-8"), b"obserra-backup-master-v1", 100000, dklen=32)
    return Fernet(base64.urlsafe_b64encode(raw))


def _enc_cfg(org):
    return (((org or {}).get("system_health") or {}).get("backup") or {}).get("encryption") or {}


async def backup_org(org_id: str, tag: str = "manual") -> dict:
    import gzip
    import json
    import uuid
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
    stamp = _now_iso().replace(":", "").replace("-", "").replace("T", "").replace(".", "").replace("+", "")[:20]
    fname = f"obserra-backup-{org_id}-{stamp}-{uuid.uuid4().hex[:6]}.json.gz"
    meta = {"org_id": org_id, "org_name": org_name, "created_at": _now_iso(),
            "collections": len(data), "docs": total, "tag": tag}
    payload = {"_meta": meta, "collections": data}
    gz = gzip.compress(json_util.dumps(payload).encode("utf-8"))
    enc = _enc_cfg(org)
    encrypt = bool(enc.get("enabled") and enc.get("wrapped_key"))
    if encrypt:
        from cryptography.fernet import Fernet
        data_key = _master_fernet().decrypt(enc["wrapped_key"].encode("utf-8"))
        blob = Fernet(data_key).encrypt(gz)
        meta["encrypted"] = True
        meta["salt"] = enc["salt"]
        meta["wrapped_key"] = enc["wrapped_key"]
    else:
        blob = gz
        meta["encrypted"] = False
    fp = os.path.join(_BACKUP_DIR, fname)
    with open(fp, "wb") as f:
        f.write(blob)
    with open(_meta_path(fname), "w", encoding="utf-8") as f:
        json.dump({**meta, "size": os.path.getsize(fp), "file": fname}, f)
    return {"file": fname, "size": os.path.getsize(fp), "collections": len(data),
            "docs": total, "org_name": org_name, "tag": tag, "encrypted": encrypt,
            "created_at": meta["created_at"]}


def _list_backup_files(org_id: str):
    import json
    if not os.path.isdir(_BACKUP_DIR):
        return []
    out = []
    for fn in os.listdir(_BACKUP_DIR):
        if fn.startswith(f"obserra-backup-{org_id}-") and fn.endswith(".json.gz"):
            fp = os.path.join(_BACKUP_DIR, fn)
            info = {"file": fn, "size": os.path.getsize(fp), "created_at": _iso_from_mtime(fp),
                    "collections": None, "docs": None, "org_name": None, "tag": None, "encrypted": False}
            mp = _meta_path(fn)
            if os.path.exists(mp):
                try:
                    with open(mp, encoding="utf-8") as f:
                        m = json.load(f)
                    info.update(collections=m.get("collections"), docs=m.get("docs"),
                                org_name=m.get("org_name"), tag=m.get("tag"),
                                encrypted=bool(m.get("encrypted")))
                except Exception:
                    pass
            out.append(info)
    return sorted(out, key=lambda x: x["file"], reverse=True)


def _read_backup(org_id: str, filename: str, passphrase: str = None):
    """Read + decrypt (if needed) + parse a backup file; returns the payload dict."""
    import gzip
    import json
    from bson import json_util
    fp = _safe_backup_path(filename)
    if not os.path.exists(fp) or f"-{org_id}-" not in filename:
        raise HTTPException(404, "Backup not found")
    meta = {}
    mp = _meta_path(filename)
    if os.path.exists(mp):
        try:
            with open(mp, encoding="utf-8") as f:
                meta = json.load(f)
        except Exception:
            meta = {}
    with open(fp, "rb") as f:
        blob = f.read()
    if meta.get("encrypted"):
        import hashlib
        from cryptography.fernet import Fernet
        if not passphrase:
            raise HTTPException(400, "This backup is encrypted — enter its passphrase to restore.")
        try:
            actual_key = _master_fernet().decrypt(meta["wrapped_key"].encode("utf-8"))
        except Exception:
            raise HTTPException(500, "Unable to unwrap the backup key on this server.")
        if hashlib.sha256(_derive_key(passphrase, meta["salt"])).hexdigest() != hashlib.sha256(actual_key).hexdigest():
            raise HTTPException(403, "Incorrect passphrase for this encrypted backup.")
        try:
            gz = Fernet(actual_key).decrypt(blob)
        except Exception:
            raise HTTPException(400, "Could not decrypt this backup.")
    else:
        gz = blob
    try:
        payload = json_util.loads(gzip.decompress(gz).decode("utf-8"))
    except Exception:
        raise HTTPException(400, "Backup file is corrupt or unreadable.")
    if payload.get("_meta", {}).get("org_id") != org_id:
        raise HTTPException(400, "Backup belongs to a different organization")
    return payload


async def restore_org(org_id: str, filename: str, auto_backup: bool = True, passphrase: str = None) -> dict:
    from db import db
    payload = _read_backup(org_id, filename, passphrase)
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


class EncryptionBody(BaseModel):
    passphrase: str


@deploy_router.get("/backup-encryption")
async def get_backup_encryption(user: dict = Depends(get_current_user)):
    from bson import ObjectId
    org = await db.organizations.find_one({"_id": ObjectId(user["org_id"])}) or {}
    return {"enabled": bool(_enc_cfg(org).get("enabled"))}


@deploy_router.put("/backup-encryption")
async def set_backup_encryption(body: EncryptionBody, user: dict = Depends(get_current_user)):
    if user.get("role") != "admin":
        raise HTTPException(403, "Admins only")
    import os as _os
    import hashlib
    from bson import ObjectId
    if len((body.passphrase or "").strip()) < 8:
        raise HTTPException(400, "Passphrase must be at least 8 characters.")
    salt = _os.urandom(16).hex()
    key = _derive_key(body.passphrase, salt)
    verifier = hashlib.sha256(key).hexdigest()
    wrapped = _master_fernet().encrypt(key).decode("utf-8")
    await db.organizations.update_one(
        {"_id": ObjectId(user["org_id"])},
        {"$set": {"system_health.backup.encryption":
                  {"enabled": True, "salt": salt, "verifier": verifier, "wrapped_key": wrapped}}})
    return {"enabled": True}


@deploy_router.post("/backup-encryption/disable")
async def disable_backup_encryption(body: EncryptionBody, user: dict = Depends(get_current_user)):
    if user.get("role") != "admin":
        raise HTTPException(403, "Admins only")
    import hashlib
    from bson import ObjectId
    org = await db.organizations.find_one({"_id": ObjectId(user["org_id"])}) or {}
    enc = _enc_cfg(org)
    if not enc.get("enabled"):
        return {"enabled": False}
    if hashlib.sha256(_derive_key(body.passphrase, enc["salt"])).hexdigest() != enc.get("verifier"):
        raise HTTPException(403, "Incorrect passphrase.")
    await db.organizations.update_one({"_id": ObjectId(user["org_id"])},
                                      {"$set": {"system_health.backup.encryption.enabled": False}})
    return {"enabled": False}


class RotateEncryptionBody(BaseModel):
    old_passphrase: str
    new_passphrase: str


@deploy_router.post("/backup-encryption/rotate")
async def rotate_backup_passphrase(body: RotateEncryptionBody, user: dict = Depends(get_current_user)):
    """Re-key snapshot encryption: verify the current passphrase, derive a new data key and
    re-encrypt every existing encrypted snapshot with it so old backups stay restorable."""
    if user.get("role") != "admin":
        raise HTTPException(403, "Admins only")
    import os as _os
    import json
    import hashlib
    from cryptography.fernet import Fernet
    from bson import ObjectId
    org = await db.organizations.find_one({"_id": ObjectId(user["org_id"])}) or {}
    enc = _enc_cfg(org)
    if not enc.get("enabled"):
        raise HTTPException(400, "Encryption isn't enabled — nothing to rotate.")
    if hashlib.sha256(_derive_key(body.old_passphrase, enc["salt"])).hexdigest() != enc.get("verifier"):
        raise HTTPException(403, "Incorrect current passphrase.")
    if len((body.new_passphrase or "").strip()) < 8:
        raise HTTPException(400, "New passphrase must be at least 8 characters.")
    new_salt = _os.urandom(16).hex()
    new_key = _derive_key(body.new_passphrase, new_salt)
    new_verifier = hashlib.sha256(new_key).hexdigest()
    new_wrapped = _master_fernet().encrypt(new_key).decode("utf-8")
    reencrypted = 0
    for info in _list_backup_files(user["org_id"]):
        if not info.get("encrypted"):
            continue
        fname = info["file"]
        mp = _meta_path(fname)
        try:
            with open(mp, encoding="utf-8") as f:
                meta = json.load(f)
            old_key = _master_fernet().decrypt(meta["wrapped_key"].encode("utf-8"))
            fp = _safe_backup_path(fname)
            with open(fp, "rb") as f:
                gz = Fernet(old_key).decrypt(f.read())
            with open(fp, "wb") as f:
                f.write(Fernet(new_key).encrypt(gz))
            meta["salt"] = new_salt
            meta["wrapped_key"] = new_wrapped
            meta["size"] = os.path.getsize(fp)
            with open(mp, "w", encoding="utf-8") as f:
                json.dump(meta, f)
            reencrypted += 1
        except Exception:
            continue
    await db.organizations.update_one(
        {"_id": ObjectId(user["org_id"])},
        {"$set": {"system_health.backup.encryption":
                  {"enabled": True, "salt": new_salt, "verifier": new_verifier, "wrapped_key": new_wrapped}}})
    return {"enabled": True, "reencrypted": reencrypted}


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
    return await restore_org(user["org_id"], body.get("file", ""), passphrase=body.get("passphrase"))


@deploy_router.post("/restore-preview")
async def restore_preview(body: dict, user: dict = Depends(get_current_user)):
    """Non-destructive diff: per-collection current-vs-backup record counts so admins can see the
    impact before restoring. Reads (and decrypts if needed) the snapshot but writes nothing."""
    if user.get("role") != "admin":
        raise HTTPException(403, "Admins only")
    from datetime import datetime, timezone
    file = body.get("file", "")
    payload = _read_backup(user["org_id"], file, passphrase=body.get("passphrase"))
    cols = payload.get("collections", {})
    rows, total_backup, total_current = [], 0, 0
    for name, docs in cols.items():
        bcount = len(docs or [])
        ccount = await db[name].count_documents({"org_id": user["org_id"]})
        rows.append({"collection": name, "current": ccount, "backup": bcount, "delta": bcount - ccount})
        total_backup += bcount
        total_current += ccount
    rows.sort(key=lambda r: (abs(r["delta"]), r["backup"]), reverse=True)
    encrypted = bool(next((b for b in _list_backup_files(user["org_id"]) if b["file"] == file), {}).get("encrypted"))
    await db.restore_previews.insert_one({
        "org_id": user["org_id"], "at": datetime.now(timezone.utc).isoformat(), "by": user.get("email"),
        "file": file, "encrypted": encrypted, "collections": len(cols),
        "total_backup": total_backup, "total_current": total_current,
        "net_delta": total_backup - total_current,
        "top": [{"collection": r["collection"], "delta": r["delta"]} for r in rows[:5]]})
    return {"rows": rows, "collections": len(cols),
            "total_backup": total_backup, "total_current": total_current}


@deploy_router.get("/restore-previews")
async def restore_preview_log(user: dict = Depends(get_current_user)):
    """Dry-run audit trail: who previewed which snapshot, when, and the net record delta."""
    if user.get("role") != "admin":
        raise HTTPException(403, "Admins only")
    rows = await db.restore_previews.find({"org_id": user["org_id"]}, {"_id": 0}).sort("at", -1).to_list(25)
    return {"previews": rows}


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
    cutoff = (now - timedelta(days=30)).isoformat()
    await db.health_history.delete_many({"org_id": org_id, "at": {"$lt": cutoff}})


async def run_health_alerts():
    """Folded into the daily cron: bundle all degraded events into ONE digest per channel per day
    (respecting routing) instead of a separate ping per event; records a health sample."""
    import logging
    from datetime import datetime, timezone
    from bson import ObjectId
    from kernel import notifications
    today = datetime.now(timezone.utc).date().isoformat()
    orgs = await db.organizations.find({}).to_list(1000)
    for org in orgs:
        oid = str(org["_id"])
        try:
            h = await evaluate_org_health(oid)
            await _record_health(oid, h)
            last_digest = (org.get("system_health") or {}).get("last_digest_date")
            if h["healthy"]:
                if last_digest:
                    await db.organizations.update_one({"_id": ObjectId(oid)},
                                                      {"$unset": {"system_health.last_digest_date": ""}})
                continue
            await notifications.create(oid, "system", "System health degraded", " · ".join(h["issues"]),
                                       ref="system-health", dedupe_key=f"health-degraded:{today}")
            if last_digest == today:
                continue
            routing = _alert_cfg(org)
            for ch in ("slack", "teams", "email"):
                evs = [msg for etype, msg in h.get("issue_types", []) if routing.get(etype, {}).get(ch)]
                if not evs:
                    continue
                body = "Daily system health digest:\n- " + "\n- ".join(evs) + "\n\nOpen System Health to review."
                await _route_alert(org, {ch: True}, "⚠ System health digest", body)
            await db.organizations.update_one({"_id": ObjectId(oid)},
                                              {"$set": {"system_health.last_digest_date": today}})
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
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=max(1, min(720, hours)))).isoformat()
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


@deploy_router.post("/health-alert-test")
async def health_alert_test(user: dict = Depends(get_current_user)):
    """Admin: fire a sample alert to Slack/Teams/email so webhooks can be verified before an incident."""
    if user.get("role") != "admin":
        raise HTTPException(403, "Admins only")
    from bson import ObjectId
    org = await db.organizations.find_one({"_id": ObjectId(user["org_id"])}) or {}
    alerts = org.get("scan_alerts") or {}
    teams_cfg = bool(alerts.get("teams_url") or (org.get("live_teams") or {}).get("webhook_url"))
    slack_cfg = bool(alerts.get("slack_url"))
    await _route_alert(org, {"slack": True, "teams": True, "email": True},
                       "✅ Obserra SAP UAC — test alert",
                       "This is a test of your System Health alert routing. If you received this, the channel is working correctly.")
    return {"slack_configured": slack_cfg, "teams_configured": teams_cfg, "email_attempted": True}


@deploy_router.get("/health-digest-preview")
async def health_digest_preview(user: dict = Depends(get_current_user)):
    """Show what today's bundled health digest WOULD send per channel, without sending it."""
    if user.get("role") != "admin":
        raise HTTPException(403, "Admins only")
    from datetime import datetime, timezone
    from bson import ObjectId
    org = await db.organizations.find_one({"_id": ObjectId(user["org_id"])}) or {}
    h = await evaluate_org_health(user["org_id"])
    routing = _alert_cfg(org)
    today = datetime.now(timezone.utc).date().isoformat()
    per_channel = {ch: [msg for etype, msg in h.get("issue_types", []) if routing.get(etype, {}).get(ch)]
                   for ch in ("slack", "teams", "email")}
    already_sent = ((org.get("system_health") or {}).get("last_digest_date") == today)
    return {"healthy": h["healthy"], "issues": h.get("issues", []), "per_channel": per_channel,
            "already_sent_today": already_sent,
            "would_send": (not h["healthy"]) and not already_sent and any(per_channel.values())}


def _build_compliance_pdf(org_name, generated_by, version, health, enc, bcfg, backup_count, latest_backup, stats, period_label="Current snapshot", period_uptime=None, verify_url=None):
    """Render a signed, auditor-ready compliance evidence PDF from the live control-plane state."""
    import hashlib
    from datetime import datetime, timezone
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table,
                                    TableStyle, HRFlowable)

    NAVY = colors.HexColor("#0f1e3d")
    ACCENT = colors.HexColor("#2f6df6")
    MUTED = colors.HexColor("#6b7280")
    GRID = colors.HexColor("#e5e7eb")
    generated_at = datetime.now(timezone.utc)

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=20 * mm, bottomMargin=18 * mm,
                            leftMargin=18 * mm, rightMargin=18 * mm,
                            title="Obserra SAP UAC — Compliance Evidence")
    styles = getSampleStyleSheet()
    h1 = ParagraphStyle("h1", parent=styles["Heading1"], textColor=NAVY, fontSize=20, spaceAfter=2, leading=24)
    subs = ParagraphStyle("subs", parent=styles["Normal"], textColor=MUTED, fontSize=9)
    h2 = ParagraphStyle("h2", parent=styles["Heading2"], textColor=NAVY, fontSize=12, spaceBefore=12, spaceAfter=4)
    body = ParagraphStyle("body", parent=styles["Normal"], fontSize=9.5, leading=14)
    small = ParagraphStyle("small", parent=styles["Normal"], fontSize=8, textColor=MUTED, leading=11)

    status = "HEALTHY" if health.get("healthy") else "DEGRADED"
    status_color = colors.HexColor("#12805c") if health.get("healthy") else colors.HexColor("#c2410c")

    el = [Paragraph("Obserra SAP UAC", h1),
          Paragraph("Compliance Evidence Report — SAP User Access Control &amp; Access Intelligence", subs),
          Spacer(1, 6),
          HRFlowable(width="100%", thickness=1.2, color=ACCENT, spaceAfter=8)]

    meta_tbl = Table([["Organization", org_name],
                      ["Reporting period", period_label],
                      ["Generated by", generated_by],
                      ["Generated at (UTC)", generated_at.strftime("%Y-%m-%d %H:%M:%S")],
                      ["Platform version", f"v{version}"]], colWidths=[45 * mm, None])
    meta_tbl.setStyle(TableStyle([("FONTSIZE", (0, 0), (-1, -1), 9.5),
                                  ("TEXTCOLOR", (0, 0), (0, -1), MUTED),
                                  ("TEXTCOLOR", (1, 0), (1, -1), NAVY),
                                  ("TOPPADDING", (0, 0), (-1, -1), 4),
                                  ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]))
    el.append(meta_tbl)

    el.append(Paragraph("1 &middot; System Health &amp; Controls", h2))
    health_tbl = Table([["Overall status", status],
                        ["Database", "Responsive" if health.get("db") else "Not responding"],
                        ["Scheduler", "Armed" if health.get("scheduler_armed") else "Not armed"],
                        ["Degraded connectors", str(len(health.get("degraded_connectors") or []))],
                        ["Backups on file", str(backup_count)],
                        ["Latest backup (UTC)", latest_backup or "None"],
                        ["Backup policy", f"{bcfg.get('frequency', 'daily').title()} · keep {bcfg.get('keep')}"],
                        ["At-rest encryption", "Enabled (AES / Fernet)" if enc.get("enabled") else "Disabled"],
                        ["Uptime (period)", f"{period_uptime}%" if period_uptime is not None else "—"]],
                       colWidths=[55 * mm, None])
    health_tbl.setStyle(TableStyle([("FONTSIZE", (0, 0), (-1, -1), 9.5),
                                    ("TEXTCOLOR", (0, 0), (0, -1), MUTED),
                                    ("GRID", (0, 0), (-1, -1), 0.4, GRID),
                                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f4f6fb")),
                                    ("TEXTCOLOR", (1, 0), (1, 0), status_color),
                                    ("FONTNAME", (1, 0), (1, 0), "Helvetica-Bold"),
                                    ("TOPPADDING", (0, 0), (-1, -1), 5),
                                    ("BOTTOMPADDING", (0, 0), (-1, -1), 5)]))
    el.append(health_tbl)

    el.append(Paragraph("2 &middot; Access Governance Coverage", h2))
    gov_rows = [["Metric", "Count"]] + [[k, str(v)] for k, v in stats.items()]
    gov_tbl = Table(gov_rows, colWidths=[None, 30 * mm])
    gov_tbl.setStyle(TableStyle([("FONTSIZE", (0, 0), (-1, -1), 9.5),
                                 ("BACKGROUND", (0, 0), (-1, 0), NAVY),
                                 ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                                 ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                                 ("GRID", (0, 0), (-1, -1), 0.4, GRID),
                                 ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                                 ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f9fafb")]),
                                 ("TOPPADDING", (0, 0), (-1, -1), 5),
                                 ("BOTTOMPADDING", (0, 0), (-1, -1), 5)]))
    el.append(gov_tbl)

    el.append(Paragraph("3 &middot; Attestation", h2))
    el.append(Paragraph(
        "This report is generated directly from the live Obserra SAP UAC control plane at the timestamp above. "
        "It reflects the operational state of segregation-of-duties, access certification, backup and "
        "at-rest encryption controls for the named organization. All figures are computed from the current "
        "data snapshot and are not editable after generation.", body))
    el.append(Spacer(1, 8))

    fingerprint = hashlib.sha256(
        f"{org_name}|{generated_by}|{generated_at.isoformat()}|{version}|{status}|{backup_count}|{stats}"
        .encode("utf-8")).hexdigest()
    el.append(HRFlowable(width="100%", thickness=0.8, color=GRID, spaceAfter=6))
    if verify_url:
        from reportlab.graphics.barcode import qr
        from reportlab.graphics.shapes import Drawing
        _w = qr.QrCodeWidget(verify_url)
        _b = _w.getBounds()
        _sz = 62
        _d = Drawing(_sz, _sz, transform=[_sz / (_b[2] - _b[0]), 0, 0, _sz / (_b[3] - _b[1]), 0, 0])
        _d.add(_w)
        verify_cell = Paragraph(
            "<b>Verify this document</b><br/>Scan the code or visit the link below to confirm this report's "
            f"authenticity and its expected SHA-256 fingerprint.<br/><font size=7 color='#2f6df6'>{verify_url}</font>", small)
        qr_tbl = Table([[_d, verify_cell]], colWidths=[70, None])
        qr_tbl.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                                    ("LEFTPADDING", (0, 0), (0, 0), 0),
                                    ("TOPPADDING", (0, 0), (-1, -1), 2),
                                    ("BOTTOMPADDING", (0, 0), (-1, -1), 2)]))
        el.append(qr_tbl)
        el.append(Spacer(1, 4))
    el.append(Paragraph(f"Document integrity signature (SHA-256): {fingerprint}", small))
    el.append(Paragraph("Obserra SAP UAC &middot; Enterprise SAP Access Governance &middot; Confidential", small))

    doc.build(el)
    return buf.getvalue()


def _resolve_period(period: dict = None):
    """Return (label, start_iso, end_iso) for a reporting-period selector."""
    from datetime import datetime, timezone, timedelta
    now = datetime.now(timezone.utc)
    period = period or {}
    kind = period.get("kind") or "current"
    MONTHS = ["", "January", "February", "March", "April", "May", "June",
              "July", "August", "September", "October", "November", "December"]
    try:
        if kind == "month" and period.get("value"):
            y, m = [int(x) for x in str(period["value"]).split("-")[:2]]
            start = datetime(y, m, 1, tzinfo=timezone.utc)
            end = datetime(y + (m // 12), (m % 12) + 1, 1, tzinfo=timezone.utc)
            return f"{MONTHS[m]} {y}", start.isoformat(), end.isoformat()
        if kind == "quarter" and period.get("value"):
            y_s, q_s = str(period["value"]).upper().split("-Q")
            y, q = int(y_s), int(q_s)
            sm = (q - 1) * 3 + 1
            start = datetime(y, sm, 1, tzinfo=timezone.utc)
            em = sm + 3
            end = datetime(y + (1 if em > 12 else 0), ((em - 1) % 12) + 1, 1, tzinfo=timezone.utc)
            return f"Q{q} {y}", start.isoformat(), end.isoformat()
    except Exception:
        pass
    return (f"Current snapshot (as of {now.date().isoformat()})",
            (now - timedelta(days=30)).isoformat(), now.isoformat())


async def _period_uptime(org_id: str, start_iso: str, end_iso: str):
    q = {"org_id": org_id, "at": {"$gte": start_iso, "$lt": end_iso}}
    total = await db.health_history.count_documents(q)
    if not total:
        return None
    healthy = await db.health_history.count_documents({**q, "healthy": True})
    return round(healthy / total * 100, 1)


async def _generate_compliance_pdf(org_id: str, generated_by: str, period: dict = None,
                                   verify_url: str = None) -> bytes:
    """Gather live control-plane state for one org and render the compliance PDF (shared by the
    ad-hoc download, the Evidence Locker and the monthly cron)."""
    from bson import ObjectId
    from starlette.concurrency import run_in_threadpool
    org = await db.organizations.find_one({"_id": ObjectId(org_id)}) or {}
    org_name = org.get("name") or "Organization"
    health = await evaluate_org_health(org_id)
    enc = _enc_cfg(org)
    bcfg = _backup_cfg(org)
    backups = _list_backup_files(org_id)
    latest_backup = backups[0]["created_at"] if backups else None
    stats = {}
    for label, coll in [("Identities (HR persons)", "sap_persons"),
                        ("SAP accounts", "sap_accounts"),
                        ("SoD mitigations", "sap_mitigations"),
                        ("Access certifications", "sap_certifications"),
                        ("ServiceNow tickets", "sap_snow_tickets"),
                        ("Watchlist items", "sap_watchlist"),
                        ("Auto-remediation actions", "sap_autoremediation_log")]:
        stats[label] = await db[coll].count_documents({"org_id": org_id})
    period_label, start_iso, end_iso = _resolve_period(period)
    period_uptime = await _period_uptime(org_id, start_iso, end_iso)
    return await run_in_threadpool(_build_compliance_pdf, org_name, generated_by,
                                   onprem_pack.read_version(), health, enc, bcfg,
                                   len(backups), latest_backup, stats,
                                   period_label, period_uptime, verify_url)


@deploy_router.get("/compliance-evidence")
async def compliance_evidence(user: dict = Depends(get_current_user)):
    """Ad-hoc download of a signed compliance-evidence PDF (admins only)."""
    if user.get("role") != "admin":
        raise HTTPException(403, "Only admins can export compliance evidence")
    from datetime import datetime, timezone
    pdf = await _generate_compliance_pdf(user["org_id"], user["email"])
    fname = f"Obserra-Compliance-Evidence-{datetime.now(timezone.utc).date().isoformat()}.pdf"
    return StreamingResponse(io.BytesIO(pdf), media_type=_PDF_MT,
                             headers={"Content-Disposition": f'attachment; filename="{fname}"'})


# --- Evidence Locker: archive generated compliance PDFs on disk (org-scoped, auditor self-serve) ---
_EVIDENCE_DIR = os.environ.get("EVIDENCE_DIR", os.path.join(_ROOT, "evidence"))


def _safe_evidence_path(filename: str) -> str:
    name = os.path.basename(filename or "")
    if not name.endswith(".pdf") or name != (filename or ""):
        raise HTTPException(400, "Invalid evidence filename")
    return os.path.join(_EVIDENCE_DIR, name)


def _archive_evidence(org_id: str, pdf: bytes, generated_by: str, source: str,
                      period_label: str = "Current snapshot", verify_token: str = None) -> dict:
    import json
    import uuid
    import hashlib
    os.makedirs(_EVIDENCE_DIR, exist_ok=True)
    stamp = _now_iso().replace(":", "").replace("-", "").replace("T", "").replace(".", "").replace("+", "")[:20]
    fname = f"obserra-evidence-{org_id}-{stamp}-{uuid.uuid4().hex[:6]}.pdf"
    fp = os.path.join(_EVIDENCE_DIR, fname)
    with open(fp, "wb") as f:
        f.write(pdf)
    meta = {"file": fname, "org_id": org_id, "created_at": _now_iso(), "generated_by": generated_by,
            "source": source, "size": len(pdf), "sha256": hashlib.sha256(pdf).hexdigest(),
            "period_label": period_label, "verify_token": verify_token}
    with open(fp + ".meta.json", "w", encoding="utf-8") as f:
        json.dump(meta, f)
    return meta


def _list_evidence_files(org_id: str):
    import json
    if not os.path.isdir(_EVIDENCE_DIR):
        return []
    out = []
    for fn in os.listdir(_EVIDENCE_DIR):
        if fn.startswith(f"obserra-evidence-{org_id}-") and fn.endswith(".pdf"):
            fp = os.path.join(_EVIDENCE_DIR, fn)
            info = {"file": fn, "size": os.path.getsize(fp), "created_at": _iso_from_mtime(fp),
                    "generated_by": None, "source": None, "sha256": None,
                    "period_label": None, "verify_token": None}
            mp = fp + ".meta.json"
            if os.path.exists(mp):
                try:
                    with open(mp, encoding="utf-8") as f:
                        m = json.load(f)
                    info.update(created_at=m.get("created_at", info["created_at"]),
                                generated_by=m.get("generated_by"), source=m.get("source"),
                                sha256=m.get("sha256"), period_label=m.get("period_label"),
                                verify_token=m.get("verify_token"))
                except Exception:
                    pass
            out.append(info)
    return sorted(out, key=lambda x: x["created_at"], reverse=True)


def _prune_evidence(org_id: str, keep: int = 60):
    for old in _list_evidence_files(org_id)[keep:]:
        for p in (os.path.join(_EVIDENCE_DIR, old["file"]), os.path.join(_EVIDENCE_DIR, old["file"] + ".meta.json")):
            try:
                os.remove(p)
            except Exception:
                pass


def _evidence_cfg(org):
    c = ((org or {}).get("system_health") or {}).get("evidence") or {}
    return {"monthly_email": bool(c.get("monthly_email", True)),
            "keep": max(1, min(365, int(c.get("keep") or 60))),
            "quarterly_pack": bool(c.get("quarterly_pack", True))}


async def _make_and_archive_evidence(org_id: str, generated_by: str, source: str, period: dict = None):
    """Generate a QR-verifiable compliance PDF, archive it, bind a verify token to its hash, prune."""
    import secrets
    from bson import ObjectId
    frontend = os.environ.get("FRONTEND_URL", "").rstrip("/")
    token = secrets.token_urlsafe(12)
    verify_url = f"{frontend}/api/deploy/evidence/verify/{token}"
    period_label, _s, _e = _resolve_period(period)
    pdf = await _generate_compliance_pdf(org_id, generated_by, period=period, verify_url=verify_url)
    meta = _archive_evidence(org_id, pdf, generated_by, source, period_label=period_label, verify_token=token)
    await db.evidence_verify.insert_one({
        "token": token, "org_id": org_id, "file": meta["file"], "sha256": meta["sha256"],
        "created_at": meta["created_at"], "generated_by": generated_by, "period_label": period_label})
    org = await db.organizations.find_one({"_id": ObjectId(org_id)}) or {}
    _prune_evidence(org_id, keep=_evidence_cfg(org)["keep"])
    return pdf, meta


class EvidenceGenerateBody(BaseModel):
    period: dict | None = None


@deploy_router.post("/evidence/generate")
async def evidence_generate(body: EvidenceGenerateBody | None = None, user: dict = Depends(get_current_user)):
    """Generate a QR-verifiable compliance PDF (optionally for a chosen period) and archive it."""
    if user.get("role") != "admin":
        raise HTTPException(403, "Admins only")
    period = body.period if body else None
    _pdf, meta = await _make_and_archive_evidence(user["org_id"], user["email"], "manual", period=period)
    return meta


@deploy_router.get("/evidence/list")
async def evidence_list(user: dict = Depends(get_current_user)):
    if user.get("role") != "admin":
        raise HTTPException(403, "Admins only")
    return {"evidence": _list_evidence_files(user["org_id"])}


@deploy_router.get("/evidence/download")
async def evidence_download(file: str, user: dict = Depends(get_current_user)):
    if user.get("role") != "admin":
        raise HTTPException(403, "Admins only")
    fp = _safe_evidence_path(file)
    if not os.path.exists(fp) or f"-{user['org_id']}-" not in file:
        raise HTTPException(404, "Evidence not found")
    with open(fp, "rb") as f:
        content = f.read()
    return StreamingResponse(io.BytesIO(content), media_type=_PDF_MT,
                             headers={"Content-Disposition": f'attachment; filename="{os.path.basename(fp)}"'})


class EvidenceConfig(BaseModel):
    monthly_email: bool = True
    keep: int = 60
    quarterly_pack: bool = True


@deploy_router.get("/evidence-config")
async def get_evidence_config(user: dict = Depends(get_current_user)):
    from bson import ObjectId
    org = await db.organizations.find_one({"_id": ObjectId(user["org_id"])}) or {}
    return _evidence_cfg(org)


@deploy_router.put("/evidence-config")
async def put_evidence_config(body: EvidenceConfig, user: dict = Depends(get_current_user)):
    if user.get("role") != "admin":
        raise HTTPException(403, "Admins only")
    from bson import ObjectId
    cfg = {"monthly_email": bool(body.monthly_email), "keep": max(1, min(365, int(body.keep))),
           "quarterly_pack": bool(body.quarterly_pack)}
    await db.organizations.update_one({"_id": ObjectId(user["org_id"])},
                                      {"$set": {"system_health.evidence": cfg}})
    return cfg


class EvidenceShareBody(BaseModel):
    file: str
    ttl_days: int = 7


@deploy_router.post("/evidence/share")
async def evidence_share(body: EvidenceShareBody, user: dict = Depends(get_current_user)):
    """Create a read-only, expiring public link to one archived evidence PDF (admins only)."""
    if user.get("role") != "admin":
        raise HTTPException(403, "Admins only")
    import secrets
    from datetime import datetime, timezone, timedelta
    fp = _safe_evidence_path(body.file)
    if not os.path.exists(fp) or f"-{user['org_id']}-" not in body.file:
        raise HTTPException(404, "Evidence not found")
    ttl = max(1, min(90, int(body.ttl_days)))
    token = secrets.token_urlsafe(16)
    expires = (datetime.now(timezone.utc) + timedelta(days=ttl)).isoformat()
    await db.evidence_shares.insert_one({"token": token, "org_id": user["org_id"], "file": body.file,
                                         "created_by": user["email"], "created_at": _now_iso(),
                                         "expires_at": expires, "opens": 0})
    frontend = os.environ.get("FRONTEND_URL", "").rstrip("/")
    return {"token": token, "url": f"{frontend}/api/deploy/evidence/shared/{token}",
            "expires_at": expires, "ttl_days": ttl}


def _watermark_pdf(pdf_bytes: bytes, text: str = "VERIFIED COPY", subtext: str = "") -> bytes:
    """Overlay a faint diagonal watermark on every page (used for shared / audit-room copies).
    Fails open: returns the original bytes if watermarking is unavailable."""
    try:
        from io import BytesIO
        from pypdf import PdfReader, PdfWriter
        from reportlab.pdfgen import canvas
        from reportlab.lib import colors
        reader = PdfReader(BytesIO(pdf_bytes))
        writer = PdfWriter()
        for page in reader.pages:
            w = float(page.mediabox.width)
            h = float(page.mediabox.height)
            buf = BytesIO()
            c = canvas.Canvas(buf, pagesize=(w, h))
            c.saveState()
            c.translate(w / 2, h / 2)
            c.rotate(38)
            c.setFillColor(colors.Color(0.55, 0.6, 0.72, alpha=0.13))
            c.setFont("Helvetica-Bold", 52)
            c.drawCentredString(0, 18, text)
            if subtext:
                c.setFont("Helvetica", 12)
                c.drawCentredString(0, -24, subtext)
            c.restoreState()
            c.save()
            buf.seek(0)
            page.merge_page(PdfReader(buf).pages[0])
            try:
                page.compress_content_streams()  # zlib-compress streams so the watermark doesn't bloat the download
            except Exception:
                pass
            writer.add_page(page)
        try:
            writer.compress_identical_objects(remove_identicals=True, remove_orphans=True)
        except Exception:
            pass
        out = BytesIO()
        writer.write(out)
        return out.getvalue()
    except Exception:
        return pdf_bytes


@deploy_router.get("/evidence/shared/{token}")
async def evidence_shared(token: str):
    """Public, unauthenticated read-only download of a shared evidence PDF."""
    from datetime import datetime, timezone
    doc = await db.evidence_shares.find_one({"token": token})
    if not doc:
        raise HTTPException(404, "This shared evidence link is invalid.")
    if doc.get("expires_at") and datetime.now(timezone.utc).isoformat() > doc["expires_at"]:
        raise HTTPException(410, "This shared evidence link has expired.")
    fp = _safe_evidence_path(doc["file"])
    if not os.path.exists(fp):
        raise HTTPException(410, "The shared evidence file is no longer available.")
    await db.evidence_shares.update_one({"token": token},
                                        {"$inc": {"opens": 1}, "$set": {"last_opened_at": _now_iso()}})
    with open(fp, "rb") as f:
        content = f.read()
    content = _watermark_pdf(content, "VERIFIED COPY",
                             f"Shared {doc.get('created_at', '')[:10]} · expires {doc.get('expires_at', '')[:10]}")
    return StreamingResponse(io.BytesIO(content), media_type=_PDF_MT,
                             headers={"Content-Disposition": f'inline; filename="{os.path.basename(fp)}"'})


def _verify_html(doc, exists=True):
    if not doc:
        inner = ('<h1>Verification failed</h1><p>This verification code is not recognised. The document may be '
                 'counterfeit or the link mistyped.</p>')
        badge = '#c2410c'
    elif not exists:
        inner = ('<h1>Record found — file no longer stored</h1><p>This report was genuinely issued by Obserra SAP UAC, '
                 f'but its archived copy has since rolled off retention.</p><p class="mono">Expected SHA-256: {doc.get("sha256")}</p>')
        badge = '#b45309'
    else:
        inner = ('<h1>&#10003; Authentic document</h1>'
                 '<p>This report was issued by the Obserra SAP UAC control plane. Confirm the copy you hold is '
                 'untampered by checking its SHA-256 fingerprint against the value below.</p>'
                 f'<table><tr><td>Organization</td><td>{doc.get("org_name") or doc.get("org_id")}</td></tr>'
                 f'<tr><td>Reporting period</td><td>{doc.get("period_label") or "—"}</td></tr>'
                 f'<tr><td>Issued (UTC)</td><td>{(doc.get("created_at") or "")[:19].replace("T", " ")}</td></tr>'
                 f'<tr><td>Issued by</td><td>{doc.get("generated_by") or "—"}</td></tr></table>'
                 f'<p class="mono">Expected SHA-256:<br>{doc.get("sha256")}</p>'
                 '<p class="hint">Run <code>shasum -a 256 &lt;file.pdf&gt;</code> (macOS/Linux) or '
                 '<code>certutil -hashfile &lt;file&gt; SHA256</code> (Windows) and compare.</p>')
        badge = '#12805c'
    return (f'<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            '<title>Obserra SAP UAC — Evidence Verification</title>'
            '<style>body{font:400 15px/1.6 -apple-system,Segoe UI,Arial;background:#0f1e3d;color:#e5e7eb;margin:0;padding:40px 16px}'
            f'.card{{max-width:640px;margin:auto;background:#fff;color:#111827;border-radius:16px;padding:32px 30px;border-top:6px solid {badge}}}'
            'h1{font-size:22px;margin:0 0 12px;color:#0f1e3d}'
            'table{width:100%;border-collapse:collapse;margin:14px 0}td{padding:7px 6px;border-bottom:1px solid #eee;font-size:14px}'
            'td:first-child{color:#6b7280;width:150px}.mono{font-family:ui-monospace,Menlo,Consolas,monospace;font-size:12px;'
            'word-break:break-all;background:#f4f6fb;padding:10px 12px;border-radius:8px;color:#0f1e3d}'
            '.hint{font-size:12px;color:#6b7280}code{background:#f4f6fb;padding:1px 5px;border-radius:4px}'
            '.brand{max-width:640px;margin:14px auto 0;text-align:center;color:#94a3b8;font-size:12px}</style></head>'
            f'<body><div class="card">{inner}</div><div class="brand">Obserra SAP UAC · Enterprise SAP Access Governance</div></body></html>')


@deploy_router.get("/evidence/verify/{token}")
async def evidence_verify(token: str):
    """Public verification page: confirms a report's authenticity + expected SHA-256."""
    from fastapi.responses import HTMLResponse
    from bson import ObjectId
    doc = await db.evidence_verify.find_one({"token": token}, {"_id": 0})
    if not doc:
        return HTMLResponse(_verify_html(None), status_code=404)
    org = await db.organizations.find_one({"_id": ObjectId(doc["org_id"])}) or {}
    doc["org_name"] = org.get("name")
    exists = os.path.exists(_safe_evidence_path(doc["file"]))
    return HTMLResponse(_verify_html(doc, exists))


@deploy_router.post("/health-digest-send")
async def health_digest_send(user: dict = Depends(get_current_user)):
    """Admin: send today's bundled health digest to Slack/Teams/email on demand (per routing)."""
    if user.get("role") != "admin":
        raise HTTPException(403, "Admins only")
    from datetime import datetime, timezone
    from bson import ObjectId
    from kernel import notifications
    org = await db.organizations.find_one({"_id": ObjectId(user["org_id"])}) or {}
    h = await evaluate_org_health(user["org_id"])
    if h["healthy"]:
        return {"sent": False, "reason": "healthy"}
    routing = _alert_cfg(org)
    sent = []
    for ch in ("slack", "teams", "email"):
        evs = [msg for etype, msg in h.get("issue_types", []) if routing.get(etype, {}).get(ch)]
        if not evs:
            continue
        body = "System health digest (sent on demand):\n- " + "\n- ".join(evs) + "\n\nOpen System Health to review."
        await _route_alert(org, {ch: True}, "⚠ System health digest", body)
        sent.append(ch)
    await db.organizations.update_one({"_id": ObjectId(user["org_id"])},
                                      {"$set": {"system_health.last_digest_date": datetime.now(timezone.utc).date().isoformat()}})
    await notifications.create(user["org_id"], "system", "System health digest sent", " · ".join(h["issues"]), ref="system-health")
    return {"sent": True, "channels": sent}


async def _run_monthly_evidence_email():
    """Monthly (1st): generate + archive each org's compliance evidence PDF and email it to
    admins/execs + saved IT/audit recipients. Folded into the monthly-board-report cron."""
    import base64
    import logging
    from kernel import notifications
    orgs = await db.organizations.find({}).to_list(1000)
    for org in orgs:
        oid = str(org["_id"])
        cfg = (org.get("system_health") or {}).get("evidence") or {}
        if cfg.get("monthly_email") is False:
            continue
        try:
            pdf = await _generate_compliance_pdf(oid, "scheduler@obserra")
            meta = _archive_evidence(oid, pdf, "scheduler@obserra", "monthly-cron")
            _prune_evidence(oid)
            recips = await db.users.find({"org_id": oid, "role": {"$in": ["admin", "executive"]}},
                                         {"_id": 0, "email": 1}).to_list(200)
            emails = {r["email"] for r in recips}
            emails |= {e for e in (org.get("deploy_recipients") or []) if e}
            if not emails:
                continue
            html = ("<div style='font:400 14px Arial;color:#1f2937;max-width:560px;margin:auto'>"
                    "<h2 style='color:#0f1e3d'>Monthly SAP Access Compliance Evidence</h2>"
                    "<p>Attached is this month's signed compliance-evidence report for your SAP "
                    "User Access Control platform — system health &amp; controls, access-governance "
                    "coverage, backup/encryption posture, and a document-integrity signature.</p>"
                    "<p style='font-size:11px;color:#9ca3af'>Obserra SAP UAC — Enterprise SAP Access Governance</p></div>")
            attachments = [{"filename": f"Obserra-Compliance-Evidence-{meta['created_at'][:10]}.pdf",
                            "content": base64.b64encode(pdf).decode()}]
            for to in emails:
                await notifications.send_email(to, "Monthly SAP Access Compliance Evidence — Obserra SAP UAC",
                                               html, attachments=attachments)
            await notifications.create(oid, "report", "Monthly compliance evidence delivered",
                                       f"Signed evidence PDF archived to the Evidence Locker and emailed to {len(emails)} recipient(s).",
                                       ref="compliance-evidence")
        except Exception as e:
            logging.getLogger("deploy").warning(f"monthly evidence email failed for org {oid}: {e}")


async def _run_quarterly_evidence_pack():
    """On the 1st of a quarter-start month (Jan/Apr/Jul/Oct), email each org a signed evidence pack
    for the just-ended quarter. Folded into the monthly-board-report cron."""
    import base64
    import logging
    from datetime import datetime, timezone
    from kernel import notifications
    now = datetime.now(timezone.utc)
    if now.month not in (1, 4, 7, 10):
        return
    pq_month, pq_year = now.month - 3, now.year
    if pq_month <= 0:
        pq_month += 12
        pq_year -= 1
    pq = (pq_month - 1) // 3 + 1
    period = {"kind": "quarter", "value": f"{pq_year}-Q{pq}"}
    for org in await db.organizations.find({}).to_list(1000):
        oid = str(org["_id"])
        if not _evidence_cfg(org).get("quarterly_pack", True):
            continue
        try:
            pdf, meta = await _make_and_archive_evidence(oid, "scheduler@obserra", "quarterly-cron", period=period)
            recips = await db.users.find({"org_id": oid, "role": {"$in": ["admin", "executive"]}}, {"_id": 0, "email": 1}).to_list(200)
            emails = {r["email"] for r in recips} | {e for e in (org.get("deploy_recipients") or []) if e}
            if not emails:
                continue
            html = ("<div style='font:400 14px Arial;color:#1f2937;max-width:560px;margin:auto'>"
                    f"<h2 style='color:#0f1e3d'>Quarter-End SAP Access Compliance Pack — {period['value']}</h2>"
                    "<p>Attached is the signed compliance-evidence pack for the just-ended quarter, covering system "
                    "health &amp; controls, access-governance coverage, quarter uptime, backup/encryption posture and a "
                    "document-integrity signature with a QR verification link.</p>"
                    "<p style='font-size:11px;color:#9ca3af'>Obserra SAP UAC — Enterprise SAP Access Governance</p></div>")
            attachments = [{"filename": f"Obserra-Quarter-End-{period['value']}.pdf", "content": base64.b64encode(pdf).decode()}]
            for to in emails:
                await notifications.send_email(to, f"Quarter-End SAP Access Compliance Pack — {period['value']}", html, attachments=attachments)
            await notifications.create(oid, "report", "Quarterly compliance pack delivered",
                                       f"Signed {period['value']} evidence archived and emailed to {len(emails)} recipient(s).", ref="compliance-evidence")
        except Exception as e:
            logging.getLogger("deploy").warning(f"quarterly pack failed for org {oid}: {e}")


class DigestTestEmail(BaseModel):
    email: str


@deploy_router.post("/health-digest-test-email")
async def health_digest_test_email(body: DigestTestEmail, user: dict = Depends(get_current_user)):
    """Send a one-off health digest to a single email so admins can preview it before wiring a channel."""
    if user.get("role") != "admin":
        raise HTTPException(403, "Admins only")
    from kernel import notifications
    email = (body.email or "").strip()
    if "@" not in email or "." not in email.split("@")[-1]:
        raise HTTPException(400, "Enter a valid email address.")
    h = await evaluate_org_health(user["org_id"])
    lines = (h.get("issues") or []) if not h["healthy"] else \
        ["All monitored systems are healthy — this is a sample digest so you can preview the format."]
    html = ("<div style='font:400 14px Arial;color:#1f2937;max-width:560px;margin:auto'>"
            "<h2 style='color:#0f1e3d'>System Health Digest (test)</h2><ul>"
            + "".join(f"<li>{ln}</li>" for ln in lines)
            + "</ul><p style='font-size:11px;color:#9ca3af'>Sent as a one-off test from Obserra SAP UAC — no channel was changed.</p></div>")
    await notifications.send_email(email, "System Health Digest (test) — Obserra SAP UAC", html)
    return {"email": email, "healthy": h["healthy"]}


class TokenBody(BaseModel):
    token: str


@deploy_router.get("/evidence/shares")
async def evidence_shares_list(user: dict = Depends(get_current_user)):
    if user.get("role") != "admin":
        raise HTTPException(403, "Admins only")
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()
    frontend = os.environ.get("FRONTEND_URL", "").rstrip("/")
    rows = await db.evidence_shares.find({"org_id": user["org_id"]}, {"_id": 0}).sort("created_at", -1).to_list(100)
    for r in rows:
        r["expired"] = bool(r.get("expires_at") and now > r["expires_at"])
        r["url"] = f"{frontend}/api/deploy/evidence/shared/{r['token']}"
    return {"shares": rows}


@deploy_router.post("/evidence/share/revoke")
async def evidence_share_revoke(body: TokenBody, user: dict = Depends(get_current_user)):
    if user.get("role") != "admin":
        raise HTTPException(403, "Admins only")
    res = await db.evidence_shares.delete_one({"token": body.token, "org_id": user["org_id"]})
    return {"revoked": res.deleted_count > 0}


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
            attachments.append({"filename": "Obserra-Control-Intelligence-Install-and-User-Guide.pdf",
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


# Auditor-governance routes/helpers live in deploy_audit (registers on deploy_router).
from deploy_audit import (  # noqa: E402,F401
    _run_audit_room_expiry_reminders,
    _run_overdue_request_digest,
    _run_weekly_escalation_rollup,
)
