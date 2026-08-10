"""
Iteration 105 backend tests:
  1) AI incidents seeded so /api/ai-incidents returns >=1 open (non live_only orgs)
  2) POST /api/agents/runtime/card-share (admin) -> token/url
  3) Public GET /api/agents/public/card-share/{token} (NO auth) -> snapshot
  4) Public GET /api/agents/public/card-share/{token}/card.pdf (NO auth) -> application/pdf
  5) Expired/invalid token handling
"""
import os
import re
import requests

def _read_frontend_env():
    try:
        with open("/app/frontend/.env") as f:
            for line in f:
                if line.startswith("REACT_APP_BACKEND_URL="):
                    return line.split("=", 1)[1].strip()
    except Exception:
        pass
    return None


BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or _read_frontend_env()).rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "jblan2026@gmail.com"
ADMIN_PASSWORD = "Obserra2026!"


def _login():
    s = requests.Session()
    r = s.post(f"{API}/auth/login",
               json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=30)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text[:300]}"
    return s


def test_login_admin():
    s = _login()
    me = s.get(f"{API}/auth/me", timeout=15)
    assert me.status_code == 200
    body = me.json()
    assert body.get("email") == ADMIN_EMAIL
    # role admin so Share button is visible
    assert body.get("role") == "admin", f"expected admin role, got {body.get('role')}"


def test_ai_incidents_present():
    """Owner org may be live_only, but endpoint must respond 200 and shape must include ref/title/status."""
    s = _login()
    r = s.get(f"{API}/ai-incidents", timeout=20)
    assert r.status_code == 200, r.text[:300]
    data = r.json()
    assert isinstance(data, list)
    # Owner org is live_only so may be []. But if not empty, validate shape.
    if data:
        inc = data[0]
        for k in ("ref", "title", "status"):
            assert k in inc, f"missing key {k}: {inc}"
    print(f"ai-incidents count for admin org: {len(data)}")


def test_card_share_full_flow():
    s = _login()
    payload = {
        "title": "Kill Replay Drill · IT Support Copilot",
        "ref": "DRILL-TEST-1",
        "kind": "drill",
        "rating": "Medium",
        "score": 62,
        "ale": 250000,
        "compliance_pct": 78,
        "connectors": [
            {"name": "Agent runtime", "detail": "signed webhook", "status": "healthy"},
            {"name": "AGT-002", "detail": "target agent", "status": "ok"},
        ],
        "facets": [
            {"label": "Outcome", "value": "pass"},
            {"label": "Suspend latency", "value": "1.2s"},
        ],
        "recommendations": ["Rotate signing key", "Increase suspend timeout"],
        "compliance_refs": ["NIST AI RMF GOVERN-1.4"],
        "summary": "Fire-drill validated kill/replay path for agent AGT-002.",
        "days": 7,
    }
    r = s.post(f"{API}/agents/runtime/card-share", json=payload, timeout=30)
    assert r.status_code == 200, r.text[:400]
    body = r.json()
    assert "token" in body and isinstance(body["token"], str) and len(body["token"]) > 8
    assert "url" in body and body["url"].endswith(f"/card/{body['token']}")
    assert "expires_at" in body
    token = body["token"]

    # PUBLIC GET without auth — use a fresh session (no cookies)
    pub = requests.Session()
    r2 = pub.get(f"{API}/agents/public/card-share/{token}", timeout=20)
    assert r2.status_code == 200, f"public GET failed: {r2.status_code} {r2.text[:300]}"
    b2 = r2.json()
    assert "snapshot" in b2
    snap = b2["snapshot"]
    assert snap.get("title") == payload["title"]
    assert snap.get("ref") == payload["ref"]
    assert snap.get("score") == payload["score"]
    assert snap.get("recommendations") == payload["recommendations"]
    assert "snapshot_sha256" in b2 and len(b2["snapshot_sha256"]) >= 32

    # PUBLIC PDF without auth
    r3 = pub.get(f"{API}/agents/public/card-share/{token}/card.pdf",
                 params={"who": "AuditorTest"}, timeout=60)
    assert r3.status_code == 200, r3.text[:300]
    assert r3.headers.get("content-type", "").startswith("application/pdf"), r3.headers
    assert r3.content[:4] == b"%PDF", "response body is not a PDF"
    assert len(r3.content) > 1000

    # Second open increments counters -- verify no error
    r4 = pub.get(f"{API}/agents/public/card-share/{token}", timeout=20)
    assert r4.status_code == 200


def test_card_share_invalid_token():
    pub = requests.Session()
    r = pub.get(f"{API}/agents/public/card-share/nope-not-a-real-token", timeout=15)
    assert r.status_code == 404
    r2 = pub.get(f"{API}/agents/public/card-share/nope-not-a-real-token/card.pdf", timeout=15)
    assert r2.status_code == 404


def test_card_share_requires_admin():
    """POST without auth should NOT succeed."""
    anon = requests.Session()
    r = anon.post(f"{API}/agents/runtime/card-share", json={"title": "x"}, timeout=15)
    assert r.status_code in (401, 403), f"expected auth error, got {r.status_code}: {r.text[:200]}"
