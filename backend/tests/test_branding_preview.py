"""Tests for GET /api/reports/branding/preview endpoint"""
import os
import requests
import pytest

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://cyber-dashboard-48.preview.emergentagent.com").rstrip("/")
ADMIN_EMAIL = "jblan2026@gmail.com"
ADMIN_PASSWORD = "Obserra2026!"


@pytest.fixture(scope="module")
def admin_session():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=15)
    assert r.status_code == 200, f"Login failed: {r.status_code} {r.text[:200]}"
    return s


def test_preview_requires_auth():
    r = requests.get(f"{BASE_URL}/api/reports/branding/preview", timeout=15)
    assert r.status_code == 401, f"Expected 401 without auth, got {r.status_code}"


def test_preview_dark(admin_session):
    r = admin_session.get(f"{BASE_URL}/api/reports/branding/preview?theme=dark", timeout=30)
    assert r.status_code == 200, f"{r.status_code}: {r.text[:200]}"
    assert r.headers.get("content-type", "").startswith("image/png"), r.headers.get("content-type")
    assert len(r.content) > 1000
    assert r.content[:8] == b"\x89PNG\r\n\x1a\n"


def test_preview_light(admin_session):
    r = admin_session.get(f"{BASE_URL}/api/reports/branding/preview?theme=light", timeout=30)
    assert r.status_code == 200
    assert r.headers.get("content-type", "").startswith("image/png")
    assert r.content[:8] == b"\x89PNG\r\n\x1a\n"


def test_preview_refreshes_after_branding_change(admin_session):
    # Save custom branding
    payload = {"enabled": True, "name": "Acme Corp — Security & Risk"}
    r = admin_session.put(f"{BASE_URL}/api/reports/branding", json=payload, timeout=15)
    if r.status_code == 404:
        r = admin_session.post(f"{BASE_URL}/api/reports/branding", json=payload, timeout=15)
    assert r.status_code in (200, 201, 204), f"branding save: {r.status_code} {r.text[:200]}"

    r1 = admin_session.get(f"{BASE_URL}/api/reports/branding/preview?theme=dark", timeout=30)
    assert r1.status_code == 200
    assert r1.content[:8] == b"\x89PNG\r\n\x1a\n"

    # Reset via PUT enabled=False
    rr = admin_session.put(f"{BASE_URL}/api/reports/branding", json={"enabled": False, "company_name": ""}, timeout=15)
    assert rr.status_code in (200, 204), f"reset: {rr.status_code}"

    r2 = admin_session.get(f"{BASE_URL}/api/reports/branding/preview?theme=light", timeout=30)
    assert r2.status_code == 200
    assert r2.content[:8] == b"\x89PNG\r\n\x1a\n"
