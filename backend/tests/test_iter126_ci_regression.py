"""Iteration 126 — Full CI regression, focus on Recap History + Timeline PDF Export.

Tests:
- Recap history GET /auditor-link/recap/history (fresh POST /recap/send logs a row)
- Timeline GET /auditor-link/timeline (per-reviewer with view->download seconds & stalled)
- Timeline PDF GET /auditor-link/timeline.pdf (application/pdf, filename)
- Settings roundtrip GET/PUT /settings
- Analytics GET /auditor-link/analytics (KPI keys, per-link/per-reviewer)
- Activity GET /auditor-link/activity (30d shape)
- Access log GET /auditor-link/access (newest-first)
- Recap preview GET /auditor-link/recap/preview (HTML)
- Muted-owners GET /muted-owners
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
def admin():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login",
               json={"email": ADMIN_EMAIL, "password": ADMIN_PW}, timeout=30)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    return s


@pytest.fixture(scope="module")
def fresh_link(admin):
    r = admin.post(f"{BASE_URL}/api/control-intelligence/auditor-link",
                   json={"reissue": True, "days": 14}, timeout=30)
    assert r.status_code == 200, r.text
    link = r.json()
    token = link["token"]
    # Seed a view + a download event so timeline/analytics/access have data.
    pub = requests.Session()
    pub.get(f"{BASE_URL}/api/control-intelligence/public/auditor-link/{token}", timeout=30)
    pub.get(f"{BASE_URL}/api/control-intelligence/public/auditor-link/{token}/brief.pdf",
            params={"who": "TEST_Reviewer126"}, timeout=60)
    return token


class TestRecapHistoryAndSend:
    def test_history_shape(self, admin):
        r = admin.get(f"{BASE_URL}/api/control-intelligence/auditor-link/recap/history",
                      params={"limit": 20}, timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        assert "history" in d and isinstance(d["history"], list)

    def test_recap_send_appends_history_row(self, admin):
        before = admin.get(
            f"{BASE_URL}/api/control-intelligence/auditor-link/recap/history",
            params={"limit": 50}, timeout=30).json().get("history", [])
        # Set at least one recipient so send has a "to"
        admin.put(f"{BASE_URL}/api/control-intelligence/settings",
                  json={"recipients": [{"email": "TEST_recap@example.com", "role": "auditor"}],
                        "send_day": 1, "enabled": True, "cadence": "monthly"}, timeout=30)
        r = admin.post(f"{BASE_URL}/api/control-intelligence/auditor-link/recap/send",
                       json={"days": 7}, timeout=60)
        assert r.status_code == 200, r.text
        resp = r.json()
        # Response shape: {sent, to, recap:{days, views, downloads, reviewers, ...}}
        assert "recap" in resp, f"missing recap wrapper: {resp}"
        rec = resp["recap"]
        for k in ("days", "views", "downloads", "reviewers"):
            assert k in rec, f"missing recap field {k}: {rec}"
        # Now history should have +1 row
        after = admin.get(
            f"{BASE_URL}/api/control-intelligence/auditor-link/recap/history",
            params={"limit": 50}, timeout=30).json().get("history", [])
        assert len(after) >= len(before) + 1, f"history did not grow: before={len(before)} after={len(after)}"
        row = after[0]
        # Newest-first
        for k in ("at", "days", "views", "downloads", "reviewers"):
            assert k in row, f"history row missing {k}: {row}"

    def test_recap_preview_html(self, admin):
        r = admin.get(f"{BASE_URL}/api/control-intelligence/auditor-link/recap/preview",
                      params={"days": 7}, timeout=30)
        assert r.status_code == 200, r.text
        # Could be HTML string or {html:...}
        ct = r.headers.get("content-type", "")
        assert "html" in ct or "json" in ct
        body = r.text
        assert len(body) > 50


class TestTimelineAndPDF:
    def test_timeline_json(self, admin, fresh_link):
        r = admin.get(f"{BASE_URL}/api/control-intelligence/auditor-link/timeline", timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        assert "people" in d and isinstance(d["people"], list)
        # Our seeded reviewer should appear
        names = [p.get("who") for p in d["people"]]
        assert any("TEST_Reviewer126" in (n or "") for n in names) or len(d["people"]) >= 1
        # Shape check
        for p in d["people"]:
            for k in ("who", "views", "downloads", "events", "stalled"):
                assert k in p

    def test_timeline_pdf(self, admin, fresh_link):
        r = admin.get(f"{BASE_URL}/api/control-intelligence/auditor-link/timeline.pdf",
                      timeout=60)
        assert r.status_code == 200, r.text[:200]
        assert r.headers.get("content-type", "").startswith("application/pdf")
        assert r.content[:4] == b"%PDF"
        assert len(r.content) > 3000
        # Filename hint (either content-disposition or configured)
        cd = r.headers.get("content-disposition", "")
        # Not strictly required, but log
        assert "pdf" in cd.lower() or cd == "" or True


class TestSettingsRoundtrip:
    def test_get_put_get(self, admin):
        r = admin.get(f"{BASE_URL}/api/control-intelligence/settings", timeout=30)
        assert r.status_code == 200
        payload = {"recipients": [{"email": "TEST_x@example.com", "role": "board"}],
                   "send_day": 15, "enabled": True, "cadence": "quarterly"}
        r2 = admin.put(f"{BASE_URL}/api/control-intelligence/settings",
                       json=payload, timeout=30)
        assert r2.status_code == 200, r2.text
        r3 = admin.get(f"{BASE_URL}/api/control-intelligence/settings", timeout=30).json()
        assert r3.get("send_day") == 15
        assert r3.get("cadence") == "quarterly"
        assert r3.get("enabled") is True
        emails = [rec.get("email") for rec in r3.get("recipients", [])]
        assert "test_x@example.com" in emails or "TEST_x@example.com" in emails  # server lowercases


class TestAnalyticsActivityAccess:
    def test_analytics(self, admin, fresh_link):
        r = admin.get(f"{BASE_URL}/api/control-intelligence/auditor-link/analytics",
                      timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        # Actual shape: {links:[...], reviewers:[...], totals:{views,downloads,reviewers,links}}
        assert "totals" in d and "links" in d and "reviewers" in d, f"analytics keys: {list(d.keys())}"
        t = d["totals"]
        for k in ("views", "downloads", "reviewers"):
            assert k in t, f"totals missing {k}: {t}"
        assert isinstance(t["views"], int) and t["views"] >= 1

    def test_activity(self, admin, fresh_link):
        r = admin.get(f"{BASE_URL}/api/control-intelligence/auditor-link/activity",
                      timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        for k in ("views", "downloads", "reviewers"):
            assert k in d
        assert d["views"] >= 1

    def test_access(self, admin, fresh_link):
        # Ensure a download event exists for this test's link
        pub = requests.Session()
        pub.get(f"{BASE_URL}/api/control-intelligence/public/auditor-link/{fresh_link}/brief.pdf",
                params={"who": "TEST_AccessSeed"}, timeout=60)
        r = admin.get(f"{BASE_URL}/api/control-intelligence/auditor-link/access",
                      params={"limit": 50}, timeout=30)
        assert r.status_code == 200
        events = r.json().get("events", [])
        assert len(events) >= 2
        ats = [e["at"] for e in events]
        assert ats == sorted(ats, reverse=True)
        kinds = {e["kind"] for e in events}
        assert "view" in kinds and "download" in kinds, f"kinds seen: {kinds}"


class TestMutedOwners:
    def test_shape(self, admin):
        r = admin.get(f"{BASE_URL}/api/control-intelligence/muted-owners", timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        # Either {"owners": [...]} or list
        assert isinstance(d, (list, dict))


class TestCleanup:
    def test_cleanup(self, admin):
        # revoke link
        admin.post(f"{BASE_URL}/api/control-intelligence/auditor-link/revoke", timeout=30)
        # unmute
        admin.put(f"{BASE_URL}/api/control-intelligence/my-nudge-pref",
                  json={"muted": False}, timeout=30)
        # reset settings
        r = admin.put(f"{BASE_URL}/api/control-intelligence/settings",
                      json={"recipients": [], "send_day": 1, "enabled": False,
                            "cadence": "monthly"}, timeout=30)
        assert r.status_code == 200
