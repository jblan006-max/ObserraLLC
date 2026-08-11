"""
Iteration 118 — Trust Link Expiry, Snooze Reason (instant+scheduled), Digest Preview
"""
import os
import secrets
import pytest
import requests
from datetime import datetime, timezone, timedelta
from bson import ObjectId

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    with open("/app/frontend/.env") as f:
        for ln in f:
            if ln.startswith("REACT_APP_BACKEND_URL="):
                BASE_URL = ln.split("=", 1)[1].strip().rstrip("/")

ADMIN_EMAIL = "jblan2026@gmail.com"
ADMIN_PW = "Obserra2026!"
SEEDED_TRUST_TOKEN = "60WMUbma7oOLPXvQ-H-0uNuoX-wZ65gr"


@pytest.fixture(scope="module")
def sess():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login",
               json={"email": ADMIN_EMAIL, "password": ADMIN_PW}, timeout=20)
    assert r.status_code == 200, f"login: {r.status_code} {r.text[:200]}"
    return s


@pytest.fixture(scope="module")
def db():
    """Direct MongoDB access for seeding trust tokens with custom expiry."""
    import motor.motor_asyncio, asyncio
    # Load env
    mongo_url = os.environ.get("MONGO_URL")
    db_name = os.environ.get("DB_NAME")
    if not mongo_url or not db_name:
        with open("/app/backend/.env") as f:
            for ln in f:
                if ln.startswith("MONGO_URL="):
                    mongo_url = ln.split("=", 1)[1].strip().strip('"')
                elif ln.startswith("DB_NAME="):
                    db_name = ln.split("=", 1)[1].strip().strip('"')
    client = motor.motor_asyncio.AsyncIOMotorClient(mongo_url)
    return client[db_name]


def _run(coro):
    import asyncio
    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            raise RuntimeError()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)


def _recent_audit_csv(sess):
    r = sess.get(f"{BASE_URL}/api/agents/runtime/audit-log.csv", timeout=20)
    assert r.status_code == 200
    return r.text


def _org_id(sess, db):
    async def _go():
        u = await db.users.find_one({"email": ADMIN_EMAIL})
        return u["org_id"]
    return _run(_go())


# ---------- 1. Trust link expiry ----------

def test_trust_lookup_future_expiry_returns_expired_false(sess, db):
    org_id = _org_id(sess, db)
    tok = "TEST_" + secrets.token_urlsafe(16)
    exp = (datetime.now(timezone.utc) + timedelta(hours=72)).isoformat()
    async def _seed():
        await db.trust_add_tokens.insert_one({
            "token": tok, "org_id": org_id, "kind": "country",
            "value": "TESTfuture", "used": False,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "expires_at": exp,
        })
    _run(_seed())
    try:
        r = sess.get(f"{BASE_URL}/api/agents/runtime/trust-suggestion/{tok}", timeout=20)
        assert r.status_code == 200, r.text[:300]
        j = r.json()
        assert j.get("kind") == "country"
        assert j.get("value") == "TESTfuture"
        assert j.get("expired") is False
        assert j.get("used") is False
        assert j.get("expires_at")
    finally:
        _run(db.trust_add_tokens.delete_one({"token": tok}))


def test_trust_lookup_past_expiry_returns_expired_true_and_apply_400(sess, db):
    org_id = _org_id(sess, db)
    tok = "TEST_" + secrets.token_urlsafe(16)
    exp = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    async def _seed():
        await db.trust_add_tokens.insert_one({
            "token": tok, "org_id": org_id, "kind": "country",
            "value": "TESTexpired", "used": False,
            "created_at": (datetime.now(timezone.utc) - timedelta(days=5)).isoformat(),
            "expires_at": exp,
        })
    _run(_seed())
    try:
        r = sess.get(f"{BASE_URL}/api/agents/runtime/trust-suggestion/{tok}", timeout=20)
        assert r.status_code == 200
        assert r.json().get("expired") is True

        r2 = sess.post(f"{BASE_URL}/api/agents/runtime/trust-suggestion/{tok}/apply",
                       json={}, timeout=20)
        assert r2.status_code == 400, r2.text[:300]
        assert "expired" in r2.text.lower()
    finally:
        _run(db.trust_add_tokens.delete_one({"token": tok}))


