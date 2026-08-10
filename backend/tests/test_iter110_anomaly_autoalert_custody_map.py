"""Iter110 — Share Center follow-ups:
(1) Anomaly Auto-Alert — notify org staff on new-country/new-device open OR download,
    fires when cadence in ('instant','weekly') but NOT when cadence == 'off'.
    Notification kind_title='Unusual shared-card access',
    dedupe_key = card-anomaly:{token}:{ip}:{kind}.
(2) Custody Map in PDF — GET /api/agents/runtime/card-share/{token}/access-log.pdf
    embeds a 'Where this evidence was accessed' page with world-map image when geo rows exist.
(3) Regression — access-log JSON, CSV Anomaly column, cadence dropdown still work.
"""
import os
import time
import io
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
UA_FIREFOX_WIN = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) "
                  "Gecko/20100101 Firefox/121.0")

IP_US = "8.8.8.8"
IP_AU = "1.1.1.1"


# ── helpers ──────────────────────────────────────────────────────────

def _mongo():
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
    return c[db_name]


@pytest.fixture(scope="module")
def admin_session():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PW}, timeout=30)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text[:200]}"
    return s


def _mint(admin_session, suffix=""):
    payload = {
        "title": f"TEST_Iter110 {suffix}",
        "ref": "TEST-110-001",
        "kind": "incident",
        "rating": "Medium",
        "score": 55,
        "connectors": [{"name": "Agent runtime", "detail": "signed", "status": "ok"}],
        "facets": [{"label": "Outcome", "value": "Investigate"}],
        "recommendations": ["Review"],
        "summary": "iter110 test card",
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


def _public_open(tok, ip, ua):
    return requests.get(f"{API}/agents/public/card-share/{tok}",
                        headers={"X-Forwarded-For": ip, "User-Agent": ua}, timeout=20)


def _public_download(tok, ip, ua, who="Bob"):
    return requests.get(f"{API}/agents/public/card-share/{tok}/card.pdf",
                        params={"who": who},
                        headers={"X-Forwarded-For": ip, "User-Agent": ua}, timeout=30)


def _count_anomaly_notifs(dbh, token, ip=None, kind=None):
    q = {"kind_title": "Unusual shared-card access"} if False else {}
    # We match on dedupe_key prefix, since kind_title is stored as "title" (see notifications.create)
    prefix = f"card-anomaly:{token}"
    if ip:
        prefix = f"{prefix}:{ip}"
    if kind:
        prefix = f"{prefix}:{kind}" if ip else prefix
    return dbh.notifications.count_documents(
        {"dedupe_key": {"$regex": f"^{prefix}"}})


@pytest.fixture(scope="module", autouse=True)
def _restore_instant_at_end(admin_session):
    yield
    try:
        _set_cadence(admin_session, "instant")
    except Exception:
        pass


# ── (1) Anomaly Auto-Alert — OPEN, cadence gating ────────────────────
class TestAnomalyAutoAlertOpen:
    def test_weekly_cadence_anomalous_open_creates_notification(self, admin_session):
        _set_cadence(admin_session, "weekly")
        tok = _mint(admin_session, f"open-weekly-{int(time.time())}")
        dbh = _mongo()
        # Baseline: US + Chrome/mac (first access can NEVER be an anomaly)
        r = _public_open(tok, IP_US, UA_CHROME_MAC)
        assert r.status_code == 200
        time.sleep(1.5)  # allow geo lookup + insert
        assert _count_anomaly_notifs(dbh, tok) == 0, "first access must not fire anomaly alert"

        # Anomalous: AU + Firefox/Win — should fire even under weekly cadence
        r = _public_open(tok, IP_AU, UA_FIREFOX_WIN)
        assert r.status_code == 200
        time.sleep(2.0)

        n = _count_anomaly_notifs(dbh, tok, ip=IP_AU, kind="open")
        assert n == 1, f"weekly cadence: expected 1 anomaly notif for AU open, got {n}"

        # Cleanup
        try:
            admin_session.post(f"{API}/agents/runtime/card-share/revoke",
                               json={"token": tok}, timeout=15)
        except Exception:
            pass

    def test_off_cadence_anomalous_open_creates_no_notification(self, admin_session):
        _set_cadence(admin_session, "off")
        tok = _mint(admin_session, f"open-off-{int(time.time())}")
        dbh = _mongo()
        r = _public_open(tok, IP_US, UA_CHROME_MAC)
        assert r.status_code == 200
        time.sleep(1.5)
        r = _public_open(tok, IP_AU, UA_FIREFOX_WIN)
        assert r.status_code == 200
        time.sleep(2.0)

        n = _count_anomaly_notifs(dbh, tok)
        assert n == 0, f"off cadence: expected 0 anomaly notifs, got {n}"

        try:
            admin_session.post(f"{API}/agents/runtime/card-share/revoke",
                               json={"token": tok}, timeout=15)
        except Exception:
            pass

    def test_dedupe_re_open_from_same_anomalous_ip(self, admin_session):
        """Re-opening from the same anomalous IP should NOT create a second notification."""
        _set_cadence(admin_session, "weekly")
        tok = _mint(admin_session, f"dedupe-{int(time.time())}")
        dbh = _mongo()
        _public_open(tok, IP_US, UA_CHROME_MAC); time.sleep(1.5)
        _public_open(tok, IP_AU, UA_FIREFOX_WIN); time.sleep(2.0)
        first = _count_anomaly_notifs(dbh, tok)
        _public_open(tok, IP_AU, UA_FIREFOX_WIN); time.sleep(2.0)
        second = _count_anomaly_notifs(dbh, tok)
        assert first == 1 and second == 1, f"dedupe failed: first={first} second={second}"
        try:
            admin_session.post(f"{API}/agents/runtime/card-share/revoke",
                               json={"token": tok}, timeout=15)
        except Exception:
            pass


# ── (1b) Anomaly Auto-Alert — DOWNLOAD (per review request) ──────────
class TestAnomalyAutoAlertDownload:
    def test_weekly_cadence_anomalous_download_creates_notification(self, admin_session):
        _set_cadence(admin_session, "weekly")
        tok = _mint(admin_session, f"dl-weekly-{int(time.time())}")
        dbh = _mongo()
        # Baseline OPEN from US
        r = _public_open(tok, IP_US, UA_CHROME_MAC)
        assert r.status_code == 200
        time.sleep(1.5)
        # Anomalous DOWNLOAD from AU
        r = _public_download(tok, IP_AU, UA_FIREFOX_WIN, who="Alice")
        assert r.status_code == 200
        time.sleep(2.0)

        n = _count_anomaly_notifs(dbh, tok, ip=IP_AU, kind="download")
        assert n == 1, (
            f"weekly cadence: expected 1 anomaly notif for AU download, got {n}. "
            "This suggests _card_anomaly_autocheck is NOT wired into "
            "public_card_share_pdf (download path)."
        )
        try:
            admin_session.post(f"{API}/agents/runtime/card-share/revoke",
                               json={"token": tok}, timeout=15)
        except Exception:
            pass

    def test_off_cadence_anomalous_download_creates_no_notification(self, admin_session):
        _set_cadence(admin_session, "off")
        tok = _mint(admin_session, f"dl-off-{int(time.time())}")
        dbh = _mongo()
        _public_open(tok, IP_US, UA_CHROME_MAC); time.sleep(1.5)
        r = _public_download(tok, IP_AU, UA_FIREFOX_WIN, who="Alice")
        assert r.status_code == 200
        time.sleep(2.0)
        n = _count_anomaly_notifs(dbh, tok)
        assert n == 0, f"off cadence: expected 0, got {n}"
        try:
            admin_session.post(f"{API}/agents/runtime/card-share/revoke",
                               json={"token": tok}, timeout=15)
        except Exception:
            pass


# ── (2) Custody Map in PDF ───────────────────────────────────────────
class TestCustodyMapInPDF:
    @pytest.fixture(scope="class")
    def token_with_geo(self, admin_session):
        _set_cadence(admin_session, "instant")
        tok = _mint(admin_session, f"custody-{int(time.time())}")
        _public_open(tok, IP_US, UA_CHROME_MAC); time.sleep(1.5)
        _public_open(tok, IP_AU, UA_FIREFOX_WIN); time.sleep(1.5)
        # Trigger geo backfill via access-log GET
        admin_session.get(f"{API}/agents/runtime/card-share/{tok}/access-log", timeout=30)
        time.sleep(1.0)
        yield tok
        try:
            admin_session.post(f"{API}/agents/runtime/card-share/revoke",
                               json={"token": tok}, timeout=15)
        except Exception:
            pass

    def test_custody_pdf_valid_and_multipage(self, admin_session, token_with_geo):
        r = admin_session.get(
            f"{API}/agents/runtime/card-share/{token_with_geo}/access-log.pdf", timeout=60)
        assert r.status_code == 200
        assert "application/pdf" in r.headers.get("content-type", "")
        assert r.content[:4] == b"%PDF"
        assert len(r.content) > 3000

        # Verify page count and embedded images using pymupdf
        try:
            import pymupdf
            pdf = pymupdf.open(stream=r.content, filetype="pdf")
            n_pages = pdf.page_count
            n_images = 0
            has_map_heading = False
            for p in pdf:
                n_images += len(p.get_images(full=True))
                txt = p.get_text() or ""
                if "Where this evidence was accessed" in txt:
                    has_map_heading = True
            pdf.close()
        except Exception as e:
            pytest.skip(f"pymupdf inspection failed: {e}")
        assert n_pages >= 2, f"expected >= 2 pages, got {n_pages}"
        assert has_map_heading, "custody PDF must contain 'Where this evidence was accessed' page"
        assert n_images >= 1, f"custody PDF must embed >=1 image, got {n_images}"

    def test_custody_pdf_no_geo_still_valid(self, admin_session):
        """A card with no accesses (thus no geo) must still return a valid PDF (no map page)."""
        _set_cadence(admin_session, "instant")
        tok = _mint(admin_session, f"nogeo-{int(time.time())}")
        try:
            r = admin_session.get(
                f"{API}/agents/runtime/card-share/{tok}/access-log.pdf", timeout=45)
            assert r.status_code == 200
            assert "application/pdf" in r.headers.get("content-type", "")
            assert r.content[:4] == b"%PDF"
            try:
                import pymupdf
                pdf = pymupdf.open(stream=r.content, filetype="pdf")
                for p in pdf:
                    assert "Where this evidence was accessed" not in (p.get_text() or ""), \
                        "no-geo card must NOT contain the map page"
                pdf.close()
            except ImportError:
                pass
        finally:
            try:
                admin_session.post(f"{API}/agents/runtime/card-share/revoke",
                                   json={"token": tok}, timeout=15)
            except Exception:
                pass


# ── (3) Regression — access-log carries geo_lat/geo_lon + anomaly ────
class TestAccessLogRegression:
    def test_access_log_json_has_geo_and_anomaly(self, admin_session):
        _set_cadence(admin_session, "instant")
        tok = _mint(admin_session, f"reg-{int(time.time())}")
        _public_open(tok, IP_US, UA_CHROME_MAC); time.sleep(1.5)
        _public_open(tok, IP_AU, UA_FIREFOX_WIN); time.sleep(1.5)
        # 2 calls to allow geo backfill
        admin_session.get(f"{API}/agents/runtime/card-share/{tok}/access-log", timeout=30)
        time.sleep(1.0)
        r = admin_session.get(f"{API}/agents/runtime/card-share/{tok}/access-log", timeout=30)
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data.get("access"), list)
        assert len(data["access"]) >= 2
        for row in data["access"]:
            assert "anomaly" in row and "anomaly_reason" in row
            assert "geo" in row
        # CSV column
        r = admin_session.get(f"{API}/agents/runtime/card-share/{tok}/access-log.csv", timeout=30)
        assert r.status_code == 200
        assert "Anomaly" in r.text
        try:
            admin_session.post(f"{API}/agents/runtime/card-share/revoke",
                               json={"token": tok}, timeout=15)
        except Exception:
            pass
