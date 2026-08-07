"""Iteration 20 backend tests: regenerate-guides admin gate + guide endpoints still 200 after regenerate."""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://cyber-dashboard-48.preview.emergentagent.com").rstrip("/")

ADMIN = {"email": "jblan2026@gmail.com", "password": "Obserra2026!"}
OPS = {"email": "analyst@obserra.demo", "password": "Analyst2026!"}


def _login(creds):
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json=creds, timeout=30)
    assert r.status_code == 200, f"login failed for {creds['email']}: {r.status_code} {r.text[:200]}"
    return s


@pytest.fixture(scope="module")
def admin_session():
    return _login(ADMIN)


@pytest.fixture(scope="module")
def ops_session():
    return _login(OPS)


def test_regenerate_guides_unauth():
    r = requests.post(f"{BASE_URL}/api/deploy/regenerate-guides", timeout=30)
    assert r.status_code in (401, 403), f"expected 401/403 without auth, got {r.status_code}"


def test_regenerate_guides_ops_forbidden(ops_session):
    r = ops_session.post(f"{BASE_URL}/api/deploy/regenerate-guides", timeout=30)
    assert r.status_code == 403, f"expected 403 for operational user, got {r.status_code}"


def test_regenerate_guides_admin_ok(admin_session):
    r = admin_session.post(f"{BASE_URL}/api/deploy/regenerate-guides", timeout=120)
    assert r.status_code == 200, f"admin regenerate failed: {r.status_code} {r.text[:300]}"
    data = r.json()
    assert data.get("ok") is True
    assert isinstance(data.get("pdf_size"), int) and data["pdf_size"] > 1000
    assert isinstance(data.get("docx_size"), int) and data["docx_size"] > 1000


def test_guide_pdf_after_regenerate(admin_session):
    r = admin_session.get(f"{BASE_URL}/api/deploy/guide.pdf", timeout=60)
    assert r.status_code == 200
    assert r.headers.get("content-type", "").startswith("application/pdf")
    assert len(r.content) > 1000


def test_guide_docx_after_regenerate(admin_session):
    r = admin_session.get(f"{BASE_URL}/api/deploy/guide.docx", timeout=60)
    assert r.status_code == 200
    ct = r.headers.get("content-type", "")
    assert "wordprocessingml" in ct or "officedocument" in ct, f"unexpected ct: {ct}"
    assert len(r.content) > 1000
