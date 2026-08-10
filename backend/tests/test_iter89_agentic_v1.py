"""Backend tests for Obserra Agentic AI Security Control Plane v1 (iter 89).

Covers:
- POST /api/agents/{ref}/enforce (suspend / kill / resume, admin gate)
- POST /api/ai-systems/discover (idempotent shadow discovery)
- GET/PUT /api/agents/board-brief/schedule
- POST /api/agents/board-brief/send (called once — real email)
- POST /api/advisor/chat (grounded response, still healthy)
"""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"
ADMIN_EMAIL = "jblan2026@gmail.com"
ADMIN_PASSWORD = "Obserra2026!"


@pytest.fixture(scope="module")
def admin_session():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=30)
    assert r.status_code == 200, f"Login failed: {r.status_code} {r.text}"
    return s


@pytest.fixture(scope="module")
def any_agent_ref(admin_session):
    r = admin_session.get(f"{API}/agents", timeout=30)
    assert r.status_code == 200, r.text
    data = r.json()
    agents = data.get("agents") or data.get("items") or (data if isinstance(data, list) else [])
    assert agents, "No agents seeded — cannot test enforce"
    ref = agents[0].get("ref") or agents[0].get("id") or agents[0].get("agent_id")
    assert ref, f"Agent record missing ref: {agents[0]}"
    return ref


# ------------ Enforcement (Kill Switch) ------------

class TestEnforce:
    def test_suspend_sets_restricted(self, admin_session, any_agent_ref):
        r = admin_session.post(f"{API}/agents/{any_agent_ref}/enforce",
                               json={"action": "suspend"}, timeout=30)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body.get("ok") is True
        assert body["agent"]["status"] == "restricted"
        assert body["agent"].get("enforced") is True
        enf = body["enforcement"]
        assert enf["action"] == "suspend"
        assert "mode" in enf and "runtime" in enf and "note" in enf

    def test_kill_sets_killed(self, admin_session, any_agent_ref):
        r = admin_session.post(f"{API}/agents/{any_agent_ref}/enforce",
                               json={"action": "kill"}, timeout=30)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["agent"]["status"] == "killed"
        assert body["agent"].get("enforced") is True
        assert body["enforcement"]["action"] == "kill"

    def test_resume_sets_sanctioned(self, admin_session, any_agent_ref):
        r = admin_session.post(f"{API}/agents/{any_agent_ref}/enforce",
                               json={"action": "resume"}, timeout=30)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["agent"]["status"] == "sanctioned"
        assert body["agent"].get("enforced") is False
        assert body["enforcement"]["action"] == "resume"

    def test_unauthenticated_blocked(self, any_agent_ref):
        r = requests.post(f"{API}/agents/{any_agent_ref}/enforce",
                          json={"action": "suspend"}, timeout=30)
        assert r.status_code in (401, 403), f"expected auth block, got {r.status_code}"


# ------------ Shadow AI Discovery ------------

class TestShadowDiscovery:
    def test_discover_and_idempotent(self, admin_session):
        r1 = admin_session.post(f"{API}/ai-systems/discover", timeout=60)
        assert r1.status_code == 200, r1.text
        b1 = r1.json()
        assert b1.get("ok") is True
        assert "added" in b1 and "shadow_total" in b1
        total1 = b1["shadow_total"]

        r2 = admin_session.post(f"{API}/ai-systems/discover", timeout=60)
        assert r2.status_code == 200, r2.text
        b2 = r2.json()
        # Idempotent: second run should NOT add duplicates
        assert b2["added"] == 0, f"Discovery not idempotent, second run added {b2['added']}"
        assert b2["shadow_total"] == total1

    def test_discover_admin_only(self):
        r = requests.post(f"{API}/ai-systems/discover", timeout=30)
        assert r.status_code in (401, 403)


# ------------ Board Brief schedule ------------

class TestBoardBriefSchedule:
    def test_get_returns_schema(self, admin_session):
        r = admin_session.get(f"{API}/agents/board-brief/schedule", timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        assert "enabled" in d and "cadence" in d

    def test_put_persists_and_restore(self, admin_session):
        # Enable weekly
        r = admin_session.put(f"{API}/agents/board-brief/schedule",
                              json={"enabled": True, "cadence": "weekly"}, timeout=30)
        assert r.status_code == 200, r.text
        g = admin_session.get(f"{API}/agents/board-brief/schedule", timeout=30).json()
        assert g["enabled"] is True
        assert g["cadence"] == "weekly"

        # Restore
        r2 = admin_session.put(f"{API}/agents/board-brief/schedule",
                               json={"enabled": False, "cadence": "monthly"}, timeout=30)
        assert r2.status_code == 200
        g2 = admin_session.get(f"{API}/agents/board-brief/schedule", timeout=30).json()
        assert g2["enabled"] is False
        assert g2["cadence"] == "monthly"


# ------------ Board Brief send (real email — one call) ------------

class TestBoardBriefSend:
    def test_send_once(self, admin_session):
        r = admin_session.post(f"{API}/agents/board-brief/send", timeout=120)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d.get("ok") is True
        assert "sent" in d
        assert isinstance(d["sent"], int)


# ------------ Advisor grounded chat ------------

class TestAdvisorChat:
    def test_chat_returns_grounded_response(self, admin_session):
        r = admin_session.post(f"{API}/advisor/chat",
                               json={"message": "Summarize agentic AI risk posture"},
                               timeout=120)
        assert r.status_code == 200, r.text
        body = r.text
        # Advisor streams SSE ('data: {...}') OR returns JSON — either is fine, just needs content
        assert body and len(body) > 20, f"Advisor returned empty payload: {body!r}"
        assert ("delta" in body) or ("reply" in body) or ("message" in body) or ("answer" in body), \
            f"No advisor content markers in response: {body[:200]}"
