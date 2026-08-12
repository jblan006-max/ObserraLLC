"""Iteration 134 — War Room Live Sync, Regulatory Auto-Alerts, ServiceNow ingest, Email Brief."""
import os
import time
import pytest
import requests

def _load_backend_url():
    v = os.environ.get("REACT_APP_BACKEND_URL", "")
    if not v:
        with open("/app/frontend/.env") as f:
            for line in f:
                if line.startswith("REACT_APP_BACKEND_URL"):
                    v = line.split("=", 1)[1].strip().strip('"').strip("'")
                    break
    return v.rstrip("/")


BASE_URL = _load_backend_url()
ADMIN_EMAIL = "jblan2026@gmail.com"
ADMIN_PASSWORD = "Obserra2026!"


def _read_env_secret():
    with open("/app/backend/.env") as f:
        for line in f:
            if line.startswith("WEBHOOK_CRON_SECRET"):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    return ""


CRON_SECRET = _read_env_secret()


@pytest.fixture(scope="module")
def admin_session():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login",
               json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=20)
    assert r.status_code == 200, f"Login failed: {r.status_code} {r.text[:200]}"
    return s


@pytest.fixture(scope="module")
def demo_ref(admin_session):
    r = admin_session.post(f"{BASE_URL}/api/crisis/demo/seed", timeout=30)
    assert r.status_code == 200, f"seed failed: {r.text[:200]}"
    data = r.json()
    ref = data.get("ref") or (data.get("case") or {}).get("ref")
    assert ref, f"No ref returned: {data}"
    return ref


# --------------------------- Regulatory scan ---------------------------------
class TestRegulatoryScan:
    def test_scan_first_sends_and_second_dedupes(self, admin_session, demo_ref):
        r1 = admin_session.post(f"{BASE_URL}/api/crisis/regulatory/scan", timeout=30)
        assert r1.status_code == 200, r1.text[:200]
        first = r1.json()
        assert "alerts_sent" in first
        assert isinstance(first["alerts_sent"], int)
        assert first["alerts_sent"] >= 1, f"Expected >=1 alert on first scan, got {first}"

        r2 = admin_session.post(f"{BASE_URL}/api/crisis/regulatory/scan", timeout=30)
        assert r2.status_code == 200
        assert r2.json().get("alerts_sent") == 0, f"Dedupe failed: {r2.json()}"

    def test_timeline_has_regulatory_event(self, admin_session, demo_ref):
        r = admin_session.get(f"{BASE_URL}/api/crisis/cases/{demo_ref}", timeout=20)
        assert r.status_code == 200
        events = (r.json() or {}).get("events") or []
        reg = [e for e in events if e.get("source") == "Regulatory Timer" or e.get("kind") == "Legal"]
        assert reg, f"No Regulatory Timer event found; kinds={[e.get('kind') for e in events]}"


# --------------------------- Obligation notify_within_hours -----------------
class TestObligationNotifyField:
    def test_create_and_patch_notify_within_hours(self, admin_session, demo_ref):
        payload = {
            "regulation": "TEST_GDPR_72h",
            "jurisdiction": "EU",
            "deadline_at": "2030-01-01T00:00:00+00:00",
            "status": "Assessing",
            "responsible": "Legal",
            "notify_within_hours": 12,
        }
        r = admin_session.post(f"{BASE_URL}/api/crisis/cases/{demo_ref}/obligations",
                               json=payload, timeout=20)
        assert r.status_code in (200, 201), r.text[:200]
        obl = r.json()
        oid = obl.get("obligation_id") or obl.get("id")
        assert obl.get("notify_within_hours") == 12, obl

        r2 = admin_session.patch(f"{BASE_URL}/api/crisis/cases/{demo_ref}/obligations/{oid}",
                                 json={"notify_within_hours": 6}, timeout=20)
        assert r2.status_code == 200, r2.text[:200]
        assert r2.json().get("notify_within_hours") == 6


