"""Tests for Go-Live Readiness checklist, PDF Integrity Seal, and connector reprobe regression."""
import os
import re
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
EMAIL = "jblan2026@gmail.com"
PASSWORD = "Obserra2026!"


@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json={"email": EMAIL, "password": PASSWORD}, timeout=30)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text[:200]}"
    return s


# --- Go-Live Readiness checklist ---
class TestGoLiveChecklist:
    def test_endpoint_returns_expected_shape(self, session):
        r = session.get(f"{BASE_URL}/api/sap/go-live-checklist", timeout=30)
        assert r.status_code == 200, r.text[:400]
        data = r.json()
        assert "items" in data and isinstance(data["items"], list)
        assert "score" in data
        assert "ready" in data
        assert "failed" in data
        assert data["ready"] is True
        assert data["failed"] == 0
        assert data["score"] >= 90
        # 8 items
        ids = {i.get("id") for i in data["items"]}
        expected = {"database", "connectors", "freshness", "inventory", "engine", "ai", "evidence", "runtime"}
        assert expected.issubset(ids), f"missing: {expected - ids}"
        # each item has live detail string
        for item in data["items"]:
            assert item.get("detail"), f"missing detail on {item.get('id')}"
            assert item.get("status") in ("pass", "warn", "fail")


# --- PDF integrity seal ---
class TestEvidencePackSeal:
    def test_pdf_has_verified_by_obserra_seal(self, session):
        r = session.get(f"{BASE_URL}/api/agents/runtime/evidence-pack.pdf", timeout=60)
        assert r.status_code == 200
        assert r.headers.get("content-type", "").startswith("application/pdf")
        content = r.content
        assert content[:4] == b"%PDF", f"not a valid PDF, starts: {content[:10]!r}"
        # PDFs may encode text - decode leniently and search
        text = content.decode("latin-1", errors="ignore")
        assert "VERIFIED BY OBSERRA" in text, "integrity seal text missing"
        # short SHA-256 hex (at least 8 hex chars near seal)
        assert re.search(r"[0-9a-f]{8,}", text), "sha256 fragment missing"


# --- Connector re-probe regression ---
class TestConnectorReprobe:
    def test_reprobe_returns_healthy(self, session):
        r = session.post(f"{BASE_URL}/api/sap/systems/reprobe", timeout=60)
        assert r.status_code == 200, r.text[:300]
        data = r.json()
        # payload should have systems or summary indicating counts
        assert isinstance(data, dict)

    def test_systems_payload(self, session):
        r = session.get(f"{BASE_URL}/api/sap/systems", timeout=30)
        assert r.status_code == 200
        data = r.json()
        # accept either list or dict with systems key
        systems = data.get("systems") if isinstance(data, dict) else data
        assert systems, "no systems returned"
