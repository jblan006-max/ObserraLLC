"""Iteration 8 backend tests:
1) Google session guards (no live OAuth)
2) ABAC enforcement (deny precedence, protected-demo behavior, RBAC)
3) Third-Party/Vendor Risk (list/composition, assess -> workflow+notification, create monotonic)
4) Branding get/put + admin gating
5) Benchmarking metrics shape
Regression sanity: manifest(15), /me, notifications list.
Idempotent + cleans up at end.
"""
import os
import pytest
import requests

def _load_frontend_env():
    p = "/app/frontend/.env"
    if os.path.exists(p):
        for line in open(p):
            line = line.strip()
            if line.startswith("REACT_APP_BACKEND_URL="):
                return line.split("=", 1)[1].strip()
    return os.environ.get("REACT_APP_BACKEND_URL", "")

BASE = _load_frontend_env().rstrip("/")
assert BASE, "REACT_APP_BACKEND_URL not set"
ADMIN = {"email": "jblan2026@gmail.com", "password": "Obserra2026!"}
OPER = {"email": "analyst@obserra.demo", "password": "Analyst2026!"}


def _client(creds=None):
    s = requests.Session()
    if creds:
        r = s.post(f"{BASE}/api/auth/login", json=creds, timeout=15)
        assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    return s


@pytest.fixture(scope="module")
def admin():
    return _client(ADMIN)


@pytest.fixture(scope="module")
def oper():
    return _client(OPER)


# ---------- 1) Google session guards ----------
class TestGoogleGuards:
    def test_missing_session_id_returns_400(self):
        r = requests.post(f"{BASE}/api/auth/google/session", timeout=15)
        assert r.status_code == 400, r.text

    def test_bogus_session_id_returns_401(self):
        r = requests.post(f"{BASE}/api/auth/google/session",
                          headers={"X-Session-ID": "obviously-bogus-session-id-xyz"}, timeout=25)
        # Emergent endpoint returns non-200 -> our code returns 401
        assert r.status_code in (401, 502), r.text
        assert r.status_code == 401 or "unreachable" in r.text.lower()

    def test_me_and_login_still_work(self, admin):
        r = admin.get(f"{BASE}/api/auth/me", timeout=10)
        assert r.status_code == 200
        assert r.json()["email"] == ADMIN["email"]


# ---------- 2) ABAC enforcement ----------
class TestABAC:
    created_rules = []

    def test_protected_demo_open_when_off(self, admin):
        # ensure enforce off first
        admin.post(f"{BASE}/api/enterprise/abac/enforce", json={"enforce": False})
        r = admin.get(f"{BASE}/api/enterprise/abac/protected-demo")
        assert r.status_code == 200
        assert r.json().get("ok") is True

    def test_create_deny_rule_and_evaluate(self, admin):
        body = {"attribute": "role", "operator": "equals", "value": "admin",
                "resource": "demo.resource", "effect": "deny"}
        r = admin.post(f"{BASE}/api/enterprise/abac", json=body)
        assert r.status_code == 200, r.text
        rid = r.json()["rule_id"]
        TestABAC.created_rules.append(rid)

        ev = admin.post(f"{BASE}/api/enterprise/abac/evaluate",
                        json={"resource": "demo.resource", "attributes": {"role": "admin"}})
        assert ev.status_code == 200
        d = ev.json()
        assert d["decision"] == "deny"
        assert d["matched"] == rid
        assert "enforced" in d

    def test_enforce_on_denies_admin_demo(self, admin):
        r = admin.post(f"{BASE}/api/enterprise/abac/enforce", json={"enforce": True})
        assert r.status_code == 200 and r.json()["enforce"] is True
        r2 = admin.get(f"{BASE}/api/enterprise/abac/protected-demo")
        assert r2.status_code == 403, r2.text

    def test_deny_precedence_over_allow(self, admin):
        allow = {"attribute": "role", "operator": "equals", "value": "admin",
                 "resource": "demo.resource", "effect": "allow"}
        r = admin.post(f"{BASE}/api/enterprise/abac", json=allow)
        assert r.status_code == 200
        TestABAC.created_rules.append(r.json()["rule_id"])
        # protected-demo should still deny
        r2 = admin.get(f"{BASE}/api/enterprise/abac/protected-demo")
        assert r2.status_code == 403

    def test_disable_and_delete_rule_returns_200(self, admin):
        admin.post(f"{BASE}/api/enterprise/abac/enforce", json={"enforce": False})
        for rid in TestABAC.created_rules:
            admin.delete(f"{BASE}/api/enterprise/abac/{rid}")
        TestABAC.created_rules.clear()
        r = admin.get(f"{BASE}/api/enterprise/abac/protected-demo")
        assert r.status_code == 200

    def test_non_admin_forbidden(self, oper):
        r1 = oper.post(f"{BASE}/api/enterprise/abac",
                       json={"attribute": "role", "operator": "equals", "value": "x",
                             "resource": "demo.resource", "effect": "allow"})
        assert r1.status_code == 403
        r2 = oper.post(f"{BASE}/api/enterprise/abac/enforce", json={"enforce": True})
        assert r2.status_code == 403


