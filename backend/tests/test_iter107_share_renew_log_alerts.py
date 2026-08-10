"""Iter107 — Share Center follow-ups: Renew, per-card Access Log, first-time Engagement Alerts."""
import os
import time
import pytest
import requests

BASE = os.environ.get("REACT_APP_BACKEND_URL") or ""
if not BASE:
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                BASE = line.split("=", 1)[1].strip()
BASE = BASE.rstrip("/")
API = f"{BASE}/api"

ADMIN_EMAIL = "jblan2026@gmail.com"
ADMIN_PW = "Obserra2026!"


@pytest.fixture(scope="module")
def admin_session():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PW}, timeout=30)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text[:200]}"
    return s


def _mint(admin_session, title_suffix=""):
    payload = {
        "title": f"TEST_Iter107 Card {title_suffix}",
        "ref": "TEST-107-001",
        "kind": "incident",
        "rating": "Medium",
        "score": 60,
        "connectors": [{"name": "Agent runtime", "detail": "signed webhook", "status": "ok"}],
        "facets": [{"label": "Outcome", "value": "Investigate"}],
        "recommendations": ["Review"],
        "summary": "iter107 test card",
        "days": 3,
    }
    r = admin_session.post(f"{API}/agents/runtime/card-share", json=payload, timeout=30)
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture()
def fresh_token(admin_session):
    tok = _mint(admin_session, str(int(time.time())))
    yield tok
    admin_session.post(f"{API}/agents/runtime/card-share/revoke", json={"token": tok}, timeout=15)


# ── Renew ─────────────────────────────────────────────────────────────
class TestRenew:
    def test_renew_extends_expiry_by_14_days(self, admin_session, fresh_token):
        # baseline expiry from list
        lst = admin_session.get(f"{API}/agents/runtime/card-shares", timeout=15).json()["cards"]
        before = next(c for c in lst if c["token"] == fresh_token)
        old_exp = before["expires_at"]

        r = admin_session.post(f"{API}/agents/runtime/card-share/renew",
                               json={"token": fresh_token, "days": 14}, timeout=15)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["ok"] is True
        assert body["token"] == fresh_token
        assert body["days"] == 14
        assert "expires_at" in body and body["expires_at"] > old_exp

        # verify persistence via list
        lst2 = admin_session.get(f"{API}/agents/runtime/card-shares", timeout=15).json()["cards"]
        after = next(c for c in lst2 if c["token"] == fresh_token)
        assert after["expires_at"] == body["expires_at"]

    def test_renew_unknown_token_404(self, admin_session):
        r = admin_session.post(f"{API}/agents/runtime/card-share/renew",
                               json={"token": "nosuchtoken123", "days": 14}, timeout=15)
        assert r.status_code == 404

    def test_renew_unauth(self, fresh_token):
        r = requests.post(f"{API}/agents/runtime/card-share/renew",
                          json={"token": fresh_token, "days": 14}, timeout=15)
        assert r.status_code in (401, 403)


# ── Access Log + Engagement Alerts ─────────────────────────────────────
class TestAccessLogAndAlerts:
    def test_access_log_empty_initially(self, admin_session, fresh_token):
        r = admin_session.get(f"{API}/agents/runtime/card-share/{fresh_token}/access-log", timeout=15)
        assert r.status_code == 200
        b = r.json()
        assert b["opens"] == 0 and b["downloads"] == 0
        assert b["access"] == []

    def test_public_opens_write_access_rows_and_admin_stats_unchanged(self, admin_session, fresh_token):
        # admin stats endpoint MUST NOT increment
        s0 = admin_session.get(f"{API}/agents/runtime/card-share/{fresh_token}/stats", timeout=15).json()
        assert s0["opens"] == 0

        # two public opens
        for _ in range(2):
            r = requests.get(f"{API}/agents/public/card-share/{fresh_token}", timeout=15)
            assert r.status_code == 200
            time.sleep(0.2)

        # one public PDF download with name
        r = requests.get(f"{API}/agents/public/card-share/{fresh_token}/card.pdf",
                         params={"who": "Jane Auditor"}, timeout=30)
        assert r.status_code == 200
        assert r.headers.get("content-type", "").startswith("application/pdf")

        # admin stats still not incremented (it just reads counters)
        # But counters WERE incremented by public endpoints — so opens=2, downloads=1
        s1 = admin_session.get(f"{API}/agents/runtime/card-share/{fresh_token}/stats", timeout=15).json()
        assert s1["opens"] == 2, f"opens={s1['opens']}"
        assert s1["downloads"] == 1

        # access log rows
        log = admin_session.get(f"{API}/agents/runtime/card-share/{fresh_token}/access-log", timeout=15).json()
        assert log["opens"] == 2 and log["downloads"] == 1
        assert log.get("last_downloaded_by") == "Jane Auditor"
        rows = log["access"]
        assert len(rows) == 3, f"expected 3 rows, got {len(rows)}: {rows}"
        kinds = sorted([r["kind"] for r in rows])
        assert kinds == ["download", "open", "open"]
        for row in rows:
            assert "ip" in row
            assert "at" in row
            if row["kind"] == "download":
                assert row.get("who") == "Jane Auditor"
            else:
                # open rows should have who=None/null
                assert not row.get("who")

    def test_engagement_alerts_fire_once_only(self, admin_session, fresh_token):
        # fresh notif snapshot before any public activity
        pre = admin_session.get(f"{API}/notifications", timeout=15).json()
        pre_items = pre.get("items", pre) if isinstance(pre, dict) else pre
        def _engage_count(items):
            return sum(1 for n in items
                       if (n.get("title") or "").lower() == "shared card engagement")
        pre_count = _engage_count(pre_items)

        # first open → should create ONE engagement notification
        requests.get(f"{API}/agents/public/card-share/{fresh_token}", timeout=15)
        time.sleep(1.0)
        # second open → should NOT create another
        requests.get(f"{API}/agents/public/card-share/{fresh_token}", timeout=15)
        time.sleep(1.0)

        # first download with a name → ONE more engagement notif
        requests.get(f"{API}/agents/public/card-share/{fresh_token}/card.pdf",
                     params={"who": "Alice Auditor"}, timeout=30)
        time.sleep(1.0)
        # second download → should NOT create another
        requests.get(f"{API}/agents/public/card-share/{fresh_token}/card.pdf",
                     params={"who": "Alice Auditor"}, timeout=30)
        time.sleep(1.0)

        post = admin_session.get(f"{API}/notifications", timeout=15).json()
        post_items = post.get("items", post) if isinstance(post, dict) else post
        delta = _engage_count(post_items) - pre_count
        assert delta == 2, f"expected exactly 2 new 'Shared card engagement' notifs (open+download), got {delta}"

        # verify body text mentions the auditor + the card title on the download alert
        titles_bodies = [(n.get("title"), n.get("body") or "") for n in post_items
                         if (n.get("title") or "").lower() == "shared card engagement"][:5]
        assert any("Alice Auditor" in b and "downloaded" in b.lower() for _, b in titles_bodies), titles_bodies
        assert any("opened" in b.lower() for _, b in titles_bodies), titles_bodies

    def test_access_log_unknown_token_404(self, admin_session):
        r = admin_session.get(f"{API}/agents/runtime/card-share/nosuchtoken123/access-log", timeout=15)
        assert r.status_code == 404
