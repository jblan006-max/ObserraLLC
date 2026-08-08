"""Enterprise Connector Catalog + real auto-discovery/probe engine.

NO-MOCK: a connector is only marked "connected" when the provider returns a real HTTP 2xx to a
live authenticated probe. When no credential is present we return a truthful "credentials_required"
result (with exactly what is needed) — never a fabricated success. Every probe is written to the
Defensibility Ledger. Providers that require a customer-side OAuth app / tenant base are listed in
the catalog with their real auth + capabilities and honestly report that setup is a prerequisite.
"""
import os
import uuid
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from auth import get_current_user, require_roles, _log_audit
from db import db

connectors_router = APIRouter(prefix="/api/connectors")


# fields drive the frontend "Connect" form. token_field/base_field tell the probe how to read creds.
# probe: {method, url (may contain {base}), header, headers, ok_note}. auth: bearer|header|basic|query|webhook_post|oauth
CATALOG = [
    # ---- Identity & Access ----
    {"id": "clerk", "name": "Clerk", "category": "Identity & Access", "auth": "bearer",
     "capabilities": ["Users", "Organizations", "Sessions", "Session revocation", "User metadata"],
     "required_credentials": ["Clerk Secret Key (sk_live_…)"], "env_vars": ["CLERK_SECRET_KEY"],
     "token_field": "token", "fields": [{"key": "token", "label": "Clerk Secret Key", "secret": True, "placeholder": "sk_live_…"}],
     "probe": {"method": "GET", "url": "https://api.clerk.com/v1/users?limit=1", "ok_note": "Clerk live — users API reachable."},
     "boundary": "Real Clerk SDK calls exist; production MFA/session-revocation require the live secret."},
    {"id": "okta", "name": "Okta", "category": "Identity & Access", "auth": "bearer",
     "capabilities": ["Users", "Groups", "SSO", "Lifecycle events"], "required_credentials": ["Okta org domain", "SSWS API token"],
     "token_field": "token", "base_field": "base",
     "fields": [{"key": "base", "label": "Okta domain", "placeholder": "https://acme.okta.com"}, {"key": "token", "label": "API token (SSWS)", "secret": True}],
     "probe": {"method": "GET", "url": "{base}/api/v1/users?limit=1", "header": "Authorization", "headers": {}, "ok_note": "Okta live — users API reachable."},
     "boundary": "Requires your Okta org domain + API token."},
    {"id": "ping-identity", "name": "Ping Identity", "category": "Identity & Access", "auth": "oauth",
     "capabilities": ["SSO", "MFA", "Directory"], "required_credentials": ["PingOne environment + OAuth client"], "connectable": False,
     "boundary": "Requires a customer PingOne environment and OAuth2 client-credentials app."},
    {"id": "entra", "name": "Microsoft Entra ID", "category": "Identity & Access", "auth": "oauth",
     "capabilities": ["Devices", "Users", "Risky users", "Conditional Access"], "required_credentials": ["Azure app (client-credentials)"], "connectable": False,
     "boundary": "Connect via the Microsoft 365 credential connector (Graph client-credentials)."},
    {"id": "active-directory", "name": "Active Directory (device collection)", "category": "Identity & Access", "auth": "agent",
     "capabilities": ["Device inventory", "Group membership"], "required_credentials": ["Obserra endpoint agent / LDAP bridge"], "connectable": False,
     "boundary": "Collected via the Obserra endpoint agent or a domain LDAP bridge."},

    # ---- Commerce ----
    {"id": "stripe", "name": "Stripe", "category": "Commerce", "auth": "bearer",
     "capabilities": ["Products", "Prices", "Payment Links", "Checkout", "Signed webhooks", "Commerce metrics"],
     "required_credentials": ["Stripe Secret Key"], "env_vars": ["STRIPE_SECRET_KEY", "STRIPE_API_KEY"],
     "token_field": "token", "fields": [{"key": "token", "label": "Stripe Secret Key", "secret": True, "placeholder": "sk_…"}],
     "probe": {"method": "GET", "url": "https://api.stripe.com/v1/balance", "ok_note": "Stripe live — balance API reachable."},
     "boundary": "Real Stripe API + signed webhooks exist; production refund/dispute/reconciliation not fully accepted."},
    {"id": "salesforce", "name": "Salesforce", "category": "Commerce", "auth": "bearer",
     "capabilities": ["Accounts", "Opportunities", "Cases"], "required_credentials": ["Instance URL", "OAuth access token"],
     "token_field": "token", "base_field": "base",
     "fields": [{"key": "base", "label": "Instance URL", "placeholder": "https://acme.my.salesforce.com"}, {"key": "token", "label": "OAuth access token", "secret": True}],
     "probe": {"method": "GET", "url": "{base}/services/data/v60.0/limits", "ok_note": "Salesforce live — limits API reachable."},
     "boundary": "Requires a connected app + instance URL and OAuth token."},

    # ---- Persistence ----
    {"id": "postgresql", "name": "PostgreSQL / Supabase", "category": "Persistence", "auth": "uri",
     "capabilities": ["EIOS persistence", "Academy LCMS", "Audit", "Releases"], "required_credentials": ["TLS PostgreSQL URI"], "connectable": False,
     "boundary": "Provide a server-side TLS Postgres URI (session pooler). Health probed by the DB driver, not over HTTP."},

    # ---- Deployment & DevOps ----
    {"id": "github", "name": "GitHub", "category": "Deployment & DevOps", "auth": "bearer",
     "capabilities": ["Repositories", "Pull requests", "Actions", "Releases", "Repository dispatch"],
     "required_credentials": ["GitHub fine-grained token / App token"], "env_vars": ["GITHUB_TOKEN"],
     "token_field": "token", "fields": [{"key": "token", "label": "GitHub token", "secret": True, "placeholder": "github_pat_…"}],
     "probe": {"method": "GET", "url": "https://api.github.com/user", "headers": {"Accept": "application/vnd.github+json"}, "ok_note": "GitHub live — authenticated user resolved."},
     "boundary": "Each app needs its own least-privilege installation and scopes."},
    {"id": "vercel", "name": "Vercel", "category": "Deployment & DevOps", "auth": "bearer",
     "capabilities": ["Deployments", "Builds", "Logs", "Domains", "Project health"],
     "required_credentials": ["Vercel management token"], "env_vars": ["VERCEL_TOKEN"],
     "token_field": "token", "fields": [{"key": "token", "label": "Vercel token", "secret": True}],
     "probe": {"method": "GET", "url": "https://api.vercel.com/v2/user", "ok_note": "Vercel live — /v2/user reachable."},
     "boundary": "Direct project/deployment visibility requires the management token + project IDs."},

    # ---- AI & Media ----
    {"id": "openai", "name": "OpenAI", "category": "AI & Media", "auth": "bearer",
     "capabilities": ["Responses API", "Course authoring", "Governed generation"],
     "required_credentials": ["OpenAI API key"], "env_vars": ["OPENAI_API_KEY"],
     "token_field": "token", "fields": [{"key": "token", "label": "OpenAI API key", "secret": True, "placeholder": "sk-…"}],
     "probe": {"method": "GET", "url": "https://api.openai.com/v1/models", "ok_note": "OpenAI live — models list reachable."},
     "boundary": "POST /v1/responses is used for authoring; bearer token + optional org/project headers."},
    {"id": "anthropic", "name": "Anthropic", "category": "AI & Media", "auth": "header",
     "capabilities": ["Messages API", "Alternate course authoring"],
     "required_credentials": ["Anthropic API key"], "env_vars": ["ANTHROPIC_API_KEY"],
     "token_field": "token", "fields": [{"key": "token", "label": "Anthropic API key", "secret": True, "placeholder": "sk-ant-…"}],
     "probe": {"method": "GET", "url": "https://api.anthropic.com/v1/models", "header": "x-api-key",
               "headers": {"anthropic-version": "2023-06-01"}, "ok_note": "Anthropic live — models list reachable."},
     "boundary": "POST /v1/messages with API key + version header."},
    {"id": "synthesia", "name": "Synthesia", "category": "AI & Media", "auth": "header",
     "capabilities": ["Template training videos", "Private visibility"],
     "required_credentials": ["Synthesia API key"], "env_vars": ["SYNTHESIA_API_KEY"],
     "token_field": "token", "fields": [{"key": "token", "label": "Synthesia API key", "secret": True}],
     "probe": {"method": "GET", "url": "https://api.synthesia.io/v2/videos?limit=1", "header": "Authorization", "ok_note": "Synthesia live — videos API reachable."},
     "boundary": "POST /v2/videos for template-based generation."},
    {"id": "heygen", "name": "HeyGen", "category": "AI & Media", "auth": "header",
     "capabilities": ["Avatar/voice videos", "Captions"],
     "required_credentials": ["HeyGen API key"], "env_vars": ["HEYGEN_API_KEY"],
     "token_field": "token", "fields": [{"key": "token", "label": "HeyGen API key", "secret": True}],
     "probe": {"method": "GET", "url": "https://api.heygen.com/v2/avatars", "header": "X-Api-Key", "ok_note": "HeyGen live — avatars API reachable."},
     "boundary": "POST /v3/videos for avatar/voice generation."},
    {"id": "local-ai", "name": "Local AI runtime", "category": "AI & Media", "auth": "none",
     "capabilities": ["Local private inference", "Model availability"], "required_credentials": ["Loopback runtime base URL"],
     "base_field": "base", "fields": [{"key": "base", "label": "Runtime base URL", "placeholder": "http://localhost:11434"}],
     "probe": {"method": "GET", "url": "{base}/api/tags", "no_auth": True, "ok_note": "Local runtime live — model tags reachable."},
     "boundary": "Loopback inference; defaults to GET /api/tags on the local runtime."},

    # ---- Notification & Collaboration ----
    {"id": "slack", "name": "Slack", "category": "Notification & Collaboration", "auth": "webhook_post",
     "capabilities": ["Test delivery", "Operational alerts", "Delivery history", "Bounded retry"],
     "required_credentials": ["Slack Incoming Webhook URL"], "token_field": "webhook_url",
     "fields": [{"key": "webhook_url", "label": "Slack Incoming Webhook URL", "secret": True, "placeholder": "https://hooks.slack.com/services/…"}],
     "probe": {"ok_note": "Slack live — webhook returned ok."},
     "boundary": "Success only when Slack returns HTTP 200 with body 'ok'."},
    {"id": "teams", "name": "Microsoft Teams (Workflows)", "category": "Notification & Collaboration", "auth": "webhook_post",
     "capabilities": ["Test delivery", "Operational alerts", "Durable delivery state", "Retries"],
     "required_credentials": ["Teams Workflow webhook URL"], "token_field": "webhook_url",
     "fields": [{"key": "webhook_url", "label": "Teams Workflow webhook URL", "secret": True, "placeholder": "https://…webhook.office.com/…"}],
     "probe": {"ok_note": "Teams live — workflow accepted the test post."},
     "boundary": "Requires a successful 2xx from the Teams Workflow endpoint."},

    # ---- ITSM & Enterprise Workflow ----
    {"id": "servicenow", "name": "ServiceNow", "category": "ITSM & Workflow", "auth": "bearer",
     "capabilities": ["Access requests", "Approvals", "Claims", "CMDB", "Workflow authority"],
     "required_credentials": ["Instance URL", "Bearer / OAuth token"], "token_field": "token", "base_field": "base",
     "fields": [{"key": "base", "label": "Instance URL", "placeholder": "https://acme.service-now.com"}, {"key": "token", "label": "Bearer token", "secret": True}],
     "probe": {"method": "GET", "url": "{base}/api/now/table/sys_user?sysparm_limit=1", "ok_note": "ServiceNow live — Table API reachable."},
     "boundary": "Production scoped app + credentials + customer acceptance required."},
    {"id": "sap-scim", "name": "SAP Cloud Identity (SCIM)", "category": "ITSM & Workflow", "auth": "bearer",
     "capabilities": ["User lookup", "User creation", "Group membership", "Role evidence", "Readback"],
     "required_credentials": ["SCIM base URL", "OAuth2 client-credentials token"], "token_field": "token", "base_field": "base",
     "fields": [{"key": "base", "label": "SCIM base URL", "placeholder": "https://acme.accounts.ondemand.com/service/scim"}, {"key": "token", "label": "OAuth access token", "secret": True}],
     "probe": {"method": "GET", "url": "{base}/Users?count=1", "ok_note": "SAP SCIM live — Users endpoint reachable."},
     "boundary": "Dry-run is default; production credentials/mappings are prerequisites."},

    # ---- Endpoint, Network & Cloud Security ----
    {"id": "cloudflare", "name": "Cloudflare", "category": "Network & Cloud Security", "auth": "bearer",
     "capabilities": ["Zero Trust", "WAF", "DNS", "Access"], "required_credentials": ["Cloudflare API token"], "env_vars": ["CLOUDFLARE_API_TOKEN"],
     "token_field": "token", "fields": [{"key": "token", "label": "Cloudflare API token", "secret": True}],
     "probe": {"method": "GET", "url": "https://api.cloudflare.com/client/v4/user/tokens/verify", "ok_note": "Cloudflare live — token verified."},
     "boundary": "Scoped API token with the required Zero Trust/WAF permissions."},
    {"id": "crowdstrike", "name": "CrowdStrike Falcon", "category": "Network & Cloud Security", "auth": "oauth",
     "capabilities": ["EDR", "Device isolation", "Detections"], "required_credentials": ["Falcon API client id/secret (OAuth2)"], "connectable": False,
     "boundary": "Requires a Falcon OAuth2 API client (client-credentials) scoped to hosts/detects."},
    {"id": "zscaler", "name": "Zscaler", "category": "Network & Cloud Security", "auth": "oauth", "capabilities": ["ZIA/ZPA", "Policy", "Logs"],
     "required_credentials": ["Zscaler API key + tenant"], "connectable": False, "boundary": "Requires tenant cloud + API credentials."},
    {"id": "paloalto", "name": "Palo Alto Networks", "category": "Network & Cloud Security", "auth": "bearer", "capabilities": ["NGFW", "Cortex", "Prisma"],
     "required_credentials": ["Cortex/PAN API key + base URL"], "connectable": False, "boundary": "Requires tenant API base + key."},
    {"id": "netskope", "name": "Netskope", "category": "Network & Cloud Security", "auth": "bearer", "capabilities": ["CASB", "SWG", "DLP"],
     "required_credentials": ["Netskope tenant + API token"], "connectable": False, "boundary": "Requires tenant URL + REST API token."},
    {"id": "cisco", "name": "Cisco", "category": "Network & Cloud Security", "auth": "oauth", "capabilities": ["Umbrella", "SecureX", "Duo"],
     "required_credentials": ["Cisco API client credentials"], "connectable": False, "boundary": "Requires product-specific API client."},
    {"id": "fortinet", "name": "Fortinet", "category": "Network & Cloud Security", "auth": "bearer", "capabilities": ["FortiGate", "FortiManager"],
     "required_credentials": ["FortiCloud/FortiManager token + base"], "connectable": False, "boundary": "Requires appliance/cloud API access."},
    {"id": "checkpoint", "name": "Check Point", "category": "Network & Cloud Security", "auth": "bearer", "capabilities": ["Quantum", "Harmony"],
     "required_credentials": ["Check Point API key + mgmt base"], "connectable": False, "boundary": "Requires management API session."},
    {"id": "proofpoint", "name": "Proofpoint", "category": "Network & Cloud Security", "auth": "basic", "capabilities": ["Email security", "TAP"],
     "required_credentials": ["Service principal + secret"], "connectable": False, "boundary": "Requires TAP service credentials."},

    # ---- SIEM & GRC ----
    {"id": "splunk", "name": "Splunk", "category": "SIEM & GRC", "auth": "bearer", "capabilities": ["Search", "Alerts", "Dashboards"],
     "required_credentials": ["Splunk base URL", "HEC / bearer token"], "token_field": "token", "base_field": "base",
     "fields": [{"key": "base", "label": "Splunk base URL", "placeholder": "https://acme.splunkcloud.com:8089"}, {"key": "token", "label": "Bearer token", "secret": True}],
     "probe": {"method": "GET", "url": "{base}/services/server/info?output_mode=json", "ok_note": "Splunk live — server info reachable."},
     "boundary": "Requires management port reachability + token."},
    {"id": "sentinel", "name": "Microsoft Sentinel", "category": "SIEM & GRC", "auth": "oauth", "capabilities": ["Incidents", "Hunting", "Analytics"],
     "required_credentials": ["Azure workspace + app"], "connectable": False, "boundary": "Via Azure Log Analytics workspace + app registration."},
    {"id": "qradar", "name": "IBM QRadar", "category": "SIEM & GRC", "auth": "header", "capabilities": ["Offenses", "Rules"],
     "required_credentials": ["QRadar base + SEC token"], "token_field": "token", "base_field": "base",
     "fields": [{"key": "base", "label": "QRadar base URL", "placeholder": "https://qradar.acme.com"}, {"key": "token", "label": "SEC token", "secret": True}],
     "probe": {"method": "GET", "url": "{base}/api/system/about", "header": "SEC", "headers": {"Version": "12.0"}, "ok_note": "QRadar live — system about reachable."},
     "boundary": "Requires appliance reachability + SEC token."},
    {"id": "auditboard", "name": "AuditBoard", "category": "SIEM & GRC", "auth": "bearer", "capabilities": ["Controls", "Findings", "Evidence"],
     "required_credentials": ["AuditBoard tenant + API token"], "connectable": False, "boundary": "Requires tenant API access."},

    # ---- Business Data & BI ----
    {"id": "powerbi", "name": "Power BI", "category": "Business Data & BI", "auth": "oauth", "capabilities": ["Datasets", "Reports", "Ingestion"],
     "required_credentials": ["Azure AD app + workspace"], "connectable": False, "boundary": "Via Azure AD app + Power BI workspace."},
    {"id": "hris", "name": "HRIS", "category": "Business Data & BI", "auth": "bearer", "capabilities": ["Worker records", "Org data"],
     "required_credentials": ["HRIS API base + token"], "connectable": False, "boundary": "Provider-specific HRIS API."},
    {"id": "office-docs", "name": "Excel & PowerPoint ingestion", "category": "Business Data & BI", "auth": "upload", "capabilities": ["Spreadsheet ingest", "Deck ingest"],
     "required_credentials": ["File upload / SharePoint"], "connectable": False, "boundary": "Ingested via upload or SharePoint/Graph."},
    {"id": "qms", "name": "Generic QMS", "category": "Business Data & BI", "auth": "bearer", "capabilities": ["Quality records", "CAPA"],
     "required_credentials": ["QMS API base + token"], "connectable": False, "boundary": "Provider-specific QMS API."},
]


