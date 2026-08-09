import os, time, hmac, hashlib, subprocess, json, urllib.parse
import requests

API = subprocess.check_output(
    "grep REACT_APP_BACKEND_URL /app/frontend/.env | cut -d= -f2",
    shell=True).decode().strip()
SECRET = "test_signing_secret_12345"

s = requests.Session()
r = s.post(f"{API}/api/auth/login", json={"email": "jblan2026@gmail.com", "password": "Obserra2026!"})
print("login", r.status_code)

# Enable Slack Ask with a known signing secret (send full current config first)
cfg = s.get(f"{API}/api/sap/digest/config").json()["config"]
cfg["slack_ask"] = True
cfg["slack_signing_secret"] = SECRET
r = s.put(f"{API}/api/sap/digest/config", json=cfg)
print("put config", r.status_code, r.text[:120] if r.status_code != 200 else "")


def signed_post(body_str, secret=SECRET, ts=None):
    ts = ts or str(int(time.time()))
    base = f"v0:{ts}:{body_str}".encode()
    sig = "v0=" + hmac.new(secret.encode(), base, hashlib.sha256).hexdigest()
    return requests.post(f"{API}/api/sap/slack/ask", data=body_str,
                         headers={"X-Slack-Request-Timestamp": ts,
                                  "X-Slack-Signature": sig,
                                  "Content-Type": "application/x-www-form-urlencoded"})


# 1) Valid signed command with a question + response_url -> immediate ephemeral ack
form = urllib.parse.urlencode({
    "text": "what are the top risks right now?",
    "response_url": "https://hooks.slack.com/commands/FAKE/RESPONSE",
    "user_name": "cfo", "team_id": "T123", "command": "/askdigest"})
r = signed_post(form)
print("VALID signed:", r.status_code, json.dumps(r.json())[:160])

# 2) Valid signed but empty text -> usage help
form2 = urllib.parse.urlencode({"text": "", "response_url": "https://hooks.slack.com/x",
                                "user_name": "cfo", "team_id": "T123"})
r = signed_post(form2)
print("EMPTY text:", r.status_code, json.dumps(r.json())[:120])

# 3) WRONG signing secret -> org not resolved (not linked message)
r = signed_post(form, secret="wrong_secret")
print("WRONG secret:", r.status_code, json.dumps(r.json())[:120])

# 4) STALE timestamp -> 401
r = signed_post(form, ts=str(int(time.time()) - 1000))
print("STALE ts:", r.status_code, r.text[:80])

# 5) No response_url -> inline synchronous answer (in_channel)
form5 = urllib.parse.urlencode({"text": "how many open critical conflicts?",
                                "user_name": "ceo", "team_id": "T123"})
r = signed_post(form5)
print("INLINE (no response_url):", r.status_code, json.dumps(r.json())[:200])

# Reset slack_ask off (leave secret; query only matches slack_ask=True)
cfg["slack_ask"] = False
cfg["slack_signing_secret"] = ""  # blank preserves existing on backend
s.put(f"{API}/api/sap/digest/config", json=cfg)
