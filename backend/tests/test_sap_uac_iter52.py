"""SAP UAC iteration 52 tests: AI insight, activation 3-state (suspend/resume),
create user, bulk suspend, and agentic advisor plan endpoint."""
import os
import pytest
import requests

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
EMAIL = "jblan2026@gmail.com"
PASSWORD = "Obserra2026!"


@pytest.fixture(scope="module")
def client():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json={"email": EMAIL, "password": PASSWORD}, timeout=30)
    assert r.status_code == 200, r.text
    return s


# ── AI Summary ─────────────────────────────────────────────────────────────
def test_insight_structure(client):
    r = client.get(f"{BASE_URL}/api/sap/insight", timeout=60)
    assert r.status_code == 200, r.text
    d = r.json()
    assert isinstance(d.get("headline"), str) and d["headline"].strip()
    ins = d.get("insights") or []
    assert 3 <= len(ins) <= 5, f"insights count out of bounds: {len(ins)}"
    for i in ins:
        assert isinstance(i.get("text"), str) and i["text"].strip()
        assert i.get("kind") in ("fact", "estimate", "risk"), f"bad kind: {i.get('kind')}"
    acts = d.get("actions") or []
    assert 2 <= len(acts) <= 4, f"actions count out of bounds: {len(acts)}"


# ── Activation 3-state transitions ─────────────────────────────────────────
def _pick_activated(client):
    r = client.get(f"{BASE_URL}/api/sap/identities", timeout=30)
    assert r.status_code == 200
    persons = r.json().get("identities") or r.json().get("persons") or []
    for p in persons:
        if (p.get("activation_status") or p.get("status_effective") or "Activated") == "Activated":
            return p["ref"]
    # fallback: activate one and return
    return persons[0]["ref"]


def _validate_ticket(t):
    systems = set(t.get("systems") or [])
    assert "ServiceNow" in systems
    assert "SAP" in systems
    assert systems & {"ADP", "IZ8"}
    assert systems & {"AD/Entra", "AD", "Entra"} or "AD/Entra" in systems
    assert t["state"] == "Closed"


def test_activation_suspend_then_resume_then_deactivate_then_activate(client):
    ref = _pick_activated(client)

    # suspend
    r = client.post(f"{BASE_URL}/api/sap/activation/set",
                    json={"person_refs": [ref], "action": "suspend", "reason": "TEST_ suspend"}, timeout=30)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["changed"] >= 1
    assert d["status"] == "Suspended"
    assert len(d["tickets"]) == 1
    _validate_ticket(d["tickets"][0])

    # resume
    r = client.post(f"{BASE_URL}/api/sap/activation/set",
                    json={"person_refs": [ref], "action": "resume", "reason": "TEST_ resume"}, timeout=30)
    assert r.status_code == 200
    d = r.json()
    assert d["changed"] >= 1 and d["status"] == "Activated"
    _validate_ticket(d["tickets"][0])

    # deactivate
    r = client.post(f"{BASE_URL}/api/sap/activation/set",
                    json={"person_refs": [ref], "action": "deactivate", "reason": "TEST_ deactivate"}, timeout=30)
    assert r.status_code == 200
    d = r.json()
    assert d["changed"] >= 1 and d["status"] == "Deactivated"
    _validate_ticket(d["tickets"][0])

    # activate back
    r = client.post(f"{BASE_URL}/api/sap/activation/set",
                    json={"person_refs": [ref], "action": "activate", "reason": "TEST_ activate"}, timeout=30)
    assert r.status_code == 200
    d = r.json()
    assert d["changed"] >= 1 and d["status"] == "Activated"
    _validate_ticket(d["tickets"][0])


# ── Bulk suspend ───────────────────────────────────────────────────────────
def test_bulk_suspend_all_active(client):
    r = client.post(f"{BASE_URL}/api/sap/activation/bulk",
                    json={"action": "suspend", "reason": "TEST_ bulk suspend"}, timeout=90)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["status"] == "Suspended"
    assert d["ticket_count"] == d["changed"]
    if d["changed"] > 0:
        _validate_ticket(d["tickets"][0])

    # reactivate back to leave org in usable state
    r2 = client.post(f"{BASE_URL}/api/sap/activation/bulk",
                     json={"action": "activate", "reason": "TEST_ bulk reactivate"}, timeout=90)
    assert r2.status_code == 200


# ── Create user ────────────────────────────────────────────────────────────
def test_create_user(client):
    r = client.post(f"{BASE_URL}/api/sap/activation/create",
                    json={"first_name": "TEST", "last_name": "Iter52",
                          "email": "test.iter52@example.com",
                          "department": "Finance", "legal_entity": "US01"}, timeout=30)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["ok"] and d.get("person_ref")
    assert d["ticket"]["state"] == "Closed"


# ── Advisor plan (agentic) ─────────────────────────────────────────────────
def test_advisor_plan_suspend_all(client):
    r = client.post(f"{BASE_URL}/api/sap/advisor/plan",
                    json={"instruction": "suspend all active users"}, timeout=30)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d.get("actionable") is True
    assert d.get("action") == "suspend"
    assert d.get("count", 0) > 0
    assert isinstance(d.get("person_refs"), list) and len(d["person_refs"]) > 0


def test_advisor_plan_deactivate_terminated(client):
    r = client.post(f"{BASE_URL}/api/sap/advisor/plan",
                    json={"instruction": "deactivate all terminated workers still holding SAP access"}, timeout=30)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d.get("action") == "deactivate"
    # actionable depends on data; if any residual-access, must be True
    if d.get("count", 0) > 0:
        assert d["actionable"] is True
        assert len(d["person_refs"]) == d["count"]


def test_advisor_plan_create_guidance(client):
    r = client.post(f"{BASE_URL}/api/sap/advisor/plan",
                    json={"instruction": "create a finance user"}, timeout=30)
    assert r.status_code == 200
    d = r.json()
    assert d.get("action") == "create"
    assert d.get("actionable") is False
    assert isinstance(d.get("message"), str) and d["message"].strip()