def _mask(s):
    return (s[:4] + "…" + s[-4:]) if s and len(s) > 8 else ("set" if s else None)


def _slug(cat):
    return cat.split("&")[0].strip().lower().replace(" ", "-")


_MUTATORS = {"stripe", "clerk", "github", "vercel", "servicenow", "sap-scim", "slack", "teams", "cloudflare"}


def _manifest(entry):
    """Provider identity manifest (published by every connector)."""
    caps = ["health.read", "inventory.read", "telemetry.read"]
    if entry["id"] in _MUTATORS:
        caps += ["actions.execute", "actions.readback"]
    return {"provider_id": f"{entry['id']}-{_slug(entry['category'])}", "version": "1.0.0",
            "capabilities": caps, "domain_capabilities": entry.get("capabilities", [])}


def _health(state, code):
    """Normalize a probe state to the standard health state + failure class."""
    if state == "connected":
        return "healthy", None
    if state == "auth_failed":
        return "unavailable", "unauthorized"
    if state == "credentials_required":
        return "unavailable", "invalid-configuration"
    if state == "unreachable":
        return "unavailable", "unavailable"
    if state == "error":
        return ("degraded", "rate-limited") if code == 429 else ("degraded", "invalid-response")
    return "unavailable", None


def _conn_state(state):
    """Map a probe state onto the authoritative connected-target connection-state taxonomy."""
    return {"connected": "connected", "auth_failed": "failed", "credentials_required": "discovered",
            "unreachable": "offline", "error": "degraded", "available": "discovered"}.get(state, "discovered")


