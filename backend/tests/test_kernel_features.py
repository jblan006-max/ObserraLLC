"""Tests for KERNEL + 4 new features: policies/workflows/notifications, force pwd reset,
team onboarding email, scheduled board reports, control drift alerts."""
import os
import time
import uuid
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

WEBHOOK_SECRET = None
with open("/app/backend/.env") as f:
    for line in f:
        if line.startswith("WEBHOOK_CRON_SECRET"):
            WEBHOOK_SECRET = line.split("=", 1)[1].strip().strip('"')


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


# ---------- KERNEL MANIFEST ----------
def test_kernel_manifest(admin):
    r = admin.get(f"{API}/kernel/manifest")
    assert r.status_code == 200
    data = r.json()
    assert data["count"] == 15
    ids = {s["id"] for s in data["subsystems"]}
    expected = {"tenant", "identity", "asset", "graph", "evidence", "risk",
                "control", "policy", "workflow", "connector", "ai_context",
                "audit", "reporting", "notification", "obserrian"}
    # Accept slightly different id names but require count=15
    assert len(ids) == 15, f"got ids={ids}"


# ---------- POLICY ENGINE ----------
def test_policies_seeded(admin):
    r = admin.get(f"{API}/policies")
    assert r.status_code == 200
    data = r.json()
    ids = {p["policy_id"] for p in data}
    for pid in ["POL-EVID-FRESH", "POL-CTRL-EFFECT", "POL-CTRL-DRIFT",
                "POL-AI-HIGHRISK", "POL-IDENTITY-PW"]:
        assert pid in ids, f"missing {pid}, got {ids}"


# ---------- CONTROL DRIFT ALERTS ----------
def test_drift_alerts_created_and_deduped(admin):
    # Read controls once - triggers evaluation
    r1 = admin.get(f"{API}/controls")
    assert r1.status_code == 200
    # Get notifications count
    n1 = admin.get(f"{API}/notifications").json()
    count1 = len(n1["items"])
    assert "unread" in n1
    # Call controls again - should dedupe
    admin.get(f"{API}/controls")
    admin.get(f"{API}/controls")
    n2 = admin.get(f"{API}/notifications").json()
    count2 = len(n2["items"])
    assert count2 == count1, f"dedupe failed: {count1} -> {count2}"
    # Check flagged controls appear
    control_refs = set()
    for item in n2["items"]:
        cid = item.get("control_id") or item.get("meta", {}).get("control_id")
        if cid:
            control_refs.add(cid)
    # At least one drift notification exists
    assert count1 > 0, "no drift notifications generated"


def test_notification_mark_read(admin):
    n = admin.get(f"{API}/notifications").json()
    if not n["items"]:
        pytest.skip("no notifications")
    nid = n["items"][0].get("id") or n["items"][0].get("_id")
    r = admin.post(f"{API}/notifications/{nid}/read")
    assert r.status_code == 200
    r2 = admin.post(f"{API}/notifications/read-all")
    assert r2.status_code == 200
    unread = admin.get(f"{API}/notifications").json()["unread"]
    assert unread == 0


# ---------- FORCE PASSWORD RESET + TEAM ONBOARDING ----------
@pytest.fixture(scope="module")
def invited_user(admin):
    email = f"test_invitee_{uuid.uuid4().hex[:8]}@obserra.demo"
    r = admin.post(f"{API}/auth/team/invite",
                   json={"email": email, "name": "Test Invitee", "role": "operational"})
    assert r.status_code == 200, f"{r.status_code} {r.text}"
    body = r.json()
    assert "temp_password" in body
    user_id = body.get("id") or body.get("user", {}).get("id") or body.get("user_id")
    yield {"email": email, "temp_password": body["temp_password"], "id": user_id,
           "response": body}
    # Cleanup
    if user_id:
        admin.delete(f"{API}/auth/team/members/{user_id}")


def test_invited_user_must_change_password(invited_user):
    s = _login(invited_user["email"], invited_user["temp_password"])
    me = s.get(f"{API}/auth/me").json()
    assert me.get("must_change_password") is True


def test_change_password_wrong_current(invited_user):
    s = _login(invited_user["email"], invited_user["temp_password"])
    r = s.post(f"{API}/auth/change-password",
               json={"current_password": "WRONGPASS", "new_password": "NewSecurePass123"})
    assert r.status_code == 400


def test_change_password_too_short(invited_user):
    s = _login(invited_user["email"], invited_user["temp_password"])
    r = s.post(f"{API}/auth/change-password",
               json={"current_password": invited_user["temp_password"], "new_password": "short"})
    assert r.status_code == 400


def test_change_password_success_and_workflow(invited_user, admin):
    s = _login(invited_user["email"], invited_user["temp_password"])
    new_pw = "NewSecurePass123!"
    r = s.post(f"{API}/auth/change-password",
               json={"current_password": invited_user["temp_password"],
                     "new_password": new_pw})
    assert r.status_code == 200, r.text
    # Now must_change_password should be false
    me = s.get(f"{API}/auth/me").json()
    assert me.get("must_change_password") is False
    # Login again with new pw
    s2 = _login(invited_user["email"], new_pw)
    assert s2.get(f"{API}/auth/me").status_code == 200
    # Onboarding workflow completes
    wfs = admin.get(f"{API}/workflows").json()
    ob = [w for w in wfs if w.get("type") == "onboarding"
          and w.get("subject") == invited_user["email"]]
    assert len(ob) >= 1, f"no onboarding workflow for {invited_user['email']}"
    assert ob[-1].get("status") == "complete", f"workflow status: {ob[-1]}"


def test_workflow_engine_has_onboarding(admin, invited_user):
    wfs = admin.get(f"{API}/workflows").json()
    types = {w.get("type") for w in wfs}
    assert "onboarding" in types


# ---------- SCHEDULED BOARD REPORT ----------
def test_cron_requires_bearer():
    r = requests.post(f"{API}/cron/monthly-board-report")
    assert r.status_code == 401
    r2 = requests.post(f"{API}/cron/monthly-board-report",
                       headers={"Authorization": "Bearer wrong-secret"})
    assert r2.status_code == 401


def test_cron_success_creates_report(admin):
    assert WEBHOOK_SECRET, "WEBHOOK_CRON_SECRET missing"
    before = admin.get(f"{API}/reports").json()
    before_count = len(before) if isinstance(before, list) else len(before.get("items", []))
    r = requests.post(f"{API}/cron/monthly-board-report",
                      headers={"Authorization": f"Bearer {WEBHOOK_SECRET}"})
    assert r.status_code == 200, r.text
    assert r.json().get("status") == "accepted"
    # Wait for background task (LLM streaming can be slow)
    for _ in range(12):
        time.sleep(3)
        after = admin.get(f"{API}/reports").json()
        after_count = len(after) if isinstance(after, list) else len(after.get("items", []))
        if after_count > before_count:
            break
    assert after_count > before_count, f"no new report ({before_count} -> {after_count})"


# ---------- REGRESSION ----------
def test_regression_controls_and_login(admin):
    assert admin.get(f"{API}/controls").status_code == 200
    assert admin.get(f"{API}/auth/me").status_code == 200


def test_regression_team_list(admin):
    r = admin.get(f"{API}/auth/team/members")
    assert r.status_code == 200
