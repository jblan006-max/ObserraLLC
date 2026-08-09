import os, time, hmac, hashlib, base64, subprocess, json, urllib.parse
import requests

API = subprocess.check_output(
    "grep REACT_APP_BACKEND_URL /app/frontend/.env | cut -d= -f2", shell=True).decode().strip()
SLACK_SECRET = "test_slack_secret_mt"
TEAMS_SECRET = base64.b64encode(b"teams-mt-secret-key-000").decode()

s = requests.Session()
print("login", s.post(f"{API}/api/auth/login",
      json={"email": "jblan2026@gmail.com", "password": "Obserra2026!"}).status_code)
cfg = s.get(f"{API}/api/sap/digest/config").json()["config"]
cfg.update({"slack_ask": True, "slack_signing_secret": SLACK_SECRET,
            "teams_ask": True, "teams_ask_secret": TEAMS_SECRET})
print("put config", s.put(f"{API}/api/sap/digest/config", json=cfg).status_code)


def slack(form):
    ts = str(int(time.time()))
    sig = "v0=" + hmac.new(SLACK_SECRET.encode(), f"v0:{ts}:{form}".encode(), hashlib.sha256).hexdigest()
    return requests.post(f"{API}/api/sap/slack/ask", data=form,
                         headers={"X-Slack-Request-Timestamp": ts, "X-Slack-Signature": sig,
                                  "Content-Type": "application/x-www-form-urlencoded"})


def teams(text):
    body = json.dumps({"type": "message", "text": text, "from": {"name": "CEO", "id": "u1"},
                       "conversation": {"id": "conv-1"}}).encode()
    sig = base64.b64encode(hmac.new(base64.b64decode(TEAMS_SECRET), body, hashlib.sha256).digest()).decode()
    return requests.post(f"{API}/api/sap/teams/ask", data=body,
                         headers={"Authorization": f"HMAC {sig}", "Content-Type": "application/json"})


# MULTI-TURN: same channel/user -> follow-up should use prior context
base = {"user_name": "cfo", "team_id": "T1", "channel_id": "C1", "user_id": "U1"}
r1 = slack(urllib.parse.urlencode({**base, "text": "how many open critical conflicts?"}))
print("SLACK turn1:", r1.status_code, (r1.json().get("text") or "")[:90])
r2 = slack(urllib.parse.urlencode({**base, "text": "which area is worst?"}))
print("SLACK turn2 (follow-up):", r2.status_code, (r2.json().get("text") or "")[:110])
# RESET keyword
rr = slack(urllib.parse.urlencode({**base, "text": "reset"}))
print("SLACK reset:", rr.status_code, (rr.json().get("text") or "")[:60])

# TEAMS multi-turn
t1 = teams("top risks")
print("TEAMS turn1:", t1.status_code, (t1.json().get("text") or "")[:80])
t2 = teams("summarise that in one line")
print("TEAMS turn2 (follow-up):", t2.status_code, (t2.json().get("text") or "")[:110])

# TEAMS TEST endpoint (admin)
tt = s.post(f"{API}/api/sap/teams/test", json={"question": "critical"}).json()
print("TEAMS TEST:", "secret_set=", tt.get("secret_set"), "webhook_configured=", tt.get("webhook_configured"),
      "answer:", (tt.get("answer") or "")[:70])

# ASK ANALYTICS
an = s.get(f"{API}/api/sap/ask-analytics").json()
print("ANALYTICS total=", an.get("total"), "by_source=", an.get("by_source"))
print("  top_questions:", [(q["question"][:30], q["count"]) for q in an.get("top_questions", [])][:4])
print("  top_askers:", [(a["user"], a["count"]) for a in an.get("top_askers", [])][:5])

# RATE LIMIT: fire >20 quick slack calls, expect a rate-limit ephemeral
limited = 0
for i in range(26):
    rr = slack(urllib.parse.urlencode({**base, "text": f"ping {i}", "channel_id": "Crl", "user_id": "Url"}))
    if "asking a lot" in (rr.json().get("text") or ""):
        limited += 1
print("RATE LIMIT: got", limited, "throttled responses out of 26")

cfg.update({"slack_ask": False, "slack_signing_secret": "", "teams_ask": False, "teams_ask_secret": ""})
s.put(f"{API}/api/sap/digest/config", json=cfg)
print("reset config done")
