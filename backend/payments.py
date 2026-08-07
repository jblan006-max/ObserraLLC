import os
import secrets
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
    {"emergent_product_id": "eios_enterprise", "name": "EIOS Enterprise (All-Access)", "tax_code": "txcd_10103001", "prices": [
        {"lookup_key": "eios_enterprise_monthly", "amount": 299900, "currency": "usd", "interval": "month"},
        {"lookup_key": "eios_enterprise_yearly", "amount": 3238800, "currency": "usd", "interval": "year"}]},
    {"emergent_product_id": "eios_pack_ai_gov", "name": "Add-on · AI Governance", "tax_code": "txcd_10103001", "prices": [
        {"lookup_key": "pack_ai_gov_monthly", "amount": 7900, "currency": "usd", "interval": "month"},
        {"lookup_key": "pack_ai_gov_yearly", "amount": 79000, "currency": "usd", "interval": "year"}]},
    {"emergent_product_id": "eios_pack_cyber", "name": "Add-on · Cyber Risk", "tax_code": "txcd_10103001", "prices": [
        {"lookup_key": "pack_cyber_monthly", "amount": 9900, "currency": "usd", "interval": "month"},
        {"lookup_key": "pack_cyber_yearly", "amount": 99000, "currency": "usd", "interval": "year"}]},
    {"emergent_product_id": "eios_pack_tpr", "name": "Add-on · Third-Party Risk", "tax_code": "txcd_10103001", "prices": [
        {"lookup_key": "pack_tpr_monthly", "amount": 5900, "currency": "usd", "interval": "month"},
        {"lookup_key": "pack_tpr_yearly", "amount": 59000, "currency": "usd", "interval": "year"}]},
    {"emergent_product_id": "eios_pack_assets", "name": "Add-on · Asset Intelligence", "tax_code": "txcd_10103001", "prices": [
        {"lookup_key": "pack_assets_monthly", "amount": 4900, "currency": "usd", "interval": "month"},
        {"lookup_key": "pack_assets_yearly", "amount": 49000, "currency": "usd", "interval": "year"}]},
    {"emergent_product_id": "eios_pack_audit", "name": "Add-on · Audit & Evidence", "tax_code": "txcd_10103001", "prices": [
        {"lookup_key": "pack_audit_monthly", "amount": 3900, "currency": "usd", "interval": "month"},
        {"lookup_key": "pack_audit_yearly", "amount": 39000, "currency": "usd", "interval": "year"}]},
    {"emergent_product_id": "eios_pack_reporting", "name": "Add-on · Reporting & Board", "tax_code": "txcd_10103001", "prices": [
        {"lookup_key": "pack_reporting_monthly", "amount": 6900, "currency": "usd", "interval": "month"},
        {"lookup_key": "pack_reporting_yearly", "amount": 69000, "currency": "usd", "interval": "year"}]},
]

BASE_ENTITLEMENTS = ["cyber_risk", "ai_governance"]
EDITIONS = {
    "eios_enterprise_monthly": {"edition": "enterprise", "interval": "month"},
    "eios_enterprise_yearly": {"edition": "enterprise", "interval": "year"},
}

