"""Tests for P1/P2 features from this session:
- AI system enum validation (status/risk_class)
- Decision counter uniqueness
- Team invite endpoints (admin-only)
- Controls, /financials/trend, evidence-pack
- graph-ask, connectors/sync
"""
import os
import asyncio
import concurrent.futures
import pytest
import requests
from pathlib import Path


def _load_frontend_env():
    envf = Path("/app/frontend/.env")
    if envf.exists():
        for line in envf.read_text().splitlines():
            if line.startswith("REACT_APP_BACKEND_URL="):
                return line.split("=", 1)[1].strip().strip('"')
    raise RuntimeError("REACT_APP_BACKEND_URL not set")


BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or _load_frontend_env()).rstrip("/")

ADMIN = {"email": "jblan2026@gmail.com", "password": "Obserra2026!"}
ANALYST = {"email": "analyst@obserra.demo", "password": "Analyst2026!"}


def _login(creds):
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json=creds, timeout=15)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    return s


@pytest.fixture(scope="module")
def admin():
    return _login(ADMIN)


@pytest.fixture(scope="module")
def analyst():
    return _login(ANALYST)


# ---------- P2: AI System enum validation ----------
class TestAISystemEnum:
    def test_bogus_status_returns_422(self, admin):
        r = admin.patch(f"{BASE_URL}/api/ai-systems/AI-001", json={"status": "bogus"})
        assert r.status_code == 422, r.text

    def test_valid_status_restricted(self, admin):
        r = admin.patch(f"{BASE_URL}/api/ai-systems/AI-001", json={"status": "restricted"})
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "restricted"
        # restore
        admin.patch(f"{BASE_URL}/api/ai-systems/AI-001", json={"status": "sanctioned"})

    def test_bogus_risk_class_returns_422(self, admin):
        r = admin.patch(f"{BASE_URL}/api/ai-systems/AI-001", json={"risk_class": "Nope"})
        assert r.status_code == 422, r.text

    def test_valid_risk_class_high(self, admin):
        r = admin.patch(f"{BASE_URL}/api/ai-systems/AI-001", json={"risk_class": "High"})
        assert r.status_code == 200, r.text
        assert r.json()["risk_class"] == "High"


# ---------- P2: Decision counter concurrency ----------
class TestDecisionCounter:
    def test_sequential_dec_refs_unique(self, admin):
        recs = admin.get(f"{BASE_URL}/api/recommendations").json()
        assert recs, "no recommendations to decide on"
        rec_ref = recs[0]["ref"]
        # fire 5 sequential decisions
        refs = []
        for _ in range(5):
            r = admin.post(f"{BASE_URL}/api/recommendations/{rec_ref}/decide",
                           json={"rec_ref": rec_ref, "chosen": "Test choice", "rationale": "counter test"})
            assert r.status_code == 200, r.text
            refs.append(r.json()["ref"])
        assert len(set(refs)) == len(refs), f"duplicate DEC refs: {refs}"
        # verify sequential numeric
        nums = [int(x.split("-")[1]) for x in refs]
        assert nums == sorted(nums), f"not monotonic: {nums}"

    def test_concurrent_dec_refs_unique(self, admin):
        recs = admin.get(f"{BASE_URL}/api/recommendations").json()
        rec_ref = recs[0]["ref"]

        # Reuse cookies in each thread
        cookies = admin.cookies

        def _decide(_):
            r = requests.post(f"{BASE_URL}/api/recommendations/{rec_ref}/decide",
                              json={"rec_ref": rec_ref, "chosen": "c", "rationale": "concurrent"},
                              cookies=cookies, timeout=20)
            return r.status_code, r.json().get("ref") if r.status_code == 200 else None

        with concurrent.futures.ThreadPoolExecutor(max_workers=6) as ex:
            results = list(ex.map(_decide, range(6)))
        refs = [ref for _, ref in results if ref]
        assert len(refs) >= 5, f"too few successes: {results}"
        assert len(set(refs)) == len(refs), f"COLLISION! {refs}"


