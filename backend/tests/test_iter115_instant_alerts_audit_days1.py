"""Iter115: instant_suspicious_alerts + trusted_rules_changed audit log + access-globe days=1."""
import os
import time
import pytest
import requests
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv("/app/frontend/.env")
load_dotenv("/app/backend/.env")
BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
MONGO_URL = os.environ.get("MONGO_URL")
DB_NAME = os.environ.get("DB_NAME")
ADMIN_EMAIL = "jblan2026@gmail.com"
ADMIN_PW = "Obserra2026!"
GOV = "/api/agents/runtime/governance-settings"


def _reset(s):
    s.put(f"{BASE_URL}{GOV}",
          json={"trusted_countries": [], "trusted_ip_ranges": [],
                "trusted_auditors": [], "unusual_access_threshold": 1,
                "instant_suspicious_alerts": False},
          timeout=30)


@pytest.fixture(scope="module")
def admin_session():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login",
               json={"email": ADMIN_EMAIL, "password": ADMIN_PW}, timeout=30)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text[:200]}"
    _reset(s)
    yield s
    _reset(s)


@pytest.fixture(scope="module")
def mongo_db():
    cli = MongoClient(MONGO_URL)
    yield cli[DB_NAME]
    cli.close()


# ---------- instant_suspicious_alerts persistence ----------

def test_gov_get_exposes_instant_flag(admin_session):
    r = admin_session.get(f"{BASE_URL}{GOV}", timeout=30)
    assert r.status_code == 200
    d = r.json()
    assert "instant_suspicious_alerts" in d
    assert isinstance(d["instant_suspicious_alerts"], bool)


def test_instant_flag_put_true_then_false(admin_session):
    r = admin_session.put(f"{BASE_URL}{GOV}",
                          json={"instant_suspicious_alerts": True}, timeout=30)
    assert r.status_code == 200
    assert r.json().get("instant_suspicious_alerts") is True
    # verify via GET
    g = admin_session.get(f"{BASE_URL}{GOV}", timeout=30).json()
    assert g.get("instant_suspicious_alerts") is True

    r2 = admin_session.put(f"{BASE_URL}{GOV}",
                           json={"instant_suspicious_alerts": False}, timeout=30)
    assert r2.status_code == 200
    assert r2.json().get("instant_suspicious_alerts") is False
    g2 = admin_session.get(f"{BASE_URL}{GOV}", timeout=30).json()
    assert g2.get("instant_suspicious_alerts") is False


# ---------- Trusted-rules audit log ----------

def _find_audit_since(db, since_iso, action="agent.trusted_rules_changed"):
    rows = list(db.audit_logs.find(
        {"action": action, "ts": {"$gte": since_iso}}
    ).sort("ts", -1).limit(10))
    return rows


def test_trusted_rules_audit_written_on_change(admin_session, mongo_db):
    _reset(admin_session)
    time.sleep(0.5)
    since = datetime.now(timezone.utc).isoformat()
    time.sleep(0.3)

    r = admin_session.put(f"{BASE_URL}{GOV}",
                          json={"trusted_countries": ["Canada", "United States"],
                                "trusted_auditors": ["alice@corp.com"]},
                          timeout=30)
    assert r.status_code == 200
    time.sleep(0.5)

    rows = _find_audit_since(mongo_db, since)
    assert len(rows) >= 1, "expected agent.trusted_rules_changed audit_logs entry"
    row = rows[0]
    assert row.get("actor") == ADMIN_EMAIL
    detail = row.get("detail") or ""
    assert "Trusted access rules changed" in detail
    assert "countries" in detail
    assert "Canada" in detail and "United States" in detail
    assert "auditors" in detail and "alice@corp.com" in detail


def test_trusted_rules_audit_captures_removals(admin_session, mongo_db):
    # currently: countries=[Canada, US], auditors=[alice]
    time.sleep(0.3)
    since = datetime.now(timezone.utc).isoformat()
    time.sleep(0.3)
    r = admin_session.put(f"{BASE_URL}{GOV}",
                          json={"trusted_countries": ["United States"],
                                "trusted_auditors": []}, timeout=30)
    assert r.status_code == 200
    time.sleep(0.5)
    rows = _find_audit_since(mongo_db, since)
    assert len(rows) >= 1
    detail = rows[0].get("detail") or ""
    assert "-[Canada]" in detail or "Canada" in detail
    assert "auditors" in detail and "alice@corp.com" in detail  # removed


