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
    payload = _read_backup(user["org_id"], body.get("file", ""), passphrase=body.get("passphrase"))
    cols = payload.get("collections", {})
    rows, total_backup, total_current = [], 0, 0
    for name, docs in cols.items():
        bcount = len(docs or [])
        ccount = await db[name].count_documents({"org_id": user["org_id"]})
        rows.append({"collection": name, "current": ccount, "backup": bcount, "delta": bcount - ccount})
        total_backup += bcount
        total_current += ccount
    rows.sort(key=lambda r: (abs(r["delta"]), r["backup"]), reverse=True)
    return {"rows": rows, "collections": len(cols),
            "total_backup": total_backup, "total_current": total_current}


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


def _build_compliance_pdf(org_name, generated_by, version, health, enc, bcfg, backup_count, latest_backup, stats):
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
                        ["At-rest encryption", "Enabled (AES / Fernet)" if enc.get("enabled") else "Disabled"]],
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
    el.append(Paragraph(f"Document integrity signature (SHA-256): {fingerprint}", small))
    el.append(Paragraph("Obserra SAP UAC &middot; Enterprise SAP Access Governance &middot; Confidential", small))

    doc.build(el)
    return buf.getvalue()


@deploy_router.get("/compliance-evidence")
async def compliance_evidence(user: dict = Depends(get_current_user)):
    """Downloadable, signed compliance-evidence PDF for auditors (admins only)."""
    if user.get("role") != "admin":
        raise HTTPException(403, "Only admins can export compliance evidence")
    from datetime import datetime, timezone
    from bson import ObjectId
    from starlette.concurrency import run_in_threadpool
    org = await db.organizations.find_one({"_id": ObjectId(user["org_id"])}) or {}
    org_name = org.get("name") or "Organization"
    health = await evaluate_org_health(user["org_id"])
    enc = _enc_cfg(org)
    bcfg = _backup_cfg(org)
    backups = _list_backup_files(user["org_id"])
    latest_backup = backups[0]["created_at"] if backups else None
    stats = {}
    for label, coll in [("Identities (HR persons)", "sap_persons"),
                        ("SAP accounts", "sap_accounts"),
                        ("SoD mitigations", "sap_mitigations"),
                        ("Access certifications", "sap_certifications"),
                        ("ServiceNow tickets", "sap_snow_tickets"),
                        ("Watchlist items", "sap_watchlist"),
                        ("Auto-remediation actions", "sap_autoremediation_log")]:
        stats[label] = await db[coll].count_documents({"org_id": user["org_id"]})
    pdf = await run_in_threadpool(_build_compliance_pdf, org_name, user["email"],
                                  onprem_pack.read_version(), health, enc, bcfg,
                                  len(backups), latest_backup, stats)
    fname = f"Obserra-Compliance-Evidence-{datetime.now(timezone.utc).date().isoformat()}.pdf"
    return StreamingResponse(io.BytesIO(pdf), media_type=_PDF_MT,
                             headers={"Content-Disposition": f'attachment; filename="{fname}"'})


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
