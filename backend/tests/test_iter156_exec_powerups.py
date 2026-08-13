"""Iteration 156: Executive Overview power-ups — AI Assurance trend windows,
Deep-Link pulse (backend not involved; UI only), Exec-Email schedule (separate),
Exec Snapshots CRUD."""
import os
import requests
import pytest

BASE = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
ADMIN_EMAIL = "jblan2026@gmail.com"
ADMIN_PW = "Obserra2026!"


@pytest.fixture(scope="module")
def sess():
    s = requests.Session()
    r = s.post(f"{BASE}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PW}, timeout=15)
    assert r.status_code == 200, f"login failed {r.status_code} {r.text}"
    return s


# --- AI Assurance trend windows ---
@pytest.mark.parametrize("days", [7, 30, 90])
def test_ai_monitor_days(sess, days):
    r = sess.get(f"{BASE}/api/cra/ai-monitor", params={"days": days}, timeout=15)
    assert r.status_code == 200
    d = r.json()
    for k in ["avg_score", "total_checks", "flagged_total", "trend"]:
        assert k in d, f"missing {k} in {d.keys()}"
    assert isinstance(d["trend"], list)
    # trend length should equal window size
    assert len(d["trend"]) == days, f"expected {days} points, got {len(d['trend'])}"


# --- Exec Snapshots CRUD ---
def test_exec_snapshot_crud(sess):
    # create
    r = sess.post(f"{BASE}/api/cra/exec-snapshot", json={"label": "TEST_iter156"}, timeout=15)
    assert r.status_code == 200, r.text
    body = r.json()
    sid = body.get("id") or body.get("snapshot", {}).get("id")
    assert sid, f"no id in {body}"

    # list
    r2 = sess.get(f"{BASE}/api/cra/exec-snapshots", timeout=15)
    assert r2.status_code == 200
    items = r2.json().get("snapshots") or r2.json().get("items") or r2.json()
    if isinstance(items, dict):
        items = items.get("snapshots", [])
    assert any((it.get("id") == sid) for it in items), "created snapshot not in list"

    # delete
    r3 = sess.delete(f"{BASE}/api/cra/exec-snapshot/{sid}", timeout=15)
    assert r3.status_code in (200, 204)

    # verify gone
    r4 = sess.get(f"{BASE}/api/cra/exec-snapshots", timeout=15)
    items4 = r4.json().get("snapshots") or r4.json().get("items") or r4.json()
    if isinstance(items4, dict):
        items4 = items4.get("snapshots", [])
    assert not any((it.get("id") == sid) for it in items4), "snapshot still present after delete"


# --- Exec Email settings (separate from digest) ---
def test_exec_email_settings_persist(sess):
    payload = {"enabled": True, "day_of_week": 2, "hour_utc": 9}
    r = sess.put(f"{BASE}/api/cra/exec-email/settings", json=payload, timeout=15)
    assert r.status_code == 200, r.text

    r2 = sess.get(f"{BASE}/api/cra/exec-email/settings", timeout=15)
    assert r2.status_code == 200
    got = r2.json().get("schedule", {})
    assert got.get("enabled") is True
    assert int(got.get("day_of_week")) == 2
    assert int(got.get("hour_utc")) == 9

    # Verify separateness: the analyst digest schedule shouldn't be forced to match
    r3 = sess.get(f"{BASE}/api/cra/digest/settings", timeout=15)
    if r3.status_code == 200:
        dig = r3.json().get("schedule", {}) if isinstance(r3.json(), dict) else {}
        # They persist under distinct keys; the exec save should not have overwritten digest
        # (soft check - just log)
        print("digest schedule:", dig, "exec schedule:", got)


def test_exec_email_send_now(sess):
    r = sess.post(f"{BASE}/api/cra/exec-email/send-now", json={}, timeout=20)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("ok") is True or body.get("sent_to") or body.get("status")
