import os
import stripe
from datetime import datetime, timezone, timedelta
from bson import ObjectId
from fastapi import APIRouter, HTTPException, Request, Depends
from pydantic import BaseModel

from db import db
from auth import get_current_user

stripe.api_key = os.environ.get("STRIPE_SECRET_KEY") or "sk_test_emergent"
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "")
payments_router = APIRouter()

CATALOG = [
    {"emergent_product_id": "eios_team", "name": "EIOS Team", "tax_code": "txcd_10103001", "prices": [
        {"lookup_key": "eios_team_monthly", "amount": 99900, "currency": "usd", "interval": "month"},
        {"lookup_key": "eios_team_yearly", "amount": 1078800, "currency": "usd", "interval": "year"}]},
    {"emergent_product_id": "eios_enterprise", "name": "EIOS Enterprise", "tax_code": "txcd_10103001", "prices": [
        {"lookup_key": "eios_enterprise_monthly", "amount": 299900, "currency": "usd", "interval": "month"},
        {"lookup_key": "eios_enterprise_yearly", "amount": 3238800, "currency": "usd", "interval": "year"}]},
    {"emergent_product_id": "eios_mod_situation", "name": "Add-on · Enterprise Situation Room", "tax_code": "txcd_10103001",
     "prices": [{"lookup_key": "eios_mod_situation", "amount": 49900, "currency": "usd"}]},
    {"emergent_product_id": "eios_mod_assets", "name": "Add-on · Asset Intelligence", "tax_code": "txcd_10103001",
     "prices": [{"lookup_key": "eios_mod_assets", "amount": 39900, "currency": "usd"}]},
    {"emergent_product_id": "eios_mod_reporting", "name": "Add-on · Evidence & Reporting", "tax_code": "txcd_10103001",
     "prices": [{"lookup_key": "eios_mod_reporting", "amount": 29900, "currency": "usd"}]},
]

BASE_ENTITLEMENTS = ["risk_register", "ai_governance"]
EDITIONS = {
    "eios_team_monthly": {"edition": "team", "interval": "month"},
    "eios_team_yearly": {"edition": "team", "interval": "year"},
    "eios_enterprise_monthly": {"edition": "enterprise", "interval": "month"},
    "eios_enterprise_yearly": {"edition": "enterprise", "interval": "year"},
}

MODULES = [
    {"id": "executive_overview", "name": "Executive Overview", "desc": "Board-ready health index, KPIs & recommendations.", "entitlement": "risk_register", "included": True, "price": 0},
    {"id": "ai_governance", "name": "AI Governance Suite", "desc": "AI inventory, NIST mapping, model cards & incidents.", "entitlement": "ai_governance", "included": True, "price": 0},
    {"id": "situation_room", "name": "Enterprise Situation Room", "desc": "Live incident + critical-risk command view.", "entitlement": "situation_room", "lookup_key": "eios_mod_situation", "price": 499},
    {"id": "asset_intelligence", "name": "Asset Intelligence", "desc": "Asset inventory, criticality & exposure scoring.", "entitlement": "asset_intelligence", "lookup_key": "eios_mod_assets", "price": 399},
    {"id": "evidence_reporting", "name": "Evidence & Reporting", "desc": "Report library, PDF/board packet & lineage.", "entitlement": "evidence_reporting", "lookup_key": "eios_mod_reporting", "price": 299},
]
_MOD_BY_LOOKUP = {m["lookup_key"]: m for m in MODULES if m.get("lookup_key")}


def setup_catalog():
    try:
        s = stripe.tax.Settings.retrieve()
        if not (s.head_office and getattr(s.head_office, "address", None)):
            stripe.tax.Settings.modify(
                head_office={"address": {"country": "US", "line1": "500 Market St", "city": "San Francisco", "state": "CA", "postal_code": "94105"}},
                defaults={"tax_behavior": "exclusive"})
    except Exception:
        pass
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
                kwargs = dict(product=product.id, unit_amount=pr["amount"], currency=pr["currency"],
                              lookup_key=pr["lookup_key"], transfer_lookup_key=True)
                if pr.get("interval"):
                    kwargs["recurring"] = {"interval": pr["interval"]}
                stripe.Price.create(**kwargs)