PACKS = [
    {"id": "ai_governance", "entitlement": "ai_governance", "name": "AI Governance",
     "desc": "AI agent oversight, NIST mapping, model cards & incidents.",
     "pages": ["AI Agents", "AI Governance"],
     "monthly": {"lookup_key": "pack_ai_gov_monthly", "price": 79}, "yearly": {"lookup_key": "pack_ai_gov_yearly", "price": 790}},
    {"id": "cyber_risk", "entitlement": "cyber_risk", "name": "Cyber Risk",
     "desc": "Risk Register, Control Monitoring & the live Situation Room.",
     "pages": ["Risk Register", "Control Monitoring", "Situation Room", "Cyber Risk"],
     "monthly": {"lookup_key": "pack_cyber_monthly", "price": 99}, "yearly": {"lookup_key": "pack_cyber_yearly", "price": 990}},
    {"id": "third_party_risk", "entitlement": "third_party_risk", "name": "Third-Party Risk",
     "desc": "Vendor risk scoring, attestations & remediation logs.",
     "pages": ["Third-Party Risk"],
     "monthly": {"lookup_key": "pack_tpr_monthly", "price": 59}, "yearly": {"lookup_key": "pack_tpr_yearly", "price": 590}},
    {"id": "asset_intelligence", "entitlement": "asset_intelligence", "name": "Asset Intelligence",
     "desc": "Asset inventory, criticality & exposure scoring.",
     "pages": ["Asset Intelligence"],
     "monthly": {"lookup_key": "pack_assets_monthly", "price": 49}, "yearly": {"lookup_key": "pack_assets_yearly", "price": 490}},
    {"id": "audit_evidence", "entitlement": "audit_evidence", "name": "Audit & Evidence",
     "desc": "Immutable audit log & the audit-ready evidence binder.",
     "pages": ["Audit Log"],
     "monthly": {"lookup_key": "pack_audit_monthly", "price": 39}, "yearly": {"lookup_key": "pack_audit_yearly", "price": 390}},
    {"id": "reporting_board", "entitlement": "reporting_board", "name": "Reporting & Board",
     "desc": "Evidence & Reporting, Exec Snapshot & compliance posture.",
     "pages": ["Evidence & Reporting", "Exec Snapshot", "Compliance Posture"],
     "monthly": {"lookup_key": "pack_reporting_monthly", "price": 69}, "yearly": {"lookup_key": "pack_reporting_yearly", "price": 690}},
]
_PACK_BY_LOOKUP = {}
for _p in PACKS:
    _PACK_BY_LOOKUP[_p["monthly"]["lookup_key"]] = _p
    _PACK_BY_LOOKUP[_p["yearly"]["lookup_key"]] = _p


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
        {"tier": "enterprise", "name": "EIOS Enterprise — All Access", "monthly": {"lookup_key": "eios_enterprise_monthly", "price": 2999},
         "yearly": {"lookup_key": "eios_enterprise_yearly", "price": 32388},
         "features": ["Every dashboard & add-on pack unlocked", "AI Governance, Cyber Risk, Third-Party Risk, Assets, Audit & Evidence, Reporting & Board", "SSO / SAML + SCIM", "Unlimited seats", "Board packet PDF + email", "Priority support"]},
    ]


@payments_router.get("/api/modules")
async def modules(user: dict = Depends(get_current_user)):
    org = await db.organizations.find_one({"_id": ObjectId(user["org_id"])})
    ents = set(org.get("entitlements", []))
    enterprise = org.get("plan") == "enterprise"
    return [{**p, "owned": bool(enterprise or p["entitlement"] in ents)} for p in PACKS]


class CheckoutRequest(BaseModel):
    lookup_key: str | None = None
    lookup_keys: list[str] | None = None
    origin_url: str


async def _checkout(req: CheckoutRequest, user: dict, mode: str):
    keys = req.lookup_keys or ([req.lookup_key] if req.lookup_key else [])
    keys = [k for k in keys if k]
    if not keys:
        raise HTTPException(400, "No plan selected")
    line_items = []
    for k in keys:
        prices = stripe.Price.list(lookup_keys=[k], active=True, limit=1).data
        if not prices:
            raise HTTPException(500, f"Price not found: {k}")
        line_items.append({"price": prices[0].id, "quantity": 1})
    kwargs = dict(
        line_items=line_items, mode=mode,
        success_url=f"{req.origin_url}/payment/success?session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=f"{req.origin_url}/app/marketplace",
        metadata={"user_id": user["id"], "org_id": user["org_id"], "lookup_keys": ",".join(keys)})
    try:
        if mode == "subscription":
            session = stripe.checkout.Session.create(**kwargs, managed_payments={"enabled": True})
        else:
            session = stripe.checkout.Session.create(**kwargs, automatic_tax={"enabled": True}, billing_address_collection="required")
    except stripe.error.InvalidRequestError:
        session = stripe.checkout.Session.create(**kwargs, automatic_tax={"enabled": True}, billing_address_collection="required")
    await db.payment_transactions.insert_one({
        "session_id": session.id, "user_id": user["id"], "org_id": user["org_id"],
        "lookup_key": keys[0], "lookup_keys": keys, "currency": "usd",
        "status": "initiated", "payment_status": "pending",
        "created_at": datetime.now(timezone.utc), "updated_at": datetime.now(timezone.utc)})
    return {"checkout_url": session.url, "session_id": session.id}


