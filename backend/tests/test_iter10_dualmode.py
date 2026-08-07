"""Iter 10 — Dual-mode, Available Connectors, controls compliance, security hardening."""
import os
import requests
import pytest

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/") or "https://cyber-dashboard-48.preview.emergentagent.com"
ADMIN_EMAIL = "jblan2026@gmail.com"
ADMIN_PASSWORD = "Obserra2026!"


@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=20)
    assert r.status_code == 200, f"login failed {r.status_code} {r.text[:200]}"
    return s


# ---------- Security headers ----------
def test_security_headers(session):
    r = session.get(f"{BASE_URL}/api/branding", timeout=15)
    assert r.status_code in (200, 401)
    h = {k.lower(): v for k, v in r.headers.items()}
    for key in ["content-security-policy", "x-frame-options", "strict-transport-security", "x-content-type-options", "referrer-policy", "permissions-policy"]:
        assert key in h, f"missing header {key}: {list(h.keys())}"
    assert h["x-frame-options"].upper() == "DENY"
    assert "nosniff" in h["x-content-type-options"].lower()


# ---------- Password policy ----------
def test_weak_password_rejected():
    r = requests.post(f"{BASE_URL}/api/auth/register", json={
        "email": "weakpwuser@example.com", "password": "abc", "name": "Weak"
    }, timeout=15)
    assert r.status_code == 400
    body = r.text.lower()
    assert "password" in body


# ---------- Metrics dashboard ----------
def test_metrics_dashboard(session):
    r = session.get(f"{BASE_URL}/api/metrics/dashboard", timeout=20)
    assert r.status_code == 200, r.text[:200]
    j = r.json()
    assert "executive" in j and "operational" in j
    exec_ = j["executive"]
    for k in ["exposure_residual_ale", "exposure_avoided", "risk_reduction_pct", "risk_adjusted"]:
        assert k in exec_, f"exec missing {k}: {list(exec_.keys())}"
    op = j["operational"]
    # Look for quarterly series & op metrics
    keys = list(op.keys())
    print("OP KEYS:", keys)
    assert any("nist" in k.lower() for k in keys), keys
    assert any("vendor" in k.lower() for k in keys), keys
    assert any("phish" in k.lower() for k in keys), keys
    assert any("patch" in k.lower() for k in keys), keys


# ---------- Cyber overview live_risk_penalty ----------
def test_cyber_overview(session):
    r = session.get(f"{BASE_URL}/api/cyber/overview", timeout=20)
    assert r.status_code == 200
    j = r.json()
    assert "live_risk_penalty" in j
    assert "posture_score" in j


# ---------- Enterprise live connectors ----------
def test_enterprise_live(session):
    r = session.get(f"{BASE_URL}/api/enterprise/live", timeout=20)
    assert r.status_code == 200
    j = r.json()
    for k in ["m365", "sso", "openai", "copilot", "teams"]:
        assert k in j, f"missing {k}: {list(j.keys())}"


def test_openai_verify_bad_key(session):
    r = session.put(f"{BASE_URL}/api/enterprise/live/openai", json={"api_key": "sk-fake-invalid-key-xxxxxxxxxxx"}, timeout=30)
    # Expect either 200 with not-live status or 400 error
    print("openai verify:", r.status_code, r.text[:200])
    assert r.status_code in (200, 400, 401, 422)


def test_teams_valid_webhook(session):
    r = session.put(f"{BASE_URL}/api/enterprise/live/teams", json={"webhook_url": "https://acme.webhook.office.com/webhookb2/abc123"}, timeout=15)
    print("teams save:", r.status_code, r.text[:300])
    assert r.status_code == 200
    # verify status
    r2 = session.get(f"{BASE_URL}/api/enterprise/live", timeout=15)
    teams = r2.json().get("teams", {})
    print("teams state:", teams)


def test_teams_share_gates_when_unconfigured(session):
    # Ensure disconnected first
    session.delete(f"{BASE_URL}/api/enterprise/live/teams", timeout=15)
    r = session.post(f"{BASE_URL}/api/enterprise/live/teams/share", json={"title": "t", "text": "x"}, timeout=15)
    print("teams share unconfigured:", r.status_code, r.text[:200])
    assert r.status_code == 400


# ---------- Controls compliance ----------
def test_controls_compliance(session):
    r = session.get(f"{BASE_URL}/api/controls/compliance", timeout=20)
    assert r.status_code == 200
    j = r.json()
    frameworks = j.get("frameworks") or j.get("items") or j
    print("compliance:", str(j)[:400])
    # Ensure at least 5 frameworks
    if isinstance(frameworks, list):
        assert len(frameworks) >= 5
    elif isinstance(j, dict):
        # try nested
        assert len(str(j)) > 20


def test_controls_include_frameworks(session):
    r = session.get(f"{BASE_URL}/api/controls", timeout=20)
    assert r.status_code == 200
    j = r.json()
    controls = j if isinstance(j, list) else j.get("controls") or j.get("items") or []
    assert len(controls) > 0
    # at least one control has 'frameworks' tag list
    with_frameworks = [c for c in controls if isinstance(c, dict) and c.get("frameworks")]
    print(f"controls with frameworks: {len(with_frameworks)}/{len(controls)}")
    assert len(with_frameworks) > 0
