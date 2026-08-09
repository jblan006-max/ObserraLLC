"""
Backend sanity tests for:
- SLA config endpoints (org + per-room)
- Bulk-status-filter (Select Across Filters)
- Audit request analytics trend
- Admin download endpoints (200)
- Auth gating: 403/401 for non-admin/unauthenticated
"""
import os
import io
import requests
import pytest

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
ADMIN_EMAIL = "jblan2026@gmail.com"
ADMIN_PASSWORD = "Obserra2026!"


@pytest.fixture(scope="module")
def admin_session():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login",
               json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
               timeout=30)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text[:200]}"
    return s


@pytest.fixture(scope="module")
def anon_session():
    return requests.Session()


# ---------- SLA config ----------

def test_sla_config_get_admin(admin_session):
    r = admin_session.get(f"{BASE_URL}/api/deploy/sla-config", timeout=30)
    assert r.status_code == 200, r.text[:200]
    data = r.json()
    assert "org_sla_hours" in data
    assert "default" in data or "default_sla_hours" in data
    assert "rooms" in data and isinstance(data["rooms"], list)


def test_sla_config_get_anon_forbidden(anon_session):
    r = anon_session.get(f"{BASE_URL}/api/deploy/sla-config", timeout=30)
    assert r.status_code in (401, 403), r.status_code


def test_sla_config_put_admin_and_persist(admin_session):
    # set 48
    r = admin_session.put(f"{BASE_URL}/api/deploy/sla-config",
                          json={"sla_hours": 48}, timeout=30)
    assert r.status_code == 200, r.text[:200]
    r2 = admin_session.get(f"{BASE_URL}/api/deploy/sla-config", timeout=30)
    assert r2.status_code == 200
    assert int(r2.json().get("org_sla_hours")) == 48
    # restore to 72
    r3 = admin_session.put(f"{BASE_URL}/api/deploy/sla-config",
                           json={"sla_hours": 72}, timeout=30)
    assert r3.status_code == 200
    r4 = admin_session.get(f"{BASE_URL}/api/deploy/sla-config", timeout=30)
    assert int(r4.json().get("org_sla_hours")) == 72


def test_sla_config_put_anon_forbidden(anon_session):
    r = anon_session.put(f"{BASE_URL}/api/deploy/sla-config",
                         json={"sla_hours": 48}, timeout=30)
    assert r.status_code in (401, 403)


# ---------- per-room SLA ----------

def test_room_sla_put_and_clear(admin_session):
    cfg = admin_session.get(f"{BASE_URL}/api/deploy/sla-config", timeout=30).json()
    rooms = cfg.get("rooms") or []
    if not rooms:
        pytest.skip("No audit rooms available")
    token = rooms[0].get("token") or rooms[0].get("room_token")
    assert token, f"room has no token: {rooms[0]}"

    # set override
    r = admin_session.put(f"{BASE_URL}/api/deploy/audit-room/{token}/sla",
                          json={"sla_hours": 24}, timeout=30)
    assert r.status_code == 200, r.text[:200]

    cfg2 = admin_session.get(f"{BASE_URL}/api/deploy/sla-config", timeout=30).json()
    match = next((rr for rr in cfg2["rooms"] if (rr.get("token") or rr.get("room_token")) == token), None)
    assert match is not None
    assert 24 in (match.get("override"), match.get("effective"))

    # clear override (null)
    r2 = admin_session.put(f"{BASE_URL}/api/deploy/audit-room/{token}/sla",
                           json={"sla_hours": None}, timeout=30)
    assert r2.status_code == 200


def test_room_sla_put_anon_forbidden(anon_session, admin_session):
    cfg = admin_session.get(f"{BASE_URL}/api/deploy/sla-config", timeout=30).json()
    rooms = cfg.get("rooms") or []
    if not rooms:
        pytest.skip("no rooms")
    token = rooms[0].get("token") or rooms[0].get("room_token")
    r = anon_session.put(f"{BASE_URL}/api/deploy/audit-room/{token}/sla",
                        json={"sla_hours": 24}, timeout=30)
    assert r.status_code in (401, 403)


# ---------- Analytics trend ----------

def test_audit_request_analytics_trend(admin_session):
    r = admin_session.get(f"{BASE_URL}/api/deploy/audit-request-analytics", timeout=30)
    assert r.status_code == 200, r.text[:200]
    data = r.json()
    assert "trend" in data and isinstance(data["trend"], list)


# ---------- Bulk status filter ----------

def test_bulk_status_filter_admin(admin_session):
    # Use filter_status open to open (should succeed even if 0 matches)
    r = admin_session.post(f"{BASE_URL}/api/deploy/audit-room-comments/bulk-status-filter",
                           json={"status": "Open", "filter_status": "Open"}, timeout=30)
    assert r.status_code == 200, r.text[:200]
    data = r.json()
    # tolerate different shapes
    assert isinstance(data, dict)


def test_bulk_status_filter_anon_forbidden(anon_session):
    r = anon_session.post(f"{BASE_URL}/api/deploy/audit-room-comments/bulk-status-filter",
                          json={"status": "Resolved", "filter_status": "Open"}, timeout=30)
    assert r.status_code in (401, 403)


# ---------- Admin downloads ----------

@pytest.mark.parametrize("path", [
    "/api/deploy/onprem-package",
    "/api/deploy/guide.pdf",
    "/api/deploy/compliance-evidence",
    "/api/sap/workflow/activity/export?format=pdf",
])
def test_admin_downloads_200(admin_session, path):
    r = admin_session.get(f"{BASE_URL}{path}", timeout=90, stream=True)
    assert r.status_code == 200, f"{path} -> {r.status_code} {r.text[:200] if r.status_code!=200 else ''}"
    # Read some bytes to ensure body streams
    chunk = next(r.iter_content(1024), b"")
    assert chunk, f"empty response body for {path}"
