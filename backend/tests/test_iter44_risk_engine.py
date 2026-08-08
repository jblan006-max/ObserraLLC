"""Iter44 — Unified Risk Correlation Engine
Tests /api/risk-engine/{strategic,tactical,exposure,compliance},
task status + action endpoints, and /api/advisor/insight for the new dashboards.
"""
import os
import time
import pytest
import requests

def _read_frontend_env():
    try:
        with open("/app/frontend/.env") as f:
            for line in f:
                if line.startswith("REACT_APP_BACKEND_URL="):
                    return line.split("=", 1)[1].strip()
    except Exception:
        return ""
    return ""

BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or _read_frontend_env() or "").rstrip("/")
assert BASE_URL, "REACT_APP_BACKEND_URL not set"
EMAIL = "jblan2026@gmail.com"
PASSWORD = "Obserra2026!"


@pytest.fixture(scope="session")
def client():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login",
               json={"email": EMAIL, "password": PASSWORD}, timeout=30)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    # Reset dep-ecdsa to Open so tactical queue has tasks
    try:
        s.post(f"{BASE_URL}/api/risk-engine/task/dep-ecdsa/status",
               json={"status": "Open"}, timeout=30)
    except Exception:
        pass
    yield s
    # cleanup: reset dep-ecdsa to Open
    try:
        s.post(f"{BASE_URL}/api/risk-engine/task/dep-ecdsa/status",
               json={"status": "Open"}, timeout=30)
    except Exception:
        pass


# ---- Strategic lens ----
def test_strategic(client):
    r = client.get(f"{BASE_URL}/api/risk-engine/strategic", timeout=60)
    assert r.status_code == 200
    d = r.json()
    p = d["portfolio"]
    for k in ("residual_ale", "inherent_ale", "reduction_pct", "p90", "ratings_dist"):
        assert k in p, f"portfolio missing {k}"
    b = d["benchmark"]
    for k in ("industry", "industry_avg", "ratio", "position", "strategic_recommendation"):
        assert k in b, f"benchmark missing {k}"
    assert "drift" in d and "appetite" in d
    assert isinstance(d.get("top_risks"), list) and len(d["top_risks"]) >= 1
    tr = d["top_risks"][0]
    for k in ("rating", "score", "residual_ale", "remediation_roi", "peer", "exceeds_appetite"):
        assert k in tr, f"top_risk missing {k}"
    board = d.get("board_summary", "")
    assert isinstance(board, str) and len(board) > 20
    # Board summary mentions industry-median position
    assert "median" in board.lower() or "industry" in board.lower()


# ---- Tactical lens ----
def test_tactical(client):
    r = client.get(f"{BASE_URL}/api/risk-engine/tactical", timeout=60)
    assert r.status_code == 200
    d = r.json()
    tasks = d.get("tasks", [])
    assert len(tasks) >= 1
    dep = next((t for t in tasks if t["id"] == "dep-ecdsa"), None)
    assert dep is not None, "dep-ecdsa task not found"
    for k in ("status", "priority_score", "remediation_roi", "exploitability",
              "fix_path", "fix_script", "blast_radius", "sla_days"):
        assert k in dep, f"task missing {k}"
    assert dep["fix_script"] == "pip install --upgrade ecdsa && pip-audit"
    for k in ("ale_reduced", "roi", "cost", "target_residual"):
        assert k in dep["remediation_roi"]
    for k in ("score", "label", "basis"):
        assert k in dep["exploitability"]
    assert isinstance(dep["fix_path"], list) and len(dep["fix_path"]) > 0
    assert "pipeline" in d and "coverage" in d


# ---- Exposure lens ----
def test_exposure(client):
    r = client.get(f"{BASE_URL}/api/risk-engine/exposure", timeout=60)
    assert r.status_code == 200
    d = r.json()
    assets = d.get("assets", [])
    assert len(assets) >= 1
    a = assets[0]
    for k in ("effective_criticality", "exploitability", "blast_radius", "internet_facing", "vulns"):
        assert k in a, f"asset missing {k}"
    em = d.get("exposure_map", [])
    assert len(em) >= 1
    row = em[0]
    for k in ("id", "cve_ids", "asset_name", "exploitability", "blast_radius", "residual_ale"):
        assert k in row, f"exposure_map missing {k}"
    assert "appetite" in d


