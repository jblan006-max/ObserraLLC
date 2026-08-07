"""Iteration 24 - Log filtering, owner notifications, exec remediation momentum."""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://cyber-dashboard-48.preview.emergentagent.com").rstrip("/")
ADMIN_EMAIL = "jblan2026@gmail.com"
ADMIN_PASSWORD = "Obserra2026!"


@pytest.fixture(scope="module")
def client():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    return s


def _pick_control_id(client):
    r = client.get(f"{BASE_URL}/api/controls")
    assert r.status_code == 200
    ctrls = r.json()
    # prefer IAM-3
    for c in ctrls:
        if c.get("control_id") == "IAM-3":
            return "IAM-3"
    return ctrls[0]["control_id"]


def _pick_vendor_ref(client):
    r = client.get(f"{BASE_URL}/api/vendors")
    assert r.status_code == 200
    data = r.json()
    vs = data["vendors"] if isinstance(data, dict) else data
    for v in vs:
        if v.get("ref") == "VND-002":
            return "VND-002"
    return vs[0]["ref"]


def _notifs(client):
    r = client.get(f"{BASE_URL}/api/notifications").json()
    return r["items"] if isinstance(r, dict) else r


class TestControlNotesAndNotifications:
    def test_add_remediation_note_creates_notification(self, client):
        cid = _pick_control_id(client)
        # baseline count
        before = _notifs(client)
        before_ct = len([n for n in before if n.get("ref") == cid and "Remediation logged" in n.get("title", "")])

        payload = {"kind": "remediation", "text": f"TEST_ iter24 remediation on {cid}"}
        r = client.post(f"{BASE_URL}/api/controls/{cid}/notes", json=payload)
        assert r.status_code == 200, r.text
        doc = r.json()
        assert doc["kind"] == "remediation"
        assert doc["text"].startswith("TEST_")
        assert "_id" not in doc

        # verify persistence via history endpoint
        hist = client.get(f"{BASE_URL}/api/controls/{cid}/history").json()
        assert any(h["text"] == payload["text"] for h in hist)

        # notification created
        after = _notifs(client)
        after_ct = len([n for n in after if n.get("ref") == cid and "Remediation logged" in n.get("title", "")])
        assert after_ct >= before_ct + 1, f"expected new notification for {cid}"

    def test_evidence_note_does_not_create_notification(self, client):
        cid = _pick_control_id(client)
        before = _notifs(client)
        before_ct = len([n for n in before if "Remediation logged" in n.get("title", "")])
        r = client.post(f"{BASE_URL}/api/controls/{cid}/notes",
                        json={"kind": "evidence", "text": "TEST_ iter24 evidence entry"})
        assert r.status_code == 200
        after = _notifs(client)
        after_ct = len([n for n in after if "Remediation logged" in n.get("title", "")])
        assert after_ct == before_ct, "evidence note should NOT create a remediation notification"

    def test_plain_note_no_notification(self, client):
        cid = _pick_control_id(client)
        r = client.post(f"{BASE_URL}/api/controls/{cid}/notes",
                        json={"kind": "note", "text": "TEST_ iter24 plain note"})
        assert r.status_code == 200
        assert r.json()["kind"] == "note"


class TestVendorNotesAndNotifications:
    def test_vendor_remediation_creates_notification(self, client):
        ref = _pick_vendor_ref(client)
        before = _notifs(client)
        before_ct = len([n for n in before if n.get("ref") == ref and "Remediation logged" in n.get("title", "")])
        r = client.post(f"{BASE_URL}/api/vendors/{ref}/notes",
                        json={"kind": "remediation", "text": f"TEST_ iter24 vendor remediation on {ref}"})
        assert r.status_code == 200, r.text
        after = _notifs(client)
        after_ct = len([n for n in after if n.get("ref") == ref and "Remediation logged" in n.get("title", "")])
        assert after_ct >= before_ct + 1


class TestRemediationActivity:
    def test_activity_shape_and_score(self, client):
        r = client.get(f"{BASE_URL}/api/remediation/activity")
        assert r.status_code == 200, r.text
        d = r.json()
        for k in ("score", "remediation_count", "evidence_count", "applied_recommendations", "activity", "window_days"):
            assert k in d, f"missing key {k}"
        assert 0 <= d["score"] <= 100
        assert isinstance(d["activity"], list)
        assert len(d["activity"]) <= 8
        # We added at least one remediation and one evidence entry in previous tests
        assert d["remediation_count"] >= 1
        assert d["evidence_count"] >= 1

    def test_activity_increases_on_new_remediation(self, client):
        cid = _pick_control_id(client)
        before = client.get(f"{BASE_URL}/api/remediation/activity").json()
        r = client.post(f"{BASE_URL}/api/controls/{cid}/notes",
                        json={"kind": "remediation", "text": "TEST_ iter24 extra remediation for score bump"})
        assert r.status_code == 200
        after = client.get(f"{BASE_URL}/api/remediation/activity").json()
        assert after["remediation_count"] >= before["remediation_count"] + 1
        assert after["score"] >= before["score"]
