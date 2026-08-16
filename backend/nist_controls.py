import os
import json
from fastapi import APIRouter, HTTPException, Request, Depends
from pydantic import BaseModel

from db import db
from auth import require_roles, get_current_user, _log_audit

nist_router = APIRouter(prefix="/api/nist")


class ControlIn(BaseModel):
    id: str
    title: str
    family: str | None = None
    description: str | None = None
    keywords: list[str] | None = None


@nist_router.post("/import")
async def import_controls(body: dict | None = None, request: Request = None, admin: dict = Depends(require_roles("admin"))):
    """Import NIST controls. Accepts JSON body (list of control objects) or will attempt to load
    deploy/onprem/nist_controls.json from disk when no body provided. Admin only."""
    data = None
    if body:
        data = body
    else:
        # try common deploy path
        path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "deploy", "onprem", "nist_controls.json")
        if not os.path.exists(path):
            path = os.path.join(os.path.dirname(__file__), "nist_controls.json")
        if not os.path.exists(path):
            raise HTTPException(status_code=400, detail="No controls provided and no deploy/onprem/nist_controls.json found. POST JSON payload or place file at deploy/onprem/nist_controls.json")
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed reading controls file: {e}")

    if not isinstance(data, list):
        raise HTTPException(status_code=400, detail="Controls payload must be a JSON array")

    docs = []
    for c in data:
        try:
            ctrl = {
                "id": str(c.get("id") or c.get("control_id") or c.get("controlId") or c.get("number") or ""),
                "title": c.get("title") or c.get("name") or "",
                "family": c.get("family") or c.get("class") or c.get("family") or "",
                "description": c.get("description") or c.get("text") or "",
                "keywords": c.get("keywords") or c.get("tags") or [],
            }
        except Exception:
            continue
        docs.append(ctrl)

    if not docs:
        raise HTTPException(status_code=400, detail="No valid controls found in payload")

    # upsert by id
    ops = []
    for d in docs:
        await db.nist_controls.update_one({"id": d["id"]}, {"$set": d}, upsert=True)

    await _log_audit(admin["org_id"], admin["email"], "nist.import", f"Imported {len(docs)} NIST controls")
    return {"imported": len(docs)}


@nist_router.get("/controls")
async def list_controls(user: dict = Depends(get_current_user)):
    docs = await db.nist_controls.find({}, {"_id": 0}).to_list(1000)
    return {"controls": docs}


