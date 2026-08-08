"""Iteration 43 backend tests - advisor endpoints: /fix (control), /insight (dashboard-scoped), /explain."""
import os
import time
import pytest
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

BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or _read_frontend_env() or "").rstrip("/")
assert BASE_URL, "REACT_APP_BACKEND_URL not found"
API = f"{BASE_URL}/api"
EMAIL = "jblan2026@gmail.com"
PASSWORD = "Obserra2026!"


@pytest.fixture(scope="module")
def sess():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": EMAIL, "password": PASSWORD}, timeout=30)
    assert r.status_code == 200, f"Login failed: {r.status_code} {r.text[:200]}"
    return s


# ---------- /advisor/fix : control entity ----------
class TestAdvisorFixControl:
    def test_fix_control_iam3(self, sess):
        r = sess.post(f"{API}/advisor/fix", json={"entity": "control", "ref": "IAM-3"}, timeout=60)
        assert r.status_code == 200, r.text[:300]
        d = r.json()
        assert d["rating"] in ("Critical", "High", "Medium", "Low"), d.get("rating")
        assert isinstance(d["score"], (int, float)) and 0 <= d["score"] <= 100
        assert isinstance(d["rationale"], list) and len(d["rationale"]) >= 1
        assert isinstance(d.get("recommendation", ""), str)
        assert isinstance(d.get("steps", []), list)
        # Control-specific line: mentions Obserra control or effectiveness vs baseline
        joined = " ".join(d["rationale"]).lower()
        assert ("effectiveness" in joined and "baseline" in joined) or "obserra control" in joined, \
            f"Missing control-specific line: {d['rationale']}"

    def test_fix_control_unknown_ref_still_returns_shape(self, sess):
        r = sess.post(f"{API}/advisor/fix", json={"entity": "control", "ref": "DOES-NOT-EXIST-999"}, timeout=60)
        assert r.status_code == 200
        d = r.json()
        assert d["rating"] in ("Critical", "High", "Medium", "Low")
        assert "rationale" in d and isinstance(d["rationale"], list)


# ---------- /advisor/insight : dashboard-specific ----------
INSIGHT_DASHBOARDS = [
    ("Compliance Posture", ["framework", "control", "compliance", "posture", "gap"]),
    ("Situation Room", ["critical", "exposure", "incident", "situation"]),
    ("Control Monitoring", ["control", "effectiveness", "monitoring"]),
    ("Risk (FAIR)", ["ale", "financial", "loss", "exposure", "fair"]),
    ("Cyber Risk Register", ["risk", "register", "residual", "tier"]),
]


class TestAdvisorInsight:
    @pytest.mark.parametrize("dashboard,keywords", INSIGHT_DASHBOARDS)
    def test_insight_dashboard_specific(self, sess, dashboard, keywords):
        r = sess.post(f"{API}/advisor/insight", json={"dashboard": dashboard, "mode": "executive"}, timeout=60)
        assert r.status_code == 200, f"{dashboard}: {r.status_code} {r.text[:200]}"
        d = r.json()
        assert "headline" in d and "insights" in d and "actions" in d
        assert isinstance(d["insights"], list)
        # Text body
        body_txt = (d.get("headline", "") + " " + " ".join(
            i.get("text", "") if isinstance(i, dict) else str(i) for i in d.get("insights", [])
        )).lower()
        # At least one keyword should appear
        matches = [k for k in keywords if k in body_txt]
        assert matches, f"{dashboard} insight lacks dashboard-specific keywords {keywords}: headline={d.get('headline')!r}, insights={d.get('insights')}"

    def test_fair_vs_register_differ(self, sess):
        r1 = sess.post(f"{API}/advisor/insight", json={"dashboard": "Risk (FAIR)", "mode": "executive"}, timeout=60)
        r2 = sess.post(f"{API}/advisor/insight", json={"dashboard": "Cyber Risk Register", "mode": "executive"}, timeout=60)
        assert r1.status_code == 200 and r2.status_code == 200
        d1, d2 = r1.json(), r2.json()
        h1 = (d1.get("headline") or "").strip()
        h2 = (d2.get("headline") or "").strip()
        ins1 = " ".join(i.get("text", "") if isinstance(i, dict) else str(i) for i in d1.get("insights", []))
        ins2 = " ".join(i.get("text", "") if isinstance(i, dict) else str(i) for i in d2.get("insights", []))
        assert (h1 != h2) or (ins1.strip() != ins2.strip()), \
            f"FAIR and Register summaries are identical!\nFAIR: {h1}\nRegister: {h2}"


# ---------- /advisor/explain ----------
class TestAdvisorExplain:
    def test_explain_fair_metric(self, sess):
        payload = {
            "title": "Posture score",
            "kind": "fair-metric",
            "context": {"posture_score": 88, "mitigation": 74, "coverage": 92, "open_risks": 1},
        }
        r = sess.post(f"{API}/advisor/explain", json=payload, timeout=60)
        assert r.status_code == 200, r.text[:300]
        d = r.json()
        assert "summary" in d and isinstance(d["summary"], str) and len(d["summary"]) > 0
        assert "recommendation" in d and isinstance(d["recommendation"], str)
        assert "steps" in d and isinstance(d["steps"], list)
        assert d.get("severity") in ("info", "opportunity", "watch", "risk")

    def test_explain_node_kind(self, sess):
        r = sess.post(f"{API}/advisor/explain", json={
            "title": "Snowflake",
            "kind": "vendor-node",
            "context": {"vendor": "Snowflake", "tier": "critical", "data_classes": ["PII"]},
        }, timeout=60)
        assert r.status_code == 200
        d = r.json()
        assert isinstance(d.get("summary"), str) and len(d["summary"]) > 0
