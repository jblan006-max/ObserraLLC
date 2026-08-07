import os
import stripe
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Request, Depends
from pydantic import BaseModel, Field

from db import db
from auth import get_current_user

stripe.api_key = os.environ.get("STRIPE_SECRET_KEY") or "sk_test_emergent"
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "")

payments_router = APIRouter()

CATALOG = [
    {"emergent_product_id": "eios_team", "name": "EIOS Team", "tax_code": "txcd_10103001",
     "prices": [{"lookup_key": "eios_team_monthly", "amount": 99900, "currency": "usd", "interval": "month"}]},
    {"emergent_product_id": "eios_enterprise", "name": "EIOS Enterprise", "tax_code": "txcd_10103001",
     "prices": [{"lookup_key": "eios_enterprise_monthly", "amount": 299900, "currency": "usd", "interval": "month"}]},
]

EDITIONS = {
    "eios_team_monthly": {"edition": "team", "entitlements": ["risk_register", "ai_governance"]},
    "eios_enterprise_monthly": {"edition": "enterprise", "entitlements": ["risk_register", "ai_governance", "sso", "priority_support"]},
}


def setup_catalog():
    for entry in CATALOG:
        product = None
        for p in stripe.Product.list(active=True).auto_paging_iter():
            if p.to_dict().get("metadata", {}).get("emergent_product_id") == entry["emergent_product_id"]:
                product = p
                break
        if not product:
            product = stripe.Product.create(name=entry["name"], tax_code=entry.get("tax_code"),
                metadata={"managed_by": "emergent", "emergent_product_id": entry["emergent_product_id"]})
        for pr in entry["prices"]:
            existing = stripe.Price.list(lookup_keys=[pr["lookup_key"]], active=True, limit=1).data
            if existing and (existing[0].unit_amount != pr["amount"] or existing[0].currency != pr["currency"]):
                stripe.Price.modify(existing[0].id, active=False)
                existing = []
            if not existing:
                stripe.Price.create(product=product.id, unit_amount=pr["amount"], currency=pr["currency"],
                    lookup_key=pr["lookup_key"], transfer_lookup_key=True, recurring={"interval": pr["interval"]})


class CheckoutRequest(BaseModel):
    lookup_key: str
    origin_url: str


@payments_router.get("/api/billing/plans")
async def plans():
    return [
        {"lookup_key": "eios_team_monthly", "name": "EIOS Team", "price": 999, "interval": "month",
         "features": ["Cyber Risk Register", "AI Governance Suite", "Dual-Mode dashboard", "Evidence-grounded AI advisor", "Up to 25 seats"]},
        {"lookup_key": "eios_enterprise_monthly", "name": "EIOS Enterprise", "price": 2999, "interval": "month",
         "features": ["Everything in Team", "SSO / SAML", "SCIM provisioning", "Unlimited seats", "Priority support", "Board packet export"]},
    ]


@payments_router.post("/api/billing/checkout")
async def create_checkout(req: CheckoutRequest, user: dict = Depends(get_current_user)):
    prices = stripe.Price.list(lookup_keys=[req.lookup_key], active=True, limit=1).data
    if not prices:
        raise HTTPException(500, f"Price not found: {req.lookup_key}")
    price = prices[0]
    session = stripe.checkout.Session.create(
        line_items=[{"price": price.id, "quantity": 1}],
        mode="subscription",
        success_url=f"{req.origin_url}/payment/success?session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=f"{req.origin_url}/billing",
        metadata={"user_id": user["id"], "org_id": user["org_id"], "lookup_key": req.lookup_key},
        automatic_tax={"enabled": True}, billing_address_collection="required",
    )
    await db.payment_transactions.insert_one({
        "session_id": session.id, "user_id": user["id"], "org_id": user["org_id"],
        "lookup_key": req.lookup_key, "amount": (price.unit_amount or 0), "currency": price.currency,
        "status": "initiated", "payment_status": "pending",
        "created_at": datetime.now(timezone.utc), "updated_at": datetime.now(timezone.utc),
    })
    return {"checkout_url": session.url, "session_id": session.id}


async def _grant_entitlement(session_meta: dict):
    org_id = session_meta.get("org_id")
    lookup = session_meta.get("lookup_key")
    ed = EDITIONS.get(lookup)
    if org_id and ed:
        await db.organizations.update_one(
            {"_id": __import__("bson").ObjectId(org_id)},
            {"$set": {"plan": ed["edition"], "entitlements": ed["entitlements"]}})


@payments_router.get("/api/payments/status/{session_id}")
async def get_status(session_id: str):
    record = await db.payment_transactions.find_one({"session_id": session_id})
    if not record:
        raise HTTPException(404, "Transaction not found")
    if record.get("payment_status") != "paid":
        try:
            s = stripe.checkout.Session.retrieve(session_id)
            if s.payment_status == "paid" or s.status == "complete":
                await db.payment_transactions.update_one(
                    {"session_id": session_id, "payment_status": {"$ne": "paid"}},
                    {"$set": {"status": "completed", "payment_status": "paid",
                              "stripe_subscription_id": s.subscription,
                              "updated_at": datetime.now(timezone.utc)}})
                await _grant_entitlement(record)
                record = await db.payment_transactions.find_one({"session_id": session_id})
        except stripe.error.StripeError:
            pass
    return {"session_id": record["session_id"], "status": record["status"],
            "payment_status": record["payment_status"]}


@payments_router.post("/api/stripe/webhook")
async def stripe_webhook(request: Request):
    payload = await request.body()
    sig = request.headers.get("stripe-signature", "")
    try:
        event = stripe.Webhook.construct_event(payload, sig, STRIPE_WEBHOOK_SECRET)
    except stripe.error.SignatureVerificationError:
        raise HTTPException(400, "Invalid signature")
    obj, t = event["data"]["object"], event["type"]
    if t == "checkout.session.completed":
        rec = await db.payment_transactions.find_one({"session_id": obj["id"]})
        await db.payment_transactions.update_one(
            {"session_id": obj["id"], "payment_status": {"$ne": "paid"}},
            {"$set": {"status": "completed", "payment_status": obj.get("payment_status", "paid"),
                      "stripe_subscription_id": obj.get("subscription"),
                      "updated_at": datetime.now(timezone.utc)}})
        if rec:
            await _grant_entitlement(rec)
    return {"status": "ok"}
