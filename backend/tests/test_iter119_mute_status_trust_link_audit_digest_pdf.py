"""
Iteration 119 — Mute status, snooze reason required, trust_link_used audit, digest PDF.
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


@pytest.fixture(scope="module")
def sess():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login",
               json={"email": ADMIN_EMAIL, "password": ADMIN_PW}, timeout=20)
    assert r.status_code == 200, f"login: {r.status_code} {r.text[:200]}"
    return s


@pytest.fixture(scope="module")
def db():
    import motor.motor_asyncio
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


def _org_id(db):
    async def _go():
        u = await db.users.find_one({"email": ADMIN_EMAIL})
        return u["org_id"]
    return _run(_go())


# ---------- 1. mute-status ----------

def test_mute_status_unmuted_then_muted_then_resume(sess):
    # ensure clean
    sess.post(f"{BASE_URL}/api/agents/runtime/alerts/snooze", json={"hours": 0}, timeout=20)

    r = sess.get(f"{BASE_URL}/api/agents/runtime/alerts/mute-status", timeout=20)
    assert r.status_code == 200
    j = r.json()
    assert j.get("muted") is False, f"expected unmuted, got {j}"

    reason = "iter119 mute-status test"
    r2 = sess.post(f"{BASE_URL}/api/agents/runtime/alerts/snooze",
                   json={"hours": 8, "reason": reason}, timeout=20)
    assert r2.status_code == 200, r2.text[:300]

    r3 = sess.get(f"{BASE_URL}/api/agents/runtime/alerts/mute-status", timeout=20)
    assert r3.status_code == 200
    j3 = r3.json()
    assert j3.get("muted") is True
    assert j3.get("source") == "immediate"
    assert j3.get("reason") == reason
    assert j3.get("until")

    # Resume
    sess.post(f"{BASE_URL}/api/agents/runtime/alerts/snooze", json={"hours": 0}, timeout=20)
    r4 = sess.get(f"{BASE_URL}/api/agents/runtime/alerts/mute-status", timeout=20)
    assert r4.json().get("muted") is False


# ---------- 2. snooze reason required ----------

def test_snooze_instant_without_reason_400(sess):
    r = sess.post(f"{BASE_URL}/api/agents/runtime/alerts/snooze",
                  json={"hours": 8}, timeout=20)
    assert r.status_code == 400, r.text[:300]


def test_snooze_instant_with_reason_ok(sess):
    r = sess.post(f"{BASE_URL}/api/agents/runtime/alerts/snooze",
                  json={"hours": 8, "reason": "SOC2 fieldwork"}, timeout=20)
    assert r.status_code == 200, r.text[:300]
    # cleanup
    sess.post(f"{BASE_URL}/api/agents/runtime/alerts/snooze", json={"hours": 0}, timeout=20)


def test_snooze_schedule_without_reason_400(sess):
    start = (datetime.now(timezone.utc) + timedelta(days=20)).strftime("%Y-%m-%dT%H:%M:%SZ")
    end = (datetime.now(timezone.utc) + timedelta(days=22)).strftime("%Y-%m-%dT%H:%M:%SZ")
    r = sess.post(f"{BASE_URL}/api/agents/runtime/alerts/snooze-schedule",
                  json={"start": start, "end": end}, timeout=20)
    assert r.status_code == 400, r.text[:300]


def test_snooze_schedule_with_reason_ok(sess):
    start = (datetime.now(timezone.utc) + timedelta(days=20)).strftime("%Y-%m-%dT%H:%M:%SZ")
    end = (datetime.now(timezone.utc) + timedelta(days=22)).strftime("%Y-%m-%dT%H:%M:%SZ")
    r = sess.post(f"{BASE_URL}/api/agents/runtime/alerts/snooze-schedule",
                  json={"start": start, "end": end, "reason": "PCI audit"}, timeout=20)
    assert r.status_code == 200, r.text[:300]
    # cleanup
    sess.post(f"{BASE_URL}/api/agents/runtime/alerts/snooze-schedule",
              json={"start": "", "end": ""}, timeout=20)


# ---------- 3. trust_link_used audit entry ----------

def test_trust_apply_writes_trust_link_used_audit(sess, db):
    org_id = _org_id(db)
    tok = "TEST_" + secrets.token_urlsafe(16)
    value = "TESTlinkused"
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

        # Check audit-logs endpoint contains trust_link_used
        al = sess.get(f"{BASE_URL}/api/audit-logs?limit=50", timeout=20)
        assert al.status_code == 200, al.text[:200]
        logs = al.json()
        rows = logs if isinstance(logs, list) else (logs.get("items") or logs.get("logs") or [])
        actions = [(r.get("action") or "") for r in rows]
        assert any("trust_link_used" in a for a in actions), f"actions seen: {actions[:20]}"
        assert any("trusted_rules_changed" in a for a in actions), f"actions seen: {actions[:20]}"

        # find the trust_link_used entry and verify detail contains value and 'link minted'
        tlu = next((r for r in rows if "trust_link_used" in (r.get("action") or "")), None)
        assert tlu, "trust_link_used not in audit rows"
        detail_blob = str(tlu.get("detail") or "") + " " + str(tlu.get("meta") or "") + " " + str(tlu)
        assert value in detail_blob, f"value not in detail: {detail_blob[:400]}"
        assert "link minted" in detail_blob.lower(), f"'link minted' missing: {detail_blob[:400]}"
    finally:
        async def _cleanup():
            await db.trust_add_tokens.delete_one({"token": tok})
            await db.organizations.update_one(
                {"_id": ObjectId(org_id)},
                {"$pull": {"trusted_countries": value}})
        _run(_cleanup())


# ---------- 4. audit-digest.pdf ----------

def test_audit_digest_pdf_returns_pdf(sess):
    r = sess.get(f"{BASE_URL}/api/agents/runtime/audit-digest.pdf", timeout=30)
    assert r.status_code == 200, r.text[:300]
    assert "application/pdf" in (r.headers.get("content-type") or "").lower()
    assert r.content[:4] == b"%PDF", f"first bytes: {r.content[:20]!r}"
