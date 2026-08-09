"""Iteration 69: /api/sap/fix (per-entity grounded rating+recommendation),
multi-turn Slack/Teams Ask, rate-limit guard, /teams/test, /ask-analytics,
Slack background logging."""
import os, time, hmac, hashlib, base64, json, subprocess
import pytest
import requests

API = subprocess.check_output(
    "grep REACT_APP_BACKEND_URL /app/frontend/.env | cut -d= -f2",
    shell=True).decode().strip()

SLACK_SECRET = "iter69_slack_secret_ABC"
TEAMS_SECRET = base64.b64encode(b"iter69-teams-shared-secret-key-xyz").decode()


# ---------------- Fixtures ----------------
@pytest.fixture(scope="module")
def admin():
    s = requests.Session()
    r = s.post(f"{API}/api/auth/login",
               json={"email": "jblan2026@gmail.com", "password": "Obserra2026!"})
    assert r.status_code == 200, f"login: {r.status_code} {r.text[:200]}"
    return s


@pytest.fixture(scope="module")
def enabled_config(admin):
    cfg = admin.get(f"{API}/api/sap/digest/config").json()["config"]
    cfg["slack_ask"] = True
    cfg["slack_signing_secret"] = SLACK_SECRET
    cfg["teams_ask"] = True
    cfg["teams_ask_secret"] = TEAMS_SECRET
    for k in ("recipients", "evidence_recipients"):
        v = cfg.get(k)
        if isinstance(v, str):
            cfg[k] = [x.strip() for x in v.split(",") if x.strip()]
        elif v is None:
            cfg[k] = []
    r = admin.put(f"{API}/api/sap/digest/config", json=cfg)
    assert r.status_code == 200, f"put cfg: {r.status_code} {r.text[:200]}"
    yield cfg
    cfg["slack_ask"] = False
    cfg["slack_signing_secret"] = ""
    cfg["teams_ask"] = False
    cfg["teams_ask_secret"] = ""
    admin.put(f"{API}/api/sap/digest/config", json=cfg)


# ---------------- Helpers ----------------
def slack_signed(form_str, secret=SLACK_SECRET, ts=None):
    ts = ts or str(int(time.time()))
    sig = "v0=" + hmac.new(secret.encode(), f"v0:{ts}:{form_str}".encode(),
                            hashlib.sha256).hexdigest()
    return requests.post(f"{API}/api/sap/slack/ask", data=form_str, headers={
        "X-Slack-Request-Timestamp": ts,
        "X-Slack-Signature": sig,
        "Content-Type": "application/x-www-form-urlencoded",
    })


def teams_signed(body_dict, secret_b64=TEAMS_SECRET):
    raw = json.dumps(body_dict).encode()
    key = base64.b64decode(secret_b64)
    sig = base64.b64encode(hmac.new(key, raw, hashlib.sha256).digest()).decode()
    return requests.post(f"{API}/api/sap/teams/ask", data=raw, headers={
        "Authorization": f"HMAC {sig}",
        "Content-Type": "application/json",
    })


