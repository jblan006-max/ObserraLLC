"""Iteration 139 backend tests: Entra risky users, SLA scan, contain playbook, branded report pack."""
import os
import re
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
EMAIL = "jblan2026@gmail.com"
PASSWORD = "Obserra2026!"


@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json={"email": EMAIL, "password": PASSWORD}, timeout=30)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text[:200]}"
    return s


@pytest.fixture(scope="module")
def demo_ref(session):
    r = session.post(f"{BASE_URL}/api/crisis/demo/seed", timeout=30)
    assert r.status_code == 200, f"seed failed: {r.status_code} {r.text[:200]}"
    ref = r.json().get("ref")
    assert ref
    yield ref
    session.post(f"{BASE_URL}/api/crisis/demo/clear", timeout=30)


# Entra risky-users — honest 400 not-connected
def test_entra_risky_users_not_connected(session):
    r = session.get(f"{BASE_URL}/api/crisis/entra/risky-users", timeout=30)
    assert r.status_code == 400, f"expected 400, got {r.status_code}: {r.text[:200]}"
    assert "Microsoft Entra is not connected" in r.text


# SLA scan endpoint
def test_sla_scan(session):
    r = session.post(f"{BASE_URL}/api/crisis/decisions/sla-scan", timeout=30)
    assert r.status_code == 200, f"{r.status_code}: {r.text[:200]}"
    data = r.json()
    assert "alerts_sent" in data
    assert isinstance(data["alerts_sent"], int)


# Contain playbook — honest 400 not-connected on valid case ref
def test_contain_playbook_not_connected(session, demo_ref):
    r = session.post(
        f"{BASE_URL}/api/crisis/cases/{demo_ref}/contain-playbook",
        json={"user_id": "dummy-uid", "upn": "test@example.com", "notify": True},
        timeout=30,
    )
    assert r.status_code == 400, f"expected 400, got {r.status_code}: {r.text[:200]}"
    assert "Microsoft Entra is not connected" in r.text


# Branded Report Pack PDF
def test_report_pack_branded(session, demo_ref):
    r = session.get(f"{BASE_URL}/api/crisis/cases/{demo_ref}/report-pack.pdf", timeout=60)
    assert r.status_code == 200, f"{r.status_code}: {r.text[:200]}"
    ct = r.headers.get("content-type", "")
    assert "pdf" in ct.lower(), f"content-type {ct}"
    body = r.content
    assert body[:4] == b"%PDF", "not a valid PDF magic"
    # Extract text (streams are compressed) via pdfminer
    import io
    from pdfminer.high_level import extract_text
    txt = extract_text(io.BytesIO(body))
    text_hits = {k: (k in txt or k.lower() in txt.lower()) for k in ("Obserra", "Crisis Report Pack", "Confidential")}
    assert all(text_hits.values()), f"branded text missing in PDF: {text_hits}"