# ---- Compliance lens ----
def test_compliance(client):
    r = client.get(f"{BASE_URL}/api/risk-engine/compliance", timeout=60)
    assert r.status_code == 200
    d = r.json()
    items = d.get("items", [])
    assert len(items) >= 1
    it = items[0]
    for k in ("area", "rating", "score", "probability", "impact", "compliance_pct"):
        assert k in it, f"compliance item missing {k}"


# ---- Task status endpoint ----
def test_task_status_transitions(client):
    # ensure baseline Open
    client.post(f"{BASE_URL}/api/risk-engine/task/dep-ecdsa/status",
                json={"status": "Open"}, timeout=30)

    # Open -> In Progress
    r = client.post(f"{BASE_URL}/api/risk-engine/task/dep-ecdsa/status",
                    json={"status": "In Progress"}, timeout=30)
    assert r.status_code == 200
    d = r.json()
    assert d.get("ok") is True
    assert d.get("status") == "In Progress"
    assert "portfolio_before" in d and "portfolio_after" in d
    assert "risk_reduced" in d

    # -> Remediated should DROP residual_ale
    r = client.post(f"{BASE_URL}/api/risk-engine/task/dep-ecdsa/status",
                    json={"status": "Remediated"}, timeout=30)
    assert r.status_code == 200
    d = r.json()
    assert d["status"] == "Remediated"
    assert d["portfolio_after"]["residual_ale"] < d["portfolio_before"]["residual_ale"], \
        f"residual_ale did not drop: {d['portfolio_before']['residual_ale']} -> {d['portfolio_after']['residual_ale']}"
    assert d["risk_reduced"] > 0

    # Reset to Open -> restores ~9.6M
    r = client.post(f"{BASE_URL}/api/risk-engine/task/dep-ecdsa/status",
                    json={"status": "Open"}, timeout=30)
    assert r.status_code == 200
    d = r.json()
    after_open = d["portfolio_after"]["residual_ale"]
    assert 8_000_000 < after_open < 11_000_000, f"expected ~9.6M residual after reset, got {after_open}"


# ---- Task action endpoint ----
def test_task_action_remediate(client):
    # ensure baseline Open
    client.post(f"{BASE_URL}/api/risk-engine/task/dep-ecdsa/status",
                json={"status": "Open"}, timeout=30)

    r = client.post(f"{BASE_URL}/api/risk-engine/task/dep-ecdsa/action",
                    json={"action": "remediate"}, timeout=30)
    assert r.status_code == 200
    d = r.json()
    assert d["status"] == "Remediated"
    assert d.get("fix_script") == "pip install --upgrade ecdsa && pip-audit"
    assert "connector" in d and "note" in d["connector"]
    before = d["portfolio_before"]["residual_ale"]
    after = d["portfolio_after"]["residual_ale"]
    assert d["risk_reduced"] > 0
    assert before > after
    # ALE approx 9.6M -> ~2.88M
    assert 8_000_000 < before < 11_000_000
    assert 1_500_000 < after < 4_500_000, f"expected ~2.88M after remediate, got {after}"

    # isolate action -> In Progress
    r = client.post(f"{BASE_URL}/api/risk-engine/task/dep-ecdsa/action",
                    json={"action": "isolate"}, timeout=30)
    assert r.status_code == 200
    assert r.json()["status"] == "In Progress"

    # CRITICAL cleanup: reset to Open
    r = client.post(f"{BASE_URL}/api/risk-engine/task/dep-ecdsa/status",
                    json={"status": "Open"}, timeout=30)
    assert r.status_code == 200
    restored = r.json()["portfolio_after"]["residual_ale"]
    assert 8_000_000 < restored < 11_000_000


# ---- Advisor insight (LLM) ----
def test_advisor_insight_remediation_center(client):
    r = client.post(f"{BASE_URL}/api/advisor/insight",
                    json={"dashboard": "Remediation Command Center"}, timeout=60)
    assert r.status_code == 200
    d = r.json()
    # summary or actions non-empty
    txt = str(d.get("summary") or "") + str(d.get("actions") or "") + str(d)
    assert len(txt) > 40, f"empty advisor response: {d}"


def test_advisor_insight_executive_briefing(client):
    r = client.post(f"{BASE_URL}/api/advisor/insight",
                    json={"dashboard": "Executive Briefing"}, timeout=60)
    assert r.status_code == 200
    d = r.json()
    txt = str(d.get("summary") or "") + str(d.get("actions") or "") + str(d)
    assert len(txt) > 40, f"empty advisor response: {d}"