def test_trust_apply_valid_unexpired_appends_and_marks_used(sess, db):
    org_id = _org_id(sess, db)
    tok = "TEST_" + secrets.token_urlsafe(16)
    value = "TESTvalidland"
    exp = (datetime.now(timezone.utc) + timedelta(hours=72)).isoformat()
    async def _seed():
        await db.trust_add_tokens.insert_one({
            "token": tok, "org_id": org_id, "kind": "country",
            "value": value, "used": False,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "expires_at": exp,
        })
    _run(_seed())
    try:
        r = sess.post(f"{BASE_URL}/api/agents/runtime/trust-suggestion/{tok}/apply",
                      json={}, timeout=20)
        assert r.status_code == 200, r.text[:300]
        j = r.json()
        assert j.get("ok") is True
        assert j.get("value") == value

        g = sess.get(f"{BASE_URL}/api/agents/runtime/governance-settings", timeout=20).json()
        tc = g.get("trusted_countries") or []
        assert value in tc, f"trusted_countries={tc}"

        # token marked used
        r2 = sess.get(f"{BASE_URL}/api/agents/runtime/trust-suggestion/{tok}", timeout=20)
        assert r2.status_code == 200
        assert r2.json().get("used") is True
    finally:
        # cleanup: remove value from trusted_countries + delete token
        async def _cleanup():
            await db.trust_add_tokens.delete_one({"token": tok})
            await db.organizations.update_one(
                {"_id": ObjectId(org_id)},
                {"$pull": {"trusted_countries": value}})
        _run(_cleanup())


# ---------- 2. Snooze reason (instant) ----------

def test_snooze_instant_with_reason_persists_and_clears(sess):
    reason = "SOC2 fieldwork"
    r = sess.post(f"{BASE_URL}/api/agents/runtime/alerts/snooze",
                  json={"hours": 8, "reason": reason}, timeout=20)
    assert r.status_code == 200, r.text[:300]
    j = r.json()
    assert j.get("snooze_reason") == reason

    g = sess.get(f"{BASE_URL}/api/agents/runtime/governance-settings", timeout=20).json()
    assert g.get("snooze_reason") == reason

    csv = _recent_audit_csv(sess)
    assert "agent.alerts_snoozed" in csv
    assert reason in csv, "audit detail should contain the reason"

    # resume clears
    r2 = sess.post(f"{BASE_URL}/api/agents/runtime/alerts/snooze",
                   json={"hours": 0}, timeout=20)
    assert r2.status_code == 200
    g2 = sess.get(f"{BASE_URL}/api/agents/runtime/governance-settings", timeout=20).json()
    assert not g2.get("snooze_reason")


# ---------- 3. Scheduled snooze reason ----------

def test_snooze_schedule_with_reason_persists_and_clears(sess):
    reason = "PCI audit week"
    start = (datetime.now(timezone.utc) + timedelta(days=10)).strftime("%Y-%m-%dT%H:%M:%SZ")
    end = (datetime.now(timezone.utc) + timedelta(days=12)).strftime("%Y-%m-%dT%H:%M:%SZ")
    r = sess.post(f"{BASE_URL}/api/agents/runtime/alerts/snooze-schedule",
                  json={"start": start, "end": end, "reason": reason}, timeout=20)
    assert r.status_code == 200, r.text[:300]
    j = r.json()
    assert j.get("snooze_window_reason") == reason

    g = sess.get(f"{BASE_URL}/api/agents/runtime/governance-settings", timeout=20).json()
    assert g.get("snooze_window_reason") == reason

    csv = _recent_audit_csv(sess)
    assert "agent.alerts_snooze_scheduled" in csv
    assert reason in csv

    # clear
    r2 = sess.post(f"{BASE_URL}/api/agents/runtime/alerts/snooze-schedule",
                   json={"start": "", "end": ""}, timeout=20)
    assert r2.status_code == 200
    g2 = sess.get(f"{BASE_URL}/api/agents/runtime/governance-settings", timeout=20).json()
    assert not g2.get("snooze_window_reason")


# ---------- 4. Digest preview ----------

def test_audit_digest_preview_returns_rows(sess):
    r = sess.get(f"{BASE_URL}/api/agents/runtime/audit-digest/preview", timeout=30)
    assert r.status_code == 200, r.text[:300]
    j = r.json()
    assert isinstance(j.get("changes"), int)
    assert isinstance(j.get("recipients"), list)
    rows = j.get("rows")
    assert isinstance(rows, list)
    # if there are rows, they should have the expected fields
    if rows:
        r0 = rows[0]
        for k in ("ts", "action", "actor", "detail"):
            assert k in r0

    # calling preview should NOT create an 'agent.audit_digest' send event
    # (i.e. changes stays the same across two calls, no digest send is logged)
    r2 = sess.get(f"{BASE_URL}/api/agents/runtime/audit-digest/preview", timeout=30)
    assert r2.status_code == 200
    # both invocations must produce identical row counts (no side effects)
    assert r2.json().get("changes") == j.get("changes")
