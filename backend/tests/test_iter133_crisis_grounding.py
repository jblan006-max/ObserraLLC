"""Iteration 133: Crisis-grounded AI insight, advisor ground_only_context, and full connector catalog."""
import os
import pytest
import requests

def _load_frontend_env():
    try:
        with open("/app/frontend/.env") as f:
            for line in f:
                if line.startswith("REACT_APP_BACKEND_URL="):
                    return line.split("=", 1)[1].strip().rstrip("/")
    except Exception:
        pass
    return os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

BASE_URL = _load_frontend_env()
assert BASE_URL, "REACT_APP_BACKEND_URL must be set"
ADMIN_EMAIL = "jblan2026@gmail.com"
ADMIN_PASSWORD = "Obserra2026!"


@pytest.fixture(scope="module")
def admin_session():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login",
               json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=20)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text[:200]}"
    return s


# ---------- Crisis insight ----------
class TestCrisisInsight:
    def test_seed_demo_case(self, admin_session):
        r = admin_session.post(f"{BASE_URL}/api/crisis/demo/seed", timeout=30)
        assert r.status_code in (200, 201), r.text[:200]
        data = r.json()
        assert data.get("ref", "").startswith("CRISIS-"), data

    def test_crisis_insight_no_ref_grounded(self, admin_session):
        r = admin_session.get(f"{BASE_URL}/api/crisis/insight", timeout=25)
        assert r.status_code == 200, r.text[:200]
        data = r.json()
        assert "headline" in data and "insights" in data and "actions" in data
        assert "model" in data and "generated_at" in data
        assert isinstance(data["insights"], list) and len(data["insights"]) >= 1
        # Every insight object must have text + kind
        for ins in data["insights"]:
            assert "text" in ins and "kind" in ins
        # Grounding check — no SAP access-posture / SoD content
        blob = (data["headline"] + " " + " ".join(i["text"] for i in data["insights"])
                + " " + " ".join(data.get("actions") or [])).lower()
        assert "sod conflict" not in blob
        assert "access posture" not in blob
        assert "segregation of duties" not in blob

    def test_crisis_insight_with_ref(self, admin_session):
        cases = admin_session.get(f"{BASE_URL}/api/crisis/cases", timeout=15).json()
        assert isinstance(cases, list) and len(cases) > 0
        ref = cases[0]["ref"]
        r = admin_session.get(f"{BASE_URL}/api/crisis/insight", params={"ref": ref}, timeout=25)
        assert r.status_code == 200
        data = r.json()
        # Grounded: the case ref (or a decision/system) should surface in text somewhere
        blob = (data["headline"] + " " + " ".join(i["text"] for i in data["insights"])).lower()
        # If fallback, it explicitly cites ref; if LLM, it should too. Accept either grounded proof.
        assert ref.lower() in blob or "crisis" in blob

    def test_crisis_insight_unknown_ref(self, admin_session):
        r = admin_session.get(f"{BASE_URL}/api/crisis/insight",
                              params={"ref": "CRISIS-DOES-NOT-EXIST"}, timeout=15)
        assert r.status_code == 200
        data = r.json()
        # No matching case -> graceful payload OR falls back to latest (both acceptable, must not 500)
        assert "insights" in data


# ---------- Advisor ground_only_context ----------
class TestAdvisorGroundOnly:
    def test_explain_ground_only_true_no_impact(self, admin_session):
        payload = {
            "title": "TEST_ Iter133 crisis case",
            "kind": "crisis-briefing",
            "context": {"case_ref": "CRISIS-TEST", "systems_down": ["SAP ERP Production"], "recovery_pct": 42},
            "ground_only_context": True,
        }
        r = admin_session.post(f"{BASE_URL}/api/advisor/explain", json=payload, timeout=30)
        assert r.status_code == 200, r.text[:300]
        data = r.json()
        assert "summary" in data and "recommendation" in data
        # Impact fields must be omitted
        assert "at_stake" not in data
        assert "reduction_if_fixed" not in data

    def test_explain_default_has_impact(self, admin_session):
        # Use a distinct title to avoid the 5-min cache from the previous test
        payload = {
            "title": "TEST_ Iter133 default explain",
            "kind": "spend-line",
            "context": {"amount": 12345, "vendor": "TEST_ Vendor"},
        }
        r = admin_session.post(f"{BASE_URL}/api/advisor/explain", json=payload, timeout=30)
        assert r.status_code == 200, r.text[:300]
        data = r.json()
        assert "summary" in data
        # Default (ground_only_context=false) should merge impact — accept either key
        assert ("at_stake" in data) or ("reduction_if_fixed" in data), \
            f"expected impact fields in default explain, got keys={list(data.keys())}"


# ---------- Connector catalog ----------
class TestConnectorCatalog:
    def test_catalog_returns_all_categories(self, admin_session):
        r = admin_session.get(f"{BASE_URL}/api/connectors/catalog", timeout=20)
        assert r.status_code == 200, r.text[:200]
        data = r.json()
        # Accept list or grouped dict
        connectors = data if isinstance(data, list) else (data.get("connectors") or data.get("items") or [])
        if isinstance(data, dict) and "categories" in data:
            connectors = []
            for cat in data["categories"]:
                connectors.extend(cat.get("connectors") or cat.get("items") or [])
        assert len(connectors) >= 20, f"expected many connectors, got {len(connectors)}"
        ids = {(c.get("id") or c.get("cid") or "").lower() for c in connectors}
        # Spot-check the ones mentioned in the review
        expected_any = ["sap-s4", "openai", "anthropic", "servicenow", "sap-scim"]
        found = [x for x in expected_any if x in ids]
        assert len(found) >= 4, f"expected core connector ids present. found={found} sample_ids={list(ids)[:15]}"

    def test_catalog_status_pill_data(self, admin_session):
        r = admin_session.get(f"{BASE_URL}/api/connectors/catalog", timeout=20)
        data = r.json()
        connectors = data if isinstance(data, list) else (data.get("connectors") or data.get("items") or [])
        if isinstance(data, dict) and "categories" in data:
            connectors = []
            for cat in data["categories"]:
                connectors.extend(cat.get("connectors") or cat.get("items") or [])
        # Every connector should expose category + name + some status/connectable info
        for c in connectors[:10]:
            assert c.get("id"), c
            assert c.get("category") or c.get("group"), c
            assert c.get("name") or c.get("label"), c

    def test_health_feed(self, admin_session):
        r = admin_session.get(f"{BASE_URL}/api/connectors/health", timeout=20)
        assert r.status_code == 200, r.text[:200]


# ---------- Regression: /api/sap/insight still works ----------
class TestSapInsightRegression:
    def test_sap_insight_ok(self, admin_session):
        r = admin_session.get(f"{BASE_URL}/api/sap/insight", timeout=25)
        assert r.status_code == 200, r.text[:200]
        data = r.json()
        assert "insights" in data or "headline" in data
