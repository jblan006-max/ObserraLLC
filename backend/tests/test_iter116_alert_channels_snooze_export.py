"""
Iteration 116 — Alert Channels + Snooze Alerts + Audit CSV/PDF Export
Tests the new fields on governance-settings, snooze endpoint w/ audit logging,
and audit-log.csv / audit-log.pdf (with ?trusted=true filter).
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


@pytest.fixture(scope="module")
def sess():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login",
               json={"email": ADMIN_EMAIL, "password": ADMIN_PW}, timeout=20)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text[:200]}"
    return s


# ---------- governance-settings new keys ----------
def test_governance_settings_has_new_keys(sess):
    r = sess.get(f"{BASE_URL}/api/agents/runtime/governance-settings", timeout=20)
    assert r.status_code == 200
    j = r.json()
    assert "alert_channel_emails" in j and isinstance(j["alert_channel_emails"], list)
    assert "alert_channel_webhook" in j and isinstance(j["alert_channel_webhook"], str)
    assert "snooze_alerts_until" in j and isinstance(j["snooze_alerts_until"], str)


def test_put_persists_emails_and_valid_webhook(sess):
    payload = {
        "alert_channel_emails": ["Alice@Example.com", "bob@example.com", "alice@example.com", "bogus"],
        "alert_channel_webhook": "https://hooks.slack.com/services/TEST/IT116/xyz",
    }
    r = sess.put(f"{BASE_URL}/api/agents/runtime/governance-settings", json=payload, timeout=20)
    assert r.status_code == 200
    j = r.json()
    # lowercased, deduped, invalid dropped
    assert sorted(j["alert_channel_emails"]) == ["alice@example.com", "bob@example.com"]
    assert j["alert_channel_webhook"] == "https://hooks.slack.com/services/TEST/IT116/xyz"

    # round-trip GET
    r2 = sess.get(f"{BASE_URL}/api/agents/runtime/governance-settings", timeout=20)
    j2 = r2.json()
    assert sorted(j2["alert_channel_emails"]) == ["alice@example.com", "bob@example.com"]
    assert j2["alert_channel_webhook"].startswith("https://")


def test_put_rejects_non_http_webhook(sess):
    r = sess.put(f"{BASE_URL}/api/agents/runtime/governance-settings",
                 json={"alert_channel_webhook": "ftp://evil.example/abc"}, timeout=20)
    assert r.status_code == 200
    assert r.json()["alert_channel_webhook"] == ""


# ---------- snooze + audit logging ----------
def test_snooze_sets_and_clears_with_audit(sess):
    # snooze 24h
    r = sess.post(f"{BASE_URL}/api/agents/runtime/alerts/snooze", json={"hours": 24}, timeout=20)
    assert r.status_code == 200
    j = r.json()
    assert j.get("ok") is True
    assert j.get("snooze_alerts_until", "").startswith("20")  # ISO ts

    g = sess.get(f"{BASE_URL}/api/agents/runtime/governance-settings", timeout=20).json()
    assert g["snooze_alerts_until"] == j["snooze_alerts_until"]

    # clear
    r2 = sess.post(f"{BASE_URL}/api/agents/runtime/alerts/snooze", json={"hours": 0}, timeout=20)
    assert r2.status_code == 200
    assert r2.json().get("snooze_alerts_until") == ""

    g2 = sess.get(f"{BASE_URL}/api/agents/runtime/governance-settings", timeout=20).json()
    assert g2["snooze_alerts_until"] == ""

    # audit-logs contain both actions
    al = sess.get(f"{BASE_URL}/api/audit-logs", timeout=20)
    assert al.status_code == 200
    entries = al.json()
    actions = [e.get("action") for e in (entries if isinstance(entries, list) else entries.get("items") or [])]
    assert "agent.alerts_snoozed" in actions
    assert "agent.alerts_snooze_cleared" in actions


# ---------- audit exports ----------
def test_audit_log_csv_full(sess):
    r = sess.get(f"{BASE_URL}/api/agents/runtime/audit-log.csv", timeout=30)
    assert r.status_code == 200
    assert "text/csv" in r.headers.get("content-type", "")
    body = r.text
    assert "Obserra" in body
    assert "Timestamp (UTC)" in body


def test_audit_log_csv_trusted_only(sess):
    # ensure at least one trusted rule change exists by toggling a trusted country
    cur = sess.get(f"{BASE_URL}/api/agents/runtime/governance-settings", timeout=20).json()
    countries = list(cur.get("trusted_countries") or [])
    if "ZZ" in countries:
        new_c = [c for c in countries if c != "ZZ"]
    else:
        new_c = countries + ["ZZ"]
    sess.put(f"{BASE_URL}/api/agents/runtime/governance-settings",
             json={"trusted_countries": new_c}, timeout=20)

    r = sess.get(f"{BASE_URL}/api/agents/runtime/audit-log.csv?trusted=true", timeout=30)
    assert r.status_code == 200
    assert "text/csv" in r.headers.get("content-type", "")
    body = r.text
    # header rows always present
    assert "Trusted rule changes" in body
    # data rows: every action cell after the header should contain 'trusted'
    lines = [ln for ln in body.splitlines() if ln.strip()]
    # find header index
    hdr_idx = next(i for i, ln in enumerate(lines) if ln.startswith("Timestamp (UTC)"))
    data_lines = lines[hdr_idx + 1:]
    for dl in data_lines:
        # action is 2nd CSV column
        parts = next(__import__("csv").reader([dl]))
        if len(parts) >= 2 and parts[1]:
            assert "trusted" in parts[1].lower(), f"non-trusted action in trusted CSV: {parts}"


def test_audit_log_pdf(sess):
    r = sess.get(f"{BASE_URL}/api/agents/runtime/audit-log.pdf", timeout=60)
    assert r.status_code == 200
    assert "application/pdf" in r.headers.get("content-type", "")
    assert r.content[:4] == b"%PDF"


def test_audit_log_pdf_trusted(sess):
    r = sess.get(f"{BASE_URL}/api/agents/runtime/audit-log.pdf?trusted=true", timeout=60)
    assert r.status_code == 200
    assert "application/pdf" in r.headers.get("content-type", "")
    assert r.content[:4] == b"%PDF"
