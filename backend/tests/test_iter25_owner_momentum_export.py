"""Iteration 25 tests: Owner Directory, Momentum Trend, Log Export PDFs, owner nudge routing."""
import os
import time
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://cyber-dashboard-48.preview.emergentagent.com").rstrip("/")
ADMIN_EMAIL = "jblan2026@gmail.com"
ADMIN_PASSWORD = "Obserra2026!"


@pytest.fixture(scope="module")
def admin_session():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text[:300]}"
    return s


@pytest.fixture(scope="module")
def admin_headers(admin_session):
    # Backwards-compat shim: return the session, tests use it like a requester (session.get/post accepts headers arg)
    return admin_session


# ---------- Owner Directory ----------
class TestOwnerDirectory:
    def test_get_owners_includes_grc_team(self, admin_headers):
        r = admin_headers.get(f"{BASE_URL}/api/owners")
        assert r.status_code == 200
        data = r.json()
        assert "owners" in data and isinstance(data["owners"], list)
        names = [o["name"] for o in data["owners"]]
        assert len(names) > 0, "expected at least one distinct owner from controls+vendors"
        # each entry must have name+email fields
        for o in data["owners"]:
            assert "name" in o and "email" in o

    def test_put_owners_saves_and_persists(self, admin_headers):
        # capture existing directory
        cur = admin_headers.get(f"{BASE_URL}/api/owners").json()["owners"]
        assert cur, "no owners"
        first = cur[0]["name"]
        directory = {o["name"]: o["email"] for o in cur if o["email"]}
        directory[first] = "TEST_owner@example.com"
        r = admin_headers.put(f"{BASE_URL}/api/owners", json={"directory": directory})
        assert r.status_code == 200, r.text
        assert r.json().get("ok") is True
        # verify persistence
        after = admin_headers.get(f"{BASE_URL}/api/owners").json()["owners"]
        emails = {o["name"].lower(): o["email"] for o in after}
        assert emails.get(first.lower()) == "TEST_owner@example.com"

    def test_put_owners_invalid_email_returns_400(self, admin_headers):
        r = admin_headers.put(f"{BASE_URL}/api/owners",
                         json={"directory": {"Nobody": "not-an-email"}})
        assert r.status_code == 400, f"expected 400 got {r.status_code}: {r.text}"


# ---------- Momentum Trend ----------
class TestMomentumTrend:
    def test_activity_returns_trend_with_8_points(self, admin_headers):
        r = admin_headers.get(f"{BASE_URL}/api/remediation/activity")
        assert r.status_code == 200
        data = r.json()
        assert "trend" in data, f"trend missing from response: {list(data.keys())}"
        assert isinstance(data["trend"], list)
        assert len(data["trend"]) == 8, f"expected 8 weekly points, got {len(data['trend'])}"
        for pt in data["trend"]:
            assert "week" in pt and "score" in pt
            assert isinstance(pt["score"], (int, float))
            assert 0 <= pt["score"] <= 100


# ---------- Log Export PDFs ----------
class TestLogExport:
    def test_control_log_pdf(self, admin_headers):
        # ensure at least one note
        admin_headers.post(f"{BASE_URL}/api/controls/IAM-3/notes",
                      json={"kind": "note", "text": "TEST_iter25 export sanity"})
        r = admin_headers.get(f"{BASE_URL}/api/reports/control-log/IAM-3.pdf")
        assert r.status_code == 200, r.text[:300]
        assert r.headers.get("content-type", "").startswith("application/pdf")
        assert r.content[:4] == b"%PDF", "response is not a PDF"
        assert len(r.content) > 1000

    def test_vendor_log_pdf(self, admin_headers):
        admin_headers.post(f"{BASE_URL}/api/vendors/VND-002/notes",
                      json={"kind": "note", "text": "TEST_iter25 vendor export"})
        r = admin_headers.get(f"{BASE_URL}/api/reports/vendor-log/VND-002.pdf")
        assert r.status_code == 200, r.text[:300]
        assert r.headers.get("content-type", "").startswith("application/pdf")
        assert r.content[:4] == b"%PDF"
        assert len(r.content) > 1000

    def test_control_log_export_requires_auth(self):
        # unauthenticated -> should be 401/403
        r = requests.get(f"{BASE_URL}/api/reports/control-log/IAM-3.pdf")
        assert r.status_code in (401, 403), f"unauth should be blocked, got {r.status_code}"

    def test_vendor_log_export_requires_auth(self):
        r = requests.get(f"{BASE_URL}/api/reports/vendor-log/VND-002.pdf")
        assert r.status_code in (401, 403), f"unauth should be blocked, got {r.status_code}"


# ---------- Owner nudge routing ----------
class TestOwnerNudge:
    def test_remediation_note_creates_notification(self, admin_headers):
        # ensure directory has an email for control owner (to hit directory branch)
        owners = admin_headers.get(f"{BASE_URL}/api/owners").json()["owners"]
        directory = {o["name"]: o["email"] or "TEST_owner@example.com" for o in owners}
        admin_headers.put(f"{BASE_URL}/api/owners", json={"directory": directory})

        # snapshot notifications
        pre = admin_headers.get(f"{BASE_URL}/api/notifications").json()
        pre_ids = {n.get("id") or n.get("_id") or n.get("ts") for n in pre.get("items", [])}

        r = admin_headers.post(f"{BASE_URL}/api/controls/IAM-3/notes",
                          json={"kind": "remediation", "text": "TEST_iter25 nudge routing"})
        assert r.status_code == 200, r.text
        time.sleep(1)

        post = admin_headers.get(f"{BASE_URL}/api/notifications").json()
        new = [n for n in post.get("items", []) if (n.get("id") or n.get("_id") or n.get("ts")) not in pre_ids]
        titles = " | ".join((n.get("title") or n.get("message") or "") for n in new)
        assert any("Remediation logged" in (n.get("title") or n.get("message") or "") for n in new), \
            f"expected 'Remediation logged' notification, got: {titles}"