# ================= /api/sap/fix (per-entity) =================
class TestSapFix:
    def _post_fix(self, admin, entity, ref):
        return admin.post(f"{API}/api/sap/fix", json={"entity": entity, "ref": ref})

    def _assert_fix_shape(self, data, entity):
        assert data["rating"] in ("Critical", "High", "Medium", "Low"), f"rating={data.get('rating')}"
        assert isinstance(data["score"], (int, float)) and 0 <= data["score"] <= 100
        assert isinstance(data["rationale"], list) and len(data["rationale"]) >= 1
        assert all(isinstance(x, str) and x.strip() for x in data["rationale"])
        rec = data["recommendation"]
        assert isinstance(rec, str) and len(rec.strip()) > 5, f"empty recommendation ({entity})"
        assert isinstance(data["steps"], list) and 2 <= len(data["steps"]) <= 4
        assert "model" in data

    def test_fix_identity_grounded_and_cached(self, admin):
        ids = admin.get(f"{API}/api/sap/identities?rating=Critical").json().get("identities", [])
        if not ids:
            ids = admin.get(f"{API}/api/sap/identities").json().get("identities", [])
        assert ids, "no identities in demo org"
        ref = ids[0]["ref"]
        r1 = self._post_fix(admin, "identity", ref)
        assert r1.status_code == 200, r1.text[:200]
        self._assert_fix_shape(r1.json(), "identity")
        # cache: 2nd identical call <1s
        t0 = time.time()
        r2 = self._post_fix(admin, "identity", ref)
        dt = time.time() - t0
        assert r2.status_code == 200
        assert dt < 1.0, f"2nd call took {dt:.2f}s (cache miss?)"
        assert r1.json() == r2.json()

    def test_fix_conflict_grounded(self, admin):
        confs = admin.get(f"{API}/api/sap/sod/conflicts?severity=Critical").json().get("conflicts", [])
        if not confs:
            confs = admin.get(f"{API}/api/sap/sod/conflicts").json().get("conflicts", [])
        assert confs, "no SoD conflicts"
        ref = confs[0].get("conflict_ref") or confs[0].get("ref")
        r = self._post_fix(admin, "conflict", ref)
        assert r.status_code == 200, r.text[:200]
        self._assert_fix_shape(r.json(), "conflict")

    def test_fix_role_grounded(self, admin):
        roles = admin.get(f"{API}/api/sap/roles").json().get("roles", [])
        assert roles, "no roles"
        ref = roles[0].get("ref") or roles[0].get("role_ref") or roles[0].get("name")
        r = self._post_fix(admin, "role", ref)
        assert r.status_code == 200, r.text[:200]
        self._assert_fix_shape(r.json(), "role")

    def test_fix_account_grounded(self, admin):
        priv = admin.get(f"{API}/api/sap/privileged").json()
        accounts = priv.get("accounts") or priv.get("privileged") or []
        ref = None
        if accounts:
            ref = accounts[0].get("ref") or accounts[0].get("account_ref") or accounts[0].get("account")
        if not ref:
            ids = admin.get(f"{API}/api/sap/identities").json().get("identities", [])
            for i in ids:
                d = admin.get(f"{API}/api/sap/identities/{i['ref']}").json()
                for a in (d.get("accounts") or d.get("person", {}).get("accounts") or []):
                    ref = a.get("ref") or a.get("account_ref") or a.get("account")
                    if ref:
                        break
                if ref:
                    break
        assert ref, "no account ref found"
        r = self._post_fix(admin, "account", ref)
        assert r.status_code == 200, r.text[:200]
        self._assert_fix_shape(r.json(), "account")

    def test_fix_unknown_ref_404(self, admin):
        r = self._post_fix(admin, "identity", "P-DOES-NOT-EXIST-9999")
        assert r.status_code == 404


# ================= Multi-turn Slack =================
class TestSlackMultiTurn:
    def test_multiturn_and_reset(self, enabled_config):
        team, chan, uid = "T_ITER69", "C_ITER69", "U_ITER69"
        base = f"team_id={team}&channel_id={chan}&user_id={uid}&user_name=itester"
        # turn 1
        r1 = slack_signed(base + "&text=how+many+open+critical+conflicts%3F")
        assert r1.status_code == 200, r1.text[:200]
        d1 = r1.json()
        assert d1.get("response_type") == "in_channel", d1
        ans1 = d1.get("text", "")
        assert len(ans1) > 20, f"turn1 short: {ans1!r}"
        # turn 2 — context: 'which area is worst?' must be answerable via prior thread
        r2 = slack_signed(base + "&text=which+area+is+worst%3F")
        assert r2.status_code == 200
        d2 = r2.json()
        assert d2.get("response_type") == "in_channel"
        ans2 = d2.get("text", "")
        assert len(ans2) > 20, f"turn2 short: {ans2!r}"
        # reset
        r3 = slack_signed(base + "&text=reset")
        assert r3.status_code == 200
        d3 = r3.json()
        assert d3.get("response_type") == "ephemeral"
        assert "Started a new conversation" in d3.get("text", ""), d3


# ================= Multi-turn Teams =================
class TestTeamsMultiTurn:
    def test_multiturn_and_reset(self, enabled_config):
        conv = "conv-iter69-abc"
        body1 = {"text": "top risks", "from": {"name": "itester"}, "conversation": {"id": conv}}
        r1 = teams_signed(body1)
        assert r1.status_code == 200, r1.text[:200]
        d1 = r1.json()
        assert d1.get("type") == "message"
        assert len(d1.get("text", "")) > 20
        body2 = {"text": "summarise that in one line", "from": {"name": "itester"},
                 "conversation": {"id": conv}}
        r2 = teams_signed(body2)
        assert r2.status_code == 200
        assert r2.json().get("type") == "message"
        assert len(r2.json().get("text", "")) > 5
        body3 = {"text": "reset", "from": {"name": "itester"}, "conversation": {"id": conv}}
        r3 = teams_signed(body3)
        assert r3.status_code == 200
        assert "Started a new conversation" in r3.json().get("text", "")


