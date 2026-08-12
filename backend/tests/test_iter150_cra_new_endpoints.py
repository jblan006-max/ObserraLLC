"""Iteration 150 - Tests for new CRA governance endpoints:
    - POST/DELETE /api/cra/demo/seed (admin, idempotent)
    - GET /api/cra/insight (grounded AI briefing)
    - POST /api/cra/products/{ref}/verification-link (admin)
    - GET /api/cra-public/verify/{token} (public, auditor role only)
"""
import os
import time
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://cyber-dashboard-48.preview.emergentagent.com").rstrip("/")
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "jblan2026@gmail.com")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "Obserra2026!")


@pytest.fixture(scope="module")
def admin_session():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login",
               json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=20)
    assert r.status_code == 200, f"admin login failed: {r.status_code} {r.text[:300]}"
    return s


@pytest.fixture(scope="module")
def anon_session():
    return requests.Session()


# ------------------ /api/cra/demo/seed ------------------

class TestSeedSampleProducts:
    def test_seed_admin_creates_or_returns_note(self, admin_session):
        r = admin_session.post(f"{BASE_URL}/api/cra/demo/seed", timeout=30)
        assert r.status_code == 200, r.text[:300]
        data = r.json()
        assert data["ok"] is True
        assert "created" in data
        # If already present the note key is set
        if data["created"] == 0:
            assert "note" in data
        else:
            assert isinstance(data.get("product_refs"), list)

    def test_seed_idempotent_second_call(self, admin_session):
        # Ensure at least one call was made
        admin_session.post(f"{BASE_URL}/api/cra/demo/seed", timeout=30)
        r = admin_session.post(f"{BASE_URL}/api/cra/demo/seed", timeout=30)
        assert r.status_code == 200
        d = r.json()
        assert d["ok"] is True
        assert d["created"] == 0
        assert "already present" in d.get("note", "").lower()

    def test_seed_non_admin_forbidden(self, anon_session):
        r = anon_session.post(f"{BASE_URL}/api/cra/demo/seed", timeout=15)
        assert r.status_code in (401, 403), f"expected 401/403 got {r.status_code}"


# ------------------ /api/cra/insight ------------------

class TestCRAInsight:
    def test_insight_shape(self, admin_session):
        # ensure some data exists
        admin_session.post(f"{BASE_URL}/api/cra/demo/seed", timeout=30)
        r = admin_session.get(f"{BASE_URL}/api/cra/insight", timeout=30)
        assert r.status_code == 200, r.text[:300]
        d = r.json()
        for k in ("headline", "insights", "actions", "model", "generated_at"):
            assert k in d, f"missing {k}"
        assert isinstance(d["headline"], str) and len(d["headline"]) > 0
        assert isinstance(d["insights"], list) and len(d["insights"]) >= 1
        for ins in d["insights"]:
            assert "text" in ins and "kind" in ins
            assert ins["kind"] in ("fact", "estimate", "risk")
        assert isinstance(d["actions"], list)

    def test_insight_requires_auth(self, anon_session):
        r = anon_session.get(f"{BASE_URL}/api/cra/insight", timeout=15)
        assert r.status_code in (401, 403)


# ------------------ verification link + public verify ------------------

class TestVerificationLink:
    @pytest.fixture(scope="class")
    def product_ref(self, admin_session):
        admin_session.post(f"{BASE_URL}/api/cra/demo/seed", timeout=30)
        r = admin_session.get(f"{BASE_URL}/api/cra/products", timeout=15)
        assert r.status_code == 200, r.text[:300]
        products = r.json()
        # products could be a list or dict-with-items
        items = products if isinstance(products, list) else products.get("items", [])
        assert len(items) > 0, "no products available"
        return items[0]["ref"]

    def test_admin_creates_verification_link(self, admin_session, product_ref):
        r = admin_session.post(f"{BASE_URL}/api/cra/products/{product_ref}/verification-link", timeout=15)
        assert r.status_code == 200, r.text[:300]
        d = r.json()
        assert "token" in d and isinstance(d["token"], str) and len(d["token"]) > 10
        assert "expires_at" in d
        assert d.get("path", "").startswith("/cra-verify/")

    def test_non_admin_forbidden(self, anon_session, product_ref):
        r = anon_session.post(f"{BASE_URL}/api/cra/products/{product_ref}/verification-link", timeout=15)
        assert r.status_code in (401, 403)

    def test_public_verify_ok(self, admin_session, anon_session, product_ref):
        r = admin_session.post(f"{BASE_URL}/api/cra/products/{product_ref}/verification-link", timeout=15)
        assert r.status_code == 200
        token = r.json()["token"]
        r2 = anon_session.get(f"{BASE_URL}/api/cra-public/verify/{token}", timeout=15)
        assert r2.status_code == 200, r2.text[:300]
        d = r2.json()
        assert d.get("role") == "auditor"
        assert d["product"]["ref"] == product_ref
        assert "integrity" in d
        assert "chain_intact" in d["integrity"]
        assert isinstance(d["integrity"].get("records_verified"), int)
        assert d["integrity"]["records_verified"] >= 1
        assert isinstance(d.get("timeline"), list)
        assert len(d["timeline"]) >= 1

    def test_public_verify_invalid_token(self, anon_session):
        r = anon_session.get(f"{BASE_URL}/api/cra-public/verify/not-a-real-token-xyz", timeout=15)
        assert r.status_code in (400, 401, 403, 404)


# ------------------ DELETE /api/cra/demo/seed (kept last to preserve data for other tests) ------------------

class TestClearSamples:
    def test_clear_non_admin_forbidden(self, anon_session):
        r = anon_session.delete(f"{BASE_URL}/api/cra/demo/seed", timeout=15)
        assert r.status_code in (401, 403)

    def test_clear_and_reseed(self, admin_session):
        admin_session.post(f"{BASE_URL}/api/cra/demo/seed", timeout=30)
        r = admin_session.delete(f"{BASE_URL}/api/cra/demo/seed", timeout=30)
        assert r.status_code == 200, r.text[:300]
        d = r.json()
        assert d["ok"] is True
        assert isinstance(d.get("removed"), int)
        # re-seed for downstream tests / manual UI verification
        r2 = admin_session.post(f"{BASE_URL}/api/cra/demo/seed", timeout=30)
        assert r2.status_code == 200
        assert r2.json().get("created", 0) >= 0
