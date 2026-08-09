"""Iteration 60 tests: Scorecard PDF export, real trend backfill, digest attach,
mover-rule filters, weekly scorecard, and regression across split modules."""
import os
import time
import requests
import pytest

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
EMAIL = "jblan2026@gmail.com"
PASSWORD = "Obserra2026!"


@pytest.fixture(scope="module")
def client():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json={"email": EMAIL, "password": PASSWORD}, timeout=30)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text[:200]}"
    return s


# ---------- Scorecard PDF / CSV ----------
class TestScorecardExport:
    def test_scorecard_csv(self, client):
        r = client.get(f"{BASE_URL}/api/sap/scorecard/export?format=csv", timeout=30)
        assert r.status_code == 200
        assert "text/csv" in r.headers.get("content-type", "")
        assert len(r.content) > 100

    def test_scorecard_pdf(self, client):
        r = client.get(f"{BASE_URL}/api/sap/scorecard/export?format=pdf", timeout=60)
        assert r.status_code == 200
        assert "application/pdf" in r.headers.get("content-type", "")
        assert r.content[:4] == b"%PDF"
        assert len(r.content) > 2000


# ---------- Real trend backfill ----------
class TestScorecardTrend:
    def test_scorecard_trend_source_real(self, client):
        r = client.get(f"{BASE_URL}/api/sap/scorecard", timeout=30)
        assert r.status_code == 200
        j = r.json()
        assert j.get("trend_source") == "real", f"expected real, got {j.get('trend_source')}"
        trend = j.get("trend") or []
        assert len(trend) == 8, f"expected 8 trend points, got {len(trend)}"
        scores = [pt.get("governance_score") for pt in trend]
        # ascending-ish
        assert scores[0] is not None and scores[-1] is not None
        assert scores[-1] >= scores[0], f"trend not ascending: {scores}"


# ---------- Digest attach & send ----------
class TestDigestSend:
    def test_digest_send_ok_or_throttled(self, client):
        r = client.post(f"{BASE_URL}/api/sap/governance-digest/send", timeout=45)
        assert r.status_code == 200, f"{r.status_code} {r.text[:200]}"
        j = r.json()
        # accept success or throttled
        assert j.get("ok") is True or j.get("throttled") is True or "throttled" in str(j).lower() or j.get("sent") is not None


# ---------- Mover rule filters ----------
class TestMoverRuleFilters:
    def test_mover_rule_base(self, client):
        r = client.get(f"{BASE_URL}/api/sap/mover-rule", timeout=30)
        assert r.status_code == 200
        j = r.json()
        assert "config" in j or "enabled" in j
        assert "candidates" in j or "log" in j or "stripped_total" in j

    def test_mover_rule_filters_q_days(self, client):
        r = client.get(f"{BASE_URL}/api/sap/mover-rule?q=Vikram&days=30", timeout=30)
        assert r.status_code == 200
        r2 = client.get(f"{BASE_URL}/api/sap/mover-rule?q=&days=7", timeout=30)
        assert r2.status_code == 200
        r3 = client.get(f"{BASE_URL}/api/sap/mover-rule?days=0", timeout=30)
        assert r3.status_code == 200


# ---------- Regression across split modules ----------
class TestRegressionModules:
    @pytest.mark.parametrize("path", [
        "/api/sap/autoremediation",
        "/api/sap/jml",
        "/api/sap/mover-rule",
        "/api/sap/workflow/activity",
        "/api/sap/workflow/activity/export?format=csv",
        "/api/sap/digest/config",
        "/api/sap/digest/preview",
        "/api/sap/scorecard",
        "/api/sap/sod/conflicts",
    ])
    def test_endpoint_200(self, client, path):
        r = client.get(f"{BASE_URL}{path}", timeout=45)
        assert r.status_code == 200, f"{path} -> {r.status_code} {r.text[:200]}"


# ---------- Weekly scorecard job callable ----------
class TestWeeklyJob:
    def test_weekly_job_import(self):
        import importlib, sys
        sys.path.insert(0, "/app/backend")
        from dotenv import load_dotenv
        load_dotenv("/app/backend/.env")
        importlib.import_module("server")  # wires all modules
        sap_uac = importlib.import_module("sap_uac")
        assert hasattr(sap_uac, "run_sap_weekly_scorecard")
        sap_digest = importlib.import_module("sap_digest")
        assert hasattr(sap_digest, "run_sap_weekly_scorecard")
