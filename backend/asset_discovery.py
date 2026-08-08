"""Zero-touch asset discovery — maps LIVE connected-SaaS devices, users and connectors into the
Unified Risk Correlation Engine as first-class assets, so their IP/MAC/site + compliance/role
posture actively affect ALE.

NOTHING here is seeded: an asset exists only when a real connector (Microsoft 365 / Intune /
Entra ID, or a catalog connector) returns live inventory to an authenticated probe. Assets that
carry genuine exposure (non-compliant devices, privileged/external/disabled identities, degraded
connectors) are turned into correlated risk records by `derive_asset_risks` so they flow through
the engine and move the portfolio ALE. Healthy assets add inventory context but no ALE.
"""
import hashlib
import logging
import uuid
from datetime import datetime, timezone

import httpx
from bson import ObjectId

from db import db

logger = logging.getLogger(__name__)


def _now():
    return datetime.now(timezone.utc).isoformat()


def _ref(prefix, raw):
    return f"{prefix}-{hashlib.sha1(str(raw).encode()).hexdigest()[:8].upper()}"


def _site_from_upn(upn):
    return upn.split("@", 1)[1] if upn and "@" in upn else None


async def _m365_users(d):
    """Live Entra ID users via Microsoft Graph (best-effort). Role/last-active drive risk."""
    try:
        async with httpx.AsyncClient(timeout=20) as c:
            tok = await c.post(
                f"https://login.microsoftonline.com/{d['tenant_id']}/oauth2/v2.0/token",
                data={"client_id": d["client_id"], "client_secret": d["client_secret"],
                      "grant_type": "client_credentials", "scope": "https://graph.microsoft.com/.default"})
            if tok.status_code != 200:
                return {"available": False, "note": "Graph token unavailable — re-check M365 credentials."}
            access = tok.json()["access_token"]
            r = await c.get(
                "https://graph.microsoft.com/v1.0/users"
                "?$select=id,displayName,userPrincipalName,jobTitle,accountEnabled,userType,signInActivity&$top=100",
                headers={"Authorization": f"Bearer {access}"})
            if r.status_code != 200:
                return {"available": False,
                        "note": f"User inventory not accessible (HTTP {r.status_code}) — grant User.Read.All."}
            vals = r.json().get("value", [])
            items = []
            for v in vals[:100]:
                title = v.get("jobTitle") or ""
                upn = v.get("userPrincipalName") or ""
                privileged = any(k in (title + " " + upn).lower()
                                 for k in ("admin", "root", "superuser", "global", "chief",
                                           "ceo", "cfo", "ciso", "cto"))
                sia = v.get("signInActivity") or {}
                items.append({"id": v.get("id"), "name": v.get("displayName") or upn, "upn": upn,
                              "title": title or None, "external": v.get("userType") == "Guest",
                              "enabled": bool(v.get("accountEnabled", True)),
                              "privileged": privileged, "last_active": sia.get("lastSignInDateTime")})
            return {"available": True, "total": len(vals), "items": items}
    except Exception as e:
        return {"available": False, "note": f"User read failed: {str(e)[:100]}"}


