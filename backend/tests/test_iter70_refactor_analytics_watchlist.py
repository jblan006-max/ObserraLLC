"""Iter 70 — regression after safe refactor + new Analytics Explorer & Risk Watchlist.

Covers:
1. Moved endpoints (now in sap_ask.py / sap_evidence.py) still 200 & correct shape.
2. Cross-module `_digest_ai_context` still resolves (digest/share).
3. NEW Analytics Explorer filters (region/department).
4. NEW Risk Watchlist (pin/unpin/404/sort).
"""
import os
import pytest
import requests

def _load_base():
    v = os.environ.get("REACT_APP_BACKEND_URL")
    if not v:
        try:
            with open("/app/frontend/.env") as f:
                for line in f:
                    if line.startswith("REACT_APP_BACKEND_URL="):
                        v = line.split("=", 1)[1].strip()
                        break
        except Exception:
            pass
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
    return s


# ── Refactor regression: endpoints MOVED to sap_ask.py ────────────────────────
class TestMovedAskEndpoints:
    def test_ask_analytics(self, sess):
        r = sess.get(f"{BASE}/api/sap/ask-analytics", timeout=20)
        assert r.status_code == 200
        j = r.json()
        for k in ("total", "by_source", "top_questions", "top_askers"):
            assert k in j

    def test_ask_log(self, sess):
        r = sess.get(f"{BASE}/api/sap/ask-log?limit=5", timeout=20)
        assert r.status_code == 200
        j = r.json()
        assert "entries" in j and "total" in j and "by_source" in j

    def test_digest_ask_intro(self, sess):
        r = sess.get(f"{BASE}/api/sap/digest/ask/intro", timeout=20)
        assert r.status_code == 200

    def test_digest_ask_history(self, sess):
        r = sess.get(f"{BASE}/api/sap/digest/ask/history", timeout=20)
        assert r.status_code == 200

    def test_digest_ask_multiturn(self, sess):
        r = sess.post(
            f"{BASE}/api/sap/digest/ask",
            json={"question": "How many open critical conflicts?", "session_id": "iter70-a"},
            timeout=60,
        )
        assert r.status_code == 200
        j = r.json()
        assert "answer" in j
        assert len(j.get("answer", "")) > 5
        # 2nd turn same session
        r2 = sess.post(
            f"{BASE}/api/sap/digest/ask",
            json={"question": "which area is worst?", "session_id": "iter70-a"},
            timeout=60,
        )
        assert r2.status_code == 200


# ── Refactor regression: endpoints MOVED to sap_evidence.py ───────────────────
class TestMovedEvidenceEndpoints:
    def test_sod_evidence_preview(self, sess):
        r = sess.get(f"{BASE}/api/sap/sod-evidence/preview", timeout=30)
        assert r.status_code == 200


# ── Refactor regression: endpoints REMAINING in sap_digest.py but cross-call moved code
class TestDigestCrossModule:
    def test_scorecard(self, sess):
        r = sess.get(f"{BASE}/api/sap/scorecard", timeout=30)
        assert r.status_code == 200
        assert "current" in r.json()

    def test_scorecard_why(self, sess):
        r = sess.get(f"{BASE}/api/sap/scorecard/why", timeout=30)
        assert r.status_code == 200

    def test_digest_config_get(self, sess):
        r = sess.get(f"{BASE}/api/sap/digest/config", timeout=20)
        assert r.status_code == 200

    def test_digest_share_uses_moved_ai_context(self, sess):
        # This internally calls _digest_ai_context which now lives in sap_ask
        r = sess.post(f"{BASE}/api/sap/digest/share", json={}, timeout=60)
        assert r.status_code == 200, f"digest/share failed: {r.status_code} {r.text[:300]}"
        j = r.json()
        assert j.get("token") or j.get("share_token") or j.get("url"), f"no share token in {j}"

    def test_digest_recap_preview(self, sess):
        r = sess.get(f"{BASE}/api/sap/digest/recap/preview", timeout=60)
        assert r.status_code == 200


