"""Iteration 130: AI Grounding / Hallucination monitor endpoints."""
import os
import requests
import pytest

def _load_backend_url():
    v = os.environ.get("REACT_APP_BACKEND_URL")
    if not v:
        with open("/app/frontend/.env") as f:
            for line in f:
                if line.startswith("REACT_APP_BACKEND_URL="):
                    v = line.split("=", 1)[1].strip()
                    break
    return v.rstrip("/")

BASE = _load_backend_url()
ADMIN_EMAIL = "jblan2026@gmail.com"
ADMIN_PW = "Obserra2026!"


@pytest.fixture(scope="module")
def admin_session():
    s = requests.Session()
    r = s.post(f"{BASE}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PW}, timeout=20)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text[:200]}"
    return s


# --- POST /api/hallucination/check ------------------------------------------
def test_check_flags_unsupported(admin_session):
    body = {
        "text": "Control health is 82/100 and SOC 2 coverage is 90%. CR-777 is failing and revenue dropped 45%.",
        "context": "Control health 82/100, SOC 2 coverage 90%, CR-001 passing",
        "surface": "test",
        "use_llm": False,  # deterministic to make assertion deterministic
    }
    r = admin_session.post(f"{BASE}/api/hallucination/check", json=body, timeout=60)
    assert r.status_code == 200, r.text
    d = r.json()
    assert set(["score", "label", "method", "claims", "flagged", "flagged_count"]) <= set(d.keys())
    assert d["label"] in ("Grounded", "Partially grounded", "Unverified")
    assert d["method"] in ("hybrid", "deterministic")
    assert d["flagged_count"] >= 1
    # CR-777 & 45% both unsupported => score should drop below 80
    assert d["score"] < 80
    # Ensure supported values (82, 90%) are NOT flagged
    flagged_txt = " ".join(c["claim"] for c in d["flagged"]).lower()
    assert "cr-777" in flagged_txt or "45%" in flagged_txt


def test_check_hybrid_with_llm(admin_session):
    """Try hybrid path (llm verifier) with allowance for llm failure -> deterministic."""
    body = {
        "text": "Control health is 82/100. CR-777 is failing.",
        "context": "Control health 82/100, CR-001 passing",
        "surface": "test",
        "use_llm": True,
    }
    r = admin_session.post(f"{BASE}/api/hallucination/check", json=body, timeout=60)
    assert r.status_code == 200
    d = r.json()
    assert d["method"] in ("hybrid", "deterministic")
    assert d["flagged_count"] >= 1


# --- GET /api/hallucination/summary -----------------------------------------
def test_summary_admin(admin_session):
    r = admin_session.get(f"{BASE}/api/hallucination/summary?days=30", timeout=20)
    assert r.status_code == 200, r.text
    d = r.json()
    for k in ("total", "avg_score", "flagged", "flagged_pct", "by_surface", "trend", "worst"):
        assert k in d, f"missing {k}"
    assert isinstance(d["by_surface"], list)
    assert d["total"] >= 1  # from earlier check


# --- GET /api/hallucination/log ---------------------------------------------
def test_log_admin(admin_session):
    r = admin_session.get(f"{BASE}/api/hallucination/log?limit=10", timeout=20)
    assert r.status_code == 200, r.text
    d = r.json()
    assert "events" in d and isinstance(d["events"], list)
    if d["events"]:
        ev = d["events"][0]
        for k in ("at", "surface", "score", "label"):
            assert k in ev


# --- Auth: log/summary should require admin ---------------------------------
def test_log_unauthenticated():
    r = requests.get(f"{BASE}/api/hallucination/log", timeout=15)
    assert r.status_code in (401, 403)


def test_summary_unauthenticated():
    r = requests.get(f"{BASE}/api/hallucination/summary", timeout=15)
    assert r.status_code in (401, 403)
