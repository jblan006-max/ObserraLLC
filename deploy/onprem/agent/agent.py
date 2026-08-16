import os
import hmac
import hashlib
import json
from fastapi import FastAPI, Request, HTTPException

app = FastAPI(title="Obserra On‑Prem Agent (Prototype)")

AGENT_SECRET = os.environ.get("AGENT_SECRET", "localtestsecret")


@app.post("/inbound/{token}")
async def inbound(token: str, request: Request):
    raw = await request.body()
    ts = request.headers.get("X-Obserra-Timestamp", "")
    sig = request.headers.get("X-Obserra-Signature", "")
    verified = False
    if AGENT_SECRET and sig.startswith("sha256="):
        try:
            expected = hmac.new(AGENT_SECRET.encode(), (ts + ".").encode() + raw, hashlib.sha256).hexdigest()
            verified = hmac.compare_digest(expected, sig.split("=", 1)[1])
        except Exception:
            verified = False
    try:
        body = json.loads(raw.decode() or "{}")
    except Exception:
        body = {}
    # Simple logging — in production the agent would apply enforcement actions locally.
    print("[agent] inbound event:", {"token": token, "verified": verified, "payload": body})
    return {"ok": True, "received": True, "verified": verified}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "5000")))
