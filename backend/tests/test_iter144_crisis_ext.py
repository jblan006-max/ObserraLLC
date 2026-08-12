"""Iter144 — Cyber Crisis Commander: Connector Health, Board Auto-Present, Auto-SITREP cadence.

Uses REACT_APP_BACKEND_URL for network APIs. Imports crisis_commander directly
for the in-process run_scheduled_sitreps invocation to avoid triggering
unrelated hourly-cron side effects.
"""
import asyncio
import os
import sys
import time
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    # dotenv-style fallback for pytest runs outside supervisor
    try:
        for line in open("/app/frontend/.env"):
            if line.startswith("REACT_APP_BACKEND_URL="):
                BASE_URL = line.split("=", 1)[1].strip().rstrip("/")
                break
    except Exception:
        pass

ADMIN_EMAIL = "jblan2026@gmail.com"
ADMIN_PASSWORD = "Obserra2026!"


@pytest.fixture(scope="module")
def sess():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    r = s.post(f"{BASE_URL}/api/auth/login",
               json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=20)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text[:200]}"
    return s


@pytest.fixture(scope="module")
def secret(sess):
    r = sess.get(f"{BASE_URL}/api/crisis/connectors/native", timeout=15)
    assert r.status_code == 200
    body = r.json()
    assert "secret" in body and body["secret"], "connector secret missing"
    return body["secret"]


# ==========================
# FEATURE 1 — Connector Health
# ==========================
class TestConnectorHealth:
    def test_native_includes_health_fields(self, sess):
        r = sess.get(f"{BASE_URL}/api/crisis/connectors/native", timeout=15)
        assert r.status_code == 200
        body = r.json()
        assert isinstance(body.get("connectors"), list) and len(body["connectors"]) >= 5
        for c in body["connectors"]:
            assert "last_received" in c
            assert "count" in c

    def test_connectors_health_endpoint(self, sess):
        r = sess.get(f"{BASE_URL}/api/crisis/connectors/health", timeout=15)
        assert r.status_code == 200
        body = r.json()
        assert "health" in body and isinstance(body["health"], dict)

    def test_splunk_ingest_updates_health(self, sess, secret):
        # baseline
        r0 = sess.get(f"{BASE_URL}/api/crisis/connectors/native", timeout=15).json()
        baseline = next((c for c in r0["connectors"] if c["vendor"] == "splunk"), None)
        assert baseline is not None
        base_count = int(baseline.get("count") or 0)

        # push a small splunk-shaped payload
        payload = {
            "result": {
                "search_name": "TEST_ITER144 splunk detection",
                "_time": "2026-01-15T10:00:00Z",
                "message": "TEST_ITER144 splunk sample",
                "severity": "high",
            }
        }
        r = requests.post(
            f"{BASE_URL}/api/crisis/ingest/native/splunk?secret={secret}",
            json=payload, timeout=15)
        assert r.status_code == 200, f"ingest failed {r.status_code} {r.text[:200]}"
        assert r.json().get("ok") is True
        assert r.json().get("ingested", 0) >= 1

        # confirm health flipped
        r2 = sess.get(f"{BASE_URL}/api/crisis/connectors/native", timeout=15).json()
        after = next((c for c in r2["connectors"] if c["vendor"] == "splunk"), None)
        assert after is not None
        assert after["last_received"], "splunk last_received still null"
        assert int(after["count"] or 0) >= base_count + 1

        # /connectors/health mirrors it
        h = sess.get(f"{BASE_URL}/api/crisis/connectors/health", timeout=15).json()["health"]
        assert "splunk" in h
        assert h["splunk"].get("last_received")


