"""Iteration 18 — Accent colour + Hint Analytics.
Tests:
 - PUT/GET /api/reports/branding accent normalization and clearing
 - GET /api/reports/branding/preview returns image/png for light+dark
 - POST /api/advisor/hint-open (any auth) records event
 - GET /api/advisor/usage (admin) returns hint_opens/hint_unique
"""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    # fallback to frontend/.env
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL"):
                BASE_URL = line.split("=", 1)[1].strip().rstrip("/")

ADMIN_EMAIL = "jblan2026@gmail.com"
ADMIN_PW = "Obserra2026!"


@pytest.fixture(scope="module")
def admin_session():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login",
               json={"email": ADMIN_EMAIL, "password": ADMIN_PW}, timeout=15)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    yield s
    # cleanup: clear accent
    s.put(f"{BASE_URL}/api/reports/branding",
          json={"enabled": False, "company_name": "", "accent": ""}, timeout=15)


class TestAccentBranding:
    def test_put_accent_valid(self, admin_session):
        r = admin_session.put(f"{BASE_URL}/api/reports/branding",
                              json={"enabled": True, "company_name": "Obserra Test",
                                    "accent": "#e11d48"}, timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["accent"].lower() == "#e11d48"

    def test_get_accent_persisted(self, admin_session):
        r = admin_session.get(f"{BASE_URL}/api/reports/branding", timeout=15)
        assert r.status_code == 200
        assert r.json()["accent"].lower() == "#e11d48"

    def test_invalid_accent_ignored(self, admin_session):
        r = admin_session.put(f"{BASE_URL}/api/reports/branding",
                              json={"enabled": True, "company_name": "Obserra Test",
                                    "accent": "red"}, timeout=15)
        assert r.status_code == 200
        assert r.json()["accent"] == ""
        # And GET confirms
        g = admin_session.get(f"{BASE_URL}/api/reports/branding", timeout=15).json()
        assert g["accent"] == ""

    def test_clear_accent_empty_string(self, admin_session):
        # set again then clear
        admin_session.put(f"{BASE_URL}/api/reports/branding",
                          json={"enabled": True, "company_name": "Obserra Test",
                                "accent": "#123456"}, timeout=15)
        r = admin_session.put(f"{BASE_URL}/api/reports/branding",
                              json={"enabled": True, "company_name": "Obserra Test",
                                    "accent": ""}, timeout=15)
        assert r.status_code == 200
        assert r.json()["accent"] == ""

    def test_preview_light_png(self, admin_session):
        # set accent then verify preview PNG
        admin_session.put(f"{BASE_URL}/api/reports/branding",
                          json={"enabled": True, "company_name": "Obserra Test",
                                "accent": "#e11d48"}, timeout=15)
        r = admin_session.get(f"{BASE_URL}/api/reports/branding/preview?theme=light", timeout=20)
        assert r.status_code == 200
        assert r.headers.get("content-type", "").startswith("image/png")
        assert r.content[:8] == b"\x89PNG\r\n\x1a\n"
        assert len(r.content) > 500

    def test_preview_dark_png(self, admin_session):
        r = admin_session.get(f"{BASE_URL}/api/reports/branding/preview?theme=dark", timeout=20)
        assert r.status_code == 200
        assert r.headers.get("content-type", "").startswith("image/png")
        assert r.content[:8] == b"\x89PNG\r\n\x1a\n"


class TestHintAnalytics:
    def test_hint_open_records(self, admin_session):
        r = admin_session.post(f"{BASE_URL}/api/advisor/hint-open", timeout=15)
        assert r.status_code == 200
        assert r.json().get("ok") is True

    def test_usage_returns_hint_counts(self, admin_session):
        r = admin_session.get(f"{BASE_URL}/api/advisor/usage", timeout=15)
        assert r.status_code == 200
        data = r.json()
        assert "hint_opens" in data
        assert "hint_unique" in data
        assert data["hint_opens"] >= 1
        assert data["hint_unique"] >= 1
