"""Iteration 68: Slack Ask, Teams Ask, slack/test, ask-log, digest config masking, SAP insight cache."""
import os, time, hmac, hashlib, base64, json, urllib.parse
import subprocess
import pytest
import requests

API = subprocess.check_output(
    "grep REACT_APP_BACKEND_URL /app/frontend/.env | cut -d= -f2",
    shell=True).decode().strip()

SLACK_SECRET = "iter68_slack_secret_xyz"
TEAMS_SECRET = base64.b64encode(b"iter68-teams-shared-secret-key-abc").decode()


@pytest.fixture(scope="module")
def admin_session():
    s = requests.Session()
    r = s.post(f"{API}/api/auth/login",
               json={"email": "jblan2026@gmail.com", "password": "Obserra2026!"})
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text[:200]}"
    return s


@pytest.fixture(scope="module")
def enabled_config(admin_session):
    s = admin_session
    cfg = s.get(f"{API}/api/sap/digest/config").json()["config"]
    cfg["slack_ask"] = True
    cfg["slack_signing_secret"] = SLACK_SECRET
    cfg["teams_ask"] = True
    cfg["teams_ask_secret"] = TEAMS_SECRET
    # ensure lists
    if isinstance(cfg.get("recipients"), str):
        cfg["recipients"] = [x.strip() for x in cfg["recipients"].split(",") if x.strip()]
    if isinstance(cfg.get("evidence_recipients"), str):
        cfg["evidence_recipients"] = [x.strip() for x in cfg["evidence_recipients"].split(",") if x.strip()]
    r = s.put(f"{API}/api/sap/digest/config", json=cfg)
    assert r.status_code == 200, f"put config: {r.status_code} {r.text[:200]}"
    yield cfg
    # teardown: reset
    cfg["slack_ask"] = False
    cfg["slack_signing_secret"] = ""
    cfg["teams_ask"] = False
    cfg["teams_ask_secret"] = ""
    s.put(f"{API}/api/sap/digest/config", json=cfg)


# ---------------- Slack signing helpers ----------------
def slack_signed(form, secret=SLACK_SECRET, ts=None):
    ts = ts or str(int(time.time()))
    sig = "v0=" + hmac.new(secret.encode(), f"v0:{ts}:{form}".encode(),
                            hashlib.sha256).hexdigest()
    return requests.post(f"{API}/api/sap/slack/ask", data=form, headers={
        "X-Slack-Request-Timestamp": ts,
        "X-Slack-Signature": sig,
        "Content-Type": "application/x-www-form-urlencoded",
    })


# ---------------- Digest config masking ----------------
class TestDigestConfigMasking:
    def test_secrets_masked_and_flags(self, admin_session, enabled_config):
        g = admin_session.get(f"{API}/api/sap/digest/config").json()
        assert g["config"]["slack_signing_secret"] == ""
        assert g["config"]["teams_ask_secret"] == ""
        assert g.get("slack_signing_secret_set") is True
        assert g.get("teams_ask_secret_set") is True

    def test_blank_secret_preserves(self, admin_session, enabled_config):
        s = admin_session
        cfg = s.get(f"{API}/api/sap/digest/config").json()["config"]
        cfg["slack_signing_secret"] = ""  # blank
        cfg["teams_ask_secret"] = ""
        assert s.put(f"{API}/api/sap/digest/config", json=cfg).status_code == 200
        # secrets still active - verify with a signed request
        form = urllib.parse.urlencode({"text": "how many open critical conflicts?",
                                       "user_name": "cfo", "team_id": "T1"})
        r = slack_signed(form)
        assert r.status_code == 200
        j = r.json()
        # If secret was wiped, this would be "isn't linked". Must NOT be.
        assert "isn't linked" not in j.get("text", "").lower() and "doesn't match" not in j.get("text", "").lower()


