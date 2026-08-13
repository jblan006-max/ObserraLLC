"""
Iteration 158 - Test new CRA risk features:
- Risk register PDF/CSV export
- Risk owners assign/clear
- Risk trend endpoint
- Public exec-overview with risk + snapshot movement
- Exec email preview includes CORRELATED RISK section
"""
import os
import re
import time
import pytest
import requests

def _read_env(path, key):
    try:
        with open(path) as f:
            for line in f:
                if line.startswith(key + "="):
                    return line.split("=", 1)[1].strip()
    except Exception:
        return None
    return None

BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or _read_env("/app/frontend/.env", "REACT_APP_BACKEND_URL") or "").rstrip("/")
assert BASE_URL, "REACT_APP_BACKEND_URL not set"
ADMIN_EMAIL = "jblan2026@gmail.com"
ADMIN_PASSWORD = "Obserra2026!"


@pytest.fixture(scope="module")
def admin_session():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=30)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text[:200]}"
    return s


# --- Risk correlation base (need keys for owner test) ---
def test_risk_correlation_has_keys(admin_session):
    r = admin_session.get(f"{BASE_URL}/api/cra/risk-correlation", timeout=30)
    assert r.status_code == 200
    data = r.json()
    risks = data.get("risks", [])
    assert len(risks) > 0, "no correlated risks returned"
    for risk in risks:
        assert "key" in risk and risk["key"], f"missing stable key: {risk}"
    # overall.top_risks
    overall = data.get("overall") or {}
    assert "top_risks" in overall, "overall.top_risks missing"


# --- Risk register CSV ---
def test_risk_register_csv(admin_session):
    r = admin_session.get(f"{BASE_URL}/api/cra/risk-register.csv", timeout=30)
    assert r.status_code == 200
    ct = r.headers.get("content-type", "")
    assert "text/csv" in ct, f"unexpected content-type: {ct}"
    first_line = r.text.splitlines()[0] if r.text else ""
    expected_header = "Rating,Score,Severity,Likelihood,Category,Risk,Owner,Owner email,Due date,Mapped controls,NIST CSF,Recommendation,Fixes"
    assert first_line == expected_header, f"header mismatch: {first_line!r}"


# --- Risk register PDF ---
def test_risk_register_pdf(admin_session):
    r = admin_session.get(f"{BASE_URL}/api/cra/risk-register.pdf", timeout=30)
    assert r.status_code == 200
    ct = r.headers.get("content-type", "")
    assert "application/pdf" in ct, f"unexpected content-type: {ct}"
    assert r.content[:4] == b"%PDF", f"not a PDF: {r.content[:20]!r}"
    assert len(r.content) > 500


# --- Risk trend ---
def test_risk_trend(admin_session):
    r = admin_session.get(f"{BASE_URL}/api/cra/risk-trend?days=30", timeout=30)
    assert r.status_code == 200
    j = r.json()
    assert "days" in j and "series" in j and "current" in j
    assert isinstance(j["series"], list)
    assert isinstance(j["current"], (int, float))


# --- Owner assign / GET / DELETE flow ---
def test_risk_owner_assign_and_clear(admin_session):
    r = admin_session.get(f"{BASE_URL}/api/cra/risk-correlation", timeout=30)
    risks = r.json().get("risks", [])
    # find an unassigned risk (skip risk-0 known assigned to Dana Ruiz)
    target = None
    for risk in risks:
        if not risk.get("owner"):
            target = risk
            break
    if target is None:
        pytest.skip("no unassigned risk available to test")

    payload = {
        "risk_key": target["key"],
        "risk_title": target.get("title") or target.get("risk") or "Test risk",
        "owner": "TEST_Owner Person",
        "owner_email": "test_owner@example.com",
        "due_date": "2026-06-30",
    }
    r2 = admin_session.post(f"{BASE_URL}/api/cra/risk-owner", json=payload, timeout=30)
    assert r2.status_code in (200, 201), f"assign failed: {r2.status_code} {r2.text[:200]}"

    # verify persisted via GET
    r3 = admin_session.get(f"{BASE_URL}/api/cra/risk-correlation", timeout=30)
    risks2 = r3.json().get("risks", [])
    found = next((x for x in risks2 if x.get("key") == target["key"]), None)
    assert found is not None
    assert found.get("owner") == "TEST_Owner Person", f"owner not joined: {found}"
    assert found.get("due_date") == "2026-06-30"

    # cleanup
    r4 = admin_session.delete(f"{BASE_URL}/api/cra/risk-owner/{target['key']}", timeout=30)
    assert r4.status_code in (200, 204)

    r5 = admin_session.get(f"{BASE_URL}/api/cra/risk-correlation", timeout=30)
    risks3 = r5.json().get("risks", [])
    cleared = next((x for x in risks3 if x.get("key") == target["key"]), None)
    assert cleared is not None
    assert not cleared.get("owner"), f"owner not cleared: {cleared}"


# --- Exec email preview includes CORRELATED RISK ---
def test_exec_email_preview_has_risk(admin_session):
    r = admin_session.get(f"{BASE_URL}/api/cra/exec-email/preview", timeout=30)
    assert r.status_code == 200
    body = r.text
    assert "CORRELATED RISK" in body.upper() or "Correlated risk" in body, "risk section missing in email preview"


# --- Public exec overview with snapshot movement + risk ---
def test_public_exec_overview_risk_and_movement(admin_session):
    # save a snapshot
    snap = admin_session.post(f"{BASE_URL}/api/cra/exec-snapshot", json={"label": "TEST_iter158"}, timeout=30)
    assert snap.status_code in (200, 201), f"snapshot failed: {snap.status_code} {snap.text[:200]}"

    # mint share link
    share = admin_session.post(f"{BASE_URL}/api/cra/exec-overview-link", json={}, timeout=30)
    assert share.status_code in (200, 201), f"share mint failed: {share.status_code} {share.text[:200]}"
    sj = share.json()
    token = sj.get("raw_token") or sj.get("token") or (sj.get("url", "").rstrip("/").split("/")[-1] if sj.get("url") else None)
    assert token, f"no token in share response: {sj}"

    # public (no auth) request
    pub = requests.get(f"{BASE_URL}/api/cra-public/exec-overview/{token}", timeout=30)
    assert pub.status_code == 200, f"public failed: {pub.status_code} {pub.text[:200]}"
    pj = pub.json()
    assert "risk" in pj, "risk hero missing"
    risk = pj["risk"]
    assert "risk_index" in risk
    assert "top_risks" in risk
    # snapshot_delta and previous_snapshot may be present
    assert "previous_snapshot" in pj or "snapshot_delta" in pj, "snapshot movement fields missing"

    # invalid token
    bad = requests.get(f"{BASE_URL}/api/cra-public/exec-overview/invalid-token-xyz", timeout=30)
    assert bad.status_code in (400, 401, 403, 404), f"invalid token accepted: {bad.status_code}"

    # cleanup: revoke share + delete snapshot (best effort)
    try:
        admin_session.post(f"{BASE_URL}/api/cra/exec-overview-link/revoke", timeout=15)
    except Exception:
        pass
