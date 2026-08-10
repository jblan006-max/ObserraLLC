"""Iter114: Globe time range + watchtower + trusted_auditors + unusual_access_threshold."""
import os
import pytest
import requests
from dotenv import load_dotenv

load_dotenv("/app/frontend/.env")
BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
ADMIN_EMAIL = "jblan2026@gmail.com"
ADMIN_PW = "Obserra2026!"
GOV = "/api/agents/runtime/governance-settings"


def _reset(s):
    s.put(f"{BASE_URL}{GOV}",
          json={"trusted_countries": [], "trusted_ip_ranges": [],
                "trusted_auditors": [], "unusual_access_threshold": 1},
          timeout=30)


@pytest.fixture(scope="module")
def admin_session():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login",
               json={"email": ADMIN_EMAIL, "password": ADMIN_PW}, timeout=30)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text[:200]}"
    _reset(s)
    yield s
    _reset(s)


# ---------- Access-globe days param ----------

@pytest.mark.parametrize("days", [7, 30, 90])
def test_access_globe_days_valid(admin_session, days):
    r = admin_session.get(f"{BASE_URL}/api/agents/runtime/access-globe",
                          params={"days": days}, timeout=30)
    assert r.status_code == 200
    d = r.json()
    assert d.get("days") == days, f"expected days echo {days}, got {d.get('days')}"
    assert "points" in d and isinstance(d["points"], list)


def test_access_globe_no_days_alltime(admin_session):
    r = admin_session.get(f"{BASE_URL}/api/agents/runtime/access-globe", timeout=30)
    assert r.status_code == 200
    d = r.json()
    assert d.get("days") is None


def test_access_globe_invalid_days_falls_back(admin_session):
    r = admin_session.get(f"{BASE_URL}/api/agents/runtime/access-globe",
                          params={"days": 5}, timeout=30)
    assert r.status_code == 200
    assert r.json().get("days") is None


# ---------- Watchtower endpoint ----------

def test_watchtower_baseline_no_trust(admin_session):
    _reset(admin_session)
    r = admin_session.get(f"{BASE_URL}/api/agents/runtime/watchtower", timeout=30)
    assert r.status_code == 200
    d = r.json()
    assert d == {"count": 0, "has_trust": False}


def test_watchtower_with_trusted_country(admin_session):
    try:
        r = admin_session.put(f"{BASE_URL}{GOV}",
                              json={"trusted_countries": ["United States"]}, timeout=30)
        assert r.status_code == 200
        w = admin_session.get(f"{BASE_URL}/api/agents/runtime/watchtower", timeout=30)
        assert w.status_code == 200
        d = w.json()
        assert d.get("has_trust") is True
        assert isinstance(d.get("count"), int)
        assert d["count"] > 0, f"expected >0 suspicious in last 24h, got {d}"
    finally:
        _reset(admin_session)


# ---------- Governance settings: trusted_auditors + threshold ----------

def test_governance_get_has_new_fields(admin_session):
    _reset(admin_session)
    g = admin_session.get(f"{BASE_URL}{GOV}", timeout=30).json()
    assert "trusted_auditors" in g and isinstance(g["trusted_auditors"], list)
    assert "unusual_access_threshold" in g
    assert isinstance(g["unusual_access_threshold"], int)
    assert g["unusual_access_threshold"] >= 1


def test_trusted_auditors_lowercased_and_deduped(admin_session):
    try:
        payload = {"trusted_auditors": ["Alice@Corp.com", " alice@corp.com ", "auditor@bigfour.com"]}
        r = admin_session.put(f"{BASE_URL}{GOV}", json=payload, timeout=30)
        assert r.status_code == 200
        g = admin_session.get(f"{BASE_URL}{GOV}", timeout=30).json()
        ta = g["trusted_auditors"]
        assert set(ta) == {"alice@corp.com", "auditor@bigfour.com"}, f"got {ta}"
        assert len(ta) == 2
    finally:
        _reset(admin_session)


def test_unusual_threshold_stored_and_clamped(admin_session):
    try:
        r = admin_session.put(f"{BASE_URL}{GOV}",
                              json={"unusual_access_threshold": 5}, timeout=30)
        assert r.status_code == 200
        g = admin_session.get(f"{BASE_URL}{GOV}", timeout=30).json()
        assert g["unusual_access_threshold"] == 5
        # clamp low
        admin_session.put(f"{BASE_URL}{GOV}", json={"unusual_access_threshold": 0}, timeout=30)
        g = admin_session.get(f"{BASE_URL}{GOV}", timeout=30).json()
        assert g["unusual_access_threshold"] == 1
        # clamp high
        admin_session.put(f"{BASE_URL}{GOV}", json={"unusual_access_threshold": 999999}, timeout=30)
        g = admin_session.get(f"{BASE_URL}{GOV}", timeout=30).json()
        assert g["unusual_access_threshold"] == 1000
    finally:
        _reset(admin_session)


