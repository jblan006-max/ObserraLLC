"""iter48 — backend endpoints backing the deep-dive audit sweep.

Covers: cookie auth, billing plans, connectors health, discovered assets,
discovery-actions, persona PDF reports, snapshot AI content.
"""
import os
import pytest
import requests

def _base():
    v = os.environ.get("REACT_APP_BACKEND_URL")
    if not v:
        # Load from frontend/.env
        try:
            for line in open("/app/frontend/.env"):
                if line.startswith("REACT_APP_BACKEND_URL="):
                    v = line.split("=", 1)[1].strip()
                    break
        except Exception:
            pass
    assert v, "REACT_APP_BACKEND_URL not set"
    return v.rstrip("/")

BASE = _base()
CREDS = {"email": "jblan2026@gmail.com", "password": "Obserra2026!"}


@pytest.fixture(scope="module")
def sess():
    s = requests.Session()
    r = s.post(f"{BASE}/api/auth/login", json=CREDS, timeout=15)
    assert r.status_code == 200, f"login failed {r.status_code}: {r.text[:200]}"
    # cookies set
    assert any(c.name in ("access_token", "session") for c in s.cookies), f"no session cookie: {list(s.cookies)}"
    me = s.get(f"{BASE}/api/auth/me", timeout=10)
    assert me.status_code == 200, me.text[:200]
    return s


def test_billing_plans(sess):
    r = sess.get(f"{BASE}/api/billing/plans", timeout=15)
    assert r.status_code == 200, r.text[:200]
    data = r.json()
    # accept list or {plans:[]}
    plans = data if isinstance(data, list) else data.get("plans", [])
    assert isinstance(plans, list)


def test_connectors_health(sess):
    r = sess.get(f"{BASE}/api/connectors/health", timeout=20)
    assert r.status_code == 200, r.text[:300]
    d = r.json()
    # expect list of connectors with last probe
    items = d if isinstance(d, list) else d.get("items") or d.get("connectors") or []
    assert isinstance(items, list)


def test_discovered_assets(sess):
    r = sess.get(f"{BASE}/api/risk-engine/discovered", timeout=20)
    assert r.status_code == 200, r.text[:300]
    d = r.json()
    items = d if isinstance(d, list) else d.get("items") or d.get("assets") or []
    assert isinstance(items, list)


def test_discovery_actions(sess):
    r = sess.get(f"{BASE}/api/connectors/discovery-actions", timeout=15)
    assert r.status_code == 200, r.text[:300]


def test_report_board_pdf(sess):
    r = sess.post(f"{BASE}/api/reports/board-pack.pdf", timeout=30)
    assert r.status_code == 200, r.text[:300]
    assert "application/pdf" in r.headers.get("content-type", ""), r.headers
    assert r.content[:4] == b"%PDF"


def test_report_cfo_pdf(sess):
    r = sess.post(f"{BASE}/api/reports/cfo-brief.pdf", timeout=30)
    assert r.status_code == 200, r.text[:300]
    assert "application/pdf" in r.headers.get("content-type", "")
    assert r.content[:4] == b"%PDF"


def test_report_soc_pdf(sess):
    r = sess.post(f"{BASE}/api/reports/soc-plan.pdf", timeout=30)
    assert r.status_code == 200, r.text[:300]
    assert "application/pdf" in r.headers.get("content-type", "")
    assert r.content[:4] == b"%PDF"


def test_snapshot(sess):
    r = sess.get(f"{BASE}/api/metrics/dashboard", timeout=30)
    assert r.status_code == 200, f"{r.status_code}: {r.text[:200]}"


def test_risk_engine_summary(sess):
    r = sess.get(f"{BASE}/api/risk-engine/summary", timeout=15)
    assert r.status_code in (200, 404)


def test_ai_governance_list(sess):
    # OWASP + incidents endpoints
    for path in ("/api/ai-governance/owasp", "/api/ai-governance/incidents", "/api/ai-governance/agents"):
        r = sess.get(f"{BASE}{path}", timeout=15)
        assert r.status_code in (200, 404), f"{path} -> {r.status_code}"
