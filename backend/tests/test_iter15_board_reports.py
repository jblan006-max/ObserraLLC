"""Iteration 15 — Board reports (PDF/Deck), recipients, branding, test-email."""
import os
import base64
import requests
import pytest

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://cyber-dashboard-48.preview.emergentagent.com").rstrip("/")
ADMIN = {"email": "jblan2026@gmail.com", "password": "Obserra2026!"}
OPS = {"email": "analyst@obserra.demo", "password": "Analyst2026!"}


def _login(creds):
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json=creds, timeout=30)
    assert r.status_code == 200, f"Login failed for {creds['email']}: {r.status_code} {r.text[:300]}"
    return s


@pytest.fixture(scope="module")
def admin_client():
    return _login(ADMIN)


@pytest.fixture(scope="module")
def ops_client():
    return _login(OPS)


# ---------- PDF export (report + deck) ----------
class TestBoardPdf:
    SAMPLE = "# Board Report\n\nExecutive Summary: Strong resilience posture.\n\n- Risk 1\n- Risk 2\n"

    def test_pdf_report_dark(self, admin_client):
        r = admin_client.post(f"{BASE_URL}/api/reports/pdf",
                              json={"report": self.SAMPLE, "title": "Board", "theme": "dark", "layout": "report"},
                              timeout=60)
        assert r.status_code == 200, r.text[:300]
        assert r.headers.get("content-type", "").startswith("application/pdf")
        assert r.content[:4] == b"%PDF"
        pytest.report_size = len(r.content)

    def test_pdf_report_light(self, admin_client):
        r = admin_client.post(f"{BASE_URL}/api/reports/pdf",
                              json={"report": self.SAMPLE, "title": "Board", "theme": "light", "layout": "report"},
                              timeout=60)
        assert r.status_code == 200
        assert r.content[:4] == b"%PDF"

    def test_pdf_deck_dark(self, admin_client):
        r = admin_client.post(f"{BASE_URL}/api/reports/pdf",
                              json={"report": self.SAMPLE, "title": "Board", "theme": "dark", "layout": "deck"},
                              timeout=60)
        assert r.status_code == 200
        assert r.headers.get("content-type", "").startswith("application/pdf")
        assert r.content[:4] == b"%PDF"
        pytest.deck_size = len(r.content)

    def test_pdf_deck_light(self, admin_client):
        r = admin_client.post(f"{BASE_URL}/api/reports/pdf",
                              json={"report": self.SAMPLE, "title": "Board", "theme": "light", "layout": "deck"},
                              timeout=60)
        assert r.status_code == 200
        assert r.content[:4] == b"%PDF"

    def test_deck_differs_from_report(self, admin_client):
        # deck should be different (usually larger, landscape multi-page) than portrait report
        assert getattr(pytest, "report_size", 0) > 0
        assert getattr(pytest, "deck_size", 0) > 0
        assert pytest.deck_size != pytest.report_size, \
            f"Deck ({pytest.deck_size}) == report ({pytest.report_size}) — likely same layout"


# ---------- Recipients ----------
class TestRecipients:
    def test_get_recipients(self, admin_client):
        r = admin_client.get(f"{BASE_URL}/api/reports/recipients", timeout=15)
        assert r.status_code == 200
        data = r.json()
        assert "extra" in data and "auto" in data
        assert isinstance(data["extra"], list)
        assert isinstance(data["auto"], list)
        assert ADMIN["email"] in data["auto"], f"Admin missing from auto list: {data['auto']}"

    def test_put_recipients_drops_invalid(self, admin_client):
        payload = {"emails": ["board1@acme.com", "bad", "board2@acme.com"]}
        r = admin_client.put(f"{BASE_URL}/api/reports/recipients", json=payload, timeout=15)
        assert r.status_code == 200, r.text[:300]
        data = r.json()
        assert "bad" not in data["extra"]
        assert "board1@acme.com" in data["extra"]
        assert "board2@acme.com" in data["extra"]

        # Verify persistence via GET
        r2 = admin_client.get(f"{BASE_URL}/api/reports/recipients", timeout=15)
        assert set(r2.json()["extra"]) >= {"board1@acme.com", "board2@acme.com"}

    def test_put_recipients_non_admin_403(self, ops_client):
        r = ops_client.put(f"{BASE_URL}/api/reports/recipients",
                           json={"emails": ["x@y.com"]}, timeout=15)
        assert r.status_code == 403, f"Expected 403 got {r.status_code}: {r.text[:200]}"

    def test_cleanup_recipients(self, admin_client):
        admin_client.put(f"{BASE_URL}/api/reports/recipients", json={"emails": []}, timeout=15)


# ---------- Branding ----------
class TestBranding:
    def _logo_b64(self):
        path = "/app/frontend/public/logo-mark-192.png"
        if not os.path.exists(path):
            # fallback: any png in public
            for p in ("/app/frontend/public/brand-mark.png",):
                if os.path.exists(p):
                    path = p
                    break
        with open(path, "rb") as f:
            b = base64.b64encode(f.read()).decode()
        return f"data:image/png;base64,{b}"

    def test_get_branding(self, admin_client):
        r = admin_client.get(f"{BASE_URL}/api/reports/branding", timeout=15)
        assert r.status_code == 200
        data = r.json()
        assert set(data.keys()) >= {"enabled", "company_name", "has_logo"}

    def test_put_branding_admin(self, admin_client):
        payload = {"enabled": True, "company_name": "Acme Corp", "logo": self._logo_b64()}
        r = admin_client.put(f"{BASE_URL}/api/reports/branding", json=payload, timeout=30)
        assert r.status_code == 200, r.text[:300]
        data = r.json()
        assert data["enabled"] is True
        assert data["company_name"] == "Acme Corp"
        assert data["has_logo"] is True

    def test_pdf_after_branding(self, admin_client):
        # PDF should still generate with branded footer
        r = admin_client.post(f"{BASE_URL}/api/reports/pdf",
                              json={"report": "# Test\nContent.", "title": "Branded", "theme": "light",
                                    "layout": "report"}, timeout=60)
        assert r.status_code == 200
        assert r.content[:4] == b"%PDF"

    def test_put_branding_non_admin_403(self, ops_client):
        r = ops_client.put(f"{BASE_URL}/api/reports/branding",
                           json={"enabled": True, "company_name": "Hax"}, timeout=15)
        assert r.status_code == 403

    def test_reset_branding(self, admin_client):
        r = admin_client.put(f"{BASE_URL}/api/reports/branding",
                             json={"enabled": False, "company_name": ""}, timeout=15)
        assert r.status_code == 200
        assert r.json()["enabled"] is False


# ---------- Test email ----------
class TestTestEmail:
    def test_admin_send_test_email(self, admin_client):
        # LLM board report generation may be slow — generous timeout
        r = admin_client.post(f"{BASE_URL}/api/reports/test-email", timeout=180)
        assert r.status_code == 200, f"{r.status_code}: {r.text[:300]}"
        data = r.json()
        assert data.get("status") == "sent"
        assert data.get("to") == ADMIN["email"]

    def test_non_admin_test_email(self, ops_client):
        r = ops_client.post(f"{BASE_URL}/api/reports/test-email", timeout=30)
        # Operational (not admin/exec) — should be 403
        assert r.status_code == 403, f"Expected 403 got {r.status_code}"
