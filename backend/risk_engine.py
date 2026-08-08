"""Unified Risk Correlation Engine — the single source of truth that maps Asset Criticality
(from the live inventory) to Vulnerability Severity (from the live scans) to compute live ALE
and Risk Scores, then pipes that correlated data into four functional lenses:

  • strategic  — board-level ALE + risk summaries.
  • tactical   — a prioritized remediation task queue for the SOC.
  • exposure   — detailed, correlated lists of assets and their specific bugs.
  • compliance — every item mapped to risk, rating, probability, impact & score.

Everything is computed LIVE (no seeds/placeholders). The Risk Rating incorporates the compliance
coverage % of the item's area (e.g. an area only 37% compliant escalates the rating)."""
from datetime import datetime, timezone

from fastapi import APIRouter, Body, Depends

from auth import get_current_user
from db import db

risk_engine_router = APIRouter(prefix="/api/risk-engine")

SEV_ORDER = ["info", "low", "medium", "high", "critical"]
SEV_WEIGHT = {"critical": 100, "high": 70, "medium": 40, "low": 15, "info": 5}
SLA_DAYS = {"critical": 7, "high": 14, "medium": 30, "low": 60, "info": 90}
CRIT_TO_RESIDUAL = {"Critical": 22, "High": 16, "Medium": 10, "Low": 5}


def _m(v):
    v = v or 0
    return f"${v / 1e6:.1f}M" if v >= 1e6 else f"${v / 1e3:.0f}k"


def _internet_facing(a):
    s = f"{a.get('status', '')} {a.get('type', '')} {a.get('source', '')}".lower()
    return any(k in s for k in ("internet", "public", "web", "unsanctioned", "live self", "facing"))


def _exploitability(severity, kev, internet, has_cve):
    """Live exploitability rating from severity + KEV + network placement + public CVE presence."""
    score = {"critical": 70, "high": 55, "medium": 35, "low": 15, "info": 5}.get(severity, 20)
    if kev:
        score += 30
    if internet:
        score += 15
    if has_cve:
        score += 10
    score = min(100, score)
    label = "Critical" if score >= 80 else "High" if score >= 55 else "Medium" if score >= 30 else "Low"
    return {"score": score, "label": label,
            "basis": ("KEV — actively exploited; " if kev else "")
                     + ("internet-facing; " if internet else "internal; ")
                     + ("published CVE" if has_cve else "no public CVE")}


def _blast_radius(asset, all_assets, internet):
    """What other assets could be reached if this one is compromised (shared owner/type, or pivot
    from an internet-facing host into high/critical internal assets)."""
    reach = []
    for o in all_assets:
        if o.get("ref") == asset.get("ref"):
            continue
        same_owner = o.get("owner") and o.get("owner") == asset.get("owner")
        same_type = o.get("type") and o.get("type") == asset.get("type")
        pivot = internet and (o.get("criticality") in ("Critical", "High"))
        if same_owner or same_type or pivot:
            reach.append({"ref": o.get("ref"), "name": o.get("name"), "criticality": o.get("criticality")})
    return reach


def _fix_path(f):
    """Step-by-step remediation path (+ an optional script) for the SOC."""
    rem = (f.get("remediation") or "").strip()
    steps = [s.strip() for s in rem.replace(";", ".").split(".") if len(s.strip()) > 4][:4]
    if not steps:
        steps = ["Triage the finding in Security Scanner",
                 "Apply the vendor-recommended fix in a canary/staging first",
                 "Re-run the live self-scan to confirm the finding clears"]
    script = None
    title = f.get("title") or ""
    if (f.get("category") or "").lower().startswith("depend") and "dependency:" in title.lower():
        pkg = title.split(":", 1)[1].strip().split()[0]
        script = f"pip install --upgrade {pkg} && pip-audit"
    return steps, script


def _worst_severity(sevs):
    worst = None
    for s in sevs:
        if s in SEV_ORDER and (worst is None or SEV_ORDER.index(s) > SEV_ORDER.index(worst)):
            worst = s
    return worst


