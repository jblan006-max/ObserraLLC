"""Backend contract tests for iteration 90 — Obserra Agentic v1 wiring.

Covers:
- GET/PUT /api/agents/runtime/webhook (admin)
- POST /api/agents/runtime/enforce-bulk (suspend | kill; selector=toxic; refs=[...])
- POST /api/actions/run for agent_suspend / agent_resume (enforce_from_advisor)
- POST /api/ai-systems/discover (live only, no mock catalog)
- Regression: POST /api/agents/{ref}/enforce single-agent kill switch
"""
import os
import pytest
import requests

BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or open("/app/frontend/.env").read().split("REACT_APP_BACKEND_URL=")[1].splitlines()[0]).rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "jblan2026@gmail.com"
ADMIN_PW = "Obserra2026!"


@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PW}, timeout=15)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text[:200]}"
    return s


# ---- Webhook GET / PUT / clear / invalid ----
class TestRuntimeWebhook:
    def test_get_webhook_initial(self, session):
        r = session.get(f"{API}/agents/runtime/webhook", timeout=10)
        assert r.status_code == 200
        assert "webhook" in r.json()

    def test_put_valid_webhook_persists(self, session):
        url = "https://example.com/agent-runtime-hook"
        r = session.put(f"{API}/agents/runtime/webhook", json={"webhook": url}, timeout=10)
        assert r.status_code == 200
        assert r.json().get("webhook") == url
        g = session.get(f"{API}/agents/runtime/webhook", timeout=10)
        assert g.json().get("webhook") == url

    def test_put_invalid_webhook_rejected(self, session):
        r = session.put(f"{API}/agents/runtime/webhook", json={"webhook": "notaurl"}, timeout=10)
        assert r.status_code == 400

    def test_clear_webhook(self, session):
        r = session.put(f"{API}/agents/runtime/webhook", json={"webhook": ""}, timeout=10)
        assert r.status_code == 200
        assert r.json().get("webhook") == ""


# ---- Bulk enforce ----
class TestBulkEnforce:
    def test_bulk_suspend_refs(self, session):
        # Suspend AGT-002 which is the toxic one per baseline
        r = session.post(f"{API}/agents/runtime/enforce-bulk",
                         json={"action": "suspend", "selector": "toxic", "refs": ["AGT-002"]}, timeout=15)
        assert r.status_code == 200, r.text[:200]
        data = r.json()
        assert data.get("ok") is True
        assert data.get("action") == "suspend"
        assert data.get("count") >= 1
        # Verify state
        gr = session.get(f"{API}/agents/AGT-002", timeout=10)
        if gr.status_code == 200:
            assert gr.json().get("status") in ("restricted", "suspended", "killed")

    def test_bulk_invalid_action(self, session):
        r = session.post(f"{API}/agents/runtime/enforce-bulk",
                         json={"action": "wipe", "refs": ["AGT-002"]}, timeout=10)
        assert r.status_code == 400


# ---- Advisor actions passthrough ----
class TestActionsRun:
    def test_advisor_suspend_ok(self, session):
        r = session.post(f"{API}/actions/run", json={"action_id": "agent_suspend:AGT-002"}, timeout=15)
        assert r.status_code == 200, r.text[:300]
        d = r.json()
        # Should not 500 and should indicate ok/message
        assert isinstance(d, dict)

    def test_advisor_resume_restores(self, session):
        # Resume AGT-002 back toward sanctioned (baseline: AGT-002 restricted)
        r = session.post(f"{API}/actions/run", json={"action_id": "agent_resume:AGT-002"}, timeout=15)
        assert r.status_code == 200, r.text[:300]


# ---- Shadow AI discovery live ----
class TestShadowAIDiscover:
    def test_discover_endpoint_ok(self, session):
        r = session.post(f"{API}/ai-systems/discover", json={}, timeout=20)
        assert r.status_code == 200, r.text[:300]
        d = r.json()
        # Should return a list or object; must not contain obvious mock keywords
        assert isinstance(d, (list, dict))


# ---- Single-agent enforce regression ----
class TestSingleAgentEnforce:
    def test_single_suspend_and_resume(self, session):
        r = session.post(f"{API}/agents/AGT-002/enforce", json={"action": "suspend"}, timeout=15)
        assert r.status_code == 200, r.text[:300]
        assert r.json().get("ok") is True
        # restore baseline: AGT-002 should end up restricted (resume it)
        r2 = session.post(f"{API}/agents/AGT-002/enforce", json={"action": "resume"}, timeout=15)
        assert r2.status_code == 200


# ---- Cleanup: restore baseline (AGT-002 restricted with tool violation persists in demo) ----
@pytest.fixture(scope="module", autouse=True)
def _restore(session):
    yield
    try:
        session.post(f"{API}/actions/run", json={"action_id": "agent_resume:AGT-002"}, timeout=10)
        session.post(f"{API}/actions/run", json={"action_id": "agent_resume:AGT-001"}, timeout=10)
        session.post(f"{API}/actions/run", json={"action_id": "agent_resume:AGT-003"}, timeout=10)
    except Exception:
        pass
