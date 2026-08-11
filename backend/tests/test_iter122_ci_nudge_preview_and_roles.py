"""Iteration 122 — Control Intelligence follow-ups:
 - GET /api/control-intelligence/owner-nudges/preview (live -> at_risk 0)
 - GET /api/control-intelligence/owner-nudges/preview?demo=true (at_risk 2, 2 owners, groups[], recipients[])
 - PUT /api/control-intelligence/settings with role objects — lowercased, invalid dropped, roles preserved
 - Legacy string recipients coerce to role 'board'
 - GET /api/control-intelligence/brief/preview returns HTML
 - POST /api/control-intelligence/email-brief returns {sent:N}
 - Cleanup: reset settings
"""
import os
import pytest
import requests

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
ADMIN_EMAIL = "jblan2026@gmail.com"
ADMIN_PW = "Obserra2026!"


@pytest.fixture(scope="module")
def admin_session():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login",
               json={"email": ADMIN_EMAIL, "password": ADMIN_PW}, timeout=30)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    return s


class TestOwnerNudgePreview:
    def test_preview_live_at_risk_zero(self, admin_session):
        r = admin_session.get(
            f"{BASE_URL}/api/control-intelligence/owner-nudges/preview", timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d.get("at_risk") == 0, d
        assert isinstance(d.get("groups", []), list)
        assert isinstance(d.get("recipients", []), list)

    def test_preview_demo_at_risk_two(self, admin_session):
        r = admin_session.get(
            f"{BASE_URL}/api/control-intelligence/owner-nudges/preview?demo=true", timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d.get("at_risk") == 2, d
        assert d.get("owners") == 2, d
        assert d.get("demo") is True
        groups = d.get("groups", [])
        assert len(groups) == 2
        owner_names = sorted(g["owner"] for g in groups)
        assert owner_names == ["Dana Ops", "Sam Vuln"], owner_names
        for g in groups:
            assert "count" in g and g["count"] >= 1
            assert isinstance(g.get("controls", []), list)
        assert isinstance(d.get("recipients", []), list)

    def test_preview_does_not_persist(self, admin_session):
        # After demo call, subsequent live call still 0
        r = admin_session.get(
            f"{BASE_URL}/api/control-intelligence/owner-nudges/preview", timeout=30)
        assert r.status_code == 200
        assert r.json().get("at_risk") == 0


class TestRecipientRoles:
    def test_put_role_objects_lowercase_dedupe_drop_invalid(self, admin_session):
        payload = {
            "recipients": [
                {"email": "Board@Co.com", "role": "board"},
                {"email": "auditor@co.com", "role": "auditor"},
                {"email": "BADEMAIL", "role": "board"},
            ],
            "send_day": 5,
            "enabled": True,
        }
        r = admin_session.put(
            f"{BASE_URL}/api/control-intelligence/settings", json=payload, timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        recips = d["recipients"]
        # Accept either list-of-dict or list-of-str; expect dict per spec
        assert isinstance(recips, list) and len(recips) == 2, recips
        # Normalize for comparison
        norm = [(x["email"], x["role"]) if isinstance(x, dict) else (x, "board") for x in recips]
        assert ("board@co.com", "board") in norm
        assert ("auditor@co.com", "auditor") in norm

        # Round-trip GET returns same
        r2 = admin_session.get(
            f"{BASE_URL}/api/control-intelligence/settings", timeout=30)
        assert r2.status_code == 200
        d2 = r2.json()
        recips2 = d2["recipients"]
        assert len(recips2) == 2
        norm2 = [(x["email"], x["role"]) if isinstance(x, dict) else (x, "board") for x in recips2]
        assert ("board@co.com", "board") in norm2
        assert ("auditor@co.com", "auditor") in norm2

    def test_legacy_string_coerces_to_board(self, admin_session):
        r = admin_session.put(
            f"{BASE_URL}/api/control-intelligence/settings",
            json={"recipients": ["Legacy@Co.com"], "send_day": 3, "enabled": False}, timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        recips = d["recipients"]
        assert len(recips) == 1
        x = recips[0]
        if isinstance(x, dict):
            assert x["email"] == "legacy@co.com"
            assert x["role"] == "board"
        else:
            assert x == "legacy@co.com"


class TestBriefPreview:
    def test_brief_preview_returns_html(self, admin_session):
        r = admin_session.get(
            f"{BASE_URL}/api/control-intelligence/brief/preview", timeout=30)
        assert r.status_code == 200, r.text
        # Endpoint returns JSON with `html` field (rendered via iframe srcDoc)
        d = r.json()
        assert "html" in d and isinstance(d["html"], str)
        assert len(d["html"]) > 500
        assert "<table" in d["html"].lower() or "<html" in d["html"].lower()


class TestEmailBriefOnce:
    def test_email_brief_endpoint_ok(self, admin_session):
        # Set to safe fake recipient to avoid spamming, then call ONCE
        admin_session.put(
            f"{BASE_URL}/api/control-intelligence/settings",
            json={"recipients": [{"email": "sink@example.com", "role": "board"}],
                  "send_day": 1, "enabled": False}, timeout=30)
        r = admin_session.post(
            f"{BASE_URL}/api/control-intelligence/email-brief", timeout=90)
        assert r.status_code == 200, r.text
        d = r.json()
        assert "sent" in d
        assert isinstance(d["sent"], int)


class TestCleanup:
    def test_reset_settings(self, admin_session):
        r = admin_session.put(
            f"{BASE_URL}/api/control-intelligence/settings",
            json={"recipients": [], "send_day": 1, "enabled": False}, timeout=30)
        assert r.status_code == 200
        d = r.json()
        assert d["recipients"] == []
        assert d["send_day"] == 1
        assert d["enabled"] is False