# ---------- 3) Third-Party/Vendor Risk ----------
class TestVendorRisk:
    def test_list_shape_and_tiers(self, admin):
        r = admin.get(f"{BASE}/api/vendors")
        assert r.status_code == 200, r.text
        j = r.json()
        assert isinstance(j["composition"], list) and len(j["composition"]) == 7
        refs = [v["ref"] for v in j["vendors"]]
        for ref in ("VND-001", "VND-002", "VND-003", "VND-004"):
            assert ref in refs
        by_ref = {v["ref"]: v for v in j["vendors"]}
        assert by_ref["VND-002"]["risk_tier"] == "Critical"
        assert by_ref["VND-004"]["risk_tier"] == "Critical"
        assert "portfolio_risk" in j and "high_risk" in j

    def test_assess_creates_workflow_and_notification(self, admin):
        ref = "VND-002"
        r = admin.post(f"{BASE}/api/vendors/{ref}/assess")
        assert r.status_code == 200, r.text
        j = r.json()
        assert j["ref"] == ref and j["risk_tier"] == "Critical"

        # workflow
        wf = admin.get(f"{BASE}/api/workflows").json()
        rem = [w for w in wf if w.get("type") == "remediation" and w.get("subject") == ref]
        assert len(rem) >= 1

        # notification (vendor_risk)
        notifs = admin.get(f"{BASE}/api/notifications").json()
        items = notifs if isinstance(notifs, list) else notifs.get("items", notifs.get("notifications", []))
        vr = [n for n in items if (n.get("kind") == "vendor_risk" or n.get("type") == "vendor_risk")
              and n.get("ref") == ref]
        assert len(vr) >= 1, f"no vendor_risk notif for {ref}; got {items[:2]}"

    def test_create_monotonic(self, admin):
        r = admin.post(f"{BASE}/api/vendors", json={
            "name": "TEST_VendorX", "category": "TEST", "criticality": "Low",
            "data_access": "None", "attestation": 90, "incidents": 0})
        assert r.status_code == 200, r.text
        ref = r.json()["ref"]
        assert ref.startswith("VND-")
        n = int(ref.split("-")[1])
        assert n >= 5
        # cleanup handled at module teardown
        TestVendorRisk._created = ref

    def test_non_admin_cannot_assess_or_create(self, oper):
        r1 = oper.post(f"{BASE}/api/vendors/VND-001/assess")
        assert r1.status_code == 403
        r2 = oper.post(f"{BASE}/api/vendors",
                       json={"name": "x", "category": "y"})
        assert r2.status_code == 403


# ---------- 4) Branding ----------
class TestBranding:
    def test_default_get(self, admin):
        r = admin.get(f"{BASE}/api/branding")
        assert r.status_code == 200
        j = r.json()
        for k in ("display_name", "accent", "logo_url"):
            assert k in j

    def test_put_persists(self, admin):
        payload = {"display_name": "TEST_Brand Co", "accent": "#ff8800", "logo_url": "/logo.png"}
        r = admin.put(f"{BASE}/api/branding", json=payload)
        assert r.status_code == 200
        assert r.json()["display_name"] == "TEST_Brand Co"
        r2 = admin.get(f"{BASE}/api/branding")
        assert r2.json()["display_name"] == "TEST_Brand Co"
        assert r2.json()["accent"] == "#ff8800"

    def test_non_admin_forbidden(self, oper):
        r = oper.put(f"{BASE}/api/branding",
                     json={"display_name": "hack", "accent": "#000000"})
        assert r.status_code == 403


# ---------- 5) Benchmarking ----------
class TestBenchmark:
    def test_shape(self, admin):
        r = admin.get(f"{BASE}/api/benchmark")
        assert r.status_code == 200
        j = r.json()
        assert "industry" in j and "peer_set" in j
        assert isinstance(j["metrics"], list) and len(j["metrics"]) == 3
        names = {m["name"] for m in j["metrics"]}
        assert "Control Effectiveness" in names
        for m in j["metrics"]:
            for k in ("you", "peer_median", "top_quartile", "percentile"):
                assert k in m


# ---------- Regression sanity ----------
class TestRegression:
    def test_manifest_15(self, admin):
        r = admin.get(f"{BASE}/api/kernel/manifest")
        assert r.status_code == 200
        j = r.json()
        subs = j.get("subsystems") or j.get("manifest") or j
        if isinstance(subs, dict):
            subs = subs.get("subsystems", [])
        assert len(subs) == 15

    def test_policies(self, admin):
        r = admin.get(f"{BASE}/api/policies")
        assert r.status_code == 200


# ---------- Cleanup ----------
def test_zzz_cleanup(admin):
    # ABAC: enforce off, clear all rules created during test
    admin.post(f"{BASE}/api/enterprise/abac/enforce", json={"enforce": False})
    rules = admin.get(f"{BASE}/api/enterprise/abac").json()
    for r in rules:
        admin.delete(f"{BASE}/api/enterprise/abac/{r['rule_id']}")

    # Vendors: delete any created > VND-004; reset last_assessed on seeds
    from pymongo import MongoClient
    mongo = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))
    db = mongo[os.environ.get("DB_NAME", "test_database")]
    me = admin.get(f"{BASE}/api/auth/me").json()
    org_id = me["org_id"]
    db.vendors.delete_many({"org_id": org_id, "ref": {"$nin": ["VND-001", "VND-002", "VND-003", "VND-004"]}})
    db.vendors.update_many({"org_id": org_id}, {"$set": {"last_assessed": None}})

    # Remove vendor_risk notifications and remediation workflows for VND-*
    db.notifications.delete_many({"org_id": org_id, "kind": "vendor_risk"})
    db.workflows.delete_many({"org_id": org_id, "type": "remediation", "subject": {"$regex": "^VND-"}})

    # Reset branding
    from bson import ObjectId
    db.organizations.update_one({"_id": ObjectId(org_id)}, {"$unset": {"branding": ""}})

    # Delete enterprise_config
    db.enterprise_config.delete_many({"org_id": org_id})
    mongo.close()
