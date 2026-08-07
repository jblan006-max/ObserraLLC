"""Iter23 P0 features tests: control/vendor notes+history, email-docs-all."""
import os
import time
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://cyber-dashboard-48.preview.emergentagent.com").rstrip("/")
ADMIN = {"email": "jblan2026@gmail.com", "password": "Obserra2026!"}


@pytest.fixture(scope="module")
def admin_client():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    r = s.post(f"{BASE_URL}/api/auth/login", json=ADMIN)
    assert r.status_code == 200, f"admin login failed: {r.status_code} {r.text}"
    return s


# ---------- Control notes + history ----------
class TestControlNotes:
    def test_get_history_ok(self, admin_client):
        # fetch first control id
        r = admin_client.get(f"{BASE_URL}/api/controls")
        assert r.status_code == 200
        controls = r.json()
        assert isinstance(controls, list) and len(controls) > 0
        cid = controls[0]["control_id"]
        h = admin_client.get(f"{BASE_URL}/api/controls/{cid}/history")
        assert h.status_code == 200
        assert isinstance(h.json(), list)

    def test_post_note_and_verify_persistence(self, admin_client):
        r = admin_client.get(f"{BASE_URL}/api/controls")
        cid = r.json()[0]["control_id"]
        text = f"TEST_iter23 remediation {int(time.time())}"
        p = admin_client.post(f"{BASE_URL}/api/controls/{cid}/notes",
                              json={"kind": "remediation", "text": text})
        assert p.status_code == 200, p.text
        doc = p.json()
        assert doc["text"] == text
        assert doc["kind"] == "remediation"
        assert doc.get("control_id") == cid
        assert "_id" not in doc
        # verify persisted at top of history
        h = admin_client.get(f"{BASE_URL}/api/controls/{cid}/history")
        items = h.json()
        assert any(it["text"] == text for it in items[:5])

    def test_post_note_empty_400(self, admin_client):
        r = admin_client.get(f"{BASE_URL}/api/controls")
        cid = r.json()[0]["control_id"]
        p = admin_client.post(f"{BASE_URL}/api/controls/{cid}/notes",
                              json={"kind": "note", "text": "   "})
        assert p.status_code == 400

    def test_post_note_invalid_kind_defaults(self, admin_client):
        r = admin_client.get(f"{BASE_URL}/api/controls")
        cid = r.json()[0]["control_id"]
        p = admin_client.post(f"{BASE_URL}/api/controls/{cid}/notes",
                              json={"kind": "bogus", "text": "TEST_iter23 kind fallback"})
        assert p.status_code == 200
        assert p.json()["kind"] == "note"


# ---------- Vendor notes + history ----------
class TestVendorNotes:
    def test_get_vendor_history_and_add(self, admin_client):
        r = admin_client.get(f"{BASE_URL}/api/vendors")
        assert r.status_code == 200
        vendors = r.json().get("vendors", [])
        assert len(vendors) > 0
        ref = vendors[0]["ref"]
        h = admin_client.get(f"{BASE_URL}/api/vendors/{ref}/history")
        assert h.status_code == 200
        assert isinstance(h.json(), list)
        text = f"TEST_iter23 vendor evidence {int(time.time())}"
        p = admin_client.post(f"{BASE_URL}/api/vendors/{ref}/notes",
                              json={"kind": "evidence", "text": text})
        assert p.status_code == 200, p.text
        doc = p.json()
        assert doc["text"] == text
        assert doc["kind"] == "evidence"
        assert "_id" not in doc
        h2 = admin_client.get(f"{BASE_URL}/api/vendors/{ref}/history")
        assert any(it["text"] == text for it in h2.json()[:5])

    def test_vendor_note_empty_400(self, admin_client):
        r = admin_client.get(f"{BASE_URL}/api/vendors")
        ref = r.json()["vendors"][0]["ref"]
        p = admin_client.post(f"{BASE_URL}/api/vendors/{ref}/notes",
                              json={"kind": "note", "text": ""})
        assert p.status_code == 400


# ---------- Email docs all ----------
class TestEmailDocsAll:
    def test_email_all_no_recipients_400(self, admin_client):
        # Clear recipients book first
        admin_client.put(f"{BASE_URL}/api/deploy/recipients", json={"recipients": []})
        r = admin_client.post(f"{BASE_URL}/api/deploy/email-docs-all")
        assert r.status_code == 400

    def test_email_all_success_after_save(self, admin_client):
        admin_client.put(f"{BASE_URL}/api/deploy/recipients",
                         json={"recipients": ["test-iter23@obserra.demo"]})
        r = admin_client.post(f"{BASE_URL}/api/deploy/email-docs-all")
        assert r.status_code == 200, r.text
        data = r.json()
        assert data.get("status") == "sent"
        assert "count" in data
        # cleanup
        admin_client.put(f"{BASE_URL}/api/deploy/recipients", json={"recipients": []})
