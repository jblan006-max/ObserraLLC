"""Iter 71 — Analytics Split regression + Analytics Export + Watchlist Alerts + Remediate.

Covers:
1. Analytics Split regression (moved into sap_analytics.py) — /analytics + filters still 200.
2. Adjacent sap_uac endpoints still 200 (overview / access-monitoring / advisor / sod/conflicts).
3. NEW Analytics Export CSV + PDF (branded, honors filters).
4. NEW Watchlist Alerts (POST /watchlist/alert enable/disable, pin side-effect, 404).
5. NEW Watchlist Remediate (POST /watchlist/remediate — ticket + owner persisted, 404).
6. Refactor regression carried over from prior iters (ask/digest/evidence/scorecard/share).
7. Cleanup all pins.
"""
import os
import pytest
import requests


def _load_base():
    v = os.environ.get("REACT_APP_BACKEND_URL")
    if not v:
        with open("/app/frontend/.env") as f:
            for line in f:
                if line.startswith("REACT_APP_BACKEND_URL="):
                    v = line.split("=", 1)[1].strip()
                    break
    assert v, "REACT_APP_BACKEND_URL not set"
    return v.rstrip("/")


BASE = _load_base()
EMAIL = "jblan2026@gmail.com"
PASSWORD = "Obserra2026!"


@pytest.fixture(scope="module")
def sess():
    s = requests.Session()
    r = s.post(f"{BASE}/api/auth/login", json={"email": EMAIL, "password": PASSWORD}, timeout=30)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    yield s
    # Cleanup: unpin everything created during tests
    try:
        w = s.get(f"{BASE}/api/sap/watchlist", timeout=15).json()
        for p in w.get("pinned", []):
            s.delete(f"{BASE}/api/sap/watchlist", params={"area": p["area"]}, timeout=15)
    except Exception:
        pass


# ── 1. Analytics Split regression ────────────────────────────────────────────
def test_analytics_base(sess):
    r = sess.get(f"{BASE}/api/sap/analytics", timeout=30)
    assert r.status_code == 200
    d = r.json()
    assert "filters" in d and isinstance(d["filters"], dict)
    assert "regions" in d["filters"] and "departments" in d["filters"]
    assert d["filters"]["region"] == ""
    assert d["filters"]["department"] == ""
    assert "kpis" in d and "identities" in d["kpis"]


def test_analytics_region_emea(sess):
    r = sess.get(f"{BASE}/api/sap/analytics", params={"region": "EMEA"}, timeout=30)
    assert r.status_code == 200
    d = r.json()
    assert d["filters"]["region"] == "EMEA"
    # scoped
    base = sess.get(f"{BASE}/api/sap/analytics", timeout=30).json()
    assert d["kpis"]["identities"] <= base["kpis"]["identities"]
    assert d["kpis"]["identities"] > 0


def test_analytics_department_finance(sess):
    r = sess.get(f"{BASE}/api/sap/analytics", params={"department": "Finance"}, timeout=30)
    assert r.status_code == 200
    d = r.json()
    assert d["filters"]["department"] == "Finance"
    assert d["kpis"]["identities"] > 0


# ── 2. Adjacent endpoints that STAYED in sap_uac.py ───────────────────────────
def test_overview(sess):
    r = sess.get(f"{BASE}/api/sap/overview", timeout=30)
    assert r.status_code == 200


def test_access_monitoring(sess):
    r = sess.get(f"{BASE}/api/sap/access-monitoring", timeout=30)
    assert r.status_code == 200


def test_advisor(sess):
    r = sess.post(f"{BASE}/api/sap/advisor", json={"question": "What are the top SoD risks?"}, timeout=60)
    assert r.status_code == 200


def test_sod_conflicts(sess):
    r = sess.get(f"{BASE}/api/sap/sod/conflicts", timeout=30)
    assert r.status_code == 200


# ── 3. Analytics Export CSV / PDF (branded, filter-honoring) ─────────────────
def test_export_csv(sess):
    r = sess.get(f"{BASE}/api/sap/analytics/export", params={"format": "csv"}, timeout=45)
    assert r.status_code == 200
    assert "text/csv" in r.headers.get("Content-Type", "")
    cd = r.headers.get("Content-Disposition", "")
    assert "attachment" in cd and ".csv" in cd
    body = r.text
    assert "Obserra SAP UAC" in body
    assert "KPI" in body
    assert "Identities" in body


