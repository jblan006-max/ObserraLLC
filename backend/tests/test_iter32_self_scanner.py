"""Iteration 32 — self vulnerability scanner + scan→compliance auto-update + advisor rename regression."""
import os
import time
import pytest
import requests

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") if False else "https://cyber-dashboard-48.preview.emergentagent.com"
# Prefer env var if provided
BASE = os.environ.get("REACT_APP_BACKEND_URL", BASE).rstrip("/")

ADMIN = {"email": "jblan2026@gmail.com", "password": "Obserra2026!"}


@pytest.fixture(scope="module")
def sess():
    s = requests.Session()
    r = s.post(f"{BASE}/api/auth/login", json=ADMIN, timeout=15)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text[:200]}"
    return s


# --- Self scanner ---
class TestSelfScanner:
    def test_run_scan(self, sess):
        r = sess.post(f"{BASE}/api/self-scan/run", timeout=90)
        assert r.status_code == 200, r.text[:300]
        d = r.json()
        assert isinstance(d.get("score"), int)
        s = d["summary"]
        for k in ["critical", "high", "medium", "low", "info", "passed",
                  "total_checks", "dependencies_scanned", "vulnerable_dependencies"]:
            assert k in s, f"missing summary key {k}"
        assert isinstance(d.get("findings"), list) and len(d["findings"]) > 0
        assert isinstance(d.get("kev_matches"), list)
        assert isinstance(d.get("remediated"), list)
        # each finding shape
        for f in d["findings"]:
            for k in ["id", "severity", "status", "evidence", "cve_ids",
                      "kev", "remediation", "control_refs"]:
                assert k in f, f"finding missing {k}: {f}"
        # security headers + CORS should PASS (per request)
        by_id = {f["id"]: f for f in d["findings"]}
        assert by_id.get("sec-headers", {}).get("status") == "pass", by_id.get("sec-headers")
        assert by_id.get("cors", {}).get("status") == "pass", by_id.get("cors")
        pytest.scan_data = d

    def test_latest(self, sess):
        r = sess.get(f"{BASE}/api/self-scan/latest", timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert d.get("id"), "latest scan should exist"
        assert d.get("score") == pytest.scan_data["score"]

    def test_history(self, sess):
        r = sess.get(f"{BASE}/api/self-scan/history", timeout=15)
        assert r.status_code == 200
        assert isinstance(r.json(), list)


# --- Compliance auto-update from scan ---
class TestScanCompliance:
    def test_crosswalk_reflects_scan(self, sess):
        r = sess.get(f"{BASE}/api/controls/crosswalk", timeout=15)
        assert r.status_code == 200
        d = r.json()
        # summary should include six frameworks, each meeting_pct >= 96
        summary = d.get("summary") or d.get("frameworks") or d
        # Try both shapes
        items = summary if isinstance(summary, list) else (
            d.get("summary") if isinstance(d.get("summary"), list) else [])
        assert items, f"unexpected crosswalk shape keys={list(d)[:8]}"
        assert len(items) >= 6
        for fw in items:
            pct = fw.get("meeting_pct")
            assert pct is not None and pct >= 96, f"{fw.get('framework')} pct={pct}"

    def test_framework_shows_self_scan_source(self, sess):
        # NIST SC-7 should be aligned via self-scan (headers/CORS pass)
        r = sess.get(f"{BASE}/api/controls/framework/NIST 800-53", timeout=15)
        assert r.status_code == 200
        d = r.json()
        controls = d.get("controls") or []
        assert controls, "no controls returned"
        # Look for a self-scan sourced control
        selfscan_ctrls = [c for c in controls if c.get("source") == "self-scan"]
        assert len(selfscan_ctrls) > 0, "expected some controls with source=self-scan"


# --- Remediation toggle ---
class TestRemediation:
    def test_toggle_remediation(self, sess):
        # pick any failing finding from latest scan
        latest = sess.get(f"{BASE}/api/self-scan/latest", timeout=15).json()
        fails = [f for f in latest.get("findings", []) if f["status"] == "fail"]
        if not fails:
            pytest.skip("no failing findings to remediate")
        fid = fails[0]["id"]
        r = sess.post(f"{BASE}/api/self-scan/remediate",
                      json={"finding_id": fid, "done": True}, timeout=15)
        assert r.status_code == 200, r.text[:300]
        assert fid in r.json().get("remediated", [])
        # reverse
        r = sess.post(f"{BASE}/api/self-scan/remediate",
                      json={"finding_id": fid, "done": False}, timeout=15)
        assert r.status_code == 200
        assert fid not in r.json().get("remediated", [])

    def test_bad_finding_id(self, sess):
        r = sess.post(f"{BASE}/api/self-scan/remediate",
                      json={"finding_id": "nope-xxx", "done": True}, timeout=15)
        assert r.status_code == 404


# --- Regressions ---
class TestRegressions:
    def test_auth_me(self, sess):
        r = sess.get(f"{BASE}/api/auth/me", timeout=10)
        assert r.status_code == 200
        assert r.json().get("email") == ADMIN["email"]

    def test_controls_crosswalk(self, sess):
        r = sess.get(f"{BASE}/api/controls/crosswalk", timeout=15)
        assert r.status_code == 200

    def test_enterprise_live(self, sess):
        r = sess.get(f"{BASE}/api/enterprise/live", timeout=15)
        assert r.status_code == 200

    def test_team(self, sess):
        r = sess.get(f"{BASE}/api/team", timeout=15)
        assert r.status_code in (200, 404)  # tolerate absence

    def test_cors_preflight(self, sess):
        r = requests.options(
            f"{BASE}/api/auth/me",
            headers={"Origin": "https://cyber-dashboard-48.preview.emergentagent.com",
                     "Access-Control-Request-Method": "GET",
                     "Access-Control-Request-Headers": "content-type"},
            timeout=10)
        assert r.status_code in (200, 204), r.status_code
        # Preview ingress handles preflight; either wildcard or explicit origin is acceptable
        aco = r.headers.get("access-control-allow-origin")
        assert aco is not None

    def test_advisor(self, sess):
        # advisor still responds
        r = sess.post(f"{BASE}/api/advisor/chat",
                      json={"message": "hi"}, timeout=60)
        # accept 200 or a graceful 402/429/503 if quota exhausted
        assert r.status_code in (200, 402, 429, 503), r.text[:200]
