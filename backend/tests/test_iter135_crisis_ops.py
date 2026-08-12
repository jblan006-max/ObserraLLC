# Force serial execution — demo/seed is a shared resource; xdist workers race.
# Run with: pytest -o addopts="" backend/tests/test_iter135_crisis_ops.py

"""Iteration 135 — War Room Live Chat, Scheduled Board Brief, ServiceNow auto-ingest cron, per-obligation notify threshold."""
import os
import time
import pytest
import requests


def _load_backend_url():
    v = os.environ.get("REACT_APP_BACKEND_URL", "")
    if not v:
        with open("/app/frontend/.env") as f:
            for line in f:
                if line.startswith("REACT_APP_BACKEND_URL"):
                    v = line.split("=", 1)[1].strip().strip('"').strip("'")
                    break
    return v.rstrip("/")


BASE_URL = _load_backend_url()
ADMIN_EMAIL = "jblan2026@gmail.com"
ADMIN_PASSWORD = "Obserra2026!"


def _read_env_secret():
    with open("/app/backend/.env") as f:
        for line in f:
            if line.startswith("WEBHOOK_CRON_SECRET"):
                # Value may contain "=" chars, take everything after first "="
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    return ""


CRON_SECRET = _read_env_secret()


@pytest.fixture(scope="module")
def admin_session():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login",
               json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=20)
    assert r.status_code == 200, f"Login failed: {r.status_code} {r.text[:200]}"
    return s


@pytest.fixture(scope="module")
def demo_ref(admin_session):
    r = admin_session.post(f"{BASE_URL}/api/crisis/demo/seed", timeout=30)
    assert r.status_code == 200, f"seed failed: {r.text[:200]}"
    data = r.json()
    ref = data.get("ref") or (data.get("case") or {}).get("ref")
    assert ref, f"No ref returned: {data}"
    return ref


# ------------------------ War Room Live Chat --------------------------------
class TestWarRoomChat:
    def test_post_and_list_messages(self, admin_session, demo_ref):
        # Post two messages
        r1 = admin_session.post(
            f"{BASE_URL}/api/crisis/cases/{demo_ref}/messages",
            json={"text": "TEST_iter135 hello from admin"}, timeout=20)
        assert r1.status_code in (200, 201), r1.text[:200]
        m1 = r1.json()
        # Ensure no _id leak in POST response
        assert "_id" not in m1, f"_id leaked: {m1}"
        assert m1.get("text") == "TEST_iter135 hello from admin"
        assert m1.get("message_id", "").startswith("MSG-")
        assert m1.get("author")
        assert m1.get("created_at")

        time.sleep(0.5)
        r2 = admin_session.post(
            f"{BASE_URL}/api/crisis/cases/{demo_ref}/messages",
            json={"text": "TEST_iter135 second msg"}, timeout=20)
        assert r2.status_code in (200, 201)
        m2 = r2.json()
        assert "_id" not in m2

        # GET list ascending, no _id
        r3 = admin_session.get(
            f"{BASE_URL}/api/crisis/cases/{demo_ref}/messages", timeout=20)
        assert r3.status_code == 200
        msgs = r3.json()
        assert isinstance(msgs, list) and len(msgs) >= 2
        for m in msgs:
            assert "_id" not in m
        # Verify ascending order by created_at
        times = [m.get("created_at") for m in msgs]
        assert times == sorted(times), "messages not ascending by created_at"

        # Find our two test messages
        ids = {m.get("message_id") for m in msgs}
        assert m1["message_id"] in ids and m2["message_id"] in ids

    def test_empty_text_rejected(self, admin_session, demo_ref):
        r = admin_session.post(
            f"{BASE_URL}/api/crisis/cases/{demo_ref}/messages",
            json={"text": ""}, timeout=20)
        assert r.status_code in (400, 422), r.status_code

    def test_unauthenticated_forbidden(self, demo_ref):
        r = requests.post(
            f"{BASE_URL}/api/crisis/cases/{demo_ref}/messages",
            json={"text": "unauth"}, timeout=20)
        assert r.status_code in (401, 403), r.status_code