# ---------------- Slack Ask ----------------
class TestSlackAsk:
    def test_valid_with_response_url_ephemeral_ack(self, enabled_config):
        form = urllib.parse.urlencode({
            "text": "what are the top risks right now?",
            "response_url": "https://hooks.slack.com/commands/FAKE/RESPONSE",
            "user_name": "cfo", "team_id": "T123", "command": "/askdigest"})
        r = slack_signed(form)
        assert r.status_code == 200
        j = r.json()
        assert j.get("response_type") == "ephemeral"
        assert "analy" in j.get("text", "").lower() or "working" in j.get("text", "").lower()

    def test_inline_no_response_url(self, enabled_config):
        form = urllib.parse.urlencode({"text": "how many open critical conflicts?",
                                       "user_name": "ceo", "team_id": "T123"})
        r = slack_signed(form)
        assert r.status_code == 200
        j = r.json()
        assert j.get("response_type") == "in_channel"
        assert len(j.get("text", "")) > 20

    def test_empty_text_usage_help(self, enabled_config):
        form = urllib.parse.urlencode({"text": "", "response_url": "https://hooks.slack.com/x",
                                       "user_name": "cfo", "team_id": "T123"})
        r = slack_signed(form)
        assert r.status_code == 200
        j = r.json()
        assert j.get("response_type") == "ephemeral"
        text = j.get("text", "").lower()
        # Usage help should list shortcut chips
        assert "shortcut" in text or "top risks" in text or "askdigest" in text

    def test_shortcut_top_risks(self, enabled_config):
        form = urllib.parse.urlencode({"text": "top risks", "user_name": "cfo", "team_id": "T1"})
        r = slack_signed(form)
        assert r.status_code == 200
        text = r.json().get("text", "")
        # Should be a grounded answer, not the literal shortcut text
        assert len(text) > 40
        assert text.strip().lower() != "top risks"

    def test_wrong_secret_not_linked(self, enabled_config):
        form = urllib.parse.urlencode({"text": "hi", "user_name": "x", "team_id": "T1"})
        r = slack_signed(form, secret="wrong_secret_here")
        assert r.status_code == 200
        j = r.json()
        text = j.get("text", "").lower()
        assert "isn't linked" in text or "doesn't match" in text or "not linked" in text

    def test_stale_timestamp_401(self, enabled_config):
        form = urllib.parse.urlencode({"text": "hi", "user_name": "x", "team_id": "T1"})
        r = slack_signed(form, ts=str(int(time.time()) - 1000))
        assert r.status_code == 401


# ---------------- Teams Ask ----------------
def teams_signed(text, secret=TEAMS_SECRET):
    body = json.dumps({"type": "message", "text": text, "from": {"name": "CEO"}}).encode()
    key = base64.b64decode(secret)
    sig = base64.b64encode(hmac.new(key, body, hashlib.sha256).digest()).decode()
    return requests.post(f"{API}/api/sap/teams/ask", data=body, headers={
        "Authorization": f"HMAC {sig}", "Content-Type": "application/json"})


class TestTeamsAsk:
    def test_valid_returns_message(self, enabled_config):
        r = teams_signed("how many critical conflicts?")
        assert r.status_code == 200
        j = r.json()
        assert j.get("type") == "message"
        assert len(j.get("text", "")) > 20

    def test_shortcut_critical_with_mention_stripped(self, enabled_config):
        r = teams_signed("<at>Bot</at> critical")
        assert r.status_code == 200
        j = r.json()
        assert j.get("type") == "message"
        text = j.get("text", "")
        assert len(text) > 40
        assert "<at>" not in text.lower()

    def test_wrong_secret(self, enabled_config):
        r = teams_signed("hi", secret=base64.b64encode(b"wrong-key").decode())
        assert r.status_code == 200
        j = r.json()
        assert j.get("type") == "message"
        assert "isn't linked" in j.get("text", "").lower() or "not linked" in j.get("text", "").lower()


# ---------------- slack/test admin ----------------
class TestSlackTestEndpoint:
    def test_admin_ok(self, admin_session, enabled_config):
        r = admin_session.post(f"{API}/api/sap/slack/test", json={"question": "score trend"})
        assert r.status_code == 200
        j = r.json()
        assert j.get("ok") is True
        assert "question" in j and "answer" in j and len(j["answer"]) > 20
        assert "signing_secret_set" in j and isinstance(j["signing_secret_set"], bool)
        assert "webhook_configured" in j and isinstance(j["webhook_configured"], bool)
        assert "webhook_posted" in j

    def test_non_admin_blocked(self, enabled_config):
        # Unauthenticated call should be blocked
        r = requests.post(f"{API}/api/sap/slack/test", json={"question": "hi"})
        assert r.status_code in (401, 403)


# ---------------- ask-log ----------------
class TestAskLog:
    def test_shape_and_accumulation(self, admin_session, enabled_config):
        r = admin_session.get(f"{API}/api/sap/ask-log?limit=20")
        assert r.status_code == 200
        j = r.json()
        assert "entries" in j and "total" in j and "by_source" in j
        assert isinstance(j["entries"], list)
        assert isinstance(j["by_source"], dict)
        for key in ("slack", "teams", "test"):
            assert key in j["by_source"]
        # entries should have expected shape when non-empty
        if j["entries"]:
            e = j["entries"][0]
            for k in ("source", "user_name", "question", "answer", "at"):
                assert k in e


# ---------------- SAP insight cache ----------------
class TestSapInsightCache:
    def test_cached_second_call_fast(self, admin_session):
        s = admin_session
        t0 = time.time()
        r1 = s.get(f"{API}/api/sap/insight?focus=SoD")
        d1 = time.time() - t0
        assert r1.status_code == 200
        j1 = r1.json()
        # grounded shape
        assert "headline" in j1 or "insights" in j1 or "actions" in j1
        t1 = time.time()
        r2 = s.get(f"{API}/api/sap/insight?focus=SoD")
        d2 = time.time() - t1
        assert r2.status_code == 200
        assert r2.json() == j1
        assert d2 < 1.0, f"second call should be cached fast, took {d2:.2f}s"
        print(f"insight timings: first={d1:.2f}s, second={d2:.3f}s")
