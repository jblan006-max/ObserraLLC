"""Backend tests for Control Intelligence iteration 123: cadence, auditor-link, public auditor, per-owner nudge preview."""
import os
import requests
import pytest

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") if os.environ.get("REACT_APP_BACKEND_URL") else "https://cyber-dashboard-48.preview.emergentagent.com"
EMAIL = "jblan2026@gmail.com"
PASSWORD = "Obserra2026!"


@pytest.fixture(scope="module")
def sess():
    s = requests.Session()
    r = s.post(f"{BASE}/api/auth/login", json={"email": EMAIL, "password": PASSWORD})
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text[:200]}"
    yield s
    # cleanup
    s.put(f"{BASE}/api/control-intelligence/settings", json={
        "recipients": [], "send_day": 1, "enabled": False, "cadence": "monthly"
    })


def test_cadence_quarterly_roundtrip(sess):
    r = sess.put(f"{BASE}/api/control-intelligence/settings",
                 json={"cadence": "quarterly", "enabled": True, "send_day": 15, "recipients": []})
    assert r.status_code == 200, r.text
    data = r.json()
    assert data.get("cadence") == "quarterly"
    g = sess.get(f"{BASE}/api/control-intelligence/settings")
    assert g.status_code == 200
    assert g.json().get("cadence") == "quarterly"


def test_cadence_invalid_coerces_monthly(sess):
    r = sess.put(f"{BASE}/api/control-intelligence/settings",
                 json={"cadence": "weekly", "enabled": False, "send_day": 1, "recipients": []})
    assert r.status_code == 200, r.text
    assert r.json().get("cadence") == "monthly"


def test_auditor_link_generate(sess):
    r = sess.post(f"{BASE}/api/control-intelligence/auditor-link", json={})
    assert r.status_code in (200, 201), r.text
    data = r.json()
    assert "url" in data or "token" in data
    token = data.get("token") or (data.get("url", "").rsplit("/", 1)[-1])
    assert token
    # expiry ~90 days
    assert "expires_at" in data or "expiry" in data or "expires" in data
    pytest.auditor_token = token
    pytest.auditor_data = data


def test_public_auditor_valid(sess):
    token = getattr(pytest, "auditor_token", None)
    assert token, "no token from prior test"
    r = requests.get(f"{BASE}/api/control-intelligence/public/auditor-link/{token}")
    assert r.status_code == 200, r.text
    data = r.json()
    for k in ("org_name", "health", "frameworks", "weak_controls"):
        assert k in data, f"missing {k} in {list(data.keys())}"


def test_public_auditor_invalid():
    r = requests.get(f"{BASE}/api/control-intelligence/public/auditor-link/deadbeef")
    assert r.status_code == 404


def test_nudge_preview_per_owner(sess):
    r = sess.get(f"{BASE}/api/control-intelligence/owner-nudges/preview?demo=true")
    assert r.status_code == 200, r.text
    data = r.json()
    groups = data.get("groups") or []
    assert len(groups) > 0
    assert "personalized" in data, f"top-level personalized missing: {list(data.keys())}"
    for g in groups:
        assert "email" in g, f"group missing email field: {g}"
        assert "owner" in g and "controls" in g