# ==========================
# FEATURE 2 — Board Auto-Present on real close
# ==========================
class TestBoardAutoPresentOnClose:
    def test_close_real_case_triggers_autopresent(self, sess):
        # Create throwaway case
        payload = {
            "title": "TEST_ITER144 throwaway close autopresent",
            "severity": "Low",
            "summary": "TEST_ITER144 — automated regression case; safe to delete.",
        }
        r = sess.post(f"{BASE_URL}/api/crisis/cases", json=payload, timeout=15)
        assert r.status_code == 200, f"create failed {r.status_code} {r.text[:200]}"
        case = r.json()
        ref = case["ref"]
        assert ref.startswith("CRISIS-")

        try:
            # Close it — should trigger _auto_present_board
            rp = sess.patch(f"{BASE_URL}/api/crisis/cases/{ref}",
                            json={"status": "Closed"}, timeout=20)
            assert rp.status_code == 200
            # Give it a moment (auto-present is inline, but be safe)
            time.sleep(1.5)

            # Verify Timeline event exists
            tl = sess.get(f"{BASE_URL}/api/crisis/cases/{ref}/timeline", timeout=15)
            assert tl.status_code == 200
            data = tl.json()
            events = data.get("events") if isinstance(data, dict) else data
            assert isinstance(events, list) and events
            auto_ev = [e for e in events if e.get("source") == "Auto-Present"]
            assert len(auto_ev) >= 1, f"no Auto-Present event; events={[e.get('title') for e in events]}"
            title = auto_ev[0].get("title", "")
            assert "Board snapshot auto-prepared on close" in title
            assert "director" in title.lower()

            # Verify a snapshot exists (non-revoked)
            sn = sess.get(f"{BASE_URL}/api/crisis/cases/{ref}/snapshot", timeout=15)
            assert sn.status_code == 200
            snap_body = sn.json()
            token = None
            if isinstance(snap_body, dict):
                token = snap_body.get("token") or (snap_body.get("snapshot") or {}).get("token")
                if not token and isinstance(snap_body.get("snapshots"), list) and snap_body["snapshots"]:
                    token = snap_body["snapshots"][0].get("token")
            assert token, f"no snapshot token found: {snap_body}"

            # Revoke snapshot cleanup
            try:
                sess.post(f"{BASE_URL}/api/crisis/cases/{ref}/snapshot/revoke",
                          json={"token": token}, timeout=15)
            except Exception:
                pass
        finally:
            # Best-effort cleanup: delete the throwaway case + its events/snapshots via Mongo
            _delete_case_via_mongo(ref)

    def test_demo_case_close_does_not_trigger(self, sess):
        # Insert a demo-flagged case directly, close via API, ensure no Auto-Present event.
        ref = _insert_demo_case_via_mongo(sess)
        try:
            rp = sess.patch(f"{BASE_URL}/api/crisis/cases/{ref}",
                            json={"status": "Closed"}, timeout=20)
            assert rp.status_code == 200
            time.sleep(1.0)
            tl = sess.get(f"{BASE_URL}/api/crisis/cases/{ref}/timeline", timeout=15).json()
            events = tl.get("events") if isinstance(tl, dict) else tl
            auto_ev = [e for e in (events or []) if e.get("source") == "Auto-Present"]
            assert len(auto_ev) == 0, "Auto-Present ran for demo case (should be skipped)"
        finally:
            _delete_case_via_mongo(ref)


