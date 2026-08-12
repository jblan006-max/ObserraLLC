"""Iter146 — Cyber Crisis Commander batch #4:
   (1) SITREP Templates CRUD, (2) Connector wizard test-event flow (already covered by test ping),
   (3) Digest Scheduling weekday/hour + preview, (4) Connector Health tile relies on
       existing /connectors/native endpoint.

Runs against the live public URL — admin: jblan2026@gmail.com.
No live emails / chat posts are triggered (we never hit /director-digest/send-now).
"""
import os
import sys
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    for line in open("/app/frontend/.env"):
        if line.startswith("REACT_APP_BACKEND_URL="):
            BASE_URL = line.split("=", 1)[1].strip().rstrip("/")
            break

ADMIN_EMAIL = "jblan2026@gmail.com"
ADMIN_PASSWORD = "Obserra2026!"

DEFAULT_TPL_IDS = {"legal-hold", "customer-comms", "exec-sync", "containment"}


@pytest.fixture(scope="module")
def sess():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    r = s.post(f"{BASE_URL}/api/auth/login",
               json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=20)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text[:200]}"
    return s


# ==========================
# FEATURE 1 — SITREP Templates
# ==========================
class TestSitrepTemplates:
    def test_get_returns_four_defaults(self, sess):
        r = sess.get(f"{BASE_URL}/api/crisis/sitrep/templates", timeout=15)
        assert r.status_code == 200
        body = r.json()
        assert "templates" in body
        templates = body["templates"]
        assert isinstance(templates, list)
        # Should have at least the 4 seeded defaults (org may have some custom too)
        ids = {t.get("id") for t in templates}
        for did in DEFAULT_TPL_IDS:
            assert did in ids, f"default template {did} missing (got {ids})"
        # shape check
        for t in templates:
            assert "id" in t and "label" in t and "text" in t
            assert isinstance(t["label"], str) and isinstance(t["text"], str)

    def test_create_delete_roundtrip(self, sess):
        # Create
        payload = {"label": "TEST_ITER146 Custom", "text": "TEST_ITER146 template body — please ignore."}
        r = sess.post(f"{BASE_URL}/api/crisis/sitrep/templates", json=payload, timeout=15)
        assert r.status_code == 200, f"{r.status_code} {r.text[:200]}"
        templates = r.json()["templates"]
        match = [t for t in templates if t.get("label") == payload["label"]]
        assert len(match) == 1, f"created template not returned: {templates}"
        tid = match[0]["id"]
        assert match[0]["text"] == payload["text"]

        # Verify via GET
        g = sess.get(f"{BASE_URL}/api/crisis/sitrep/templates", timeout=15).json()
        assert any(t.get("id") == tid for t in g["templates"])

        # Delete
        d = sess.delete(f"{BASE_URL}/api/crisis/sitrep/templates/{tid}", timeout=15)
        assert d.status_code == 200
        remaining_ids = {t.get("id") for t in d.json()["templates"]}
        assert tid not in remaining_ids

        # Defaults should still be intact
        for did in DEFAULT_TPL_IDS:
            assert did in remaining_ids

    def test_create_dedupes_same_label(self, sess):
        payload = {"label": "TEST_ITER146 Dup", "text": "v1"}
        r1 = sess.post(f"{BASE_URL}/api/crisis/sitrep/templates", json=payload, timeout=15)
        assert r1.status_code == 200
        payload2 = {"label": "TEST_ITER146 Dup", "text": "v2"}
        r2 = sess.post(f"{BASE_URL}/api/crisis/sitrep/templates", json=payload2, timeout=15)
        assert r2.status_code == 200
        dupes = [t for t in r2.json()["templates"] if t["label"].strip().lower() == "test_iter146 dup"]
        assert len(dupes) == 1, f"expected dedupe on label, got {dupes}"
        assert dupes[0]["text"] == "v2"
        # cleanup
        sess.delete(f"{BASE_URL}/api/crisis/sitrep/templates/{dupes[0]['id']}", timeout=15)

    def test_requires_auth(self):
        r = requests.get(f"{BASE_URL}/api/crisis/sitrep/templates", timeout=10)
        assert r.status_code in (401, 403)
        r = requests.post(f"{BASE_URL}/api/crisis/sitrep/templates", json={"label": "x", "text": "y"}, timeout=10)
        assert r.status_code in (401, 403)


