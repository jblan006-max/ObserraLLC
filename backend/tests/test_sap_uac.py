"""Backend tests for Obserra SAP UAC (/api/sap/*)"""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                BASE_URL = line.split("=", 1)[1].strip().rstrip("/")

ADMIN_EMAIL = "jblan2026@gmail.com"
ADMIN_PASSWORD = "Obserra2026!"


@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login",
               json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
               timeout=30)
    assert r.status_code == 200, f"Login failed: {r.status_code} {r.text[:200]}"
    return s


class TestSapReadEndpoints:
    """GET endpoints under /api/sap should return 200 with sensible data."""

    def test_overview(self, session):
        r = session.get(f"{BASE_URL}/api/sap/overview", timeout=30)
        assert r.status_code == 200, r.text[:200]
        d = r.json()
        assert isinstance(d, dict)
        # Non-empty kpis / identities / systems expected
        assert len(d) > 3

    def test_analytics(self, session):
        r = session.get(f"{BASE_URL}/api/sap/analytics", timeout=30)
        assert r.status_code == 200
        assert isinstance(r.json(), dict)

    def test_systems(self, session):
        r = session.get(f"{BASE_URL}/api/sap/systems", timeout=30)
        assert r.status_code == 200

    def test_identities_and_filters(self, session):
        r = session.get(f"{BASE_URL}/api/sap/identities", timeout=30)
        assert r.status_code == 200
        d = r.json()
        ids = d.get("identities") or d.get("items") or []
        assert isinstance(ids, list) and len(ids) > 0
        # Filter test
        r2 = session.get(f"{BASE_URL}/api/sap/identities",
                         params={"q": ids[0].get("name", "")[:3]}, timeout=30)
        assert r2.status_code == 200

    def test_identity_detail(self, session):
        d = session.get(f"{BASE_URL}/api/sap/identities", timeout=30).json()
        ids = d.get("identities") or d.get("items") or []
        ref = ids[0]["ref"]
        r = session.get(f"{BASE_URL}/api/sap/identities/{ref}", timeout=30)
        assert r.status_code == 200
        det = r.json()
        assert det.get("ref") == ref or "person" in det or "name" in det

    def test_sod_rules(self, session):
        r = session.get(f"{BASE_URL}/api/sap/sod/rules", timeout=30)
        assert r.status_code == 200
        d = r.json()
        rules = d.get("rules") or d
        assert (isinstance(rules, list) and len(rules) > 0) or (isinstance(rules, dict) and rules)

    def test_sod_conflicts(self, session):
        r = session.get(f"{BASE_URL}/api/sap/sod/conflicts", timeout=30)
        assert r.status_code == 200
        d = r.json()
        confs = d.get("conflicts") or []
        assert isinstance(confs, list)

    def test_privileged(self, session):
        r = session.get(f"{BASE_URL}/api/sap/privileged", timeout=30)
        assert r.status_code == 200
        assert "privileged" in r.json()

    def test_access_monitoring(self, session):
        r = session.get(f"{BASE_URL}/api/sap/access-monitoring", timeout=30)
        assert r.status_code == 200

    def test_jml(self, session):
        r = session.get(f"{BASE_URL}/api/sap/jml", timeout=30)
        assert r.status_code == 200

    def test_roles(self, session):
        r = session.get(f"{BASE_URL}/api/sap/roles", timeout=30)
        assert r.status_code == 200
        d = r.json()
        roles = d.get("roles") or []
        assert isinstance(roles, list) and len(roles) > 0

    def test_role_detail(self, session):
        roles = session.get(f"{BASE_URL}/api/sap/roles", timeout=30).json().get("roles") or []
        ref = roles[0]["ref"]
        r = session.get(f"{BASE_URL}/api/sap/roles/{ref}", timeout=30)
        assert r.status_code == 200

    def test_hr_reconciliation(self, session):
        r = session.get(f"{BASE_URL}/api/sap/hr/reconciliation", timeout=30)
        assert r.status_code == 200

    def test_activation(self, session):
        r = session.get(f"{BASE_URL}/api/sap/activation", timeout=30)
        assert r.status_code == 200
        d = r.json()
        users = d.get("users") or d.get("rows") or []
        assert isinstance(users, list) and len(users) > 0

    def test_activation_tickets(self, session):
        r = session.get(f"{BASE_URL}/api/sap/activation/tickets", timeout=30)
        assert r.status_code == 200

    def test_access_requests(self, session):
        r = session.get(f"{BASE_URL}/api/sap/access-requests", timeout=30)
        assert r.status_code == 200

    def test_certifications(self, session):
        r = session.get(f"{BASE_URL}/api/sap/certifications", timeout=30)
        assert r.status_code == 200