# ---------- P1: Team invites ----------
class TestTeamInvites:
    def test_list_members_admin_ok(self, admin):
        r = admin.get(f"{BASE_URL}/api/auth/team/members")
        assert r.status_code == 200, r.text
        data = r.json()
        assert isinstance(data, list)
        assert any(m["email"] == "jblan2026@gmail.com" for m in data)

    def test_list_members_non_admin_forbidden(self, analyst):
        r = analyst.get(f"{BASE_URL}/api/auth/team/members")
        assert r.status_code == 403, r.text

    def test_invite_flow(self, admin):
        import time
        email = f"test_invite_{int(time.time())}@example.com"
        # invalid role
        r = admin.post(f"{BASE_URL}/api/auth/team/invite",
                       json={"email": email, "name": "Test", "role": "superuser"})
        assert r.status_code == 400, r.text

        # valid invite
        r = admin.post(f"{BASE_URL}/api/auth/team/invite",
                       json={"email": email, "name": "Test User", "role": "operational"})
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["email"] == email
        assert data["role"] == "operational"
        assert "temp_password" in data and len(data["temp_password"]) > 6
        member_id = data["id"]

        # duplicate email
        r = admin.post(f"{BASE_URL}/api/auth/team/invite",
                       json={"email": email, "name": "Dup", "role": "operational"})
        assert r.status_code == 400, r.text

        # verify appears in members list
        r = admin.get(f"{BASE_URL}/api/auth/team/members")
        assert any(m["id"] == member_id for m in r.json())

        # remove self forbidden
        me = admin.get(f"{BASE_URL}/api/auth/me").json()
        r = admin.delete(f"{BASE_URL}/api/auth/team/members/{me['id']}")
        assert r.status_code == 400, r.text

        # cleanup: remove invited
        r = admin.delete(f"{BASE_URL}/api/auth/team/members/{member_id}")
        assert r.status_code == 200

    def test_invite_non_admin_forbidden(self, analyst):
        r = analyst.post(f"{BASE_URL}/api/auth/team/invite",
                         json={"email": "x@y.z", "name": "x", "role": "operational"})
        assert r.status_code == 403


# ---------- P1: Connector sync ----------
class TestConnectorSync:
    def test_sync_returns_records(self, admin):
        r = admin.post(f"{BASE_URL}/api/connectors/sync")
        assert r.status_code == 200, r.text
        data = r.json()
        assert "records_ingested" in data
        assert isinstance(data["records_ingested"], int)


# ---------- Last Feature Batch: Controls, financials/trend, evidence-pack, graph-ask ----------
class TestControls:
    def test_controls_list(self, admin):
        r = admin.get(f"{BASE_URL}/api/controls")
        assert r.status_code == 200, r.text
        data = r.json()
        assert len(data) >= 5
        c0 = data[0]
        for key in ("control_id", "name", "effectiveness", "maturity", "status", "stale", "drift", "days_to_expiry"):
            assert key in c0, f"missing {key}"

    def test_evidence_pack_pdf(self, admin):
        r = admin.post(f"{BASE_URL}/api/reports/evidence-pack", json={"control_id": "IAM-3"})
        assert r.status_code == 200, r.text[:200]
        assert r.headers.get("content-type", "").startswith("application/pdf")
        assert len(r.content) > 1000
        assert r.content[:4] == b"%PDF"

    def test_evidence_pack_not_found(self, admin):
        r = admin.post(f"{BASE_URL}/api/reports/evidence-pack", json={"control_id": "XXX-999"})
        assert r.status_code == 404


class TestFinancialsTrend:
    def test_trend_series(self, admin):
        r = admin.get(f"{BASE_URL}/api/financials/trend")
        assert r.status_code == 200, r.text
        data = r.json()
        assert "series" in data and "current" in data
        assert isinstance(data["current"], (int, float))
        # series may be empty if no health history; but seed data usually has history
        if data["series"]:
            assert data["series"][-1]["exposure"] == round(data["current"])
            for pt in data["series"]:
                assert "month" in pt and "exposure" in pt


class TestGraphAsk:
    def test_graph_ask_returns_answer_and_highlight(self, admin):
        r = admin.post(f"{BASE_URL}/api/advisor/graph-ask",
                       json={"question": "Which AI systems process Confidential PII from risky vendors?"})
        assert r.status_code == 200, r.text[:300]
        data = r.json()
        assert "answer" in data and "highlight" in data
        assert isinstance(data["highlight"], list)
        # heuristic highlights D-CONF for "confiden"/"pii" queries
        assert "D-CONF" in data["highlight"]
