"""Iteration 153 — EU CRA AI Analyst + Explain + connectors catalog (Universal API, QMS, LIMS)."""
import os
import re
import pytest
import requests

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://cyber-dashboard-48.preview.emergentagent.com').rstrip('/')
ADMIN_EMAIL = 'jblan2026@gmail.com'
ADMIN_PWD = 'Obserra2026!'

TABS = ["products", "portal", "ledger", "sbom", "vulnerability", "labs",
        "declaration", "regulation", "controls", "nist"]


@pytest.fixture(scope="session")
def sess():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login",
               json={"email": ADMIN_EMAIL, "password": ADMIN_PWD}, timeout=30)
    assert r.status_code == 200, f"Login failed: {r.status_code} {r.text[:200]}"
    return s


# ---- dashboard-insight per tab ----
@pytest.mark.parametrize("tab", TABS)
def test_dashboard_insight_per_tab(sess, tab):
    r = sess.post(f"{BASE_URL}/api/cra/dashboard-insight", json={"tab": tab}, timeout=60)
    assert r.status_code == 200, f"{tab}: {r.status_code} {r.text[:200]}"
    body = r.json()
    assert "headline" in body and isinstance(body["headline"], str) and body["headline"].strip()
    assert isinstance(body.get("insights"), list) and 3 <= len(body["insights"]) <= 6
    assert isinstance(body.get("actions"), list) and len(body["actions"]) >= 1
    assert body.get("tab") == tab
    # Must not mention forbidden domains
    combined = (body["headline"] + " " + " ".join([i.get("text", "") for i in body["insights"]]) +
                " " + " ".join(body["actions"])).lower()
    for bad in ("sap", "sod ", "cyber crisis", "cyber-crisis"):
        assert bad not in combined, f"Tab {tab} leaked forbidden term '{bad}': {combined[:200]}"


# ---- explain ----
def test_explain_returns_expected_shape(sess):
    payload = {
        "title": "Article 14 vulnerability reporting",
        "kind": "control",
        "context": {"requirement_id": "CRA-VULN-01", "status": "Partial",
                    "compliance_rate": 0.4, "risk": "High"}
    }
    r = sess.post(f"{BASE_URL}/api/cra/explain", json=payload, timeout=60)
    assert r.status_code == 200, r.text[:200]
    b = r.json()
    for k in ("summary", "severity", "risk", "risk_detail", "recommendation", "steps"):
        assert k in b, f"missing {k}"
    assert b["severity"] in ("risk", "watch", "opportunity", "info")
    assert isinstance(b["steps"], list) and len(b["steps"]) >= 2
    lowered = (b["summary"] + " " + b["risk_detail"] + " " + b["recommendation"]).lower()
    for bad in ("sap", "sod ", "cyber crisis"):
        assert bad not in lowered


# ---- NIST ----
def test_nist_endpoint(sess):
    r = sess.get(f"{BASE_URL}/api/cra/nist", timeout=30)
    assert r.status_code == 200
    b = r.json()
    assert "overall" in b
    pct = b["overall"].get("percentage") or b["overall"].get("alignment_percentage")
    assert isinstance(pct, (int, float))
    codes = {f["code"] for f in b.get("functions", [])}
    assert {"GV", "ID", "PR", "DE", "RS", "RC"}.issubset(codes)