# ---------- Auditor allow-list effect on access-globe ----------

def test_auditor_allowlist_excludes_from_suspicious(admin_session):
    try:
        # First find an auditor 'who' outside the US
        admin_session.put(f"{BASE_URL}{GOV}",
                          json={"trusted_countries": ["United States"], "trusted_auditors": []},
                          timeout=30)
        d = admin_session.get(f"{BASE_URL}/api/agents/runtime/access-globe", timeout=30).json()
        sus_whos = sorted({p.get("who") for p in d["points"]
                           if p.get("suspicious") and p.get("who")})
        assert sus_whos, "no suspicious pins with who found in seeded data"
        target = sus_whos[0]
        # Add target to trusted_auditors
        r = admin_session.put(f"{BASE_URL}{GOV}",
                              json={"trusted_countries": ["United States"],
                                    "trusted_auditors": [target]}, timeout=30)
        assert r.status_code == 200
        d2 = admin_session.get(f"{BASE_URL}/api/agents/runtime/access-globe", timeout=30).json()
        # target's pins must NOT be suspicious
        target_lc = target.strip().lower()
        target_pins = [p for p in d2["points"] if (p.get("who") or "").strip().lower() == target_lc]
        assert target_pins, "expected pins for target auditor"
        assert all(p.get("suspicious") is False for p in target_pins), \
            f"target auditor pins still suspicious: {target_pins[:2]}"
        # Other outside-US suspicious pins should remain suspicious
        others_sus = [p for p in d2["points"]
                      if p.get("suspicious") and (p.get("who") or "").strip().lower() != target_lc]
        # only assert if there were other suspicious whos originally
        if len(sus_whos) > 1:
            assert len(others_sus) > 0, "expected other suspicious pins to remain"
    finally:
        _reset(admin_session)


# ---------- Regressions ----------

def test_access_globe_has_drilldown_fields(admin_session):
    r = admin_session.get(f"{BASE_URL}/api/agents/runtime/access-globe", timeout=30)
    d = r.json()
    assert "suspicious" in d and "has_trust" in d
    if d["points"]:
        p = d["points"][0]
        for k in ("who", "device", "ip", "at", "source", "title", "token", "suspicious"):
            assert k in p, f"missing drilldown key {k}"


def test_snapshot_status_and_retire_gate(admin_session):
    r = admin_session.get(f"{BASE_URL}/api/agents/runtime/snapshot-status", timeout=30)
    assert r.status_code == 200
    n = r.json()["snapshot_incidents"]
    rr = admin_session.post(f"{BASE_URL}/api/agents/runtime/retire-snapshots", timeout=30)
    assert rr.status_code == 409
    r2 = admin_session.get(f"{BASE_URL}/api/agents/runtime/snapshot-status", timeout=30).json()
    assert r2["snapshot_incidents"] == n


def test_trusted_countries_ips_still_validate(admin_session):
    try:
        r = admin_session.put(f"{BASE_URL}{GOV}",
                              json={"trusted_countries": ["Australia", "Australia", ""],
                                    "trusted_ip_ranges": ["10.0.0.0/8", "10.0.0.0/8", "bad"]},
                              timeout=30)
        assert r.status_code == 200
        g = admin_session.get(f"{BASE_URL}{GOV}", timeout=30).json()
        assert g["trusted_countries"].count("Australia") == 1
        assert g["trusted_ip_ranges"].count("10.0.0.0/8") == 1
        assert "bad" not in g["trusted_ip_ranges"]
    finally:
        _reset(admin_session)


def test_weekly_drift_digest_cron(admin_session):
    secret = ""
    try:
        with open("/app/backend/.env") as f:
            for line in f:
                if line.startswith("WEBHOOK_CRON_SECRET"):
                    secret = line.split("=", 1)[1].strip().strip('"').strip("'")
                    break
    except Exception:
        pass
    assert secret
    r = requests.post(f"{BASE_URL}/api/cron/weekly-drift-digest",
                      headers={"Authorization": f"Bearer {secret}"}, timeout=90)
    assert 200 <= r.status_code < 300
