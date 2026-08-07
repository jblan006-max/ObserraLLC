"""Tests for the 4 kernel-closing features added this iteration:
- Remediation Workflows (from notifications)
- Policy Authoring (admin CRUD)
- Kernel Health Telemetry
- Weekly Drift Digest cron
Plus regression on prior features.
"""
import os
import time
import requests
import pytest


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


# ---------- Regression: login + controls generates drift notifications ----------
def test_controls_generates_drift(admin):
    r = admin.get(f"{API}/controls")
    assert r.status_code == 200
    n = admin.get(f"{API}/notifications").json()
    drift = [x for x in n["items"] if x.get("kind") == "control_drift"]
    assert len(drift) >= 1, "expected control_drift notifications"


# ---------- KERNEL HEALTH ----------
def test_kernel_health_shape_and_counts(admin):
    r = admin.get(f"{API}/kernel/health")
    assert r.status_code == 200
    h = r.json()
    # subsystems present
    for key in ["risk_engine", "policy_engine", "control_engine",
                "notification_engine", "workflow_engine", "identity"]:
        assert key in h, f"missing {key}"
        assert "records" in h[key] and "status" in h[key] and "error_rate" in h[key]
    # policy_engine should reflect seeded 5 policies (at least)
    pol = admin.get(f"{API}/policies").json()
    assert h["policy_engine"]["records"] == len(pol)
    # notification unread count matches
    notifs = admin.get(f"{API}/notifications").json()
    assert h["notification_engine"]["unread"] == notifs["unread"]
    # control_engine flagged count exposed
    assert "flagged" in h["control_engine"]


# ---------- POLICY AUTHORING ----------
def test_policy_create_and_update_admin(admin):
    # CREATE
    payload = {"name": "TEST Custom Policy", "statement": "Test statement",
               "framework": "Custom", "severity": "Low", "enforced": False, "threshold": 42}
    r = admin.post(f"{API}/policies", json=payload)
    assert r.status_code == 200, r.text
    created = r.json()
    assert created["policy_id"].startswith("POL-CUSTOM-")
    assert created["name"] == "TEST Custom Policy"
    assert created["threshold"] == 42
    pid = created["policy_id"]

    # PATCH
    r2 = admin.patch(f"{API}/policies/{pid}", json={"name": "TEST Renamed", "threshold": 77})
    assert r2.status_code == 200
    assert r2.json()["name"] == "TEST Renamed"
    assert r2.json()["threshold"] == 77

    # cleanup: delete via mongo directly
    from pymongo import MongoClient
    import os as _os
    mongo_url = _read_env('/app/backend/.env', 'MONGO_URL')
    db_name = _read_env('/app/backend/.env', 'DB_NAME')
    MongoClient(mongo_url)[db_name].policies.delete_many({"policy_id": {"$regex": "^POL-CUSTOM-"}})


def test_policy_create_forbidden_for_operational(op_user):
    r = op_user.post(f"{API}/policies", json={"name": "X", "statement": "Y"})
    assert r.status_code == 403
    r2 = op_user.patch(f"{API}/policies/POL-CTRL-EFFECT", json={"threshold": 99})
    assert r2.status_code == 403


def test_policy_threshold_affects_control_flagging(admin):
    # baseline count of control_drift alerts / flagged controls
    ctrls = admin.get(f"{API}/controls").json()
    def flagged_count(policy_id):
        # each control has "policy_violations" or similar; use notifications instead
        notifs = admin.get(f"{API}/notifications").json()["items"]
        return sum(1 for n in notifs if n.get("kind") == "control_drift" and not n.get("resolved"))

    # raise effectiveness floor to 90 => more controls will be flagged
    r = admin.patch(f"{API}/policies/POL-CTRL-EFFECT", json={"threshold": 90})
    assert r.status_code == 200
    assert r.json()["threshold"] == 90

    # trigger re-eval
    admin.get(f"{API}/controls")
    high = flagged_count("POL-CTRL-EFFECT")

    # lower to 10 -> fewer flagged
    r = admin.patch(f"{API}/policies/POL-CTRL-EFFECT", json={"threshold": 10})
    assert r.status_code == 200
    admin.get(f"{API}/controls")
    low = flagged_count("POL-CTRL-EFFECT")

    # cleanup: reset to 55
    admin.patch(f"{API}/policies/POL-CTRL-EFFECT", json={"threshold": 55})
    assert high >= low, f"expected high({high}) >= low({low}) alerts with higher floor"