async def discover_and_map_assets(org_id: str) -> dict:
    """Probe every LIVE source and upsert its inventory into db.assets (tagged discovered=True).
    Re-runnable (upsert by ref) so the daily zero-touch cron keeps the inventory fresh."""
    from self_scan import _m365_devices
    org = await db.organizations.find_one({"_id": ObjectId(org_id)}) or {}
    summary = {"devices": 0, "users": 0, "connectors": 0, "sources": []}
    upserts = []

    m365 = org.get("live_m365")
    if m365 and (m365.get("live") or m365.get("synced_at")):
        dev = await _m365_devices(m365)
        if dev.get("available"):
            summary["sources"].append("Microsoft 365 (Intune)")
            for it in dev.get("items", []):
                noncompliant = it.get("compliance") == "noncompliant"
                upserts.append({
                    "ref": _ref("DEV", it["id"]), "name": it.get("name") or "device",
                    "type": "Managed Device", "criticality": "High" if noncompliant else "Medium",
                    "owner": it.get("owner") or "Unassigned", "source": "Microsoft 365 (Intune)",
                    "status": (it.get("compliance") or "unknown").title(), "freshness": "live",
                    "discovered": True,
                    "network": {"ip": it.get("ip"), "mac": it.get("mac"), "site": it.get("site")},
                    "os": " ".join(x for x in [it.get("os"), it.get("os_version")] if x) or None,
                    "compliance": it.get("compliance"), "last_active": it.get("last_sync"),
                    "exposure": 70 if noncompliant else 30})
            summary["devices"] = len(dev.get("items", []))

        usr = await _m365_users(m365)
        if usr.get("available"):
            summary["sources"].append("Microsoft 365 (Entra ID)")
            for it in usr.get("items", []):
                risky = it.get("privileged") or it.get("external") or not it.get("enabled")
                crit = "High" if it.get("privileged") else "Medium" if risky else "Low"
                upserts.append({
                    "ref": _ref("USR", it["id"]), "name": it.get("name"), "type": "Identity",
                    "criticality": crit, "owner": it.get("name"), "source": "Microsoft 365 (Entra ID)",
                    "status": it.get("title") or ("Guest" if it.get("external") else "Member"),
                    "freshness": "live", "discovered": True,
                    "network": {"ip": None, "mac": None, "site": _site_from_upn(it.get("upn"))},
                    "role": it.get("title"), "privileged": it.get("privileged"),
                    "external_user": it.get("external"), "enabled": it.get("enabled"),
                    "last_active": it.get("last_active"), "exposure": 60 if it.get("privileged") else 25})
            summary["users"] = len(usr.get("items", []))

    # Catalog connectors (36-provider) — connected ones are live integration surfaces.
    from connectors_catalog import CATALOG
    cat_by_id = {e["id"]: e for e in CATALOG}
    states = await db.connector_state.find({"org_id": org_id}, {"_id": 0}).to_list(200)
    mapped_states = ("connected", "auth_failed", "unreachable", "error")
    for st in states:
        if st.get("state") not in mapped_states:
            continue
        cid = st.get("cid")
        entry = cat_by_id.get(cid) or {}
        degraded = st.get("state") != "connected"
        cat = entry.get("category") or "Integration"
        crit = "High" if (degraded or cat.startswith(("Identity", "Network", "SIEM"))) else "Medium"
        upserts.append({
            "ref": _ref("CX", cid), "name": entry.get("name") or cid, "type": "SaaS Connector",
            "criticality": crit, "owner": "Integrations", "source": entry.get("name") or cid,
            "status": "Degraded" if degraded else "Connected", "freshness": "live", "discovered": True,
            "network": {"ip": None, "mac": None, "site": st.get("endpoint")},
            "category": cat, "connector_state": st.get("state"), "degraded": degraded,
            "exposure": 65 if degraded else 20})
        summary["connectors"] += 1

    # ---- Deep inventory: GitHub repositories + ServiceNow CMDB (when connected with creds) ----
    st_by_id = {st.get("cid"): st for st in states}
    gh = st_by_id.get("github")
    if gh and gh.get("state") == "connected" and gh.get("creds"):
        repos = await _github_inventory(gh["creds"])
        if repos:
            summary["sources"].append("GitHub")
        for it in repos:
            upserts.append({
                "ref": _ref("REPO", it["id"]), "name": it["name"], "type": "Code Repository",
                "criticality": it["criticality"], "owner": it.get("owner") or "Engineering",
                "source": "GitHub", "status": it["visibility"].title(), "freshness": "live", "discovered": True,
                "network": {"ip": None, "mac": None, "site": it.get("url")},
                "visibility": it["visibility"], "pushed_at": it.get("pushed_at"), "exposure": it["exposure"]})
        summary["repos"] = len(repos)
    sn = st_by_id.get("servicenow")
    if sn and sn.get("state") == "connected" and sn.get("creds"):
        cis = await _servicenow_cmdb(sn["creds"])
        if cis:
            summary["sources"].append("ServiceNow CMDB")
        for it in cis:
            upserts.append({
                "ref": _ref("CI", it["id"]), "name": it["name"], "type": it.get("ci_class") or "CMDB CI",
                "criticality": it["criticality"], "owner": it.get("owner") or "IT",
                "source": "ServiceNow CMDB", "status": it.get("status") or "Operational",
                "freshness": "live", "discovered": True,
                "network": {"ip": it.get("ip"), "mac": it.get("mac"), "site": it.get("location")},
                "exposure": it["exposure"]})
        summary["cmdb_cis"] = len(cis)

    for a in upserts:
        await db.assets.update_one({"org_id": org_id, "ref": a["ref"]},
                                   {"$set": {**a, "org_id": org_id, "discovered_at": _now()}}, upsert=True)
    await _maybe_open_actions(org_id, upserts)
    return summary


