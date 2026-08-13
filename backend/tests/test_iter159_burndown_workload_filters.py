"""Iteration 159 backend tests: risk burndown target, register filters/sort, chat alert tick, weekly owner digest."""
import os
import sys
import pytest
import requests

# Load backend env so cra_governance imports work
try:
    from dotenv import load_dotenv
    load_dotenv("/app/backend/.env")
except Exception:
    pass
sys.path.insert(0, "/app/backend")

def _load_backend_url():
    v = os.environ.get("REACT_APP_BACKEND_URL")
    if not v:
        # fallback to frontend/.env
        try:
            with open("/app/frontend/.env") as f:
                for line in f:
                    if line.startswith("REACT_APP_BACKEND_URL="):
                        v = line.split("=", 1)[1].strip()
                        break
        except Exception:
            pass
    assert v, "REACT_APP_BACKEND_URL not set"
    return v.rstrip("/")


BASE_URL = _load_backend_url()
ADMIN_EMAIL = "jblan2026@gmail.com"
ADMIN_PASSWORD = "Obserra2026!"


@pytest.fixture(scope="module")
def admin_client():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text[:200]}"
    return s


# --- Risk Burndown Target ---
class TestRiskBurndownTarget:
    def test_get_risk_target(self, admin_client):
        r = admin_client.get(f"{BASE_URL}/api/cra/risk-target")
        assert r.status_code == 200
        d = r.json()
        for k in ["target", "current", "gap", "on_track", "slope_per_day", "days_to_target", "projected_date", "is_default", "points"]:
            assert k in d, f"missing {k}"
        assert isinstance(d["target"], int)
        assert isinstance(d["current"], (int, float))

    def test_put_risk_target_admin(self, admin_client):
        r = admin_client.put(f"{BASE_URL}/api/cra/risk-target", json={"target": 40})
        assert r.status_code == 200, r.text[:300]
        d = r.json()
        assert d["target"] == 40
        assert d["gap"] == d["current"] - 40

    def test_put_target_validation(self, admin_client):
        r = admin_client.put(f"{BASE_URL}/api/cra/risk-target", json={"target": 250})
        assert r.status_code in (400, 422)


# --- Register Filters & Sort ---
class TestRegisterFiltersAndSort:
    def test_csv_all(self, admin_client):
        r = admin_client.get(f"{BASE_URL}/api/cra/risk-register.csv")
        assert r.status_code == 200
        assert "text/csv" in r.headers.get("content-type", "")
        rows_all = r.text.strip().splitlines()
        assert len(rows_all) >= 2

    def test_csv_rating_critical(self, admin_client):
        r = admin_client.get(f"{BASE_URL}/api/cra/risk-register.csv?rating=Critical")
        assert r.status_code == 200
        rows = r.text.strip().splitlines()
        # header + N critical only
        for row in rows[1:]:
            assert row.startswith("Critical"), f"Non-critical row: {row[:80]}"

    def test_csv_rating_reduces_rows(self, admin_client):
        r_all = admin_client.get(f"{BASE_URL}/api/cra/risk-register.csv").text.strip().splitlines()
        r_crit = admin_client.get(f"{BASE_URL}/api/cra/risk-register.csv?rating=Critical").text.strip().splitlines()
        assert len(r_crit) <= len(r_all)

    def test_pdf_filter_and_sort(self, admin_client):
        r = admin_client.get(f"{BASE_URL}/api/cra/risk-register.pdf?rating=Critical,High&sort=due")
        assert r.status_code == 200
        assert r.headers.get("content-type", "").startswith("application/pdf")
        assert r.content[:4] == b"%PDF"

    def test_owner_unassigned_filter(self, admin_client):
        r = admin_client.get(f"{BASE_URL}/api/cra/risk-register.csv?owner=__unassigned__")
        assert r.status_code == 200
        rows = r.text.strip().splitlines()[1:]
        # owner column index 6 (0-based) — should be empty
        import csv, io
        for row in csv.reader(io.StringIO("\n".join(rows))):
            if row:
                assert row[6] == "", f"owner should be empty for unassigned filter, got: {row[6]}"


# --- Risk Correlation still healthy (governance tick sanity: computes without 500) ---
class TestRiskCorrelation:
    def test_risk_correlation_ok(self, admin_client):
        r = admin_client.get(f"{BASE_URL}/api/cra/risk-correlation")
        assert r.status_code == 200
        d = r.json()
        assert "risks" in d
        # Verify Dana Ruiz owner is present on some risk
        owners = [r.get("owner") for r in d["risks"]]
        assert "Dana Ruiz" in owners, f"Expected Dana Ruiz assigned; got owners={owners}"


# --- Owner Digest / Chat Alert code path importable ---
class TestBackgroundJobs:
    def test_import_owner_digest_and_tick(self):
        import importlib
        m = importlib.import_module("cra_governance")
        assert hasattr(m, "_run_cra_risk_owner_digest")
        assert hasattr(m, "_run_cra_risk_governance_tick")
        assert hasattr(m, "_cra_risk_owner_digest_html")

    def test_owner_digest_html_render(self):
        from cra_governance import _cra_risk_owner_digest_html
        html = _cra_risk_owner_digest_html("Acme", [
            {"title": "Sample risk", "rating": "Critical", "due_date": "2026-06-20", "overdue": False, "controls": ["A-1"]}
        ])
        assert "Sample risk" in html
        assert "Critical" in html
        assert "2026-06-20" in html

    def test_weekly_cron_registered(self):
        import inspect, scheduled
        src = inspect.getsource(scheduled)
        assert "_run_cra_risk_owner_digest" in src
        assert "weekly-drift-digest" in src


# --- Non-admin cannot set target ---
class TestAuthGuards:
    def test_put_target_unauth(self):
        r = requests.put(f"{BASE_URL}/api/cra/risk-target", json={"target": 25})
        assert r.status_code in (401, 403)
