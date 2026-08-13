"""Iteration 154 — /api/version, /api/cra/ground and /api/cra/ai-monitor."""
import os, requests, pytest

def _read_env():
    p = "/app/frontend/.env"
    if os.path.exists(p):
        for line in open(p):
            if line.startswith("REACT_APP_BACKEND_URL="):
                return line.split("=", 1)[1].strip()
    return os.environ.get("REACT_APP_BACKEND_URL", "")

BASE = _read_env().rstrip("/")
EMAIL = "jblan2026@gmail.com"
PW = "Obserra2026!"


@pytest.fixture(scope="module")
def sess():
    s = requests.Session()
    r = s.post(f"{BASE}/api/auth/login", json={"email": EMAIL, "password": PW}, timeout=20)
    assert r.status_code == 200, f"login failed {r.status_code} {r.text[:200]}"
    return s


# --- Versioning -------------------------------------------------------------
def test_version_endpoint():
    r = requests.get(f"{BASE}/api/version", timeout=15)
    assert r.status_code == 200
    d = r.json()
    assert d["name"] == "Obserra EU CRA Governance"
    assert d["version"] == "1.0.0"
    assert d["regulation"] == "Regulation (EU) 2024/2847"


# --- CRA grounding (insight) -----------------------------------------------
def test_cra_ground_insight_products(sess):
    ans = "Your organization tracks 8 products with digital elements. Only some are fully assessed for EU CRA compliance."
    r = sess.post(f"{BASE}/api/cra/ground",
                  json={"kind": "insight", "tab": "products", "answer": ans}, timeout=60)
    assert r.status_code == 200, r.text[:300]
    d = r.json()
    assert isinstance(d["score"], int) and 0 <= d["score"] <= 100
    assert d["label"] in ("Grounded", "Partially grounded", "Unverified")
    assert isinstance(d["flagged_count"], int)
    assert isinstance(d["flagged"], list)
    assert isinstance(d["claims"], list)
    assert "method" in d
    assert d["version"] == "1.0.0"


# --- CRA grounding (explain) -----------------------------------------------
def test_cra_ground_explain(sess):
    body = {
        "kind": "explain",
        "title": "CVE-2024-0001 in Test Firewall",
        "context": {"cve_id": "CVE-2024-0001", "product": "Test Firewall", "cvss": 7.5, "status": "open"},
        "answer": "CVE-2024-0001 affects Test Firewall with CVSS 7.5 and remains open, requiring remediation.",
    }
    r = sess.post(f"{BASE}/api/cra/ground", json=body, timeout=60)
    assert r.status_code == 200, r.text[:300]
    d = r.json()
    assert isinstance(d["score"], int)
    assert d["label"] in ("Grounded", "Partially grounded", "Unverified")
    assert d["version"] == "1.0.0"


# --- CRA AI monitor ---------------------------------------------------------
def test_cra_ai_monitor_aggregates(sess):
    # ensure at least one CRA grounding row exists
    sess.post(f"{BASE}/api/cra/ground",
              json={"kind": "insight", "tab": "sbom",
                    "answer": "SBOM coverage is being tracked across products."}, timeout=60)
    r = sess.get(f"{BASE}/api/cra/ai-monitor", timeout=30)
    assert r.status_code == 200, r.text[:300]
    d = r.json()
    assert d["version"] == "1.0.0"
    assert isinstance(d["total_checks"], int) and d["total_checks"] > 0
    assert d["label"] in ("Grounded", "Partially grounded", "Unverified")
    assert isinstance(d["by_surface"], list) and len(d["by_surface"]) > 0
    assert isinstance(d["recent"], list) and len(d["recent"]) > 0
    # all surfaces must be CRA-prefixed
    for s in d["by_surface"]:
        assert s["surface"].startswith("cra:"), s
    for r0 in d["recent"]:
        assert (r0.get("surface") or "").startswith("cra:")
