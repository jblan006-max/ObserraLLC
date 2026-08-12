"""Iteration 141 — Crisis Commander: webhook feed, board snapshot link, sample-breach scenario."""
import os
import requests
import pytest

BASE = (os.environ.get("REACT_APP_BACKEND_URL") or open("/app/frontend/.env").read().split("REACT_APP_BACKEND_URL=")[1].splitlines()[0]).rstrip("/")
API = f"{BASE}/api"

EMAIL = "jblan2026@gmail.com"
PASS = "Obserra2026!"


@pytest.fixture(scope="module")
def s():
    sess = requests.Session()
    r = sess.post(f"{API}/auth/login", json={"email": EMAIL, "password": PASS}, timeout=20)
    assert r.status_code == 200, r.text
    return sess


@pytest.fixture(scope="module")
def public():
    # No auth session (cookies must not be sent)
    return requests.Session()


# ---------------- Webhook ----------------

def test_webhook_config(s):
    r = s.get(f"{API}/crisis/webhook/config", timeout=15)
    assert r.status_code == 200, r.text
    j = r.json()
    assert "secret" in j and isinstance(j["secret"], str) and len(j["secret"]) >= 16
    assert j["path"] == "/api/crisis/ingest/webhook"
    assert isinstance(j.get("recent"), list)
    assert isinstance(j.get("count"), int)


def test_webhook_rotate_changes_secret(s):
    before = s.get(f"{API}/crisis/webhook/config").json()["secret"]
    r = s.post(f"{API}/crisis/webhook/rotate", timeout=15)
    assert r.status_code == 200, r.text
    new = r.json().get("secret")
    assert new and new != before


def test_webhook_ingest_invalid_secret(public):
    r = public.post(f"{API}/crisis/ingest/webhook",
                    json={"secret": "bogus-secret", "events": [{"title": "x"}]}, timeout=15)
    assert r.status_code == 401, r.text


def test_webhook_ingest_missing_secret(public):
    r = public.post(f"{API}/crisis/ingest/webhook",
                    json={"secret": "", "events": [{"title": "x"}]}, timeout=15)
    assert r.status_code == 401


def test_webhook_ingest_empty_events_400(s, public):
    secret = s.get(f"{API}/crisis/webhook/config").json()["secret"]
    r = public.post(f"{API}/crisis/ingest/webhook",
                    json={"secret": secret, "events": []}, timeout=15)
    assert r.status_code == 400, r.text


def test_webhook_ingest_public_no_cookie_success(s, public):
    secret = s.get(f"{API}/crisis/webhook/config").json()["secret"]
    payload = {
        "secret": secret,
        "open_case": True,
        "case_title": "TEST_iter141 inbound webhook",
        "events": [
            {"title": "TEST_iter141 event A", "detail": "detail A", "severity": "High"},
            {"title": "TEST_iter141 event B", "detail": "detail B"},
        ],
    }
    r = public.post(f"{API}/crisis/ingest/webhook", json=payload, timeout=20)
    assert r.status_code == 200, r.text
    j = r.json()
    assert j.get("ok") is True
    assert j.get("case_ref")
    assert j.get("ingested") == 2
    # Should appear in webhook/config.recent (as via='webhook')
    cfg = s.get(f"{API}/crisis/webhook/config").json()
    titles = [e.get("title", "") for e in cfg["recent"]]
    assert any("TEST_iter141" in t for t in titles), f"recent lacks TEST_iter141: {titles[:5]}"


# ---------------- Snapshot ----------------

@pytest.fixture(scope="module")
def case_ref(s):
    # Reuse an open case if possible, else use one from webhook ingest above
    r = s.get(f"{API}/crisis/cases", timeout=15)
    if r.status_code == 200:
        cases = r.json() if isinstance(r.json(), list) else r.json().get("cases", [])
        if cases:
            return cases[0].get("ref") or cases[0].get("case_ref")
    # Fallback: open one via webhook
    secret = s.get(f"{API}/crisis/webhook/config").json()["secret"]
    r = requests.post(f"{API}/crisis/ingest/webhook",
                      json={"secret": secret, "open_case": True,
                            "events": [{"title": "TEST_iter141 fixture"}]}, timeout=15)
    return r.json()["case_ref"]


def test_snapshot_create_get_public_revoke(s, public, case_ref):
    r = s.post(f"{API}/crisis/cases/{case_ref}/snapshot", json={"expires_days": 7}, timeout=15)
    assert r.status_code == 200, r.text
    j = r.json()
    tok = j["token"]
    assert j["path"] == f"/crisis-snapshot/{tok}"
    assert "expires_at" in j

    g = s.get(f"{API}/crisis/cases/{case_ref}/snapshot", timeout=15).json()
    assert g["active"] is True and g["token"] == tok

    # PUBLIC — no cookie
    p = public.get(f"{API}/crisis/public/snapshot/{tok}", timeout=15)
    assert p.status_code == 200, p.text
    pj = p.json()
    for k in ("timeline", "pending_decisions", "regulatory"):
        assert k in pj, f"missing {k}"

    # Bogus token 404
    b = public.get(f"{API}/crisis/public/snapshot/nope-bogus-token-xyz", timeout=15)
    assert b.status_code == 404

    # Revoke
    rv = s.post(f"{API}/crisis/cases/{case_ref}/snapshot/revoke", timeout=15)
    assert rv.status_code == 200
    p2 = public.get(f"{API}/crisis/public/snapshot/{tok}", timeout=15)
    assert p2.status_code == 404


# ---------------- Scenario ----------------

def test_scenario_full_flow(s):
    # Stop any pre-existing
    s.post(f"{API}/crisis/scenario/stop", timeout=15)

    r = s.post(f"{API}/crisis/scenario/start", timeout=20)
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["step"] == 1
    total = j["total"]
    assert total == 9
    ref = j["ref"]

    st = s.get(f"{API}/crisis/scenario/status", timeout=15).json()
    assert st["active"] is True and st["step"] == 1 and st["total"] == total and st["done"] is False

    # Advance to step 2
    a2 = s.post(f"{API}/crisis/scenario/advance", timeout=15).json()
    assert a2["step"] == 2 and a2["done"] is False and isinstance(a2.get("revealed"), list)

    # Advance all the way to done
    last = a2
    for _ in range(total + 2):
        if last.get("done"):
            break
        last = s.post(f"{API}/crisis/scenario/advance", timeout=15).json()
    assert last.get("done") is True
    assert last["step"] == total

    # Stop clears
    stop = s.post(f"{API}/crisis/scenario/stop", timeout=15)
    assert stop.status_code == 200
    st2 = s.get(f"{API}/crisis/scenario/status", timeout=15).json()
    assert st2.get("active") is False
    return ref


# ---------------- Cleanup ----------------

def test_zz_cleanup(s):
    s.post(f"{API}/crisis/scenario/stop", timeout=15)
    r = s.post(f"{API}/crisis/demo/clear", timeout=20)
    # demo/clear may be 200 or 204
    assert r.status_code in (200, 204), r.text
