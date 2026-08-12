# Force serial execution — demo/seed is a shared resource; xdist workers race.
# Run with: pytest -o addopts="" backend/tests/test_iter136_crisis_ops.py

"""Iteration 136 — Chat Mentions & Alerts, Turn-message-into-decision, Auto-Escalate Brief."""
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


def _get_case_detail(admin_session, ref):
    r = admin_session.get(f"{BASE_URL}/api/crisis/cases/{ref}", timeout=20)
    assert r.status_code == 200, r.text[:200]
    return r.json()


# ---------------------- Chat Mentions & Alerts ------------------------------
class TestChatMentions:
    def test_mentions_resolved_by_role_full_string(self, admin_session, demo_ref):
        # Fetch participants to find a real role
        detail = _get_case_detail(admin_session, demo_ref)
        participants = detail.get("participants") or []
        assert participants, "Demo case has no participants"
        # Pick a role that likely exists like 'Incident Commander'
        roles = [p.get("role") for p in participants if p.get("role")]
        assert roles, "No roles found on participants"
        # prefer 'Incident Commander' if present
        target_role = next((r for r in roles if r == "Incident Commander"), roles[0])

        text = f"@{target_role} please jump in"
        r = admin_session.post(
            f"{BASE_URL}/api/crisis/cases/{demo_ref}/messages",
            json={"text": text}, timeout=20)
        assert r.status_code in (200, 201), r.text[:200]
        m = r.json()
        assert "_id" not in m
        assert m.get("mentions"), f"mentions[] empty for text='{text}': {m}"
        # Should include the target role
        assert any(mm.get("role") == target_role for mm in m["mentions"]), m["mentions"]

    def test_partial_role_does_not_match(self, admin_session, demo_ref):
        # '@Legal' should NOT match 'Legal / Privacy'
        detail = _get_case_detail(admin_session, demo_ref)
        roles = [p.get("role") for p in (detail.get("participants") or [])]
        if not any(r and "Legal / Privacy" in r for r in roles):
            pytest.skip("Demo does not contain 'Legal / Privacy' role")
        r = admin_session.post(
            f"{BASE_URL}/api/crisis/cases/{demo_ref}/messages",
            json={"text": "@Legal quick question"}, timeout=20)
        assert r.status_code in (200, 201)
        m = r.json()
        # Should not match the compound role via partial
        assert not any(mm.get("role") == "Legal / Privacy" for mm in (m.get("mentions") or [])), m

    def test_no_mention_no_mentions_array(self, admin_session, demo_ref):
        r = admin_session.post(
            f"{BASE_URL}/api/crisis/cases/{demo_ref}/messages",
            json={"text": "TEST_iter136 plain message no mention"}, timeout=20)
        assert r.status_code in (200, 201)
        m = r.json()
        assert m.get("mentions") == [] or m.get("mentions") is None


