"""Live posture engine — derives the Risk Register, the endpoint asset and the
Health Index from the latest LIVE self-scan (findings + CISA-KEV/threat matches).

Used for live-only orgs so every dashboard reflects the real endpoint + live
threat feeds (benchmarked against the static IBM/AI figures) instead of demo
seed data. Idempotent: it only replaces the docs it owns (derived == True /
source == 'live-scan')."""
from datetime import datetime, timezone

from bson import ObjectId

from db import db

# severity -> FAIR-style base scoring (inherent 1-25, impact/likelihood 1-5)
_SEV = {
    "critical": {"inherent": 25, "impact": 5, "likelihood": 5, "confidence": 0.9},
    "high": {"inherent": 20, "impact": 5, "likelihood": 4, "confidence": 0.85},
    "medium": {"inherent": 12, "impact": 3, "likelihood": 3, "confidence": 0.8},
    "low": {"inherent": 6, "impact": 2, "likelihood": 2, "confidence": 0.75},
    "info": {"inherent": 4, "impact": 1, "likelihood": 1, "confidence": 0.7},
}
_SEV_PEN = {"critical": 25, "high": 12, "medium": 6, "low": 2, "info": 0}

# scan finding category -> risk taxonomy category
_CAT = {
    "Dependency": "Vulnerability Mgmt",
    "Web Hardening": "Vulnerability Mgmt",
    "API Hardening": "Data Protection",
    "Identity": "Identity & Access",
}
_HEALTH_CATS = ["Identity & Access", "Vulnerability Mgmt", "Data Protection",
                "AI Governance", "Resilience", "Third Party"]
_WEIGHTS = {"Identity & Access": 0.25, "Vulnerability Mgmt": 0.2, "Data Protection": 0.2,
            "AI Governance": 0.15, "Resilience": 0.1, "Third Party": 0.1}


def _now():
    return datetime.now(timezone.utc).isoformat()


def _grade(score):
    if score >= 90:
        return "A"
    if score >= 80:
        return "B"
    if score >= 70:
        return "C"
    if score >= 60:
        return "D"
    return "F"


async def rebuild_live_posture(org_id: str):
    """Regenerate live-derived risks + endpoint asset + health index from the
    latest self-scan. Returns a small summary dict."""
    scan = await db.self_scans.find_one({"org_id": org_id}, sort=[("ts", -1)])

    # Replace only what this engine owns; keep any manually-added items.
    await db.risks.delete_many({"org_id": org_id, "derived": True})
    await db.assets.delete_many({"org_id": org_id, "derived": True})

    if not scan:
        await db.health_index.delete_many({"org_id": org_id, "source": "live-scan"})
        return {"risks": 0, "assets": 0, "score": None, "endpoint": None}

    findings = scan.get("findings", []) or []
    fails = [f for f in findings if f.get("status") == "fail"]
    order = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
    fails.sort(key=lambda f: (0 if f.get("kev") else 1, order.get(f.get("severity"), 5)))

    risks = []
    for i, f in enumerate(fails, 1):
        sev = f.get("severity", "medium")
        base = _SEV.get(sev, _SEV["medium"])
        inherent, impact, likelihood = base["inherent"], base["impact"], base["likelihood"]
        if f.get("kev"):
            inherent, likelihood, impact = max(inherent, 24), 5, max(impact, 5)
        cat = _CAT.get(f.get("category"), "Vulnerability Mgmt")
        cves = f.get("cve_ids") or []
        risks.append({
            "org_id": org_id, "derived": True, "ref": f"LR-{i:03d}",
            "finding_id": f.get("id"), "severity": sev,
            "title": f.get("title", "Live finding"), "category": cat,
            "inherent": inherent, "residual": inherent,  # unremediated until fixed
            "likelihood": likelihood, "impact": impact,
            "status": "Open", "treatment": "Mitigate", "owner": "Security Team",
            "kri": (f.get("evidence") or "")[:180],
            "source": "Live self-scan", "freshness": "live", "confidence": base["confidence"],
            "data_type": "fact" if cves else "estimate",
            "business_impact": (("Actively exploited (CISA KEV) — " if f.get("kev") else "")
                                + (", ".join(cves[:3]) if cves else f.get("category", "Live finding"))),
            "trend": "up" if f.get("kev") else "flat",
            "cve_ids": cves, "kev": bool(f.get("kev")),
            "control_refs": f.get("control_refs", []), "remediation": f.get("remediation"),
            "created_at": _now(), "updated_at": _now(),
        })
    if risks:
        await db.risks.insert_many(risks)

    # The endpoint itself as a live asset.
    score = scan.get("score", 100)
    endpoint = scan.get("endpoint") or "this install"
    exposure = max(0, min(100, 100 - score))
    kevn = len(scan.get("kev_matches") or [])
    crit = exposure >= 55 or kevn > 0
    await db.assets.insert_one({
        "org_id": org_id, "derived": True, "ref": "AST-ENDPOINT",
        "name": endpoint, "type": "Web application (this install)",
        "criticality": "Critical" if crit else ("High" if exposure >= 30 else "Medium"),
        "exposure": exposure, "owner": "Platform", "status": "Monitored — live scan",
        "source": "Live self-scan", "freshness": "live",
    })

    # Health index from the live scan score + per-category penalties.
    cat_scores = {c: 100 for c in _HEALTH_CATS}
    for f in fails:
        c = _CAT.get(f.get("category"), "Vulnerability Mgmt")
        cat_scores[c] = max(0, cat_scores[c] - _SEV_PEN.get(f.get("severity"), 0))
    components = [{"name": c, "score": cat_scores[c], "weight": _WEIGHTS[c],
                  "trend": "flat", "confidence": 0.9} for c in _HEALTH_CATS]

    prev = await db.health_index.find_one({"org_id": org_id}) or {}
    hist = [h for h in (prev.get("history") or []) if isinstance(h, dict)]
    month = datetime.now(timezone.utc).strftime("%b")
    hist = [h for h in hist if h.get("month") != month]
    hist.append({"month": month, "score": score, "security_score": score})
    hist = hist[-6:]

    await db.health_index.update_one(
        {"org_id": org_id},
        {"$set": {"org_id": org_id, "score": score, "grade": _grade(score),
                  "components": components, "computed_at": _now(),
                  "freshness": "live", "source": "live-scan", "history": hist}},
        upsert=True)

    return {"risks": len(risks), "assets": 1, "score": score, "endpoint": endpoint,
            "kev_matches": kevn}
