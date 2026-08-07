"""New feature tests for iteration 2: actions/run, subscription, assets, modules,
billing (monthly+yearly), QR login, reports PDF/email, advisor board-report."""
import os
import uuid
import time
import requests
import pytest

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
ADMIN_EMAIL = "jblan2026@gmail.com"
ADMIN_PASSWORD = "Obserra2026!"


@pytest.fixture(scope="module")
def admin():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login",
               json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=15)
    assert r.status_code == 200, r.text
    return s


@pytest.fixture(scope="module")
def new_org():
    s = requests.Session()
    email = f"test.{uuid.uuid4().hex[:10]}@example.com"
    r = s.post(f"{BASE_URL}/api/auth/register",
               json={"email": email, "password": "Testing2026!", "name": "New Test",
                     "org_name": f"TEST Org {uuid.uuid4().hex[:6]}"}, timeout=30)
    assert r.status_code == 200, r.text
    s.email = email
    return s


# ============ Subscription gating ============
class TestSubscription:
    def test_admin_enterprise_active(self, admin):
        r = admin.get(f"{BASE_URL}/api/subscription")
        assert r.status_code == 200
        d = r.json()
        assert d["plan"] == "enterprise"
        assert d["active"] is True

    def test_new_org_trial_active(self, new_org):
        r = new_org.get(f"{BASE_URL}/api/subscription")
        assert r.status_code == 200
        d = r.json()
        assert d["active"] is True
        assert d.get("status") in ("trialing", "active")
        assert d.get("trial_end") is not None


# ============ Actions/Run ============
class TestActions:
    def test_run_entra_enforce_pim_reduces_residual(self, new_org):
        # get target risk residual before
        risks = new_org.get(f"{BASE_URL}/api/risks").json()
        cr1_before = [r for r in risks if r["ref"] == "CR-001"][0]
        r = new_org.post(f"{BASE_URL}/api/actions/run", json={"action_id": "entra_enforce_pim"})
        assert r.status_code == 200, r.text
        d = r.json()
        assert "message" in d and d["risk"]["ref"] == "CR-001"
        assert d["risk"]["residual"] <= cr1_before["residual"]
        assert d["risk"]["residual"] >= 3

    def test_casb_quarantine_sanctions_ai003(self, new_org):
        r = new_org.post(f"{BASE_URL}/api/actions/run", json={"action_id": "casb_quarantine_shadow"})
        assert r.status_code == 200
        ai = new_org.get(f"{BASE_URL}/api/ai-systems").json()
        ai003 = [a for a in ai if a["ref"] == "AI-003"][0]
        assert ai003["status"] == "sanctioned"

    def test_unknown_action_404(self, admin):
        r = admin.post(f"{BASE_URL}/api/actions/run", json={"action_id": "does_not_exist"})
        assert r.status_code == 404

    def test_actions_unauth(self):
        r = requests.post(f"{BASE_URL}/api/actions/run", json={"action_id": "entra_enforce_pim"})
        assert r.status_code == 401


# ============ Assets ============
class TestAssets:
    def test_admin_assets_seeded(self, admin):
        r = admin.get(f"{BASE_URL}/api/assets")
        assert r.status_code == 200
        assets = r.json()
        assert len(assets) == 8
        refs = {a["ref"] for a in assets}
        assert "AST-001" in refs and "AST-008" in refs
        for a in assets:
            assert "_id" not in a

    def test_new_org_gets_own_assets(self, new_org):
        r = new_org.get(f"{BASE_URL}/api/assets")
        assert r.status_code == 200
        assert len(r.json()) == 8


# ============ Modules Marketplace ============
class TestModules:
    def test_admin_all_owned(self, admin):
        r = admin.get(f"{BASE_URL}/api/modules")
        assert r.status_code == 200
        mods = r.json()
        assert len(mods) == 5
        for m in mods:
            assert m["owned"] is True, f"enterprise admin should own {m['id']}"

    def test_new_org_addons_not_owned(self, new_org):
        r = new_org.get(f"{BASE_URL}/api/modules")
        assert r.status_code == 200
        mods = {m["id"]: m for m in r.json()}
        # Base modules included
        assert mods["executive_overview"]["owned"] is True
        assert mods["ai_governance"]["owned"] is True
        # Add-ons not owned for trial team org
        for addon in ("situation_room", "asset_intelligence", "evidence_reporting"):
            assert mods[addon]["owned"] is False, f"trial/team should NOT own {addon}"
            assert mods[addon]["lookup_key"], f"{addon} must have lookup_key"

    def test_module_checkout_returns_stripe_url(self, new_org):
        r = new_org.post(f"{BASE_URL}/api/modules/checkout",
                         json={"lookup_key": "eios_mod_situation", "origin_url": BASE_URL})
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["checkout_url"].startswith("https://")
        assert "checkout.stripe.com" in d["checkout_url"] or "stripe" in d["checkout_url"]