async def _log(org_id, entry):
    now = datetime.now(timezone.utc).isoformat()
    doc = {"org_id": org_id, "id": str(uuid.uuid4()), "started_at": now, "finished_at": now, **entry}
    await db.remediation_ledger.insert_one(dict(doc))
    return doc["id"]


async def _probe(entry, creds=None):
    """Perform a REAL connectivity probe. Returns (state, http_status, endpoint, detail, source)."""
    creds = creds or {}
    auth = entry.get("auth")
    probe = entry.get("probe")
    if entry.get("connectable") is False or not probe:
        needs = ", ".join(entry.get("required_credentials", ["provider-side setup"]))
        return ("credentials_required", None, entry.get("id"),
                f"Not connected — requires {needs}. {entry.get('boundary', '')}".strip(), None)

    # resolve token/base from provided creds, else environment
    source = None
    token = None
    tf = entry.get("token_field")
    if tf and creds.get(tf):
        token = creds.get(tf); source = "provided"
    if token is None and auth != "none":
        for ev in entry.get("env_vars", []):
            if os.environ.get(ev):
                token = os.environ[ev]; source = "env"; break

    base = creds.get(entry.get("base_field")) if entry.get("base_field") else None
    url = probe.get("url", "")
    if "{base}" in url:
        if not base:
            return ("credentials_required", None, entry.get("id"),
                    f"Provide the base URL — {', '.join(entry.get('required_credentials', []))}.", None)
        url = url.replace("{base}", base.rstrip("/"))

    if auth == "webhook_post":
        wh = token
        if not wh:
            return ("credentials_required", None, "POST <webhook>", "Paste the webhook URL to run a live test post.", None)
        try:
            async with httpx.AsyncClient(timeout=15) as c:
                r = await c.post(wh, json={"text": "Obserra EIOS connectivity test — please ignore."})
        except Exception as e:
            return ("unreachable", None, "POST <webhook>", f"Network error: {str(e)[:160]}", source)
        ok = r.status_code in (200, 201, 202, 204) and (entry["id"] != "slack" or r.text.strip().lower() == "ok")
        if ok:
            return ("connected", r.status_code, "POST <webhook>", probe.get("ok_note", "Webhook accepted the test post."), source)
        return ("error", r.status_code, "POST <webhook>", f"Webhook returned {r.status_code}: {r.text[:120]}", source)

    if auth in ("bearer", "header", "basic", "query") and not token:
        return ("credentials_required", None, f"{probe.get('method', 'GET')} {url}",
                f"No credential present — provide {', '.join(entry.get('required_credentials', ['an API key']))}.", None)

    headers = dict(probe.get("headers", {}))
    auth_arg = None
    params = {}
    if auth == "bearer":
        headers["Authorization"] = f"Bearer {token}"
    elif auth == "header":
        headers[probe.get("header", "x-api-key")] = token
    elif auth == "basic":
        u, _, p = (token or "").partition(":")
        auth_arg = (u, p)
    elif auth == "query":
        params[probe.get("param", "key")] = token

    method = probe.get("method", "GET")
    ep = f"{method} {url}"
    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as c:
            r = await c.request(method, url, headers=headers, params=params, auth=auth_arg)
    except Exception as e:
        return ("unreachable", None, ep, f"Network error: {str(e)[:160]}", source)
    if r.status_code in (200, 201, 204):
        return ("connected", r.status_code, ep, probe.get("ok_note", f"Live — provider returned {r.status_code}."), source)
    if r.status_code in (401, 403):
        return ("auth_failed", r.status_code, ep, f"Reached provider but rejected ({r.status_code}) — check the credential/scopes.", source)
    return ("error", r.status_code, ep, f"Provider returned {r.status_code}: {r.text[:140]}", source)


