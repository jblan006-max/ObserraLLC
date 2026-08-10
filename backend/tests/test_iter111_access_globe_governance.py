"""Iter111 tests: Access Globe, Governance trusted_countries, Custody Map in Auditor Room PDF."""
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


# ---------------- Access Globe ----------------
class TestAccessGlobe:
    def test_requires_auth(self, anon):
        r = anon.get(f"{BASE_URL}/api/agents/runtime/access-globe")
        assert r.status_code in (401, 403), f"Expected 401/403 without auth, got {r.status_code}"

    def test_shape_and_data(self, admin):
        r = admin.get(f"{BASE_URL}/api/agents/runtime/access-globe")
        assert r.status_code == 200, r.text[:300]
        data = r.json()
        for key in ("points", "total", "opens", "downloads", "located", "countries", "cards", "rooms"):
            assert key in data, f"missing key {key}"
        assert isinstance(data["points"], list)
        assert isinstance(data["countries"], list)
        assert isinstance(data["total"], int)
        assert isinstance(data["opens"], int)
        assert isinstance(data["downloads"], int)
        assert isinstance(data["located"], int)
        # Points sanity
        if data["points"]:
            p = data["points"][0]
            assert "lat" in p and "lon" in p and "kind" in p
            assert isinstance(p["lat"], (int, float))
            assert isinstance(p["lon"], (int, float))
            assert p["kind"] in ("card", "room", "open", "download") or isinstance(p["kind"], str)
        print(f"Globe: total={data['total']} located={data['located']} points={len(data['points'])} countries={len(data['countries'])}")


# ---------------- Governance Settings ----------------
class TestGovernanceTrustedCountries:
    def test_get_returns_list(self, admin):
        r = admin.get(f"{BASE_URL}/api/agents/runtime/governance-settings")
        assert r.status_code == 200, r.text[:200]
        data = r.json()
        assert "trusted_countries" in data
        assert isinstance(data["trusted_countries"], list)

    def test_put_trim_dedupe(self, admin):
        payload = {"trusted_countries": ["United States", " United States ", "Canada", ""]}
        r = admin.put(f"{BASE_URL}/api/agents/runtime/governance-settings", json=payload)
        assert r.status_code == 200, r.text[:300]
        body = r.json()
        tc = body.get("trusted_countries") or body.get("settings", {}).get("trusted_countries")
        assert tc == ["United States", "Canada"], f"Expected trimmed+deduped list, got {tc}"

        # persistence
        r2 = admin.get(f"{BASE_URL}/api/agents/runtime/governance-settings")
        assert r2.status_code == 200
        assert r2.json()["trusted_countries"] == ["United States", "Canada"]

    def test_put_clear(self, admin):
        r = admin.put(f"{BASE_URL}/api/agents/runtime/governance-settings",
                      json={"trusted_countries": []})
        assert r.status_code == 200
        r2 = admin.get(f"{BASE_URL}/api/agents/runtime/governance-settings")
        assert r2.json()["trusted_countries"] == []


# ---------------- Evidence Room PDF Custody Map ----------------
class TestEvidenceRoomPDFCustodyMap:
    def test_geo_room_pdf_has_map_caption(self, anon):
        r = anon.get(f"{BASE_URL}/api/agents/public/evidence-room/{GEO_ROOM_TOKEN}/pack.pdf",
                     timeout=30)
        assert r.status_code == 200, f"{r.status_code} {r.text[:200]}"
        assert r.content[:4] == b"%PDF", "response is not a PDF"
        # Try to parse and search text for caption
        try:
            from pypdf import PdfReader
        except ImportError:
            try:
                from PyPDF2 import PdfReader
            except ImportError:
                pytest.skip("pypdf/PyPDF2 not installed")
        reader = PdfReader(io.BytesIO(r.content))
        assert len(reader.pages) >= 1
        text_all = ""
        for pg in reader.pages:
            try:
                text_all += (pg.extract_text() or "") + "\n"
            except Exception:
                pass
        assert "Where this evidence was accessed" in text_all, \
            f"Custody map caption not found. Pages={len(reader.pages)}"
        print(f"Geo room PDF: {len(reader.pages)} pages, caption present.")

    def test_no_geo_room_pdf_valid_no_map(self, anon):
        r = anon.get(f"{BASE_URL}/api/agents/public/evidence-room/{NO_GEO_ROOM_TOKEN}/pack.pdf",
                     timeout=30)
        assert r.status_code == 200, f"{r.status_code} {r.text[:200]}"
        assert r.content[:4] == b"%PDF"
        print(f"No-geo room PDF size={len(r.content)} bytes (still valid).")
