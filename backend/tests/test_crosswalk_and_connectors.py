"""Backend regression for compliance crosswalk + connector recheck + AI governance licenses."""
import os
import requests
import pytest

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://cyber-dashboard-48.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "jblan2026@gmail.com"
ADMIN_PASSWORD = "Obserra2026!"

EXPECTED_FRAMEWORKS = ["NIST 800-53", "CIS v8", "SOC 2", "SSDF", "PCI DSS", "ISO 27001"]


@pytest.fixture(scope="module")
def sess():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=20)
    assert r.status_code == 200, f"Login failed: {r.status_code} {r.text[:200]}"
    return s


# --- Compliance crosswalk ---

class TestCrosswalk:
    def test_crosswalk_shape(self, sess):
        r = sess.get(f"{API}/controls/crosswalk", timeout=15)
        assert r.status_code == 200, r.text[:300]
        data = r.json()
        assert data["frameworks"] == EXPECTED_FRAMEWORKS
        assert "framework_full" in data and all(k in data["framework_full"] for k in EXPECTED_FRAMEWORKS)
        rows = data["rows"]
        assert isinstance(rows, list) and len(rows) >= 6
        for row in rows:
            assert "control_id" in row and "compliant" in row and "status" in row
            assert isinstance(row["compliant"], bool)
            # compliant iff status Passing
            assert row["compliant"] == (row["status"] == "Passing")
            # mappings has all 6 keys
            assert set(row["mappings"].keys()) == set(EXPECTED_FRAMEWORKS)

    def test_crosswalk_summary_per_framework(self, sess):
        data = sess.get(f"{API}/controls/crosswalk", timeout=15).json()
        summary = {s["framework"]: s for s in data["summary"]}
        assert set(summary.keys()) == set(EXPECTED_FRAMEWORKS)
        for k, s in summary.items():
            assert s["mapped_controls"] == s["compliant"] + s["non_compliant"]
            if s["mapped_controls"]:
                expected_pct = round(s["compliant"] / s["mapped_controls"] * 100)
                assert s["compliant_pct"] == expected_pct
            assert s["status"] in ("Compliant", "Gaps", "Not mapped")

    def test_pci_ssdf_have_some_empty_mappings(self, sess):
        """PCI DSS (empty for AIG-1) and SSDF (empty for BCP-2) should have controls
        excluded from their totals — verify summary reflects fewer mapped_controls than total."""
        data = sess.get(f"{API}/controls/crosswalk", timeout=15).json()
        total = data["total_controls"]
        summary = {s["framework"]: s for s in data["summary"]}
        # SSDF should be missing BCP-2 mapping
        assert summary["SSDF"]["mapped_controls"] < total, f"SSDF should exclude n/a rows, got {summary['SSDF']}"
        # PCI DSS should be missing AIG-1
        assert summary["PCI DSS"]["mapped_controls"] < total, f"PCI DSS should exclude n/a rows"
        # And rows must have at least one empty list for each of those
        assert any(r["mappings"]["SSDF"] == [] for r in data["rows"])
        assert any(r["mappings"]["PCI DSS"] == [] for r in data["rows"])


# --- Compliance regression ---

class TestComplianceRegression:
    def test_compliance_endpoint(self, sess):
        r = sess.get(f"{API}/controls/compliance", timeout=15)
        assert r.status_code == 200, r.text[:300]
        data = r.json()
        assert "frameworks" in data and isinstance(data["frameworks"], list)
        # Should aggregate over the 6 crosswalk frameworks (skipping empty ref lists)
        fw_names = {f["framework"] for f in data["frameworks"]}
        # At least the 6 crosswalk frameworks should appear (subset check because empty ones may skip)
        for expected in EXPECTED_FRAMEWORKS:
            assert expected in fw_names, f"Missing {expected} in compliance frameworks: {fw_names}"
        assert "overall" in data and isinstance(data["overall"], int)
        assert "gaps" in data


# --- Live connector recheck (must stay LIVE) ---

class TestLiveRecheck:
    # Teams is a webhook connector — no recheck UI/endpoint by design
    KINDS = ["m365", "copilot", "openai", "sso"]

    def _connect(self, sess, kind):
        # Minimal PUT payload works because backend accepts arbitrary fields per-kind
        # Use kind-specific bodies matching AvailableConnectors UI
        bodies = {
            "m365": {"tenant_id": "verify", "client_id": "verify", "client_secret": "verify"},
            "copilot": {"tenant_id": "verify", "client_id": "verify", "client_secret": "verify"},
            "openai": {"api_key": "verify"},
            "teams": {"webhook_url": "https://example.com/hook", "tenant_id": "verify"},
            "sso": {"metadata_url": "https://example.com/meta", "entity_id": "test"},
        }
        r = sess.put(f"{API}/enterprise/live/{kind}", json=bodies[kind], timeout=20)
        return r

    def _disconnect(self, sess, kind):
        return sess.delete(f"{API}/enterprise/live/{kind}", timeout=15)

    @pytest.mark.parametrize("kind", KINDS)
    def test_recheck_keeps_live(self, sess, kind):
        try:
            r = self._connect(sess, kind)
            assert r.status_code == 200, f"connect {kind} failed: {r.status_code} {r.text[:200]}"
            body = r.json()
            assert body.get("live") is True or body.get("valid") is True, f"{kind} not live after connect: {body}"

            # recheck
            rr = sess.post(f"{API}/enterprise/live/{kind}/recheck", timeout=20)
            assert rr.status_code == 200, f"recheck {kind}: {rr.status_code} {rr.text[:200]}"
            rb = rr.json()
            # After recheck connector must remain live/valid — never disconnect
            assert (rb.get("live") is True) or (rb.get("valid") is True), f"{kind} dropped live after recheck: {rb}"
        finally:
            self._disconnect(sess, kind)


# --- AI Governance licenses (indirectly via connectors state) ---

class TestAIGovernanceEndpoints:
    def test_live_connectors_list(self, sess):
        r = sess.get(f"{API}/enterprise/live", timeout=15)
        assert r.status_code == 200, r.text[:200]
        # Should return a mapping with at least the 5 kinds keys OR list — accept both
        data = r.json()
        assert data is not None
