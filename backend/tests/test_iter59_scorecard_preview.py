"""iter59: scorecard + digest preview + mover-rule report."""
import os, re, requests, pytest

BASE = os.environ.get("REACT_APP_BACKEND_URL", "https://cyber-dashboard-48.preview.emergentagent.com").rstrip("/")
EMAIL = "jblan2026@gmail.com"
PASS = "Obserra2026!"


@pytest.fixture(scope="module")
def sess():
    s = requests.Session()
    r = s.post(f"{BASE}/api/auth/login", json={"email": EMAIL, "password": PASS}, timeout=30)
    assert r.status_code == 200, r.text
    return s


# --- Scorecard ---
def test_scorecard(sess):
    r = sess.get(f"{BASE}/api/sap/scorecard", timeout=30)
    assert r.status_code == 200, r.text
    d = r.json()
    # governance score present + meaningful
    gs = (d.get("current") or {}).get("governance_score") or d.get("governance_score")
    assert gs is not None and gs != 0, f"governance_score not meaningful: {d}"
    # trend has 8 points
    trend = d.get("trend") or d.get("series") or []
    assert isinstance(trend, list) and len(trend) == 8, f"trend length {len(trend)}"
    # source chip
    src = (d.get("trend_source") or d.get("source") or "").lower()
    assert src in ("live", "derived"), f"trend_source={src}"


def test_scorecard_export(sess):
    r = sess.get(f"{BASE}/api/sap/scorecard/export?format=csv", timeout=30)
    assert r.status_code == 200
    assert "text/csv" in r.headers.get("content-type", "").lower()
    assert len(r.text) > 20


# --- Digest preview ---
def test_digest_preview(sess):
    r = sess.get(f"{BASE}/api/sap/digest/preview", timeout=30)
    assert r.status_code == 200, r.text
    ct = r.headers.get("content-type", "").lower()
    body = r.text if "html" in ct else (r.json().get("html") or r.json().get("body") or "")
    assert body and len(body) > 500, f"preview body too small: len={len(body)}"
    assert "<" in body and ">" in body


# --- Governance digest send (may be throttled) ---
def test_digest_send(sess):
    r = sess.post(f"{BASE}/api/sap/governance-digest/send", json={}, timeout=60)
    assert r.status_code == 200, r.text
    d = r.json()
    assert ("ok" in d) or ("throttled" in d) or ("sent" in d)


# --- Mover rule ---
def test_mover_rule_get(sess):
    r = sess.get(f"{BASE}/api/sap/mover-rule", timeout=30)
    assert r.status_code == 200
    d = r.json()
    assert "enabled" in d or "rule" in d or "config" in d


# --- Regression endpoints ---
@pytest.mark.parametrize("path", [
    "/api/sap/sod/conflicts",
    "/api/sap/autoremediation",
    "/api/sap/workflow/activity",
    "/api/sap/identities",
    "/api/sap/jml",
    "/api/sap/digest/config",
    "/api/sap/systems",
])
def test_regression(sess, path):
    r = sess.get(f"{BASE}{path}", timeout=30)
    assert r.status_code == 200, f"{path} -> {r.status_code} {r.text[:200]}"
