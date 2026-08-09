"""Iter 83: Bulk resolve, template editor, CSV export, portal reply-alert tests."""
import os, re, requests, pytest
from pathlib import Path

def _load_env():
    env = Path("/app/frontend/.env").read_text()
    for line in env.splitlines():
        if line.startswith("REACT_APP_BACKEND_URL="):
            return line.split("=", 1)[1].strip()
    raise RuntimeError("REACT_APP_BACKEND_URL not found")

BASE = os.environ.get("REACT_APP_BACKEND_URL", _load_env()).rstrip("/")
EMAIL = "jblan2026@gmail.com"
PASSWORD = "Obserra2026!"
ROOM_TOKEN = "d6hUYZlup7KLlDnJVVVQMw"


@pytest.fixture(scope="module")
def sess():
    s = requests.Session()
    r = s.post(f"{BASE}/api/auth/login", json={"email": EMAIL, "password": PASSWORD})
    assert r.status_code == 200, r.text
    return s


# --- Reply templates GET/PUT ---
def test_templates_get_defaults(sess):
    r = sess.get(f"{BASE}/api/deploy/reply-templates")
    assert r.status_code == 200
    data = r.json()
    assert "templates" in data
    assert isinstance(data["templates"], list)
    assert len(data["templates"]) >= 1


def test_templates_put_drops_blank_labels(sess):
    payload = {"templates": [
        {"label": "TEST_ACK", "text": "TEST acknowledged"},
        {"label": "", "text": "should be dropped"},
        {"label": "  ", "text": "also dropped"},
    ]}
    r = sess.put(f"{BASE}/api/deploy/reply-templates", json=payload)
    assert r.status_code == 200, r.text
    data = r.json()
    labels = [t["label"] for t in data["templates"]]
    assert "TEST_ACK" in labels
    assert "" not in labels
    # verify persistence
    r2 = sess.get(f"{BASE}/api/deploy/reply-templates")
    labels2 = [t["label"] for t in r2.json()["templates"]]
    assert "TEST_ACK" in labels2


# --- Bulk status ---
def test_bulk_status_updates(sess):
    # get existing comments
    r = sess.get(f"{BASE}/api/deploy/audit-room-comments")
    assert r.status_code == 200
    comments = r.json().get("comments", [])
    assert len(comments) >= 2
    # pick 2 Resolved (Sam Reviewer) ids and flip to Open (so modified_count>0), then restore
    ids = [c["id"] for c in comments if c.get("status") == "Resolved"][:2]
    if len(ids) < 2:
        ids = [c["id"] for c in comments][:2]
    r = sess.post(f"{BASE}/api/deploy/audit-room-comments/bulk-status",
                  json={"ids": ids, "status": "In Progress"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("updated") >= 1
    # restore
    sess.post(f"{BASE}/api/deploy/audit-room-comments/bulk-status",
              json={"ids": ids, "status": "Resolved"})


def test_bulk_status_invalid_status(sess):
    r = sess.post(f"{BASE}/api/deploy/audit-room-comments/bulk-status",
                  json={"ids": ["nonexistent"], "status": "Bogus"})
    assert r.status_code in (400, 422)


# --- CSV export ---
def test_export_csv(sess):
    r = sess.get(f"{BASE}/api/deploy/audit-room-comments/export.csv")
    assert r.status_code == 200
    ctype = r.headers.get("content-type", "")
    assert "csv" in ctype.lower()
    text = r.content.decode("utf-8-sig")  # strip BOM
    lines = text.strip().split("\n")
    assert len(lines) >= 2  # header + at least 1 row
    # header should contain expected columns
    hdr = lines[0].lower()
    assert "status" in hdr


# --- Portal reply alert (unauth) ---
def test_portal_reply_alert_present():
    r = requests.get(f"{BASE}/api/deploy/audit-room/{ROOM_TOKEN}")
    assert r.status_code == 200
    html = r.text
    assert 'id="reply-alert"' in html or "id='reply-alert'" in html
    assert "obserra_seen_replies_" in html  # localStorage script
    assert "Sam Reviewer" in html or "governance" in html.lower()


# --- Regression: oldest open banner data ---
def test_comments_have_marcus_open(sess):
    r = sess.get(f"{BASE}/api/deploy/audit-room-comments")
    assert r.status_code == 200
    comments = r.json().get("comments", [])
    open_comments = [c for c in comments if c.get("status") == "Open"]
    assert len(open_comments) >= 1