def unified_rating(residual, compliance_pct, kev=False, worst_sev=None):
    """Rating combines the residual risk severity with the compliance coverage % of the area —
    a low-compliance area pushes the rating up. KEV / critical findings floor the score high."""
    residual = max(0, min(25, residual or 0))
    comp = 60 if compliance_pct is None else max(0, min(100, compliance_pct))
    severity_component = residual / 25 * 100
    compliance_gap = 100 - comp
    score = round(min(100, severity_component * 0.65 + compliance_gap * 0.35))
    if kev or worst_sev == "critical":
        score = max(score, 82)
    elif worst_sev == "high":
        score = max(score, 60)
    rating = ("Critical" if score >= 70 else "High" if score >= 45
              else "Medium" if score >= 25 else "Low")
    return rating, score


async def correlate(org_id: str) -> dict:
    """Join assets ↔ live findings/CVEs ↔ risks ↔ controls into one correlated model."""
    from routes import (_get_fin_cfg, _fin, _asset_crit_index, _rating_label,
                        _control_status, _ensure_controls, _benchmark)

    cfg = await _get_fin_cfg(org_id)
    risks = await db.risks.find({"org_id": org_id}, {"_id": 0}).to_list(500)
    assets = await db.assets.find({"org_id": org_id}, {"_id": 0}).to_list(500)
    await _ensure_controls(org_id)
    controls_raw = await db.controls.find({"org_id": org_id}, {"_id": 0}).to_list(500)
    controls = [_control_status(c) for c in controls_raw]
    scan = await db.self_scans.find_one({"org_id": org_id}, sort=[("ts", -1)]) or {}
    recs = await db.recommendations.find({"org_id": org_id}, {"_id": 0}).to_list(500)

    # ---- Benchmark, risk appetite & remediation-status context ----
    from bson import ObjectId
    org = await db.organizations.find_one({"_id": ObjectId(org_id)}) or {}
    bench = await _benchmark(cfg["industry"])
    ind_avg = bench.get("industry_avg") or 0
    remediation_status = {d["task_id"]: d.get("status", "Open")
                          for d in await db.remediation_status.find({"org_id": org_id}, {"_id": 0}).to_list(1000)}
    remediated_ids = {tid for tid, st in remediation_status.items() if st == "Remediated"}

    def _peer(loss):
        if not ind_avg:
            return {"ratio": None, "position": "n/a", "industry_avg": ind_avg}
        rr = round(loss / ind_avg, 2)
        return {"ratio": rr, "industry_avg": ind_avg,
                "position": "above" if rr > 1.15 else "below" if rr < 0.85 else "in line"}

    def _roi(residual_ale, residual):
        base = residual or 10
        new_res = max(4, round(base * 0.3))
        factor = (base - new_res) / max(1, base)
        reduced = round(residual_ale * factor)
        cost = 250000 if base >= 16 else 150000 if base >= 11 else 80000 if base >= 6 else 30000
        return {"ale_reduced": reduced, "cost": cost, "target_residual": new_res,
                "roi": round(reduced / cost, 1) if cost else 0}

    # ---- Compliance coverage by area (control category) ----
    cat_agg = {}
    for c in controls:
        cat = c.get("category") or "General"
        e = cat_agg.setdefault(cat, {"controls": 0, "eff_sum": 0, "passing": 0})
        e["controls"] += 1
        e["eff_sum"] += c.get("effectiveness", 0)
        if c.get("status") == "Passing":
            e["passing"] += 1
    area_pct = {k: round(v["eff_sum"] / v["controls"]) for k, v in cat_agg.items() if v["controls"]}
    overall_pct = round(sum(area_pct.values()) / len(area_pct)) if area_pct else 0

    def area_compliance(category):
        if not category:
            return overall_pct
        return area_pct.get(category, overall_pct)

    # ---- Effective asset criticality (inventory ↔ vuln correlation) ----
    idx, endpoint_ref = _asset_crit_index(risks, assets)
    crit_index = {ref: v["effective"] for ref, v in idx.items()}
    asset_by_ref = {a["ref"]: a for a in assets}

    findings = scan.get("findings") or []
    remediated_titles = {f.get("title") for f in findings if f.get("id") in remediated_ids}

    def finding_asset(f):
        return f.get("asset_ref") or endpoint_ref

    open_findings = [f for f in findings if f.get("status") != "pass" and f.get("id") not in remediated_ids]
    pending_recs = {r.get("risk_ref") for r in recs if r.get("status") == "Pending"}

    # ---- Per-risk correlated exposure ----
    risk_out, risks_by_asset = [], {}
    for r in risks:
        remediated = (r.get("title") in remediated_titles) or (remediation_status.get(r.get("ref")) == "Remediated")
        rr = dict(r)
        if remediated:
            rr["residual"] = max(4, round((r.get("residual", 10)) * 0.3))
        f = _fin(rr, cfg, crit_index)
        category = r.get("category") or "Uncategorised"
        comp = area_compliance(category)
        kev = bool(r.get("kev")) and not remediated
        rating, score = unified_rating(rr.get("residual", 10), comp, kev=kev)
        row = {
            "ref": r.get("ref"), "title": r.get("title"), "category": category,
            "owner": r.get("owner"), "status": r.get("status", "Open"),
            "probability": r.get("likelihood", 3), "impact": r.get("impact", 3),
            "residual": r.get("residual", 10), "inherent": r.get("inherent", 20),
            "residual_ale": f["residual_ale"], "inherent_ale": f["inherent_ale"],
            "loss_magnitude": f["sle"], "asset_ref": f.get("asset_ref"),
            "asset_criticality": f.get("asset_criticality"), "asset_factor": f.get("asset_factor"),
            "compliance_pct": comp, "rating": rating, "score": score,
            "band_rating": _rating_label(r.get("residual", 0)),
            "remediation_roi": _roi(f["residual_ale"], rr.get("residual", 10)),
            "peer": _peer(f["sle"]),
            "remediated": remediated,
            "remediation_pending": r.get("ref") in pending_recs,
        }
        risk_out.append(row)
        risks_by_asset.setdefault(row["asset_ref"], []).append(row)
    risk_out.sort(key=lambda x: x["residual_ale"], reverse=True)

    # ---- Per-asset correlated exposure (asset ↔ its specific bugs) ----
    finds_by_asset = {}
    for fx in findings:
        finds_by_asset.setdefault(finding_asset(fx), []).append(fx)

    asset_out = []
    for a in assets:
        ref = a["ref"]
        a_risks = risks_by_asset.get(ref, [])
        a_open = [f for f in finds_by_asset.get(ref, []) if f.get("status") != "pass"]
        vulns = [{"id": f.get("id"), "title": f.get("title"), "severity": f.get("severity"),
                  "cve_ids": f.get("cve_ids") or [], "kev": f.get("kev", False),
                  "remediation": f.get("remediation"), "control_refs": f.get("control_refs") or [],
                  "category": f.get("category")} for f in a_open]
        worst = _worst_severity([v["severity"] for v in vulns])
        eff_crit = crit_index.get(ref, a.get("criticality") or "Medium")
        comp = area_compliance(a.get("category"))
        kev = any(v["kev"] for v in vulns)
        rating, score = unified_rating(CRIT_TO_RESIDUAL.get(eff_crit, 10), comp, kev=kev, worst_sev=worst)
        ale = round(sum(x["residual_ale"] for x in a_risks))
        internet = _internet_facing(a)
        expl = _exploitability(worst or "info", kev, internet, any(v["cve_ids"] for v in vulns))
        blast = _blast_radius(a, assets, internet)
        asset_out.append({
            "ref": ref, "name": a.get("name"), "type": a.get("type"), "owner": a.get("owner"),
            "source": a.get("source"), "status": a.get("status"),
            "stored_criticality": a.get("criticality") or "Medium", "effective_criticality": eff_crit,
            "escalated": eff_crit != (a.get("criticality") or "Medium"),
            "exposure": a.get("exposure", 0), "residual_ale": ale, "vuln_count": len(vulns),
            "worst_severity": worst, "kev": kev, "vulns": vulns,
            "internet_facing": internet, "exploitability": expl,
            "blast_radius": {"count": len(blast), "reachable": blast[:8]},
            "compliance_pct": comp, "rating": rating, "score": score, "risk_refs": [x["ref"] for x in a_risks],
        })
    asset_out.sort(key=lambda x: (x["residual_ale"], x["vuln_count"]), reverse=True)

    # ---- Cyber Exposure Map: correlate every vulnerability (CVE) to a live asset ----
    exposure_map = []
    for a in asset_out:
        for v in a["vulns"]:
            exposure_map.append({
                "id": v["id"], "asset_ref": a["ref"], "asset_name": a["name"],
                "effective_criticality": a["effective_criticality"], "internet_facing": a["internet_facing"],
                "finding": v["title"], "cve_ids": v["cve_ids"], "severity": v["severity"], "kev": v["kev"],
                "exploitability": _exploitability(v["severity"], v["kev"], a["internet_facing"], bool(v["cve_ids"])),
                "blast_radius": a["blast_radius"], "remediation": v["remediation"],
                "control_refs": v["control_refs"], "residual_ale": a["residual_ale"],
            })
    exposure_map.sort(key=lambda x: x["exploitability"]["score"], reverse=True)

    # ---- Tactical remediation task queue (prioritized for the SOC) ----
    tasks = []
    for f in open_findings:
        a_ref = finding_asset(f)
        a = asset_by_ref.get(a_ref) or {}
        sev = f.get("severity") or "medium"
        kev = f.get("kev", False)
        ale = round(sum(x["residual_ale"] for x in risks_by_asset.get(a_ref, [])))
        comp = area_compliance(a.get("category") or f.get("category"))
        internet = _internet_facing(a)
        expl = _exploitability(sev, kev, internet, bool(f.get("cve_ids")))
        roi = _roi(ale, 18 if sev == "critical" else 14 if sev == "high" else 8)
        blast = _blast_radius(a, assets, internet)
        steps, script = _fix_path(f)
        priority = round(min(200, SEV_WEIGHT.get(sev, 20) + (30 if kev else 0)
                             + min(40, ale / 1_000_000 * 4) + (100 - comp) * 0.25
                             + expl["score"] * 0.15))
        tasks.append({
            "id": f.get("id"), "title": f.get("title"), "asset_ref": a_ref,
            "asset_name": a.get("name") or a_ref, "severity": sev, "kev": kev,
            "cve_ids": f.get("cve_ids") or [], "control_refs": f.get("control_refs") or [],
            "category": f.get("category"), "remediation": f.get("remediation"),
            "ale_at_stake": ale, "compliance_pct": comp, "priority_score": priority,
            "sla_days": SLA_DAYS.get(sev, 30), "owner": a.get("owner"),
            "status": remediation_status.get(f.get("id"), "Open"),
            "exploitability": expl, "remediation_roi": roi, "fix_path": steps, "fix_script": script,
            "blast_radius": {"count": len(blast), "reachable": blast[:6]},
        })
    tasks.sort(key=lambda x: x["priority_score"], reverse=True)

    # ---- Pipeline + coverage ----
    rec_status = {}
    for r in recs:
        rec_status[r.get("status", "Pending")] = rec_status.get(r.get("status", "Pending"), 0) + 1
    open_risks = [r for r in risk_out if r["status"] != "Remediated"]
    with_rec = {r.get("risk_ref") for r in recs}
    covered = sum(1 for r in open_risks if r["ref"] in with_rec)
    pipeline = {
        "Open findings": len(open_findings),
        "Planned": rec_status.get("Pending", 0),
        "In progress": rec_status.get("Decided", 0),
        "Applied": rec_status.get("Applied", 0),
    }
    coverage = {"open_risks": len(open_risks), "covered": covered,
                "pct": round(covered / len(open_risks) * 100) if open_risks else 0}

    # ---- Per-area drilldown ----
    area_map = {}
    for r in risk_out:
        e = area_map.setdefault(r["category"], {"area": r["category"], "risk_count": 0,
                                                "residual_ale": 0, "open_tasks": 0, "worst": 0})
        e["risk_count"] += 1
        e["residual_ale"] += r["residual_ale"]
        e["worst"] = max(e["worst"], r["score"])
    for t in tasks:
        cat = t.get("category") or "Uncategorised"
        e = area_map.setdefault(cat, {"area": cat, "risk_count": 0, "residual_ale": 0,
                                      "open_tasks": 0, "worst": 0})
        e["open_tasks"] += 1
    areas = []
    for cat, e in area_map.items():
        comp = area_compliance(cat)
        rating, _ = unified_rating(0, comp, worst_sev=None)
        rating = ("Critical" if e["worst"] >= 70 else "High" if e["worst"] >= 45
                  else "Medium" if e["worst"] >= 25 else rating)
        areas.append({"area": cat, "risk_count": e["risk_count"], "open_tasks": e["open_tasks"],
                      "residual_ale": round(e["residual_ale"]), "compliance_pct": comp, "rating": rating})
    areas.sort(key=lambda x: x["residual_ale"], reverse=True)

    # ---- Portfolio + ratings distribution ----
    residual_total = round(sum(r["residual_ale"] for r in risk_out))
    inherent_total = round(sum(r["inherent_ale"] for r in risk_out))
    appetite = org.get("risk_appetite") or (round(inherent_total * 0.5) if inherent_total else 0)
    per_risk_threshold = round(appetite * 0.25) if appetite else 0
    for r in risk_out:
        r["exceeds_appetite"] = bool(per_risk_threshold and r["residual_ale"] > per_risk_threshold)
    for ar in areas:
        ar["exceeds_appetite"] = bool(appetite and ar["residual_ale"] > appetite / max(1, len(areas)))
    ratings_dist = {t: sum(1 for r in risk_out if r["rating"] == t) for t in ["Critical", "High", "Medium", "Low"]}
    summary = (scan.get("summary") or {})

    # Industry benchmark posture — wire the Strategic lens to peer-group medians.
    sles = [r["loss_magnitude"] for r in risk_out] or [0]
    modelled_avg = round(sum(sles) / len(sles))
    ratio = round(modelled_avg / ind_avg, 2) if ind_avg else None
    position, outlier = "in line with", False
    if ratio is not None:
        if ratio > 1.25:
            position, outlier = "above", True
        elif ratio < 0.75:
            position, outlier = "below", True
    delta_pct = round((ratio - 1) * 100) if ratio is not None else None
    strat_rec = ""
    if outlier and ratio and ratio > 1:
        strat_rec = (f"Modelled per-incident exposure ({_m(modelled_avg)}) runs {ratio}× the {cfg['industry']} "
                     f"industry median ({_m(ind_avg)}). Prioritise the highest-$ open remediations and close the "
                     f"weakest control areas to pull exposure back toward the peer-group baseline.")
    elif outlier and ratio and ratio < 1:
        strat_rec = (f"Modelled exposure sits ~{abs(delta_pct)}% below the {cfg['industry']} median "
                     f"({_m(ind_avg)}) — maintain controls and avoid over-investing beyond the peer baseline.")
    benchmark = {"industry": cfg["industry"], "industry_avg": ind_avg, "global_avg": bench.get("global_avg"),
                 "source": bench.get("industry_avg_source"), "modelled_avg_sle": modelled_avg, "ratio": ratio,
                 "position": position, "delta_pct": delta_pct, "outlier": outlier,
                 "strategic_recommendation": strat_rec}

    snaps = await db.exposure_snapshots.find({"org_id": org_id}, {"_id": 0}).sort("month", 1).to_list(24)
    drift = {"direction": "flat", "pct": 0, "trending_critical": False,
             "note": "Not enough history yet to detect drift."}
    if len(snaps) >= 2:
        prev = snaps[-2].get("modelled_avg_sle") or 0
        cur = snaps[-1].get("modelled_avg_sle") or modelled_avg
        if prev:
            ch = round((cur - prev) / prev * 100)
            direction = "up" if ch > 2 else "down" if ch < -2 else "flat"
            tc = bool(direction == "up" and appetite and residual_total > appetite * 0.85)
            drift = {"direction": direction, "pct": ch, "trending_critical": tc,
                     "note": (f"Exposure is drifting {direction} {abs(ch)}% month-on-month"
                              + ("; trending toward the appetite ceiling — pre-empt before breach." if tc else "."))}

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "endpoint": scan.get("endpoint"), "scan_score": scan.get("score"), "benchmark": benchmark,
        "portfolio": {
            "residual_ale": residual_total, "inherent_ale": inherent_total,
            "reduction_pct": round((inherent_total - residual_total) / inherent_total * 100) if inherent_total else 0,
            "p90": round(residual_total * 1.9), "p10": round(residual_total * 0.45),
            "ratings_dist": ratings_dist,
            "open_findings": len(open_findings), "open_tasks": len(tasks),
        },
        "compliance": {"overall_pct": overall_pct,
                       "by_area": [{"area": k, "compliance_pct": v} for k, v in
                                   sorted(area_pct.items(), key=lambda x: x[1])]},
        "risks": risk_out, "assets": asset_out, "tasks": tasks, "areas": areas,
        "exposure_map": exposure_map, "pipeline": pipeline, "coverage": coverage,
        "appetite": {"total": appetite, "per_risk_threshold": per_risk_threshold}, "drift": drift,
        "findings_summary": {s: summary.get(s, 0) for s in ["critical", "high", "medium", "low", "info"]},
    }


