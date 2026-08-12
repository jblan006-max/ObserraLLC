"""Iteration 151 — EU CRA Governance: Control Dashboard, deadline chip, digest
settings/optin/send-now, auditor access log round-trip. Uses cookie-auth.
"""
import os
import time
import uuid
import requests
import pytest

def _load_frontend_env_url():
    try:
        with open("/app/frontend/.env") as f:
            for line in f:
                if line.startswith("REACT_APP_BACKEND_URL="):
                    return line.split("=", 1)[1].strip()
    except Exception:
        return None
    return None

BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or _load_frontend_env_url()).rstrip("/")
ADMIN_EMAIL = "jblan2026@gmail.com"
ADMIN_PASSWORD = "Obserra2026!"


@pytest.fixture(scope="module")
def admin_client():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=30)
    assert r.status_code == 200, f"admin login failed: {r.status_code} {r.text}"
    return s


@pytest.fixture(scope="module")
def fresh_nonadmin_client():
    s = requests.Session()
    email = f"nonadmin_iter151_{uuid.uuid4().hex[:8]}@example.com"
    r = s.post(f"{BASE_URL}/api/auth/register", json={
        "email": email, "password": "SafePass!2026-longer", "name": "Iter151 NonAdmin",
        "org_name": f"Iter151 Org {uuid.uuid4().hex[:6]}",
    }, timeout=30)
    assert r.status_code == 200, f"register failed: {r.status_code} {r.text}"
    return s, email


# ---- /cra/controls ------------------------------------------------------

def test_controls_dashboard_shape(admin_client):
    r = admin_client.get(f"{BASE_URL}/api/cra/controls", timeout=30)
    assert r.status_code == 200, r.text
    d = r.json()
    assert "overall" in d and "controls" in d
    o = d["overall"]
    for k in ("percentage", "requirements_total", "implemented", "partial", "gaps",
              "not_started", "high_risk", "products_assessed", "products_total"):
        assert k in o, f"missing overall.{k}"
    assert 0 <= o["percentage"] <= 100
    assert o["requirements_total"] == len(d["controls"])
    assert o["requirements_total"] >= 18
    valid_status = {"Implemented", "Partial", "Gap", "Not Started"}
    valid_risk = {"Low", "Medium", "High", "Unknown"}
    for c in d["controls"]:
        for k in ("requirement_id", "domain", "title", "legal_refs", "assessed",
                  "conforming", "partial", "nonconforming", "compliance_rate", "status", "risk"):
            assert k in c, f"missing control.{k}"
        assert c["status"] in valid_status
        assert c["risk"] in valid_risk
        if c["assessed"] == 0:
            assert c["compliance_rate"] is None
            assert c["status"] == "Not Started"
        else:
            assert 0 <= c["compliance_rate"] <= 100


# ---- /cra/dashboard next_deadline --------------------------------------

def test_dashboard_next_deadline(admin_client):
    r = admin_client.get(f"{BASE_URL}/api/cra/dashboard", timeout=30)
    assert r.status_code == 200, r.text
    d = r.json()
    nd = d.get("next_deadline")
    assert nd is not None, "next_deadline missing"
    for k in ("date", "label", "days_remaining"):
        assert k in nd, f"missing next_deadline.{k}"
    assert nd["date"] in {"2026-06-11", "2026-09-11", "2027-12-11"}
    assert isinstance(nd["days_remaining"], int)


# ---- /cra/insight headline includes deadline -------------------------

def test_insight_headline_countdown(admin_client):
    r = admin_client.get(f"{BASE_URL}/api/cra/insight", timeout=90)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d.get("next_deadline") is not None
    headline = (d.get("headline") or "").lower()
    # Should reference either the days-remaining or the deadline label/date.
    assert any(w in headline for w in ("day", "days", "2026", "2027", "deadline")), f"headline missing countdown: {headline!r}"


# ---- /cra/digest/settings + optin + send-now (admin) ------------------

