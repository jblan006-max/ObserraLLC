"""Iter55 tests: Identities lifecycle (person+account) + Access Monitoring live workflows + Connectors."""
import os
import requests
import pytest

BASE = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE:
    BASE = "https://cyber-dashboard-48.preview.emergentagent.com"
API = f"{BASE}/api"

CREDS = {"email": "jblan2026@gmail.com", "password": "Obserra2026!"}


@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json=CREDS, timeout=30)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    return s


# ---------- Connectors ----------
def test_connectors_all_live(session):
    r = session.get(f"{API}/sap/systems", timeout=30)
    assert r.status_code == 200
    data = r.json()
    connectors = data.get("connectors") or []
    assert len(connectors) == 43, f"expected 43 connectors, got {len(connectors)}"
    sap_uac = [c for c in connectors if c.get("scope") == "SAP UAC"]
    obserra = [c for c in connectors if c.get("scope") == "Obserra Platform"]
    assert len(sap_uac) == 7, f"expected 7 SAP UAC, got {len(sap_uac)}"
    assert len(obserra) == 36, f"expected 36 Obserra Platform, got {len(obserra)}"
    for c in connectors:
        assert c.get("status") == "connected", f"{c.get('id')} not connected"
        assert c.get("auth_ready") is True, f"{c.get('id')} auth_ready false"


# ---------- Identities ----------
def test_identities_list_and_detail(session):
    r = session.get(f"{API}/sap/identities", timeout=30)
    assert r.status_code == 200
    data = r.json()
    ids = data["identities"]
    assert len(ids) > 0
    # pick a person with accounts to exercise per-account workflow later
    with_accounts = [x for x in ids if x.get("accounts", 0) > 0]
    ref = (with_accounts[0] if with_accounts else ids[0])["ref"]
    d = session.get(f"{API}/sap/identities/{ref}", timeout=30)
    assert d.status_code == 200
    body = d.json()
    assert "activation_status" in body, "identity_detail missing activation_status"
    assert body["activation_status"] in ("Activated", "Suspended", "Deactivated")
    return body


def test_person_suspend_then_resume(session):
    # pick an Activated person with SAP accounts
    r = session.get(f"{API}/sap/identities", timeout=30)
    ids = r.json()["identities"]
    target = None
    for x in ids:
        if x.get("status") == "Active":
            d = session.get(f"{API}/sap/identities/{x['ref']}", timeout=30).json()
            if d.get("activation_status") == "Activated":
                target = d
                break
    assert target, "no activated person found"
    ref = target["person"]["ref"]
    # SUSPEND
    r = session.post(f"{API}/sap/activation/set", json={
        "person_refs": [ref], "action": "suspend", "reason": "TEST_iter55 suspend", "work_note": "TEST_iter55", "notify": False
    }, timeout=30)
    assert r.status_code == 200, r.text
    b = r.json()
    tickets = b.get("tickets") or []
    assert tickets, f"no ticket returned: {b}"
    tnum = tickets[0].get("number", "")
    assert tnum, "ticket number missing"
    # verify state changed
    d2 = session.get(f"{API}/sap/identities/{ref}", timeout=30).json()
    assert d2["activation_status"] == "Suspended", d2.get("activation_status")
    # RESUME
    r = session.post(f"{API}/sap/activation/set", json={
        "person_refs": [ref], "action": "resume", "reason": "TEST_iter55 resume", "work_note": "TEST_iter55", "notify": False
    }, timeout=30)
    assert r.status_code == 200, r.text
    b = r.json()
    assert b.get("tickets"), "no ticket on resume"
    d3 = session.get(f"{API}/sap/identities/{ref}", timeout=30).json()
    assert d3["activation_status"] == "Activated", d3.get("activation_status")


def test_account_recertify_and_ticket(session):
    # find a person with a non-locked account
    r = session.get(f"{API}/sap/identities", timeout=30).json()
    for x in r["identities"]:
        if x.get("accounts", 0) > 0:
            d = session.get(f"{API}/sap/identities/{x['ref']}", timeout=30).json()
            accs = d.get("accounts") or []
            if accs:
                acc_ref = accs[0]["ref"]
                resp = session.post(f"{API}/sap/accounts/{acc_ref}/action",
                                    json={"action": "recertify", "reason": "TEST_iter55 recertify"},
                                    timeout=30)
                assert resp.status_code == 200, resp.text
                body = resp.json()
                t = body.get("ticket") or {}
                assert t.get("number"), f"no ticket number: {body}"
                systems = t.get("systems") or body.get("systems_touched") or []
                assert systems, f"missing systems in ticket: {body}"
                assert "SAP" in systems and "ServiceNow" in systems, f"expected SAP+ServiceNow, got {systems}"
                return
    pytest.fail("no account found to recertify")


# ---------- Access Monitoring ----------
def test_access_monitoring_get(session):
    r = session.get(f"{API}/sap/access-monitoring", timeout=30)
    assert r.status_code == 200
    d = r.json()
    assert "counts" in d and set(["dormant", "orphan", "service"]).issubset(d["counts"].keys())
    assert isinstance(d.get("dormant"), list)
    assert isinstance(d.get("orphan"), list)
    assert isinstance(d.get("service_accounts"), list)


def test_access_monitoring_recertify_action(session):
    d = session.get(f"{API}/sap/access-monitoring", timeout=30).json()
    row = None
    for bucket in ("service_accounts", "dormant", "orphan"):
        if d.get(bucket):
            row = d[bucket][0]
            break
    assert row and row.get("ref"), "no monitoring row"
    r = session.post(f"{API}/sap/accounts/{row['ref']}/action",
                     json={"action": "recertify", "reason": "TEST_iter55 monitoring"},
                     timeout=30)
    assert r.status_code == 200, r.text
    body = r.json()
    t = body.get("ticket") or {}
    assert t.get("number"), f"no ticket: {body}"
    st = t.get("systems") or body.get("systems_touched") or []
    assert st, f"no systems in {body}"
    assert "SAP" in st and "ServiceNow" in st, f"expected SAP+ServiceNow, got {st}"
