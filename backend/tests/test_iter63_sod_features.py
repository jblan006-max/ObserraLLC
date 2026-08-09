"""Backend smoke tests for iteration 63 SoD features: mute/unmute, approve/unapprove, forecast, preview, why."""
import os
import requests
import pytest

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    # fall back to reading /app/frontend/.env
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                BASE_URL = line.split("=", 1)[1].strip().rstrip("/")

API = f"{BASE_URL}/api"
EMAIL = "jblan2026@gmail.com"
PASS = "Obserra2026!"


@pytest.fixture(scope="module")
def sess():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": EMAIL, "password": PASS}, timeout=15)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    return s


def test_scorecard_forecast(sess):
    r = sess.get(f"{API}/sap/scorecard", timeout=15)
    assert r.status_code == 200
    data = r.json()
    assert "forecast" in data, "scorecard missing forecast"
    fc = data["forecast"]
    assert "next_week_score" in fc and "delta" in fc
    assert isinstance(fc["next_week_score"], int)
    assert isinstance(fc["delta"], int)


def test_scorecard_why(sess):
    r = sess.get(f"{API}/sap/scorecard/why", timeout=30)
    assert r.status_code == 200
    data = r.json()
    assert "summary" in data and isinstance(data["summary"], str) and len(data["summary"]) > 5


def test_mute_unmute_flow(sess):
    # start clean
    sess.post(f"{API}/sap/scorecard/alert-unmute", json={}, timeout=15)
    r = sess.post(f"{API}/sap/scorecard/alert-mute", json={"hours": 24, "reason": "TEST_mute"}, timeout=15)
    assert r.status_code == 200, r.text
    g = sess.get(f"{API}/sap/scorecard/alerts", timeout=15)
    assert g.status_code == 200
    d = g.json()
    assert d.get("muted") is True
    assert d.get("mute_until")
    assert d.get("mute_reason") == "TEST_mute"

    # while muted, alert-check should not post
    ac = sess.post(f"{API}/sap/scorecard/alert-check", json={}, timeout=15)
    assert ac.status_code == 200
    # unmute
    u = sess.post(f"{API}/sap/scorecard/alert-unmute", json={}, timeout=15)
    assert u.status_code == 200
    g2 = sess.get(f"{API}/sap/scorecard/alerts", timeout=15)
    assert g2.json().get("muted") is False


def test_evidence_approve_unapprove(sess):
    # set prepared_by first via digest config
    cfg = sess.get(f"{API}/sap/digest/config", timeout=15).json().get("config", {})
    cfg2 = dict(cfg)
    cfg2["evidence_prepared_by"] = "TEST_PrepUser"
    put = sess.put(f"{API}/sap/digest/config", json=cfg2, timeout=15)
    assert put.status_code == 200, put.text

    r = sess.post(f"{API}/sap/sod-evidence/approve", json={"approved_by": "TEST_Approver"}, timeout=15)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d.get("approved_by") == "TEST_Approver"

    # verify config reflects approver
    c2 = sess.get(f"{API}/sap/digest/config", timeout=15).json().get("config", {})
    assert c2.get("evidence_approved_by") == "TEST_Approver"

    # unapprove
    u = sess.post(f"{API}/sap/sod-evidence/unapprove", json={}, timeout=15)
    assert u.status_code == 200
    c3 = sess.get(f"{API}/sap/digest/config", timeout=15).json().get("config", {})
    assert not c3.get("evidence_approved_by")


def test_evidence_preview_with_scopes(sess):
    cfg = sess.get(f"{API}/sap/digest/config", timeout=15).json().get("config", {})
    cfg2 = dict(cfg)
    cfg2["evidence_recipients"] = ["test-auditor@example.com"]
    cfg2["recipients"] = cfg.get("recipients", []) or []
    cfg2["auditor_scopes"] = [{"email": "test-auditor@example.com", "areas": "Finance", "systems": "S4P"}]
    put = sess.put(f"{API}/sap/digest/config", json=cfg2, timeout=15)
    assert put.status_code == 200, put.text

    r = sess.get(f"{API}/sap/sod-evidence/preview", timeout=20)
    assert r.status_code == 200
    d = r.json()
    # should include recipients array or per-recipient details
    assert "recipients" in d or "detail" in d or "rows" in d, f"preview keys: {list(d.keys())}"
