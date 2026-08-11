"""
Iteration 117 — Alert Test Ping + Scheduled Snooze + Audit Digest + One-click Trust suggestion
"""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    with open("/app/frontend/.env") as f:
        for ln in f:
            if ln.startswith("REACT_APP_BACKEND_URL="):
                BASE_URL = ln.split("=", 1)[1].strip().rstrip("/")

ADMIN_EMAIL = "jblan2026@gmail.com"
ADMIN_PW = "Obserra2026!"
TRUST_TOKEN = "Z8mUUfQKCp6TO73ylE8h5iajulib6LHw"


@pytest.fixture(scope="module")
def sess():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login",
               json={"email": ADMIN_EMAIL, "password": ADMIN_PW}, timeout=20)
    assert r.status_code == 200, f"login: {r.status_code} {r.text[:200]}"
    return s


def _recent_audit_actions(sess, limit=50):
    r = sess.get(f"{BASE_URL}/api/agents/runtime/audit-log.csv", timeout=20)
    assert r.status_code == 200, r.text[:200]
    # csv: header + rows; return the joined text (we just search for action strings)
    return r.text


# ---------- 1. Alert Test Ping ----------
def test_alerts_test_ping(sess):
    r = sess.post(f"{BASE_URL}/api/agents/runtime/alerts/test", json={}, timeout=25)
    assert r.status_code == 200, r.text[:300]
    j = r.json()
    assert j.get("ok") is True
    assert isinstance(j.get("emails"), list)
    assert isinstance(j.get("webhook"), bool)
    assert isinstance(j.get("chat_fallback"), bool)

    actions = _recent_audit_actions(sess, 20)
    assert "agent.alerts_test" in actions, "audit missing agent.alerts_test"


# ---------- 2. Scheduled Snooze ----------
def test_snooze_schedule_set_400_and_clear(sess):
    # set valid future window (within ~1 year)
    from datetime import datetime, timedelta, timezone
    start = (datetime.now(timezone.utc) + timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
    end = (datetime.now(timezone.utc) + timedelta(days=31)).strftime("%Y-%m-%dT%H:%M:%SZ")
    payload = {"start": start, "end": end}
    r = sess.post(f"{BASE_URL}/api/agents/runtime/alerts/snooze-schedule", json=payload, timeout=20)
    assert r.status_code == 200, r.text[:300]

    g = sess.get(f"{BASE_URL}/api/agents/runtime/governance-settings", timeout=20).json()
    assert g.get("snooze_window_start")
    assert g.get("snooze_window_end")

    actions = _recent_audit_actions(sess, 20)
    assert "agent.alerts_snooze_scheduled" in actions

    # invalid: end <= start
    bad = {"start": end, "end": start}
    r2 = sess.post(f"{BASE_URL}/api/agents/runtime/alerts/snooze-schedule", json=bad, timeout=20)
    assert r2.status_code == 400

    # clear
    r3 = sess.post(f"{BASE_URL}/api/agents/runtime/alerts/snooze-schedule",
                   json={"start": "", "end": ""}, timeout=20)
    assert r3.status_code == 200
    g2 = sess.get(f"{BASE_URL}/api/agents/runtime/governance-settings", timeout=20).json()
    assert not g2.get("snooze_window_start")
    assert not g2.get("snooze_window_end")

    actions2 = _recent_audit_actions(sess, 20)
    assert "agent.alerts_snooze_schedule_cleared" in actions2


# ---------- 3. Audit Digest ----------
def test_audit_digest_settings_roundtrip_and_send(sess):
    payload = {
        "audit_digest_enabled": True,
        "audit_digest_recipients": ["Board@Example.com", "bad", "cfo@example.com"],
    }
    r = sess.put(f"{BASE_URL}/api/agents/runtime/governance-settings", json=payload, timeout=20)
    assert r.status_code == 200, r.text[:300]
    j = r.json()
    assert j.get("audit_digest_enabled") is True
    recips = j.get("audit_digest_recipients") or []
    assert "board@example.com" in [x.lower() for x in recips]
    assert "cfo@example.com" in [x.lower() for x in recips]
    assert "bad" not in [x.lower() for x in recips]

    # round-trip
    g = sess.get(f"{BASE_URL}/api/agents/runtime/governance-settings", timeout=20).json()
    assert g.get("audit_digest_enabled") is True
    assert any("board@example.com" == x.lower() for x in (g.get("audit_digest_recipients") or []))

    # send now
    r2 = sess.post(f"{BASE_URL}/api/agents/runtime/audit-digest/send", json={}, timeout=60)
    assert r2.status_code == 200, r2.text[:300]
    j2 = r2.json()
    assert "sent" in j2 and "changes" in j2
    assert isinstance(j2["sent"], int) and isinstance(j2["changes"], int)

    actions = _recent_audit_actions(sess, 20)
    assert "agent.audit_digest" in actions


# ---------- 4. Trust Suggestion ----------
def test_trust_suggestion_lookup_bogus_404(sess):
    r = sess.get(f"{BASE_URL}/api/agents/runtime/trust-suggestion/DOESNOTEXIST_XYZ", timeout=20)
    assert r.status_code == 404


def test_trust_suggestion_get_and_apply(sess):
    # GET (should be seeded, unused)
    r = sess.get(f"{BASE_URL}/api/agents/runtime/trust-suggestion/{TRUST_TOKEN}", timeout=20)
    assert r.status_code == 200, r.text[:300]
    j = r.json()
    assert j.get("kind") == "country"
    assert j.get("value") == "Testland"
    # Note: if already used from previous run, still 200 with used=True; apply may 4xx
    was_used = bool(j.get("used"))

    # Apply
    r2 = sess.post(f"{BASE_URL}/api/agents/runtime/trust-suggestion/{TRUST_TOKEN}/apply",
                   json={}, timeout=20)
    if was_used:
        # already consumed - just accept 200/400/409
        assert r2.status_code in (200, 400, 409)
    else:
        assert r2.status_code == 200, r2.text[:300]
        # verify trusted_countries now contains Testland
        g = sess.get(f"{BASE_URL}/api/agents/runtime/governance-settings", timeout=20).json()
        tc = g.get("trusted_countries") or []
        assert any(x.lower() == "testland" for x in tc), f"trusted_countries={tc}"
        actions = _recent_audit_actions(sess, 20)
        assert "agent.trusted_rules_changed" in actions

        # token should now be marked used
        r3 = sess.get(f"{BASE_URL}/api/agents/runtime/trust-suggestion/{TRUST_TOKEN}", timeout=20)
        if r3.status_code == 200:
            assert r3.json().get("used") is True