@payments_router.get("/api/billing/plans")
async def plans():
    return [
        {"tier": "team", "name": "EIOS Team", "monthly": {"lookup_key": "eios_team_monthly", "price": 999},
         "yearly": {"lookup_key": "eios_team_yearly", "price": 10788},
         "features": ["Executive Overview dashboard", "Cyber Risk Register", "AI Governance Suite", "Evidence-grounded worker AI", "Up to 25 seats", "14-day trial"]},
        {"tier": "enterprise", "name": "EIOS Enterprise", "monthly": {"lookup_key": "eios_enterprise_monthly", "price": 2999},
         "yearly": {"lookup_key": "eios_enterprise_yearly", "price": 32388},
         "features": ["Everything in Team", "SSO / SAML + SCIM", "Unlimited seats", "All add-on dashboards included", "Board packet PDF + email", "Priority support"]},
    ]


@payments_router.get("/api/modules")
async def modules(user: dict = Depends(get_current_user)):
    org = await db.organizations.find_one({"_id": ObjectId(user["org_id"])})
    ents = set(org.get("entitlements", []))
    enterprise = org.get("plan") == "enterprise"
    out = []
    for m in MODULES:
        owned = m.get("included") or m["entitlement"] in ents or enterprise
        out.append({**m, "owned": bool(owned), "included": bool(m.get("included"))})
    return out


class CheckoutRequest(BaseModel):
    lookup_key: str
    origin_url: str


async def _checkout(req: CheckoutRequest, user: dict, mode: str):
    prices = stripe.Price.list(lookup_keys=[req.lookup_key], active=True, limit=1).data
    if not prices:
        raise HTTPException(500, f"Price not found: {req.lookup_key}")
    price = prices[0]
    kwargs = dict(
        line_items=[{"price": price.id, "quantity": 1}], mode=mode,
        success_url=f"{req.origin_url}/payment/success?session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=f"{req.origin_url}/billing",
        metadata={"user_id": user["id"], "org_id": user["org_id"], "lookup_key": req.lookup_key})
    try:
        if mode == "subscription":
            session = stripe.checkout.Session.create(**kwargs, managed_payments={"enabled": True})
        else:
            session = stripe.checkout.Session.create(**kwargs, automatic_tax={"enabled": True}, billing_address_collection="required")
    except stripe.error.InvalidRequestError as e:
        session = stripe.checkout.Session.create(**kwargs, automatic_tax={"enabled": True}, billing_address_collection="required")
    await db.payment_transactions.insert_one({
        "session_id": session.id, "user_id": user["id"], "org_id": user["org_id"],
        "lookup_key": req.lookup_key, "amount": (price.unit_amount or 0), "currency": price.currency,
        "status": "initiated", "payment_status": "pending",
        "created_at": datetime.now(timezone.utc), "updated_at": datetime.now(timezone.utc)})
    return {"checkout_url": session.url, "session_id": session.id}


@payments_router.post("/api/billing/checkout")
async def create_checkout(req: CheckoutRequest, user: dict = Depends(get_current_user)):
    return await _checkout(req, user, "subscription")


@payments_router.post("/api/modules/checkout")
async def module_checkout(req: CheckoutRequest, user: dict = Depends(get_current_user)):
    return await _checkout(req, user, "payment")


async def _grant(record: dict):
    org_id = record.get("org_id")
    lookup = record.get("lookup_key")
    if not org_id:
        return
    oid = {"_id": ObjectId(org_id)}
    if lookup in EDITIONS:
        ed = EDITIONS[lookup]
        days = 365 if ed["interval"] == "year" else 30
        await db.organizations.update_one(oid, {"$set": {
            "plan": ed["edition"], "subscription_status": "active", "billing_interval": ed["interval"],
            "current_period_end": (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()},
            "$addToSet": {"entitlements": {"$each": BASE_ENTITLEMENTS}}})
    elif lookup in _MOD_BY_LOOKUP:
        await db.organizations.update_one(oid, {"$addToSet": {"entitlements": _MOD_BY_LOOKUP[lookup]["entitlement"]}})
    await db.audit_logs.insert_one({"org_id": org_id, "actor": "stripe", "action": "billing.grant",
        "detail": f"Entitlement granted for {lookup}", "ts": datetime.now(timezone.utc).isoformat()})


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
                    {"$set": {"status": "completed", "payment_status": "paid", "updated_at": datetime.now(timezone.utc)}})
                await _grant(record)
                record = await db.payment_transactions.find_one({"session_id": session_id})
        except stripe.error.StripeError:
            pass
    return {"session_id": record["session_id"], "status": record["status"], "payment_status": record["payment_status"]}


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
            {"$set": {"status": "completed", "payment_status": obj.get("payment_status", "paid"), "updated_at": datetime.now(timezone.utc)}})
        if rec:
            await _grant(rec)
    return {"status": "ok"}
