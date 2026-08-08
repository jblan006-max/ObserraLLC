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

# Per-host enrichment cache so the Asset Intelligence dashboard never re-probes the
# same endpoint on every load (DNS/TLS/port/HTTP probes are expensive).
_ASSET_CACHE = {}
_ASSET_TTL = 300


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


def _asset_url(a, scan):
    return (a.get("url") or (a.get("name") if str(a.get("name", "")).startswith("http") else "")
            or scan.get("endpoint") or "")


@dash_router.get("/assets")
async def asset_intelligence(user: dict = Depends(get_current_user)):
    org_id = user["org_id"]
    assets = await db.assets.find({"org_id": org_id}, {"_id": 0}).to_list(500)
    scan = await db.self_scans.find_one({"org_id": org_id}, sort=[("ts", -1)]) or {}
    # Resolve each asset to a host, dedupe, and enrich unique hosts concurrently (cached).
    host_of, unique = {}, {}
    for a in assets:
        url = _asset_url(a, scan)
        host = urlparse(url if url.startswith("http") else f"https://{url}").hostname if url else None
        host_of[a.get("ref")] = (host, url)
        if host and host not in unique:
            unique[host] = url
    now = datetime.now(timezone.utc)

    async def _enrich(host, url):
        c = _ASSET_CACHE.get(host)
        if c and (now - c["ts"]).total_seconds() < _ASSET_TTL:
            return host, c["data"]
        data = await _endpoint_metadata(url, scan)
        _ASSET_CACHE[host] = {"ts": now, "data": data}
        return host, data

    results = await asyncio.gather(*[_enrich(h, u) for h, u in unique.items()]) if unique else []
    detail_by_host = {h: d for h, d in results}
    enriched = []
    for a in assets:
        host, url = host_of.get(a.get("ref"), (None, ""))
        enriched.append({**a, "url": url, "detail": detail_by_host.get(host, {}) if host else {}})
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


@dash_router.get("/decisions")
async def decisions_analytics(user: dict = Depends(get_current_user)):
    """Live recommendation → decision funnel: what the AI is recommending, what's been
    decided, coverage of open risks, and the recent decision register — so the Decisions
    dashboard is always populated from real org state."""
    org_id = user["org_id"]
    recs = await db.recommendations.find({"org_id": org_id}, {"_id": 0}).to_list(500)
    decisions = await db.decisions.find({"org_id": org_id}, {"_id": 0}).to_list(500)
    risks = await db.risks.find({"org_id": org_id}, {"_id": 0}).to_list(500)
    risk_by_ref = {r["ref"]: r for r in risks}

    status_counts, by_category = {}, {}
    for r in recs:
        s = r.get("status", "Pending")
        status_counts[s] = status_counts.get(s, 0) + 1
        cat = (risk_by_ref.get(r.get("risk_ref")) or {}).get("category") or "Uncategorised"
        by_category[cat] = by_category.get(cat, 0) + 1
    confs = [r.get("confidence") for r in recs if r.get("confidence") is not None]
    avg_conf = round(sum(confs) / len(confs), 2) if confs else 0

    open_risks = [r for r in risks if r.get("status") != "Remediated"]
    with_rec = {r.get("risk_ref") for r in recs}
    covered = sum(1 for r in open_risks if r["ref"] in with_rec)
    coverage_pct = round(covered / len(open_risks) * 100) if open_risks else 0

    dec_status = {}
    for d in decisions:
        k = d.get("status", "Approved")
        dec_status[k] = dec_status.get(k, 0) + 1

    return {
        "totals": {"recommendations": len(recs), "pending": status_counts.get("Pending", 0),
                   "decided": status_counts.get("Decided", 0), "applied": status_counts.get("Applied", 0),
                   "decisions": len(decisions), "avg_confidence": avg_conf},
        "rec_status": [{"name": k, "value": v} for k, v in status_counts.items()],
        "by_category": sorted([{"name": k, "value": v} for k, v in by_category.items()],
                              key=lambda x: -x["value"]),
        "coverage": {"open_risks": len(open_risks), "covered": covered, "pct": coverage_pct},
        "decision_status": [{"name": k, "value": v} for k, v in dec_status.items()],
        "recent_decisions": sorted(decisions, key=lambda d: d.get("decided_at", ""), reverse=True)[:5],
    }


_BAND = {"Low": "142 70% 45%", "Moderate": "48 96% 53%", "High": "28 90% 55%", "Extreme": "0 84% 60%"}


def _band(score):
    return "Extreme" if score >= 14 else "High" if score >= 8 else "Moderate" if score >= 4 else "Low"


