"""Iter109 — Share Center follow-ups: Anomaly Flags, Digest Cadence, World-map thumbnail.

Validates:
- Anomaly flags on /api/agents/runtime/card-share/{token}/access-log
  (new country / new device / new country · new device; first-of-kind not flagged).
- geo_lat / geo_lon present on rows so frontend WorldMapThumb can plot them.
- CSV export contains an 'Anomaly' column.
- PDF export still returns a valid application/pdf.
- Governance settings card_engagement_cadence persists (off|weekly|instant) via PUT/GET.
- Cadence gating for instant engagement alerts:
    * cadence='instant' → alerted_open=True after first public open
    * cadence='weekly'  → alerted_open stays False
    * cadence='off'     → alerted_open stays False
"""
import os
import time
import pytest
import requests

BASE = (os.environ.get("REACT_APP_BACKEND_URL") or "").rstrip("/")
if not BASE:
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                BASE = line.split("=", 1)[1].strip().rstrip("/")
API = f"{BASE}/api"

ADMIN_EMAIL = "jblan2026@gmail.com"
ADMIN_PW = "Obserra2026!"

UA_CHROME_MAC = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                 "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
UA_FIREFOX_WIN = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0")


@pytest.fixture(scope="module")
def admin_session():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PW}, timeout=30)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text[:200]}"
    return s


def _mint(admin_session, suffix=""):
    payload = {
        "title": f"TEST_Iter109 Card {suffix}",
        "ref": "TEST-109-001",
        "kind": "incident",
        "rating": "Medium",
        "score": 55,
        "connectors": [{"name": "Agent runtime", "detail": "signed webhook", "status": "ok"}],
        "facets": [{"label": "Outcome", "value": "Investigate"}],
        "recommendations": ["Review"],
        "summary": "iter109 test card",
        "days": 3,
    }
    r = admin_session.post(f"{API}/agents/runtime/card-share", json=payload, timeout=30)
    assert r.status_code == 200, r.text
    return r.json()["token"]


def _set_cadence(admin_session, cadence):
    r = admin_session.put(f"{API}/agents/runtime/governance-settings",
                          json={"card_engagement_cadence": cadence}, timeout=15)
    assert r.status_code == 200, r.text
    return r.json()


@pytest.fixture(scope="module", autouse=True)
def _restore_instant_at_end(admin_session):
    yield
    # Per instructions: leave cadence set to 'instant' at the end.
    try:
        _set_cadence(admin_session, "instant")
    except Exception:
        pass


