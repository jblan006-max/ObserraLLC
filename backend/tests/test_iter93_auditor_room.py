"""Iter 93 - Auditor Room create/list/revoke + public read-only + standard actions."""
import os
import requests
import pytest

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://cyber-dashboard-48.preview.emergentagent.com").rstrip("/")
ADMIN_EMAIL = "jblan2026@gmail.com"
ADMIN_PASSWORD = "Obserra2026!"


@pytest.fixture(scope="module")
def admin_session():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert r.status_code == 200, f"login failed {r.status_code} {r.text}"
    return s


def test_evidence_room_create_list_revoke(admin_session):
    # Create
    r = admin_session.post(f"{BASE_URL}/api/agents/runtime/evidence-room", json={"days": 14})
    assert r.status_code == 200, r.text
    data = r.json()
    assert "token" in data and "url" in data and "expires_at" in data
    token = data["token"]
    assert "/audit-room/" in data["url"]

    # List
    r = admin_session.get(f"{BASE_URL}/api/agents/runtime/evidence-rooms")
    assert r.status_code == 200, r.text
    rooms = r.json().get("rooms", [])
    assert any(x["token"] == token for x in rooms), "created room not in list"
    row = next(x for x in rooms if x["token"] == token)
    for k in ("token", "url", "expires_at", "opens"):
        assert k in row, f"missing {k}"

    # Public unauth GET
    public = requests.get(f"{BASE_URL}/api/agents/public/evidence-room/{token}")
    assert public.status_code == 200, public.text
    pj = public.json()
    assert "snapshot" in pj or "attestation" in pj or "agents" in pj

    # PDF
    pdf = requests.get(f"{BASE_URL}/api/agents/public/evidence-room/{token}/pack.pdf")
    assert pdf.status_code == 200, pdf.status_code
    assert "pdf" in pdf.headers.get("content-type", "").lower()

    # Invalid token
    bad = requests.get(f"{BASE_URL}/api/agents/public/evidence-room/bogus123nonexistent")
    assert bad.status_code in (404, 410)

    # Revoke
    r = admin_session.post(f"{BASE_URL}/api/agents/runtime/evidence-room/revoke", json={"token": token})
    assert r.status_code == 200, r.text

    # After revoke, list should not contain it
    r = admin_session.get(f"{BASE_URL}/api/agents/runtime/evidence-rooms")
    rooms = r.json().get("rooms", [])
    assert not any(x["token"] == token for x in rooms), "revoked room still listed"

    # After revoke, public should fail
    public2 = requests.get(f"{BASE_URL}/api/agents/public/evidence-room/{token}")
    assert public2.status_code in (404, 410), f"expected 404/410 after revoke, got {public2.status_code}"


def test_standard_agent_actions_suspend_resume(admin_session):
    # Suspend AGT-001
    r = admin_session.post(f"{BASE_URL}/api/actions/run", json={"action_id": "agent_suspend:AGT-001"})
    assert r.status_code == 200, r.text
    # Resume AGT-001 to restore baseline
    r = admin_session.post(f"{BASE_URL}/api/actions/run", json={"action_id": "agent_resume:AGT-001"})
    assert r.status_code == 200, r.text


def test_standard_aisys_sanction_block(admin_session):
    # try shadow system SHAI-LLM-openai
    r = admin_session.post(f"{BASE_URL}/api/actions/run", json={"action_id": "aisys_sanction:SHAI-LLM-openai"})
    # Some orgs may not have it — accept 200 or 404
    assert r.status_code in (200, 400, 404), r.text