# ---------------------- Scheduled Board Brief -------------------------------
class TestScheduledBoardBrief:
    def test_patch_brief_schedule_hours_persists(self, admin_session, demo_ref):
        r = admin_session.patch(
            f"{BASE_URL}/api/crisis/cases/{demo_ref}",
            json={"brief_schedule_hours": 4}, timeout=20)
        assert r.status_code == 200, r.text[:200]
        # Returned case should have the field
        case = r.json()
        # PATCH may return {case: {...}} or the case itself
        c = case.get("case") if isinstance(case, dict) and "case" in case else case
        assert c.get("brief_schedule_hours") == 4, c

        # GET verifies persistence
        rg = admin_session.get(f"{BASE_URL}/api/crisis/cases/{demo_ref}", timeout=20)
        payload = rg.json()
        c2 = payload.get("case") or payload
        assert c2.get("brief_schedule_hours") == 4

    def test_cron_triggers_scheduled_brief_and_dedupes(self, admin_session, demo_ref):
        assert CRON_SECRET, "WEBHOOK_CRON_SECRET missing"

        # Clear brief_last_sent_at so brief is due
        # We can't PATCH to null via the API easily — but any prior cron will
        # have set it. To make the test deterministic, first set cadence to 4h
        # and force a "due" state by tolerating either outcome and asserting
        # that after the cron a Scheduled Brief event exists OR one already existed.
        admin_session.patch(
            f"{BASE_URL}/api/crisis/cases/{demo_ref}",
            json={"brief_schedule_hours": 4}, timeout=20)

        # First cron run — should attempt the send if due
        r1 = requests.post(
            f"{BASE_URL}/api/cron/hourly-overdue-digest",
            headers={"Authorization": f"Bearer {CRON_SECRET}"}, timeout=30)
        assert r1.status_code in (200, 202), f"{r1.status_code} {r1.text[:200]}"
        assert r1.json().get("status") in ("accepted", "ok")

        # Give background tasks a moment to run
        time.sleep(6)

        # Check case has brief_last_sent_at & Scheduled Brief Communication event
        rg = admin_session.get(f"{BASE_URL}/api/crisis/cases/{demo_ref}", timeout=20)
        payload = rg.json()
        c = payload.get("case") or payload
        events = payload.get("events") or []
        # brief_last_sent_at should be set now
        assert c.get("brief_last_sent_at"), f"brief_last_sent_at not set: {c.get('brief_last_sent_at')}"
        # A Communication event with source 'Scheduled Brief' should exist
        sched_events = [e for e in events
                        if e.get("source") == "Scheduled Brief"
                        or "Scheduled board brief" in (e.get("title") or "")]
        assert sched_events, f"No Scheduled Brief communication event found; got sources={[e.get('source') for e in events]}"

        first_last_sent = c.get("brief_last_sent_at")
        first_event_count = len(sched_events)

        # Second immediate cron run — cadence gate should prevent re-send
        r2 = requests.post(
            f"{BASE_URL}/api/cron/hourly-overdue-digest",
            headers={"Authorization": f"Bearer {CRON_SECRET}"}, timeout=30)
        assert r2.status_code in (200, 202)
        time.sleep(6)

        rg2 = admin_session.get(f"{BASE_URL}/api/crisis/cases/{demo_ref}", timeout=20)
        payload2 = rg2.json()
        c2 = payload2.get("case") or payload2
        events2 = payload2.get("events") or []
        sched_events2 = [e for e in events2
                         if e.get("source") == "Scheduled Brief"
                         or "Scheduled board brief" in (e.get("title") or "")]
        # Cadence gate: brief_last_sent_at not updated & no new event
        assert c2.get("brief_last_sent_at") == first_last_sent, (
            f"Cadence gate failed: {first_last_sent} -> {c2.get('brief_last_sent_at')}")
        assert len(sched_events2) == first_event_count, (
            f"Cadence gate failed: {first_event_count} -> {len(sched_events2)} events")


# -------------------- ServiceNow auto-ingest (cron) -------------------------
class TestServiceNowIngest:
    def test_manual_ingest_400_when_not_connected(self, admin_session):
        r = admin_session.post(f"{BASE_URL}/api/crisis/ingest/servicenow", timeout=20)
        assert r.status_code == 400, f"{r.status_code} {r.text[:200]}"
        detail = (r.json().get("detail") or "").lower()
        assert "servicenow" in detail and "connect" in detail

    def test_cron_401_without_bearer(self):
        r = requests.post(f"{BASE_URL}/api/cron/hourly-overdue-digest", timeout=20)
        assert r.status_code == 401

    def test_cron_401_wrong_bearer(self):
        r = requests.post(
            f"{BASE_URL}/api/cron/hourly-overdue-digest",
            headers={"Authorization": "Bearer wrong-secret"}, timeout=20)
        assert r.status_code == 401

    def test_cron_200_with_correct_bearer_noop_servicenow(self):
        assert CRON_SECRET
        r = requests.post(
            f"{BASE_URL}/api/cron/hourly-overdue-digest",
            headers={"Authorization": f"Bearer {CRON_SECRET}"}, timeout=30)
        assert r.status_code in (200, 202)
        assert r.json().get("status") in ("accepted", "ok")


