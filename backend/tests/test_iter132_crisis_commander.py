"""Iteration 132 - Cyber Crisis Commander backend tests.

Covers: demo mode (seed/clear/status), war-room participants CRUD,
recovery items CRUD + advance, regulatory obligations, case status update,
and PIR PDF generation via /api/studio/report/pdf with an em-dash in title.
"""
import os
from datetime import datetime, timedelta, timezone

import pytest
import requests

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
ADMIN_EMAIL = "jblan2026@gmail.com"
ADMIN_PASSWORD = "Obserra2026!"


@pytest.fixture(scope="module")
def client():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login",
               json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=30)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text[:400]}"
    return s


# ---------------- Demo Mode ----------------
class TestDemoMode:
    def test_demo_clear_then_status_inactive(self, client):
        # Ensure clean baseline
        r = client.post(f"{BASE_URL}/api/crisis/demo/clear", timeout=30)
        assert r.status_code == 200
        assert r.json().get("cleared") is True

        r = client.get(f"{BASE_URL}/api/crisis/demo/status", timeout=30)
        assert r.status_code == 200
        assert r.json().get("active") is False

    def test_demo_seed_creates_case_and_status_active(self, client):
        r = client.post(f"{BASE_URL}/api/crisis/demo/seed", timeout=60)
        assert r.status_code == 200, r.text[:400]
        data = r.json()
        assert data.get("seeded") is True
        assert data.get("ref", "").startswith("CRISIS-")
        assert data["events"] >= 5 and data["actions"] >= 5
        assert data["participants"] >= 5 and data["recovery"] >= 5
        assert data["obligations"] >= 3

        # GET case detail verifies persistence
        ref = data["ref"]
        r = client.get(f"{BASE_URL}/api/crisis/cases/{ref}", timeout=30)
        assert r.status_code == 200
        j = r.json()
        assert j["case"]["ref"] == ref
        assert j["case"].get("demo") is True
        assert len(j["participants"]) >= 5
        assert len(j["recovery"]) >= 5
        assert len(j["obligations"]) >= 3

        r = client.get(f"{BASE_URL}/api/crisis/demo/status", timeout=30)
        assert r.json()["active"] is True

    def test_demo_clear_removes_case(self, client):
        r = client.post(f"{BASE_URL}/api/crisis/demo/clear", timeout=30)
        assert r.status_code == 200
        cleared = r.json()
        assert cleared["cases"] >= 1
        r = client.get(f"{BASE_URL}/api/crisis/demo/status", timeout=30)
        assert r.json()["active"] is False


# ---------------- Helper to get a persistent test case ----------------
@pytest.fixture(scope="module")
def test_case_ref(client):
    r = client.post(f"{BASE_URL}/api/crisis/cases",
                    json={"title": "TEST_ Iter132 case",
                          "severity": "High",
                          "summary": "TEST case for iteration 132"}, timeout=30)
    assert r.status_code == 200, r.text[:400]
    return r.json()["ref"]


# ---------------- War Room participants ----------------
class TestWarRoom:
    def test_add_and_remove_participant(self, client, test_case_ref):
        ref = test_case_ref
        r = client.post(f"{BASE_URL}/api/crisis/cases/{ref}/participants",
                        json={"role": "TEST_ Legal Counsel", "name": "Jane Doe",
                              "responsibility": "Regulatory", "status": "Engaged"},
                        timeout=30)
        assert r.status_code == 200, r.text[:400]
        p = r.json()
        assert p["role"] == "TEST_ Legal Counsel"
        assert p["participant_id"].startswith("WAR-")
        pid = p["participant_id"]

        # Verify persistence via GET
        r = client.get(f"{BASE_URL}/api/crisis/cases/{ref}", timeout=30)
        assert any(x["participant_id"] == pid for x in r.json()["participants"])

        # Remove
        r = client.delete(f"{BASE_URL}/api/crisis/cases/{ref}/participants/{pid}", timeout=30)
        assert r.status_code == 200
        assert r.json().get("ok") is True

        r = client.get(f"{BASE_URL}/api/crisis/cases/{ref}", timeout=30)
        assert all(x["participant_id"] != pid for x in r.json()["participants"])


