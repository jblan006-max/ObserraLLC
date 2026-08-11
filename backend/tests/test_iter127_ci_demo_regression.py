"""Iteration 127 — Regression after ci_demo.py backend extraction + Demo Everywhere
+ Recap Auto-Send.

Focus:
- ci_demo.py routes (demo/state, seed, clear, status) attached to ci_router still register.
- Rest of Control Intelligence suite intact (settings/eff-history/auditor-link/activity/
  recap history+preview, timeline, analytics, follow-up nudge, access log, timeline.pdf).
- Recap auto-send state persistence.
- Public auditor portal token still resolves.
"""
import os
import pytest
import requests

def _read_frontend_url():
    p = "/app/frontend/.env"
    with open(p) as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                return line.split("=", 1)[1].strip()
    raise RuntimeError("REACT_APP_BACKEND_URL missing")

BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or _read_frontend_url()).rstrip("/")
ADMIN_EMAIL = "jblan2026@gmail.com"
ADMIN_PASSWORD = "Obserra2026!"


@pytest.fixture(scope="module")
def client():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login",
               json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=20)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text[:200]}"
    return s


@pytest.fixture(scope="module", autouse=True)
def _cleanup(client):
    yield
    # Leave a clean state — clear demo if still active, but DO NOT touch recap toggle.
    try:
        client.post(f"{BASE_URL}/api/control-intelligence/auditor-link/demo/clear", timeout=20)
    except Exception:
        pass


# ---------- ci_demo.py routes ----------