def test_digest_settings_get_shape(admin_client):
    r = admin_client.get(f"{BASE_URL}/api/cra/digest/settings", timeout=15)
    assert r.status_code == 200, r.text
    d = r.json()
    assert "schedule" in d and "optin" in d and "is_admin" in d
    assert d["is_admin"] is True
    sch = d["schedule"]
    assert set(("enabled", "day_of_week", "hour_utc")).issubset(sch.keys())
    assert 0 <= int(sch["day_of_week"]) <= 6
    assert 0 <= int(sch["hour_utc"]) <= 23


def test_digest_settings_put_admin_persists(admin_client):
    payload = {"enabled": True, "day_of_week": 3, "hour_utc": 14}
    r = admin_client.put(f"{BASE_URL}/api/cra/digest/settings", json=payload, timeout=15)
    assert r.status_code == 200, r.text
    # Verify via GET
    r2 = admin_client.get(f"{BASE_URL}/api/cra/digest/settings", timeout=15)
    sch = r2.json()["schedule"]
    assert sch["day_of_week"] == 3 and sch["hour_utc"] == 14 and sch["enabled"] is True


def test_digest_optin_toggle(admin_client):
    r = admin_client.put(f"{BASE_URL}/api/cra/digest/optin", json={"optin": False}, timeout=15)
    assert r.status_code == 200 and r.json()["optin"] is False
    r2 = admin_client.get(f"{BASE_URL}/api/cra/digest/settings", timeout=15)
    assert r2.json()["optin"] is False
    # restore
    r3 = admin_client.put(f"{BASE_URL}/api/cra/digest/optin", json={"optin": True}, timeout=15)
    assert r3.status_code == 200 and r3.json()["optin"] is True


def test_digest_send_now_admin_with_products(admin_client):
    # admin org already has CRA products from prior seed
    r = admin_client.post(f"{BASE_URL}/api/cra/digest/send-now", timeout=90)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d.get("ok") is True
    assert d.get("sent_to", "").lower() == ADMIN_EMAIL.lower()


# ---- Non-admin negatives -----------------------------------------------

def test_digest_settings_put_nonadmin_forbidden(fresh_nonadmin_client):
    s, _ = fresh_nonadmin_client
    r = s.put(f"{BASE_URL}/api/cra/digest/settings",
              json={"enabled": True, "day_of_week": 1, "hour_utc": 9}, timeout=15)
    assert r.status_code == 403, f"expected 403, got {r.status_code} {r.text}"


def test_send_now_no_products_returns_400(fresh_nonadmin_client):
    s, _ = fresh_nonadmin_client
    r = s.post(f"{BASE_URL}/api/cra/digest/send-now", timeout=30)
    assert r.status_code == 400, f"expected 400, got {r.status_code} {r.text}"


# ---- Auditor access-log round-trip -------------------------------------

def test_auditor_access_log_roundtrip(admin_client):
    products = admin_client.get(f"{BASE_URL}/api/cra/products", timeout=15).json()
    assert products, "no CRA products present for admin org"
    ref = products[0]["ref"]
    before_count = int(products[0].get("verification_view_count", 0) or 0)

    # mint auditor link
    lr = admin_client.post(f"{BASE_URL}/api/cra/products/{ref}/verification-link", timeout=30)
    assert lr.status_code == 200, lr.text
    token = lr.json()["token"]

    # open public verify (no auth, use a fresh session)
    anon = requests.Session()
    pv = anon.get(f"{BASE_URL}/api/cra-public/verify/{token}", timeout=30)
    assert pv.status_code == 200, pv.text

    # give MongoDB a beat to flush the write
    time.sleep(0.5)

    products2 = admin_client.get(f"{BASE_URL}/api/cra/products", timeout=15).json()
    p2 = next((p for p in products2 if p["ref"] == ref), None)
    assert p2 is not None
    assert p2.get("last_verification_view_at"), "last_verification_view_at missing after public verify"
    after_count = int(p2.get("verification_view_count", 0) or 0)
    assert after_count == before_count + 1, f"count did not increment: {before_count} -> {after_count}"
