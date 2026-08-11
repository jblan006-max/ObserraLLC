"""
Iteration 128 — CI refactor regression.
Verify NO endpoint 404s/500s after the ci_auditor.py + ci_recap.py extraction
from control_intelligence.py, and validate the Recap Recipients feature
(board + auditor recipients now included in recap/send `to` list).
"""
import os
import pytest
import requests

def _load_backend_url():
    v = os.environ.get("REACT_APP_BACKEND_URL")
    if v:
        return v.rstrip("/")
    try:
        with open("/app/frontend/.env") as f:
            for ln in f:
                if ln.startswith("REACT_APP_BACKEND_URL="):
                    return ln.split("=", 1)[1].strip().rstrip("/")
    except Exception:
        pass
    raise RuntimeError("REACT_APP_BACKEND_URL not set")

BASE = _load_backend_url()
EMAIL = "jblan2026@gmail.com"
PASSWORD = "Obserra2026!"


@pytest.fixture(scope="module")
def sess():
    s = requests.Session()
    r = s.post(f"{BASE}/api/auth/login", json={"email": EMAIL, "password": PASSWORD}, timeout=30)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text[:200]}"
    return s


@pytest.fixture(scope="module")
def minted_token(sess):
    r = sess.post(f"{BASE}/api/control-intelligence/auditor-link", json={}, timeout=30)
    assert r.status_code == 200, r.text[:200]
    tok = r.json().get("token") or r.json().get("auditor_link", {}).get("token")
    assert tok, r.json()
    yield tok
    # cleanup at module end
    sess.post(f"{BASE}/api/control-intelligence/auditor-link/revoke", json={}, timeout=30)


# ---------- Auditor group (ci_auditor.py) ----------
class TestAuditorGroup:
    def test_get_auditor_link(self, sess):
        r = sess.get(f"{BASE}/api/control-intelligence/auditor-link", timeout=30)
        assert r.status_code == 200, r.text[:200]

    def test_get_access(self, sess):
        r = sess.get(f"{BASE}/api/control-intelligence/auditor-link/access", timeout=30)
        assert r.status_code == 200

    def test_get_analytics(self, sess):
        r = sess.get(f"{BASE}/api/control-intelligence/auditor-link/analytics", timeout=30)
        assert r.status_code == 200
        data = r.json()
        assert "totals" in data or "links" in data

    def test_brief_recipients(self, sess):
        r = sess.get(f"{BASE}/api/control-intelligence/brief/recipients", timeout=30)
        assert r.status_code == 200

    def test_my_nudge_pref_get_and_put(self, sess):
        r = sess.get(f"{BASE}/api/control-intelligence/my-nudge-pref", timeout=30)
        assert r.status_code == 200
        current = r.json()
        r2 = sess.put(f"{BASE}/api/control-intelligence/my-nudge-pref",
                      json={"muted": bool(current.get("muted", False))}, timeout=30)
        assert r2.status_code == 200

    def test_muted_owners(self, sess):
        r = sess.get(f"{BASE}/api/control-intelligence/muted-owners", timeout=30)
        assert r.status_code == 200

    def test_brief_pdf(self, sess):
        r = sess.get(f"{BASE}/api/control-intelligence/brief.pdf", timeout=60)
        assert r.status_code == 200
        assert r.headers.get("content-type", "").startswith("application/pdf")
        assert r.content[:5] == b"%PDF-"

    def test_email_brief(self, sess):
        r = sess.post(f"{BASE}/api/control-intelligence/email-brief", json={}, timeout=60)
        assert r.status_code == 200, r.text[:200]

    def test_public_auditor_link_meta_and_pdf(self, sess, minted_token):
        r = sess.get(f"{BASE}/api/control-intelligence/public/auditor-link/{minted_token}", timeout=30)
        assert r.status_code == 200
        rp = sess.get(f"{BASE}/api/control-intelligence/public/auditor-link/{minted_token}/brief.pdf", timeout=60)
        assert rp.status_code == 200
        assert rp.headers.get("content-type", "").startswith("application/pdf")