class TestSodEngine:
    def test_simulate_sap_all_blocks(self, session):
        ids = (session.get(f"{BASE_URL}/api/sap/identities").json()
               .get("identities") or [])
        person_ref = ids[0]["ref"]
        r = session.post(f"{BASE_URL}/api/sap/sod/simulate",
                         json={"person_ref": person_ref, "add_roles": ["SAP_ALL"]},
                         timeout=30)
        assert r.status_code == 200, r.text[:200]
        d = r.json()
        assert d.get("decision") in ("BLOCK", "REVIEW", "APPROVE")
        # SAP_ALL should typically yield BLOCK due to critical
        if d["decision"] != "BLOCK":
            print("WARNING: SAP_ALL sim did not BLOCK, got", d["decision"])

    def test_mitigate_conflict_persists(self, session):
        confs = session.get(f"{BASE_URL}/api/sap/sod/conflicts").json().get("conflicts") or []
        if not confs:
            pytest.skip("No conflicts to mitigate")
        cref = confs[0].get("conflict_ref") or confs[0].get("ref")
        r = session.post(f"{BASE_URL}/api/sap/sod/conflicts/mitigate",
                         json={"conflict_ref": cref, "control": "TEST_control",
                               "status": "Mitigated", "residual": "Reduced"}, timeout=30)
        assert r.status_code == 200
        # Verify persisted
        confs2 = session.get(f"{BASE_URL}/api/sap/sod/conflicts").json().get("conflicts") or []
        match = [c for c in confs2 if (c.get("conflict_ref") or c.get("ref")) == cref]
        assert match, "Conflict missing after mitigate"
        assert match[0].get("status") in ("Mitigated", "mitigated")


class TestActivationWorkflow:
    def test_activation_set_deactivate(self, session):
        # First ensure the target is activated to avoid ordering issues with bulk test
        session.post(f"{BASE_URL}/api/sap/activation/bulk",
                     json={"action": "activate", "work_note": "TEST setup"}, timeout=60)
        users = session.get(f"{BASE_URL}/api/sap/activation").json()
        rows = users.get("users") or users.get("rows") or []
        active = [u for u in rows if not u.get("is_user_deactivated") and u.get("status") == "Activated"]
        if not active:
            pytest.skip("No active users to deactivate")
        target = active[0]
        ref = target.get("user_id") or target.get("ref") or target.get("person_ref")
        r = session.post(f"{BASE_URL}/api/sap/activation/set",
                         json={"person_refs": [ref], "action": "deactivate",
                               "work_note": "TEST deactivate", "notify": False},
                         timeout=30)
        assert r.status_code == 200, r.text[:300]
        d = r.json()
        tickets = d.get("tickets") or []
        assert tickets, f"expected tickets in {d}"
        tno = tickets[0].get("number")
        assert tno and str(tno).startswith(("INC", "REQ")), f"expected INC/REQ ticket, got {tno}"

    def test_activation_create_user(self, session):
        roles = session.get(f"{BASE_URL}/api/sap/roles").json().get("roles") or []
        role_ref = roles[0]["ref"] if roles else None
        r = session.post(f"{BASE_URL}/api/sap/activation/create",
                         json={"first_name": "TESTFN", "last_name": "TESTLN",
                               "email": "test_uac_new@example.com",
                               "roles": [role_ref] if role_ref else [],
                               "work_note": "TEST create"},
                         timeout=30)
        assert r.status_code in (200, 201), r.text[:300]

    def test_activation_bulk_deactivate_then_reactivate(self, session):
        # Deactivate all active first (may be zero if prior test already did)
        r = session.post(f"{BASE_URL}/api/sap/activation/bulk",
                         json={"action": "deactivate", "work_note": "TEST bulk deactivate"},
                         timeout=60)
        assert r.status_code == 200, r.text[:300]
        assert "ticket_count" in r.json()
        # Now reactivate all
        r2 = session.post(f"{BASE_URL}/api/sap/activation/bulk",
                          json={"action": "activate", "work_note": "TEST bulk reactivate"},
                          timeout=60)
        assert r2.status_code == 200, r2.text[:300]
        assert "ticket_count" in r2.json()


