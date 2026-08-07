"""Iter 9 tests — Cyber Risk, Studio (dashboard + report), Advisor (deep, opus-4-8)."""
import os
import json
import time
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    # Fallback for backend-run env — read frontend .env
    with open("/app/frontend/.env") as f:
        for ln in f:
            if ln.startswith("REACT_APP_BACKEND_URL="):
                BASE_URL = ln.split("=", 1)[1].strip().rstrip("/")

ADMIN = {"email": "jblan2026@gmail.com", "password": "Obserra2026!"}


@pytest.fixture(scope="module")
def admin_session():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json=ADMIN, timeout=15)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text[:200]}"
    return s


# ---------- Cyber Risk ----------
class TestCyber:
    def test_overview(self, admin_session):
        r = admin_session.get(f"{BASE_URL}/api/cyber/overview", timeout=15)
        assert r.status_code == 200, r.text
        d = r.json()
        for k in ["composition", "posture_score", "mitigation_pct",
                  "control_coverage", "open_risks", "total_risks", "risks"]:
            assert k in d, f"missing {k}"
        assert isinstance(d["composition"], list) and len(d["composition"]) >= 5
        assert isinstance(d["risks"], list)

    def test_treat_risk(self, admin_session):
        ov = admin_session.get(f"{BASE_URL}/api/cyber/overview", timeout=15).json()
        assert ov["risks"], "no risks seeded"
        ref = ov["risks"][0]["ref"]
        r = admin_session.post(f"{BASE_URL}/api/cyber/risks/{ref}/treat", timeout=15)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d.get("ok") is True and d.get("ref") == ref

    def test_treat_missing_risk(self, admin_session):
        r = admin_session.post(f"{BASE_URL}/api/cyber/risks/CR-DOES-NOT-EXIST/treat", timeout=15)
        assert r.status_code == 404


# ---------- Studio Dashboard ----------
class TestStudioDashboard:
    def test_get(self, admin_session):
        r = admin_session.get(f"{BASE_URL}/api/studio/dashboard", timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert "available" in d and "selected" in d
        assert len(d["available"]) >= 6
        ids = {w["id"] for w in d["available"]}
        assert "open_risks" in ids

    def test_put_persists(self, admin_session):
        new_sel = ["open_risks", "high_risk_vendors", "unread_alerts"]
        r = admin_session.put(f"{BASE_URL}/api/studio/dashboard",
                              json={"selected": new_sel}, timeout=15)
        assert r.status_code == 200
        assert r.json()["selected"] == new_sel
        # re-read
        r2 = admin_session.get(f"{BASE_URL}/api/studio/dashboard", timeout=15).json()
        assert r2["selected"] == new_sel

    def test_report_sections(self, admin_session):
        r = admin_session.get(f"{BASE_URL}/api/studio/report/sections", timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert isinstance(d, list) and any(s["id"] == "exec_summary" for s in d)


# ---------- Studio Report Compose (LLM) ----------
class TestStudioReport:
    def test_compose_with_narrative(self, admin_session):
        payload = {"title": "TEST_Custom_Report",
                   "sections": ["exec_summary", "top_risks", "ai_governance"]}
        r = admin_session.post(f"{BASE_URL}/api/studio/report/compose",
                               json=payload, timeout=60)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["title"] == payload["title"]
        assert isinstance(d["blocks"], list) and len(d["blocks"]) == 3
        assert "ai_narrative" in d
        assert isinstance(d["ai_narrative"], str)
        # narrative may be empty on LLM failure — surface it but not fail suite
        if not d["ai_narrative"].strip():
            pytest.fail(f"ai_narrative empty; model={d.get('model')}")


# ---------- Advisor deep mode (SSE) ----------
class TestAdvisor:
    def test_deep_stream_opus(self, admin_session):
        payload = {"message": "What is our top cyber risk right now?",
                   "mode": "executive", "deep": True}
        with admin_session.post(f"{BASE_URL}/api/advisor/chat",
                                json=payload, stream=True, timeout=60) as r:
            assert r.status_code == 200, r.text[:500]
            got_delta = False
            got_done = False
            model_line = None
            deadline = time.time() + 45
            for raw in r.iter_lines(decode_unicode=True):
                if time.time() > deadline:
                    break
                if not raw:
                    continue
                if raw.startswith("data:"):
                    try:
                        ev = json.loads(raw[5:].strip())
                    except Exception:
                        continue
                    if ev.get("delta"):
                        got_delta = True
                    if ev.get("done"):
                        got_done = True
                        model_line = ev.get("model")
                        break
            assert got_delta, "no text stream received"
            assert got_done, "no done event"
            assert model_line and "claude-opus-4-8" in model_line, f"model was {model_line}"


# ---------- Regression ----------
class TestRegression:
    @pytest.mark.parametrize("path", [
        "/api/auth/me",
        "/api/overview",
        "/api/vendors",
        "/api/agents",
        "/api/branding",
        "/api/kernel/manifest",
    ])
    def test_endpoints_ok(self, admin_session, path):
        r = admin_session.get(f"{BASE_URL}{path}", timeout=15)
        assert r.status_code in (200, 204), f"{path} -> {r.status_code} {r.text[:200]}"