# ------------------- Turn message into decision -----------------------------
class TestMessageToAction:
    def test_convert_message_creates_decision_action(self, admin_session, demo_ref):
        # Post a message
        text = "TEST_iter136 decide whether to isolate segment A"
        r = admin_session.post(
            f"{BASE_URL}/api/crisis/cases/{demo_ref}/messages",
            json={"text": text}, timeout=20)
        assert r.status_code in (200, 201), r.text[:200]
        m = r.json()
        mid = m.get("message_id")
        assert mid and mid.startswith("MSG-")

        # Convert
        r2 = admin_session.post(
            f"{BASE_URL}/api/crisis/cases/{demo_ref}/messages/{mid}/to-action",
            timeout=20)
        assert r2.status_code in (200, 201), r2.text[:200]
        act = r2.json()
        assert "_id" not in act
        assert act.get("action_type") == "Decision"
        assert act.get("status") == "Awaiting Approval"
        assert act.get("decision_required") is True
        assert act.get("source") == "War Room Chat"
        assert (act.get("title") or "").startswith("TEST_iter136 decide")
        act_id = act.get("action_id")
        assert act_id and act_id.startswith("ACT-")

        # 400 on duplicate convert
        r3 = admin_session.post(
            f"{BASE_URL}/api/crisis/cases/{demo_ref}/messages/{mid}/to-action",
            timeout=20)
        assert r3.status_code == 400, r3.text[:200]
        assert act_id in (r3.json().get("detail") or ""), r3.text

        # Message flagged converted in listing
        rlist = admin_session.get(
            f"{BASE_URL}/api/crisis/cases/{demo_ref}/messages", timeout=20)
        assert rlist.status_code == 200
        listed = next((mm for mm in rlist.json() if mm.get("message_id") == mid), None)
        assert listed and listed.get("converted_action_id") == act_id

        # Timeline event 'Decision' added and action appears in case actions
        det = _get_case_detail(admin_session, demo_ref)
        events = det.get("events") or []
        dec_events = [e for e in events if e.get("kind") == "Decision"
                      and act_id in (e.get("title") or "")]
        assert dec_events, f"No Decision timeline event for {act_id}"
        actions = det.get("actions") or []
        our = next((a for a in actions if a.get("action_id") == act_id), None)
        assert our and our.get("status") == "Awaiting Approval"
        assert our.get("source") == "War Room Chat"

        # Approve via existing approve flow — verify status transitions
        # (approve endpoint per code base — typically PATCH action or /approve)
        # Try common patterns; skip if not present
        approve_url = f"{BASE_URL}/api/crisis/cases/{demo_ref}/actions/{act_id}/approve"
        ra = admin_session.post(approve_url, json={"outcome": "Approved"}, timeout=20)
        if ra.status_code == 404:
            # Try PATCH status
            ra2 = admin_session.patch(
                f"{BASE_URL}/api/crisis/cases/{demo_ref}/actions/{act_id}",
                json={"status": "Approved", "outcome": "OK"}, timeout=20)
            assert ra2.status_code == 200, f"Approve flow missing/broken: {ra2.status_code} {ra2.text[:200]}"
        else:
            assert ra.status_code == 200, ra.text[:200]

    def test_convert_missing_message_404(self, admin_session, demo_ref):
        r = admin_session.post(
            f"{BASE_URL}/api/crisis/cases/{demo_ref}/messages/MSG-DOES-NOT-EXIST/to-action",
            timeout=20)
        assert r.status_code == 404