# ==========================
# FEATURE 4 — Auto-SITREP cadence
# ==========================
class TestAutoSitrepCadence:
    def test_sitrep_schedule_hours_patch_persists(self, sess):
        # create throwaway
        r = sess.post(f"{BASE_URL}/api/crisis/cases",
                      json={"title": "TEST_ITER144 sitrep cadence",
                            "severity": "Low",
                            "summary": "TEST_ITER144"}, timeout=15)
        assert r.status_code == 200
        ref = r.json()["ref"]
        try:
            for hrs in (4, 12, 24, 0):
                rp = sess.patch(f"{BASE_URL}/api/crisis/cases/{ref}",
                                json={"sitrep_schedule_hours": hrs}, timeout=15)
                assert rp.status_code == 200
                got = sess.get(f"{BASE_URL}/api/crisis/cases/{ref}", timeout=15).json()
                case = got.get("case", got)
                assert int(case.get("sitrep_schedule_hours") or 0) == hrs
        finally:
            _delete_case_via_mongo(ref)

    def test_run_scheduled_sitreps_writes_single_event(self, sess):
        # Create throwaway ACTIVE case
        r = sess.post(f"{BASE_URL}/api/crisis/cases",
                      json={"title": "TEST_ITER144 sitrep run",
                            "severity": "Low",
                            "summary": "TEST_ITER144"}, timeout=15)
        assert r.status_code == 200
        ref = r.json()["ref"]
        # Set cadence 4h
        sess.patch(f"{BASE_URL}/api/crisis/cases/{ref}",
                   json={"sitrep_schedule_hours": 4}, timeout=15)
        # Call run_scheduled_sitreps directly, monkey-patch chat post to no-op to keep test safe.
        try:
            sys.path.insert(0, "/app/backend")
            # Load backend .env into os.environ before importing crisis_commander
            for line in open("/app/backend/.env"):
                if "=" in line and not line.strip().startswith("#"):
                    k, _, v = line.strip().partition("=")
                    os.environ.setdefault(k, v.strip().strip('"').strip("'"))
            import importlib
            cc = importlib.import_module("crisis_commander")
            org_id = _org_id_for_email(ADMIN_EMAIL)
            assert org_id, "org_id not resolvable"

            # Patch the imported symbol resolved inside run_scheduled_sitreps
            import self_scan as _ss
            original = getattr(_ss, "_post_chat_alert", None)
            calls = {"n": 0}

            async def _no_op_post(oid, title, text):
                calls["n"] += 1
                return None

            _ss._post_chat_alert = _no_op_post
            try:
                sent = asyncio.get_event_loop().run_until_complete(
                    cc.run_scheduled_sitreps(org_id=org_id)
                ) if False else asyncio.run(cc.run_scheduled_sitreps(org_id=org_id))
            finally:
                if original is not None:
                    _ss._post_chat_alert = original

            assert sent >= 1, f"expected >=1 sitrep sent, got {sent}"

            # Confirm exactly one Auto-SITREP timeline event on THIS case
            tl = sess.get(f"{BASE_URL}/api/crisis/cases/{ref}/timeline", timeout=15).json()
            events = tl.get("events") if isinstance(tl, dict) else tl
            auto = [e for e in (events or []) if e.get("source") == "Auto-SITREP"]
            assert len(auto) == 1, f"expected exactly 1 Auto-SITREP event, got {len(auto)}"
            assert "Auto-SITREP posted to leadership chat" in auto[0].get("title", "")
        finally:
            # Reset cadence and cleanup
            try:
                sess.patch(f"{BASE_URL}/api/crisis/cases/{ref}",
                           json={"sitrep_schedule_hours": 0}, timeout=15)
            except Exception:
                pass
            _delete_case_via_mongo(ref)


# ==========================
# Helpers (Mongo direct — cleanup + demo insert)
# ==========================
def _mongo_db():
    sys.path.insert(0, "/app/backend")
    from pymongo import MongoClient
    url = os.environ.get("MONGO_URL")
    dbname = os.environ.get("DB_NAME")
    if not url:
        # read from backend/.env
        for line in open("/app/backend/.env"):
            k, _, v = line.strip().partition("=")
            if k == "MONGO_URL":
                url = v.strip().strip('"').strip("'")
            elif k == "DB_NAME":
                dbname = v.strip().strip('"').strip("'")
    return MongoClient(url)[dbname]


def _org_id_for_email(email: str) -> str:
    db = _mongo_db()
    u = db.users.find_one({"email": email})
    return str(u["org_id"]) if u else ""


def _delete_case_via_mongo(ref: str):
    try:
        db = _mongo_db()
        db.crisis_cases.delete_many({"ref": ref})
        db.crisis_events.delete_many({"case_ref": ref})
        db.crisis_snapshots.delete_many({"case_ref": ref})
        db.crisis_actions.delete_many({"case_ref": ref})
        db.crisis_participants.delete_many({"case_ref": ref})
        db.crisis_recovery.delete_many({"case_ref": ref})
        db.crisis_obligations.delete_many({"case_ref": ref})
    except Exception as e:
        print("cleanup failed:", e)


def _insert_demo_case_via_mongo(sess) -> str:
    """Create case via API then flag demo:true directly in Mongo."""
    r = sess.post(f"{BASE_URL}/api/crisis/cases",
                  json={"title": "TEST_ITER144 demo skip",
                        "severity": "Low",
                        "summary": "TEST_ITER144 demo"}, timeout=15)
    ref = r.json()["ref"]
    db = _mongo_db()
    db.crisis_cases.update_one({"ref": ref}, {"$set": {"demo": True}})
    return ref
