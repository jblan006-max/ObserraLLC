"""Iteration 16 — Settings polish: dropped-email feedback, logo size guard, branding reset."""
import os, base64, requests, pytest
from pathlib import Path

def _load_url():
    v = os.environ.get("REACT_APP_BACKEND_URL")
    if v: return v.rstrip("/")
    for line in Path("/app/frontend/.env").read_text().splitlines():
        if line.startswith("REACT_APP_BACKEND_URL="):
            return line.split("=", 1)[1].strip().rstrip("/")
    raise RuntimeError("REACT_APP_BACKEND_URL missing")

BASE_URL = _load_url()
ADMIN = {"email": "jblan2026@gmail.com", "password": "Obserra2026!"}


@pytest.fixture(scope="module")
def admin_session():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json=ADMIN, timeout=15)
    assert r.status_code == 200, r.text
    return s


# --- Recipients: dropped invalid ---
def test_recipients_returns_dropped_for_invalid(admin_session):
    payload = {"emails": ["good@example.com", "not-an-email", "ciso@example.com", "bad@@x"]}
    r = admin_session.put(f"{BASE_URL}/api/reports/recipients", json=payload, timeout=15)
    assert r.status_code == 200, r.text
    data = r.json()
    assert "dropped" in data and "extra" in data
    assert "good@example.com" in data["extra"]
    assert "ciso@example.com" in data["extra"]
    assert set(data["dropped"]) == {"not-an-email", "bad@@x"}


def test_recipients_all_valid_no_dropped(admin_session):
    payload = {"emails": ["a@example.com", "b@example.com"]}
    r = admin_session.put(f"{BASE_URL}/api/reports/recipients", json=payload, timeout=15)
    assert r.status_code == 200
    data = r.json()
    assert data["dropped"] == []
    assert set(data["extra"]) == {"a@example.com", "b@example.com"}


def test_recipients_get_persists(admin_session):
    admin_session.put(f"{BASE_URL}/api/reports/recipients", json={"emails": ["c@example.com"]}, timeout=15)
    r = admin_session.get(f"{BASE_URL}/api/reports/recipients", timeout=15)
    assert r.status_code == 200
    assert "c@example.com" in r.json()["extra"]
    # cleanup
    admin_session.put(f"{BASE_URL}/api/reports/recipients", json={"emails": []}, timeout=15)


# --- Branding: size guard + reset ---
def test_branding_logo_too_large_rejected(admin_session):
    huge = "A" * 2_100_000  # >2M base64 chars
    body = {"enabled": True, "company_name": "Acme", "logo": f"data:image/png;base64,{huge}"}
    r = admin_session.put(f"{BASE_URL}/api/reports/branding", json=body, timeout=15)
    assert r.status_code == 400
    assert "large" in r.text.lower()


def test_branding_save_then_reset(admin_session):
    # Save custom branding
    tiny_png = base64.b64encode(
        bytes.fromhex("89504E470D0A1A0A0000000D49484452000000010000000108060000001F15C4890000000A49444154789C6300010000000500010D0A2DB40000000049454E44AE426082")
    ).decode()
    r = admin_session.put(f"{BASE_URL}/api/reports/branding",
                          json={"enabled": True, "company_name": "Acme Corp", "logo": f"data:image/png;base64,{tiny_png}"},
                          timeout=15)
    assert r.status_code == 200
    d = r.json()
    assert d["enabled"] is True
    assert d["company_name"] == "Acme Corp"
    assert d["has_logo"] is True

    # Verify via GET
    r = admin_session.get(f"{BASE_URL}/api/reports/branding", timeout=15)
    d = r.json()
    assert d["enabled"] is True and d["has_logo"] is True and d["company_name"] == "Acme Corp"

    # Reset via remove_logo:true
    r = admin_session.put(f"{BASE_URL}/api/reports/branding",
                          json={"enabled": False, "company_name": "", "remove_logo": True}, timeout=15)
    assert r.status_code == 200
    d = r.json()
    assert d["enabled"] is False
    assert d["company_name"] == ""
    assert d["has_logo"] is False

    # Verify via GET
    r = admin_session.get(f"{BASE_URL}/api/reports/branding", timeout=15)
    d = r.json()
    assert d["enabled"] is False and d["company_name"] == "" and d["has_logo"] is False


def test_branding_non_admin_forbidden():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login",
               json={"email": "analyst@obserra.demo", "password": "Analyst2026!"}, timeout=15)
    assert r.status_code == 200
    r = s.put(f"{BASE_URL}/api/reports/branding", json={"enabled": False, "remove_logo": True}, timeout=15)
    assert r.status_code == 403
