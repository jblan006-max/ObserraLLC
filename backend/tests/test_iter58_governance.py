"""Iter58 backend tests: Digest scheduling, mover auto-strip rule, connector re-probe, chat webhook."""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://cyber-dashboard-48.preview.emergentagent.com").rstrip("/")
EMAIL = "jblan2026@gmail.com"
PASSWORD = "Obserra2026!"


@pytest.fixture(scope="module")
def sess():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json={"email": EMAIL, "password": PASSWORD}, timeout=20)
    assert r.status_code == 200, r.text
    return s


# --- Connector Health Depth ---
class TestConnectorHealth:
    def test_systems_list(self, sess):
        r = sess.get(f"{BASE_URL}/api/sap/systems", timeout=30)
        assert r.status_code == 200
        data = r.json()
        # Expect systems array
        systems = data.get("systems") or data.get("connectors") or data
        assert isinstance(systems, list)
        assert len(systems) >= 1

    def test_reprobe_all(self, sess):
        r = sess.post(f"{BASE_URL}/api/sap/systems/reprobe", json={}, timeout=60)
        assert r.status_code == 200, r.text
        data = r.json()
        # look for healthy count / summary
        assert data.get("ok") is True or "summary" in data or "healthy" in str(data)

    def test_systems_after_reprobe_has_health(self, sess):
        # Re-probe then GET
        r0 = sess.post(f"{BASE_URL}/api/sap/systems/reprobe", json={}, timeout=60)
        assert r0.status_code == 200
        r = sess.get(f"{BASE_URL}/api/sap/systems", timeout=30)
        assert r.status_code == 200
        data = r.json()
        connectors = data.get("connectors") or []
        assert len(connectors) >= 1
        # Verify health metadata on connectors
        c = connectors[0]
        assert "health" in c, f"Missing health on connector: {c}"
        assert "drift_note" in c, f"Missing drift_note on connector: {c}"
        # Health summary
        hsum = data.get("connector_health") or {}
        assert "healthy" in hsum
        total = sum(hsum.values())
        # After reprobe, expect all healthy
        assert hsum.get("healthy", 0) == total, f"Not all healthy after reprobe: {hsum}"
        print(f"Connector health after reprobe: {hsum} total={total}")


# --- Digest Schedule Config ---
class TestDigestConfig:
    def test_get_digest_config(self, sess):
        r = sess.get(f"{BASE_URL}/api/sap/digest/config", timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        # Should have enabled, days, recipients keys
        assert isinstance(data, dict)

    def test_put_digest_config_persist(self, sess):
        payload = {
            "enabled": True,
            "days": "weekdays",
            "recipients": ["jblan2026@gmail.com"],
            "chat_alert": True,
            "teams_url": "",
            "slack_url": "",
        }
        r = sess.put(f"{BASE_URL}/api/sap/digest/config", json=payload, timeout=20)
        assert r.status_code == 200, r.text
        r2 = sess.get(f"{BASE_URL}/api/sap/digest/config", timeout=15)
        assert r2.status_code == 200
        cfg = r2.json()
        blob = cfg.get("config", cfg)
        assert blob.get("enabled") is True
        assert blob.get("days") == "weekdays"
        assert blob.get("chat_alert") is True
        assert "jblan2026@gmail.com" in blob.get("recipients", [])

    def test_test_chat_alert(self, sess):
        r = sess.post(f"{BASE_URL}/api/sap/digest/test-chat", json={}, timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        # Should indicate posted true/false without throwing
        assert "posted" in data or "ok" in data or "webhook" in data

    def test_send_digest_now(self, sess):
        r = sess.post(f"{BASE_URL}/api/sap/governance-digest/send", json={}, timeout=45)
        assert r.status_code == 200, r.text
        data = r.json()
        # Either sent, or throttled
        assert data.get("ok") is True or data.get("throttled") is True or "sent" in data


# --- Mover Auto-Strip Rule ---
class TestMoverRule:
    def test_get_mover_rule(self, sess):
        r = sess.get(f"{BASE_URL}/api/sap/mover-rule", timeout=20)
        assert r.status_code == 200, r.text
        data = r.json()
        # Expect config + candidates
        assert isinstance(data, dict)
        # candidates or movers
        cands = data.get("candidates")
        assert cands is not None
        # accept both list and int count
        if isinstance(cands, list):
            print(f"Candidates count: {len(cands)}")
        else:
            print(f"Candidates: {cands}")

    def test_put_mover_rule_enable(self, sess):
        r = sess.put(f"{BASE_URL}/api/sap/mover-rule", json={"enabled": True}, timeout=45)
        assert r.status_code == 200, r.text
        data = r.json()
        # cleaned/stripped indicator
        print(f"Mover rule enable response: {data}")
        assert data.get("ok") is True or "cleaned" in data or "stripped" in str(data).lower()

    def test_get_mover_rule_after_enable(self, sess):
        r = sess.get(f"{BASE_URL}/api/sap/mover-rule", timeout=20)
        assert r.status_code == 200
        data = r.json()
        cands = data.get("candidates")
        if isinstance(cands, list):
            assert len(cands) == 0, f"Expected 0 candidates after auto-strip, got {len(cands)}"


# --- Regression ---
class TestRegression:
    def test_sod_conflicts(self, sess):
        r = sess.get(f"{BASE_URL}/api/sap/sod/conflicts", timeout=20)
        assert r.status_code == 200

    def test_autorem_config(self, sess):
        r = sess.get(f"{BASE_URL}/api/sap/autoremediation", timeout=20)
        assert r.status_code == 200

    def test_workflow_activity(self, sess):
        r = sess.get(f"{BASE_URL}/api/sap/workflow/activity", timeout=20)
        assert r.status_code == 200

    def test_identities(self, sess):
        r = sess.get(f"{BASE_URL}/api/sap/identities", timeout=20)
        assert r.status_code == 200

    def test_jml(self, sess):
        r = sess.get(f"{BASE_URL}/api/sap/jml", timeout=20)
        assert r.status_code == 200