# ---- Scorecard link + revoke + public + PDF ----
def test_scorecard_mint_revoke_public_pdf(sess):
    # Revoke first to ensure capacity
    sess.post(f"{BASE_URL}/api/cra/scorecard-link/revoke", timeout=30)
    r = sess.post(f"{BASE_URL}/api/cra/scorecard-link", timeout=30)
    assert r.status_code == 200, r.text[:200]
    tok = r.json()["token"]
    # Public endpoint (no auth)
    pub = requests.get(f"{BASE_URL}/api/cra-public/scorecard/{tok}", timeout=30)
    assert pub.status_code == 200
    body = pub.json()
    assert "overall" in body and "percentage" in body["overall"]
    # PDF
    pdf = requests.get(f"{BASE_URL}/api/cra-public/scorecard/{tok}/pdf", timeout=60)
    assert pdf.status_code == 200
    assert pdf.headers.get("content-type", "").startswith("application/pdf")
    assert pdf.content[:5] == b"%PDF-"
    # Revoke
    rv = sess.post(f"{BASE_URL}/api/cra/scorecard-link/revoke", timeout=30)
    assert rv.status_code == 200
    # After revoke public should 404/403
    pub2 = requests.get(f"{BASE_URL}/api/cra-public/scorecard/{tok}", timeout=30)
    assert pub2.status_code in (401, 403, 404, 410)


# ---- Assignment (controls) ----
def test_control_assignment(sess):
    ctrls = sess.get(f"{BASE_URL}/api/cra/controls", timeout=30).json()
    rid = ctrls["controls"][0]["requirement_id"]
    r = sess.put(f"{BASE_URL}/api/cra/controls/{rid}/assignment",
                 json={"owner": "TEST_owner@example.com", "status": "In Progress",
                       "due_date": "2026-12-31", "note": "iter153 auto-test"}, timeout=30)
    assert r.status_code == 200, r.text[:200]
    # verify
    ctrls2 = sess.get(f"{BASE_URL}/api/cra/controls", timeout=30).json()
    match = [c for c in ctrls2["controls"] if c["requirement_id"] == rid][0]
    asn = match.get("assignment") or {}
    assert asn.get("owner") == "TEST_owner@example.com"


# ---- Connector catalog: three new categories present ----
EXPECTED_UNIVERSAL = {"universal-rest", "universal-apikey", "universal-webhook"}
EXPECTED_QMS = {"greenlight-guru", "mastercontrol", "qualio", "etq-reliance",
                "veeva-vault-qms", "sparta-trackwise"}
EXPECTED_LIMS = {"labware-lims", "labvantage", "starlims", "benchling",
                 "thermo-samplemanager", "ul-solutions", "intertek",
                 "tuv-sud", "eurofins"}


def test_connectors_catalog_new_categories(sess):
    r = sess.get(f"{BASE_URL}/api/connectors/catalog", timeout=30)
    assert r.status_code == 200
    items = r.json()
    # normalise to list
    if isinstance(items, dict):
        items = items.get("items") or items.get("catalog") or []
    cats = {}
    for it in items:
        cats.setdefault(it.get("category"), set()).add(it.get("id"))
    assert EXPECTED_UNIVERSAL.issubset(cats.get("Universal API", set())), cats.get("Universal API")
    assert EXPECTED_QMS.issubset(cats.get("Quality Management (QMS)", set())), cats.get("Quality Management (QMS)")
    assert EXPECTED_LIMS.issubset(cats.get("Labs & Testing (LIMS)", set())), cats.get("Labs & Testing (LIMS)")


def test_connectors_health_honest(sess):
    r = sess.get(f"{BASE_URL}/api/connectors/health", timeout=60)
    assert r.status_code == 200
    body = r.json()
    items = body if isinstance(body, list) else (body.get("connectors") or body.get("items") or body.get("health") or [])
    # health should return per-connector states; assert no fabricated 'connected' on non-configured items
    assert len(items) >= 20
    # Verify new categories present in health feed too
    cats = {it.get("category") for it in items}
    assert "Universal API" in cats
    assert "Quality Management (QMS)" in cats
    assert "Labs & Testing (LIMS)" in cats
    # Honest state — non-credentialled ones should NOT be 'connected'
    for it in items:
        if it.get("state") == "connected":
            # only allow if it's a webhook/self-hosted DISCOVERED-type; can't easily check, but ensure not fabricated for known credential-required ids
            assert it["id"] not in {"greenlight-guru", "labware-lims", "ul-solutions", "mastercontrol"}
