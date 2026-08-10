"""Iter113: Suspicious globe filter, board map PDF regression, snapshot retire gate, regressions."""
import os
import io
import time
import pytest
import requests
from dotenv import load_dotenv

load_dotenv("/app/frontend/.env")
BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
ADMIN_EMAIL = "jblan2026@gmail.com"
ADMIN_PW = "Obserra2026!"


@pytest.fixture(scope="module")
def admin_session():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login",
               json={"email": ADMIN_EMAIL, "password": ADMIN_PW}, timeout=30)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text[:200]}"
    yield s
    # baseline reset
    try:
        s.put(f"{BASE_URL}/api/agents/runtime/governance-settings",
              json={"trusted_countries": [], "trusted_ip_ranges": []}, timeout=30)
    except Exception:
        pass


# --- Suspicious/has_trust on access-globe ---

def test_access_globe_baseline_no_trust(admin_session):
    # ensure baseline empty
    admin_session.put(f"{BASE_URL}/api/agents/runtime/governance-settings",
                      json={"trusted_countries": [], "trusted_ip_ranges": []}, timeout=30)
    r = admin_session.get(f"{BASE_URL}/api/agents/runtime/access-globe", timeout=30)
    assert r.status_code == 200
    d = r.json()
    assert "suspicious" in d and "has_trust" in d
    assert d["has_trust"] is False
    assert d["suspicious"] == 0
    pts = d.get("points", [])
    assert len(pts) > 0
    assert all("suspicious" in p for p in pts)
    assert all(p["suspicious"] is False for p in pts)


def test_access_globe_with_trusted_country_flags_suspicious(admin_session):
    r = admin_session.put(f"{BASE_URL}/api/agents/runtime/governance-settings",
                          json={"trusted_countries": ["United States"], "trusted_ip_ranges": []},
                          timeout=30)
    assert r.status_code == 200
    g = admin_session.get(f"{BASE_URL}/api/agents/runtime/access-globe", timeout=30)
    assert g.status_code == 200
    d = g.json()
    assert d["has_trust"] is True
    assert d["suspicious"] > 0
    # at least some pins flagged suspicious
    sus_pts = [p for p in d["points"] if p.get("suspicious")]
    assert len(sus_pts) > 0
    # reset
    admin_session.put(f"{BASE_URL}/api/agents/runtime/governance-settings",
                      json={"trusted_countries": [], "trusted_ip_ranges": []}, timeout=30)


# --- Board access map PDF still valid ---

def test_access_globe_pdf(admin_session):
    r = admin_session.get(f"{BASE_URL}/api/agents/runtime/access-globe.pdf", timeout=90)
    assert r.status_code == 200
    assert r.headers.get("content-type", "").startswith("application/pdf")
    body = r.content
    assert body[:4] == b"%PDF"
    # count pages heuristically
    n_pages = body.count(b"/Type /Page") + body.count(b"/Type/Page")
    assert n_pages >= 3, f"expected >=3 pages got {n_pages}"


# --- Snapshot status + retire gate ---

def test_snapshot_status(admin_session):
    r = admin_session.get(f"{BASE_URL}/api/agents/runtime/snapshot-status", timeout=30)
    assert r.status_code == 200
    d = r.json()
    assert "snapshot_incidents" in d
    assert isinstance(d["snapshot_incidents"], int)
    assert d.get("live_source_connected") is False
    assert d.get("live_source", "") == ""


def test_retire_snapshots_gated_409(admin_session):
    # capture count before
    s_before = admin_session.get(f"{BASE_URL}/api/agents/runtime/snapshot-status", timeout=30).json()
    n_before = s_before["snapshot_incidents"]

    r = admin_session.post(f"{BASE_URL}/api/agents/runtime/retire-snapshots", timeout=30)
    assert r.status_code == 409, f"expected 409 got {r.status_code} {r.text[:200]}"
    # clear message
    txt = r.text.lower()
    assert "live" in txt and ("connect" in txt or "source" in txt)

    # ensure nothing deleted
    s_after = admin_session.get(f"{BASE_URL}/api/agents/runtime/snapshot-status", timeout=30).json()
    assert s_after["snapshot_incidents"] == n_before


# --- governance PUT/GET regression: validate & dedupe ---

def test_governance_settings_dedupe_and_validate(admin_session):
    payload = {
        "trusted_countries": ["United States", "United States", "  Australia  ", ""],
        "trusted_ip_ranges": ["203.0.113.0/24", "203.0.113.0/24", "notanip", "198.51.100.7"],
    }
    r = admin_session.put(f"{BASE_URL}/api/agents/runtime/governance-settings",
                          json=payload, timeout=30)
    assert r.status_code == 200
    g = admin_session.get(f"{BASE_URL}/api/agents/runtime/governance-settings", timeout=30).json()
    assert "United States" in g["trusted_countries"]
    assert g["trusted_countries"].count("United States") == 1
    assert "Australia" in g["trusted_countries"]
    assert "203.0.113.0/24" in g["trusted_ip_ranges"]
    assert g["trusted_ip_ranges"].count("203.0.113.0/24") == 1
    assert "notanip" not in g["trusted_ip_ranges"]
    # reset
    admin_session.put(f"{BASE_URL}/api/agents/runtime/governance-settings",
                      json={"trusted_countries": [], "trusted_ip_ranges": []}, timeout=30)


# --- Regression: existing endpoints respond ---

@pytest.mark.parametrize("path", [
    "/api/agents/runtime/shared-cards",
    "/api/agents/runtime/access-log.csv",
    "/api/agents/runtime/board-evidence-digest",
])
def test_regression_endpoints_respond(admin_session, path):
    r = admin_session.get(f"{BASE_URL}{path}", timeout=60)
    assert r.status_code < 500, f"{path} -> {r.status_code} {r.text[:200]}"


def test_weekly_drift_digest_cron(admin_session):
    secret = os.environ.get("WEBHOOK_CRON_SECRET", "")
    if not secret:
        # try reading backend env
        try:
            with open("/app/backend/.env") as f:
                for line in f:
                    if line.startswith("WEBHOOK_CRON_SECRET"):
                        secret = line.split("=", 1)[1].strip().strip('"').strip("'")
                        break
        except Exception:
            pass
    assert secret, "WEBHOOK_CRON_SECRET missing"
    r = requests.post(f"{BASE_URL}/api/cron/weekly-drift-digest",
                      headers={"Authorization": f"Bearer {secret}"}, timeout=90)
    assert 200 <= r.status_code < 300, f"{r.status_code} {r.text[:200]}"
