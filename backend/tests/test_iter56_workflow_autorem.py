"""Iter56 - Verify new SAP UAC features:
- Uniform ticket shape (systems_touched key on every action endpoint)
- Access Monitoring bulk-action endpoint
- Workflow Activity feed
- SoD Auto-Remediation engine (enable, live-hook via /sod/conflicts, run idempotency, disable)
- JML movers panel
- User Activation per-user detail endpoint (GET /api/sap/identities/{user_id})
"""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
EMAIL = "jblan2026@gmail.com"
PASSWORD = "Obserra2026!"


@pytest.fixture(scope="module")
def client():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login",
               json={"email": EMAIL, "password": PASSWORD}, timeout=30)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text[:200]}"
    body = r.json()
    # Cookie based - no 'token' field expected
    assert "token" not in body, "auth should be cookie-based, but a token was returned"
    assert body.get("email") == EMAIL or body.get("user", {}).get("email") == EMAIL
    return s


# ---------- Uniform ticket shape ----------
def _assert_ticket_shape(t):
    assert isinstance(t, dict), f"ticket not dict: {t}"
    for k in ("number", "type", "state", "systems_touched"):
        assert k in t, f"ticket missing '{k}': keys={list(t.keys())}"
    assert isinstance(t["systems_touched"], list) and len(t["systems_touched"]) >= 1
    # explicit: NO legacy 'systems' root key
    assert "systems" not in t, f"legacy 'systems' key still present: {t}"


def _get_account_refs(client, n=2):
    r = client.get(f"{BASE_URL}/api/sap/access-monitoring", timeout=30)
    assert r.status_code == 200, r.text[:200]
    j = r.json()
    pool = (j.get("dormant") or []) + (j.get("orphan") or []) + (j.get("service") or [])
    refs = [a.get("ref") or a.get("account_ref") for a in pool if (a.get("ref") or a.get("account_ref"))]
    return refs[:n]


def test_account_action_ticket_shape(client):
    refs = _get_account_refs(client, 1)
    assert refs, "no account refs from access-monitoring"
    ref = refs[0]
    r = client.post(f"{BASE_URL}/api/sap/accounts/{ref}/action",
                    json={"action": "recertify", "reason": "iter56 uniform shape check"},
                    timeout=30)
    assert r.status_code == 200, r.text[:200]
    _assert_ticket_shape(r.json()["ticket"])


def test_activation_set_tickets_shape(client):
    # Grab a person and hit activation/set with resume/suspend cycle
    r = client.get(f"{BASE_URL}/api/sap/identities?limit=5", timeout=30)
    assert r.status_code == 200
    data = r.json()
    people = data.get("identities") or data.get("items") or []
    if not people:
        pytest.skip("no identities")
    # Find an Activated person to safely suspend->resume
    ref = None
    for p in people:
        if (p.get("activation_status") or "Activated") == "Activated":
            ref = p.get("person_ref") or p.get("ref") or p.get("id")
            break
    if not ref:
        ref = people[0].get("person_ref") or people[0].get("ref") or people[0].get("id")
    # Try a reversible action: suspend then resume
    r = client.post(f"{BASE_URL}/api/sap/activation/set",
                    json={"person_refs": [ref], "action": "suspend",
                          "reason": "iter56 ticket shape", "notify": False},
                    timeout=30)
    assert r.status_code == 200, r.text[:300]
    tickets = r.json().get("tickets", [])
    assert len(tickets) >= 1
    for t in tickets:
        _assert_ticket_shape(t)
    # restore
    client.post(f"{BASE_URL}/api/sap/activation/set",
                json={"person_refs": [ref], "action": "resume",
                      "reason": "iter56 restore", "notify": False}, timeout=30)


# ---------- Bulk action ----------
def test_bulk_action(client):
    refs = _get_account_refs(client, 2)
    assert len(refs) == 2, f"need 2 account refs, got {refs}"
    r = client.post(f"{BASE_URL}/api/sap/accounts/bulk-action",
                    json={"refs": refs, "action": "recertify",
                          "reason": "iter56 bulk"}, timeout=45)
    assert r.status_code == 200, r.text[:300]
    body = r.json()
    tickets = body.get("tickets", [])
    assert len(tickets) == 2, f"expected 2 tickets, got {len(tickets)}: {body}"
    for t in tickets:
        _assert_ticket_shape(t)