class TestCiDemoRoutes:
    def test_demo_state_initial_or_clear(self, client):
        # Ensure clean starting point
        client.post(f"{BASE_URL}/api/control-intelligence/auditor-link/demo/clear", timeout=20)
        r = client.get(f"{BASE_URL}/api/control-intelligence/demo/state", timeout=15)
        assert r.status_code == 200
        assert r.json().get("active") is False

    def test_demo_seed_response(self, client):
        r = client.post(f"{BASE_URL}/api/control-intelligence/auditor-link/demo/seed", timeout=25)
        assert r.status_code == 200, r.text[:200]
        d = r.json()
        assert d.get("seeded") is True
        assert d.get("events") == 6
        assert d.get("links") == 2
        assert d.get("reviewers") == 2

    def test_demo_state_active_after_seed(self, client):
        r = client.get(f"{BASE_URL}/api/control-intelligence/demo/state", timeout=15)
        assert r.status_code == 200
        assert r.json().get("active") is True

    def test_demo_status_counters(self, client):
        r = client.get(f"{BASE_URL}/api/control-intelligence/auditor-link/demo/status", timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert d["active"] is True
        assert d["events"] >= 6
        assert d["links"] >= 2
        assert d["recaps"] >= 1

    def test_access_log_has_demo_rows(self, client):
        r = client.get(f"{BASE_URL}/api/control-intelligence/auditor-link/access?limit=20", timeout=15)
        assert r.status_code == 200
        payload = r.json()
        rows = payload if isinstance(payload, list) else (payload.get("events") or payload.get("rows") or payload.get("access") or [])
        who_all = " ".join([(row.get("who") or "").lower() for row in rows])
        assert "priya" in who_all and "elena" in who_all and "marcus" in who_all, f"missing demo reviewers, got: {who_all[:400]}"

    def test_analytics_reflects_demo(self, client):
        r = client.get(f"{BASE_URL}/api/control-intelligence/auditor-link/analytics", timeout=15)
        assert r.status_code == 200
        d = r.json()
        totals = d.get("totals", d)
        # 4 views (Priya 1 + Elena 1 + Marcus 2), 2 downloads (Priya+Elena), 2 reviewers (Marcus never downloaded).
        assert totals.get("views", 0) >= 4
        assert totals.get("downloads", 0) >= 2
        assert totals.get("reviewers", 0) >= 2

    def test_controls_demo_flag_shows_iam3(self, client):
        r = client.get(f"{BASE_URL}/api/controls?demo=true", timeout=20)
        assert r.status_code == 200
        controls = r.json() if isinstance(r.json(), list) else r.json().get("controls", [])
        at_risk = [c for c in controls if c.get("demo_at_risk")]
        assert len(at_risk) >= 2, f"expected >=2 demo_at_risk controls, got {len(at_risk)}"
        # First flipped is Failing at 47% (per _apply_demo_at_risk)
        failing = [c for c in at_risk if c.get("status") == "Failing"]
        assert failing and failing[0].get("effectiveness") == 47

    def test_recap_preview_includes_dana_ops(self, client):
        r = client.get(f"{BASE_URL}/api/control-intelligence/auditor-link/recap/preview", timeout=20)
        assert r.status_code == 200
        # preview returns HTML or JSON — accept both
        body = r.text.lower()
        assert "dana" in body, "recap preview should reference nudged owner Dana Ops"

    def test_demo_clear(self, client):
        r = client.post(f"{BASE_URL}/api/control-intelligence/auditor-link/demo/clear", timeout=20)
        assert r.status_code == 200
        assert r.json().get("cleared") is True

    def test_demo_state_inactive_after_clear(self, client):
        r = client.get(f"{BASE_URL}/api/control-intelligence/demo/state", timeout=15)
        assert r.status_code == 200
        assert r.json().get("active") is False


# ---------- Regression: rest of CI suite ----------

class TestCiRegression:
    def test_settings_get(self, client):
        r = client.get(f"{BASE_URL}/api/control-intelligence/settings", timeout=15)
        assert r.status_code == 200
        assert isinstance(r.json(), dict)

    def test_recap_settings_persistence(self, client):
        # Enable recap and set Monday (0)
        r = client.put(f"{BASE_URL}/api/control-intelligence/settings",
                       json={"recap_enabled": True, "recap_weekday": 0}, timeout=15)
        assert r.status_code == 200
        r2 = client.get(f"{BASE_URL}/api/control-intelligence/settings", timeout=15)
        assert r2.status_code == 200
        d = r2.json()
        assert d.get("recap_enabled") is True
        assert d.get("recap_weekday") == 0

    def test_effectiveness_history(self, client):
        r = client.get(f"{BASE_URL}/api/control-intelligence/effectiveness-history", timeout=15)
        assert r.status_code == 200

    def test_auditor_link_activity(self, client):
        r = client.get(f"{BASE_URL}/api/control-intelligence/auditor-link/activity", timeout=15)
        assert r.status_code == 200
        d = r.json()
        for k in ("views", "downloads", "reviewers"):
            assert k in d

    def test_recap_history(self, client):
        r = client.get(f"{BASE_URL}/api/control-intelligence/auditor-link/recap/history", timeout=15)
        assert r.status_code == 200
        d = r.json()
        history = d if isinstance(d, list) else d.get("history")
        assert isinstance(history, list)

    def test_timeline(self, client):
        r = client.get(f"{BASE_URL}/api/control-intelligence/auditor-link/timeline", timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert "people" in d

    def test_timeline_pdf(self, client):
        r = client.get(f"{BASE_URL}/api/control-intelligence/auditor-link/timeline.pdf", timeout=30)
        assert r.status_code == 200
        assert r.headers.get("content-type", "").startswith("application/pdf")
        assert r.content[:4] == b"%PDF"

    def test_auditor_link_generate_reissue_revoke(self, client):
        gen = client.post(f"{BASE_URL}/api/control-intelligence/auditor-link",
                          json={"expires_days": 30}, timeout=15)
        assert gen.status_code == 200, gen.text[:200]
        d = gen.json()
        token = d.get("token") or (d.get("link") or {}).get("token")
        assert token
        # public portal resolution
        pub = requests.get(f"{BASE_URL}/api/control-intelligence/public/auditor-link/{token}/meta", timeout=15)
        assert pub.status_code == 200, f"public meta returned {pub.status_code}"
        # Reissue by generating again (existing route; iteration_126 confirmed reissue is idempotent generate)
        rei = client.post(f"{BASE_URL}/api/control-intelligence/auditor-link",
                          json={"expires_days": 30}, timeout=15)
        assert rei.status_code == 200
        rev = client.post(f"{BASE_URL}/api/control-intelligence/auditor-link/revoke", timeout=15)
        assert rev.status_code == 200

    def test_follow_up_nudge_preview(self, client):
        r = client.get(f"{BASE_URL}/api/control-intelligence/owner-nudges/preview", timeout=15)
        assert r.status_code == 200
