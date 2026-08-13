"""Iteration 152 — EU CRA Governance: product_status drill, brief.pdf,
scorecard-link (+ public scorecard), verification-link guardrail (429).
"""
import os
import uuid
import requests
import pytest


def _load_frontend_env_url():
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                return line.split("=", 1)[1].strip()
    return None


BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or _load_frontend_env_url()).rstrip("/")
ADMIN_EMAIL = "jblan2026@gmail.com"
ADMIN_PASSWORD = "Obserra2026!"


@pytest.fixture(scope="module")
def admin_client():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login",
               json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=30)
    assert r.status_code == 200, r.text
    return s


@pytest.fixture(scope="module")
def fresh_nonadmin_client():
    s = requests.Session()
    email = f"nonadmin_iter152_{uuid.uuid4().hex[:8]}@example.com"
    r = s.post(f"{BASE_URL}/api/auth/register", json={
        "email": email, "password": "SafePass!2026-longer",
        "name": "Iter152 NonAdmin",
        "org_name": f"Iter152 Org {uuid.uuid4().hex[:6]}",
    }, timeout=30)
    assert r.status_code == 200, r.text
    return s, email


# ---- 1) /cra/controls: product_status ----------------------------------

def test_controls_product_status_present(admin_client):
    r = admin_client.get(f"{BASE_URL}/api/cra/controls", timeout=30)
    assert r.status_code == 200, r.text
    d = r.json()
    assert 0 <= d["overall"]["percentage"] <= 100
    assert d["controls"], "no controls returned"
    for c in d["controls"]:
        assert "product_status" in c, f"missing product_status in {c.get('requirement_id')}"
        assert isinstance(c["product_status"], list)
        for ps in c["product_status"]:
            assert set(("ref", "name", "status")).issubset(ps.keys())
            assert ps["status"] in ("Conforming", "Partial", "Nonconforming", "Not Assessed")


# ---- 2) /cra/digest/brief.pdf ------------------------------------------

def test_brief_pdf_download(admin_client):
    r = admin_client.get(f"{BASE_URL}/api/cra/digest/brief.pdf", timeout=60)
    assert r.status_code == 200, r.text
    assert r.headers.get("content-type", "").startswith("application/pdf")
    cd = r.headers.get("content-disposition", "")
    assert "attachment" in cd.lower()
    assert r.content[:4] == b"%PDF", "response body is not a PDF"
    assert len(r.content) > 500


def test_brief_pdf_no_products_returns_400(fresh_nonadmin_client):
    s, _ = fresh_nonadmin_client
    r = s.get(f"{BASE_URL}/api/cra/digest/brief.pdf", timeout=30)
    assert r.status_code == 400, f"expected 400, got {r.status_code} {r.text}"


# ---- 3) /cra/scorecard-link + public scorecard --------------------------

@pytest.fixture(scope="module")
def scorecard_token(admin_client):
    r = admin_client.post(f"{BASE_URL}/api/cra/scorecard-link", timeout=30)
    assert r.status_code == 200, r.text
    d = r.json()
    for k in ("token", "expires_at", "path"):
        assert k in d
    assert d["path"] == f"/cra-scorecard/{d['token']}"
    return d["token"]


def test_scorecard_link_nonadmin_forbidden(fresh_nonadmin_client):
    s, _ = fresh_nonadmin_client
    r = s.post(f"{BASE_URL}/api/cra/scorecard-link", timeout=15)
    assert r.status_code == 403, f"expected 403, got {r.status_code} {r.text}"


