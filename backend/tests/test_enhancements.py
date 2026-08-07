"""Tests for iteration 6 enhancements:
1) Remediation SLAs (due_at on remediation workflows)
2) Assignee Directory (GET /api/members)
3) Policy Simulation (POST /api/policies/simulate)
4) Digest Preferences (PATCH /api/auth/preferences + /auth/me digest_cadence)
5) Daily digest cron (POST /api/cron/daily-drift-digest)
"""
import os
import requests
import pytest
from datetime import datetime, timezone


def _read_env(path, key):
    with open(path) as f:
        for line in f:
            if line.startswith(key + "="):
                return line.split("=", 1)[1].strip().strip('"')
    return None


BASE_URL = (os.environ.get('REACT_APP_BACKEND_URL') or
            _read_env('/app/frontend/.env', 'REACT_APP_BACKEND_URL')).rstrip('/')
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "jblan2026@gmail.com"
ADMIN_PW = "Obserra2026!"
OP_EMAIL = "analyst@obserra.demo"
OP_PW = "Analyst2026!"
WEBHOOK_SECRET = _read_env('/app/backend/.env', 'WEBHOOK_CRON_SECRET')


def _login(email, pw):
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": email, "password": pw})
    assert r.status_code == 200, f"login {email} -> {r.status_code} {r.text}"
    return s


@pytest.fixture(scope="module")
def admin():
    return _login(ADMIN_EMAIL, ADMIN_PW)


@pytest.fixture(scope="module")
def op_user():
    return _login(OP_EMAIL, OP_PW)


# ---------- 1) Remediation SLA ----------
def test_remediation_has_due_at(admin):
    # ensure control drift notifications exist
    admin.get(f"{API}/controls")
    n = admin.get(f"{API}/notifications").json()
    drift = [x for x in n["items"] if x.get("kind") == "control_drift" and not x.get("resolved")]
    assert drift, "expected control_drift notifications"
    notif_id = drift[0]["id"]
    r = admin.post(f"{API}/notifications/{notif_id}/remediate")
    assert r.status_code == 200, r.text
    wf = r.json()
    assert wf.get("type") == "remediation"
    assert "due_at" in wf and wf["due_at"], "remediation workflow missing due_at"
    # due_at is 7 days from now (approx)
    due = datetime.fromisoformat(wf["due_at"])
    delta = (due - datetime.now(timezone.utc)).days
    assert 5 <= delta <= 7, f"due_at delta days={delta}"
    # GET /workflows/{id}
    wfid = wf["id"]
    g = admin.get(f"{API}/workflows/{wfid}")
    assert g.status_code == 200
    assert g.json().get("due_at") == wf["due_at"]
    # And appears in list
    lst = admin.get(f"{API}/workflows").json()
    assert any(w.get("id") == wfid and w.get("due_at") for w in lst)


# ---------- 2) Assignee Directory ----------
def test_members_endpoint_admin(admin):
    r = admin.get(f"{API}/members")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    emails = {m["email"] for m in data}
    assert ADMIN_EMAIL in emails
    assert OP_EMAIL in emails
    # role/name present
    for m in data:
        assert "name" in m and "role" in m


def test_members_endpoint_operational(op_user):
    r = op_user.get(f"{API}/members")
    assert r.status_code == 200
    assert len(r.json()) >= 2


# ---------- 3) Policy Simulation ----------
def test_policy_simulate_applies_effect_high_vs_low(admin):
    r_hi = admin.post(f"{API}/policies/simulate",
                      json={"policy_id": "POL-CTRL-EFFECT", "threshold": 90})
    assert r_hi.status_code == 200, r_hi.text
    hi = r_hi.json()
    assert hi["applies"] is True
    assert "flagged" in hi and "total" in hi and "controls" in hi
    r_lo = admin.post(f"{API}/policies/simulate",
                      json={"policy_id": "POL-CTRL-EFFECT", "threshold": 10})
    lo = r_lo.json()
    assert hi["flagged"] >= lo["flagged"], f"higher threshold should flag >= lower: hi={hi['flagged']} lo={lo['flagged']}"


def test_policy_simulate_evid_fresh(admin):
    r = admin.post(f"{API}/policies/simulate",
                   json={"policy_id": "POL-EVID-FRESH", "threshold": 30})
    assert r.status_code == 200
    assert r.json()["applies"] is True


def test_policy_simulate_non_threshold_applies_false(admin):
    r = admin.post(f"{API}/policies/simulate",
                   json={"policy_id": "POL-CUSTOM-XYZ", "threshold": 50})
    assert r.status_code == 200
    assert r.json()["applies"] is False


def test_policy_simulate_forbidden_for_operational(op_user):
    r = op_user.post(f"{API}/policies/simulate",
                     json={"policy_id": "POL-CTRL-EFFECT", "threshold": 50})
    assert r.status_code == 403


# ---------- 4) Digest Preferences ----------
def test_digest_preferences_valid_values(admin):
    for val in ("daily", "off", "weekly"):
        r = admin.patch(f"{API}/auth/preferences", json={"digest_cadence": val})
        assert r.status_code == 200, r.text
        assert r.json().get("digest_cadence") == val
        me = admin.get(f"{API}/auth/me").json()
        assert me.get("digest_cadence") == val
    # cleanup -> weekly
    admin.patch(f"{API}/auth/preferences", json={"digest_cadence": "weekly"})


def test_digest_preferences_invalid_400(admin):
    r = admin.patch(f"{API}/auth/preferences", json={"digest_cadence": "hourly"})
    assert r.status_code == 400


# ---------- 5) Daily digest cron ----------
def test_daily_cron_unauthorized_without_token():
    r = requests.post(f"{API}/cron/daily-drift-digest")
    assert r.status_code == 401


def test_daily_cron_ok_with_bearer():
    assert WEBHOOK_SECRET, "WEBHOOK_CRON_SECRET missing"
    r = requests.post(f"{API}/cron/daily-drift-digest",
                      headers={"Authorization": f"Bearer {WEBHOOK_SECRET}"})
    assert r.status_code == 200
    assert r.json().get("status") == "accepted"


def test_weekly_cron_still_works():
    r = requests.post(f"{API}/cron/weekly-drift-digest",
                      headers={"Authorization": f"Bearer {WEBHOOK_SECRET}"})
    assert r.status_code == 200


# ---------- Regression: SLA overdue behavior via GET (create+manual overdue not needed;
# just confirm badge fields are exposed) ----------
def test_remediation_regression_assign_resolve_with_member(admin):
    admin.get(f"{API}/controls")
    n = admin.get(f"{API}/notifications").json()
    drift = [x for x in n["items"] if x.get("kind") == "control_drift" and not x.get("resolved")]
    if not drift:
        pytest.skip("no drift notifications")
    notif_id = drift[0]["id"]
    r = admin.post(f"{API}/notifications/{notif_id}/remediate")
    wf = r.json()
    wfid = wf["id"]
    # assign from members
    members = admin.get(f"{API}/members").json()
    assignee_name = members[0]["name"]
    a = admin.post(f"{API}/workflows/{wfid}/action",
                   json={"action": "assign", "assignee": assignee_name})
    assert a.status_code == 200
    assert a.json().get("assignee") == assignee_name
    # resolve
    res = admin.post(f"{API}/workflows/{wfid}/action", json={"action": "resolve"})
    assert res.status_code == 200
    assert res.json().get("status") == "resolved"


# ---------- Kernel manifest still 15 ----------
def test_kernel_manifest_15(admin):
    r = admin.get(f"{API}/kernel/manifest")
    assert r.status_code == 200
    assert r.json().get("count") == 15
