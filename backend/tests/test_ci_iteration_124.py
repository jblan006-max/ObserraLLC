"""Iteration 124: Owner mute, signed auditor PDF, auditor-link controls, send-now recipient count."""
import os
import pytest
import requests

BASE = (os.environ.get("REACT_APP_BACKEND_URL") or "https://cyber-dashboard-48.preview.emergentagent.com").rstrip("/")
EMAIL = "jblan2026@gmail.com"
PW = "Obserra2026!"


@pytest.fixture(scope="module")
def admin_sess():
    s = requests.Session()
    r = s.post(f"{BASE}/api/auth/login", json={"email": EMAIL, "password": PW}, timeout=30)
    assert r.status_code == 200, r.text
    return s


@pytest.fixture(scope="module", autouse=True)
def cleanup(admin_sess):
    yield
    # cleanup
    try:
        admin_sess.put(f"{BASE}/api/control-intelligence/my-nudge-pref", json={"muted": False}, timeout=30)
        admin_sess.post(f"{BASE}/api/control-intelligence/auditor-link/revoke", timeout=30)
        admin_sess.put(f"{BASE}/api/control-intelligence/settings",
                       json={"recipients": [], "send_day": 1, "enabled": False, "cadence": "monthly"}, timeout=30)
    except Exception:
        pass


# ---------- Owner mute backend ----------
class TestOwnerMute:
    def test_get_default_false(self, admin_sess):
        # start from a clean state
        admin_sess.put(f"{BASE}/api/control-intelligence/my-nudge-pref", json={"muted": False})
        r = admin_sess.get(f"{BASE}/api/control-intelligence/my-nudge-pref", timeout=30)
        assert r.status_code == 200
        assert r.json() == {"muted": False}

    def test_put_true_persists(self, admin_sess):
        r = admin_sess.put(f"{BASE}/api/control-intelligence/my-nudge-pref", json={"muted": True}, timeout=30)
        assert r.status_code == 200 and r.json()["muted"] is True
        r2 = admin_sess.get(f"{BASE}/api/control-intelligence/my-nudge-pref", timeout=30)
        assert r2.json()["muted"] is True

    def test_put_false_persists(self, admin_sess):
        r = admin_sess.put(f"{BASE}/api/control-intelligence/my-nudge-pref", json={"muted": False}, timeout=30)
        assert r.status_code == 200 and r.json()["muted"] is False
        r2 = admin_sess.get(f"{BASE}/api/control-intelligence/my-nudge-pref", timeout=30)
        assert r2.json()["muted"] is False

    def test_owner_nudge_preview_muted_reflection(self, admin_sess):
        # Mute the admin, then check demo preview has muted groups
        admin_sess.put(f"{BASE}/api/control-intelligence/my-nudge-pref", json={"muted": True})
        r = admin_sess.get(f"{BASE}/api/control-intelligence/owner-nudges/preview?demo=true", timeout=30)
        assert r.status_code == 200
        data = r.json()
        # Groups should have `muted` field. Personalized should exclude muted admin
        groups = data.get("groups") or data.get("owner_groups") or []
        assert isinstance(groups, list)
        has_muted_flag = any("muted" in g for g in groups)
        assert has_muted_flag, f"No 'muted' key in any group. Data: {data}"
        personalized = data.get("personalized") or []
        assert EMAIL not in personalized, f"Muted admin should not be in personalized list. Got: {personalized}"
        # reset
        admin_sess.put(f"{BASE}/api/control-intelligence/my-nudge-pref", json={"muted": False})


