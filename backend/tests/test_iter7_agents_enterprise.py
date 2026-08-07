"""Iteration 7 tests: Remediation KPI Strip, Policy History, AI Agent Governance,
Enterprise Access (Connectors / SSO / SCIM / ABAC). External integrations are MOCKED.
"""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://cyber-dashboard-48.preview.emergentagent.com").rstrip("/")
ADMIN_EMAIL = "jblan2026@gmail.com"
ADMIN_PW = "Obserra2026!"
OP_EMAIL = "analyst@obserra.demo"
OP_PW = "Analyst2026!"


def _login(email, pw):
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": pw}, timeout=20)
    assert r.status_code == 200, f"login failed {email}: {r.status_code} {r.text}"
    return s


@pytest.fixture(scope="module")
def admin():
    return _login(ADMIN_EMAIL, ADMIN_PW)


@pytest.fixture(scope="module")
def op():
    return _login(OP_EMAIL, OP_PW)


# ----- (A) REMEDIATION KPI STRIP -----
class TestRemediationKPI:
    def test_kpi_shape(self, admin):
        r = admin.get(f"{BASE_URL}/api/kernel/remediation-kpi")
        assert r.status_code == 200
        data = r.json()
        for k in ("open", "overdue", "resolved", "total"):
            assert k in data and isinstance(data[k], int)
        assert data["total"] == data["open"] + data["resolved"] or data["total"] >= data["resolved"]

    def test_kpi_accessible_operational(self, op):
        r = op.get(f"{BASE_URL}/api/kernel/remediation-kpi")
        assert r.status_code == 200


# ----- (B) POLICY HISTORY -----
class TestPolicyHistory:
    def test_patch_records_history(self, admin):
        # patch a seeded policy threshold
        r = admin.patch(f"{BASE_URL}/api/policies/POL-CTRL-DRIFT", json={"threshold": 9})
        assert r.status_code == 200, r.text
        assert r.json()["threshold"] == 9
        h = admin.get(f"{BASE_URL}/api/policies/POL-CTRL-DRIFT/history")
        assert h.status_code == 200
        items = h.json()
        assert isinstance(items, list) and len(items) >= 1
        latest = items[0]
        assert "changes" in latest and "by" in latest and "at" in latest
        assert latest["by"] == ADMIN_EMAIL
        found = any(c["field"] == "threshold" and c["to"] == 9 for c in latest["changes"])
        assert found
        # reset
        admin.patch(f"{BASE_URL}/api/policies/POL-CTRL-DRIFT", json={"threshold": 8})

    def test_history_admin_only(self, op):
        r = op.get(f"{BASE_URL}/api/policies/POL-CTRL-DRIFT/history")
        assert r.status_code == 403


# ----- (C) AI AGENT GOVERNANCE -----
class TestAIAgents:
    def test_list_agents_composition(self, admin):
        r = admin.get(f"{BASE_URL}/api/agents")
        assert r.status_code == 200
        d = r.json()
        assert "composition" in d and len(d["composition"]) == 7
        refs = {a["ref"] for a in d["agents"]}
        assert {"AGT-001", "AGT-002", "AGT-003"}.issubset(refs)
        agt2 = next(a for a in d["agents"] if a["ref"] == "AGT-002")
        assert "shell.exec" in agt2["tool_violations"]
        for a in d["agents"]:
            for k in ("guardrails", "tools", "permissions", "risk_class", "status"):
                assert k in a

    def test_patch_forbidden_for_operational(self, op):
        r = op.patch(f"{BASE_URL}/api/agents/AGT-002", json={"input_filtering": True})
        assert r.status_code == 403

    def test_redteam_forbidden_for_operational(self, op):
        r = op.post(f"{BASE_URL}/api/agents/AGT-002/redteam")
        assert r.status_code == 403

    def test_redteam_critical_composes_kernel(self, admin):
        # Reset AGT-002 to all-false first
        admin.patch(f"{BASE_URL}/api/agents/AGT-002", json={
            "input_filtering": False, "output_filtering": False,
            "tool_allowlist": False, "human_in_loop": False})
        r = admin.post(f"{BASE_URL}/api/agents/AGT-002/redteam")
        assert r.status_code == 200
        d = r.json()
        assert d["total"] == 5
        assert d["score"] == 0
        assert d["passed"] == 0
        assert d["evaluation"] == "heuristic (MOCKED)"
        assert len(d["findings"]) == 5
        # Composition: remediation workflow started
        wfs = admin.get(f"{BASE_URL}/api/workflows").json()
        rem = [w for w in wfs if w.get("type") == "remediation" and w.get("subject") == "AGT-002"]
        assert len(rem) >= 1, "expected remediation workflow for AGT-002"
        # Composition: agent_risk notification created
        notifs = admin.get(f"{BASE_URL}/api/notifications").json()["items"]
        assert any(n.get("kind") == "agent_risk" and n.get("ref") == "AGT-002" for n in notifs)

    def test_harden_yields_score_100(self, admin):
        admin.patch(f"{BASE_URL}/api/agents/AGT-002", json={
            "input_filtering": True, "output_filtering": True,
            "tool_allowlist": True, "human_in_loop": True})
        r = admin.post(f"{BASE_URL}/api/agents/AGT-002/redteam")
        assert r.status_code == 200
        d = r.json()
        assert d["score"] == 100, d
        assert d["passed"] == 5


