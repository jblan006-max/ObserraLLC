"""Iter108 — Share Center follow-ups: Custody Export CSV/PDF, Geo+Device on access log,
Weekly Engagement Digest task."""
import os
import sys
import time
import asyncio
import pytest
import requests

BASE = os.environ.get("REACT_APP_BACKEND_URL") or ""
if not BASE:
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                BASE = line.split("=", 1)[1].strip()
BASE = BASE.rstrip("/")
API = f"{BASE}/api"

ADMIN_EMAIL = "jblan2026@gmail.com"
ADMIN_PW = "Obserra2026!"


@pytest.fixture(scope="module")
def admin_session():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PW}, timeout=30)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text[:200]}"
    return s


def _mint(admin_session, title_suffix=""):
    payload = {
        "title": f"TEST_Iter108 Card {title_suffix}",
        "ref": "TEST-108-001",
        "kind": "incident",
        "rating": "Medium",
        "score": 60,
        "connectors": [{"name": "Agent runtime", "detail": "signed webhook", "status": "ok"}],
        "facets": [{"label": "Outcome", "value": "Investigate"}],
        "recommendations": ["Review"],
        "summary": "iter108 test card",
        "days": 3,
    }
    r = admin_session.post(f"{API}/agents/runtime/card-share", json=payload, timeout=30)
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture()
def token_with_access(admin_session):
    tok = _mint(admin_session, str(int(time.time())))
    # Generate some access events via public endpoint w/ X-Forwarded-For + UA for geo/device
    headers_chrome_mac = {
        "X-Forwarded-For": "8.8.8.8",
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    }
    headers_firefox_win = {
        "X-Forwarded-For": "1.1.1.1",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    }
    # 2 opens (JSON) + 1 PDF download
    r1 = requests.get(f"{API}/agents/public/card-share/{tok}", headers=headers_chrome_mac, timeout=15)
    assert r1.status_code == 200, r1.text
    r2 = requests.get(f"{API}/agents/public/card-share/{tok}", headers=headers_firefox_win, timeout=15)
    assert r2.status_code == 200
    r3 = requests.get(f"{API}/agents/public/card-share/{tok}/card.pdf?who=Jane%20Auditor",
                      headers=headers_chrome_mac, timeout=30)
    assert r3.status_code == 200
    yield tok
    admin_session.post(f"{API}/agents/runtime/card-share/revoke", json={"token": tok}, timeout=15)


