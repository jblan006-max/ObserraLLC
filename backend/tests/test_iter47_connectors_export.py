"""Iter47 — Connector catalog + auto-discover + connect + ledger export + regressions."""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://cyber-dashboard-48.preview.emergentagent.com").rstrip("/")
ADMIN_EMAIL = "jblan2026@gmail.com"
ADMIN_PASSWORD = "Obserra2026!"


@pytest.fixture(scope="module")
def admin_session():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login",
               json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=30)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text[:200]}"
    yield s
    # teardown: restore dep-ecdsa to Open
    try:
        s.post(f"{BASE_URL}/api/risk-engine/task/dep-ecdsa/status",
               json={"status": "Open"}, timeout=15)
    except Exception:
        pass


# ---------- Connector catalog ----------
def test_catalog_shape(admin_session):
    r = admin_session.get(f"{BASE_URL}/api/connectors/catalog", timeout=30)
    assert r.status_code == 200
    d = r.json()
    assert d["total"] >= 30, f"expected ~36 connectors, got {d['total']}"
    assert d["total"] == len(d["items"])
    cats = {c["name"] for c in d["categories"]}
    assert len(cats) >= 8, f"expected ~10 categories, got {cats}"
    # each item shape
    ids = {i["id"] for i in d["items"]}
    for req in ("stripe", "github", "clerk", "okta"):
        assert req in ids, f"missing {req}"
    sample = next(i for i in d["items"] if i["id"] == "stripe")
    for k in ("manifest", "auth", "capabilities", "health", "failure_class",
              "connection_state", "fields", "state"):
        assert k in sample, f"stripe missing key {k}"
    assert "stripe" in str(sample["manifest"].get("provider_id", "")).lower()


def test_discover_live_probes(admin_session):
    r = admin_session.post(f"{BASE_URL}/api/connectors/discover", timeout=120)
    assert r.status_code == 200, r.text[:300]
    d = r.json()
    summary = d["summary"]
    print("discover summary:", summary)
    # Stripe should connect via env STRIPE_SECRET_KEY
    assert summary.get("connected", 0) >= 1, f"expected >=1 connected (Stripe), got {summary}"
    stripe = next(x for x in d["results"] if x["id"] == "stripe")
    assert stripe["state"] == "connected", f"stripe not connected: {stripe}"
    assert stripe["http_status"] == 200
    # crowdstrike/zscaler etc → credentials_required
    for cid in ("crowdstrike", "zscaler"):
        row = next((x for x in d["results"] if x["id"] == cid), None)
        if row:
            assert row["state"] in ("credentials_required",), \
                f"{cid} should be credentials_required, got {row['state']}"
            assert row["failure_class"] == "invalid-configuration"
    # catalog reflects connected count
    cat = admin_session.get(f"{BASE_URL}/api/connectors/catalog", timeout=30).json()
    assert cat["connected"] >= 1
    stripe_cat = next(i for i in cat["items"] if i["id"] == "stripe")
    assert stripe_cat["state"] == "connected"
    # ledger has connector-discover
    lg = admin_session.get(f"{BASE_URL}/api/risk-engine/ledger", timeout=15).json()
    entries = lg.get("entries") or lg
    if isinstance(entries, dict):
        entries = entries.get("entries", [])
    actions = [e.get("action") for e in entries]
    assert "connector-discover" in actions, f"no connector-discover in ledger, actions={actions[:10]}"


def test_connect_github_bogus_token_is_honest(admin_session):
    r = admin_session.post(f"{BASE_URL}/api/connectors/github/connect",
                           json={"creds": {"token": "ghp_thisIsABogusTokenForTest12345678"}}, timeout=30)
    assert r.status_code == 200
    d = r.json()
    print("github connect:", d)
    assert d["state"] != "connected", f"github should NOT be connected with fake token: {d}"
    assert d["state"] in ("auth_failed", "error", "unreachable")
    assert d.get("detail")
    # catalog reflects it
    cat = admin_session.get(f"{BASE_URL}/api/connectors/catalog", timeout=30).json()
    gh = next(i for i in cat["items"] if i["id"] == "github")
    assert gh["state"] != "connected"


def test_connector_test_and_disconnect(admin_session):
    # test uses saved creds
    r = admin_session.post(f"{BASE_URL}/api/connectors/github/test", timeout=30)
    assert r.status_code == 200
    d = r.json()
    assert d["state"] != "connected"
    # disconnect clears state
    r2 = admin_session.post(f"{BASE_URL}/api/connectors/github/disconnect", timeout=15)
    assert r2.status_code == 200 and r2.json().get("ok") is True
    cat = admin_session.get(f"{BASE_URL}/api/connectors/catalog", timeout=30).json()
    gh = next(i for i in cat["items"] if i["id"] == "github")
    assert gh["state"] in ("available",), f"post-disconnect state = {gh['state']}"


# ---------- Ledger export ----------
def test_ledger_export_csv(admin_session):
    r = admin_session.get(f"{BASE_URL}/api/risk-engine/ledger/export?format=csv", timeout=30)
    assert r.status_code == 200
    assert "text/csv" in r.headers.get("content-type", "")
    assert "attachment" in r.headers.get("content-disposition", "").lower()
    body = r.text
    assert "started_at" in body.split("\n", 1)[0]  # header
    assert "# integrity_sha256" in body


def test_ledger_export_pdf(admin_session):
    r = admin_session.get(f"{BASE_URL}/api/risk-engine/ledger/export?format=pdf", timeout=60)
    assert r.status_code == 200
    assert "application/pdf" in r.headers.get("content-type", "")
    assert r.content[:4] == b"%PDF"


def test_ledger_export_json(admin_session):
    r = admin_session.get(f"{BASE_URL}/api/risk-engine/ledger/export?format=json", timeout=30)
    assert r.status_code == 200
    d = r.json()
    assert "integrity_sha256" in d and len(d["integrity_sha256"]) == 64
    assert "entries" in d and isinstance(d["entries"], list)


# ---------- Regression: No-Mock core ----------
def test_dep_ecdsa_honest_failure(admin_session):
    r = admin_session.post(f"{BASE_URL}/api/risk-engine/task/dep-ecdsa/action",
                           json={"action": "remediate"}, timeout=60)
    assert r.status_code == 200
    d = r.json()
    assert d.get("ok") is False
    assert d.get("verified") is False
    msg = (d.get("message") or "").lower()
    assert "no fixed release" in msg or "no fixed" in msg, f"unexpected msg: {d}"


def test_economics_shape(admin_session):
    r = admin_session.get(f"{BASE_URL}/api/risk-engine/economics", timeout=30)
    assert r.status_code == 200
    d = r.json()
    econ = d.get("economics", d)
    assert econ.get("tprm", {}).get("total_premium") == 0
    roi = econ.get("spend", {}).get("blended_roi")
    assert roi is not None and 20 <= float(roi) <= 35, f"roi off: {roi}"