# ================= Rate limit =================
class TestRateLimit:
    def test_slack_rate_limit_throttles(self, enabled_config):
        # Fire >20 HMAC-valid slack requests; some later ones should be throttled
        base = "team_id=T_RL&channel_id=C_RL&user_id=U_RL&user_name=rl&text=score"
        throttled = 0
        errors_500 = 0
        for _ in range(28):
            r = slack_signed(base)
            if r.status_code >= 500:
                errors_500 += 1
            elif r.status_code == 200 and "asking a lot" in (r.json().get("text") or ""):
                throttled += 1
        assert errors_500 == 0, f"got {errors_500} 500s during rate-limit test"
        assert throttled > 0, "expected at least one throttled response after 20"

    def test_teams_rate_limit_throttles(self, enabled_config):
        # Use 'reset' text so each hit skips LLM and stays within the 60s window
        throttled = 0
        errors_500 = 0
        for i in range(28):
            r = teams_signed({"text": "reset", "from": {"name": "rl"},
                              "conversation": {"id": f"conv-rl-{i}"}})
            if r.status_code >= 500:
                errors_500 += 1
            elif r.status_code == 200 and "asking a lot" in (r.json().get("text") or ""):
                throttled += 1
        assert errors_500 == 0
        assert throttled > 0


# ================= Teams test endpoint =================
class TestTeamsTest:
    def test_admin_teams_test(self, admin, enabled_config):
        r = admin.post(f"{API}/api/sap/teams/test", json={"question": "top risks"})
        assert r.status_code == 200, r.text[:200]
        d = r.json()
        for k in ("ok", "question", "answer", "model", "secret_set",
                  "webhook_configured", "webhook_posted"):
            assert k in d, f"missing {k} in response"
        assert d["ok"] is True
        assert len(d["answer"]) > 20
        assert d["secret_set"] is True

    def test_non_admin_forbidden(self):
        r = requests.post(f"{API}/api/sap/teams/test",
                          json={"question": "x"})
        assert r.status_code in (401, 403)


# ================= Ask analytics =================
class TestAskAnalytics:
    def test_shape(self, admin):
        r = admin.get(f"{API}/api/sap/ask-analytics")
        assert r.status_code == 200, r.text[:200]
        d = r.json()
        assert "total" in d
        assert "by_source" in d and isinstance(d["by_source"], dict)
        for src in ("slack", "teams", "test"):
            d["by_source"].setdefault(src, 0)
        assert isinstance(d["top_questions"], list)
        assert isinstance(d["top_askers"], list)
        if d["top_questions"]:
            q0 = d["top_questions"][0]
            assert "question" in q0 and "count" in q0
        if d["top_askers"]:
            u0 = d["top_askers"][0]
            assert "user" in u0 and "count" in u0 and "last" in u0


# ================= Slack background logging bug fix =================
class TestSlackBackgroundLogging:
    def test_response_url_path_logs_to_ask_log(self, admin, enabled_config):
        # Get before count of slack entries
        before = admin.get(f"{API}/api/sap/ask-log?source=slack&limit=200").json()
        before_total = before.get("by_source", {}).get("slack", 0)
        # Slack request WITH response_url — use httpbin to swallow the delayed POST
        team, chan, uid = "T_BGLOG", "C_BGLOG", "U_BGLOG"
        form = (f"team_id={team}&channel_id={chan}&user_id={uid}&user_name=bglog"
                f"&text=score&response_url=https%3A%2F%2Fhttpbin.org%2Fpost")
        r = slack_signed(form)
        assert r.status_code == 200
        d = r.json()
        assert d.get("response_type") == "ephemeral"
        assert "Analyzing" in d.get("text", ""), d
        # Wait for background task
        time.sleep(12)
        after = admin.get(f"{API}/api/sap/ask-log?source=slack&limit=200").json()
        after_total = after.get("by_source", {}).get("slack", 0)
        assert after_total > before_total, (
            f"expected slack ask-log to grow after background responder ran "
            f"(before={before_total}, after={after_total})")