def test_export_csv_filtered(sess):
    r = sess.get(f"{BASE}/api/sap/analytics/export", params={"format": "csv", "region": "EMEA"}, timeout=45)
    assert r.status_code == 200
    assert "text/csv" in r.headers.get("Content-Type", "")
    assert "EMEA" in r.text  # slice label appears


def test_export_pdf(sess):
    r = sess.get(f"{BASE}/api/sap/analytics/export", params={"format": "pdf"}, timeout=60)
    assert r.status_code == 200
    assert "application/pdf" in r.headers.get("Content-Type", "")
    assert r.content[:4] == b"%PDF"
    assert len(r.content) > 1000


def test_export_pdf_filtered(sess):
    r = sess.get(f"{BASE}/api/sap/analytics/export",
                 params={"format": "pdf", "department": "Finance"}, timeout=60)
    assert r.status_code == 200
    assert r.content[:4] == b"%PDF"


# ── 4. Watchlist Alerts (new) ────────────────────────────────────────────────
def test_watchlist_alert_enable_and_disable(sess):
    # enable (also pins)
    r = sess.post(f"{BASE}/api/sap/watchlist/alert",
                  json={"area": "Finance", "alert": True, "threshold": 2}, timeout=30)
    assert r.status_code == 200
    w = r.json()
    fin = next((p for p in w["pinned"] if p["area"] == "Finance"), None)
    assert fin is not None, "Finance not pinned after alert enable"
    assert fin["alert"] is True
    assert fin["threshold"] == 2

    # persists on GET
    w2 = sess.get(f"{BASE}/api/sap/watchlist", timeout=15).json()
    fin2 = next((p for p in w2["pinned"] if p["area"] == "Finance"), None)
    assert fin2 and fin2["alert"] is True and fin2["threshold"] == 2

    # disable
    r = sess.post(f"{BASE}/api/sap/watchlist/alert",
                  json={"area": "Finance", "alert": False, "threshold": 2}, timeout=30)
    assert r.status_code == 200
    w3 = r.json()
    fin3 = next((p for p in w3["pinned"] if p["area"] == "Finance"), None)
    assert fin3 and fin3["alert"] is False


def test_watchlist_alert_unknown_area(sess):
    r = sess.post(f"{BASE}/api/sap/watchlist/alert",
                  json={"area": "NoSuchArea", "alert": True, "threshold": 1}, timeout=30)
    assert r.status_code == 404


# ── 5. Watchlist Remediate (new enhancement) ────────────────────────────────
def test_watchlist_remediate(sess):
    r = sess.post(f"{BASE}/api/sap/watchlist/remediate",
                  json={"area": "Finance", "owner": "jane@x.com"}, timeout=45)
    assert r.status_code == 200
    d = r.json()
    assert d["ok"] is True
    assert d["owner"] == "jane@x.com"
    assert "ticket" in d
    assert d["ticket"].get("number")
    assert d["ticket"].get("state")
    assert d["ticket"].get("type")

    # persistence check
    w = sess.get(f"{BASE}/api/sap/watchlist", timeout=15).json()
    fin = next((p for p in w["pinned"] if p["area"] == "Finance"), None)
    assert fin is not None
    assert fin["owner"] == "jane@x.com"
    assert fin.get("ticket") and fin["ticket"].get("number")


def test_watchlist_remediate_unknown(sess):
    r = sess.post(f"{BASE}/api/sap/watchlist/remediate",
                  json={"area": "BogusArea", "owner": "x@y.com"}, timeout=30)
    assert r.status_code == 404


# ── 6. Prior-refactor endpoints still respond 200 ─────────────────────────────
def test_prior_refactor_endpoints(sess):
    for path in ["/api/sap/ask-analytics", "/api/sap/digest/ask/intro",
                 "/api/sap/sod-evidence/preview", "/api/sap/scorecard"]:
        r = sess.get(f"{BASE}{path}", timeout=30)
        assert r.status_code == 200, f"{path} -> {r.status_code}"


def test_digest_ask_multiturn(sess):
    r = sess.post(f"{BASE}/api/sap/digest/ask",
                  json={"question": "Summarize open SoD risks.", "session_id": "iter71-a"}, timeout=60)
    assert r.status_code == 200


def test_digest_share(sess):
    r = sess.post(f"{BASE}/api/sap/digest/share", json={}, timeout=30)
    assert r.status_code == 200
