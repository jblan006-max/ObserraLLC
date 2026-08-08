"""Iter45 — No-Mock Remediation, Ledger, Verify-Connectors, Economics (TPRM + Spend).
Auth is cookie-based (login sets 'token' cookie).
"""
import os, time, pytest, requests

def _load_url():
    v = os.environ.get('REACT_APP_BACKEND_URL')
    if v:
        return v.rstrip('/')
    # Load from frontend .env
    p = '/app/frontend/.env'
    if os.path.exists(p):
        for line in open(p):
            if line.startswith('REACT_APP_BACKEND_URL='):
                return line.split('=', 1)[1].strip().rstrip('/')
    raise RuntimeError("REACT_APP_BACKEND_URL not set")

BASE_URL = _load_url()
EMAIL = "jblan2026@gmail.com"
PASS = "Obserra2026!"


@pytest.fixture(scope="session")
def client():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login",
               json={"email": EMAIL, "password": PASS}, timeout=30)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text[:200]}"
    yield s
    # teardown: restore dep-ecdsa Open
    try:
        s.post(f"{BASE_URL}/api/risk-engine/task/dep-ecdsa/status",
               json={"status": "Open"}, timeout=30)
    except Exception:
        pass


# ---- Economics (TPRM + Spend) ----
class TestEconomics:
    def test_economics_endpoint(self, client):
        r = client.get(f"{BASE_URL}/api/risk-engine/economics", timeout=30)
        assert r.status_code == 200
        d = r.json()
        assert "economics" in d
        e = d["economics"]
        assert "tprm" in e and "spend" in e
        # TPRM shape
        t = e["tprm"]
        for k in ("vendor_count", "total_premium", "top_vendors", "note"):
            assert k in t, f"tprm missing {k}"
        # live_only: 0 vendors, premium 0, honest note
        assert t["vendor_count"] == 0
        assert t["total_premium"] == 0
        assert "no third-party" in t["note"].lower() or "0" in t["note"]
        # Spend shape
        sp = e["spend"]
        for k in ("modelled_investment", "ale_reducible", "blended_roi", "by_area", "best_area", "note"):
            assert k in sp, f"spend missing {k}"
        assert isinstance(sp["blended_roi"], (int, float))
        assert sp["blended_roi"] > 0, f"blended_roi should be positive; got {sp['blended_roi']}"

    def test_strategic_includes_economics(self, client):
        r = client.get(f"{BASE_URL}/api/risk-engine/strategic", timeout=30)
        assert r.status_code == 200
        d = r.json()
        assert "economics" in d
        assert "tprm" in d["economics"] and "spend" in d["economics"]
        assert d["economics"]["tprm"]["vendor_count"] == 0
        assert d["economics"]["spend"]["blended_roi"] > 0


# ---- No-Mock remediation truth ----
class TestNoMockRemediation:
    def test_remediate_dep_ecdsa_honest_failure(self, client):
        # Ensure Open first
        client.post(f"{BASE_URL}/api/risk-engine/task/dep-ecdsa/status",
                    json={"status": "Open"}, timeout=30)
        before = client.get(f"{BASE_URL}/api/risk-engine/strategic", timeout=30).json()["portfolio"]["residual_ale"]

        r = client.post(f"{BASE_URL}/api/risk-engine/task/dep-ecdsa/action",
                        json={"action": "remediate"}, timeout=60)
        assert r.status_code == 200
        d = r.json()
        assert d.get("ok") is False, f"expected ok=false, got {d}"
        assert d.get("verified") is False
        assert d.get("status") == "Open"
        assert d.get("provider") == "osv.dev"
        msg = (d.get("message") or "").lower()
        assert "no fixed release" in msg or "cannot be auto-patched" in msg or "cannot auto-patch" in msg
        assert "cve-2024-23342" in msg or "cve" in msg
        assert d.get("ledger_id"), "ledger_id must be present"

        after = client.get(f"{BASE_URL}/api/risk-engine/strategic", timeout=30).json()["portfolio"]["residual_ale"]
        # ALE unchanged (no fake reduction)
        assert after == before, f"ALE should not change on no-patch; before={before} after={after}"

    def test_isolate_honest_failure(self, client):
        r = client.post(f"{BASE_URL}/api/risk-engine/task/dep-ecdsa/action",
                        json={"action": "isolate"}, timeout=60)
        assert r.status_code == 200
        d = r.json()
        assert d.get("ok") is False
        assert d.get("verified") is False
        msg = (d.get("message") or "").lower()
        assert "edr" in msg or "connector" in msg or "isolation" in msg
        assert d.get("ledger_id")


# ---- Verify Connectors (real live Stripe + Clerk not-configured) ----
class TestVerifyConnectors:
    def test_verify_connectors(self, client):
        r = client.post(f"{BASE_URL}/api/risk-engine/verify-connectors", timeout=60)
        assert r.status_code == 200
        d = r.json()
        assert "stripe" in d and "clerk" in d
        s = d["stripe"]; c = d["clerk"]
        # Stripe live 200
        assert s.get("ok") is True, f"stripe ok expected True: {s}"
        assert s.get("status") == 200
        assert s.get("configured") is True
        # Clerk not configured (honest)
        assert c.get("ok") is False
        assert c.get("configured") is False


# ---- Ledger persists attempts ----
class TestLedger:
    def test_ledger_contains_recent_entries(self, client):
        r = client.get(f"{BASE_URL}/api/risk-engine/ledger", timeout=30)
        assert r.status_code == 200
        d = r.json()
        assert "entries" in d and isinstance(d["entries"], list)
        assert len(d["entries"]) >= 1
        actions = {e.get("action") for e in d["entries"]}
        # After the tests above, we should have remediate + verify-connectors + isolate
        assert "remediate" in actions or "verify-connectors" in actions, f"actions={actions}"


# ---- Status transitions still work ----
class TestStatusTransitions:
    def test_status_transitions(self, client):
        r1 = client.post(f"{BASE_URL}/api/risk-engine/task/dep-ecdsa/status",
                         json={"status": "In Progress"}, timeout=30)
        assert r1.status_code == 200
        d1 = r1.json()
        assert "portfolio_before" in d1 and "portfolio_after" in d1
        assert "risk_reduced" in d1

        r2 = client.post(f"{BASE_URL}/api/risk-engine/task/dep-ecdsa/status",
                         json={"status": "Open"}, timeout=30)
        assert r2.status_code == 200
        d2 = r2.json()
        # Confirm residual restored
        final = client.get(f"{BASE_URL}/api/risk-engine/strategic", timeout=30).json()["portfolio"]["residual_ale"]
        assert final >= 9_000_000, f"residual should restore to ~9.6M; got {final}"