async def _state_index(org_id):
    rows = await db.connector_state.find({"org_id": org_id}, {"_id": 0}).to_list(200)
    return {r["cid"]: r for r in rows}


def _public(entry, st):
    st = st or {}
    return {
        "id": entry["id"], "name": entry["name"], "category": entry["category"], "auth": entry["auth"],
        "capabilities": entry.get("capabilities", []), "required_credentials": entry.get("required_credentials", []),
        "boundary": entry.get("boundary", ""), "connectable": entry.get("connectable", True),
        "fields": entry.get("fields", []),
        "state": st.get("state", "available"), "http_status": st.get("http_status"),
        "endpoint": st.get("endpoint"), "detail": st.get("detail"),
        "checked_at": st.get("checked_at"), "connected_at": st.get("connected_at"),
        "creds_masked": st.get("creds_masked"), "source": st.get("source"),
        "manifest": _manifest(entry),
        "health": _health(st.get("state", "available"), st.get("http_status"))[0],
        "failure_class": _health(st.get("state", "available"), st.get("http_status"))[1],
        "connection_state": _conn_state(st.get("state", "available")),
    }


@connectors_router.get("/catalog")
async def get_catalog(user: dict = Depends(get_current_user)):
    idx = await _state_index(user["org_id"])
    items = [_public(e, idx.get(e["id"])) for e in CATALOG]
    cats = {}
    for it in items:
        cats.setdefault(it["category"], []).append(it)
    connected = sum(1 for i in items if i["state"] == "connected")
    return {"categories": [{"name": k, "items": v} for k, v in cats.items()],
            "items": items, "total": len(items), "connected": connected}