@nist_router.post("/map/{org_id}")
async def map_controls(org_id: str, admin: dict = Depends(require_roles("admin"))):
    """Compute mapping of NIST controls to organization evidence and return compliance score.
    This is a heuristic mapping: for each control, check if organization's health components,
    connectors or risks contain keywords matching control keywords or family."""
    from bson import ObjectId

    # load controls
    controls = await db.nist_controls.find({}, {"_id": 0}).to_list(5000)
    if not controls:
        raise HTTPException(status_code=404, detail="No NIST controls imported")

    # fetch org artifacts
    org = await db.organizations.find_one({"_id": ObjectId(org_id)})
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    health = await db.health_index.find_one({"org_id": org_id}) or {}
    connectors = await db.connectors.find({"org_id": org_id}).to_list(200)
    risks = await db.risks.find({"org_id": org_id}).to_list(500)
    evidence_docs = await db.connector_evidence.find({"org_id": org_id}).to_list(200)

    # prepare searchable text
    health_text = " ".join([c.get("name", "") + " " + str(c.get("score", "")) for c in (health.get("components") or [])])
    connector_text_parts = [c.get("name", "") + " " + c.get("type", "") for c in connectors]
    # include deterministic connector evidence text
    for e in evidence_docs:
        try:
            ev = e.get("evidence") or {}
            # summarize evidence details into text
            details = ev.get("details") or []
            for d in details:
                if isinstance(d, dict):
                    connector_text_parts.append(" ".join([str(v) for v in d.values() if v]))
                else:
                    connector_text_parts.append(str(d))
        except Exception:
            pass
    connector_text = " ".join(connector_text_parts)
    risks_text = " ".join([r.get("title", "") + " " + r.get("category", "") for r in risks])

    matched = []
    family_counts: dict = {}
    for c in controls:
        kws = [k.lower() for k in (c.get("keywords") or []) if isinstance(k, str)]
        title = (c.get("title") or "").lower()
        fam = (c.get("family") or "").upper()
        satisfied = False
        # simple heuristics
        for kw in kws + [title, fam.lower()]:
            if not kw:
                continue
            if kw in health_text.lower() or kw in connector_text.lower() or kw in risks_text.lower():
                satisfied = True
                break
        matched.append({"id": c.get("id"), "title": c.get("title"), "family": fam, "satisfied": satisfied})
        family_counts[fam] = family_counts.get(fam, {"total": 0, "satisfied": 0})
        family_counts[fam]["total"] += 1
        if satisfied:
            family_counts[fam]["satisfied"] += 1

    total = len(matched)
    sat = sum(1 for m in matched if m.get("satisfied"))
    score = round((sat / total) * 100, 1) if total else 0.0

    result = {"org_id": org_id, "score_percent": score, "total_controls": total, "satisfied": sat, "by_family": family_counts, "mapping": matched}

    # store a snapshot for org
    await db.control_mappings.update_one({"org_id": org_id}, {"$set": {"last_mapping": result}}, upsert=True)
    await _log_audit(admin["org_id"], admin["email"], "nist.map", f"Computed NIST mapping for org {org_id} — score {score}%")
    return result


@nist_router.post("/import-remote")
async def import_remote(body: dict | None = None, admin: dict = Depends(require_roles("admin"))):
    """Admin endpoint: fetch NIST controls and EU CRA requirements from URLs and import them.
    Body example: { "nist_url": "https://.../nist.json", "cra_url": "https://.../eu_cra.json" }
    If urls are omitted, attempts to read deploy/onprem/nist_controls.json and deploy/onprem/eu_cra_requirements.json.
    """
    import httpx
    base_dir = os.path.dirname(os.path.dirname(__file__))
    nist_url = (body or {}).get("nist_url") if body else None
    cra_url = (body or {}).get("cra_url") if body else None
    nist_data = None
    cra_data = None
    # try fetch or local file for NIST
    try:
        if nist_url:
            async with httpx.AsyncClient(timeout=30) as c:
                r = await c.get(nist_url)
                r.raise_for_status()
                nist_data = r.json()
        else:
            path = os.path.join(base_dir, "deploy", "onprem", "nist_controls.json")
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    nist_data = json.load(f)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to load NIST data: {e}")

    try:
        if cra_url:
            async with httpx.AsyncClient(timeout=30) as c:
                r = await c.get(cra_url)
                r.raise_for_status()
                cra_data = r.json()
        else:
            path = os.path.join(base_dir, "deploy", "onprem", "eu_cra_requirements.json")
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    cra_data = json.load(f)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to load EU CRA data: {e}")

    imported = {"nist": 0, "cra": 0}
    if nist_data:
        if isinstance(nist_data, dict) and nist_data.get("controls"):
            nlist = nist_data.get("controls")
        else:
            nlist = nist_data
        for c in nlist:
            doc = {
                "id": str(c.get("id") or c.get("controlId") or c.get("number") or ""),
                "title": c.get("title") or c.get("name") or "",
                "family": c.get("family") or c.get("class") or "",
                "description": c.get("description") or c.get("text") or "",
                "keywords": c.get("keywords") or c.get("tags") or [],
            }
            if doc["id"]:
                await db.nist_controls.update_one({"id": doc["id"]}, {"$set": doc}, upsert=True)
                imported["nist"] += 1

    if cra_data:
        # persist list into eu_cra_requirements collection
        if isinstance(cra_data, dict) and cra_data.get("requirements"):
            clist = cra_data.get("requirements")
        else:
            clist = cra_data
        await db.eu_cra_requirements.delete_many({})
        if isinstance(clist, list):
            for r in clist:
                await db.eu_cra_requirements.insert_one(r)
                imported["cra"] += 1

    await _log_audit(admin["org_id"], admin["email"], "nist.import_remote", f"Imported NIST {imported['nist']} controls and CRA {imported['cra']} requirements")
    return {"imported": imported}


