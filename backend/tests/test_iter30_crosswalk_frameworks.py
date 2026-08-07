"""Iteration 30 — Compliance crosswalk + full-catalog framework endpoint + regression."""
import os
import urllib.parse
import pytest
import requests

def _load_backend_url():
    v = os.environ.get("REACT_APP_BACKEND_URL")
    if v:
        return v.rstrip("/")
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                return line.split("=", 1)[1].strip().rstrip("/")
    raise RuntimeError("REACT_APP_BACKEND_URL not found")

BASE_URL = _load_backend_url()
ADMIN_EMAIL = "jblan2026@gmail.com"
ADMIN_PASSWORD = "Obserra2026!"

EXPECTED_CATALOG = {
    "NIST 800-53": 322,
    "CIS v8": 153,
    "SOC 2": 61,
    "SSDF": 42,
    "PCI DSS": 277,
    "ISO 27001": 93,
}


@pytest.fixture(scope="module")
def client():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    return s


# --- Crosswalk summary + criticality ---
class TestCrosswalk:
    def test_crosswalk_structure(self, client):
        r = client.get(f"{BASE_URL}/api/controls/crosswalk")
        assert r.status_code == 200
        data = r.json()
        assert set(data["frameworks"]) == set(EXPECTED_CATALOG.keys())
        # Summary shape
        for s in data["summary"]:
            for k in ("assessed_controls", "compliant", "compliant_pct",
                      "mapped_ref_count", "catalog_controls", "coverage_pct"):
                assert k in s, f"missing {k} in summary entry {s.get('framework')}"
            assert s["catalog_controls"] == EXPECTED_CATALOG[s["framework"]]
        # by_criticality present
        tiers = {b["criticality"]: b for b in data["by_criticality"]}
        assert set(tiers.keys()) == {"Critical", "High", "Medium", "Low"}
        for t in tiers.values():
            for k in ("controls", "compliant", "compliant_pct"):
                assert k in t

    def test_crosswalk_rows_have_criticality_and_real_ids(self, client):
        r = client.get(f"{BASE_URL}/api/controls/crosswalk").json()
        # Find IAM-3 row and verify mapping contains AC-2 for NIST 800-53
        iam3 = next(row for row in r["rows"] if row["control_id"] == "IAM-3")
        assert iam3["criticality"] == "Critical"
        assert "AC-2" in iam3["mappings"]["NIST 800-53"]
        assert "5.1" in iam3["mappings"]["CIS v8"]
        # every row has a criticality
        for row in r["rows"]:
            assert row["criticality"] in {"Critical", "High", "Medium", "Low"}


# --- Full-catalog per framework ---
class TestFrameworkCatalog:
    @pytest.mark.parametrize("fw,expected_total", list(EXPECTED_CATALOG.items()))
    def test_full_catalog_counts(self, client, fw, expected_total):
        enc = urllib.parse.quote(fw)
        r = client.get(f"{BASE_URL}/api/controls/framework/{enc}")
        assert r.status_code == 200, f"{fw}: {r.status_code} {r.text}"
        data = r.json()
        assert data["framework"] == fw
        assert data["total"] == expected_total
        assert len(data["controls"]) == expected_total
        # counts add up
        assert data["aligned"] + data["gap"] + data["not_assessed"] == data["total"]
        # coverage_pct present
        assert "coverage_pct" in data
        # each control shape
        sample = data["controls"][0]
        for k in ("id", "group", "status", "mapped_to"):
            assert k in sample
        assert sample["status"] in {"aligned", "gap", "not_assessed"}

    def test_nist_ac2_aligned_iam3(self, client):
        r = client.get(f"{BASE_URL}/api/controls/framework/{urllib.parse.quote('NIST 800-53')}").json()
        by_id = {c["id"]: c for c in r["controls"]}
        assert "AC-2" in by_id
        ac2 = by_id["AC-2"]
        assert ac2["status"] == "aligned", f"AC-2 status={ac2['status']} mapped_to={ac2['mapped_to']}"
        mapped_ids = [m["control_id"] for m in ac2["mapped_to"]]
        assert "IAM-3" in mapped_ids
        # AC-1 should be not_assessed (not in any mapping)
        assert by_id["AC-1"]["status"] == "not_assessed"

    def test_unknown_framework_404(self, client):
        r = client.get(f"{BASE_URL}/api/controls/framework/BogusFW")
        assert r.status_code == 404


# --- Regression ---
class TestRegression:
    def test_controls_compliance_ok(self, client):
        r = client.get(f"{BASE_URL}/api/controls/compliance")
        assert r.status_code == 200
        d = r.json()
        assert "frameworks" in d and "overall" in d and "gaps" in d

    def test_enterprise_live_ok(self, client):
        r = client.get(f"{BASE_URL}/api/enterprise/live")
        assert r.status_code == 200
