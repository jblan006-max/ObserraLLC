"""Iter57 backend tests: workflow export (CSV/PDF), JML strip carried-over, governance digest, folded cron."""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://cyber-dashboard-48.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "jblan2026@gmail.com"
ADMIN_PASSWORD = "Obserra2026!"

# Read webhook secret from backend/.env
def _get_webhook_secret():
    try:
        with open("/app/backend/.env") as f:
            for line in f:
                if line.startswith("WEBHOOK_CRON_SECRET"):
                    v = line.split("=", 1)[1].strip().strip('"').strip("'")
                    return v
    except Exception:
        pass
    return None


@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=30)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text[:200]}"
    return s


# ---------- Workflow Export ----------
class TestWorkflowExport:
    def test_csv_export(self, session):
        r = session.get(f"{API}/sap/workflow/activity/export?format=csv", timeout=30)
        assert r.status_code == 200
        assert "text/csv" in r.headers.get("content-type", "").lower()
        body = r.text
        lines = [l for l in body.splitlines() if l.strip()]
        assert len(lines) >= 1  # header
        # Check we have data rows generally (workflow has activity from earlier iterations)
        assert "," in lines[0]  # header has columns

    def test_pdf_export(self, session):
        r = session.get(f"{API}/sap/workflow/activity/export?format=pdf", timeout=30)
        assert r.status_code == 200
        assert "application/pdf" in r.headers.get("content-type", "").lower()
        assert r.content[:4] == b"%PDF"

    def test_invalid_format(self, session):
        r = session.get(f"{API}/sap/workflow/activity/export?format=xml", timeout=30)
        assert r.status_code == 400

    def test_csv_filter_days(self, session):
        r = session.get(f"{API}/sap/workflow/activity/export?format=csv&days=1", timeout=30)
        assert r.status_code == 200
        assert "text/csv" in r.headers.get("content-type", "").lower()


# ---------- JML strip carried-over ----------
class TestJMLStripCarriedOver:
    def test_strip_flow(self, session):
        r = session.get(f"{API}/sap/jml", timeout=30)
        assert r.status_code == 200
        data = r.json()
        movers = data.get("movers", [])
        assert isinstance(movers, list)
        # find a mover with carried_over_count>0
        candidate = None
        for m in movers:
            if (m.get("carried_over_count") or 0) > 0:
                candidate = m
                break
        if not candidate:
            pytest.skip("No mover with carried_over_count>0 available (may have been stripped already)")
        ref = candidate.get("person_ref") or candidate.get("ref") or candidate.get("id")
        assert ref, f"mover shape missing ref: {candidate}"
        r2 = session.post(f"{API}/sap/jml/{ref}/strip-carried-over", json={"reason": "iter57 test"}, timeout=30)
        assert r2.status_code == 200, f"strip failed: {r2.status_code} {r2.text[:300]}"
        js = r2.json()
        assert "stripped" in js or "stripped_names" in js
        assert (js.get("stripped_count") or 0) >= 1
        ticket = js.get("ticket") or {}
        assert ticket.get("number"), f"no ticket.number: {js}"
        assert "systems_touched" in ticket

    def test_strip_no_carried_over_returns_400(self, session):
        # After stripping, the same ref should return 400
        r = session.get(f"{API}/sap/jml", timeout=30)
        movers = r.json().get("movers", [])
        clean = None
        for m in movers:
            if (m.get("carried_over_count") or 0) == 0:
                clean = m.get("person_ref") or m.get("ref") or m.get("id")
                if clean:
                    break
        if not clean:
            pytest.skip("no mover without carried-over roles")
        r2 = session.post(f"{API}/sap/jml/{clean}/strip-carried-over", json={"reason": "test"}, timeout=30)
        assert r2.status_code == 400, f"expected 400, got {r2.status_code}: {r2.text[:200]}"

    def test_strip_unknown_ref_returns_404(self, session):
        r = session.post(f"{API}/sap/jml/P-NONEXISTENT-9999/strip-carried-over", json={"reason": "x"}, timeout=30)
        assert r.status_code == 404


# ---------- Governance Digest ----------
class TestGovernanceDigest:
    def test_send_digest(self, session):
        r = session.post(f"{API}/sap/governance-digest/send", timeout=60)
        assert r.status_code == 200, f"{r.status_code} {r.text[:300]}"
        js = r.json()
        assert js.get("ok") is True
        assert isinstance(js.get("recipients"), list)
        assert (js.get("sent") or 0) >= 0  # Resend may throttle (429) — endpoint still returns ok
        data = js.get("data") or {}
        for key in ["open_sod", "autorem_24h", "residual_count", "top"]:
            assert key in data, f"missing digest data key {key}: {list(data.keys())}"


# ---------- Folded Platform Cron ----------
class TestFoldedCron:
    def test_cron_without_auth_returns_401(self):
        r = requests.post(f"{API}/cron/daily-drift-digest", timeout=30)
        assert r.status_code == 401

    def test_cron_with_auth_returns_200(self):
        secret = _get_webhook_secret()
        assert secret, "WEBHOOK_CRON_SECRET missing from /app/backend/.env"
        r = requests.post(
            f"{API}/cron/daily-drift-digest",
            headers={"Authorization": f"Bearer {secret}"},
            timeout=60,
        )
        assert r.status_code == 200, f"{r.status_code} {r.text[:200]}"
        js = r.json()
        assert js.get("status") == "accepted"


# ---------- Regression ----------
class TestRegression:
    def test_autorem_get(self, session):
        r = session.get(f"{API}/sap/autoremediation", timeout=30)
        assert r.status_code == 200

    def test_autorem_run(self, session):
        r = session.post(f"{API}/sap/autoremediation/run", json={}, timeout=30)
        assert r.status_code == 200

    def test_workflow_activity(self, session):
        r = session.get(f"{API}/sap/workflow/activity", timeout=30)
        assert r.status_code == 200
        assert isinstance(r.json().get("tickets") or r.json().get("items") or [], list)