@nist_router.post("/import-local")
async def import_local(body: dict | None = None, admin: dict = Depends(require_roles("admin"))):
    """Admin endpoint: import NIST and EU CRA from a local repository path.
    Body example: { "repo_root": "C:\\path\\to\\repo" }
    If repo_root omitted, falls back to the current repository directory detected by __file__ parents.
    """
    repo_root = (body or {}).get("repo_root") if body else None
    if not repo_root:
        # default: two levels up from this file (repo root in our workspace)
        repo_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    # candidate file locations
    nist_candidates = [
        os.path.join(repo_root, "sp800_53_rev5.json"),
        os.path.join(repo_root, "sp800-53-rev5.json"),
        os.path.join(repo_root, "deploy", "onprem", "nist_controls.json"),
        os.path.join(repo_root, "deploy", "onprem", "sp800_53_rev5.json"),
    ]
    cra_candidates = [
        os.path.join(repo_root, "eu_cra_requirements.json"),
        os.path.join(repo_root, "deploy", "onprem", "eu_cra_requirements.json"),
    ]

    nist_data = None
    cra_data = None
    for p in nist_candidates:
        if os.path.exists(p):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    nist_data = json.load(f)
                break
            except Exception:
                continue
    for p in cra_candidates:
        if os.path.exists(p):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    cra_data = json.load(f)
                break
            except Exception:
                continue

    if not nist_data and not cra_data:
        raise HTTPException(status_code=404, detail=f"No NIST or EU CRA files found in {repo_root}; checked candidate paths.")

    imported = {"nist": 0, "cra": 0}
    if nist_data:
        if isinstance(nist_data, dict) and nist_data.get("controls"):
            nlist = nist_data.get("controls")
        else:
            nlist = nist_data
        for c in nlist:
            doc = {
                "id": str(c.get("id") or c.get("controlId") or c.get("number") or c.get("identifier") or ""),
                "title": c.get("title") or c.get("name") or "",
                "family": c.get("family") or c.get("class") or "",
                "description": c.get("description") or c.get("text") or "",
                "keywords": c.get("keywords") or c.get("tags") or [],
            }
            if doc["id"]:
                await db.nist_controls.update_one({"id": doc["id"]}, {"$set": doc}, upsert=True)
                imported["nist"] += 1

    if cra_data:
        if isinstance(cra_data, dict) and cra_data.get("requirements"):
            clist = cra_data.get("requirements")
        else:
            clist = cra_data
        await db.eu_cra_requirements.delete_many({})
        if isinstance(clist, list):
            for r in clist:
                await db.eu_cra_requirements.insert_one(r)
                imported["cra"] += 1

    await _log_audit(admin["org_id"], admin["email"], "nist.import_local", f"Imported from local repo {repo_root}: NIST {imported['nist']} CRA {imported['cra']}")
    return {"imported": imported, "repo_root": repo_root}