# ---------- Auditor link controls ----------
class TestAuditorLink:
    def test_revoke_then_get_inactive(self, admin_sess):
        admin_sess.post(f"{BASE}/api/control-intelligence/auditor-link/revoke", timeout=30)
        r = admin_sess.get(f"{BASE}/api/control-intelligence/auditor-link", timeout=30)
        assert r.status_code == 200
        assert r.json() == {"active": False}

    def test_generate_with_days(self, admin_sess):
        r = admin_sess.post(f"{BASE}/api/control-intelligence/auditor-link", json={"days": 30}, timeout=30)
        assert r.status_code == 200
        data = r.json()
        assert data["active"] is True
        assert "url" in data and "/ci-audit/" in data["url"]
        assert "token" in data and "expires_at" in data
        pytest.token = data["token"]

    def test_get_active(self, admin_sess):
        r = admin_sess.get(f"{BASE}/api/control-intelligence/auditor-link", timeout=30)
        assert r.status_code == 200
        data = r.json()
        assert data["active"] is True
        assert data.get("url", "").endswith(pytest.token) or pytest.token in data["url"]

    def test_reissue_new_token(self, admin_sess):
        old = pytest.token
        r = admin_sess.post(f"{BASE}/api/control-intelligence/auditor-link",
                            json={"reissue": True, "days": 60}, timeout=30)
        assert r.status_code == 200
        data = r.json()
        assert data["active"] is True and data["token"] != old
        # Old token should now be revoked → public endpoint 404
        r_old = requests.get(f"{BASE}/api/control-intelligence/public/auditor-link/{old}", timeout=30)
        assert r_old.status_code == 404
        pytest.token = data["token"]

    def test_revoke(self, admin_sess):
        tok = pytest.token
        r = admin_sess.post(f"{BASE}/api/control-intelligence/auditor-link/revoke", timeout=30)
        assert r.status_code == 200
        r2 = admin_sess.get(f"{BASE}/api/control-intelligence/auditor-link", timeout=30)
        assert r2.json() == {"active": False}
        r3 = requests.get(f"{BASE}/api/control-intelligence/public/auditor-link/{tok}", timeout=30)
        assert r3.status_code == 404


# ---------- Signed PDF ----------
class TestSignedPdf:
    def test_generate_and_download(self, admin_sess):
        # Fresh link
        admin_sess.post(f"{BASE}/api/control-intelligence/auditor-link/revoke", timeout=30)
        r = admin_sess.post(f"{BASE}/api/control-intelligence/auditor-link", json={"days": 90}, timeout=30)
        tok = r.json()["token"]
        r2 = requests.get(f"{BASE}/api/control-intelligence/public/auditor-link/{tok}/brief.pdf",
                          params={"who": "Jane Auditor"}, timeout=60)
        assert r2.status_code == 200
        assert "application/pdf" in r2.headers.get("content-type", "")
        assert "attachment" in r2.headers.get("content-disposition", "").lower()
        assert r2.content[:4] == b"%PDF", f"Not a PDF header: {r2.content[:20]}"
        assert len(r2.content) > 5000

    def test_invalid_token_404(self):
        r = requests.get(f"{BASE}/api/control-intelligence/public/auditor-link/deadbeef/brief.pdf", timeout=30)
        assert r.status_code == 404


# ---------- Send-now recipient count ----------
class TestBriefRecipients:
    def test_recipients_shape(self, admin_sess):
        r = admin_sess.get(f"{BASE}/api/control-intelligence/brief/recipients", timeout=30)
        assert r.status_code == 200
        data = r.json()
        for k in ("board", "auditor", "total"):
            assert k in data and isinstance(data[k], int)
        assert data["total"] == data["board"] + data["auditor"]

    def test_recipients_update_after_settings(self, admin_sess):
        before = admin_sess.get(f"{BASE}/api/control-intelligence/brief/recipients").json()
        payload = {"recipients": [{"email": "TEST_auditor@example.com", "role": "auditor"}],
                   "send_day": 1, "enabled": False, "cadence": "monthly"}
        rs = admin_sess.put(f"{BASE}/api/control-intelligence/settings", json=payload, timeout=30)
        assert rs.status_code == 200
        after = admin_sess.get(f"{BASE}/api/control-intelligence/brief/recipients").json()
        assert after["auditor"] >= before["auditor"] + 1, f"before={before} after={after}"
        # reset
        admin_sess.put(f"{BASE}/api/control-intelligence/settings",
                       json={"recipients": [], "send_day": 1, "enabled": False, "cadence": "monthly"})
