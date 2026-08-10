"""Iter106 — Share Center admin list, revoke, attach, stats, Auto Board Attach digest."""
import os
import pytest
import requests

BASE = os.environ.get("REACT_APP_BACKEND_URL")
if not BASE:
    # fallback: read from frontend/.env
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


@pytest.fixture(scope="module")
def minted_token(admin_session):
    payload = {
        "title": "TEST_ShareCenter Card",
        "ref": "TEST-SC-001",
        "kind": "incident",
        "rating": "High",
        "score": 72,
        "connectors": [{"name": "Agent runtime", "detail": "signed webhook", "status": "ok"}],
        "facets": [{"label": "Outcome", "value": "Suspend"}],
        "recommendations": ["Rotate keys"],
        "summary": "test share center card",
        "days": 7,
    }
    r = admin_session.post(f"{API}/agents/runtime/card-share", json=payload, timeout=30)
    assert r.status_code == 200, r.text
    tok = r.json()["token"]
    yield tok
    # cleanup best-effort
    admin_session.post(f"{API}/agents/runtime/card-share/revoke", json={"token": tok}, timeout=15)


class TestShareCenter:
    def test_list_contains_minted(self, admin_session, minted_token):
        r = admin_session.get(f"{API}/agents/runtime/card-shares", timeout=15)
        assert r.status_code == 200
        cards = r.json()["cards"]
        assert isinstance(cards, list)
        row = next((c for c in cards if c["token"] == minted_token), None)
        assert row is not None, "minted card not in list"
        assert row["title"] == "TEST_ShareCenter Card"
        assert row["rating"] == "High"
        assert row["opens"] == 0
        assert row["downloads"] == 0
        assert row["attach_to_board"] is False
        assert row["url"].endswith(f"/card/{minted_token}")

    def test_stats_no_increment(self, admin_session, minted_token):
        r1 = admin_session.get(f"{API}/agents/runtime/card-share/{minted_token}/stats", timeout=15)
        assert r1.status_code == 200
        opens1 = r1.json()["opens"]
        # call again — must NOT increment opens
        r2 = admin_session.get(f"{API}/agents/runtime/card-share/{minted_token}/stats", timeout=15)
        assert r2.status_code == 200
        assert r2.json()["opens"] == opens1

    def test_public_open_increments(self, admin_session, minted_token):
        pre = admin_session.get(f"{API}/agents/runtime/card-share/{minted_token}/stats").json()["opens"]
        # public — no auth
        r = requests.get(f"{API}/agents/public/card-share/{minted_token}", timeout=15)
        assert r.status_code == 200
        post = admin_session.get(f"{API}/agents/runtime/card-share/{minted_token}/stats").json()["opens"]
        assert post == pre + 1

    def test_public_pdf_increments_downloads(self, admin_session, minted_token):
        pre = admin_session.get(f"{API}/agents/runtime/card-share/{minted_token}/stats").json()["downloads"]
        r = requests.get(f"{API}/agents/public/card-share/{minted_token}/card.pdf", timeout=30)
        assert r.status_code == 200
        assert r.headers.get("content-type", "").startswith("application/pdf")
        assert r.content[:4] == b"%PDF"
        post = admin_session.get(f"{API}/agents/runtime/card-share/{minted_token}/stats").json()["downloads"]
        assert post == pre + 1

    def test_attach_toggle(self, admin_session, minted_token):
        r = admin_session.post(f"{API}/agents/runtime/card-share/attach",
                               json={"token": minted_token, "attach": True}, timeout=15)
        assert r.status_code == 200
        assert r.json()["attach_to_board"] is True
        # list should reflect
        cards = admin_session.get(f"{API}/agents/runtime/card-shares").json()["cards"]
        row = next(c for c in cards if c["token"] == minted_token)
        assert row["attach_to_board"] is True

    def test_board_digest_preview_includes_card(self, admin_session, minted_token):
        # Ensure attached
        admin_session.post(f"{API}/agents/runtime/card-share/attach",
                           json={"token": minted_token, "attach": True}, timeout=15)
        r = admin_session.get(f"{API}/agents/runtime/board-evidence-digest/preview", timeout=30)
        assert r.status_code == 200
        body = r.text
        assert "Shared detail cards" in body, "board digest missing shared cards section"
        assert f"/card/{minted_token}" in body, "board digest missing link to minted card"

    def test_attach_off_removes_from_digest(self, admin_session, minted_token):
        r = admin_session.post(f"{API}/agents/runtime/card-share/attach",
                               json={"token": minted_token, "attach": False}, timeout=15)
        assert r.status_code == 200
        assert r.json()["attach_to_board"] is False
        prev = admin_session.get(f"{API}/agents/runtime/board-evidence-digest/preview", timeout=30).text
        assert f"/card/{minted_token}" not in prev

    def test_revoke_and_public_404(self, admin_session):
        # mint a fresh card just for this test
        payload = {"title": "TEST_RevokeCard", "ref": "TEST-RV-1", "kind": "incident",
                   "rating": "Low", "score": 10, "days": 3}
        tok = admin_session.post(f"{API}/agents/runtime/card-share", json=payload).json()["token"]
        r = admin_session.post(f"{API}/agents/runtime/card-share/revoke",
                               json={"token": tok}, timeout=15)
        assert r.status_code == 200
        # public URL should 404
        pub = requests.get(f"{API}/agents/public/card-share/{tok}", timeout=15)
        assert pub.status_code == 404
        # list should NOT contain
        cards = admin_session.get(f"{API}/agents/runtime/card-shares").json()["cards"]
        assert not any(c["token"] == tok for c in cards)

    def test_revoke_unknown_token_404(self, admin_session):
        r = admin_session.post(f"{API}/agents/runtime/card-share/revoke",
                               json={"token": "definitely-not-a-real-token-xyz"}, timeout=15)
        assert r.status_code == 404

    def test_unauth_endpoints_reject(self):
        r = requests.get(f"{API}/agents/runtime/card-shares", timeout=15)
        assert r.status_code in (401, 403)