# ==========================
# FEATURE 3 — Digest Scheduling weekday/hour + Preview
# ==========================
class TestDigestScheduling:
    def test_settings_weekday_hour_roundtrip(self, sess):
        # Read current
        r0 = sess.get(f"{BASE_URL}/api/crisis/settings", timeout=15).json()
        assert "director_digest_weekday" in r0
        assert "director_digest_hour" in r0
        assert 0 <= int(r0["director_digest_weekday"]) <= 6
        assert 0 <= int(r0["director_digest_hour"]) <= 23

        # Set to Wed (2) / 15:00
        r1 = sess.post(f"{BASE_URL}/api/crisis/settings",
                       json={"director_digest_weekday": 2, "director_digest_hour": 15}, timeout=15)
        assert r1.status_code == 200
        b1 = r1.json()
        assert b1["director_digest_weekday"] == 2
        assert b1["director_digest_hour"] == 15

        # Verify persisted via GET
        r2 = sess.get(f"{BASE_URL}/api/crisis/settings", timeout=15).json()
        assert r2["director_digest_weekday"] == 2
        assert r2["director_digest_hour"] == 15

        # Reset to defaults (Mon=0 / 08:00)
        r3 = sess.post(f"{BASE_URL}/api/crisis/settings",
                       json={"director_digest_weekday": 0, "director_digest_hour": 8}, timeout=15)
        assert r3.status_code == 200
        assert r3.json()["director_digest_weekday"] == 0
        assert r3.json()["director_digest_hour"] == 8

    def test_settings_validation_out_of_range(self, sess):
        r = sess.post(f"{BASE_URL}/api/crisis/settings",
                      json={"director_digest_weekday": 9}, timeout=15)
        assert r.status_code in (400, 422)
        r = sess.post(f"{BASE_URL}/api/crisis/settings",
                      json={"director_digest_hour": 24}, timeout=15)
        assert r.status_code in (400, 422)

    def test_preview_endpoint_returns_shape(self, sess):
        r = sess.get(f"{BASE_URL}/api/crisis/director-digest/preview", timeout=20)
        assert r.status_code == 200, f"{r.status_code} {r.text[:200]}"
        b = r.json()
        assert "html" in b and "crises" in b
        assert isinstance(b["crises"], int)
        if b["crises"] >= 1:
            assert isinstance(b["html"], str) and len(b["html"]) > 0
            assert "Weekly Crisis Digest" in b["html"] or "OBSERRA" in b["html"].upper()
        else:
            # crises=0 -> html may be empty
            assert isinstance(b["html"], str)

    def test_preview_requires_auth(self):
        r = requests.get(f"{BASE_URL}/api/crisis/director-digest/preview", timeout=10)
        assert r.status_code in (401, 403)


# ==========================
# FEATURE 2 — Connector Wizard: uses existing /connectors/{vendor}/test which
# is thoroughly covered by iter145. Here we just re-verify the vendors the
# wizard exposes.
# ==========================
class TestConnectorWizardVendors:
    def test_all_wizard_vendors_test_ok(self, sess):
        for v in ("crowdstrike", "splunk", "sentinel", "servicenow", "generic"):
            r = sess.post(f"{BASE_URL}/api/crisis/connectors/{v}/test", timeout=15)
            assert r.status_code == 200, f"{v} -> {r.status_code} {r.text[:200]}"
            body = r.json()
            assert body.get("ok") is True
            assert body.get("vendor") == v


# ==========================
# FEATURE 4 — Connector Health tile relies on GET /connectors/native
# ==========================
class TestConnectorNativeForTile:
    def test_native_endpoint_shape(self, sess):
        r = sess.get(f"{BASE_URL}/api/crisis/connectors/native", timeout=15)
        assert r.status_code == 200
        b = r.json()
        assert "connectors" in b and isinstance(b["connectors"], list)
        for c in b["connectors"]:
            assert "vendor" in c
            # count / last_received may be missing before first event