@payments_router.post("/api/billing/checkout")
async def create_checkout(req: CheckoutRequest, user: dict = Depends(get_current_user)):
    return await _checkout(req, user, "subscription")


@payments_router.post("/api/modules/checkout")
async def module_checkout(req: CheckoutRequest, user: dict = Depends(get_current_user)):
    return await _checkout(req, user, "subscription")


@payments_router.get("/api/licenses")
async def licenses(user: dict = Depends(get_current_user)):
    org = await db.organizations.find_one({"_id": ObjectId(user["org_id"])}, {"_id": 0, "licenses": 1}) or {}
    return org.get("licenses", [])


def _gen_key(pack):
    return f"OBS-{pack['entitlement'][:4].upper()}-{secrets.token_hex(4).upper()}-{secrets.token_hex(2).upper()}"


async def _issue_license(org_id: str, pack: dict, lookup: str) -> str:
    key = _gen_key(pack)
    await db.organizations.update_one({"_id": ObjectId(org_id)}, {"$push": {"licenses": {
        "key": key, "entitlement": pack["entitlement"], "pack": pack["name"], "lookup_key": lookup,
        "issued_at": datetime.now(timezone.utc).isoformat()}}})
    return key


async def _email_licenses(org_id: str, granted: list):
    from kernel import notifications
    admins = await db.users.find({"org_id": org_id, "role": {"$in": ["admin", "executive"]}}, {"_id": 0, "email": 1}).to_list(50)
    rows = "".join(
        f"<tr><td style='padding:6px 12px;border-bottom:1px solid #eee'>{p['name']}</td>"
        f"<td style='padding:6px 12px;border-bottom:1px solid #eee;font-family:monospace;color:#0e7490'>{k}</td></tr>"
        for p, k in granted)
    html = ("<div style='font:400 14px Arial;color:#0f1e3d'>"
            "<h2 style='font:800 18px Arial'>Your Obserra add-on is active</h2>"
            "<p>Access has been unlocked in-app for your organization. Your license key(s):</p>"
            f"<table style='border-collapse:collapse;margin:8px 0'>{rows}</table>"
            "<p style='color:#6b7280;font-size:12px'>Keep these keys confidential — they identify your entitlement.</p></div>")
    for a in admins:
        if a.get("email"):
            try:
                await notifications.send_email(a["email"], "Obserra — add-on unlocked & license key", html)
            except Exception:
                pass


async def _grant(record: dict):
    org_id = record.get("org_id")
    if not org_id:
        return
    keys = record.get("lookup_keys") or ([record.get("lookup_key")] if record.get("lookup_key") else [])
    oid = {"_id": ObjectId(org_id)}
    org = await db.organizations.find_one(oid, {"_id": 0, "entitlements": 1}) or {}
    have = set(org.get("entitlements", []))
    granted = []
    for lookup in keys:
        if lookup in EDITIONS:
            ed = EDITIONS[lookup]
            days = 365 if ed["interval"] == "year" else 30
            await db.organizations.update_one(oid, {"$set": {
                "plan": ed["edition"], "subscription_status": "active", "billing_interval": ed["interval"],
                "current_period_end": (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()},
                "$addToSet": {"entitlements": {"$each": BASE_ENTITLEMENTS}}})
        elif lookup in _PACK_BY_LOOKUP:
            pack = _PACK_BY_LOOKUP[lookup]
            await db.organizations.update_one(oid, {"$addToSet": {"entitlements": pack["entitlement"]}})
            if pack["entitlement"] not in have:
                key = await _issue_license(org_id, pack, lookup)
                granted.append((pack, key))
                have.add(pack["entitlement"])
    if granted:
        await _email_licenses(org_id, granted)
    await db.audit_logs.insert_one({"org_id": org_id, "actor": "stripe", "action": "billing.grant",
        "detail": f"Entitlement granted for {', '.join(keys)}", "ts": datetime.now(timezone.utc).isoformat()})


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
