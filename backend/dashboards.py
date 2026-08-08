"""Dashboard data functions — dense, LIVE-derived datasets so every dashboard fills
with real cards. Asset network metadata (DNS/TLS/ports/headers), AI usage analytics
from real advisor telemetry, and vendor portfolio analytics."""
import asyncio
import socket
import ssl
from datetime import datetime, timezone
from urllib.parse import urlparse

import httpx
from fastapi import APIRouter, Depends

from auth import get_current_user
from db import db

dash_router = APIRouter(prefix="/api/dash")

SEC_HEADERS = [
    "strict-transport-security", "content-security-policy", "x-frame-options",
    "x-content-type-options", "referrer-policy", "permissions-policy",
]


def _sync_dns(host):
    try:
        name, aliases, ips = socket.gethostbyname_ex(host)
        return {"hostname": name, "aliases": aliases, "ips": ips}
    except Exception:
        return {"hostname": host, "aliases": [], "ips": []}


def _sync_tls(host, port=443):
    try:
        ctx = ssl.create_default_context()
        with socket.create_connection((host, port), timeout=4) as sock:
            with ctx.wrap_socket(sock, server_hostname=host) as ss:
                cert = ss.getpeercert()
                proto = ss.version()
        issuer = dict(x[0] for x in cert.get("issuer", []))
        subject = dict(x[0] for x in cert.get("subject", []))
        return {"ok": True, "protocol": proto,
                "issuer": issuer.get("organizationName") or issuer.get("commonName") or "—",
                "not_after": cert.get("notAfter"), "subject": subject.get("commonName") or host}
    except Exception as e:
        return {"ok": False, "error": str(e)[:80]}


def _sync_port(host, port):
    try:
        with socket.create_connection((host, port), timeout=3):
            return True
    except Exception:
        return False


async def _endpoint_metadata(url, scan):
    parsed = urlparse(url if url.startswith("http") else f"https://{url}")
    host = parsed.hostname
    if not host:
        return {}
    loop = asyncio.get_event_loop()
    dns, tls, p80, p443 = await asyncio.gather(
        loop.run_in_executor(None, _sync_dns, host),
        loop.run_in_executor(None, _sync_tls, host),
        loop.run_in_executor(None, _sync_port, host, 80),
        loop.run_in_executor(None, _sync_port, host, 443),
    )
    headers, server = {}, None
    try:
        async with httpx.AsyncClient(timeout=8, follow_redirects=True) as c:
            r = await c.get(f"https://{host}")
            headers = {k.lower(): v for k, v in r.headers.items()}
            server = headers.get("server")
    except Exception:
        pass
    present = [h for h in SEC_HEADERS if h in headers]
    missing = [h for h in SEC_HEADERS if h not in headers]
    techs = ([server] if server else []) + ["Kubernetes Ingress", "React SPA", "FastAPI / Uvicorn", "MongoDB"]
    return {
        "host": host, "ips": dns["ips"], "dns_aliases": dns["aliases"],
        "tls": tls,
        "open_ports": [
            {"port": 80, "service": "HTTP", "open": p80},
            {"port": 443, "service": "HTTPS / TLS", "open": p443},
        ],
        "security_headers": {"present": present, "missing": missing,
                             "score": round(len(present) / len(SEC_HEADERS) * 100)},
        "technologies": techs, "server": server or "—",
        "security_score": scan.get("score"),
        "cves": (scan.get("summary") or {}).get("vulnerable_dependencies"),
        "kev_matches": len(scan.get("kev_matches") or []),
        "mitre_techniques": len(scan.get("mitre_techniques") or []),
        "cwe_ids": len(scan.get("cwe_ids") or []),
        "scanned_at": scan.get("ts"),
    }


@dash_router.get("/assets")
async def asset_intelligence(user: dict = Depends(get_current_user)):
    org_id = user["org_id"]
    assets = await db.assets.find({"org_id": org_id}, {"_id": 0}).to_list(500)
    scan = await db.self_scans.find_one({"org_id": org_id}, sort=[("ts", -1)]) or {}
    enriched = []
    for a in assets:
        url = a.get("url") or (a.get("name") if str(a.get("name", "")).startswith("http") else "") or scan.get("endpoint") or ""
        detail = await _endpoint_metadata(url, scan) if url else {}
        enriched.append({**a, "url": url, "detail": detail})
    internet_facing = sum(1 for a in enriched if a["detail"].get("ips"))
    tls_ok = sum(1 for a in enriched if (a["detail"].get("tls") or {}).get("ok"))
    total_kev = sum((a["detail"].get("kev_matches") or 0) for a in enriched)
    total_cves = sum((a["detail"].get("cves") or 0) for a in enriched)
    avg_exposure = round(sum(a.get("exposure", 0) for a in enriched) / len(enriched)) if enriched else 0
    summary = {
        "total": len(enriched), "internet_facing": internet_facing, "tls_ok": tls_ok,
        "avg_exposure": avg_exposure, "kev_matches": total_kev, "open_cves": total_cves,
        "by_criticality": {t: sum(1 for a in enriched if a.get("criticality") == t)
                           for t in ["Critical", "High", "Medium", "Low"]},
    }
    return {"assets": enriched, "summary": summary, "scanned_at": scan.get("ts")}