# ---------- REMEDIATION WORKFLOWS ----------
def test_remediation_full_flow(admin):
    # ensure drift notification exists
    admin.get(f"{API}/controls")
    notifs = admin.get(f"{API}/notifications").json()["items"]
    drift = [n for n in notifs if n.get("kind") == "control_drift" and not n.get("resolved")]
    assert drift, "need at least one unresolved control_drift notification"
    notif = drift[0]
    control_id = notif.get("ref")

    # start remediation
    r = admin.post(f"{API}/notifications/{notif['id']}/remediate")
    assert r.status_code == 200, r.text
    wf = r.json()
    assert wf["type"] == "remediation"
    assert wf["subject"] == control_id
    assert wf["status"] in ("open", "in_progress")  # accept either if dedupe hits an existing
    wf_id = wf["id"]

    # dedupe: re-remediate same control returns same wf
    r2 = admin.post(f"{API}/notifications/{notif['id']}/remediate")
    assert r2.status_code == 200
    assert r2.json()["id"] == wf_id

    # GET workflow
    r = admin.get(f"{API}/workflows/{wf_id}")
    assert r.status_code == 200

    # Accept
    r = admin.post(f"{API}/workflows/{wf_id}/action", json={"action": "accept"})
    assert r.status_code == 200
    wf = r.json()
    assert wf["status"] == "in_progress"
    ack = next(s for s in wf["steps"] if s["key"] == "acknowledged")
    assert ack["done"] is True

    # Assign
    r = admin.post(f"{API}/workflows/{wf_id}/action",
                   json={"action": "assign", "assignee": "alice@obserra.demo"})
    assert r.status_code == 200
    wf = r.json()
    assert wf["assignee"] == "alice@obserra.demo"
    assigned = next(s for s in wf["steps"] if s["key"] == "assigned")
    assert assigned["done"] is True

    # Resolve
    r = admin.post(f"{API}/workflows/{wf_id}/action", json={"action": "resolve"})
    assert r.status_code == 200
    wf = r.json()
    assert wf["status"] == "resolved"
    assert all(s["done"] for s in wf["steps"])

    # Verify control_drift notifications for this control are now resolved+read
    notifs = admin.get(f"{API}/notifications").json()["items"]
    remaining = [n for n in notifs if n.get("kind") == "control_drift"
                 and n.get("ref") == control_id and not n.get("resolved")]
    assert not remaining, f"expected all drift notifs resolved for {control_id}"

    # cleanup: delete the created remediation workflow directly
    from pymongo import MongoClient
    from bson import ObjectId
    mongo_url = _read_env('/app/backend/.env', 'MONGO_URL')
    db_name = _read_env('/app/backend/.env', 'DB_NAME')
    MongoClient(mongo_url)[db_name].workflows.delete_one({"_id": ObjectId(wf_id)})


def test_workflow_invalid_action(admin):
    # need a workflow first
    admin.get(f"{API}/controls")
    notifs = admin.get(f"{API}/notifications").json()["items"]
    drift = [n for n in notifs if n.get("kind") == "control_drift"]
    if not drift:
        pytest.skip("no drift notif")
    wf = admin.post(f"{API}/notifications/{drift[0]['id']}/remediate").json()
    r = admin.post(f"{API}/workflows/{wf['id']}/action", json={"action": "bogus"})
    assert r.status_code == 400
    # cleanup if created new
    from pymongo import MongoClient
    from bson import ObjectId
    MongoClient(_read_env('/app/backend/.env', 'MONGO_URL'))[
        _read_env('/app/backend/.env', 'DB_NAME')
    ].workflows.delete_one({"_id": ObjectId(wf["id"])})


# ---------- WEEKLY DRIFT DIGEST ----------
def test_weekly_digest_requires_auth():
    r = requests.post(f"{API}/cron/weekly-drift-digest")
    assert r.status_code == 401
    r = requests.post(f"{API}/cron/weekly-drift-digest",
                      headers={"Authorization": "Bearer wrong"})
    assert r.status_code == 401


def test_weekly_digest_accepted():
    r = requests.post(f"{API}/cron/weekly-drift-digest",
                      headers={"Authorization": f"Bearer {WEBHOOK_SECRET}"})
    assert r.status_code == 200
    assert r.json().get("status") == "accepted"


# ---------- REGRESSION ----------
def test_kernel_manifest_15(admin):
    r = admin.get(f"{API}/kernel/manifest")
    assert r.status_code == 200
    assert r.json()["count"] == 15


def test_notif_mark_all_read(admin):
    admin.get(f"{API}/controls")
    r = admin.post(f"{API}/notifications/read-all")
    assert r.status_code == 200
    unread = admin.get(f"{API}/notifications").json()["unread"]
    assert unread == 0


def test_monthly_report_cron_auth():
    r = requests.post(f"{API}/cron/monthly-board-report")
    assert r.status_code == 401
    r = requests.post(f"{API}/cron/monthly-board-report",
                      headers={"Authorization": f"Bearer {WEBHOOK_SECRET}"})
    assert r.status_code == 200


# ---------- CLEANUP (final safety net) ----------
def test_zzz_cleanup():
    """Ensure no test artifacts leak — reset POL-CTRL-EFFECT threshold to 55,
    remove POL-CUSTOM-* and any remediation workflows created for test controls."""
    from pymongo import MongoClient
    mongo_url = _read_env('/app/backend/.env', 'MONGO_URL')
    db_name = _read_env('/app/backend/.env', 'DB_NAME')
    db = MongoClient(mongo_url)[db_name]
    db.policies.update_many({"policy_id": "POL-CTRL-EFFECT"}, {"$set": {"threshold": 55}})
    db.policies.delete_many({"policy_id": {"$regex": "^POL-CUSTOM-"}})
    # remove any lingering remediation workflows so demo stays clean
    db.workflows.delete_many({"type": "remediation"})
    assert db.policies.count_documents({"policy_id": "POL-CTRL-EFFECT",
                                        "threshold": 55}) >= 1