# --------------------- Auto-Escalate Brief ----------------------------------
class TestAutoEscalate:
    def test_high_to_critical_sets_cadence_4_and_writes_event(self, admin_session, demo_ref):
        # First move to High and clear cadence to 0
        r0 = admin_session.patch(
            f"{BASE_URL}/api/crisis/cases/{demo_ref}",
            json={"severity": "High", "brief_schedule_hours": 0}, timeout=20)
        assert r0.status_code == 200, r0.text[:200]
        c0 = r0.json()
        c0 = c0.get("case") if isinstance(c0, dict) and "case" in c0 else c0
        assert c0.get("severity") == "High"
        assert int(c0.get("brief_schedule_hours") or 0) == 0

        # Count Auto-Escalation events before
        det_before = _get_case_detail(admin_session, demo_ref)
        before_ae = [e for e in (det_before.get("events") or []) if e.get("source") == "Auto-Escalation"]

        # Now transition to Critical
        r = admin_session.patch(
            f"{BASE_URL}/api/crisis/cases/{demo_ref}",
            json={"severity": "Critical"}, timeout=20)
        assert r.status_code == 200, r.text[:200]
        c = r.json()
        c = c.get("case") if isinstance(c, dict) and "case" in c else c
        assert c.get("severity") == "Critical"
        assert int(c.get("brief_schedule_hours") or 0) == 4, f"cadence not auto-set: {c.get('brief_schedule_hours')}"

        det_after = _get_case_detail(admin_session, demo_ref)
        ae_after = [e for e in (det_after.get("events") or []) if e.get("source") == "Auto-Escalation"]
        assert len(ae_after) == len(before_ae) + 1, (
            f"Auto-Escalation event not written: before={len(before_ae)} after={len(ae_after)}")
        # Verify the last event mentions 4h
        last = ae_after[-1]
        assert "4h" in (last.get("title") or "") or "every 4" in (last.get("title") or "").lower(), last

    def test_already_critical_does_not_re_escalate(self, admin_session, demo_ref):
        # Ensure severity is Critical (from previous test). Force cadence to 24 first
        r0 = admin_session.patch(
            f"{BASE_URL}/api/crisis/cases/{demo_ref}",
            json={"brief_schedule_hours": 24}, timeout=20)
        assert r0.status_code == 200
        # Count AE events
        det_before = _get_case_detail(admin_session, demo_ref)
        c_before = det_before.get("case") or det_before
        assert c_before.get("severity") == "Critical"
        before_ae = [e for e in (det_before.get("events") or []) if e.get("source") == "Auto-Escalation"]

        # PATCH severity=Critical (already Critical) — should NOT re-escalate
        r = admin_session.patch(
            f"{BASE_URL}/api/crisis/cases/{demo_ref}",
            json={"severity": "Critical"}, timeout=20)
        assert r.status_code == 200
        c = r.json()
        c = c.get("case") if isinstance(c, dict) and "case" in c else c
        # cadence must remain 24 (user's explicit value from setup, not overridden)
        assert int(c.get("brief_schedule_hours") or 0) == 24, c.get("brief_schedule_hours")

        det_after = _get_case_detail(admin_session, demo_ref)
        ae_after = [e for e in (det_after.get("events") or []) if e.get("source") == "Auto-Escalation"]
        assert len(ae_after) == len(before_ae), (
            f"Should NOT re-escalate: before={len(before_ae)} after={len(ae_after)}")

    def test_user_explicit_cadence_respected_on_critical_transition(self, admin_session, demo_ref):
        # Move back to High with any cadence
        r0 = admin_session.patch(
            f"{BASE_URL}/api/crisis/cases/{demo_ref}",
            json={"severity": "High", "brief_schedule_hours": 0}, timeout=20)
        assert r0.status_code == 200

        det_before = _get_case_detail(admin_session, demo_ref)
        before_ae = [e for e in (det_before.get("events") or []) if e.get("source") == "Auto-Escalation"]

        # Transition to Critical WITH explicit brief_schedule_hours=24 in same PATCH
        r = admin_session.patch(
            f"{BASE_URL}/api/crisis/cases/{demo_ref}",
            json={"severity": "Critical", "brief_schedule_hours": 24}, timeout=20)
        assert r.status_code == 200, r.text[:200]
        c = r.json()
        c = c.get("case") if isinstance(c, dict) and "case" in c else c
        assert c.get("severity") == "Critical"
        # user's 24 should be respected — NOT overridden to 4
        assert int(c.get("brief_schedule_hours") or 0) == 24, (
            f"User cadence overridden: {c.get('brief_schedule_hours')}")

        det_after = _get_case_detail(admin_session, demo_ref)
        ae_after = [e for e in (det_after.get("events") or []) if e.get("source") == "Auto-Escalation"]
        # No Auto-Escalation event should be written when user sets cadence explicitly
        assert len(ae_after) == len(before_ae), (
            f"Should not auto-escalate when user set cadence explicitly: "
            f"before={len(before_ae)} after={len(ae_after)}")


# ---------------------- Regression sanity (iter136) -------------------------
class TestRegression:
    def test_roster_and_chat_baseline(self, admin_session, demo_ref):
        # roster/participants readable
        det = _get_case_detail(admin_session, demo_ref)
        assert det.get("participants"), "Demo participants missing"
        # chat list still returns no _id
        r = admin_session.get(f"{BASE_URL}/api/crisis/cases/{demo_ref}/messages", timeout=20)
        assert r.status_code == 200
        for m in r.json():
            assert "_id" not in m

    def test_connectors_health(self, admin_session):
        r = admin_session.get(f"{BASE_URL}/api/connectors/health", timeout=20)
        assert r.status_code == 200

    def test_servicenow_manual_ingest_400_when_not_connected(self, admin_session):
        r = admin_session.post(f"{BASE_URL}/api/crisis/ingest/servicenow", timeout=20)
        assert r.status_code == 400
        detail = (r.json().get("detail") or "").lower()
        assert "servicenow" in detail and "connect" in detail

    def test_crisis_insight_grounded(self, admin_session, demo_ref):
        r = admin_session.get(f"{BASE_URL}/api/crisis/insight?ref={demo_ref}", timeout=60)
        assert r.status_code == 200
        d = r.json()
        assert "headline" in d and "insights" in d and "actions" in d
