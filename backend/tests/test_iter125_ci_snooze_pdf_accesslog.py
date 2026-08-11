"""Iteration 125 — Control Intelligence enhancements:
 - Owner snooze/mute PUT /my-nudge-pref (snooze_days=30, muted=true, unmute)
 - _muted_emails suppression via ci_nudge_muted OR ci_nudge_muted_until>now (indirect via owner-nudges/preview demo)
 - Public PDF still 200 application/pdf starting %PDF (branded)
 - Auditor access log: GET /auditor-link/access newest-first, view+download events
 - Cleanup at end
"""
import os
import pytest
import requests
from datetime import datetime, timezone

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


class TestNudgePref:
    def test_get_default_shape(self, admin_session):
        # Ensure clean state first
        admin_session.put(f"{BASE_URL}/api/control-intelligence/my-nudge-pref",
                          json={"muted": False}, timeout=30)
        r = admin_session.get(f"{BASE_URL}/api/control-intelligence/my-nudge-pref", timeout=30)
        assert r.status_code == 200
        d = r.json()
        assert set(d.keys()) >= {"muted", "muted_until", "active"}
        assert d["muted"] is False
        assert d["muted_until"] is None
        assert d["active"] is False

    def test_snooze_30d_sets_muted_until_active(self, admin_session):
        r = admin_session.put(f"{BASE_URL}/api/control-intelligence/my-nudge-pref",
                              json={"snooze_days": 30}, timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["muted"] is False
        assert d["active"] is True
        assert d["muted_until"] is not None
        # muted_until ~30d in future
        until = datetime.fromisoformat(d["muted_until"].replace("Z", "+00:00"))
        delta = (until - datetime.now(timezone.utc)).total_seconds()
        assert 28 * 86400 < delta < 32 * 86400, f"unexpected delta {delta}"

        # GET returns same
        r2 = admin_session.get(f"{BASE_URL}/api/control-intelligence/my-nudge-pref", timeout=30)
        d2 = r2.json()
        assert d2["active"] is True and d2["muted"] is False and d2["muted_until"] is not None

    def test_mute_indefinite(self, admin_session):
        r = admin_session.put(f"{BASE_URL}/api/control-intelligence/my-nudge-pref",
                              json={"muted": True}, timeout=30)
        assert r.status_code == 200
        d = r.json()
        assert d["muted"] is True
        assert d["muted_until"] is None
        assert d["active"] is True

    def test_unmute(self, admin_session):
        r = admin_session.put(f"{BASE_URL}/api/control-intelligence/my-nudge-pref",
                              json={"muted": False}, timeout=30)
        assert r.status_code == 200
        d = r.json()
        assert d["muted"] is False
        assert d["muted_until"] is None
        assert d["active"] is False


class TestAuditorLinkPDFAndAccessLog:
    def test_pdf_and_access_events(self, admin_session):
        # Create a fresh auditor link
        r = admin_session.post(f"{BASE_URL}/api/control-intelligence/auditor-link",
                               json={"reissue": True, "days": 30}, timeout=30)
        assert r.status_code == 200, r.text
        link = r.json()
        assert link.get("active") is True
        token = link["token"]

        # 1) Public portal view (uses public session, no auth)
        s = requests.Session()
        rv = s.get(f"{BASE_URL}/api/control-intelligence/public/auditor-link/{token}", timeout=30)
        assert rv.status_code == 200, rv.text
        pv = rv.json()
        assert "org_name" in pv and "frameworks" in pv

        # 2) PDF download (public, ?who=)
        rp = s.get(f"{BASE_URL}/api/control-intelligence/public/auditor-link/{token}/brief.pdf",
                   params={"who": "TEST_Auditor"}, timeout=60)
        assert rp.status_code == 200, rp.text[:200]
        assert rp.headers.get("content-type", "").startswith("application/pdf")
        assert rp.content[:4] == b"%PDF"
        assert len(rp.content) > 3000

        # 3) Access log via admin
        ra = admin_session.get(f"{BASE_URL}/api/control-intelligence/auditor-link/access",
                               params={"limit": 12}, timeout=30)
        assert ra.status_code == 200, ra.text
        events = ra.json().get("events", [])
        assert isinstance(events, list) and len(events) >= 2

        # Newest-first ordering
        ats = [e["at"] for e in events]
        assert ats == sorted(ats, reverse=True), "events should be newest-first"

        # Filter to this token
        my = [e for e in events if e.get("token") == token]
        kinds = [e["kind"] for e in my]
        assert "view" in kinds and "download" in kinds

        download_ev = next(e for e in my if e["kind"] == "download")
        assert download_ev["who"] == "TEST_Auditor"
        view_ev = next(e for e in my if e["kind"] == "view")
        assert view_ev["who"] == ""
        for e in my:
            assert "org_id" in e and "at" in e

    def test_invalid_token_pdf_404(self, admin_session):
        r = requests.get(
            f"{BASE_URL}/api/control-intelligence/public/auditor-link/deadbeefbadtoken/brief.pdf",
            params={"who": "x"}, timeout=30)
        assert r.status_code == 404


class TestCleanup:
    def test_cleanup(self, admin_session):
        r = admin_session.put(f"{BASE_URL}/api/control-intelligence/my-nudge-pref",
                              json={"muted": False}, timeout=30)
        assert r.status_code == 200
        r2 = admin_session.post(f"{BASE_URL}/api/control-intelligence/auditor-link/revoke", timeout=30)
        assert r2.status_code == 200
        r3 = admin_session.put(
            f"{BASE_URL}/api/control-intelligence/settings",
            json={"recipients": [], "send_day": 1, "enabled": False, "cadence": "monthly"}, timeout=30)
        assert r3.status_code == 200