def test_public_scorecard_shape_and_no_product_names(admin_client, scorecard_token):
    anon = requests.Session()
    r = anon.get(f"{BASE_URL}/api/cra-public/scorecard/{scorecard_token}", timeout=30)
    assert r.status_code == 200, r.text
    d = r.json()
    assert "organization" in d
    for k in ("percentage", "implemented", "partial", "gaps", "not_started",
              "high_risk", "requirements_total", "products_assessed", "products_total"):
        assert k in d["overall"], f"missing overall.{k}"
    assert isinstance(d["top_gaps"], list)
    for g in d["top_gaps"]:
        for k in ("requirement_id", "domain", "title", "compliance_rate", "status", "risk"):
            assert k in g
    # Must NOT expose product names or internal product_status
    body = r.text
    assert "product_status" not in body, "product_status leaked in public scorecard"
    # Fetch admin's product names, ensure none appear in public payload
    prods = admin_client.get(f"{BASE_URL}/api/cra/products", timeout=15).json()
    for p in prods:
        name = p.get("name")
        if name:
            assert name not in body, f"product name '{name}' leaked in public scorecard"
        ref = p.get("ref")
        if ref:
            assert ref not in body, f"product ref '{ref}' leaked in public scorecard"


def test_public_scorecard_rejects_auditor_token(admin_client):
    # Mint an auditor token (needs a product); tolerate 429 if org already has 5 active links
    prods = admin_client.get(f"{BASE_URL}/api/cra/products", timeout=15).json()
    assert prods, "no CRA products on admin org"
    auditor_token = None
    for p in prods:
        r = admin_client.post(
            f"{BASE_URL}/api/cra/products/{p['ref']}/verification-link", timeout=30)
        if r.status_code == 200:
            auditor_token = r.json()["token"]
            break
        # 429 means saturated; try next product
    if not auditor_token:
        pytest.skip("all products saturated with 5 active auditor links")
    anon = requests.Session()
    r = anon.get(f"{BASE_URL}/api/cra-public/scorecard/{auditor_token}", timeout=30)
    assert r.status_code == 403, f"expected 403, got {r.status_code} {r.text}"


# ---- 4) Verification-link cap (5 → 429) --------------------------------

def test_verification_link_cap_5_then_429(admin_client):
    # Create a NEW product so we start at 0 active auditor links
    payload = {"name": f"Iter152 GuardTest {uuid.uuid4().hex[:6]}",
               "manufacturer_name": "Iter152 Test Manufacturer",
               "core_functionality": "test product for verification-link cap",
               "category_codes": ["I-01"], "support_period_years": 5, "eu_market": True}
    cr = admin_client.post(f"{BASE_URL}/api/cra/products", json=payload, timeout=15)
    if cr.status_code not in (200, 201):
        pytest.skip(f"could not create fresh product: {cr.status_code} {cr.text}")
    ref = cr.json().get("ref") or cr.json().get("product", {}).get("ref")
    assert ref, f"product ref missing in create response: {cr.text}"

    # Mint 5 successfully
    tokens = []
    for i in range(5):
        r = admin_client.post(
            f"{BASE_URL}/api/cra/products/{ref}/verification-link", timeout=15)
        assert r.status_code == 200, f"call #{i+1} failed: {r.status_code} {r.text}"
        tokens.append(r.json()["token"])
    # 6th must be 429
    r6 = admin_client.post(
        f"{BASE_URL}/api/cra/products/{ref}/verification-link", timeout=15)
    assert r6.status_code == 429, f"expected 429 on 6th, got {r6.status_code} {r6.text}"


# ---- 5) Scorecard-link cap (bonus, best-effort) ------------------------

def test_scorecard_link_cap_5_then_429_best_effort(admin_client):
    """Bonus check: attempt to hit the org-level 5-active-scorecard cap.
    We already minted 1 in scorecard_token fixture; try to top-up to 5 then
    expect 429 on the 6th. Skip if org already saturated from prior runs.
    """
    # See how many active we already have by attempting mints
    minted = 0
    for _ in range(6):
        r = admin_client.post(f"{BASE_URL}/api/cra/scorecard-link", timeout=15)
        if r.status_code == 200:
            minted += 1
            continue
        if r.status_code == 429:
            # cap enforced -- success
            assert "5 active" in r.text or "429" in str(r.status_code)
            return
        pytest.fail(f"unexpected status {r.status_code}: {r.text}")
    pytest.fail("did not hit 429 after 6 mints")
