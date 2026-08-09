import os, time, hmac, hashlib, base64, subprocess, json, urllib.parse
import requests

API = subprocess.check_output(
    "grep REACT_APP_BACKEND_URL /app/frontend/.env | cut -d= -f2",
    shell=True).decode().strip()
SLACK_SECRET = "test_slack_secret_abc"
TEAMS_SECRET = base64.b64encode(b"teams-shared-secret-key-123456").decode()

s = requests.Session()
print("login", s.post(f"{API}/api/auth/login",
      json={"email": "jblan2026@gmail.com", "password": "Obserra2026!"}).status_code)

cfg = s.get(f"{API}/api/sap/digest/config").json()["config"]
cfg["slack_ask"] = True
cfg["slack_signing_secret"] = SLACK_SECRET
cfg["teams_ask"] = True
cfg["teams_ask_secret"] = TEAMS_SECRET
print("put config", s.put(f"{API}/api/sap/digest/config", json=cfg).status_code)

# Confirm GET masks both secrets and reports *_set flags
g = s.get(f"{API}/api/sap/digest/config").json()
print("slack_secret masked:", repr(g["config"]["slack_signing_secret"]), "set:", g.get("slack_signing_secret_set"))
print("teams_secret masked:", repr(g["config"]["teams_ask_secret"]), "set:", g.get("teams_ask_secret_set"))


def slack_signed(form, secret=SLACK_SECRET):
    ts = str(int(time.time()))
    sig = "v0=" + hmac.new(secret.encode(), f"v0:{ts}:{form}".encode(), hashlib.sha256).hexdigest()
    return requests.post(f"{API}/api/sap/slack/ask", data=form,
                         headers={"X-Slack-Request-Timestamp": ts, "X-Slack-Signature": sig,
                                  "Content-Type": "application/x-www-form-urlencoded"})


# Slack SHORTCUT expansion: text="top risks" (no response_url -> inline synchronous)
r = slack_signed(urllib.parse.urlencode({"text": "top risks", "user_name": "cfo", "team_id": "T1"}))
print("SLACK shortcut 'top risks':", r.status_code, json.dumps(r.json())[:140])

# Teams signed request
def teams_signed(text, secret=TEAMS_SECRET):
    body = json.dumps({"type": "message", "text": text, "from": {"name": "CEO"}}).encode()
    key = base64.b64decode(secret)
    sig = base64.b64encode(hmac.new(key, body, hashlib.sha256).digest()).decode()
    return requests.post(f"{API}/api/sap/teams/ask", data=body,
                         headers={"Authorization": f"HMAC {sig}", "Content-Type": "application/json"})

r = teams_signed("<at>Bot</at> critical")
print("TEAMS shortcut 'critical':", r.status_code, json.dumps(r.json())[:180])

r = teams_signed("hi", secret=base64.b64encode(b"wrong-key").decode())
print("TEAMS wrong secret:", r.status_code, json.dumps(r.json())[:90])

# slack/test admin round-trip
r = s.post(f"{API}/api/sap/slack/test", json={"question": "score trend"})
j = r.json()
print("SLACK TEST:", r.status_code, "secret_set=", j.get("signing_secret_set"),
      "webhook_configured=", j.get("webhook_configured"), "answer:", (j.get("answer") or "")[:80])

# ask-log
r = s.get(f"{API}/api/sap/ask-log?limit=10")
j = r.json()
print("ASK-LOG:", r.status_code, "total=", j.get("total"), "by_source=", j.get("by_source"),
      "latest=", (j.get("entries") or [{}])[0].get("source"), "/", (j.get("entries") or [{}])[0].get("user_name"))

# reset
cfg["slack_ask"] = False; cfg["slack_signing_secret"] = ""
cfg["teams_ask"] = False; cfg["teams_ask_secret"] = ""
s.put(f"{API}/api/sap/digest/config", json=cfg)
print("reset done")