@nist_router.post("/auto-import")
async def auto_import(admin: dict = Depends(require_roles("admin"))):
    """Attempt to fetch canonical NIST SP 800-53 Rev.5 and EU CRA requirements
    from a set of known public mirrors. If remote fetches fail, fall back to
    the packaged files under deploy/onprem/. Saves any downloaded files into
    deploy/onprem/ and imports them into the DB collections.
    """
    import httpx
    repo_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    deploy_dir = os.path.join(repo_root, "deploy", "onprem")
    os.makedirs(deploy_dir, exist_ok=True)

    nist_candidates = [
        # common raw GitHub or mirror locations (best-effort)
        "https://raw.githubusercontent.com/usnistgov/800-53-rev5/main/controls.json",
        "https://raw.githubusercontent.com/usnistgov/800-53-rev5/main/sp800_53_rev5.json",
        "https://raw.githubusercontent.com/usnistgov/800-53/main/sp800-53-rev5.json",
        "https://raw.githubusercontent.com/18F/cybersecurity-controls/master/sp800-53/rev5/sp800_53_r5.json",
    ]
    cra_candidates = [
        # no canonical public eu cra json known; attempt common paths used by projects
        "https://raw.githubusercontent.com/org/eu-cra/main/eu_cra_requirements.json",
        "https://raw.githubusercontent.com/obserra/eu-cra/main/eu_cra_requirements.json",
    ]

    fetched_nist = None
    fetched_cra = None
    async with httpx.AsyncClient(timeout=30) as client:
        for u in nist_candidates:
            try:
                r = await client.get(u)
                if r.status_code == 200:
                    try:
                        j = r.json()
                        # heuristics: accept if list or dict containing controls
                        if isinstance(j, list) or (isinstance(j, dict) and (j.get("controls") or j.get("controls"))):
                            fetched_nist = j
                            outn = os.path.join(deploy_dir, "sp800_53_rev5.json")
                            with open(outn, "w", encoding="utf-8") as f:
                                json.dump(j, f, ensure_ascii=False, indent=2)
                            break
                    except Exception:
                        continue
            except Exception:
                continue

        for u in cra_candidates:
            try:
                r = await client.get(u)
                if r.status_code == 200:
                    try:
                        j = r.json()
                        if isinstance(j, list) or isinstance(j, dict):
                            fetched_cra = j
                            outc = os.path.join(deploy_dir, "eu_cra_requirements.json")
                            with open(outc, "w", encoding="utf-8") as f:
                                json.dump(j, f, ensure_ascii=False, indent=2)
                            break
                    except Exception:
                        continue
            except Exception:
                continue

    # If nothing fetched, fall back to packaged samples
    if not fetched_nist:
        local_n = os.path.join(deploy_dir, "nist_controls.json")
        if os.path.exists(local_n):
            with open(local_n, "r", encoding="utf-8") as f:
                try:
                    fetched_nist = json.load(f)
                except Exception:
                    fetched_nist = None

    if not fetched_cra:
        local_c = os.path.join(deploy_dir, "eu_cra_requirements.json")
        if os.path.exists(local_c):
            with open(local_c, "r", encoding="utf-8") as f:
                try:
                    fetched_cra = json.load(f)
                except Exception:
                    fetched_cra = None

    imported = {"nist": 0, "cra": 0}
    if fetched_nist:
        if isinstance(fetched_nist, dict) and fetched_nist.get("controls"):
            nlist = fetched_nist.get("controls")
        else:
            nlist = fetched_nist
        for c in nlist:
            doc = {
                "id": str(c.get("id") or c.get("controlId") or c.get("number") or c.get("identifier") or ""),
                "title": c.get("title") or c.get("name") or "",
                "family": c.get("family") or c.get("class") or "",
                "description": c.get("description") or c.get("text") or "",
                "keywords": c.get("keywords") or c.get("tags") or [],
            }
            if doc["id"]:
                await db.nist_controls.update_one({"id": doc["id"]}, {"$set": doc}, upsert=True)
                imported["nist"] += 1

    if fetched_cra:
        if isinstance(fetched_cra, dict) and fetched_cra.get("requirements"):
            clist = fetched_cra.get("requirements")
        else:
            clist = fetched_cra
        # refresh collection
        await db.eu_cra_requirements.delete_many({})
        if isinstance(clist, list):
            for r in clist:
                await db.eu_cra_requirements.insert_one(r)
                imported["cra"] += 1

    await _log_audit(admin["org_id"], admin["email"], "nist.auto_import", f"Auto-import NIST {imported['nist']} CRA {imported['cra']}")
    return {"imported": imported}


