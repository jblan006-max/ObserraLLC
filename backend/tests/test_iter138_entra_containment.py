"""Iteration 138: Entra connector + crisis identity containment tests."""
import os
import pytest
import requests

def _load_url():
    v = os.environ.get("REACT_APP_BACKEND_URL")
    if not v:
        try:
            with open("/app/frontend/.env") as f:
                for line in f:
                    if line.startswith("REACT_APP_BACKEND_URL="):
                        v = line.split("=", 1)[1].strip()
                        break
        except Exception:
            pass
    return (v or "").rstrip("/")

BASE_URL = _load_url()
ADMIN_EMAIL = "jblan2026@gmail.com"
ADMIN_PASSWORD = "Obserra2026!"


@pytest.fixture(scope="module")
def admin_session():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login",
               json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
               timeout=30)
    assert r.status_code == 200, f"Admin login failed: {r.status_code} {r.text[:200]}"
    return s


# ---- Connectors catalog / Entra connector ----
class TestEntraConnector:
    def test_catalog_entra_connectable(self, admin_session):
        r = admin_session.get(f"{BASE_URL}/api/connectors/catalog", timeout=30)
        assert r.status_code == 200
        data = r.json()
        # find catalog list
        items = data.get("connectors") or data.get("catalog") or data if isinstance(data, list) else data.get("items") or []
        if isinstance(data, dict) and not items:
            for v in data.values():
                if isinstance(v, list):
                    items = v
                    break
        assert len(items) >= 30, f"expected ~40 connectors, got {len(items)}"
        entra = next((c for c in items if c.get("id") == "entra"), None)
        assert entra is not None, "entra connector missing from catalog"
        assert entra.get("connectable") is True, f"entra not connectable: {entra}"
        assert entra.get("category") == "Identity & Access"
        fields = entra.get("fields") or []
        field_names = {(f.get("key") or f.get("name") if isinstance(f, dict) else f) for f in fields}
        assert {"tenant", "client_id", "client_secret"}.issubset(field_names), f"missing fields: {field_names}"

    def test_entra_connect_missing_creds(self, admin_session):
        r = admin_session.post(f"{BASE_URL}/api/connectors/entra/connect",
                               json={"creds": {}}, timeout=30)
        # Accept either 200 with state or 400
        assert r.status_code in (200, 400), r.text[:200]
        body = r.json() if r.headers.get("content-type","").startswith("application/json") else {}
        state = body.get("state") or body.get("status") or body.get("detail")
        assert "credentials_required" in str(body).lower() or r.status_code == 400, f"unexpected: {body}"

    def test_entra_connect_dummy_creds_auth_failed(self, admin_session):
        # Real call to Microsoft; should be rejected -> auth_failed
        r = admin_session.post(
            f"{BASE_URL}/api/connectors/entra/connect",
            json={"creds": {
                "tenant": "00000000-0000-0000-0000-000000000000",
                "client_id": "00000000-0000-0000-0000-000000000000",
                "client_secret": "not-a-real-secret",
            }},
            timeout=45,
        )
        assert r.status_code in (200, 400, 401), r.text[:200]
        body = r.json()
        text = str(body).lower()
        assert "connected" not in text or "auth_failed" in text or "not_connected" in text, \
            f"Should not report connected for fake creds: {body}"
        # state key check
        state = body.get("state") or body.get("status")
        assert state != "connected", f"MUST NEVER be connected with fake creds: {body}"


# ---- Crisis endpoints (require operator) ----
class TestCrisisEntraEndpoints:
    def test_crisis_entra_users_not_connected(self, admin_session):
        r = admin_session.get(f"{BASE_URL}/api/crisis/entra/users", timeout=30)
        assert r.status_code == 400, f"expected 400, got {r.status_code}: {r.text[:200]}"
        assert "not connected" in r.text.lower() or "entra" in r.text.lower()

    def test_crisis_contain_identity_not_connected(self, admin_session):
        # Need a crisis case ref. Try to list cases.
        rc = admin_session.get(f"{BASE_URL}/api/crisis/cases", timeout=30)
        ref = None
        if rc.status_code == 200:
            data = rc.json()
            cases = data if isinstance(data, list) else (data.get("cases") or data.get("items") or [])
            if cases:
                ref = cases[0].get("ref") or cases[0].get("id")
        if not ref:
            # create one
            rc2 = admin_session.post(f"{BASE_URL}/api/crisis/cases",
                                     json={"title": "TEST_iter138", "severity": "high"}, timeout=30)
            if rc2.status_code in (200, 201):
                ref = rc2.json().get("ref") or rc2.json().get("id")
        if not ref:
            pytest.skip("No crisis case available")
        r = admin_session.post(
            f"{BASE_URL}/api/crisis/cases/{ref}/contain-identity",
            json={"user_id": "abc", "upn": "x@example.com"}, timeout=30,
        )
        assert r.status_code == 400, f"expected 400, got {r.status_code}: {r.text[:200]}"
        assert "not connected" in r.text.lower()


# ---- Regression: other connectors ----
class TestConnectorRegression:
    def test_discover_still_works(self, admin_session):
        r = admin_session.post(f"{BASE_URL}/api/connectors/discover", json={}, timeout=90)
        assert r.status_code == 200, f"discover failed: {r.status_code} {r.text[:200]}"
        body = r.json()
        assert isinstance(body, (dict, list))

    def test_stripe_test_still_works(self, admin_session):
        r = admin_session.post(f"{BASE_URL}/api/connectors/stripe/test", json={}, timeout=45)
        # Should not 500; state should be one of standard values
        assert r.status_code in (200, 400), f"stripe test broken: {r.status_code} {r.text[:200]}"
        body = r.json()
        state = body.get("state") or body.get("status")
        assert state in ("connected", "auth_failed", "not_connected", "credentials_required", "unreachable", None), body

    def test_catalog_count_and_categories(self, admin_session):
        r = admin_session.get(f"{BASE_URL}/api/connectors/catalog", timeout=30)
        assert r.status_code == 200
        data = r.json()
        items = data if isinstance(data, list) else (data.get("connectors") or data.get("catalog") or data.get("items") or [])
        if isinstance(data, dict) and not items:
            for v in data.values():
                if isinstance(v, list):
                    items = v; break
        assert len(items) >= 35, f"expected ~40 connectors, got {len(items)}"
        cats = {c.get("category") for c in items}
        assert len(cats) >= 3
