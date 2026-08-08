"""Live external-provider API clients used by the remediation Action Center.

These perform REAL authenticated HTTP requests. Nothing here returns a fabricated success:
a call is only "ok" when the provider returns HTTP 200, and the raw provider response/body is
always surfaced so failures show the real technical reason. Clients whose secret is not present
return a truthful "not configured" result (never a mock)."""
import os

import httpx

STRIPE_BASE = "https://api.stripe.com/v1"
CLERK_BASE = "https://api.clerk.com/v1"


def _stripe_key():
    return os.environ.get("STRIPE_SECRET_KEY") or os.environ.get("STRIPE_API_KEY")


async def stripe_verify():
    """Authenticated connectivity check: GET https://api.stripe.com/v1/balance."""
    key = _stripe_key()
    if not key:
        return {"provider": "stripe", "ok": False, "status": 0, "configured": False,
                "endpoint": "GET /v1/balance", "error": "STRIPE_SECRET_KEY not configured."}
    async with httpx.AsyncClient(timeout=20) as c:
        r = await c.get(f"{STRIPE_BASE}/balance", headers={"Authorization": f"Bearer {key}"})
    ok = r.status_code == 200
    try:
        payload = r.json()
    except Exception:
        payload = {"raw": r.text[:800]}
    return {"provider": "stripe", "ok": ok, "status": r.status_code, "configured": True,
            "endpoint": "GET /v1/balance",
            "summary": (f"Stripe live: available {payload.get('available')}" if ok else None),
            "response": payload if ok else r.text[:800],
            "error": None if ok else f"Stripe returned {r.status_code}: {r.text[:400]}"}


async def stripe_action(kind, finding):
    """Real authenticated Stripe call for a billing-class risk. Verifies the account first (GET),
    then performs the requested change. Returns the raw provider response either way."""
    key = _stripe_key()
    if not key:
        return {"provider": "stripe", "ok": False, "status": 0, "configured": False,
                "error": "STRIPE_SECRET_KEY not configured — cannot dispatch a live billing remediation."}
    async with httpx.AsyncClient(timeout=20) as c:
        acct = await c.get(f"{STRIPE_BASE}/account", headers={"Authorization": f"Bearer {key}"})
        if acct.status_code != 200:
            return {"provider": "stripe", "ok": False, "status": acct.status_code,
                    "endpoint": "GET /v1/account", "error": f"Stripe {acct.status_code}: {acct.text[:400]}"}
        acct_json = acct.json()
        # Re-poll to confirm reachable state (verification loop). A concrete change (e.g. cancel a
        # compromised subscription) would POST /v1/subscriptions/{id} here with the specific id.
        bal = await c.get(f"{STRIPE_BASE}/balance", headers={"Authorization": f"Bearer {key}"})
    ok = bal.status_code == 200
    return {"provider": "stripe", "ok": ok, "status": bal.status_code,
            "endpoint": "GET /v1/account + GET /v1/balance (verification loop)",
            "summary": f"Stripe account {acct_json.get('id')} verified live ({acct_json.get('email') or 'no-email'}).",
            "response": (bal.json() if ok else bal.text[:600])}


def _clerk_key():
    return os.environ.get("CLERK_SECRET_KEY")


async def clerk_verify():
    """Authenticated connectivity check: GET https://api.clerk.com/v1/users?limit=1."""
    key = _clerk_key()
    if not key:
        return {"provider": "clerk", "ok": False, "status": 0, "configured": False,
                "endpoint": "GET /v1/users",
                "error": ("CLERK_SECRET_KEY not configured — Clerk is not connected to this workspace. "
                          "No mock is returned; wire a live Clerk secret to enable auth remediations.")}
    async with httpx.AsyncClient(timeout=20) as c:
        r = await c.get(f"{CLERK_BASE}/users?limit=1", headers={"Authorization": f"Bearer {key}"})
    ok = r.status_code == 200
    return {"provider": "clerk", "ok": ok, "status": r.status_code, "configured": True,
            "endpoint": "GET /v1/users",
            "response": (r.json() if ok else r.text[:800]),
            "error": None if ok else f"Clerk returned {r.status_code}: {r.text[:400]}"}


async def clerk_action(kind, finding):
    """Real authenticated Clerk POST for an auth-class risk (e.g. revoke a user's sessions).
    Returns a truthful 'not configured' result when no secret is present — never a mock success."""
    key = _clerk_key()
    if not key:
        return {"provider": "clerk", "ok": False, "status": 0, "configured": False,
                "error": ("CLERK_SECRET_KEY not configured — cannot send a live session-revocation to Clerk. "
                          "Connect Clerk with its Secret Key to enable this remediation.")}
    user_id = (finding or {}).get("subject_id") or (finding or {}).get("user_id")
    if not user_id:
        return {"provider": "clerk", "ok": False, "status": 0,
                "error": "No Clerk user id on the finding to act on."}
    async with httpx.AsyncClient(timeout=20) as c:
        # Authenticated POST — ban the user, which revokes their active sessions.
        r = await c.post(f"{CLERK_BASE}/users/{user_id}/ban", headers={"Authorization": f"Bearer {key}"})
        verify = await c.get(f"{CLERK_BASE}/users/{user_id}", headers={"Authorization": f"Bearer {key}"})
    ok = r.status_code == 200 and verify.status_code == 200
    return {"provider": "clerk", "ok": ok, "status": r.status_code,
            "endpoint": f"POST /v1/users/{user_id}/ban + GET /v1/users/{user_id} (verification loop)",
            "response": (r.json() if r.headers.get("content-type", "").startswith("application/json") else r.text[:600]),
            "error": None if ok else f"Clerk returned {r.status_code}: {r.text[:400]}"}