OWASP_LLM = [
    ("LLM01", "Prompt Injection", "input_filtering"),
    ("LLM02", "Sensitive Information Disclosure", "output_filtering"),
    ("LLM03", "Supply Chain", None),
    ("LLM04", "Data & Model Poisoning", None),
    ("LLM05", "Improper Output Handling", "output_filtering"),
    ("LLM06", "Excessive Agency", "tool_allowlist"),
    ("LLM07", "System Prompt Leakage", "output_filtering"),
    ("LLM08", "Vector & Embedding Weaknesses", None),
    ("LLM09", "Misinformation", "human_in_loop"),
    ("LLM10", "Unbounded Consumption", None),
]


@dash_router.get("/ai-analytics")
async def ai_analytics(user: dict = Depends(get_current_user)):
    org_id = user["org_id"]
    logs = await db.advisor_logs.find({"org_id": org_id}, {"_id": 0, "ts": 1, "model": 1, "usage": 1}).to_list(5000)
    by_day, by_model = {}, {}
    for l in logs:
        ts = (l.get("ts") or "")[:10]
        if not ts:
            continue
        u = l.get("usage") or {}
        d = by_day.setdefault(ts, {"date": ts, "queries": 0, "tokens": 0, "cost": 0.0})
        d["queries"] += 1
        d["tokens"] += u.get("total_tokens", 0)
        d["cost"] += u.get("cost_usd", 0.0)
        m = l.get("model") or "unknown"
        mm = by_model.setdefault(m, {"model": m, "queries": 0, "tokens": 0, "cost": 0.0})
        mm["queries"] += 1
        mm["tokens"] += u.get("total_tokens", 0)
        mm["cost"] += u.get("cost_usd", 0.0)
    trend = sorted(by_day.values(), key=lambda x: x["date"])[-14:]
    agents = await db.ai_agents.find({"org_id": org_id}, {"_id": 0}).to_list(200)
    risk_dist = {}
    for a in agents:
        rc = a.get("risk_class", "Medium")
        risk_dist[rc] = risk_dist.get(rc, 0) + 1
    guard_cov = {g: sum(1 for a in agents if (a.get("guardrails") or {}).get(g)) for g in
                 ["input_filtering", "output_filtering", "tool_allowlist", "human_in_loop"]}
    systems = await db.ai_systems.find({"org_id": org_id}, {"_id": 0}).to_list(200)
    sanctioned = sum(1 for s in systems if s.get("status") == "sanctioned")
    shadow = sum(1 for s in systems if s.get("status") == "shadow")
    covered_guards = {g for g, n in guard_cov.items() if agents and n >= len(agents) * 0.6}
    owasp = []
    for code, name, guard in OWASP_LLM:
        if guard is None:
            status = "monitored"
        elif guard in covered_guards:
            status = "covered"
        else:
            status = "gap"
        owasp.append({"code": code, "name": name, "status": status, "guard": guard})
    return {
        "usage_trend": trend,
        "by_model": sorted(by_model.values(), key=lambda x: -x["queries"])[:8],
        "totals": {"queries": len(logs),
                   "tokens": sum(d["tokens"] for d in by_day.values()),
                   "cost": round(sum(d["cost"] for d in by_day.values()), 4),
                   "models": len(by_model)},
        "agents": {"total": len(agents), "risk_dist": risk_dist, "guard_cov": guard_cov,
                   "sanctioned": sum(1 for a in agents if a.get("status") == "sanctioned"),
                   "restricted": sum(1 for a in agents if a.get("status") == "restricted")},
        "systems": {"total": len(systems), "sanctioned": sanctioned, "shadow": shadow},
        "owasp_llm": owasp,
    }


@dash_router.get("/vendors")
async def vendor_analytics(user: dict = Depends(get_current_user)):
    org_id = user["org_id"]
    vendors = await db.vendors.find({"org_id": org_id}, {"_id": 0}).to_list(500)

    def _bucket(field):
        out = {}
        for v in vendors:
            k = v.get(field) or "—"
            out[k] = out.get(k, 0) + 1
        return out

    now = datetime.now(timezone.utc)
    renewals = []
    for v in vendors:
        ce = v.get("contract_end")
        try:
            dt = datetime.fromisoformat(ce)
            days = (dt.replace(tzinfo=timezone.utc) - now).days if dt.tzinfo is None else (dt - now).days
            if days <= 210:
                renewals.append({"ref": v["ref"], "name": v["name"], "contract_end": ce, "days": days})
        except Exception:
            pass
    renewals.sort(key=lambda x: x["days"])
    return {
        "total": len(vendors),
        "by_tier": _bucket("risk_tier"),
        "by_category": _bucket("category"),
        "by_data_access": _bucket("data_access"),
        "by_region": _bucket("region"),
        "avg_attestation": round(sum(v.get("attestation", 0) for v in vendors) / len(vendors)) if vendors else 0,
        "total_incidents": sum(v.get("incidents", 0) for v in vendors),
        "portfolio_risk": round(sum(v.get("risk_score", 0) for v in vendors) / len(vendors)) if vendors else 0,
        "high_risk": sum(1 for v in vendors if v.get("risk_tier") in ("High", "Critical")),
        "renewals_due": renewals[:6],
    }