# ── NEW: Analytics Explorer filters ───────────────────────────────────────────
class TestAnalyticsExplorer:
    def test_no_filter_returns_filters_object(self, sess):
        r = sess.get(f"{BASE}/api/sap/analytics", timeout=30)
        assert r.status_code == 200
        j = r.json()
        assert "filters" in j
        f = j["filters"]
        assert isinstance(f.get("regions"), list) and len(f["regions"]) > 0
        assert isinstance(f.get("departments"), list) and len(f["departments"]) > 0
        assert f.get("region") == ""
        assert f.get("department") == ""
        self._baseline = j["kpis"]["identities"]
        pytest.baseline_identities = self._baseline
        pytest.regions = f["regions"]
        pytest.departments = f["departments"]

    def test_region_filter_scopes(self, sess):
        regions = getattr(pytest, "regions", None)
        assert regions, "run test_no_filter first"
        region = "EMEA" if "EMEA" in regions else regions[0]
        r = sess.get(f"{BASE}/api/sap/analytics?region={region}", timeout=30)
        assert r.status_code == 200
        j = r.json()
        assert j["filters"]["region"] == region
        # scoped: identities should be <= baseline
        assert j["kpis"]["identities"] <= pytest.baseline_identities
        assert j["kpis"]["identities"] > 0

    def test_department_filter_scopes(self, sess):
        depts = getattr(pytest, "departments", None)
        assert depts, "run test_no_filter first"
        dept = "Finance" if "Finance" in depts else depts[0]
        r = sess.get(f"{BASE}/api/sap/analytics?department={dept}", timeout=30)
        assert r.status_code == 200
        j = r.json()
        assert j["filters"]["department"] == dept
        assert j["kpis"]["identities"] <= pytest.baseline_identities

    def test_combined_filter(self, sess):
        regions = pytest.regions
        depts = pytest.departments
        region = regions[0]
        dept = depts[0]
        r = sess.get(f"{BASE}/api/sap/analytics?region={region}&department={dept}", timeout=30)
        assert r.status_code == 200
        j = r.json()
        assert j["filters"]["region"] == region
        assert j["filters"]["department"] == dept


# ── NEW: SoD Risk Watchlist ───────────────────────────────────────────────────
class TestWatchlist:
    def test_get_empty_or_current(self, sess):
        r = sess.get(f"{BASE}/api/sap/watchlist", timeout=20)
        assert r.status_code == 200
        j = r.json()
        assert "pinned" in j and "available" in j
        assert isinstance(j["available"], list) and len(j["available"]) > 0
        # available sorted hottest first (by open)
        opens = [a["open"] for a in j["available"]]
        assert opens == sorted(opens, reverse=True) or all(o == opens[0] for o in opens)
        # each has required fields
        a0 = j["available"][0]
        for k in ("area", "open", "Critical", "High", "Medium", "Low", "pinned"):
            assert k in a0
        # clean up any pre-existing pinned areas from prior runs
        for p in j["pinned"]:
            sess.delete(f"{BASE}/api/sap/watchlist", params={"area": p["area"]}, timeout=10)

    def test_pin_finance(self, sess):
        r = sess.post(f"{BASE}/api/sap/watchlist", json={"area": "Finance"}, timeout=20)
        assert r.status_code == 200, f"{r.status_code} {r.text}"
        j = r.json()
        assert any(p["area"] == "Finance" for p in j["pinned"])
        # 'pinned' flag reflected in available
        fin_avail = next((a for a in j["available"] if a["area"] == "Finance"), None)
        assert fin_avail and fin_avail["pinned"] is True

    def test_pin_unknown_area_404(self, sess):
        r = sess.post(f"{BASE}/api/sap/watchlist", json={"area": "NotARealArea_ZZZ"}, timeout=20)
        assert r.status_code == 404

    def test_pinned_sort(self, sess):
        # pin at least 2 areas to verify sort
        r0 = sess.get(f"{BASE}/api/sap/watchlist", timeout=20).json()
        # pick 2 unpinned real areas
        others = [a["area"] for a in r0["available"] if not a["pinned"]][:2]
        for a in others:
            sess.post(f"{BASE}/api/sap/watchlist", json={"area": a}, timeout=20)
        j = sess.get(f"{BASE}/api/sap/watchlist", timeout=20).json()
        p = j["pinned"]
        # sorted by -Critical, then -open
        for i in range(len(p) - 1):
            a, b = p[i], p[i + 1]
            assert (a["Critical"], a["open"]) >= (b["Critical"], b["open"]) or a["Critical"] > b["Critical"] or (
                a["Critical"] == b["Critical"] and a["open"] >= b["open"]
            )

    def test_unpin(self, sess):
        r = sess.delete(f"{BASE}/api/sap/watchlist", params={"area": "Finance"}, timeout=20)
        assert r.status_code == 200
        j = r.json()
        assert not any(p["area"] == "Finance" for p in j["pinned"])

    def test_cleanup(self, sess):
        # unpin everything created
        j = sess.get(f"{BASE}/api/sap/watchlist", timeout=20).json()
        for p in j["pinned"]:
            sess.delete(f"{BASE}/api/sap/watchlist", params={"area": p["area"]}, timeout=10)
        final = sess.get(f"{BASE}/api/sap/watchlist", timeout=20).json()
        assert final["pinned"] == []
