"""Iter 33 — Security Scanner + Autonomous Engine + Assets endpoints."""
import os, time
import pytest
import requests

def _read_frontend_env():
    p = "/app/frontend/.env"
    if os.path.exists(p):
        for line in open(p):
            if line.startswith("REACT_APP_BACKEND_URL="):
                return line.split("=", 1)[1].strip()
    return None

BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or _read_frontend_env()).rstrip("/")
ADMIN = {"email": "jblan2026@gmail.com", "password": "Obserra2026!"}


@pytest.fixture(scope="module")
def admin_session():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json=ADMIN, timeout=30)
    assert r.status_code == 200, f"login failed {r.status_code} {r.text[:200]}"
    return s


# ---------- Ping (unauth) ----------
def test_ping_unauth():
    r = requests.get(f"{BASE_URL}/api/self-scan/ping", timeout=15)
    assert r.status_code == 200
    assert r.json().get("ok") is True


# ---------- Live scan ----------
def test_run_live_scan(admin_session):
    r = admin_session.post(f"{BASE_URL}/api/self-scan/run", timeout=90)
    assert r.status_code == 200, r.text[:300]
    d = r.json()
    assert isinstance(d.get("score"), int)
    assert 0 <= d["score"] <= 100
    assert d.get("endpoint")
    assert "localhost" not in (d.get("endpoint") or "").lower(), f"endpoint should be public url, got {d.get('endpoint')}"
    assert isinstance(d.get("findings"), list) and len(d["findings"]) > 0
    # MITRE ATT&CK + CWE aggregated on scan doc
    assert isinstance(d.get("mitre_techniques"), list)
    assert isinstance(d.get("cwe_ids"), list)
    assert len(d["mitre_techniques"]) > 0
    assert len(d["cwe_ids"]) > 0
    # Each failing finding has mitre + cwe chips
    fails = [f for f in d["findings"] if f["status"] == "fail"]
    for f in fails:
        assert isinstance(f.get("mitre"), list) and len(f["mitre"]) > 0, f"finding {f['id']} missing mitre"
        assert isinstance(f.get("cwe"), list) and len(f["cwe"]) > 0, f"finding {f['id']} missing cwe"
        assert "cve_ids" in f
        assert "kev" in f


def test_latest_scan(admin_session):
    r = admin_session.get(f"{BASE_URL}/api/self-scan/latest", timeout=30)
    assert r.status_code == 200
    d = r.json()
    assert d.get("id")
    assert isinstance(d.get("findings"), list)


# ---------- Engine ----------
def test_engine_get_bootstrap(admin_session):
    r = admin_session.get(f"{BASE_URL}/api/self-scan/engine", timeout=30)
    assert r.status_code == 200
    d = r.json()
    eng = d.get("engine") or {}
    assert eng.get("enabled") is True, "engine should be auto-enabled by first-install bootstrap"
    assert d.get("endpoint")
    assert "localhost" not in d["endpoint"].lower()
    # pending is a list
    assert isinstance(d.get("pending"), list)


def test_engine_pause_blocks_run(admin_session):
    # Pause
    r = admin_session.put(f"{BASE_URL}/api/self-scan/engine", json={"paused": True}, timeout=15)
    assert r.status_code == 200
    assert r.json().get("paused") is True
    # Run should be blocked with 400
    r2 = admin_session.post(f"{BASE_URL}/api/self-scan/engine/run", timeout=15)
    assert r2.status_code == 400
    # Resume
    r3 = admin_session.put(f"{BASE_URL}/api/self-scan/engine", json={"paused": False}, timeout=15)
    assert r3.status_code == 200
    assert r3.json().get("paused") is False


def test_engine_autoapply_toggle(admin_session):
    r = admin_session.put(f"{BASE_URL}/api/self-scan/engine", json={"auto_apply_config": True}, timeout=15)
    assert r.status_code == 200
    assert r.json().get("auto_apply_config") is True


def test_engine_run_now(admin_session):
    # Ensure engine enabled & not paused
    admin_session.put(f"{BASE_URL}/api/self-scan/engine", json={"enabled": True, "paused": False}, timeout=15)
    r = admin_session.post(f"{BASE_URL}/api/self-scan/engine/run", timeout=120)
    assert r.status_code == 200
    d = r.json()
    assert "score" in d
    assert isinstance(d.get("applied"), list)
    assert isinstance(d.get("queued"), list)


# ---------- Approvals ----------
def test_pending_approvals_present(admin_session):
    r = admin_session.get(f"{BASE_URL}/api/self-scan/engine", timeout=30)
    assert r.status_code == 200
    pending = r.json().get("pending") or []
    # Expected dependency approvals (starlette, ecdsa) per install scan
    kinds = {p.get("kind") for p in pending}
    assert any(p.get("kind") == "dependency" for p in pending), f"expected dependency approvals, got {pending}"
    ids = [p["id"] for p in pending if p.get("kind") == "dependency"]
    assert ids, "no dependency approval ids"


def test_reject_approval(admin_session):
    r = admin_session.get(f"{BASE_URL}/api/self-scan/engine", timeout=30)
    pending = r.json().get("pending") or []
    if not pending:
        pytest.skip("no pending approvals to reject")
    target = pending[0]
    r2 = admin_session.post(f"{BASE_URL}/api/self-scan/upgrade/approve",
                            json={"approval_id": target["id"], "approve": False}, timeout=30)
    assert r2.status_code == 200
    assert r2.json().get("status") == "rejected"


# ---------- Remediate ----------
def test_remediate_toggle(admin_session):
    latest = admin_session.get(f"{BASE_URL}/api/self-scan/latest", timeout=15).json()
    fails = [f for f in latest.get("findings", []) if f["status"] == "fail"]
    if not fails:
        pytest.skip("no failing findings")
    fid = fails[0]["id"]
    r = admin_session.post(f"{BASE_URL}/api/self-scan/remediate",
                           json={"finding_id": fid, "done": True}, timeout=15)
    assert r.status_code == 200
    assert fid in r.json().get("remediated", [])
    # reopen
    r2 = admin_session.post(f"{BASE_URL}/api/self-scan/remediate",
                            json={"finding_id": fid, "done": False}, timeout=15)
    assert r2.status_code == 200
    assert fid not in r2.json().get("remediated", [])


def test_remediate_unknown(admin_session):
    r = admin_session.post(f"{BASE_URL}/api/self-scan/remediate",
                           json={"finding_id": "no-such-finding-xyz", "done": True}, timeout=15)
    assert r.status_code == 404


# ---------- Assets overview ----------
def test_assets_overview(admin_session):
    r = admin_session.get(f"{BASE_URL}/api/self-scan/assets", timeout=45)
    assert r.status_code == 200
    d = r.json()
    assert "sources" in d
    assert "devices" in d
    assert "overview" in d
    ov = d["overview"]
    assert "security_score" in ov
    assert "app_health" in ov
    assert "compliance_pct" in ov
    # Sources present per bootstrap
    assert isinstance(d["sources"], list)
    assert d.get("total_sources", 0) >= 0
    # Devices: either items available or note (Intune not connected)
    dv = d["devices"]
    assert (dv.get("available") is True) or dv.get("note")