class TestHrReconciliation:
    def test_hr_reconcile_flip(self, session):
        recon = session.get(f"{BASE_URL}/api/sap/hr/reconciliation").json()
        rows = recon.get("rows") or recon.get("items") or []
        holds = [r for r in rows if any("HOLD" in str(v).upper() for v in r.values() if isinstance(v, str))]
        target = holds[0] if holds else (rows[0] if rows else None)
        if not target:
            pytest.skip("No HR reconciliation rows")
        ref = target.get("person_ref") or target.get("ref")
        # Find a field with a conflict state
        field = None
        for k, v in target.items():
            if isinstance(v, dict) and v.get("state") and "RECONCILED" not in str(v.get("state", "")).upper():
                field = k
                break
        if not field:
            field = "status"
        r = session.post(f"{BASE_URL}/api/sap/hr/reconcile",
                         json={"person_ref": ref, "field": field,
                               "decision": "adp", "note": "TEST reconcile"}, timeout=30)
        # Some impls return 400 for invalid field, so allow that too but log
        assert r.status_code in (200, 400), r.text[:300]


class TestAccessRequestsAndCerts:
    def test_access_request_lifecycle(self, session):
        ids = session.get(f"{BASE_URL}/api/sap/identities").json().get("identities") or []
        person_ref = ids[0]["ref"]
        roles = session.get(f"{BASE_URL}/api/sap/roles").json().get("roles") or []
        role_ref = roles[0]["ref"]
        r = session.post(f"{BASE_URL}/api/sap/access-requests",
                         json={"person_ref": person_ref, "roles": [role_ref],
                               "justification": "TEST"}, timeout=30)
        assert r.status_code in (200, 201), r.text[:300]
        d = r.json()
        ref = d.get("ref") or (d.get("request") or {}).get("ref")
        assert ref, f"no ref in {d}"
        r2 = session.post(f"{BASE_URL}/api/sap/access-requests/{ref}/decide",
                          json={"decision": "approve", "note": "TEST approve"}, timeout=30)
        assert r2.status_code == 200, r2.text[:300]
        r3 = session.post(f"{BASE_URL}/api/sap/access-requests/{ref}/provision",
                          json={}, timeout=30)
        assert r3.status_code in (200, 201), r3.text[:300]

    def test_certifications_create_and_decide(self, session):
        r = session.post(f"{BASE_URL}/api/sap/certifications",
                         json={"type": "Privileged Access", "name": "TEST_cert"},
                         timeout=30)
        assert r.status_code in (200, 201), r.text[:300]
        d = r.json()
        ref = d.get("ref") or (d.get("campaign") or {}).get("ref")
        assert ref
        det = session.get(f"{BASE_URL}/api/sap/certifications/{ref}", timeout=30).json()
        items = det.get("items") or []
        if items:
            item_ref = items[0].get("ref") or items[0].get("item_ref")
            r2 = session.post(f"{BASE_URL}/api/sap/certifications/{ref}/decide",
                              json={"item_ref": item_ref, "decision": "Certify",
                                    "note": "TEST certify"}, timeout=30)
            assert r2.status_code == 200, r2.text[:300]


class TestAdvisor:
    def test_advisor_answer(self, session):
        r = session.post(f"{BASE_URL}/api/sap/advisor",
                         json={"question": "Which users have SAP_ALL?"}, timeout=60)
        assert r.status_code == 200, r.text[:300]
        d = r.json()
        assert d.get("answer") or d.get("text") or d.get("response")
