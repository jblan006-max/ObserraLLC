"""Iter 86: SLA Escalation, Digest Scheduling, SLA Heatmap + regression after backend module split."""
import os
import requests
import pytest

def _load_base_url():
    v = os.environ.get("REACT_APP_BACKEND_URL")
    if v:
        return v.rstrip("/")
    try:
        with open("/app/frontend/.env") as f:
            for line in f:
                if line.startswith("REACT_APP_BACKEND_URL="):
                    return line.split("=", 1)[1].strip().rstrip("/")
    except FileNotFoundError:
        pass
    raise RuntimeError("REACT_APP_BACKEND_URL not set")

BASE_URL = _load_base_url()
EMAIL = "jblan2026@gmail.com"
PASSWORD = "Obserra2026!"


@pytest.fixture(scope="module")
def admin_session():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json={"email": EMAIL, "password": PASSWORD}, timeout=30)
    assert r.status_code == 200, f"Login failed: {r.status_code} {r.text[:200]}"
    return s


# ---- Regression: audit-governance endpoints still work after split ----
class TestAuditRegression:
    def test_audit_rooms(self, admin_session):
        r = admin_session.get(f"{BASE_URL}/api/deploy/audit-rooms", timeout=30)
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, (list, dict))

    def test_audit_comments(self, admin_session):
        r = admin_session.get(f"{BASE_URL}/api/deploy/audit-room-comments", timeout=30)
        assert r.status_code == 200

    def test_sla_config_get(self, admin_session):
        r = admin_session.get(f"{BASE_URL}/api/deploy/sla-config", timeout=30)
        assert r.status_code == 200
        data = r.json()
        assert "org_sla_hours" in data or "sla_hours" in data
        assert "rooms" in data

    def test_sla_config_put(self, admin_session):
        r = admin_session.put(f"{BASE_URL}/api/deploy/sla-config", json={"sla_hours": 72}, timeout=30)
        assert r.status_code == 200
        body = r.json()
        assert body.get("sla_hours") == 72 or body.get("org_sla_hours") == 72

    def test_room_sla_put(self, admin_session):
        rooms_r = admin_session.get(f"{BASE_URL}/api/deploy/audit-rooms", timeout=30)
        rooms = rooms_r.json()
        items = rooms if isinstance(rooms, list) else rooms.get("rooms", rooms.get("items", []))
        if not items:
            pytest.skip("no audit rooms")
        token = items[0].get("token") or items[0].get("share_token") or items[0].get("id")
        # send None to clear override
        r = admin_session.put(f"{BASE_URL}/api/deploy/audit-room/{token}/sla", json={"sla_hours": None}, timeout=30)
        assert r.status_code in (200, 204)

    def test_analytics(self, admin_session):
        r = admin_session.get(f"{BASE_URL}/api/deploy/audit-request-analytics", timeout=30)
        assert r.status_code == 200
        data = r.json()
        org = data.get("org") or {}
        # Heatmap fields at org level
        for key in ("on_time", "breached", "pending", "on_time_pct", "sla_hours"):
            assert key in org, f"missing org key {key}: {list(org.keys())[:30]}"
        rooms = data.get("rooms") or []
        if rooms:
            first = rooms[0]
            for key in ("on_time", "breached", "pending", "on_time_pct", "sla_hours"):
                assert key in first, f"missing room key {key} in {list(first.keys())[:30]}"

    def test_reply_templates(self, admin_session):
        r = admin_session.get(f"{BASE_URL}/api/deploy/reply-templates", timeout=30)
        assert r.status_code == 200

    def test_export_csv(self, admin_session):
        r = admin_session.get(f"{BASE_URL}/api/deploy/audit-room-comments/export.csv", timeout=30)
        assert r.status_code == 200
        assert "text/csv" in r.headers.get("content-type", "").lower() or r.text.startswith(("id,", "comment", "\ufeff"))

    def test_bulk_status(self, admin_session):
        r = admin_session.post(f"{BASE_URL}/api/deploy/audit-room-comments/bulk-status", json={"ids": [], "status": "resolved"}, timeout=30)
        assert r.status_code in (200, 400, 422)

    def test_bulk_status_filter(self, admin_session):
        r = admin_session.post(f"{BASE_URL}/api/deploy/audit-room-comments/bulk-status-filter", json={"status": "resolved", "filters": {}}, timeout=30)
        assert r.status_code in (200, 400, 422)

    def test_public_portal(self, admin_session):
        rooms_r = admin_session.get(f"{BASE_URL}/api/deploy/audit-rooms", timeout=30)
        items_raw = rooms_r.json()
        items = items_raw if isinstance(items_raw, list) else items_raw.get("rooms", items_raw.get("items", []))
        if not items:
            pytest.skip("no rooms")
        token = items[0].get("token") or items[0].get("share_token")
        if not token:
            pytest.skip("no token")
        r = requests.get(f"{BASE_URL}/api/deploy/audit-room/{token}", timeout=30)
        assert r.status_code == 200

    def test_health_detail(self, admin_session):
        r = admin_session.get(f"{BASE_URL}/api/deploy/health-detail", timeout=30)
        assert r.status_code == 200

    def test_backups(self, admin_session):
        r = admin_session.get(f"{BASE_URL}/api/deploy/backups", timeout=30)
        assert r.status_code == 200

    def test_guide_pdf(self, admin_session):
        r = admin_session.get(f"{BASE_URL}/api/deploy/guide.pdf", timeout=30)
        assert r.status_code == 200
        assert "pdf" in r.headers.get("content-type", "").lower() or r.content[:4] == b"%PDF"


