"""Iteration 157 backend tests: Risk Correlation + Executive Overview power-ups liveness sweep."""
import os
import re
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
ADMIN_EMAIL = "jblan2026@gmail.com"
ADMIN_PASSWORD = "Obserra2026!"


@pytest.fixture(scope="module")
def admin_session():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login",
               json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
               timeout=30)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    return s


# ---- Risk Correlation (new this round) ----
class TestRiskCorrelation:
    def test_risk_correlation_shape(self, admin_session):
        r = admin_session.get(f"{BASE_URL}/api/cra/risk-correlation", timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "overall" in data and "risks" in data
        overall = data["overall"]
        for k in ("total", "counts", "risk_index", "top_rating", "most_correlated_control"):
            assert k in overall, f"missing overall.{k}"
        assert isinstance(overall["risk_index"], (int, float))
        assert 0 <= overall["risk_index"] <= 100
        assert isinstance(overall["counts"], dict)
        for rt in ("Critical", "High", "Medium", "Low"):
            assert rt in overall["counts"], f"missing counts.{rt}"
        assert isinstance(data["risks"], list)
        if data["risks"]:
            r0 = data["risks"][0]
            for k in ("id", "title", "category", "severity", "likelihood", "score",
                     "rating", "drivers", "affected", "recommendation", "fixes",
                     "mapped_controls"):
                assert k in r0, f"risk missing {k}"
            assert r0["rating"] in ("Critical", "High", "Medium", "Low")


# ---- Executive Overview power-ups: preview / shareable link ----
class TestExecEmailPreview:
    def test_exec_email_preview(self, admin_session):
        r = admin_session.get(f"{BASE_URL}/api/cra/exec-email/preview", timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "html" in data and "subject" in data
        assert isinstance(data["html"], str) and len(data["html"]) > 200
        assert "<" in data["html"]  # looks like HTML


class TestExecOverviewShareLink:
    def test_mint_list_public_and_revoke(self, admin_session):
        # Cleanup: revoke everything first to ensure predictable state
        admin_session.post(f"{BASE_URL}/api/cra/exec-overview-link/revoke", timeout=30)

        # Mint
        r = admin_session.post(f"{BASE_URL}/api/cra/exec-overview-link", timeout=30)
        assert r.status_code == 200, r.text
        payload = r.json()
        assert "token" in payload and "path" in payload and "expires_at" in payload
        token = payload["token"]
        assert payload["path"].startswith("/exec-overview/")

        # List
        r2 = admin_session.get(f"{BASE_URL}/api/cra/exec-overview-links", timeout=30)
        assert r2.status_code == 200
        assert r2.json().get("active", 0) >= 1

        # Public access - NO auth
        pub = requests.get(f"{BASE_URL}/api/cra-public/exec-overview/{token}", timeout=30)
        assert pub.status_code == 200, f"public fetch failed: {pub.status_code} {pub.text}"
        pdata = pub.json()
        for k in ("kpis", "controls", "nist", "classifications", "next_deadline",
                  "organization", "role", "generated_at"):
            assert k in pdata, f"public payload missing {k}"
        assert pdata["role"] == "exec_overview"
        # Must NOT expose product names
        assert "products" not in pdata
        assert "product_names" not in pdata

        # Invalid token
        bad = requests.get(f"{BASE_URL}/api/cra-public/exec-overview/thisisnotarealtoken",
                           timeout=30)
        assert bad.status_code in (401, 403), bad.status_code

        # Revoke and verify revoked token no longer works
        rv = admin_session.post(f"{BASE_URL}/api/cra/exec-overview-link/revoke", timeout=30)
        assert rv.status_code == 200
        pub2 = requests.get(f"{BASE_URL}/api/cra-public/exec-overview/{token}", timeout=30)
        assert pub2.status_code in (401, 403), \
            f"revoked token still works: {pub2.status_code}"

    def test_link_cap_of_5_returns_429(self, admin_session):
        # Revoke first
        admin_session.post(f"{BASE_URL}/api/cra/exec-overview-link/revoke", timeout=30)
        minted = []
        for i in range(5):
            r = admin_session.post(f"{BASE_URL}/api/cra/exec-overview-link", timeout=30)
            assert r.status_code == 200, f"mint {i} failed: {r.status_code} {r.text}"
            minted.append(r.json()["token"])
        r = admin_session.post(f"{BASE_URL}/api/cra/exec-overview-link", timeout=30)
        assert r.status_code == 429, f"expected 429 on 6th, got {r.status_code}"
        # Cleanup
        admin_session.post(f"{BASE_URL}/api/cra/exec-overview-link/revoke", timeout=30)


# ---- Liveness sweep of all endpoints listed in the review ----
LIVENESS_PATHS = [
    "/api/cra/dashboard",
    "/api/cra/products",
    "/api/cra/assessments",
    "/api/cra/vulnerabilities",
    "/api/cra/external-assessments",
    "/api/cra/ledger",
    "/api/cra/controls",
    "/api/cra/nist",
    "/api/cra/regulation",
    "/api/cra/insight",
    "/api/cra/ai-monitor",
    "/api/cra/risk-correlation",
    "/api/cra/providers",
    "/api/cra/exec-snapshots",
    "/api/connectors/health",
]


@pytest.mark.parametrize("path", LIVENESS_PATHS)
def test_liveness_endpoint_200(admin_session, path):
    r = admin_session.get(f"{BASE_URL}{path}", timeout=30)
    assert r.status_code == 200, f"{path} -> {r.status_code}: {r.text[:200]}"


# ---- AI monitor forward-filled continuity (30d/90d) ----
class TestAiMonitorTrendLength:
    @pytest.mark.parametrize("days", [7, 30, 90])
    def test_trend_length(self, admin_session, days):
        r = admin_session.get(f"{BASE_URL}/api/cra/ai-monitor?days={days}", timeout=30)
        assert r.status_code == 200
        data = r.json()
        assert "trend" in data
        assert len(data["trend"]) == days
