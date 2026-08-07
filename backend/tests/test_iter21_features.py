"""Iteration 21 backend tests: email-docs endpoint + regenerate-guides regression."""
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


# --- Email docs ---

def test_email_docs_unauth():
    r = requests.post(f"{BASE_URL}/api/deploy/email-docs", json={"to": "foo@bar.com"}, timeout=30)
    assert r.status_code in (401, 403), f"expected 401/403 unauth, got {r.status_code}"


def test_email_docs_ops_forbidden(ops_session):
    r = ops_session.post(f"{BASE_URL}/api/deploy/email-docs", json={"to": "foo@bar.com"}, timeout=30)
    assert r.status_code == 403, f"expected 403 for operational, got {r.status_code} {r.text[:200]}"


def test_email_docs_invalid(admin_session):
    r = admin_session.post(f"{BASE_URL}/api/deploy/email-docs", json={"to": "not-an-email"}, timeout=30)
    assert r.status_code == 400, f"expected 400 invalid email, got {r.status_code} {r.text[:200]}"
    body = r.json()
    msg = (body.get("detail") or body.get("message") or "").lower()
    assert "valid" in msg and "email" in msg, f"unexpected error message: {body}"


def test_email_docs_admin_ok(admin_session):
    r = admin_session.post(
        f"{BASE_URL}/api/deploy/email-docs",
        json={"to": ADMIN["email"]},
        timeout=120,
    )
    assert r.status_code == 200, f"admin email-docs failed: {r.status_code} {r.text[:400]}"
    data = r.json()
    assert data.get("status") == "sent", f"unexpected response: {data}"


# --- Regenerate guides regression ---

def test_regenerate_guides_admin_ok(admin_session):
    r = admin_session.post(f"{BASE_URL}/api/deploy/regenerate-guides", timeout=180)
    assert r.status_code == 200, f"regen failed: {r.status_code} {r.text[:300]}"
    data = r.json()
    assert data.get("ok") is True


def test_guide_pdf_downloads(admin_session):
    r = admin_session.get(f"{BASE_URL}/api/deploy/guide.pdf", timeout=60)
    assert r.status_code == 200
    assert r.headers.get("content-type", "").startswith("application/pdf")
    assert len(r.content) > 1000


def test_guide_docx_downloads(admin_session):
    r = admin_session.get(f"{BASE_URL}/api/deploy/guide.docx", timeout=60)
    assert r.status_code == 200
    ct = r.headers.get("content-type", "")
    assert "wordprocessingml" in ct or "officedocument" in ct
    assert len(r.content) > 1000
