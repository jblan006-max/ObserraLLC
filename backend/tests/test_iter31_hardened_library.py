"""Iteration 31 — Hardened control library + meet-by-default framework model + Obserrian rename."""
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

EXPECTED_GAP = {
    "NIST 800-53": 4,
    "CIS v8": 3,
    "SOC 2": 2,
    "SSDF": 1,
    "PCI DSS": 3,
    "ISO 27001": 2,
}

EXPECTED_GAP_IDS_NIST = {"AC-25", "PM-31", "PT-8", "SR-8"}


@pytest.fixture(scope="module")
def client():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login",
               json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    return s


# --- Hardened control library ---
class TestHardenedLibrary:
    def test_controls_compliance_24_all_passing(self, client):
        r = client.get(f"{BASE_URL}/api/controls/compliance")
        assert r.status_code == 200
        d = r.json()
        assert d["total_controls"] == 24, f"expected 24, got {d['total_controls']}"
        assert d["passing"] == 24, f"expected all 24 passing, got {d['passing']}"
        assert d["gaps"] == [] or len(d["gaps"]) == 0

    def test_crosswalk_24_all_compliant(self, client):
        r = client.get(f"{BASE_URL}/api/controls/crosswalk")
        assert r.status_code == 200
        d = r.json()
        assert d["total_controls"] == 24
        assert d["compliant_controls"] == 24

    def test_crosswalk_by_criticality_100pct(self, client):
        d = client.get(f"{BASE_URL}/api/controls/crosswalk").json()
        tiers = {b["criticality"]: b for b in d["by_criticality"]}
        assert set(tiers) == {"Critical", "High", "Medium", "Low"}
        for tier, entry in tiers.items():
            assert entry["controls"] > 0, f"{tier} tier empty"
            assert entry["compliant_pct"] == 100, f"{tier}: {entry}"


# --- Meet-by-default summary ---
class TestMeetByDefault:
    def test_summary_shape_and_gaps(self, client):
        d = client.get(f"{BASE_URL}/api/controls/crosswalk").json()
        by_fw = {s["framework"]: s for s in d["summary"]}
        assert set(by_fw) == set(EXPECTED_CATALOG.keys())
        for fw, entry in by_fw.items():
            for k in ("total", "aligned", "met", "gap", "meeting",
                      "meeting_pct", "evidence_pct", "compliant_pct"):
                assert k in entry, f"{fw} missing {k}"
            assert entry["total"] == EXPECTED_CATALOG[fw]
            assert entry["gap"] == EXPECTED_GAP[fw], f"{fw}: gap={entry['gap']}"
            assert entry["aligned"] + entry["met"] + entry["gap"] == entry["total"]
            assert entry["meeting_pct"] >= 96.0, f"{fw} meeting_pct={entry['meeting_pct']}"


# --- Per-framework catalog ---
class TestFrameworkCatalog:
    @pytest.mark.parametrize("fw,expected_total", list(EXPECTED_CATALOG.items()))
    def test_full_catalog(self, client, fw, expected_total):
        enc = urllib.parse.quote(fw)
        r = client.get(f"{BASE_URL}/api/controls/framework/{enc}")
        assert r.status_code == 200, f"{fw}: {r.status_code} {r.text}"
        d = r.json()
        assert d["framework"] == fw
        assert d["total"] == expected_total
        assert len(d["controls"]) == expected_total
        assert d["aligned"] + d["met"] + d["gap"] == d["total"]
        assert d["gap"] == EXPECTED_GAP[fw]
        # status vocabulary
        allowed = {"aligned", "met", "gap"}
        for c in d["controls"]:
            assert c["status"] in allowed, f"{fw}/{c['id']} status={c['status']}"
            for k in ("id", "group", "status", "mapped_to"):
                assert k in c

    def test_nist_ac2_aligned_ac10_met_gap_ids(self, client):
        d = client.get(
            f"{BASE_URL}/api/controls/framework/{urllib.parse.quote('NIST 800-53')}").json()
        by_id = {c["id"]: c for c in d["controls"]}
        assert "AC-2" in by_id
        assert by_id["AC-2"]["status"] == "aligned", by_id["AC-2"]
        mapped_ids = [m["control_id"] for m in by_id["AC-2"]["mapped_to"]]
        assert "IAM-3" in mapped_ids
        # A default control (no explicit mapping) → 'met'
        assert "AC-10" in by_id
        assert by_id["AC-10"]["status"] == "met", by_id["AC-10"]
        # Gap IDs
        for gid in EXPECTED_GAP_IDS_NIST:
            assert gid in by_id, f"{gid} missing from NIST catalog"
            assert by_id[gid]["status"] == "gap", f"{gid}: {by_id[gid]}"

    def test_unknown_framework_404(self, client):
        r = client.get(f"{BASE_URL}/api/controls/framework/BogusFW")
        assert r.status_code == 404


# --- Regression / upsert idempotency ---
class TestRegression:
    def test_repeated_calls_stable(self, client):
        a = client.get(f"{BASE_URL}/api/controls/compliance").json()
        b = client.get(f"{BASE_URL}/api/controls/compliance").json()
        assert a["total_controls"] == b["total_controls"] == 24
        assert a["passing"] == b["passing"] == 24

        c = client.get(f"{BASE_URL}/api/controls/crosswalk").json()
        d = client.get(f"{BASE_URL}/api/controls/crosswalk").json()
        assert c["total_controls"] == d["total_controls"] == 24
        assert {s["framework"]: s["gap"] for s in c["summary"]} == \
               {s["framework"]: s["gap"] for s in d["summary"]}

    def test_enterprise_live_ok(self, client):
        r = client.get(f"{BASE_URL}/api/enterprise/live")
        assert r.status_code == 200
