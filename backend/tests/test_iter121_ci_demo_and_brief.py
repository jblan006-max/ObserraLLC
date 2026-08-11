"""Iteration 121 — Control Intelligence P0 batch:
 - GET /api/controls (baseline all Passing)
 - GET /api/controls?demo=true (non-persistent overlay: 1 Failing eff=47, 1 Drifting eff=61)
 - Baseline persistence: subsequent /api/controls (no demo) still all Passing
 - PUT/GET /api/control-intelligence/settings (validation, dedupe/lowercase, day clamp)
 - POST /api/control-intelligence/email-brief (returns {sent: N})
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


class TestControlsDemoOverlay:
    def test_baseline_all_passing_24(self, admin_session):
        r = admin_session.get(f"{BASE_URL}/api/controls", timeout=30)
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        assert len(data) == 24, f"expected 24 controls, got {len(data)}"
        statuses = [c["status"] for c in data]
        assert all(s == "Passing" for s in statuses), f"non-passing baseline: {statuses}"
        # Guard: nothing should be demo-flagged in baseline
        assert not any(c.get("demo_at_risk") for c in data)

    def test_demo_overlay_flips_two(self, admin_session):
        r = admin_session.get(f"{BASE_URL}/api/controls?demo=true", timeout=30)
        assert r.status_code == 200
        data = r.json()
        assert len(data) == 24
        flagged = [c for c in data if c.get("demo_at_risk")]
        assert len(flagged) == 2, f"expected exactly 2 demo_at_risk, got {len(flagged)}"

        failing = [c for c in flagged if c["status"] == "Failing"]
        drifting = [c for c in flagged if c["status"] == "Drifting"]
        assert len(failing) == 1 and len(drifting) == 1
        assert failing[0]["effectiveness"] == 47
        assert drifting[0]["effectiveness"] == 61
        assert drifting[0].get("drift") is True
        assert failing[0].get("drift") is True

    def test_demo_is_not_persisted(self, admin_session):
        # after demo call, next non-demo call must be all Passing again
        r = admin_session.get(f"{BASE_URL}/api/controls", timeout=30)
        assert r.status_code == 200
        data = r.json()
        assert all(c["status"] == "Passing" for c in data)
        assert not any(c.get("demo_at_risk") for c in data)


class TestCIBriefSettings:
    def test_get_settings_shape(self, admin_session):
        r = admin_session.get(f"{BASE_URL}/api/control-intelligence/settings", timeout=30)
        assert r.status_code == 200
        d = r.json()
        assert "recipients" in d and isinstance(d["recipients"], list)
        assert "send_day" in d and 1 <= d["send_day"] <= 28
        assert "enabled" in d and isinstance(d["enabled"], bool)

    def test_put_validation_dedupe_lowercase_clamp(self, admin_session):
        r = admin_session.put(
            f"{BASE_URL}/api/control-intelligence/settings",
            json={
                "recipients": ["a@b.com", "BADEMAIL", "A@B.COM"],
                "send_day": 40,
                "enabled": True,
            }, timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["recipients"] == ["a@b.com"], d["recipients"]
        assert d["send_day"] == 28
        assert d["enabled"] is True

        # Round-trip GET
        r2 = admin_session.get(f"{BASE_URL}/api/control-intelligence/settings", timeout=30)
        assert r2.status_code == 200
        d2 = r2.json()
        assert d2["recipients"] == ["a@b.com"]
        assert d2["send_day"] == 28
        assert d2["enabled"] is True

    def test_send_brief_now(self, admin_session):
        # ensure at least one recipient exists (from prior test)
        r = admin_session.post(
            f"{BASE_URL}/api/control-intelligence/email-brief", timeout=90)
        assert r.status_code == 200, r.text
        d = r.json()
        assert "sent" in d
        assert isinstance(d["sent"], int)
        # Recipient is a@b.com (fake) — Resend may error per address but endpoint should not 500.

    def test_cleanup_reset_settings(self, admin_session):
        r = admin_session.put(
            f"{BASE_URL}/api/control-intelligence/settings",
            json={"recipients": [], "send_day": 1, "enabled": False}, timeout=30)
        assert r.status_code == 200
        d = r.json()
        assert d["recipients"] == []
        assert d["send_day"] == 1
        assert d["enabled"] is False
