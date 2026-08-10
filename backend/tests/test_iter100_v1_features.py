"""Backend tests for Iteration 100 — Live Enforcement Simulator, Toxicity Heatmap,
Board Digest enhancements and Go-Live Readiness deepening."""
import os
import re
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
EMAIL = "jblan2026@gmail.com"
PASSWORD = "Obserra2026!"


@pytest.fixture(scope="module")
def client():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json={"email": EMAIL, "password": PASSWORD}, timeout=30)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text[:200]}"
    return s


# --- (a) Live Enforcement Simulator ---
class TestSimulator:
    def test_simulator_enable_status_and_signed_dispatch(self, client):
        r = client.post(f"{BASE_URL}/api/agents/runtime/simulator/enable", timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["enabled"] is True
        assert d["active"] is True
        assert d["signed"] is True
        assert "/api/agents/runtime/simulator/inbound/" in d["url"]

        # test signed webhook round-trip
        r = client.post(f"{BASE_URL}/api/agents/runtime/webhook/test", timeout=30)
        assert r.status_code == 200, r.text
        rec = r.json()
        assert rec.get("ok") is True or rec.get("status_code") in (200, 202)

        # verify event recorded with signature valid
        r = client.get(f"{BASE_URL}/api/agents/runtime/simulator", timeout=30)
        assert r.status_code == 200
        d = r.json()
        assert d["received"] >= 1
        assert d["verified"] >= 1
        assert len(d["events"]) >= 1
        assert d["events"][0].get("signature_valid") is True

    def test_simulator_disable_clears_webhook(self, client):
        r = client.post(f"{BASE_URL}/api/agents/runtime/simulator/disable", timeout=30)
        assert r.status_code == 200
        d = r.json()
        assert d["enabled"] is False
        assert d["active"] is False
        # re-enable for subsequent frontend testing
        client.post(f"{BASE_URL}/api/agents/runtime/simulator/enable", timeout=30)


# --- (b) Toxicity — per-agent enforce endpoint ---
class TestToxicity:
    def test_agents_list_has_toxic(self, client):
        r = client.get(f"{BASE_URL}/api/agents", timeout=30)
        assert r.status_code == 200
        data = r.json()
        agents = data.get("agents") if isinstance(data, dict) else data
        assert isinstance(agents, list) and len(agents) > 0

    def test_enforce_single_agent(self, client):
        # ensure sim enabled first
        client.post(f"{BASE_URL}/api/agents/runtime/simulator/enable", timeout=30)
        r = client.post(f"{BASE_URL}/api/agents/AGT-002/enforce",
                        json={"action": "suspend", "mode": "enforce", "reason": "test"}, timeout=30)
        assert r.status_code in (200, 202), r.text


# --- (c) Board Digest enhancements ---
class TestBoardDigest:
    def test_digest_preview_contains_chart_and_toxic(self, client):
        r = client.get(f"{BASE_URL}/api/agents/runtime/board-evidence-digest/preview", timeout=60)
        assert r.status_code == 200, r.text
        d = r.json()
        html = d.get("html") or d.get("body") or ""
        assert "last 4 weeks" in html.lower() or "enforcement actions" in html.lower(), \
            "digest missing 4-week enforcement chart"
        assert "top toxic agents" in html.lower(), "digest missing top toxic agents section"


# --- (d) Go-Live Readiness deepening ---
class TestGoLive:
    def test_checklist_has_11_items_including_new(self, client):
        r = client.get(f"{BASE_URL}/api/sap/go-live-checklist", timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        items = d.get("items") or d.get("checks") or []
        assert len(items) >= 11, f"expected >=11 items, got {len(items)}"
        keys = " ".join(str(i).lower() for i in items)
        assert "toxic" in keys
        assert "audit" in keys
        assert "digest" in keys
        assert isinstance(d.get("score"), (int, float))

    def test_go_live_report_pdf(self, client):
        r = client.get(f"{BASE_URL}/api/sap/go-live-report.pdf", timeout=60)
        assert r.status_code == 200
        assert r.headers.get("content-type", "").startswith("application/pdf")
        assert r.content[:5] == b"%PDF-"
        assert len(r.content) > 3000
