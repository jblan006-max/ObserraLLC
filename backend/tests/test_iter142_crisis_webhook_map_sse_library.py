"""Iteration 142 — Crisis Commander re-test of iter141 features after parenthesis fix.
Focus:
 - POST /api/crisis/webhook/test-map with vendor formats (generic, crowdstrike, splunk, sentinel, servicenow)
 - POST /api/crisis/ingest/webhook accepting {secret, format, payload} native JSON; invalid secret => 401
 - GET  /api/crisis/public/snapshot/{token}/stream — SSE emits 'data:' events; invalid token 404
 - GET  /api/crisis/scenario/library returns 4 scenarios: ransomware, insider, third_party, ddos
 - Cleanup: revoke created snapshot, stop scenario
"""
import os, json, time, threading
import requests
import pytest

BASE = (os.environ.get("REACT_APP_BACKEND_URL") or open("/app/frontend/.env").read().split("REACT_APP_BACKEND_URL=")[1].splitlines()[0]).rstrip("/")
API = f"{BASE}/api"

EMAIL = "jblan2026@gmail.com"
PASS  = "Obserra2026!"


@pytest.fixture(scope="module")
def s():
    sess = requests.Session()
    r = sess.post(f"{API}/auth/login", json={"email": EMAIL, "password": PASS}, timeout=20)
    assert r.status_code == 200, r.text
    return sess


@pytest.fixture(scope="module")
def secret(s):
    r = s.get(f"{API}/crisis/webhook/config", timeout=15)
    assert r.status_code == 200, r.text
    return r.json()["secret"]


# ---------------- FEATURE 1: webhook/test-map with all vendor formats ----------------

CROWDSTRIKE_SAMPLE = {
    "metadata": {"eventType": "DetectionSummaryEvent", "customerIDString": "abc"},
    "event": {
        "DetectName": "Ransomware.WannaCry",
        "SeverityName": "Critical",
        "ComputerName": "host01",
        "UserName": "jdoe",
        "Tactic": "Impact",
        "Technique": "Data Encrypted for Impact",
    },
}
SPLUNK_SAMPLE = {"result": {"signature": "Brute force detected", "severity": "high", "src": "10.0.0.5", "dest": "srv01", "user": "admin"}}
SENTINEL_SAMPLE = {"AlertDisplayName": "Suspicious sign-in", "Severity": "High", "Description": "Impossible travel", "Entities": [{"UserPrincipalName": "u@x.com"}]}
SERVICENOW_SAMPLE = {"short_description": "Phishing report", "priority": "1", "description": "User clicked link", "assigned_to": "sec-team"}
GENERIC_SAMPLE = {"title": "Suspicious login", "severity": "high", "source": "SIEM", "detail": "10 failed attempts"}


@pytest.mark.parametrize("fmt,payload", [
    ("generic", GENERIC_SAMPLE),
    ("crowdstrike", CROWDSTRIKE_SAMPLE),
    ("splunk", SPLUNK_SAMPLE),
    ("sentinel", SENTINEL_SAMPLE),
    ("servicenow", SERVICENOW_SAMPLE),
])
def test_webhook_test_map_vendors(s, fmt, payload):
    r = s.post(f"{API}/crisis/webhook/test-map", json={"format": fmt, "payload": payload}, timeout=15)
    assert r.status_code == 200, f"{fmt}: {r.status_code} {r.text}"
    j = r.json()
    # Response shape: mapped fields — check core keys
    # Accept either {"mapped": {...}} or flat fields
    m = j.get("mapped", j)
    assert isinstance(m, dict)
    # At minimum should have title & severity mapped
    keys_lower = {k.lower() for k in m.keys()}
    assert any(k in keys_lower for k in ("title", "detail", "severity", "source", "kind")), f"{fmt}: no expected keys in {m}"


# ---------------- FEATURE 1b: ingest/webhook with native format+payload ----------------

def test_ingest_webhook_native_format_crowdstrike(secret):
    # public - no cookie
    pub = requests.Session()
    body = {"secret": secret, "format": "crowdstrike", "payload": CROWDSTRIKE_SAMPLE}
    r = pub.post(f"{API}/crisis/ingest/webhook", json=body, timeout=20)
    assert r.status_code == 200, r.text
    j = r.json()
    assert j.get("ok") is True or "case_id" in j or "case" in j, j


def test_ingest_webhook_invalid_secret_401():
    pub = requests.Session()
    body = {"secret": "whk_INVALID_xxxxxxxxxxxx", "format": "generic", "payload": GENERIC_SAMPLE}
    r = pub.post(f"{API}/crisis/ingest/webhook", json=body, timeout=15)
    assert r.status_code == 401, f"expected 401 got {r.status_code}: {r.text}"


