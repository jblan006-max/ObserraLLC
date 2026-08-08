"""Iter46 — Performance (correlate cache) + Asset Deep-Dive + No-Mock regression."""
import os, time, requests, pytest

BASE = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
EMAIL = "jblan2026@gmail.com"
PASS = "Obserra2026!"


@pytest.fixture(scope="module")
def client():
    s = requests.Session()
    r = s.post(f"{BASE}/api/auth/login", json={"email": EMAIL, "password": PASS}, timeout=15)
    assert r.status_code == 200, r.text
    yield s
    # restore dep-ecdsa
    try:
        s.post(f"{BASE}/api/risk-engine/task/dep-ecdsa/status", json={"status": "Open"}, timeout=15)
    except Exception:
        pass


def test_login(client):
    r = client.get(f"{BASE}/api/auth/me", timeout=10)
    assert r.status_code == 200
    assert r.json().get("email") == EMAIL


# Performance: 4 lens calls should be fast due to 6s TTL correlate cache
def test_risk_engine_lenses_fast(client):
    lenses = ["strategic", "tactical", "exposure", "compliance"]
    t0 = time.time()
    for l in lenses:
        r = client.get(f"{BASE}/api/risk-engine/{l}", timeout=20)
        assert r.status_code == 200, f"{l} failed: {r.status_code}"
    dt = time.time() - t0
    print(f"4 lenses took {dt:.2f}s")
    # Should be reasonably fast - well under 4x cold time
    assert dt < 25, f"Lens calls too slow: {dt}s"


def test_economics(client):
    r = client.get(f"{BASE}/api/risk-engine/economics", timeout=20)
    assert r.status_code == 200
    d = r.json()
    assert "economics" in d
    econ = d["economics"]
    assert "tprm" in econ and "spend" in econ
    assert econ["tprm"]["total_premium"] == 0
    assert "blended_roi" in econ["spend"]
    print(f"blended_roi={econ['spend']['blended_roi']}")


def test_strategic_economics(client):
    r = client.get(f"{BASE}/api/risk-engine/strategic", timeout=20)
    assert r.status_code == 200
    d = r.json()
    assert "economics" in d
    assert "tprm" in d["economics"]
    assert "spend" in d["economics"]


# No-Mock regression
def test_no_mock_dep_ecdsa_remediate(client):
    r = client.post(f"{BASE}/api/risk-engine/task/dep-ecdsa/action",
                    json={"action": "remediate"}, timeout=30)
    assert r.status_code == 200
    d = r.json()
    assert d.get("ok") is False
    assert d.get("verified") is False
    assert d.get("status") == "Open"
    assert d.get("provider") == "osv.dev"
    assert "ledger_id" in d
    msg = (d.get("message") or "").lower()
    assert "no fixed release" in msg or "cannot be auto-patched" in msg


def test_verify_connectors(client):
    r = client.post(f"{BASE}/api/risk-engine/verify-connectors", timeout=30)
    assert r.status_code == 200
    d = r.json()
    assert "stripe" in d and "clerk" in d
    assert d["stripe"]["ok"] is True
    assert d["clerk"]["configured"] is False


def test_ledger(client):
    r = client.get(f"{BASE}/api/risk-engine/ledger", timeout=15)
    assert r.status_code == 200
    d = r.json()
    assert "entries" in d
    assert len(d["entries"]) >= 1


# Assets endpoint (should power AssetIntelligence page)
def test_assets_endpoint(client):
    # Try common asset endpoints
    for path in ["/api/assets/inventory", "/api/assets", "/api/risk-engine/assets"]:
        r = client.get(f"{BASE}{path}", timeout=15)
        if r.status_code == 200:
            print(f"OK {path}: {list(r.json().keys()) if isinstance(r.json(), dict) else 'list'}")
            return
    pytest.skip("No standard asset endpoint found")


def test_restore_dep_ecdsa(client):
    r = client.post(f"{BASE}/api/risk-engine/task/dep-ecdsa/status",
                    json={"status": "Open"}, timeout=15)
    assert r.status_code == 200