# --------------------------- Cron auth ---------------------------------------
class TestHourlyCronAuth:
    def test_no_auth_401(self):
        r = requests.post(f"{BASE_URL}/api/cron/hourly-overdue-digest", timeout=20)
        assert r.status_code == 401

    def test_wrong_auth_401(self):
        r = requests.post(f"{BASE_URL}/api/cron/hourly-overdue-digest",
                          headers={"Authorization": "Bearer wrong-secret"}, timeout=20)
        assert r.status_code == 401

    def test_correct_auth_2xx(self):
        assert CRON_SECRET, "WEBHOOK_CRON_SECRET missing in /app/backend/.env"
        r = requests.post(f"{BASE_URL}/api/cron/hourly-overdue-digest",
                          headers={"Authorization": f"Bearer {CRON_SECRET}"}, timeout=30)
        assert r.status_code in (200, 202), f"{r.status_code} {r.text[:200]}"
        assert r.json().get("status") in ("accepted", "ok")


# --------------------------- ServiceNow ingest -------------------------------
class TestServiceNowIngest:
    def test_not_connected_returns_400(self, admin_session):
        r = admin_session.post(f"{BASE_URL}/api/crisis/ingest/servicenow", timeout=20)
        assert r.status_code == 400, f"Expected 400 (not connected) got {r.status_code}: {r.text[:200]}"
        detail = (r.json().get("detail") or "").lower()
        assert "servicenow" in detail and "connect" in detail

    def test_viewer_forbidden(self):
        # Try with unauthenticated session — should be 401/403 (not 400)
        r = requests.post(f"{BASE_URL}/api/crisis/ingest/servicenow", timeout=20)
        assert r.status_code in (401, 403), r.status_code


# --------------------------- Email brief -------------------------------------
class TestEmailBrief:
    def test_email_brief_sends(self, admin_session, demo_ref):
        r = admin_session.post(f"{BASE_URL}/api/crisis/cases/{demo_ref}/email-brief", timeout=60)
        assert r.status_code == 200, r.text[:300]
        data = r.json()
        assert "sent" in data and "recipients" in data
        assert isinstance(data["recipients"], list) and len(data["recipients"]) >= 1
        assert data["sent"] >= 1, f"Expected sent>=1, got {data}"


# --------------------------- War Room / regression --------------------------
class TestWarRoomAndRegression:
    def test_case_detail_ok(self, admin_session, demo_ref):
        r = admin_session.get(f"{BASE_URL}/api/crisis/cases/{demo_ref}", timeout=20)
        assert r.status_code == 200
        payload = r.json()
        case = payload.get("case") or payload
        assert case.get("ref") == demo_ref

    def test_join_warroom(self, admin_session, demo_ref):
        # POST participant with 'join' semantics: endpoint likely /participants
        # Try known endpoint first.
        r = admin_session.post(f"{BASE_URL}/api/crisis/cases/{demo_ref}/warroom/join", timeout=20)
        if r.status_code == 404:
            pytest.skip("No /warroom/join endpoint (frontend-only helper).")
        assert r.status_code in (200, 201), r.text[:200]
        # verify roster contains an entry
        rp = admin_session.get(f"{BASE_URL}/api/crisis/cases/{demo_ref}/participants", timeout=20)
        assert rp.status_code == 200
        parts = rp.json()
        assert isinstance(parts, list) and len(parts) >= 1

    def test_crisis_insight_regression(self, admin_session, demo_ref):
        r = admin_session.get(f"{BASE_URL}/api/crisis/insight?ref={demo_ref}", timeout=60)
        assert r.status_code == 200
        d = r.json()
        assert "headline" in d and "insights" in d and "actions" in d

    def test_connectors_health(self, admin_session):
        r = admin_session.get(f"{BASE_URL}/api/connectors/health", timeout=20)
        assert r.status_code == 200