# ------------------ Per-obligation notify threshold -------------------------
class TestObligationThreshold:
    def test_patch_notify_within_hours_persists(self, admin_session, demo_ref):
        # Create a fresh obligation
        payload = {
            "regulation": "TEST_iter135_threshold",
            "jurisdiction": "EU",
            "deadline_at": "2035-01-01T00:00:00+00:00",
            "status": "Assessing",
            "responsible": "Legal",
            "notify_within_hours": 24,
        }
        r = admin_session.post(
            f"{BASE_URL}/api/crisis/cases/{demo_ref}/obligations",
            json=payload, timeout=20)
        assert r.status_code in (200, 201), r.text[:200]
        obl = r.json()
        oid = obl.get("obligation_id") or obl.get("id")
        assert obl.get("notify_within_hours") == 24

        # PATCH to 6
        r2 = admin_session.patch(
            f"{BASE_URL}/api/crisis/cases/{demo_ref}/obligations/{oid}",
            json={"notify_within_hours": 6}, timeout=20)
        assert r2.status_code == 200
        assert r2.json().get("notify_within_hours") == 6

        # PATCH to 72
        r3 = admin_session.patch(
            f"{BASE_URL}/api/crisis/cases/{demo_ref}/obligations/{oid}",
            json={"notify_within_hours": 72}, timeout=20)
        assert r3.status_code == 200
        assert r3.json().get("notify_within_hours") == 72

    def test_regulatory_scan_honours_threshold(self, admin_session, demo_ref):
        from datetime import datetime, timezone, timedelta
        # Create an obligation with deadline ~2h out
        deadline = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()
        payload = {
            "regulation": "TEST_iter135_scan_honour",
            "jurisdiction": "EU",
            "deadline_at": deadline,
            "status": "Assessing",
            "responsible": "Legal",
            # Threshold below remaining hours -> NO alert expected on first pass
            "notify_within_hours": 1,
        }
        r = admin_session.post(
            f"{BASE_URL}/api/crisis/cases/{demo_ref}/obligations",
            json=payload, timeout=20)
        assert r.status_code in (200, 201), r.text[:200]
        oid = r.json().get("obligation_id") or r.json().get("id")

        # scan — the SPECIFIC obligation should not fire because 2h > 1h threshold
        # (other obligations may or may not fire; we only check this obligation's alert_state)
        s1 = admin_session.post(f"{BASE_URL}/api/crisis/regulatory/scan", timeout=30)
        assert s1.status_code == 200

        # Fetch obligation status via case detail
        rg = admin_session.get(f"{BASE_URL}/api/crisis/cases/{demo_ref}", timeout=20)
        payload_g = rg.json()
        obligations = payload_g.get("obligations") or (payload_g.get("case") or {}).get("obligations") or []
        me = next((o for o in obligations if (o.get("obligation_id") or o.get("id")) == oid), None)
        assert me, f"Obligation {oid} not found in case detail"
        # No alert should have been fired yet at threshold=1h with 2h remaining
        assert not me.get("alert_state"), (
            f"Obligation alerted at threshold=1h with 2h left: alert_state={me.get('alert_state')}")

        # Raise threshold above remaining hours -> alert should fire on next scan
        pr = admin_session.patch(
            f"{BASE_URL}/api/crisis/cases/{demo_ref}/obligations/{oid}",
            json={"notify_within_hours": 6}, timeout=20)
        assert pr.status_code == 200
        assert pr.json().get("notify_within_hours") == 6

        s2 = admin_session.post(f"{BASE_URL}/api/crisis/regulatory/scan", timeout=30)
        assert s2.status_code == 200

        rg2 = admin_session.get(f"{BASE_URL}/api/crisis/cases/{demo_ref}", timeout=20)
        payload_g2 = rg2.json()
        obligations2 = payload_g2.get("obligations") or (payload_g2.get("case") or {}).get("obligations") or []
        me2 = next((o for o in obligations2 if (o.get("obligation_id") or o.get("id")) == oid), None)
        assert me2, "Obligation missing after re-scan"
        assert me2.get("alert_state"), (
            f"Expected alert to fire at threshold=6h with ~2h left, alert_state={me2.get('alert_state')}")


# ---------------------- Regression sanity -----------------------------------
class TestRegression:
    def test_crisis_insight(self, admin_session, demo_ref):
        r = admin_session.get(f"{BASE_URL}/api/crisis/insight?ref={demo_ref}", timeout=60)
        assert r.status_code == 200
        d = r.json()
        assert "headline" in d and "insights" in d and "actions" in d

    def test_connectors_health(self, admin_session):
        r = admin_session.get(f"{BASE_URL}/api/connectors/health", timeout=20)
        assert r.status_code == 200

    def test_email_brief_still_lives(self, admin_session, demo_ref):
        r = admin_session.post(
            f"{BASE_URL}/api/crisis/cases/{demo_ref}/email-brief", timeout=60)
        assert r.status_code == 200
        d = r.json()
        assert "sent" in d and "recipients" in d
        assert d["sent"] >= 1
