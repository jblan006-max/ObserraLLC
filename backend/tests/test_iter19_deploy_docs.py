"""Iteration 19: Deployment package & docs downloads + PWA manifest."""
import os
import io
import json
import zipfile
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://cyber-dashboard-48.preview.emergentagent.com").rstrip("/")
ADMIN_EMAIL = "jblan2026@gmail.com"
ADMIN_PASS = "Obserra2026!"
OP_EMAIL = "analyst@obserra.demo"
OP_PASS = "Analyst2026!"


@pytest.fixture(scope="module")
def admin_session():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASS})
    assert r.status_code == 200, f"admin login failed: {r.status_code} {r.text}"
    return s


@pytest.fixture(scope="module")
def op_session():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json={"email": OP_EMAIL, "password": OP_PASS})
    assert r.status_code == 200, f"op login failed: {r.status_code} {r.text}"
    return s


class TestDeployAuth:
    def test_onprem_unauth(self):
        r = requests.get(f"{BASE_URL}/api/deploy/onprem-package")
        assert r.status_code in (401, 403)

    def test_pdf_unauth(self):
        r = requests.get(f"{BASE_URL}/api/deploy/guide.pdf")
        assert r.status_code in (401, 403)

    def test_docx_unauth(self):
        r = requests.get(f"{BASE_URL}/api/deploy/guide.docx")
        assert r.status_code in (401, 403)

    def test_onprem_non_admin_forbidden(self, op_session):
        r = op_session.get(f"{BASE_URL}/api/deploy/onprem-package")
        assert r.status_code == 403


class TestDeployAdmin:
    def test_onprem_package(self, admin_session):
        r = admin_session.get(f"{BASE_URL}/api/deploy/onprem-package")
        assert r.status_code == 200
        assert "application/zip" in r.headers.get("content-type", "")
        z = zipfile.ZipFile(io.BytesIO(r.content))
        names = z.namelist()
        required = ["docker-compose.yml", "backend.Dockerfile", "frontend.Dockerfile",
                    "nginx.conf", ".env.example", "INSTALL.md", "install.sh"]
        for req in required:
            assert any(n.endswith(req) and n.startswith("obserra-onprem/") for n in names), \
                f"missing {req} in zip. got: {names}"

    def test_guide_pdf(self, admin_session):
        r = admin_session.get(f"{BASE_URL}/api/deploy/guide.pdf")
        assert r.status_code == 200
        assert r.headers.get("content-type") == "application/pdf"
        assert r.content[:4] == b"%PDF"
        assert len(r.content) > 10000

    def test_guide_docx(self, admin_session):
        r = admin_session.get(f"{BASE_URL}/api/deploy/guide.docx")
        assert r.status_code == 200
        ct = r.headers.get("content-type", "")
        assert "wordprocessingml" in ct
        # docx = zip; starts with PK
        assert r.content[:2] == b"PK"
        assert len(r.content) > 10000


class TestPWA:
    def test_manifest(self):
        # manifest is served by frontend, not backend
        # Use REACT_APP_BACKEND_URL which is the same origin
        r = requests.get(f"{BASE_URL}/manifest.json")
        assert r.status_code == 200
        data = r.json()
        assert data.get("display") == "standalone"
        assert data.get("start_url") == "/app"
        assert len(data.get("icons", [])) >= 2

    def test_service_worker_file(self):
        r = requests.get(f"{BASE_URL}/push-sw.js")
        assert r.status_code == 200
        assert "javascript" in r.headers.get("content-type", "").lower() or "text" in r.headers.get("content-type", "").lower()
        assert b"install" in r.content or b"self.addEventListener" in r.content