# ---------------- Recovery ----------------
class TestRecovery:
    def test_recovery_add_and_advance_flow(self, client, test_case_ref):
        ref = test_case_ref
        r = client.post(f"{BASE_URL}/api/crisis/cases/{ref}/recovery",
                        json={"name": "TEST_ Order Mgmt", "category": "System",
                              "status": "Down"}, timeout=30)
        assert r.status_code == 200, r.text[:400]
        item = r.json()
        assert item["status"] == "Down"
        assert item["pct"] == 0
        rid = item["recovery_id"]

        # Advance Down -> Restoring
        r = client.patch(f"{BASE_URL}/api/crisis/cases/{ref}/recovery/{rid}",
                         json={"status": "Restoring"}, timeout=30)
        assert r.status_code == 200
        assert r.json()["pct"] == 50

        # Restoring -> Validated
        r = client.patch(f"{BASE_URL}/api/crisis/cases/{ref}/recovery/{rid}",
                         json={"status": "Validated"}, timeout=30)
        assert r.json()["pct"] == 80

        # Validated -> Operational
        r = client.patch(f"{BASE_URL}/api/crisis/cases/{ref}/recovery/{rid}",
                         json={"status": "Operational"}, timeout=30)
        assert r.json()["pct"] == 100
        assert r.json()["status"] == "Operational"


# ---------------- Regulatory obligations ----------------
class TestRegulatory:
    def test_add_obligation_with_deadline(self, client, test_case_ref):
        ref = test_case_ref
        deadline = (datetime.now(timezone.utc) + timedelta(hours=72)).isoformat()
        r = client.post(f"{BASE_URL}/api/crisis/cases/{ref}/obligations",
                        json={"jurisdiction": "TEST_ EU",
                              "regulation": "GDPR Art. 33",
                              "trigger": "PII exposure",
                              "deadline_at": deadline,
                              "responsible": "GC",
                              "status": "Assessing"}, timeout=30)
        assert r.status_code == 200, r.text[:400]
        ob = r.json()
        assert ob["obligation_id"].startswith("REG-")
        assert ob["deadline_at"] == deadline


# ---------------- PIR PDF (em-dash bug regression) ----------------
class TestPIRPDF:
    def test_pir_pdf_with_em_dash_returns_200(self, client, test_case_ref):
        # Close the case first (matches the frontend gating condition)
        r = client.patch(f"{BASE_URL}/api/crisis/cases/{test_case_ref}",
                         json={"status": "Closed"}, timeout=30)
        assert r.status_code == 200
        assert r.json()["status"] == "Closed"

        # Now generate a PIR PDF using an em-dash in the title
        payload = {
            "title": "Post-Incident Review — TEST_ Iter132",
            "blocks": [
                {"heading": "Overview",
                 "lines": ["Case ref: " + test_case_ref, "Severity: High"]},
                {"heading": "Recovery",
                 "lines": ["Order Mgmt restored"]},
            ],
        }
        r = client.post(f"{BASE_URL}/api/studio/report/pdf", json=payload, timeout=60)
        assert r.status_code == 200, f"{r.status_code} {r.text[:400]}"
        ct = r.headers.get("content-type", "").lower()
        assert "pdf" in ct, f"unexpected content-type: {ct}"
        # PDF magic bytes
        assert r.content[:4] == b"%PDF", "response is not a PDF"
        # Content-Disposition should be latin-1 safe (no em-dash)
        cd = r.headers.get("content-disposition", "")
        try:
            cd.encode("latin-1")
        except UnicodeEncodeError:
            pytest.fail(f"Content-Disposition not latin-1 safe: {cd!r}")
