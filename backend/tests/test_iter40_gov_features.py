"""Iteration 40 — Verify governance features:
- Feature 2: /api/financial/nist-coverage returns 16 controls with basis+raise
- Feature 3: /api/reports/board-pack.pdf generation + /api/reports/board-pack/history
- Feature 4: /cron/weekly-drift-digest returns 200 with valid secret
"""
import os
import time
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://cyber-dashboard-48.preview.emergentagent.com").rstrip("/")
ADMIN_EMAIL = "jblan2026@gmail.com"
ADMIN_PASSWORD = "Obserra2026!"
CRON_SECRET = "029630dc6aeb167fc6c18f40799eae3ab523d91adad87112e647ee0e939b60f0"


@pytest.fixture(scope="module")
def auth_session():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login",
               json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=20)
    assert r.status_code == 200, f"Login failed: {r.status_code} {r.text[:200]}"
    return s


# Feature 2 - NIST Coverage
def test_nist_coverage_16_controls_with_basis_and_raise(auth_session):
    r = auth_session.get(f"{BASE_URL}/api/financial/nist-coverage", timeout=30)
    assert r.status_code == 200, r.text[:200]
    data = r.json()
    controls = data.get("controls", [])
    assert len(controls) == 16, f"Expected 16 controls, got {len(controls)}"
    for i, c in enumerate(controls):
        for k in ("c", "type", "fn", "vec", "fw", "cov", "basis", "raise"):
            assert k in c, f"control {i} missing '{k}': {c}"
        assert c["basis"].strip(), f"control {i} basis empty"
        assert c["raise"].strip(), f"control {i} raise empty"


# Feature 3 - Board pack history endpoint (list)
def test_board_pack_history_endpoint(auth_session):
    r = auth_session.get(f"{BASE_URL}/api/reports/board-pack/history", timeout=15)
    assert r.status_code == 200, r.text[:200]
    data = r.json()
    assert "history" in data
    assert isinstance(data["history"], list)


# Feature 3 - Board pack PDF generation & history addition
def test_board_pack_generation_and_history_row(auth_session):
    before = auth_session.get(f"{BASE_URL}/api/reports/board-pack/history", timeout=15).json().get("history", [])
    before_count = len(before)

    # Trigger generation
    r = auth_session.post(f"{BASE_URL}/api/reports/board-pack.pdf", timeout=120)
    # It may return the PDF synchronously or accept as background task
    assert r.status_code in (200, 201, 202), f"Generation failed: {r.status_code} {r.text[:200]}"

    # Poll history for up to 60s
    found_new = False
    for _ in range(20):
        time.sleep(3)
        h = auth_session.get(f"{BASE_URL}/api/reports/board-pack/history", timeout=15).json().get("history", [])
        if len(h) > before_count:
            found_new = True
            row = h[0]  # newest-first
            # basic shape
            assert isinstance(row, dict)
            break
    assert found_new, f"No new history row after generation (before={before_count})"


# Feature 4 - Cron weekly drift digest
def test_cron_weekly_drift_digest_ok():
    r = requests.post(f"{BASE_URL}/api/cron/weekly-drift-digest",
                      headers={"Authorization": f"Bearer {CRON_SECRET}"}, timeout=15)
    assert r.status_code == 200, f"{r.status_code} {r.text[:200]}"
    assert r.json().get("status") == "accepted"


def test_cron_weekly_drift_digest_unauthorized():
    r = requests.post(f"{BASE_URL}/api/cron/weekly-drift-digest", timeout=10)
    assert r.status_code == 401