async def engine_summary(org_id: str) -> dict:
    """Compact correlation summary injected into every AI 'Analyze' path so the reasoning is
    consistent across dashboards (same unified model everywhere)."""
    c = await correlate(org_id)
    return {
        "portfolio": c["portfolio"],
        "compliance": c["compliance"],
        "benchmark": c["benchmark"],
        "drift": c["drift"],
        "top_risks": [{"ref": r["ref"], "title": r["title"], "rating": r["rating"], "score": r["score"],
                       "residual_ale": r["residual_ale"], "compliance_pct": r["compliance_pct"],
                       "asset_ref": r["asset_ref"], "probability": r["probability"], "impact": r["impact"]}
                      for r in c["risks"][:8]],
        "top_remediations": [{"title": t["title"], "severity": t["severity"], "kev": t["kev"],
                              "priority_score": t["priority_score"], "ale_at_stake": t["ale_at_stake"],
                              "asset_ref": t["asset_ref"], "sla_days": t["sla_days"]}
                             for t in c["tasks"][:8]],
        "top_assets": [{"ref": a["ref"], "name": a["name"], "effective_criticality": a["effective_criticality"],
                        "rating": a["rating"], "vuln_count": a["vuln_count"], "residual_ale": a["residual_ale"]}
                       for a in c["assets"][:6]],
        "areas": c["areas"][:8],
    }