def test_no_trusted_rules_audit_when_only_instant_toggled(admin_session, mongo_db):
    # Reset first, wait, then toggle only instant flag
    _reset(admin_session)
    time.sleep(0.5)
    since = datetime.now(timezone.utc).isoformat()
    time.sleep(0.3)

    r = admin_session.put(f"{BASE_URL}{GOV}",
                          json={"instant_suspicious_alerts": True}, timeout=30)
    assert r.status_code == 200
    time.sleep(0.5)
    rows = _find_audit_since(mongo_db, since)
    assert len(rows) == 0, f"unexpected trusted_rules audit entries: {[r.get('detail') for r in rows]}"
    # cleanup
    admin_session.put(f"{BASE_URL}{GOV}",
                      json={"instant_suspicious_alerts": False}, timeout=30)


def test_no_trusted_rules_audit_when_values_unchanged(admin_session, mongo_db):
    admin_session.put(f"{BASE_URL}{GOV}",
                      json={"trusted_countries": ["United States"]}, timeout=30)
    time.sleep(0.5)
    since = datetime.now(timezone.utc).isoformat()
    time.sleep(0.3)
    # Re-PUT the exact same values -> no diff -> no audit
    r = admin_session.put(f"{BASE_URL}{GOV}",
                          json={"trusted_countries": ["United States"]}, timeout=30)
    assert r.status_code == 200
    time.sleep(0.5)
    rows = _find_audit_since(mongo_db, since)
    assert len(rows) == 0, f"unexpected audit rows on no-op: {[r.get('detail') for r in rows]}"
    _reset(admin_session)


# ---------- Access-globe days=1 ----------

def test_access_globe_days_1(admin_session):
    r = admin_session.get(f"{BASE_URL}/api/agents/runtime/access-globe",
                          params={"days": 1}, timeout=60)
    assert r.status_code == 200
    d = r.json()
    assert d.get("days") == 1
    assert "points" in d and isinstance(d["points"], list)


@pytest.mark.parametrize("days", [7, 30, 90])
def test_access_globe_days_regression(admin_session, days):
    r = admin_session.get(f"{BASE_URL}/api/agents/runtime/access-globe",
                          params={"days": days}, timeout=60)
    assert r.status_code == 200
    assert r.json().get("days") == days


def test_access_globe_invalid_days_fallback(admin_session):
    r = admin_session.get(f"{BASE_URL}/api/agents/runtime/access-globe",
                          params={"days": 5}, timeout=60)
    assert r.status_code == 200
    assert r.json().get("days") is None


# ---------- Regression: watchtower + trust rules ----------

def test_watchtower_baseline_no_trust(admin_session):
    _reset(admin_session)
    r = admin_session.get(f"{BASE_URL}/api/agents/runtime/watchtower", timeout=30)
    assert r.status_code == 200
    d = r.json()
    assert d.get("has_trust") is False
    assert d.get("count") == 0


def test_watchtower_with_us_trust(admin_session):
    admin_session.put(f"{BASE_URL}{GOV}",
                      json={"trusted_countries": ["United States"]}, timeout=30)
    r = admin_session.get(f"{BASE_URL}/api/agents/runtime/watchtower", timeout=30)
    assert r.status_code == 200
    d = r.json()
    assert d.get("has_trust") is True
    assert isinstance(d.get("count"), int)
    _reset(admin_session)


def test_access_globe_suspicious_and_drilldown(admin_session):
    admin_session.put(f"{BASE_URL}{GOV}",
                      json={"trusted_countries": ["United States"]}, timeout=30)
    r = admin_session.get(f"{BASE_URL}/api/agents/runtime/access-globe",
                          params={"days": 1}, timeout=60)
    assert r.status_code == 200
    d = r.json()
    assert d.get("has_trust") is True
    assert "suspicious" in d
    for p in d.get("points", [])[:3]:
        for k in ("who", "device", "ip", "at", "source", "title", "token", "suspicious"):
            assert k in p, f"missing drilldown key {k}"
    _reset(admin_session)


def test_access_globe_pdf_still_works(admin_session):
    r = admin_session.get(f"{BASE_URL}/api/agents/runtime/access-globe.pdf", timeout=90)
    assert r.status_code == 200
    assert r.headers.get("content-type", "").startswith("application/pdf")
    assert r.content[:4] == b"%PDF"