# ---- SLA Escalation ----
class TestEscalationConfig:
    def test_get_default(self, admin_session):
        r = admin_session.get(f"{BASE_URL}/api/deploy/escalation-config", timeout=30)
        assert r.status_code == 200
        data = r.json()
        assert set(["enabled", "contacts", "multiplier"]).issubset(data.keys())
        assert isinstance(data["contacts"], list)

    def test_put_validates_emails_and_clamps_multiplier(self, admin_session):
        payload = {
            "enabled": True,
            "contacts": ["owner@company.com", "owner@company.com", "bad-email", "  security@company.com  "],
            "multiplier": 10.0,
        }
        r = admin_session.put(f"{BASE_URL}/api/deploy/escalation-config", json=payload, timeout=30)
        assert r.status_code == 200
        data = r.json()
        assert data["enabled"] is True
        assert data["multiplier"] == 5.0, f"multiplier should clamp to 5.0, got {data['multiplier']}"
        contacts = data["contacts"]
        assert "owner@company.com" in contacts
        assert "security@company.com" in contacts
        assert "bad-email" not in contacts
        # exact-string dedupe
        assert len(contacts) == len(set(contacts))

    def test_put_clamps_low_multiplier(self, admin_session):
        r = admin_session.put(f"{BASE_URL}/api/deploy/escalation-config",
                              json={"enabled": True, "contacts": ["owner@company.com"], "multiplier": 0.1}, timeout=30)
        assert r.status_code == 200
        assert r.json()["multiplier"] == 1.0

    def test_restore_defaults(self, admin_session):
        r = admin_session.put(f"{BASE_URL}/api/deploy/escalation-config",
                              json={"enabled": False, "contacts": [], "multiplier": 1.5}, timeout=30)
        assert r.status_code == 200
        data = r.json()
        assert data["enabled"] is False
        assert data["contacts"] == []


# ---- Digest Scheduling ----
class TestDigestSchedule:
    def test_get_default(self, admin_session):
        r = admin_session.get(f"{BASE_URL}/api/deploy/digest-schedule", timeout=30)
        assert r.status_code == 200
        data = r.json()
        assert "enabled" in data
        assert "days" in data
        assert "run_hour_utc" in data
        assert data["run_hour_utc"] == 8

    def test_put_days_dedupe_and_sort(self, admin_session):
        r = admin_session.put(f"{BASE_URL}/api/deploy/digest-schedule",
                              json={"enabled": True, "days": [3, 1, 1, 5, 3]}, timeout=30)
        assert r.status_code == 200
        assert r.json()["days"] == [1, 3, 5]

    def test_put_empty_days_defaults_all_seven(self, admin_session):
        r = admin_session.put(f"{BASE_URL}/api/deploy/digest-schedule",
                              json={"enabled": True, "days": []}, timeout=30)
        assert r.status_code == 200
        assert r.json()["days"] == [0, 1, 2, 3, 4, 5, 6]

    def test_restore_all_days(self, admin_session):
        r = admin_session.put(f"{BASE_URL}/api/deploy/digest-schedule",
                              json={"enabled": True, "days": [0, 1, 2, 3, 4, 5, 6]}, timeout=30)
        assert r.status_code == 200
        data = r.json()
        assert data["enabled"] is True
        assert data["days"] == [0, 1, 2, 3, 4, 5, 6]