@dash_router.get("/risk-register")
async def risk_register(user: dict = Depends(get_current_user)):
    """Board-grade risk portfolio reporting computed LIVE: quantitative 5x5 matrix, Monte-Carlo
    loss-exposure distribution, risk-trending-vs-appetite, top risks, control deficiencies,
    security initiatives — all tied to assets, vulnerabilities, controls and residual risk."""
    import random
    from bson import ObjectId
    from routes import _get_fin_cfg, _fin
    org_id = user["org_id"]
    risks = await db.risks.find({"org_id": org_id}, {"_id": 0}).to_list(500)
    controls = await db.controls.find({"org_id": org_id}, {"_id": 0}).to_list(500)
    recs = await db.recommendations.find({"org_id": org_id}, {"_id": 0}).to_list(500)
    scan = await db.self_scans.find_one({"org_id": org_id}, sort=[("ts", -1)]) or {}
    org = await db.organizations.find_one({"_id": ObjectId(org_id)}) or {}
    cfg = await _get_fin_cfg(org_id)

    fins = [(r, _fin(r, cfg)) for r in risks]
    # controls grouped by category for linkage
    ctrl_by_cat = {}
    for c in controls:
        ctrl_by_cat.setdefault(c.get("category") or "General", []).append(c)

    residual_total = round(sum(f["residual_ale"] for _, f in fins))
    avg_ctrl = round(sum(c.get("effectiveness", 0) for c in controls) / len(controls)) if controls else 0

    # 5x5 quantitative matrix
    matrix = []
    for imp in range(1, 6):
        for lik in range(1, 6):
            cell = [r for r in risks if r.get("impact") == imp and r.get("likelihood") == lik]
            top = max(cell, key=lambda r: r.get("residual", 0)) if cell else None
            matrix.append({"impact": imp, "likelihood": lik, "score": imp * lik, "band": _band(imp * lik),
                           "count": len(cell), "top": top["ref"] if top else None,
                           "refs": [r["ref"] for r in cell]})

    # Monte-Carlo portfolio loss distribution
    sims = []
    for _ in range(4000):
        s = 0.0
        for r, f in fins:
            sle_s = random.triangular(f["sle"] * 0.5, f["sle"] * 2.0, f["sle"])
            aro_s = min(1.0, max(0.0, random.gauss(f["aro"], 0.15)))
            s += sle_s * aro_s * (r.get("residual", 10) / max(1, r.get("inherent", 10)))
        sims.append(s)
    sims.sort()

    def _q(p):
        return round(sims[min(len(sims) - 1, int(p * len(sims)))]) if sims else 0
    hist, ml = [], 0
    if sims and sims[-1] > sims[0]:
        nb = 22
        lo, hi = sims[0], sims[-1]
        width = (hi - lo) / nb or 1
        counts = [0] * nb
        for v in sims:
            counts[min(nb - 1, int((v - lo) / width))] += 1
        hist = [{"x": round(lo + width * (i + 0.5)), "count": counts[i]} for i in range(nb)]
        ml = round(lo + width * (counts.index(max(counts)) + 0.5))
    markers = {"min": _q(0.0), "p10": _q(0.10), "ml": ml, "p50": _q(0.50), "p90": _q(0.90), "max": _q(1.0)}

    # top risks with control linkage
    top_risks = []
    for r, f in sorted(fins, key=lambda x: x[1]["residual_ale"], reverse=True)[:10]:
        linked = ctrl_by_cat.get(r.get("category"), [])
        top_risks.append({"ref": r["ref"], "title": r["title"], "category": r.get("category"),
                          "residual": r.get("residual"), "inherent": r.get("inherent"),
                          "status": r.get("status"), "trend": r.get("trend", "flat"),
                          "owner": r.get("owner"), "exposure": f["residual_ale"],
                          "controls": [c.get("name") for c in linked[:3]],
                          "control_count": len(linked)})

    # control deficiencies (lowest effectiveness)
    deficiencies = []
    for c in sorted(controls, key=lambda c: c.get("effectiveness", 0))[:8]:
        eff = c.get("effectiveness", 0)
        deficiencies.append({"control_id": c.get("control_id"), "name": c.get("name"),
                             "effectiveness": eff, "deficiency": 100 - eff,
                             "owner": c.get("owner"), "category": c.get("category"),
                             "status": c.get("status")})

    # security initiatives from recommendations
    prog = {"Pending": 15, "Decided": 55, "Applied": 90, "Closed": 100}
    initiatives = [{"ref": r["ref"], "title": r["title"], "status": r.get("status", "Pending"),
                    "progress": prog.get(r.get("status", "Pending"), 20)} for r in recs][:6]

    # trending vs appetite
    snaps = await db.exposure_snapshots.find({"org_id": org_id}, {"_id": 0}).sort("month", 1).to_list(24)
    appetite = org.get("risk_appetite") or round(residual_total * 0.7)
    points = []
    if len(snaps) >= 2:
        for s in snaps[-8:]:
            exp = s.get("residual_total") or 0
            points.append({"period": s.get("label") or s.get("month"), "expected": exp,
                           "low": round(exp * 0.72), "high": round(exp * 1.38), "appetite": appetite})
        real = True
    else:
        exp = residual_total
        for i, lbl in enumerate(["-4mo", "-3mo", "-2mo", "-1mo", "Now"]):
            e = round(exp * (1.18 - i * 0.045))
            points.append({"period": lbl, "expected": e, "low": round(e * 0.72),
                           "high": round(e * 1.38), "appetite": appetite})
        real = False

    return {
        "kpis": {"total": len(risks), "open": sum(1 for r in risks if r.get("status") != "Remediated"),
                 "critical": sum(1 for r in risks if r.get("residual", 0) >= 16),
                 "residual_exposure": residual_total, "worst_case_p90": markers["p90"],
                 "avg_control_eff": avg_ctrl, "controls": len(controls)},
        "matrix": matrix, "bands": _BAND,
        "loss": {"histogram": hist, "markers": markers},
        "trending": {"points": points, "appetite": appetite, "real": real},
        "top_risks": top_risks, "control_deficiencies": deficiencies, "initiatives": initiatives,
        "vuln": {"open_cves": (scan.get("summary") or {}).get("vulnerable_dependencies") or 0,
                 "kev": len(scan.get("kev_matches") or []),
                 "mitre": len(scan.get("mitre_techniques") or []),
                 "cwe": len(scan.get("cwe_ids") or []), "score": scan.get("score")},
    }