async def _compute_mapping_for_org(org_id: str):
    """Helper to compute mapping for an org_id and return result dict."""
    from bson import ObjectId
    controls = await db.nist_controls.find({}, {"_id": 0}).to_list(5000)
    if not controls:
        raise HTTPException(status_code=404, detail="No NIST controls imported")
    org = await db.organizations.find_one({"_id": ObjectId(org_id)})
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    health = await db.health_index.find_one({"org_id": org_id}) or {}
    connectors = await db.connectors.find({"org_id": org_id}).to_list(200)
    risks = await db.risks.find({"org_id": org_id}).to_list(500)
    health_text = " ".join([c.get("name", "") + " " + str(c.get("score", "")) for c in (health.get("components") or [])])
    connector_text = " ".join([c.get("name", "") + " " + c.get("type", "") for c in connectors])
    risks_text = " ".join([r.get("title", "") + " " + r.get("category", "") for r in risks])
    matched = []
    family_counts: dict = {}
    for c in controls:
        kws = [k.lower() for k in (c.get("keywords") or []) if isinstance(k, str)]
        title = (c.get("title") or "").lower()
        fam = (c.get("family") or "").upper()
        satisfied = False
        for kw in kws + [title, fam.lower()]:
            if not kw:
                continue
            if kw in health_text.lower() or kw in connector_text.lower() or kw in risks_text.lower():
                satisfied = True
                break
        matched.append({"id": c.get("id"), "title": c.get("title"), "family": fam, "satisfied": satisfied})
        family_counts[fam] = family_counts.get(fam, {"total": 0, "satisfied": 0})
        family_counts[fam]["total"] += 1
        if satisfied:
            family_counts[fam]["satisfied"] += 1
    total = len(matched)
    sat = sum(1 for m in matched if m.get("satisfied"))
    score = round((sat / total) * 100, 1) if total else 0.0
    result = {"org_id": org_id, "score_percent": score, "total_controls": total, "satisfied": sat, "by_family": family_counts, "mapping": matched}
    await db.control_mappings.update_one({"org_id": org_id}, {"$set": {"last_mapping": result}}, upsert=True)
    return result


@nist_router.post("/map-me")
async def map_me(user: dict = Depends(get_current_user)):
    """Compute mapping for the current user's org and return result. Authenticated users can call to see compliance for their org."""
    res = await _compute_mapping_for_org(user["org_id"])
    await _log_audit(user.get("org_id"), user.get("email"), "nist.map.me", f"User requested NIST mapping snapshot — score {res.get('score_percent')}%")
    return res


@nist_router.get("/mapping")
async def get_mapping(user: dict = Depends(get_current_user)):
    """Return the last stored mapping snapshot for the current user's org, or run a new mapping if missing."""
    doc = await db.control_mappings.find_one({"org_id": user["org_id"]}) or {}
    if doc.get("last_mapping"):
        return doc["last_mapping"]
    res = await _compute_mapping_for_org(user["org_id"])
    await _log_audit(user.get("org_id"), user.get("email"), "nist.map.auto", f"Auto-computed NIST mapping — score {res.get('score_percent')}%")
    return res


@nist_router.get("/eu-cra")
async def eu_cra_requirements():
    # load a local EU CRA requirements file if present
    path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "deploy", "onprem", "eu_cra_requirements.json")
    if not os.path.exists(path):
        # try local
        path = os.path.join(os.path.dirname(__file__), "eu_cra_requirements.json")
    if not os.path.exists(path):
        return {"requirements": []}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return {"requirements": data}
    except Exception:
        return {"requirements": []}