async def _persist(org_id, entry, state, http_status, endpoint, detail, source, creds=None):
    now = datetime.now(timezone.utc).isoformat()
    doc = {"org_id": org_id, "cid": entry["id"], "state": state, "http_status": http_status,
           "endpoint": endpoint, "detail": detail, "checked_at": now, "source": source}
    if state == "connected":
        doc["connected_at"] = now
    if creds:
        # store raw creds for future re-probes; only a masked hint is ever returned to clients
        tf = entry.get("token_field")
        doc["creds"] = creds
        if tf and creds.get(tf):
            doc["creds_masked"] = _mask(creds.get(tf))
    await db.connector_state.update_one({"org_id": org_id, "cid": entry["id"]}, {"$set": doc}, upsert=True)
    return doc


@connectors_router.post("/discover")
async def discover(admin: dict = Depends(require_roles("admin"))):
    """Auto-discovery: probe every provider LIVE. Connects the ones with valid credentials (env or
    saved), truthfully marks the rest 'credentials_required', and records the sweep to the ledger."""
    org_id = admin["org_id"]
    idx = await _state_index(org_id)
    results = []
    summary = {"connected": 0, "credentials_required": 0, "auth_failed": 0, "unreachable": 0, "error": 0}
    for e in CATALOG:
        saved = (idx.get(e["id"]) or {}).get("creds")
        state, code, ep, detail, source = await _probe(e, saved)
        await _persist(org_id, e, state, code, ep, detail, source, creds=saved)
        summary[state] = summary.get(state, 0) + 1
        hh, fc = _health(state, code)
        results.append({"id": e["id"], "name": e["name"], "state": state, "health": hh, "failure_class": fc,
                        "connection_state": _conn_state(state), "http_status": code, "endpoint": ep, "detail": detail})
    await _log(org_id, {"action": "connector-discover", "by": admin.get("email"), "provider": "catalog",
                        "status": f"{summary['connected']} connected", "verified": summary["connected"] > 0,
                        "message": (f"Auto-discovery probed {len(CATALOG)} providers: {summary['connected']} connected, "
                                    f"{summary['credentials_required']} need credentials, {summary['auth_failed']} auth-failed, "
                                    f"{summary['unreachable'] + summary['error']} unreachable/error."),
                        "external": {"summary": summary, "results": results}})
    await _log_audit(org_id, admin["email"], "connector.discover", f"Auto-discovery: {summary['connected']} connected")
    return {"summary": summary, "results": results}


