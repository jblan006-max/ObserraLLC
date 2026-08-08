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

    for a in upserts:
        await db.assets.update_one({"org_id": org_id, "ref": a["ref"]},
                                   {"$set": {**a, "org_id": org_id, "discovered_at": _now()}}, upsert=True)
    return summary


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
