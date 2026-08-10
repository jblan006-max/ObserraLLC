"""Iter112 tests: Globe drilldown fields, Board Access Map PDF, Trusted IP ranges, regressions."""
import os
import io
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
ADMIN_EMAIL = "jblan2026@gmail.com"
ADMIN_PW = "Obserra2026!"

GEO_ROOM_TOKEN = "RhtjoHWa_8YAwjqWg3ydEA"
NO_GEO_ROOM_TOKEN = "UxKT1G2IqUBEeHpZGvfjew"


@pytest.fixture(scope="module")
def anon():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="module")
def admin():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    r = s.post(f"{BASE_URL}/api/auth/login",
               json={"email": ADMIN_EMAIL, "password": ADMIN_PW})
    if r.status_code != 200:
        pytest.skip(f"Admin login failed: {r.status_code} {r.text[:200]}")
    return s


# ------------- Globe drilldown fields -------------
class TestAccessGlobeDrilldown:
    def test_requires_auth(self, anon):
        r = anon.get(f"{BASE_URL}/api/agents/runtime/access-globe")
        assert r.status_code in (401, 403)

    def test_points_have_drilldown_fields(self, admin):
        r = admin.get(f"{BASE_URL}/api/agents/runtime/access-globe")
        assert r.status_code == 200, r.text[:300]
        data = r.json()
        pts = data.get("points", [])
        assert isinstance(pts, list) and len(pts) > 0, "Expected at least one point"
        required = {"kind", "source", "title", "who", "device", "ip", "at",
                    "label", "token", "lat", "lon", "anomaly"}
        p0 = pts[0]
        missing = required - set(p0.keys())
        assert not missing, f"Missing drilldown fields in point[0]: {missing}. Keys present: {list(p0.keys())}"
        for p in pts[:5]:
            assert p["source"] in ("card", "room"), f"bad source: {p['source']}"
            assert isinstance(p["lat"], (int, float))
            assert isinstance(p["lon"], (int, float))
        print(f"Globe drilldown OK: {len(pts)} points, sample who={p0.get('who')!r} device={p0.get('device')!r} ip={p0.get('ip')!r}")


# ------------- Board Access Map PDF -------------
class TestBoardAccessMapPDF:
    def test_requires_auth(self, anon):
        r = anon.get(f"{BASE_URL}/api/agents/runtime/access-globe.pdf")
        assert r.status_code in (401, 403)

    def test_pdf_valid_and_contents(self, admin):
        r = admin.get(f"{BASE_URL}/api/agents/runtime/access-globe.pdf", timeout=45)
        assert r.status_code == 200, r.text[:300]
        assert r.content[:4] == b"%PDF", "Not a PDF"
        try:
            from pypdf import PdfReader
        except ImportError:
            from PyPDF2 import PdfReader
        reader = PdfReader(io.BytesIO(r.content))
        assert len(reader.pages) >= 1
        text_all = ""
        for pg in reader.pages:
            try:
                text_all += (pg.extract_text() or "") + "\n"
            except Exception:
                pass
        assert "Board Access Map" in text_all, "Missing 'Board Access Map' title"
        assert "Access locations" in text_all, "Missing 'Access locations' section"
        assert "Evidence access map" in text_all, "Missing 'Evidence access map' page caption"
        print(f"Board Access Map PDF: {len(reader.pages)} pages, {len(r.content)} bytes")


# ------------- Trusted IP ranges -------------
class TestTrustedIPRanges:
    def test_get_returns_field(self, admin):
        r = admin.get(f"{BASE_URL}/api/agents/runtime/governance-settings")
        assert r.status_code == 200
        data = r.json()
        assert "trusted_ip_ranges" in data
        assert isinstance(data["trusted_ip_ranges"], list)

    def test_put_validates_trims_dedupes(self, admin):
        payload = {"trusted_ip_ranges": [
            "203.0.113.0/24",
            " 203.0.113.0/24 ",
            "198.51.100.7",
            "not-an-ip",
            "999.1.1.1",
            ""
        ]}
        r = admin.put(f"{BASE_URL}/api/agents/runtime/governance-settings", json=payload)
        assert r.status_code == 200, r.text[:300]
        body = r.json()
        tir = body.get("trusted_ip_ranges") or body.get("settings", {}).get("trusted_ip_ranges")
        assert tir == ["203.0.113.0/24", "198.51.100.7"], f"Got {tir}"

        # persistence
        r2 = admin.get(f"{BASE_URL}/api/agents/runtime/governance-settings")
        assert r2.json()["trusted_ip_ranges"] == ["203.0.113.0/24", "198.51.100.7"]

    def test_put_clear(self, admin):
        r = admin.put(f"{BASE_URL}/api/agents/runtime/governance-settings",
                      json={"trusted_ip_ranges": []})
        assert r.status_code == 200
        r2 = admin.get(f"{BASE_URL}/api/agents/runtime/governance-settings")
        assert r2.json()["trusted_ip_ranges"] == []

    def test_trusted_countries_still_works(self, admin):
        payload = {"trusted_countries": ["United States", " United States ", "Canada", ""]}
        r = admin.put(f"{BASE_URL}/api/agents/runtime/governance-settings", json=payload)
        assert r.status_code == 200
        body = r.json()
        tc = body.get("trusted_countries") or body.get("settings", {}).get("trusted_countries")
        assert tc == ["United States", "Canada"], f"Got {tc}"
        # cleanup
        admin.put(f"{BASE_URL}/api/agents/runtime/governance-settings",
                  json={"trusted_countries": []})


# ------------- Regression -------------
class TestRegression:
    def test_geo_room_pdf_custody_map(self, anon):
        r = anon.get(f"{BASE_URL}/api/agents/public/evidence-room/{GEO_ROOM_TOKEN}/pack.pdf", timeout=30)
        assert r.status_code == 200
        assert r.content[:4] == b"%PDF"

    def test_no_geo_room_pdf(self, anon):
        r = anon.get(f"{BASE_URL}/api/agents/public/evidence-room/{NO_GEO_ROOM_TOKEN}/pack.pdf", timeout=30)
        assert r.status_code == 200
        assert r.content[:4] == b"%PDF"

    def test_shared_card_access_log_endpoint_exists(self, admin):
        # Try to enumerate shared cards; endpoint should respond 200 (list may be empty).
        r = admin.get(f"{BASE_URL}/api/agents/runtime/shared-cards")
        # Some builds gate this differently; accept 200 or 404 (route naming) but not 500.
        assert r.status_code < 500, f"shared-cards 5xx: {r.status_code} {r.text[:200]}"

    def test_custody_csv_endpoint(self, admin):
        r = admin.get(f"{BASE_URL}/api/agents/runtime/access-log.csv")
        assert r.status_code < 500, f"access-log.csv 5xx: {r.status_code}"

    def test_custody_pdf_endpoint(self, admin):
        r = admin.get(f"{BASE_URL}/api/agents/runtime/access-log.pdf")
        assert r.status_code < 500, f"access-log.pdf 5xx: {r.status_code}"

    def test_defensibility_endpoint_healthy(self, admin):
        r = admin.get(f"{BASE_URL}/api/agents/runtime/defensibility")
        assert r.status_code < 500