# ----- (D) ENTERPRISE CONNECTORS -----
class TestEnterpriseConnectors:
    def test_list_8_connectors(self, admin):
        r = admin.get(f"{BASE_URL}/api/enterprise/connectors")
        assert r.status_code == 200
        conns = r.json()
        assert len(conns) == 8
        cids = {c["cid"] for c in conns}
        assert {"m365", "azure", "aws", "okta", "crowdstrike", "splunk", "servicenow", "wiz"} == cids

    def test_connect_sync_disconnect_flow(self, admin):
        r = admin.post(f"{BASE_URL}/api/enterprise/connectors/wiz/connect")
        assert r.status_code == 200
        c = r.json()
        assert c["status"] == "connected"
        assert c["records_ingested"] > 0
        before = c["records_ingested"]
        s = admin.post(f"{BASE_URL}/api/enterprise/connectors/wiz/sync")
        assert s.status_code == 200
        assert s.json()["records_ingested"] == before + 137
        d = admin.post(f"{BASE_URL}/api/enterprise/connectors/wiz/disconnect")
        assert d.status_code == 200

    def test_connect_admin_only(self, op):
        r = op.post(f"{BASE_URL}/api/enterprise/connectors/wiz/connect")
        assert r.status_code == 403

    def test_sync_requires_connected(self, admin):
        r = admin.post(f"{BASE_URL}/api/enterprise/connectors/wiz/sync")
        assert r.status_code == 400


# ----- (E) SSO + SCIM -----
class TestSSOSCIM:
    def test_get_config(self, admin):
        r = admin.get(f"{BASE_URL}/api/enterprise/config")
        assert r.status_code == 200
        d = r.json()
        assert "sso" in d and "scim" in d

    def test_update_sso(self, admin):
        r = admin.put(f"{BASE_URL}/api/enterprise/sso", json={
            "enabled": True, "provider": "SAML 2.0",
            "entity_id": "urn:test:obserra", "sso_url": "https://idp.example/sso", "certificate": "CERT"})
        assert r.status_code == 200
        assert r.json()["enabled"] is True
        # verify persistence
        cfg = admin.get(f"{BASE_URL}/api/enterprise/config").json()
        assert cfg["sso"]["entity_id"] == "urn:test:obserra"

    def test_sso_admin_only(self, op):
        r = op.put(f"{BASE_URL}/api/enterprise/sso", json={"enabled": False})
        assert r.status_code == 403

    def test_scim_toggle_issues_token(self, admin):
        r = admin.post(f"{BASE_URL}/api/enterprise/scim/toggle")
        assert r.status_code == 200
        d = r.json()
        if d["enabled"]:
            assert d["token"] and len(d["token"]) > 10
        # flip back
        admin.post(f"{BASE_URL}/api/enterprise/scim/toggle")


# ----- (F) ABAC -----
class TestABAC:
    created = []

    def test_create_list_delete(self, admin):
        r = admin.post(f"{BASE_URL}/api/enterprise/abac", json={
            "attribute": "department", "operator": "equals", "value": "finance",
            "resource": "risks", "effect": "allow"})
        assert r.status_code == 200
        rule = r.json()
        assert rule["rule_id"].startswith("ABAC-")
        TestABAC.created.append(rule["rule_id"])
        rs = admin.get(f"{BASE_URL}/api/enterprise/abac").json()
        assert any(x["rule_id"] == rule["rule_id"] for x in rs)
        d = admin.delete(f"{BASE_URL}/api/enterprise/abac/{rule['rule_id']}")
        assert d.status_code == 200

    def test_create_admin_only(self, op):
        r = op.post(f"{BASE_URL}/api/enterprise/abac", json={
            "attribute": "x", "operator": "equals", "value": "y", "resource": "risks", "effect": "allow"})
        assert r.status_code == 403


# ----- (G) REGRESSION -----
class TestRegression:
    def test_manifest(self, admin):
        r = admin.get(f"{BASE_URL}/api/kernel/manifest")
        assert r.status_code == 200
        d = r.json()
        assert d["count"] == 15
        assert len(d["subsystems"]) == 15

    def test_kernel_health(self, admin):
        r = admin.get(f"{BASE_URL}/api/kernel/health")
        assert r.status_code == 200

    def test_policies_list(self, admin):
        r = admin.get(f"{BASE_URL}/api/policies")
        assert r.status_code == 200
        assert len(r.json()) >= 5

    def test_policy_simulate(self, admin):
        r = admin.post(f"{BASE_URL}/api/policies/simulate",
                       json={"policy_id": "POL-CTRL-EFFECT", "threshold": 60})
        assert r.status_code == 200
        assert "flagged" in r.json()


# ----- CLEANUP -----
def test_zzz_cleanup(admin):
    """Reset AGT-002 to all-false, clear last_redteam via re-patch,
    remove created ABAC rules, disconnect any lingering connectors."""
    # reset AGT-002 guardrails to all-false
    admin.patch(f"{BASE_URL}/api/agents/AGT-002", json={
        "input_filtering": False, "output_filtering": False,
        "tool_allowlist": False, "human_in_loop": False})
    # ensure wiz disconnected
    admin.post(f"{BASE_URL}/api/enterprise/connectors/wiz/disconnect")
    # reset POL-CTRL-DRIFT to 8, POL-CTRL-EFFECT to 55
    admin.patch(f"{BASE_URL}/api/policies/POL-CTRL-DRIFT", json={"threshold": 8})
    admin.patch(f"{BASE_URL}/api/policies/POL-CTRL-EFFECT", json={"threshold": 55})
    # delete any leftover ABAC test rules
    rules = admin.get(f"{BASE_URL}/api/enterprise/abac").json()
    for r in rules:
        admin.delete(f"{BASE_URL}/api/enterprise/abac/{r['rule_id']}")