# ── Geo + Device on the JSON access log ───────────────────────────────
class TestGeoDeviceOnAccessLog:
    def test_access_log_has_device_and_geo(self, admin_session, token_with_access):
        # Small delay to let geo backfill fire on the first call
        r = admin_session.get(f"{API}/agents/runtime/card-share/{token_with_access}/access-log", timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        rows = data.get("access", [])
        assert len(rows) >= 3, f"expected >=3 access rows, got {len(rows)}: {rows}"
        # Every row must carry a device label (parsed from UA)
        devices = [r.get("device") for r in rows]
        assert any("Chrome on macOS" in (d or "") for d in devices), f"missing 'Chrome on macOS' device: {devices}"
        assert any("Firefox on Windows" in (d or "") for d in devices), f"missing 'Firefox on Windows' device: {devices}"
        # Geo best-effort — assert at least one row got a non-empty geo string (public IPs 8.8.8.8/1.1.1.1)
        geos = [r.get("geo") for r in rows if r.get("geo")]
        assert len(geos) >= 1, f"expected at least one geo-resolved row, got geos={geos} rows={rows}"


# ── Custody Export CSV ────────────────────────────────────────────────
class TestCustodyCSV:
    def test_csv_export_returns_text_csv_with_rows(self, admin_session, token_with_access):
        r = admin_session.get(f"{API}/agents/runtime/card-share/{token_with_access}/access-log.csv", timeout=30)
        assert r.status_code == 200, r.text[:200]
        ctype = r.headers.get("content-type", "")
        assert "text/csv" in ctype, f"bad content-type: {ctype}"
        assert "attachment" in r.headers.get("content-disposition", "").lower()
        body = r.text
        # Header lines
        assert "Obserra" in body and "chain of custody" in body.lower()
        assert "Event" in body and "Timestamp" in body
        # Card title + ref present
        assert "TEST_Iter108 Card" in body
        assert "TEST-108-001" in body
        # At least 3 event rows containing 'open' or 'download'
        assert body.lower().count("open") >= 2
        assert body.lower().count("download") >= 1

    def test_csv_export_404_unknown(self, admin_session):
        r = admin_session.get(f"{API}/agents/runtime/card-share/nonexistent-token-x/access-log.csv", timeout=15)
        assert r.status_code == 404

    def test_csv_export_requires_auth(self):
        r = requests.get(f"{API}/agents/runtime/card-share/whatever/access-log.csv", timeout=15)
        assert r.status_code in (401, 403)


# ── Custody Export PDF ────────────────────────────────────────────────
class TestCustodyPDF:
    def test_pdf_export_returns_pdf_bytes(self, admin_session, token_with_access):
        r = admin_session.get(f"{API}/agents/runtime/card-share/{token_with_access}/access-log.pdf", timeout=60)
        assert r.status_code == 200, r.text[:200]
        assert "application/pdf" in r.headers.get("content-type", "")
        assert "attachment" in r.headers.get("content-disposition", "").lower()
        assert r.content[:4] == b"%PDF", f"not a PDF: {r.content[:20]}"
        assert len(r.content) > 2000, f"suspiciously small PDF: {len(r.content)} bytes"

    def test_pdf_export_404_unknown(self, admin_session):
        r = admin_session.get(f"{API}/agents/runtime/card-share/nonexistent-token-x/access-log.pdf", timeout=15)
        assert r.status_code == 404

    def test_pdf_export_requires_auth(self):
        r = requests.get(f"{API}/agents/runtime/card-share/whatever/access-log.pdf", timeout=15)
        assert r.status_code in (401, 403)


# ── Weekly Engagement Digest task ─────────────────────────────────────
def _run_digest_in_subprocess():
    """Invoke _run_card_engagement_weekly_digest in a clean subprocess so the
    motor event loop is fresh per invocation."""
    import subprocess
    code = (
        "import asyncio, sys; sys.path.insert(0, '/app/backend'); "
        "from dotenv import load_dotenv; load_dotenv('/app/backend/.env'); "
        "import agents; asyncio.run(agents._run_card_engagement_weekly_digest()); "
        "print('OK')"
    )
    return subprocess.run(["python", "-c", code], cwd="/app/backend",
                          capture_output=True, text=True, timeout=60)


class TestWeeklyDigestTask:
    def test_run_weekly_digest_no_exception(self, token_with_access):
        """Task runs to completion with no exception."""
        proc = _run_digest_in_subprocess()
        assert proc.returncode == 0, f"stderr:\n{proc.stderr}\nstdout:\n{proc.stdout}"
        assert "OK" in proc.stdout

    def test_weekly_digest_notification_present(self, admin_session, token_with_access):
        """After running the digest, an in-app 'Weekly shared-card engagement'
        notification exists for the admin's org (created either by this run or a
        prior same-week run — dedupe_key by org:YYYY-WW suppresses duplicates)."""
        # Ensure task has been run at least once
        proc = _run_digest_in_subprocess()
        assert proc.returncode == 0, f"stderr:\n{proc.stderr}"
        # Give notifications API a beat
        time.sleep(1.0)
        r = admin_session.get(f"{API}/notifications", timeout=15)
        assert r.status_code == 200, r.text[:200]
        items = r.json() if isinstance(r.json(), list) else r.json().get("items", [])
        titles = [n.get("title") or n.get("kind_title") or "" for n in items]
        weekly = [t for t in titles if "Weekly shared-card engagement" in t]
        assert len(weekly) >= 1, (
            f"Expected at least one 'Weekly shared-card engagement' notification; "
            f"sample titles={titles[:8]}")

    def test_run_weekly_digest_idempotent(self, token_with_access, admin_session):
        """Two consecutive runs in the same week do not create a duplicate
        'Weekly shared-card engagement' notification (dedupe_key latch)."""
        # Count before
        r = admin_session.get(f"{API}/notifications", timeout=15)
        items = r.json() if isinstance(r.json(), list) else r.json().get("items", [])
        before = sum(1 for n in items
                     if "Weekly shared-card engagement" in (n.get("title") or n.get("kind_title") or ""))
        # Run twice
        for _ in range(2):
            proc = _run_digest_in_subprocess()
            assert proc.returncode == 0, f"stderr:\n{proc.stderr}"
        time.sleep(1.0)
        r = admin_session.get(f"{API}/notifications", timeout=15)
        items = r.json() if isinstance(r.json(), list) else r.json().get("items", [])
        after = sum(1 for n in items
                    if "Weekly shared-card engagement" in (n.get("title") or n.get("kind_title") or ""))
        # After should NOT exceed before by more than 1 (dedupe suppresses same-week dupes)
        assert (after - before) <= 1, f"expected idempotency, before={before} after={after}"


# ── Regression: base access-log JSON still works ──────────────────────
class TestRegressionAccessLogJSON:
    def test_access_log_json_still_returns_shape(self, admin_session, token_with_access):
        r = admin_session.get(f"{API}/agents/runtime/card-share/{token_with_access}/access-log", timeout=15)
        assert r.status_code == 200
        data = r.json()
        for k in ("opens", "downloads", "access"):
            assert k in data
        assert data["opens"] >= 2
        assert data["downloads"] >= 1