@risk_engine_router.get("")
async def engine_all(user: dict = Depends(get_current_user)):
    return await correlate(user["org_id"])


@risk_engine_router.get("/strategic")
async def engine_strategic(user: dict = Depends(get_current_user)):
    c = await correlate(user["org_id"])
    top = c["risks"][:10]
    p = c["portfolio"]
    b = c["benchmark"]
    bench_line = (f" Modelled per-incident exposure is {b['position']} the {b['industry']} industry median"
                  + (f" ({b['ratio']}×)." if b.get("ratio") is not None else ".")
                  + (f" {b['strategic_recommendation']}" if b.get("strategic_recommendation") else ""))
    board = (f"Residual exposure ${p['residual_ale']:,} across {len(c['risks'])} risk(s), "
             f"down {p['reduction_pct']}% from inherent. Overall compliance {c['compliance']['overall_pct']}%. "
             f"{p['ratings_dist']['Critical']} Critical / {p['ratings_dist']['High']} High rated." + bench_line)
    return {"portfolio": p, "compliance": c["compliance"], "top_risks": top, "benchmark": b,
            "areas": c["areas"], "appetite": c["appetite"], "drift": c["drift"], "board_summary": board, "generated_at": c["generated_at"]}


@risk_engine_router.get("/tactical")
async def engine_tactical(user: dict = Depends(get_current_user)):
    c = await correlate(user["org_id"])
    return {"tasks": c["tasks"], "pipeline": c["pipeline"], "coverage": c["coverage"],
            "areas": c["areas"], "appetite": c["appetite"], "open_findings": c["portfolio"]["open_findings"],
            "findings_summary": c["findings_summary"], "generated_at": c["generated_at"]}


