"""P0 features: knowledge-graph, financials, simulate, evidence drill-down."""
import os
import requests
import pytest

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
ADMIN_EMAIL = "jblan2026@gmail.com"
ADMIN_PASSWORD = "Obserra2026!"


@pytest.fixture(scope="module")
def admin():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login",
               json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=15)
    assert r.status_code == 200, r.text
    return s


class TestKnowledgeGraph:
    def test_graph_returns_nodes_edges(self, admin):
        r = admin.get(f"{BASE_URL}/api/knowledge-graph")
        assert r.status_code == 200, r.text
        d = r.json()
        assert "nodes" in d and "edges" in d
        assert len(d["nodes"]) >= 20, f"expected ~25 nodes, got {len(d['nodes'])}"
        assert len(d["edges"]) > 0
        for n in d["nodes"]:
            assert "id" in n and "type" in n and "label" in n

    def test_preset_conf_risky_vendor(self, admin):
        r = admin.post(f"{BASE_URL}/api/knowledge-graph/query",
                       json={"preset": "conf_risky_vendor"})
        assert r.status_code == 200, r.text
        d = r.json()
        matches = d.get("matches") or d.get("matched_nodes") or []
        # Normalize: matches could be list of strings or list of dicts with id
        match_ids = [m if isinstance(m, str) else m.get("id") or m.get("ref") for m in matches]
        assert "AI-001" in match_ids and "AI-003" in match_ids, f"got {match_ids}"
        assert "explanation" in d and len(d["explanation"]) > 10

    def test_preset_shadow_exposure(self, admin):
        r = admin.post(f"{BASE_URL}/api/knowledge-graph/query",
                       json={"preset": "shadow_exposure"})
        assert r.status_code == 200
        d = r.json()
        matches = d.get("matches") or d.get("matched_nodes") or []
        match_ids = [m if isinstance(m, str) else m.get("id") or m.get("ref") for m in matches]
        # Should include shadow AI (AI-003)
        assert any("AI-003" in str(m) for m in match_ids), f"got {match_ids}"

    def test_preset_critical_risks(self, admin):
        r = admin.post(f"{BASE_URL}/api/knowledge-graph/query",
                       json={"preset": "critical_risks"})
        assert r.status_code == 200
        d = r.json()
        matches = d.get("matches") or d.get("matched_nodes") or []
        assert len(matches) >= 1


class TestFinancials:
    def test_financials_shape(self, admin):
        r = admin.get(f"{BASE_URL}/api/financials")
        assert r.status_code == 200, r.text
        d = r.json()
        assert "items" in d
        for k in ("total_residual_ale", "total_inherent_ale", "total_risk_adjusted", "avoided"):
            assert k in d, f"missing {k}"
            assert isinstance(d[k], (int, float))
        assert len(d["items"]) > 0
        for it in d["items"]:
            for k in ("sle", "aro", "inherent_ale", "residual_ale", "risk_adjusted"):
                assert k in it, f"missing {k} in item {it}"

    def test_totals_consistent(self, admin):
        d = admin.get(f"{BASE_URL}/api/financials").json()
        total_residual = sum(i["residual_ale"] for i in d["items"])
        assert abs(total_residual - d["total_residual_ale"]) < 1.0


class TestSimulate:
    def test_simulate_cr002(self, admin):
        r = admin.post(f"{BASE_URL}/api/simulate",
                       json={"risk_ref": "CR-002", "target_residual": 6})
        assert r.status_code == 200, r.text
        d = r.json()
        for k in ("exposure_before", "exposure_after", "expected_reduction",
                  "estimated_cost", "roi", "health_delta", "payback_months"):
            assert k in d, f"missing {k}: {d}"
        assert d["exposure_before"] >= d["exposure_after"]

    def test_simulate_unknown_risk(self, admin):
        r = admin.post(f"{BASE_URL}/api/simulate",
                       json={"risk_ref": "CR-999", "target_residual": 5})
        assert r.status_code in (404, 400)


class TestEvidence:
    def test_evidence_risk_cr002(self, admin):
        r = admin.get(f"{BASE_URL}/api/evidence/risk/CR-002")
        assert r.status_code == 200, r.text
        d = r.json()
        for k in ("metric", "value", "calculation", "methodology", "source_system",
                  "evidence", "evidence_owner", "freshness", "confidence",
                  "completeness", "reliability", "related_controls", "frameworks",
                  "historical", "human_validation", "financial"):
            assert k in d, f"missing {k}"
        assert isinstance(d["evidence"], list)

    def test_evidence_health_component(self, admin):
        # URL-encoded path segment
        r = admin.get(f"{BASE_URL}/api/evidence/health/Identity%20%26%20Access")
        assert r.status_code == 200, r.text
        d = r.json()
        assert "metric" in d and "source_system" in d


class TestRegression:
    def test_overview(self, admin):
        assert admin.get(f"{BASE_URL}/api/overview").status_code == 200

    def test_risks(self, admin):
        assert admin.get(f"{BASE_URL}/api/risks").status_code == 200

    def test_ai_systems(self, admin):
        assert admin.get(f"{BASE_URL}/api/ai-systems").status_code == 200

    def test_modules(self, admin):
        assert admin.get(f"{BASE_URL}/api/modules").status_code == 200

    def test_billing_plans(self, admin):
        assert admin.get(f"{BASE_URL}/api/billing/plans").status_code == 200

    def test_me(self, admin):
        r = admin.get(f"{BASE_URL}/api/auth/me")
        assert r.status_code == 200
        assert r.json()["email"] == ADMIN_EMAIL