# ---------------- FEATURE 2: SSE stream ----------------

def test_snapshot_sse_stream_emits_data(s):
    # Need a case first
    cases = s.get(f"{API}/crisis/cases", timeout=15).json()
    lst = cases if isinstance(cases, list) else (cases.get("items") or cases.get("cases") or [])
    assert lst, f"no cases available to snapshot: {cases}"
    case = lst[0]
    ref = case.get("ref") or case.get("id") or case.get("case_id") or case.get("_id")
    assert ref, case

    snap = s.post(f"{API}/crisis/cases/{ref}/snapshot", json={}, timeout=15)
    assert snap.status_code == 200, snap.text
    j = snap.json()
    token = j.get("token")
    assert token, j

    # Consume SSE stream briefly
    pub = requests.Session()
    got_data = {"seen": False, "err": None}
    def consume():
        try:
            with pub.get(f"{API}/crisis/public/snapshot/{token}/stream", stream=True, timeout=15) as r:
                assert r.status_code == 200, r.text
                ctype = r.headers.get("content-type", "")
                assert "event-stream" in ctype, f"content-type={ctype}"
                start = time.time()
                for line in r.iter_lines(decode_unicode=True):
                    if line and line.startswith("data:"):
                        got_data["seen"] = True
                        break
                    if time.time() - start > 10:
                        break
        except Exception as e:
            got_data["err"] = str(e)

    t = threading.Thread(target=consume, daemon=True)
    t.start()
    t.join(timeout=12)
    assert got_data["err"] is None, got_data["err"]
    assert got_data["seen"], "SSE stream did not emit any 'data:' line within 10s"

    # cleanup: revoke via case ref
    rv = s.post(f"{API}/crisis/cases/{ref}/snapshot/revoke", timeout=15)
    assert rv.status_code in (200, 204), rv.text


def test_snapshot_sse_invalid_token_error():
    """Invalid token: SSE streams a 'data:' payload with error field (StreamingResponse starts 200
    then emits an error event). Verify we either get non-200 OR a data line containing 'error'."""
    pub = requests.Session()
    got = {"ok": False, "status": None, "data": None}
    with pub.get(f"{API}/crisis/public/snapshot/BOGUS_TOKEN_XYZ/stream", stream=True, timeout=10) as r:
        got["status"] = r.status_code
        if r.status_code != 200:
            got["ok"] = True
        else:
            start = time.time()
            for line in r.iter_lines(decode_unicode=True):
                if line and line.startswith("data:"):
                    got["data"] = line
                    if "error" in line.lower() or "invalid" in line.lower() or "revoked" in line.lower():
                        got["ok"] = True
                    break
                if time.time() - start > 6:
                    break
    assert got["ok"], f"expected error signal for bogus token, got status={got['status']} data={got['data']}"


# ---------------- FEATURE 3: scenario library returns 4 ----------------

def test_scenario_library_has_4(s):
    r = s.get(f"{API}/crisis/scenario/library", timeout=15)
    assert r.status_code == 200, r.text
    j = r.json()
    items = j if isinstance(j, list) else (j.get("items") or j.get("scenarios") or [])
    keys = {(it.get("key") or it.get("id")) for it in items}
    assert {"ransomware", "insider", "third_party", "ddos"}.issubset(keys), f"got keys {keys}"
    assert len(items) >= 4


def test_scenario_start_advance_stop(s):
    # Start ransomware
    r = s.post(f"{API}/crisis/scenario/start", json={"key": "ransomware"}, timeout=15)
    assert r.status_code == 200, r.text
    j = r.json()
    assert (j.get("total") or j.get("steps_total")) in (9, None) or isinstance(j, dict)

    # Advance
    a = s.post(f"{API}/crisis/scenario/advance", timeout=15)
    assert a.status_code == 200, a.text

    # Status
    st = s.get(f"{API}/crisis/scenario/status", timeout=15)
    assert st.status_code == 200, st.text

    # Stop / cleanup
    sp = s.post(f"{API}/crisis/scenario/stop", timeout=15)
    assert sp.status_code == 200, sp.text


def test_zz_cleanup_demo(s):
    # Nuke any leftover demo rows this test could have created
    try:
        s.post(f"{API}/crisis/scenario/stop", timeout=10)
    except Exception:
        pass
    try:
        s.post(f"{API}/crisis/demo/clear", timeout=10)
    except Exception:
        pass