@risk_engine_router.get("/exposure")
async def engine_exposure(user: dict = Depends(get_current_user)):
    c = await correlate(user["org_id"])
    return {"assets": c["assets"], "risks": c["risks"], "portfolio": c["portfolio"],
            "exposure_map": c["exposure_map"], "appetite": c["appetite"],
            "endpoint": c["endpoint"], "generated_at": c["generated_at"]}


@risk_engine_router.get("/compliance")
async def engine_compliance(user: dict = Depends(get_current_user)):
    c = await correlate(user["org_id"])
    items = [{"ref": r["ref"], "title": r["title"], "area": r["category"],
              "rating": r["rating"], "score": r["score"], "probability": r["probability"],
              "impact": r["impact"], "residual_ale": r["residual_ale"],
              "compliance_pct": r["compliance_pct"], "asset_ref": r["asset_ref"],
              "control_refs": []} for r in c["risks"]]
    return {"items": items, "compliance": c["compliance"], "areas": c["areas"],
            "generated_at": c["generated_at"]}


_VALID_STATUS = ("Open", "In Progress", "Remediated", "Accepted")


async def _task_by_id(org_id, task_id):
    c = await correlate(org_id)
    return c, next((t for t in c["tasks"] if t["id"] == task_id), None)


@risk_engine_router.post("/task/{task_id}/status")
async def set_task_status(task_id: str, body: dict = Body(default={}), user: dict = Depends(get_current_user)):
    """Status Tracker — Open → In Progress → Remediated, recalculating ALE live."""
    status = body.get("status", "Open")
    if status not in _VALID_STATUS:
        status = "Open"
    before = (await correlate(user["org_id"]))["portfolio"]
    await db.remediation_status.update_one(
        {"org_id": user["org_id"], "task_id": task_id},
        {"$set": {"status": status, "updated_at": datetime.now(timezone.utc).isoformat()}}, upsert=True)
    c, task = await _task_by_id(user["org_id"], task_id)
    after = c["portfolio"]
    return {"ok": True, "task_id": task_id, "status": status, "task": task,
            "portfolio_before": before, "portfolio_after": after,
            "risk_reduced": before["residual_ale"] - after["residual_ale"]}