# ---------- Recap group (ci_recap.py) ----------
class TestRecapGroup:
    def test_recap_preview(self, sess):
        r = sess.get(f"{BASE}/api/control-intelligence/auditor-link/recap/preview", timeout=30)
        assert r.status_code == 200

    def test_recap_history(self, sess):
        r = sess.get(f"{BASE}/api/control-intelligence/auditor-link/recap/history", timeout=30)
        assert r.status_code == 200
        assert "history" in r.json()

    def test_timeline(self, sess):
        r = sess.get(f"{BASE}/api/control-intelligence/auditor-link/timeline", timeout=30)
        assert r.status_code == 200
        assert "people" in r.json()

    def test_timeline_pdf(self, sess):
        r = sess.get(f"{BASE}/api/control-intelligence/auditor-link/timeline.pdf", timeout=60)
        assert r.status_code == 200
        assert r.headers.get("content-type", "").startswith("application/pdf")
        assert r.content[:5] == b"%PDF-"

    def test_activity(self, sess):
        r = sess.get(f"{BASE}/api/control-intelligence/auditor-link/activity", timeout=30)
        assert r.status_code == 200

    def test_follow_up(self, sess, minted_token):
        r = sess.post(f"{BASE}/api/control-intelligence/auditor-link/follow-up",
                      json={"token": minted_token}, timeout=30)
        assert r.status_code == 200, r.text[:200]
        data = r.json()
        assert "sent" in data and "to" in data

    def test_public_meta(self, sess, minted_token):
        r = sess.get(f"{BASE}/api/control-intelligence/public/auditor-link/{minted_token}/meta", timeout=30)
        assert r.status_code == 200


# ---------- Core (control_intelligence.py) ----------
class TestCore:
    def test_settings_get_put_roundtrip(self, sess):
        r = sess.get(f"{BASE}/api/control-intelligence/settings", timeout=30)
        assert r.status_code == 200
        original = r.json()
        # PUT identical to avoid mutation
        r2 = sess.put(f"{BASE}/api/control-intelligence/settings",
                      json=original, timeout=30)
        assert r2.status_code == 200

    def test_effectiveness_history(self, sess):
        r = sess.get(f"{BASE}/api/control-intelligence/effectiveness-history", timeout=30)
        assert r.status_code == 200

    def test_owner_nudges_preview(self, sess):
        r = sess.get(f"{BASE}/api/control-intelligence/owner-nudges/preview", timeout=30)
        assert r.status_code == 200

    def test_owner_nudges_post(self, sess):
        r = sess.post(f"{BASE}/api/control-intelligence/owner-nudges", json={}, timeout=60)
        assert r.status_code == 200

    def test_brief_preview(self, sess):
        r = sess.get(f"{BASE}/api/control-intelligence/brief/preview", timeout=30)
        assert r.status_code == 200


# ---------- Demo (ci_demo.py) ----------
class TestDemo:
    def test_demo_state(self, sess):
        r = sess.get(f"{BASE}/api/control-intelligence/demo/state", timeout=30)
        assert r.status_code == 200
        assert "active" in r.json() or "demo_active" in r.json() or isinstance(r.json(), dict)

    def test_demo_status(self, sess):
        r = sess.get(f"{BASE}/api/control-intelligence/auditor-link/demo/status", timeout=30)
        assert r.status_code == 200

    def test_demo_seed_and_clear(self, sess):
        r = sess.post(f"{BASE}/api/control-intelligence/auditor-link/demo/seed", json={}, timeout=60)
        assert r.status_code == 200
        r2 = sess.post(f"{BASE}/api/control-intelligence/auditor-link/demo/clear", json={}, timeout=60)
        assert r2.status_code == 200


# ---------- Recap Recipients feature ----------
class TestRecapRecipients:
    """Feature under test: recap now sends to admins + board + auditor recipients."""

    def test_recap_send_includes_board_and_auditor(self, sess):
        # Read original settings
        r0 = sess.get(f"{BASE}/api/control-intelligence/settings", timeout=30)
        assert r0.status_code == 200
        original = r0.json()

        # Set recipients
        board_email = "test_board_iter128@example.com"
        auditor_email = "test_auditor_iter128@example.com"
        new_settings = dict(original)
        new_settings["recipients"] = [
            {"email": board_email, "role": "board"},
            {"email": auditor_email, "role": "auditor"},
        ]
        rp = sess.put(f"{BASE}/api/control-intelligence/settings",
                      json=new_settings, timeout=30)
        assert rp.status_code == 200, rp.text[:300]

        try:
            # Send recap
            rs = sess.post(f"{BASE}/api/control-intelligence/auditor-link/recap/send",
                           json={}, timeout=60)
            assert rs.status_code == 200, rs.text[:300]
            data = rs.json()
            to_list = data.get("to") or data.get("recap", {}).get("to") or []
            to_lower = [str(x).lower() for x in to_list]
            assert board_email in to_lower, f"board email missing from to list: {to_list}"
            assert auditor_email in to_lower, f"auditor email missing from to list: {to_list}"
            # Admin present too
            assert any("jblan2026" in x for x in to_lower), f"admin missing from to list: {to_list}"
        finally:
            # cleanup: restore recipients to []
            restore = dict(original)
            if "recipients" not in restore:
                restore["recipients"] = []
            else:
                restore["recipients"] = []
            sess.put(f"{BASE}/api/control-intelligence/settings", json=restore, timeout=30)
            # Verify clean
            r_after = sess.get(f"{BASE}/api/control-intelligence/settings", timeout=30).json()
            assert r_after.get("recipients", []) == [], f"cleanup failed: {r_after.get('recipients')}"