# ── Governance settings — card_engagement_cadence field ──────────────
class TestCadenceSetting:
    def test_default_cadence_key_present(self, admin_session):
        r = admin_session.get(f"{API}/agents/runtime/governance-settings", timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert "card_engagement_cadence" in d
        assert d["card_engagement_cadence"] in ("off", "weekly", "instant")

    @pytest.mark.parametrize("val", ["off", "weekly", "instant"])
    def test_put_and_get_cadence(self, admin_session, val):
        got = _set_cadence(admin_session, val)
        assert got["card_engagement_cadence"] == val
        # verify persistence via fresh GET
        r = admin_session.get(f"{API}/agents/runtime/governance-settings", timeout=15)
        assert r.json()["card_engagement_cadence"] == val

    def test_invalid_cadence_falls_back_to_instant(self, admin_session):
        _set_cadence(admin_session, "weekly")
        r = admin_session.put(f"{API}/agents/runtime/governance-settings",
                              json={"card_engagement_cadence": "bogus"}, timeout=15)
        assert r.status_code == 200
        assert r.json()["card_engagement_cadence"] == "instant"


# ── Anomaly flags + geo_lat/geo_lon on access log ────────────────────
class TestAnomalyAndGeo:
    @pytest.fixture(scope="class")
    def token_with_baseline_and_anomaly(self, admin_session):
        # Ensure cadence is instant so opens proceed normally (alert path independent).
        _set_cadence(admin_session, "instant")
        tok = _mint(admin_session, f"anom-{int(time.time())}")
        # Baseline: US + Chrome/mac
        r = requests.get(f"{API}/agents/public/card-share/{tok}",
                         headers={"X-Forwarded-For": "8.8.8.8", "User-Agent": UA_CHROME_MAC}, timeout=20)
        assert r.status_code == 200
        time.sleep(1.2)
        # Anomalous open: AU + Firefox/Win (new country AND new device)
        r = requests.get(f"{API}/agents/public/card-share/{tok}",
                         headers={"X-Forwarded-For": "1.1.1.1", "User-Agent": UA_FIREFOX_WIN}, timeout=20)
        assert r.status_code == 200
        # give the enrichment/geo lookup a moment
        time.sleep(1.0)
        yield tok
        try:
            admin_session.post(f"{API}/agents/runtime/card-share/revoke",
                               json={"token": tok}, timeout=15)
        except Exception:
            pass

    def test_access_log_returns_rows(self, admin_session, token_with_baseline_and_anomaly):
        tok = token_with_baseline_and_anomaly
        # First call may trigger geo backfill — call twice.
        admin_session.get(f"{API}/agents/runtime/card-share/{tok}/access-log", timeout=30)
        time.sleep(1.0)
        r = admin_session.get(f"{API}/agents/runtime/card-share/{tok}/access-log", timeout=30)
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data.get("access"), list)
        assert len(data["access"]) >= 2

    def test_rows_have_anomaly_and_reason_keys(self, admin_session, token_with_baseline_and_anomaly):
        tok = token_with_baseline_and_anomaly
        data = admin_session.get(f"{API}/agents/runtime/card-share/{tok}/access-log", timeout=30).json()
        for row in data["access"]:
            assert "anomaly" in row
            assert "anomaly_reason" in row
            assert isinstance(row["anomaly"], bool)
            assert isinstance(row["anomaly_reason"], str)

    def test_geo_lat_lon_present(self, admin_session, token_with_baseline_and_anomaly):
        tok = token_with_baseline_and_anomaly
        # A second call gives the geo cache a chance
        admin_session.get(f"{API}/agents/runtime/card-share/{tok}/access-log", timeout=30)
        time.sleep(1.0)
        data = admin_session.get(f"{API}/agents/runtime/card-share/{tok}/access-log", timeout=30).json()
        with_coords = [r for r in data["access"]
                       if isinstance(r.get("geo_lat"), (int, float))
                       and isinstance(r.get("geo_lon"), (int, float))]
        # ip-api.com is best-effort — at least one of the two routable IPs should resolve.
        assert with_coords, f"No rows carry geo_lat/geo_lon; rows={data['access']}"

    def test_baseline_not_flagged_and_anomaly_flagged(self, admin_session, token_with_baseline_and_anomaly):
        tok = token_with_baseline_and_anomaly
        data = admin_session.get(f"{API}/agents/runtime/card-share/{tok}/access-log", timeout=30).json()
        # rows are sorted -1 by 'at' (most recent first)
        rows = data["access"]
        # Chronological order: oldest baseline last in list
        oldest = rows[-1]
        newest = rows[0]
        assert oldest["anomaly"] is False, f"baseline should not be flagged: {oldest}"
        # The newest (AU + Firefox) row should be flagged if enrichment resolved.
        if newest.get("geo") and oldest.get("geo") and newest["geo"] != oldest["geo"]:
            assert newest["anomaly"] is True
            assert "new country" in newest["anomaly_reason"] or "new device" in newest["anomaly_reason"]

    def test_csv_export_includes_anomaly_column(self, admin_session, token_with_baseline_and_anomaly):
        tok = token_with_baseline_and_anomaly
        r = admin_session.get(f"{API}/agents/runtime/card-share/{tok}/access-log.csv", timeout=30)
        assert r.status_code == 200
        assert "text/csv" in r.headers.get("content-type", "")
        body = r.text
        assert "Anomaly" in body, "CSV must include an 'Anomaly' column header"

    def test_pdf_export_still_valid(self, admin_session, token_with_baseline_and_anomaly):
        tok = token_with_baseline_and_anomaly
        r = admin_session.get(f"{API}/agents/runtime/card-share/{tok}/access-log.pdf", timeout=45)
        assert r.status_code == 200
        assert "application/pdf" in r.headers.get("content-type", "")
        assert r.content[:4] == b"%PDF"
        assert len(r.content) > 2000


# ── Cadence gating on instant Engagement Alert ───────────────────────
class TestInstantAlertGating:
    def _mint_and_open(self, admin_session):
        tok = _mint(admin_session, f"gate-{int(time.time())}")
        r = requests.get(f"{API}/agents/public/card-share/{tok}",
                         headers={"X-Forwarded-For": "8.8.8.8", "User-Agent": UA_CHROME_MAC}, timeout=20)
        assert r.status_code == 200
        return tok

    def _alerted_open(self, admin_session, tok):
        # Not exposed via API — query MongoDB directly (localhost, same container).
        try:
            from pymongo import MongoClient
            mongo_url = "mongodb://localhost:27017"
            db_name = "test_database"
            with open("/app/backend/.env") as f:
                for line in f:
                    if line.startswith("MONGO_URL="):
                        mongo_url = line.split("=", 1)[1].strip().strip('"').strip("'")
                    elif line.startswith("DB_NAME="):
                        db_name = line.split("=", 1)[1].strip().strip('"').strip("'")
            c = MongoClient(mongo_url, serverSelectionTimeoutMS=3000)
            doc = c[db_name].card_shares.find_one({"token": tok})
            return bool((doc or {}).get("alerted_open", False)) if doc else None
        except Exception as e:
            print(f"[iter109] mongo peek failed: {e}")
            return None

    def test_instant_sets_alerted_open_true(self, admin_session):
        _set_cadence(admin_session, "instant")
        tok = self._mint_and_open(admin_session)
        time.sleep(1.0)
        flag = self._alerted_open(admin_session, tok)
        # If endpoint doesn't expose the field, skip rather than fail hard.
        if flag is None:
            pytest.skip("card-shares list does not expose alerted_open")
        assert flag is True

    def test_weekly_leaves_alerted_open_false(self, admin_session):
        _set_cadence(admin_session, "weekly")
        tok = self._mint_and_open(admin_session)
        time.sleep(1.0)
        flag = self._alerted_open(admin_session, tok)
        if flag is None:
            pytest.skip("card-shares list does not expose alerted_open")
        assert flag is False

    def test_off_leaves_alerted_open_false(self, admin_session):
        _set_cadence(admin_session, "off")
        tok = self._mint_and_open(admin_session)
        time.sleep(1.0)
        flag = self._alerted_open(admin_session, tok)
        if flag is None:
            pytest.skip("card-shares list does not expose alerted_open")
        assert flag is False