async def _github_inventory(creds):
    """Live GitHub repository inventory (real authenticated call). Public repos carry more exposure."""
    token = creds.get("token")
    if not token:
        return []
    out = []
    try:
        async with httpx.AsyncClient(timeout=20) as c:
            r = await c.get("https://api.github.com/user/repos?per_page=100&sort=pushed",
                            headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"})
        if r.status_code != 200:
            return []
        for repo in r.json()[:100]:
            vis = "public" if not repo.get("private") else "private"
            out.append({"id": repo.get("id"), "name": repo.get("full_name") or repo.get("name"),
                        "owner": (repo.get("owner") or {}).get("login"), "visibility": vis,
                        "url": repo.get("html_url"), "pushed_at": repo.get("pushed_at"),
                        "criticality": "High" if vis == "public" else "Medium",
                        "exposure": 70 if vis == "public" else 35})
    except Exception as e:
        logger.warning(f"GitHub inventory failed: {e}")
    return out


async def _servicenow_cmdb(creds):
    """Live ServiceNow CMDB configuration-item inventory (real Table API call)."""
    token, base = creds.get("token"), creds.get("base")
    if not token or not base:
        return []
    out = []
    try:
        url = (base.rstrip("/") + "/api/now/table/cmdb_ci?sysparm_limit=100"
               "&sysparm_fields=sys_id,name,sys_class_name,ip_address,mac_address,location,operational_status")
        async with httpx.AsyncClient(timeout=20) as c:
            r = await c.get(url, headers={"Authorization": f"Bearer {token}", "Accept": "application/json"})
        if r.status_code != 200:
            return []
        for ci in (r.json().get("result") or [])[:100]:
            op = str(ci.get("operational_status") or "")
            operational = op in ("", "1")
            out.append({"id": ci.get("sys_id") or ci.get("name"), "name": ci.get("name") or "CI",
                        "ci_class": ci.get("sys_class_name"), "ip": ci.get("ip_address") or None,
                        "mac": ci.get("mac_address") or None, "location": ci.get("location") or None,
                        "status": "Operational" if operational else (op or "Unknown"),
                        "criticality": "Medium" if operational else "High",
                        "exposure": 25 if operational else 55})
    except Exception as e:
        logger.warning(f"ServiceNow CMDB failed: {e}")
    return out


_ACTION_KIND = {
    "device": ("device-remediation", "Non-compliant device discovered — remediation task opened"),
    "identity": ("jit-access-review", "Privileged/guest identity discovered — JIT access review opened"),
    "connector": ("connector-recredential", "Connector degraded — re-credential task opened"),
}


async def _maybe_open_actions(org_id, upserts):
    """Zero-touch auto-action: the moment discovery finds a non-compliant device, a privileged/guest
    identity, or a degraded connector, open a remediation task / JIT access review (once per asset)
    and alert. So exposure is actioned as it appears — not on the next manual review."""
    from kernel import notifications
    from self_scan import _post_chat_alert
    opened = 0
    for a in upserts:
        typ = a.get("type")
        kind = reason = None
        if typ == "Managed Device" and a.get("compliance") == "noncompliant":
            kind, reason = "device", f"Device '{a.get('name')}' is non-compliant"
        elif typ == "Identity" and (a.get("privileged") or a.get("external_user")):
            kind = "identity"
            reason = (f"Privileged identity '{a.get('name')}'" if a.get("privileged")
                      else f"External/guest identity '{a.get('name')}'")
        elif typ == "SaaS Connector" and a.get("degraded"):
            kind, reason = "connector", f"Connector '{a.get('name')}' degraded ({a.get('connector_state')})"
        if not kind:
            continue
        if await db.discovery_actions.find_one({"org_id": org_id, "ref": a["ref"], "status": "open"}):
            continue
        action_kind, title = _ACTION_KIND[kind]
        await db.discovery_actions.insert_one({
            "org_id": org_id, "id": uuid.uuid4().hex, "ref": a["ref"], "asset_name": a.get("name"),
            "asset_type": typ, "kind": action_kind, "status": "open", "reason": reason,
            "network": a.get("network"), "created_at": _now()})
        try:
            await notifications.create(org_id, "discovery", title, reason,
                                       ref=f"disc-{a['ref']}", dedupe_key=f"disc-action:{a['ref']}")
            await _post_chat_alert(org_id, f"🛡 {title}",
                                   f"{reason}. Auto-actioned the moment it was discovered — "
                                   "review under Asset Intelligence → Discovery Actions.")
        except Exception as e:
            logger.warning(f"discovery action alert failed: {e}")
        opened += 1
    if opened:
        logger.info(f"Opened {opened} discovery action(s) for org {org_id}")


def _mk(asset_ref, pfx, title, category, impact, likelihood, inherent, residual, owner):
    return {"ref": f"{pfx}-{asset_ref}", "title": title, "category": category, "owner": owner,
            "status": "Open", "impact": impact, "likelihood": likelihood, "inherent": inherent,
            "residual": residual, "confidence": 0.7, "kev": False, "asset_ref": asset_ref,
            "derived": True, "source": "connector-discovery"}


def derive_asset_risks(assets):
    """Correlate discovered live assets that carry genuine exposure into risk records so the
    engine prices their ALE. Deterministic (no LLM): posture → probability/impact band."""
    out = []
    for a in assets:
        if not a.get("discovered"):
            continue
        ref, typ = a.get("ref"), a.get("type")
        if typ == "Managed Device" and a.get("compliance") == "noncompliant":
            out.append(_mk(ref, "END", f"Non-compliant managed device — {a.get('name')}",
                           "Endpoint Security", 4, 4, 20, 16, a.get("owner")))
        elif typ == "Identity":
            if a.get("privileged"):
                out.append(_mk(ref, "IAM", f"Privileged identity exposure — {a.get('name')}",
                               "Identity & Access", 4, 3, 18, 13, a.get("owner")))
            elif a.get("external_user"):
                out.append(_mk(ref, "IAM", f"External/guest identity — {a.get('name')}",
                               "Identity & Access", 3, 3, 12, 9, a.get("owner")))
            elif a.get("enabled") is False:
                out.append(_mk(ref, "IAM", f"Stale/disabled account still present — {a.get('name')}",
                               "Identity & Access", 2, 2, 8, 6, a.get("owner")))
        elif typ == "SaaS Connector" and a.get("degraded"):
            out.append(_mk(ref, "TPR", f"Degraded connector — {a.get('name')} ({a.get('connector_state')})",
                           "Third-Party Risk", 3, 3, 12, 10, "Integrations"))
    return out