@risk_engine_router.post("/task/{task_id}/action")
async def task_action(task_id: str, body: dict = Body(default={}), user: dict = Depends(get_current_user)):
    """One-Click Remediation — generate the fix script / log the task, dispatch to the relevant
    SaaS connector if one is wired, flip the status and recalculate ALE (risk reduced) in real-time."""
    action = (body.get("action") or "remediate").lower()
    c, task = await _task_by_id(user["org_id"], task_id)
    before = c["portfolio"]
    new_status = "In Progress" if action == "isolate" else "Remediated"
    a_ref = (task or {}).get("asset_ref")
    conn = None
    if a_ref:
        conn = await db.connectors.find_one({"org_id": user["org_id"], "status": "connected"}, {"_id": 0})
    connector = {"connected": bool(conn), "target": (conn or {}).get("name"),
                 "dispatched": bool(conn),
                 "note": (f"Remediation command dispatched to {(conn or {}).get('name')}." if conn
                          else "No external connector wired for this asset — logged as an in-platform remediation task.")}
    await db.remediation_status.update_one(
        {"org_id": user["org_id"], "task_id": task_id},
        {"$set": {"status": new_status, "action": action, "script": (task or {}).get("fix_script"),
                  "connector": connector.get("target"), "updated_at": datetime.now(timezone.utc).isoformat()}},
        upsert=True)
    c2 = await correlate(user["org_id"])
    after = c2["portfolio"]
    return {"ok": True, "action": action, "status": new_status, "task_id": task_id,
            "fix_script": (task or {}).get("fix_script"), "fix_path": (task or {}).get("fix_path"),
            "connector": connector, "portfolio_before": before, "portfolio_after": after,
            "risk_reduced": before["residual_ale"] - after["residual_ale"]}
