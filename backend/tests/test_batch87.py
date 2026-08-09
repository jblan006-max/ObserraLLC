"""Backend tests for batch 87: digest-schedule (hour), heatmap tokens, SLA banner, resolved_at, cron."""
import os
import pytest
import requests

BASE = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
ADMIN = {"email": "jblan2026@gmail.com", "password": "Obserra2026!"}


@pytest.fixture(scope="module")
def admin_client():
    s = requests.Session()
    r = s.post(f"{BASE}/api/auth/login", json=ADMIN)
    assert r.status_code == 200, f"login failed {r.status_code} {r.text}"
    return s


# ---------- Digest schedule ----------
class TestDigestSchedule:
    def test_get_shape(self, admin_client):
        r = admin_client.get(f"{BASE}/api/deploy/digest-schedule")
        assert r.status_code == 200
        d = r.json()
        assert "enabled" in d and "days" in d and "hour" in d
        assert "run_hour_utc" not in d
        assert isinstance(d["hour"], int) and 0 <= d["hour"] <= 23
        assert isinstance(d["days"], list)

    def test_put_hour_persists(self, admin_client):
        # set hour=15
        r = admin_client.put(f"{BASE}/api/deploy/digest-schedule",
                             json={"enabled": True, "days": [0,1,2,3,4,5,6], "hour": 15})
        assert r.status_code == 200
        assert r.json()["hour"] == 15
        r = admin_client.get(f"{BASE}/api/deploy/digest-schedule")
        assert r.json()["hour"] == 15

    def test_put_clamps_hour(self, admin_client):
        r = admin_client.put(f"{BASE}/api/deploy/digest-schedule",
                             json={"enabled": True, "days": [0,1,2,3,4,5,6], "hour": 99})
        assert r.status_code == 200
        assert 0 <= r.json()["hour"] <= 23

        r2 = admin_client.put(f"{BASE}/api/deploy/digest-schedule",
                              json={"enabled": True, "days": [0,1,2,3,4,5,6], "hour": -5})
        assert r2.status_code == 200
        assert 0 <= r2.json()["hour"] <= 23

    def test_restore_defaults(self, admin_client):
        r = admin_client.put(f"{BASE}/api/deploy/digest-schedule",
                             json={"enabled": True, "days": [0,1,2,3,4,5,6], "hour": 8})
        assert r.status_code == 200
        d = r.json()
        assert d["enabled"] is True
        assert sorted(d["days"]) == [0,1,2,3,4,5,6]
        assert d["hour"] == 8


# ---------- Analytics room tokens ----------
class TestAnalyticsTokens:
    def test_room_tokens_present(self, admin_client):
        r = admin_client.get(f"{BASE}/api/deploy/audit-request-analytics")
        assert r.status_code == 200
        data = r.json()
        rooms = data.get("rooms") or data.get("heatmap") or []
        assert isinstance(rooms, list) and len(rooms) > 0, f"no rooms: {data}"
        for row in rooms:
            assert "token" in row, f"missing token in room row: {row}"


# ---------- SLA banner ----------
class TestSlaBanner:
    def test_banner_shape(self, admin_client):
        r = admin_client.get(f"{BASE}/api/deploy/audit-sla-banner")
        assert r.status_code == 200
        d = r.json()
        for k in ("open_overdue", "breached_7d", "escalated_7d"):
            assert k in d, f"missing {k}"
            assert isinstance(d[k], int)

    def test_banner_non_admin_403(self):
        # unauth (no cookies) — should be 401/403
        r = requests.get(f"{BASE}/api/deploy/audit-sla-banner")
        assert r.status_code in (401, 403)


# ---------- Resolved_at stamping ----------
class TestResolvedAt:
    def test_status_update_returns_200(self, admin_client):
        # find any comment
        r = admin_client.get(f"{BASE}/api/deploy/audit-room-comments")
        assert r.status_code == 200
        comments = r.json().get("comments") or r.json().get("items") or r.json()
        if not comments:
            pytest.skip("no comments to test with")
        target = None
        for c in comments:
            if c.get("status") != "resolved":
                target = c
                break
        target = target or comments[0]
        cid = target.get("id") or target.get("_id")
        assert cid
        r2 = admin_client.post(f"{BASE}/api/deploy/audit-room-comments/{cid}/status",
                               json={"status": "Resolved"})
        assert r2.status_code == 200, f"{r2.status_code} {r2.text}"
        # re-open at least one so an Open remains
        admin_client.post(f"{BASE}/api/deploy/audit-room-comments/{cid}/status",
                          json={"status": "Open"})


# ---------- Cron endpoints ----------
class TestCrons:
    def test_hourly_overdue_digest_requires_auth(self):
        r = requests.post(f"{BASE}/api/cron/hourly-overdue-digest")
        assert r.status_code == 401, f"expected 401 unauth, got {r.status_code}"

    def test_monthly_board_report_exists(self):
        r = requests.post(f"{BASE}/api/cron/monthly-board-report")
        assert r.status_code == 401


# ---------- Regressions ----------
class TestRegression:
    def test_sla_config(self, admin_client):
        r = admin_client.get(f"{BASE}/api/deploy/sla-config")
        assert r.status_code == 200

    def test_escalation_config(self, admin_client):
        r = admin_client.get(f"{BASE}/api/deploy/escalation-config")
        assert r.status_code == 200

    def test_reply_templates(self, admin_client):
        r = admin_client.get(f"{BASE}/api/deploy/reply-templates")
        assert r.status_code == 200

    def test_export_csv(self, admin_client):
        r = admin_client.get(f"{BASE}/api/deploy/audit-room-comments/export.csv")
        assert r.status_code == 200

    def test_restore_escalation(self, admin_client):
        r = admin_client.put(f"{BASE}/api/deploy/escalation-config",
                             json={"enabled": False, "contacts": []})
        assert r.status_code == 200

    def test_restore_sla_72h(self, admin_client):
        r = admin_client.put(f"{BASE}/api/deploy/sla-config",
                             json={"sla_hours": 72})
        assert r.status_code == 200