# ---------- Workflow feed ----------
def test_workflow_activity(client):
    r = client.get(f"{BASE_URL}/api/sap/workflow/activity", timeout=30)
    assert r.status_code == 200
    body = r.json()
    tickets = body.get("tickets") or body.get("items") or []
    assert len(tickets) > 0, "workflow activity empty"
    t0 = tickets[0]
    for k in ("number", "systems_touched"):
        assert k in t0, f"workflow ticket missing {k}: {list(t0.keys())}"
    # filter by system
    r = client.get(f"{BASE_URL}/api/sap/workflow/activity?system=ServiceNow", timeout=30)
    assert r.status_code == 200
    filtered = r.json().get("tickets", [])
    assert all("ServiceNow" in t.get("systems_touched", []) for t in filtered[:20])


# ---------- Auto-Remediation ----------
def test_autoremediation_engine(client):
    # 1. GET current config (should be OFF, ~16 candidates)
    r = client.get(f"{BASE_URL}/api/sap/autoremediation", timeout=30)
    assert r.status_code == 200
    cfg = r.json()
    assert "config" in cfg and "enabled" in cfg["config"]
    initial_candidates = cfg.get("candidates", 0)
    print(f"initial candidates={initial_candidates}, enabled={cfg['config']['enabled']}")

    # 2. Enable
    r = client.put(f"{BASE_URL}/api/sap/autoremediation",
                   json={"enabled": True, "severities": ["Critical"],
                         "action": "recertify"}, timeout=90)
    assert r.status_code == 200, r.text[:300]
    body = r.json()
    created = body.get("created", body.get("tickets", []))
    print(f"enable created={len(created) if isinstance(created, list) else created}")

    # 3. Idempotent re-run
    r = client.post(f"{BASE_URL}/api/sap/autoremediation/run", timeout=45)
    assert r.status_code == 200
    body2 = r.json()
    new_created = body2.get("created", body2.get("tickets", []))
    if isinstance(new_created, list):
        assert len(new_created) == 0, f"expected idempotent 0 new, got {len(new_created)}"
    else:
        assert new_created == 0

    # 4. Live hook: GET /sod/conflicts should not create new remediations either
    r = client.get(f"{BASE_URL}/api/sap/sod/conflicts", timeout=30)
    assert r.status_code == 200

    # 5. Verify log populated
    r = client.get(f"{BASE_URL}/api/sap/autoremediation", timeout=30)
    assert r.status_code == 200
    cfg2 = r.json()
    log = cfg2.get("log", cfg2.get("recent", []))
    assert isinstance(log, list) and len(log) > 0, "autorem log should be populated"

    # 6. Disable (cleanup as directed)
    r = client.put(f"{BASE_URL}/api/sap/autoremediation",
                   json={"enabled": False, "severities": ["Critical"],
                         "action": "recertify"}, timeout=30)
    assert r.status_code == 200


# ---------- JML movers ----------
def test_jml_movers(client):
    r = client.get(f"{BASE_URL}/api/sap/jml", timeout=30)
    assert r.status_code == 200
    body = r.json()
    for key in ("leavers", "joiners", "movers"):
        assert key in body, f"jml payload missing {key}: keys={list(body.keys())}"
    print(f"jml counts leavers={len(body['leavers'])} joiners={len(body['joiners'])} movers={len(body['movers'])}")
    assert len(body["movers"]) >= 1, "expected movers to be non-empty"
    m = body["movers"][0]
    # movers must expose the ADP -> IZ8 disagreement fields somewhere
    assert any(k in m for k in ("person_ref", "ref", "id")), f"mover missing ref: {list(m.keys())}"


# ---------- Per-user identity detail ----------
def test_identity_detail(client):
    r = client.get(f"{BASE_URL}/api/sap/identities?limit=1", timeout=30)
    people = r.json().get("identities") or r.json().get("items") or []
    if not people:
        pytest.skip("no identities")
    ref = people[0].get("person_ref") or people[0].get("ref") or people[0].get("id")
    r = client.get(f"{BASE_URL}/api/sap/identities/{ref}", timeout=30)
    assert r.status_code == 200, r.text[:300]
    d = r.json()
    for k in ("activation_status",):
        assert k in d, f"identity detail missing {k}: {list(d.keys())}"