class ConnectBody(BaseModel):
    creds: dict = {}


@connectors_router.post("/{cid}/connect")
async def connect(cid: str, body: ConnectBody, admin: dict = Depends(require_roles("admin"))):
    entry = next((e for e in CATALOG if e["id"] == cid), None)
    if not entry:
        return {"state": "error", "detail": "Unknown connector."}
    state, code, ep, detail, source = await _probe(entry, body.creds)
    await _persist(admin["org_id"], entry, state, code, ep, detail, source or "provided", creds=body.creds or None)
    await _log(admin["org_id"], {"action": "connector-connect", "provider": entry["name"], "by": admin.get("email"),
                                 "status": state, "verified": state == "connected", "message": detail,
                                 "external": {"endpoint": ep, "http_status": code, "state": state}})
    await _log_audit(admin["org_id"], admin["email"], "connector.connect", f"{cid} → {state}")
    return {"id": cid, "state": state, "health": _health(state, code)[0], "failure_class": _health(state, code)[1],
            "connection_state": _conn_state(state), "http_status": code, "endpoint": ep, "detail": detail}


@connectors_router.post("/{cid}/test")
async def test_connector(cid: str, admin: dict = Depends(require_roles("admin"))):
    entry = next((e for e in CATALOG if e["id"] == cid), None)
    if not entry:
        return {"state": "error", "detail": "Unknown connector."}
    idx = await _state_index(admin["org_id"])
    saved = (idx.get(cid) or {}).get("creds")
    state, code, ep, detail, source = await _probe(entry, saved)
    await _persist(admin["org_id"], entry, state, code, ep, detail, source, creds=saved)
    await _log(admin["org_id"], {"action": "connector-test", "provider": entry["name"], "by": admin.get("email"),
                                 "status": state, "verified": state == "connected", "message": detail,
                                 "external": {"endpoint": ep, "http_status": code, "state": state}})
    return {"id": cid, "state": state, "health": _health(state, code)[0], "failure_class": _health(state, code)[1],
            "connection_state": _conn_state(state), "http_status": code, "endpoint": ep, "detail": detail}


@connectors_router.post("/{cid}/disconnect")
async def disconnect(cid: str, admin: dict = Depends(require_roles("admin"))):
    await db.connector_state.delete_one({"org_id": admin["org_id"], "cid": cid})
    await _log_audit(admin["org_id"], admin["email"], "connector.disconnect", f"Disconnected {cid}")
    return {"ok": True}
