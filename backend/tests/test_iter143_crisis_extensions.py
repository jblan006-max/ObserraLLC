"""Iteration 143 — Crisis Commander Extensions:
Native SIEM Connectors, War Room Broadcast, Board Dashboard, Present to Board.
"""
import os
import json
import time
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    # Fallback to reading frontend/.env
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                BASE_URL = line.split("=", 1)[1].strip().rstrip("/")

ADMIN_EMAIL = "jblan2026@gmail.com"
ADMIN_PASSWORD = "Obserra2026!"


@pytest.fixture(scope="module")
def sess():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login",
               json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
               timeout=15)
    assert r.status_code == 200, f"Login failed: {r.status_code} {r.text[:200]}"
    return s


@pytest.fixture(scope="module")
def case_ref(sess):
    # Get a current case (should be CRISIS-0002 or similar real case)
    r = sess.get(f"{BASE_URL}/api/crisis/cases", timeout=15)
    assert r.status_code == 200
    data = r.json()
    cases = data if isinstance(data, list) else (data.get("cases") or data.get("items") or [])
    assert cases, f"No cases available: {str(data)[:200]}"
    ref = cases[0].get("ref") or cases[0].get("case_ref") or cases[0].get("id")
    assert ref
    return ref


# ---------- FEATURE 1: Native SIEM Connectors ----------
class TestNativeConnectors:
    def test_native_connectors_list(self, sess):
        r = sess.get(f"{BASE_URL}/api/crisis/connectors/native", timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "secret" in data and isinstance(data["secret"], str) and len(data["secret"]) > 5
        assert "connectors" in data and isinstance(data["connectors"], list)
        assert len(data["connectors"]) == 5
        vendors = {c.get("vendor") or c.get("id") or c.get("key") for c in data["connectors"]}
        expected = {"crowdstrike", "splunk", "sentinel", "servicenow", "generic"}
        assert expected.issubset({v.lower() for v in vendors if v}), f"Vendors: {vendors}"
        # Each has push URL embedding the secret
        for c in data["connectors"]:
            url = c.get("url") or c.get("push_url") or c.get("path") or ""
            assert "secret=" in url, f"URL missing secret: {c}"

    def test_ingest_native_crowdstrike_ok(self, sess):
        r = sess.get(f"{BASE_URL}/api/crisis/connectors/native", timeout=15)
        secret = r.json()["secret"]
        payload = {
            "detection_name": "TEST_ITER143 Malware Detected",
            "SeverityName": "Critical",
            "description": "Iter143 test native ingest — please ignore",
            "ComputerName": "TEST-HOST-01",
        }
        r2 = requests.post(
            f"{BASE_URL}/api/crisis/ingest/native/crowdstrike?secret={secret}",
            json=payload, timeout=15,
        )
        assert r2.status_code == 200, r2.text
        out = r2.json()
        assert out.get("ok") is True
        assert out.get("ingested", 0) >= 1

    def test_ingest_native_missing_secret_401(self):
        r = requests.post(
            f"{BASE_URL}/api/crisis/ingest/native/crowdstrike",
            json={"detection_name": "x", "SeverityName": "Low"},
            timeout=15,
        )
        assert r.status_code == 401, f"Expected 401, got {r.status_code}: {r.text[:200]}"

    def test_ingest_native_bad_secret_401(self):
        r = requests.post(
            f"{BASE_URL}/api/crisis/ingest/native/crowdstrike?secret=BOGUS",
            json={"detection_name": "x", "SeverityName": "Low"},
            timeout=15,
        )
        assert r.status_code == 401

    def test_ingest_native_empty_body_400(self, sess):
        secret = sess.get(f"{BASE_URL}/api/crisis/connectors/native").json()["secret"]
        r = requests.post(
            f"{BASE_URL}/api/crisis/ingest/native/crowdstrike?secret={secret}",
            data="", headers={"Content-Type": "application/json"}, timeout=15,
        )
        assert r.status_code in (400, 422), f"Got {r.status_code}: {r.text[:200]}"

    def test_ingest_native_header_secret(self, sess):
        secret = sess.get(f"{BASE_URL}/api/crisis/connectors/native").json()["secret"]
        r = requests.post(
            f"{BASE_URL}/api/crisis/ingest/native/splunk",
            json={"search_name": "TEST_ITER143 splunk alert", "severity": "high",
                  "result": {"message": "test"}},
            headers={"X-Obserra-Secret": secret},
            timeout=15,
        )
        assert r.status_code == 200, r.text
        assert r.json().get("ok") is True


# ---------- FEATURE 2: War Room Broadcast ----------
class TestBroadcast:
    def test_broadcast_status(self, sess):
        r = sess.get(f"{BASE_URL}/api/crisis/broadcast/status", timeout=15)
        assert r.status_code == 200, r.text
        d = r.json()
        assert "teams" in d and "slack" in d
        assert isinstance(d["teams"], bool)
        assert isinstance(d["slack"], bool)

    # NOTE: Skipping actual broadcast since Teams+Slack are live.
    # Frontend test will do a single labelled broadcast.


# ---------- FEATURE 3: Board Dashboard ----------
class TestBoardView:
    def test_board_view(self, sess, case_ref):
        r = sess.get(f"{BASE_URL}/api/crisis/cases/{case_ref}/board", timeout=15)
        assert r.status_code == 200, r.text
        d = r.json()
        # Should include snapshot-shape plus recovery
        # Common keys: severity, contained, decisions_pending, exposure, regulatory
        assert isinstance(d, dict) and len(d) > 3, f"Board payload thin: {d}"
        # recovery_overall or recovery_items should exist
        assert "recovery_overall" in d or "recovery_items" in d or "recovery" in d, f"No recovery keys: {list(d.keys())}"


# ---------- FEATURE 4: Present to Board ----------
class TestPresentToBoard:
    def test_present_board_and_pdf(self, sess, case_ref):
        r = sess.post(f"{BASE_URL}/api/crisis/cases/{case_ref}/present-board", json={}, timeout=20)
        assert r.status_code == 200, r.text
        d = r.json()
        assert "snapshot_path" in d or "snapshot_url" in d or "snapshot" in d, f"No snapshot ref: {d}"

        # Fetch one-page PDF
        r2 = sess.get(f"{BASE_URL}/api/crisis/cases/{case_ref}/board-onepager.pdf", timeout=30)
        assert r2.status_code == 200, r2.text[:200]
        assert r2.content.startswith(b"%PDF"), f"Not a PDF: {r2.content[:20]}"
        assert len(r2.content) > 20_000, f"PDF too small: {len(r2.content)}"

    def test_cleanup_revoke_snapshot(self, sess, case_ref):
        # Best-effort cleanup — revoke snapshot created in previous test
        try:
            sess.post(f"{BASE_URL}/api/crisis/cases/{case_ref}/snapshot/revoke", json={}, timeout=10)
        except Exception:
            pass