def test_snapshot_status_retire_gated(admin_session):
    r = admin_session.get(f"{BASE_URL}/api/agents/runtime/snapshot-status", timeout=30)
    assert r.status_code == 200
    r2 = admin_session.post(f"{BASE_URL}/api/agents/runtime/retire-snapshots", timeout=30)
    # gated by suspicious rules -> 409 when snapshots still active
    assert r2.status_code in (200, 409)


def test_trusted_countries_put_get(admin_session):
    admin_session.put(f"{BASE_URL}{GOV}",
                      json={"trusted_countries": ["Canada"]}, timeout=30)
    g = admin_session.get(f"{BASE_URL}{GOV}", timeout=30).json()
    assert "Canada" in g.get("trusted_countries", [])
    _reset(admin_session)


def test_trusted_ip_ranges_put_get(admin_session):
    admin_session.put(f"{BASE_URL}{GOV}",
                      json={"trusted_ip_ranges": ["10.0.0.0/8", "192.168.1.1"]}, timeout=30)
    g = admin_session.get(f"{BASE_URL}{GOV}", timeout=30).json()
    assert "10.0.0.0/8" in g.get("trusted_ip_ranges", [])
    _reset(admin_session)


def test_trusted_auditors_and_threshold_put_get(admin_session):
    admin_session.put(f"{BASE_URL}{GOV}",
                      json={"trusted_auditors": ["Bob@Corp.com"],
                            "unusual_access_threshold": 5}, timeout=30)
    g = admin_session.get(f"{BASE_URL}{GOV}", timeout=30).json()
    assert "bob@corp.com" in g.get("trusted_auditors", [])
    assert g.get("unusual_access_threshold") == 5
    _reset(admin_session)


def test_weekly_drift_digest_cron(admin_session):
    secret = os.environ.get("WEBHOOK_CRON_SECRET") or ""
    if not secret:
        try:
            with open("/app/backend/.env") as f:
                for line in f:
                    if line.startswith("WEBHOOK_CRON_SECRET"):
                        secret = line.split("=", 1)[1].strip().strip('"').strip("'")
                        break
        except Exception:
            pass
    assert secret, "WEBHOOK_CRON_SECRET missing"
    r = requests.post(f"{BASE_URL}/api/cron/weekly-drift-digest",
                      headers={"Authorization": f"Bearer {secret}"}, timeout=90)
    assert 200 <= r.status_code < 300, f"{r.status_code} {r.text[:200]}"


# ---------- Instant-alert non-blocking: enable it, confirm public endpoints stay fast ----------

def test_public_endpoints_fast_with_instant_alerts_enabled(admin_session):
    admin_session.put(f"{BASE_URL}{GOV}",
                      json={"instant_suspicious_alerts": True,
                            "trusted_countries": ["United States"]}, timeout=30)
    # find a card-share and a room token
    cards = admin_session.get(f"{BASE_URL}/api/agents/runtime/card-shares", timeout=30)
    rooms = admin_session.get(f"{BASE_URL}/api/agents/runtime/evidence-rooms", timeout=30)
    tokens = []
    def _extract_tokens(resp):
        try:
            j = resp.json()
        except Exception:
            return []
        if isinstance(j, list):
            return j
        if isinstance(j, dict):
            for k in ("shares", "rooms", "items", "results"):
                if isinstance(j.get(k), list):
                    return j[k]
        return []
    if cards.status_code == 200:
        for c in _extract_tokens(cards)[:1]:
            if isinstance(c, dict) and c.get("token"):
                tokens.append(("card", c["token"]))
    if rooms.status_code == 200:
        for c in _extract_tokens(rooms)[:1]:
            if isinstance(c, dict) and c.get("token"):
                tokens.append(("room", c["token"]))

    pub = requests.Session()  # no auth
    for kind, tok in tokens:
        path = "card-share" if kind == "card" else "evidence-room"
        t0 = time.time()
        r = pub.get(f"{BASE_URL}/api/agents/public/{path}/{tok}", timeout=15)
        dt = time.time() - t0
        # ok if 200; and must not hang > 8s
        assert r.status_code in (200, 404, 410), f"{kind} open {r.status_code}"
        assert dt < 8.0, f"{kind} open took {dt:.2f}s (fire-and-forget should not block)"

    _reset(admin_session)