# ============ Billing plans + checkout ============
class TestBillingV2:
    def test_plans_shape(self):
        r = requests.get(f"{BASE_URL}/api/billing/plans", timeout=10)
        assert r.status_code == 200
        plans = r.json()
        assert len(plans) == 2
        tiers = {p["tier"]: p for p in plans}
        assert "team" in tiers and "enterprise" in tiers
        for p in plans:
            assert "monthly" in p and "yearly" in p
            assert p["monthly"]["lookup_key"].endswith("_monthly")
            assert p["yearly"]["lookup_key"].endswith("_yearly")
            assert p["yearly"]["price"] > p["monthly"]["price"]

    def test_subscription_checkout_monthly(self, admin):
        r = admin.post(f"{BASE_URL}/api/billing/checkout",
                       json={"lookup_key": "eios_team_monthly", "origin_url": BASE_URL})
        assert r.status_code == 200, r.text
        assert r.json()["checkout_url"].startswith("https://")

    def test_subscription_checkout_yearly(self, admin):
        r = admin.post(f"{BASE_URL}/api/billing/checkout",
                       json={"lookup_key": "eios_enterprise_yearly", "origin_url": BASE_URL})
        assert r.status_code == 200, r.text
        assert r.json()["checkout_url"].startswith("https://")


# ============ QR passwordless ============
class TestQR:
    def test_qr_full_flow(self, admin):
        # 1) Start
        r = requests.post(f"{BASE_URL}/api/auth/qr/start", timeout=10)
        assert r.status_code == 200
        d = r.json()
        qr_token = d["qr_token"]
        poll_token = d["poll_token"]
        assert d["approve_url"].endswith(qr_token)

        # 2) Poll before approval → pending
        p = requests.post(f"{BASE_URL}/api/auth/qr/poll", json={"poll_token": poll_token}, timeout=10)
        assert p.status_code == 200
        assert p.json()["status"] in ("pending", "approved")

        # 3) Authenticated approve
        a = admin.post(f"{BASE_URL}/api/auth/qr/approve", json={"qr_token": qr_token})
        assert a.status_code == 200, a.text
        assert a.json()["status"] == "approved"

        # 4) Poll again with fresh session → claimed + cookies set
        fresh = requests.Session()
        p2 = fresh.post(f"{BASE_URL}/api/auth/qr/poll", json={"poll_token": poll_token}, timeout=10)
        assert p2.status_code == 200, p2.text
        assert p2.json()["status"] == "claimed"
        # Cookies should now be set — verify /me works
        me = fresh.get(f"{BASE_URL}/api/auth/me")
        assert me.status_code == 200
        assert me.json()["email"] == ADMIN_EMAIL

    def test_qr_approve_unauth(self):
        r = requests.post(f"{BASE_URL}/api/auth/qr/approve", json={"qr_token": "bogus"}, timeout=10)
        assert r.status_code == 401

    def test_qr_approve_invalid(self, admin):
        r = admin.post(f"{BASE_URL}/api/auth/qr/approve", json={"qr_token": "invalid-token-xyz"})
        assert r.status_code == 410


# ============ Reports ============
class TestReports:
    REPORT_MD = "# Test Report\n## Executive Summary\nAll clear.\n## Recommendations\nHold the line."

    def test_pdf_generation(self, admin):
        r = admin.post(f"{BASE_URL}/api/reports/pdf",
                       json={"report": self.REPORT_MD, "title": "TEST Board Report"})
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("application/pdf")
        assert r.content[:4] == b"%PDF"

    def test_pdf_unauth(self):
        r = requests.post(f"{BASE_URL}/api/reports/pdf",
                          json={"report": "x", "title": "y"}, timeout=10)
        assert r.status_code == 401

    def test_reports_list(self, admin):
        r = admin.get(f"{BASE_URL}/api/reports")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_email_send(self, admin):
        r = admin.post(f"{BASE_URL}/api/reports/email",
                       json={"report": self.REPORT_MD, "title": "TEST Email Report"})
        # Allow 200 (sent), or 502 if managed email is transiently unavailable
        assert r.status_code in (200, 502), r.text
        if r.status_code == 200:
            d = r.json()
            assert d["status"] == "sent"
            assert d["to"] == ADMIN_EMAIL


# ============ Advisor board-report ============
class TestAdvisorBoardReport:
    def test_board_report(self, admin):
        r = admin.post(f"{BASE_URL}/api/advisor/board-report", timeout=90)
        # LLM may take a bit
        assert r.status_code == 200, r.text
        d = r.json()
        assert "report" in d
        assert len(d["report"]) > 50


# ============ Integrations ============
class TestIntegrations:
    def test_integrations_list(self, admin):
        r = admin.get(f"{BASE_URL}/api/integrations")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list) and len(data) >= 1
