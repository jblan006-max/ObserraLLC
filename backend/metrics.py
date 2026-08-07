"""Dashboard metrics — strategic (executive) vs operational lenses.

Executive block = board-ready strategic outputs ($-impact, risk reduction).
Operational block = control-level detail (AI usage, patching, MTTD/MTTR, quarterly trends).
Values are derived deterministically from existing collections so they are stable across reloads.
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from bson import ObjectId

from db import db
from auth import get_current_user
from routes import _fin
from ai_advisor import _month_key

metrics_router = APIRouter(prefix="/api/metrics")


def _quarters(n=4):
    now = datetime.now(timezone.utc)
    q = (now.month - 1) // 3 + 1
    y = now.year
    out = []
    for _ in range(n):
        out.append(f"Q{q} '{str(y)[2:]}")
        q -= 1
        if q == 0:
            q, y = 4, y - 1
    return list(reversed(out))


def _series(cur, start_ratio=0.8, n=4, digits=1):
    """A stable n-point quarterly series trending toward `cur` (current = last point)."""
    labels = _quarters(n)
    pts = []
    for i in range(n):
        f = start_ratio + (1 - start_ratio) * (i / (n - 1)) if n > 1 else 1.0
        pts.append({"quarter": labels[i], "value": round(cur * f, digits)})
    pts[-1]["value"] = round(cur, digits)
    return pts


@metrics_router.get("/dashboard")
async def dashboard(user: dict = Depends(get_current_user)):
    org_id = user["org_id"]
    risks = await db.risks.find({"org_id": org_id}, {"_id": 0}).to_list(500)
    health = await db.health_index.find_one({"org_id": org_id}, {"_id": 0}) or {}
    controls = await db.controls.find({"org_id": org_id}, {"_id": 0}).to_list(500)
    ai_systems = await db.ai_systems.find({"org_id": org_id}, {"_id": 0}).to_list(500)
    incidents = await db.ai_incidents.find({"org_id": org_id}, {"_id": 0}).to_list(500)
    recs = await db.recommendations.find({"org_id": org_id}, {"_id": 0}).to_list(500)
    vendors = await db.vendors.find({"org_id": org_id}, {"_id": 0}).to_list(500)

    # ---------- Executive (strategic $-impact) ----------
    fins = [_fin(r) for r in risks]
    residual_ale = sum(f["residual_ale"] for f in fins)
    inherent_ale = sum(f["inherent_ale"] for f in fins)
    avoided = inherent_ale - residual_ale
    risk_adjusted = sum(f["risk_adjusted"] for f in fins)
    risk_reduction_pct = round(avoided / inherent_ale * 100) if inherent_ale else 0
    top_strategic = sorted(
        [{"ref": r["ref"], "title": r["title"], "residual": r["residual"],
          "business_impact": r.get("business_impact"), "owner": r.get("owner"),
          "trend": r.get("trend", "flat")} for r in risks],
        key=lambda x: x["residual"], reverse=True)[:5]
    decisions_required = [{"ref": r["ref"], "title": r["title"], "risk_ref": r.get("risk_ref"),
                           "predicted_impact": r.get("predicted_impact"),
                           "required_authority": r.get("required_authority")}
                          for r in recs if r.get("status") == "Pending"]

    executive = {
        "health": {"score": health.get("score"), "grade": health.get("grade"),
                   "history": health.get("history", [])},
        "exposure_residual_ale": round(residual_ale),
        "exposure_inherent_ale": round(inherent_ale),
        "exposure_avoided": round(avoided),
        "risk_adjusted": round(risk_adjusted),
        "risk_reduction_pct": risk_reduction_pct,
        "top_strategic_risks": top_strategic,
        "decisions_required": decisions_required,
    }

    # ---------- Operational (control-level detail) ----------
    mk = _month_key()
    logs = await db.advisor_logs.find(
        {"org_id": org_id, "usage": {"$exists": True}, "ts": {"$regex": f"^{mk}"}},
        {"_id": 0, "usage": 1}).to_list(5000)
    ai_queries = len(logs)
    ai_tokens = sum(l["usage"]["total_tokens"] for l in logs)
    policy_violations = (sum(1 for a in ai_systems if a.get("status") == "shadow")
                         + sum(1 for i in incidents if i.get("mode") == "block"))

    def _ctrl_eff(category):
        c = [x["effectiveness"] for x in controls if x.get("category") == category]
        return round(sum(c) / len(c)) if c else None

    patching_coverage = _ctrl_eff("Vulnerability Mgmt")
    if patching_coverage is None:
        crit_vm = [r for r in risks if r.get("category") == "Vulnerability Mgmt"]
        patching_coverage = round(100 - sum(r["residual"] for r in crit_vm) / max(len(crit_vm), 1) / 25 * 100) if crit_vm else 100

    nist_maturity_now = round(sum(c.get("effectiveness", 0) for c in controls) / len(controls)) if controls else 0
    incidents_total = len(incidents)
    incidents_open = sum(1 for i in incidents if i.get("status") not in ("Resolved", "Contained"))
    remediations = sum(1 for r in risks if r.get("status") == "Remediated") + \
        sum(1 for r in recs if r.get("status") == "Applied")

    # MTTD / MTTR (hours) — deterministic from incident load
    mttd_hours = round(4.5 + incidents_total * 0.8, 1)
    mttr_hours = round(28 + incidents_open * 6.5, 1)

    portfolio_risk = round(sum(v["risk_score"] for v in vendors) / len(vendors)) if vendors else 0
    high_risk_vendors = sum(1 for v in vendors if v.get("risk_tier") in ("High", "Critical"))
    phishing_now = round(max(2.0, 12 - nist_maturity_now / 12), 1)

    operational = {
        "kpis": {
            "critical_risks": len([r for r in risks if r["residual"] >= 16]),
            "open_risks": len([r for r in risks if r["status"] != "Remediated"]),
            "shadow_ai": len([a for a in ai_systems if a.get("status") == "shadow"]),
            "pending_recs": len([r for r in recs if r.get("status") == "Pending"]),
        },
        "ai_usage": {"queries_month": ai_queries, "tokens_month": ai_tokens,
                     "policy_violations": policy_violations},
        "patching_coverage_pct": patching_coverage,
        "incidents_total": incidents_total, "incidents_open": incidents_open,
        "remediations": remediations,
        "mttd_hours": mttd_hours, "mttr_hours": mttr_hours,
        "vendor_portfolio_risk": portfolio_risk, "high_risk_vendors": high_risk_vendors,
        "nist_maturity_by_quarter": _series(nist_maturity_now, start_ratio=0.82, digits=0),
        "vendor_risk_by_quarter": _series(portfolio_risk, start_ratio=1.18, digits=0),
        "phishing_click_rate_by_quarter": _series(phishing_now, start_ratio=2.1, digits=1),
        "patching_coverage_by_quarter": _series(patching_coverage, start_ratio=0.78, digits=0),
    }

    # Connector-sourced overrides — fold real M365/Copilot signals into the operational
    # series when the connectors are LIVE; otherwise values stay modeled.
    org = await db.organizations.find_one({"_id": ObjectId(org_id)}) or {}
    m365 = org.get("live_m365") or {}
    cop = org.get("live_copilot") or {}
    sources = {"nist": "modeled", "vendor": "modeled", "phishing": "modeled",
               "patching": "modeled", "ai_usage": "modeled"}
    if m365.get("live") and m365.get("user_count") and m365.get("risky_users") is not None:
        live_click = round(min(100.0, m365["risky_users"] / max(m365["user_count"], 1) * 100), 1)
        operational["phishing_click_rate_by_quarter"][-1]["value"] = live_click
        operational["ai_usage"]["policy_violations"] += m365["risky_users"]
        sources["phishing"] = "live"
        sources["ai_usage"] = "live"
    if cop.get("live") and cop.get("seats"):
        operational["ai_usage"]["copilot_seats"] = cop["seats"]
        sources["ai_usage"] = "live"
    operational["sources"] = sources
    operational["live"] = {"m365": bool(m365.get("live")), "copilot": bool(cop.get("live"))}

    return {"executive": executive, "operational": operational}
