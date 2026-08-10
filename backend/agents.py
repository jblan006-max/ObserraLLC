"""AI Agent Governance — the first standalone app composed on the kernel.

Composes: Asset Model (agent inventory) · Policy Engine (tool/permission
governance) · Obserrian AI + AI Context Engine (red-team) · Workflow Engine
(finding remediation) · Notification Engine (alerts) · Audit Ledger.

Red-team scoring is heuristic/deterministic (MOCKED evaluation) — it inspects
each agent's guardrails rather than calling a live model, so runs are fast,
free and reproducible.
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from auth import get_current_user, require_roles, _log_audit
from db import db
from kernel import notifications, workflows
from agent_reports import (
    _evidence_snapshot, _evidence_markdown, _evidence_pdf, _qa_markdown,
    _build_board_digest, _brand_watermark_pdf, _RUNTIME_PLAYBOOKS,
    _sla_for, _escalation_hours_for, _oncall_recipient, _canonical_snapshot_hash,
    _stamp_verified_seal, _run_auditor_room_weekly_digest,
)

agents_router = APIRouter(prefix="/api/agents")

KERNEL_COMPOSITION = [
    "Asset Model", "Policy Engine", "AI Context Engine", "Obserrian AI",
    "Workflow Engine", "Notification Engine", "Audit Ledger",
]

AGENT_SEED = [
    {"ref": "AGT-001", "name": "Invoice Reconciliation Agent", "owner": "Finance Ops", "model": "gpt-5.6",
     "tools": ["sql.read", "email.send", "erp.write"], "permissions": ["finance.read", "finance.write"],
     "risk_class": "High", "status": "sanctioned",
     "guardrails": {"input_filtering": True, "output_filtering": True, "tool_allowlist": True, "human_in_loop": False}},
    {"ref": "AGT-002", "name": "IT Support Copilot", "owner": "Service Desk", "model": "claude-sonnet-5",
     "tools": ["kb.read", "ticket.write", "shell.exec"], "permissions": ["itsm.read", "itsm.write"],
     "risk_class": "Critical", "status": "restricted",
     "guardrails": {"input_filtering": False, "output_filtering": False, "tool_allowlist": False, "human_in_loop": False}},
    {"ref": "AGT-003", "name": "HR Policy Assistant", "owner": "People Team", "model": "gemini-3-pro",
     "tools": ["kb.read"], "permissions": ["hr.read"],
     "risk_class": "Medium", "status": "sanctioned",
     "guardrails": {"input_filtering": True, "output_filtering": True, "tool_allowlist": True, "human_in_loop": True}},
]

# Each probe is defended when the mapped guardrail is present.
REDTEAM_PROBES = [
    {"id": "PI-01", "name": "Direct instruction override", "category": "Prompt Injection", "guard": "input_filtering", "severity": "High"},
    {"id": "PI-02", "name": "Indirect injection via tool output", "category": "Prompt Injection", "guard": "output_filtering", "severity": "High"},
    {"id": "TL-01", "name": "Unsanctioned tool invocation", "category": "Tool Misuse", "guard": "tool_allowlist", "severity": "Critical"},
    {"id": "DA-01", "name": "Sensitive data exfiltration", "category": "Data Leakage", "guard": "output_filtering", "severity": "High"},
    {"id": "JB-01", "name": "High-impact action without approval", "category": "Jailbreak", "guard": "human_in_loop", "severity": "Critical"},
]

SANCTIONED_TOOLS = {"sql.read", "kb.read", "ticket.write", "email.send", "erp.write", "itsm.read", "itsm.write", "hr.read"}
DANGEROUS_TOOLS = {"shell.exec", "cloud.admin", "iam.write"}


def _now():
    return datetime.now(timezone.utc).isoformat()


async def _seed(org_id):
    from bson import ObjectId
    org = await db.organizations.find_one({"_id": ObjectId(org_id)}, {"live_only": 1})
    if org and org.get("live_only"):
        return
    if await db.ai_agents.count_documents({"org_id": org_id}) == 0:
        await db.ai_agents.insert_many([{**a, "org_id": org_id, "last_redteam": None} for a in AGENT_SEED])


def _tool_violations(agent):
    return [t for t in agent.get("tools", []) if t in DANGEROUS_TOOLS and not agent["guardrails"].get("tool_allowlist")]


@agents_router.get("")
async def list_agents(user: dict = Depends(get_current_user)):
    await _seed(user["org_id"])
    agents = await db.ai_agents.find({"org_id": user["org_id"]}, {"_id": 0}).to_list(200)
    for a in agents:
        a["tool_violations"] = _tool_violations(a)
    return {"composition": KERNEL_COMPOSITION, "agents": agents}


@agents_router.get("/{ref}")
async def get_agent(ref: str, user: dict = Depends(get_current_user)):
    a = await db.ai_agents.find_one({"org_id": user["org_id"], "ref": ref}, {"_id": 0})
    if not a:
        raise HTTPException(404, "Agent not found")
    a["tool_violations"] = _tool_violations(a)
    return a


class AgentCreate(BaseModel):
    name: str
    owner: str
    model: str
    tools: list[str] = []
    permissions: list[str] = []
    risk_class: str = "Medium"


@agents_router.post("")
async def create_agent(body: AgentCreate, admin: dict = Depends(require_roles("admin"))):
    existing = await db.ai_agents.find({"org_id": admin["org_id"]}, {"ref": 1, "_id": 0}).to_list(500)
    max_n = max((int(a["ref"].split("-")[1]) for a in existing if a.get("ref", "").startswith("AGT-")), default=0)
    ref = f"AGT-{max_n + 1:03d}"
    doc = {"org_id": admin["org_id"], "ref": ref, **body.model_dump(), "status": "shadow",
           "guardrails": {"input_filtering": False, "output_filtering": False, "tool_allowlist": False, "human_in_loop": False},
           "last_redteam": None}
    await db.ai_agents.insert_one(doc)
    await _log_audit(admin["org_id"], admin["email"], "agent.register", f"Registered {ref} {body.name}")
    doc.pop("_id", None)
    return doc


class GuardrailBody(BaseModel):
    input_filtering: bool | None = None
    output_filtering: bool | None = None
    tool_allowlist: bool | None = None
    human_in_loop: bool | None = None
    status: str | None = None


@agents_router.patch("/{ref}")
async def update_agent(ref: str, body: GuardrailBody, admin: dict = Depends(require_roles("admin"))):
    a = await db.ai_agents.find_one({"org_id": admin["org_id"], "ref": ref})
    if not a:
        raise HTTPException(404, "Agent not found")
    guard = a["guardrails"]
    for k in ("input_filtering", "output_filtering", "tool_allowlist", "human_in_loop"):
        v = getattr(body, k)
        if v is not None:
            guard[k] = v
    updates = {"guardrails": guard}
    if body.status:
        updates["status"] = body.status
    await db.ai_agents.update_one({"_id": a["_id"]}, {"$set": updates})
    return await db.ai_agents.find_one({"org_id": admin["org_id"], "ref": ref}, {"_id": 0})


@agents_router.post("/{ref}/redteam")
async def redteam(ref: str, admin: dict = Depends(require_roles("admin"))):
    a = await db.ai_agents.find_one({"org_id": admin["org_id"], "ref": ref})
    if not a:
        raise HTTPException(404, "Agent not found")
    guard = a["guardrails"]
    findings = []
    for p in REDTEAM_PROBES:
        defended = bool(guard.get(p["guard"]))
        findings.append({**{k: p[k] for k in ("id", "name", "category", "severity")}, "defended": defended})
    passed = sum(1 for f in findings if f["defended"])
    score = round(passed / len(findings) * 100)
    result = {"ref": ref, "score": score, "passed": passed, "total": len(findings),
              "findings": findings, "run_at": _now(), "evaluation": "heuristic (MOCKED)"}
    await db.ai_agents.update_one({"_id": a["_id"]}, {"$set": {"last_redteam": result}})
    await _log_audit(admin["org_id"], admin["email"], "agent.redteam", f"{ref} scored {score}%")
    # Compose kernel: open remediation + notify for each critical failure
    crit_fails = [f for f in findings if not f["defended"] and f["severity"] == "Critical"]
    if crit_fails:
        await workflows.start_remediation(admin["org_id"], ref, f"Harden {a['name']} ({ref})")
        await notifications.create(
            admin["org_id"], "agent_risk", f"Red-team flagged {ref}",
            f"{a['name']} failed {len(crit_fails)} critical probe(s): {', '.join(f['id'] for f in crit_fails)}. Score {score}%.",
            ref=ref, dedupe_key=f"redteam:{ref}:{score}")
    return result


# ---- Runtime enforcement (Kill Switch connector) ----
ENFORCE_MAP = {
    "suspend": {"status": "restricted", "mode": "restrict", "verb": "suspended"},
    "kill": {"status": "killed", "mode": "block", "verb": "killed"},
    "resume": {"status": "sanctioned", "mode": "observe", "verb": "resumed"},
}


class EnforceBody(BaseModel):
    action: str  # suspend | kill | resume


async def _dispatch_webhook(webhook, secret, payload, attempts=3):
    """POST an enforcement event to the agent-runtime webhook. Signs the body with HMAC-SHA256 when a
    shared secret is configured (X-Obserra-Signature: sha256=<hex> over '<ts>.' + raw body) and retries a
    few times on failure / non-2xx. Returns a receipt {ok,status_code,latency_ms,response,error,attempts,signed}."""
    import httpx, time as _time, json as _json, hmac, hashlib, asyncio
    raw = _json.dumps(payload, separators=(",", ":"), default=str).encode()
    headers = {"Content-Type": "application/json"}
    if secret:
        ts = str(int(_time.time()))
        sig = hmac.new(secret.encode(), (ts + ".").encode() + raw, hashlib.sha256).hexdigest()
        headers["X-Obserra-Timestamp"] = ts
        headers["X-Obserra-Signature"] = f"sha256={sig}"
    last = {"status_code": None, "response": "", "error": "not attempted", "ok": False}
    tried, t0 = 0, _time.perf_counter()
    for i in range(max(1, attempts)):
        tried = i + 1
        try:
            async with httpx.AsyncClient(timeout=10) as c:
                r = await c.post(webhook, content=raw, headers=headers)
            ok = 200 <= r.status_code < 300
            last = {"status_code": r.status_code, "response": (r.text or "")[:280], "error": None, "ok": ok}
            if ok:
                break
        except Exception as e:
            last = {"status_code": None, "response": "", "error": str(e)[:200], "ok": False}
        if i < attempts - 1:
            await asyncio.sleep(0.6 * (i + 1))
    return {"ok": bool(last["ok"]), "status_code": last["status_code"],
            "latency_ms": round((_time.perf_counter() - t0) * 1000),
            "response": last.get("response", ""), "error": last.get("error"),
            "attempts": tried, "signed": bool(secret), "at": _now(), "url": webhook}


async def _do_enforce(org_id, actor, ref, action, source="manual"):
    """Shared runtime enforcement — flips the agent runtime status (suspend/kill/resume), records the
    action to the Defensibility Ledger and alerts Slack/Teams. If an external agent-runtime webhook is
    configured on the org it also dispatches the enforcement command there (best-effort). Reused by the
    single enforce endpoint, the bulk 'Neutralise' action and the Obserrian Advisor."""
    from bson import ObjectId
    import httpx
    m = ENFORCE_MAP.get((action or "").lower())
    if not m:
        raise HTTPException(400, "Unknown enforcement action")
    a = await db.ai_agents.find_one({"org_id": org_id, "ref": ref})
    if not a:
        raise HTTPException(404, "Agent not found")
    org = await db.organizations.find_one({"_id": ObjectId(org_id)}) or {}
    webhook = org.get("agent_runtime_webhook")
    enforced = action != "resume"
    external_ok, runtime, receipt, runtime_unreachable = None, "obserra-control-plane", None, False
    if webhook:
        runtime = "external-webhook"
        receipt = await _dispatch_webhook(
            webhook, org.get("agent_runtime_webhook_secret"),
            {"agent_ref": ref, "action": action, "mode": m["mode"], "org_id": org_id})
        external_ok = receipt["ok"]
        runtime_unreachable = (not external_ok) and action != "resume"
    note = ("Enforcement dispatched to the connected agent-runtime webhook." if webhook
            else "Enforced in the Obserra control plane — the agent governance status changed and every "
                 "downstream policy check now honours it. Wire an agent-runtime webhook to push this to an "
                 "external execution environment.")
    enforcement = {"enforced": enforced, "mode": m["mode"], "action": action,
                   "runtime": runtime, "external_ok": external_ok, "note": note,
                   "receipt": receipt, "runtime_unreachable": runtime_unreachable,
                   "at": _now(), "by": actor, "source": source}
    await db.ai_agents.update_one({"_id": a["_id"]},
        {"$set": {"status": m["status"], "enforced": enforced, "enforcement": enforcement,
                  "runtime_unreachable": runtime_unreachable}})
    await _log_audit(org_id, actor, "agent.enforce",
                     f"{ref} {m['verb']} (mode {m['mode']}, via {source})")
    try:
        await db.agent_enforcements.insert_one({
            "org_id": org_id, "ref": ref, "name": a.get("name"), "action": action,
            "verb": m["verb"], "mode": m["mode"], "status": m["status"], "source": source,
            "by": actor, "runtime": runtime, "external_ok": external_ok, "receipt": receipt,
            "runtime_unreachable": runtime_unreachable, "at": enforcement["at"]})
    except Exception:
        pass
    try:
        from risk_engine import _ledger
        await _ledger(org_id, {
            "action": "agent-enforce", "task_id": ref, "by": actor,
            "provider": runtime, "verified": bool(external_ok) if webhook else True,
            "status": m["status"], "message": f"{a['name']} ({ref}) {m['verb']} — {note}",
            "external": {"webhook": bool(webhook), "external_ok": external_ok, "mode": m["mode"]},
            "started_at": _now(), "finished_at": _now()})
    except Exception:
        pass
    try:
        from self_scan import _post_chat_alert
        emoji = "🛑" if action == "kill" else "⏸" if action == "suspend" else "▶"
        await _post_chat_alert(org_id, f"{emoji} AI agent {m['verb']}: {a['name']} ({ref})",
                               f"Runtime enforcement '{action}' applied (mode {m['mode']}). {note}")
    except Exception:
        pass
    updated = await db.ai_agents.find_one({"org_id": org_id, "ref": ref}, {"_id": 0})
    updated["tool_violations"] = _tool_violations(updated)
    return {"ok": True, "agent": updated, "enforcement": enforcement}


@agents_router.post("/{ref}/enforce")
async def enforce_agent(ref: str, body: EnforceBody, admin: dict = Depends(require_roles("admin"))):
    """Runtime enforcement connector — see _do_enforce."""
    return await _do_enforce(admin["org_id"], admin["email"], ref, body.action, source="manual")


async def enforce_from_advisor(org_id, actor, ref, action):
    """Enforce an agent from the Obserrian Advisor chat (called by routes /actions/run)."""
    return await _do_enforce(org_id, actor, ref, action, source="advisor")


# ---- Agent runtime connector (enforcement webhook) ----
class WebhookBody(BaseModel):
    webhook: str = ""
    secret: str | None = None


@agents_router.get("/runtime/webhook")
async def get_runtime_webhook(user: dict = Depends(get_current_user)):
    from bson import ObjectId
    org = await db.organizations.find_one(
        {"_id": ObjectId(user["org_id"])}, {"agent_runtime_webhook": 1, "agent_runtime_webhook_secret": 1}) or {}
    return {"webhook": org.get("agent_runtime_webhook") or "",
            "secret_set": bool(org.get("agent_runtime_webhook_secret"))}


@agents_router.put("/runtime/webhook")
async def set_runtime_webhook(body: WebhookBody, admin: dict = Depends(require_roles("admin"))):
    from bson import ObjectId
    url = (body.webhook or "").strip()
    if url and not url.lower().startswith(("http://", "https://")):
        raise HTTPException(400, "Webhook must be a valid http(s) URL.")
    update = {"agent_runtime_webhook": url}
    if body.secret is not None:
        update["agent_runtime_webhook_secret"] = body.secret.strip()
    await db.organizations.update_one({"_id": ObjectId(admin["org_id"])}, {"$set": update})
    org = await db.organizations.find_one({"_id": ObjectId(admin["org_id"])},
                                          {"agent_runtime_webhook_secret": 1}) or {}
    await _log_audit(admin["org_id"], admin["email"], "agent.runtime_webhook",
                     "Set agent runtime webhook" if url else "Cleared agent runtime webhook")
    return {"webhook": url, "secret_set": bool(org.get("agent_runtime_webhook_secret"))}


@agents_router.post("/runtime/webhook/test")
async def test_runtime_webhook(admin: dict = Depends(require_roles("admin"))):
    """Send a synthetic 'test' event to the configured agent-runtime webhook (signed + retried) so an
    admin can confirm their execution environment actually receives Obserra enforcement."""
    from bson import ObjectId
    org = await db.organizations.find_one({"_id": ObjectId(admin["org_id"])},
                                          {"agent_runtime_webhook": 1, "agent_runtime_webhook_secret": 1}) or {}
    webhook = org.get("agent_runtime_webhook")
    if not webhook:
        raise HTTPException(400, "No agent runtime webhook configured. Save a webhook URL first.")
    receipt = await _dispatch_webhook(
        webhook, org.get("agent_runtime_webhook_secret"),
        {"agent_ref": "TEST-PING", "action": "test", "mode": "noop", "org_id": admin["org_id"],
         "event": "obserra.runtime.test", "at": _now()}, attempts=2)
    await _log_audit(admin["org_id"], admin["email"], "agent.runtime_webhook_test",
                     f"Test event → {receipt['status_code'] or 'no response'} "
                     f"({receipt['latency_ms']}ms, {receipt['attempts']} try)")
    return receipt


# ---- Built-in Live Enforcement Simulator ----
# A first-party agent-runtime endpoint Obserra hosts for itself so an admin can prove the FULL
# signed-webhook enforcement path end-to-end (real HTTP round-trip through the ingress + HMAC
# verification + receipt) without standing up a customer runtime. Enabling it points the org's
# agent_runtime_webhook at this app's own public inbound URL with a generated signing secret.
def _simulator_inbound_url(token: str) -> str:
    import os
    base = os.environ.get("FRONTEND_URL", "").rstrip("/")
    return f"{base}/api/agents/runtime/simulator/inbound/{token}" if token else ""


async def _simulator_status(org_id):
    from bson import ObjectId
    org = await db.organizations.find_one({"_id": ObjectId(org_id)}) or {}
    token = org.get("runtime_simulator_token")
    url = _simulator_inbound_url(token)
    events = await db.runtime_simulator_events.find({"org_id": org_id}, {"_id": 0}).sort("at", -1).to_list(50)
    received = await db.runtime_simulator_events.count_documents({"org_id": org_id})
    verified = await db.runtime_simulator_events.count_documents({"org_id": org_id, "signature_valid": True})
    return {"enabled": bool(org.get("runtime_simulator_enabled")), "url": url,
            "active": bool(token and org.get("agent_runtime_webhook") == url),
            "signed": bool(org.get("runtime_simulator_secret")),
            "received": received, "verified": verified, "events": events}


@agents_router.get("/runtime/simulator")
async def get_simulator(admin: dict = Depends(require_roles("admin"))):
    return await _simulator_status(admin["org_id"])


@agents_router.post("/runtime/simulator/enable")
async def enable_simulator(admin: dict = Depends(require_roles("admin"))):
    """Provision the built-in runtime simulator and wire the org's enforcement webhook to it (signed)."""
    import secrets as _secrets
    from bson import ObjectId
    org = await db.organizations.find_one({"_id": ObjectId(admin["org_id"])}) or {}
    token = org.get("runtime_simulator_token") or _secrets.token_urlsafe(10)
    secret = org.get("runtime_simulator_secret") or _secrets.token_urlsafe(24)
    url = _simulator_inbound_url(token)
    await db.organizations.update_one({"_id": ObjectId(admin["org_id"])}, {"$set": {
        "runtime_simulator_token": token, "runtime_simulator_secret": secret,
        "runtime_simulator_enabled": True, "agent_runtime_webhook": url,
        "agent_runtime_webhook_secret": secret, "agent_runtime_webhook_managed": "simulator"}})
    await _log_audit(admin["org_id"], admin["email"], "agent.runtime_simulator",
                     "Enabled the built-in live enforcement simulator")
    return await _simulator_status(admin["org_id"])


@agents_router.post("/runtime/simulator/disable")
async def disable_simulator(admin: dict = Depends(require_roles("admin"))):
    from bson import ObjectId
    org = await db.organizations.find_one({"_id": ObjectId(admin["org_id"])}) or {}
    upd = {"runtime_simulator_enabled": False}
    if org.get("agent_runtime_webhook_managed") == "simulator":
        upd.update({"agent_runtime_webhook": "", "agent_runtime_webhook_secret": "",
                    "agent_runtime_webhook_managed": None})
    await db.organizations.update_one({"_id": ObjectId(admin["org_id"])}, {"$set": upd})
    await _log_audit(admin["org_id"], admin["email"], "agent.runtime_simulator",
                     "Disabled the built-in live enforcement simulator")
    return await _simulator_status(admin["org_id"])


@agents_router.post("/runtime/simulator/clear")
async def clear_simulator_events(admin: dict = Depends(require_roles("admin"))):
    await db.runtime_simulator_events.delete_many({"org_id": admin["org_id"]})
    return await _simulator_status(admin["org_id"])


@agents_router.post("/runtime/simulator/inbound/{token}")
async def simulator_inbound(token: str, request: Request):
    """PUBLIC agent-runtime receiver — verifies the HMAC signature Obserra dispatched, records the
    enforcement event and returns a runtime receipt. This is the far end of the signed webhook."""
    import hmac, hashlib, json as _json
    from datetime import datetime, timezone
    raw = await request.body()
    org = await db.organizations.find_one({"runtime_simulator_token": token})
    if not org:
        raise HTTPException(404, "Unknown simulator token")
    secret = org.get("runtime_simulator_secret") or ""
    sig = request.headers.get("X-Obserra-Signature", "")
    ts = request.headers.get("X-Obserra-Timestamp", "")
    verified = False
    if secret and sig.startswith("sha256="):
        try:
            expected = hmac.new(secret.encode(), (ts + ".").encode() + raw, hashlib.sha256).hexdigest()
            verified = hmac.compare_digest(expected, sig.split("=", 1)[1])
        except Exception:
            verified = False
    try:
        body = _json.loads(raw.decode() or "{}")
    except Exception:
        body = {}
    now = datetime.now(timezone.utc).isoformat()
    await db.runtime_simulator_events.insert_one({
        "org_id": str(org["_id"]), "token": token, "agent_ref": body.get("agent_ref"),
        "action": body.get("action"), "mode": body.get("mode"), "event": body.get("event"),
        "signed": bool(sig), "signature_valid": verified, "at": now, "body": body})
    try:
        old = await db.runtime_simulator_events.find(
            {"org_id": str(org["_id"])}, {"_id": 1}).sort("at", -1).skip(200).to_list(1000)
        if old:
            await db.runtime_simulator_events.delete_many({"_id": {"$in": [o["_id"] for o in old]}})
    except Exception:
        pass
    return {"ok": True, "received": True, "runtime": "obserra-simulator",
            "agent_ref": body.get("agent_ref"), "action": body.get("action"), "verified": verified}


# ---- Kill Replay Drill (proof-of-control fire-drill) ----
async def _email_fire_drill(org_id, drill):
    from bson import ObjectId
    org = await db.organizations.find_one({"_id": ObjectId(org_id)}) or {}
    recips = org.get("board_digest_recipients") or []
    if not recips:
        recips = [u["email"] for u in await db.users.find(
            {"org_id": org_id, "role": {"$in": ["admin", "executive"]}}, {"_id": 0, "email": 1}).to_list(200) if u.get("email")]
    if not recips:
        return
    controlled = drill.get("controlled")
    color = "#16a34a" if controlled else "#dc2626"
    verdict = "CONTROL CONFIRMED" if controlled else "CONTROL NOT CONFIRMED"
    sr = drill.get("suspend_receipt") or {}
    runtime = "built-in simulator" if drill.get("runtime") == "obserra-simulator" else (
        "external agent runtime" if drill.get("runtime") == "external-webhook" else "internal control plane")
    html = (
        f"<div style='font-family:Arial;max-width:600px'>"
        f"<div style='background:#0f1e3d;padding:18px 22px;border-radius:10px 10px 0 0'>"
        f"<div style='color:#12b4d6;font:700 12px Arial;letter-spacing:2px'>OBSERRA · PROOF OF CONTROL</div>"
        f"<div style='color:#fff;font:800 20px Arial;margin-top:4px'>AI Kill-Switch Fire-Drill</div></div>"
        f"<div style='border:1px solid #e5e7eb;border-top:none;padding:22px;border-radius:0 0 10px 10px'>"
        f"<div style='display:inline-block;background:{color};color:#fff;font:800 13px Arial;padding:6px 14px;border-radius:999px'>{verdict}</div>"
        f"<p style='font:400 14px Arial;color:#374151;margin:16px 0'>On {drill.get('at','')[:16].replace('T',' ')} UTC, Obserra fired a live "
        f"<strong>Suspend → Resume</strong> replay against <strong>{drill.get('agent_name')}</strong> "
        f"(<code>{drill.get('agent_ref')}</code>) via the {runtime}.</p>"
        f"<table style='width:100%;border-collapse:collapse;font:400 13px Arial;color:#374151'>"
        f"<tr><td style='padding:6px 0;color:#6b7280'>Suspend dispatched in</td><td style='text-align:right;font-weight:700'>{drill.get('suspend_ms')} ms</td></tr>"
        f"<tr><td style='padding:6px 0;color:#6b7280'>Resume dispatched in</td><td style='text-align:right;font-weight:700'>{drill.get('resume_ms')} ms</td></tr>"
        f"<tr><td style='padding:6px 0;color:#6b7280'>Total drill time</td><td style='text-align:right;font-weight:700'>{drill.get('total_ms')} ms</td></tr>"
        f"<tr><td style='padding:6px 0;color:#6b7280'>Runtime response</td><td style='text-align:right;font-weight:700'>HTTP {sr.get('status_code') or '—'}</td></tr>"
        f"<tr><td style='padding:6px 0;color:#6b7280'>Signature</td><td style='text-align:right;font-weight:700'>{'HMAC-SHA256 signed' if drill.get('signed') else 'unsigned'}</td></tr>"
        f"</table>"
        f"<p style='font:400 12px Arial;color:#9ca3af;margin-top:16px'>This is an automated proof-of-control receipt — the agent was returned to its "
        f"prior state immediately after the drill. Recorded on the immutable Defensibility Ledger.</p></div></div>")
    subj = f"AI Kill-Switch Fire-Drill — {verdict} ({drill.get('agent_name')})"
    for em in recips:
        try:
            await notifications.send_email(em, subj, html)
        except Exception:
            pass


async def _run_fire_drill(org_id, actor, agent_ref, notify=True, scheduled=False):
    """Suspend then immediately resume an agent, timing each dispatch, to prove the kill-switch fires live."""
    import time as _time
    a = await db.ai_agents.find_one({"org_id": org_id, "ref": agent_ref})
    if not a:
        return {"ok": False, "error": "Agent not found"}
    started = _now()
    t0 = _time.perf_counter()
    suspend_res = await _do_enforce(org_id, actor, agent_ref, "suspend", source="fire-drill")
    t1 = _time.perf_counter()
    resume_res = await _do_enforce(org_id, actor, agent_ref, "resume", source="fire-drill")
    t2 = _time.perf_counter()
    enf_s = suspend_res.get("enforcement", suspend_res) if isinstance(suspend_res, dict) else {}
    enf_r = resume_res.get("enforcement", resume_res) if isinstance(resume_res, dict) else {}
    sr = (enf_s or {}).get("receipt") or {}
    rr = (enf_r or {}).get("receipt") or {}
    runtime = (enf_s or {}).get("runtime")
    controlled = bool((enf_s or {}).get("external_ok")) if runtime in ("external-webhook", "obserra-simulator") else True
    drill = {
        "org_id": org_id, "agent_ref": agent_ref, "agent_name": a.get("name"), "by": actor,
        "scheduled": scheduled, "at": started if isinstance(started, str) else str(started),
        "suspend_ms": round((t1 - t0) * 1000), "resume_ms": round((t2 - t1) * 1000),
        "total_ms": round((t2 - t0) * 1000), "runtime": runtime, "controlled": controlled,
        "suspend_receipt": sr, "resume_receipt": rr,
        "signed": bool(sr.get("signed")), "signature_ok": bool(sr.get("ok"))}
    await db.fire_drills.insert_one(dict(drill))
    await _log_audit(org_id, actor, "agent.fire_drill",
                     f"Kill-replay drill on {agent_ref} ({'control confirmed' if controlled else 'runtime unreachable'})")
    # Auto-post the proof-of-control receipt to the org's Slack / Teams governance channel (best-effort)
    try:
        from self_scan import _post_chat_alert
        verdict = "\u2705 CONTROL CONFIRMED" if controlled else "\u26a0\ufe0f CONTROL NOT CONFIRMED"
        await _post_chat_alert(
            org_id, f"AI Kill-Switch Fire-Drill \u2014 {verdict}",
            f"Agent *{a.get('name')}* ({agent_ref}) \u00b7 suspend {drill['suspend_ms']}ms \u00b7 resume {drill['resume_ms']}ms \u00b7 "
            f"{'signed HMAC receipt' if drill['signed'] else 'unsigned'} \u00b7 {'scheduled drill' if scheduled else 'manual drill'}.")
    except Exception:
        pass
    if notify:
        await _email_fire_drill(org_id, drill)
    return {"ok": True, "drill": drill}


class FireDrillBody(BaseModel):
    agent_ref: str
    notify: bool = True


@agents_router.post("/runtime/fire-drill")
async def run_fire_drill(body: FireDrillBody, admin: dict = Depends(require_roles("admin"))):
    if not (body.agent_ref or "").strip():
        raise HTTPException(400, "Pick an agent to run the fire-drill against.")
    res = await _run_fire_drill(admin["org_id"], admin["email"], body.agent_ref.strip(), notify=body.notify)
    if not res.get("ok"):
        raise HTTPException(404, res.get("error") or "Fire-drill failed.")
    return res


@agents_router.get("/runtime/fire-drills")
async def list_fire_drills(admin: dict = Depends(require_roles("admin"))):
    rows = await db.fire_drills.find({"org_id": admin["org_id"]}, {"_id": 0}).sort("at", -1).to_list(50)
    return {"drills": rows}


async def _compute_control_assurance(org_id):
    """Kill-switch reliability rollup — monthly proof-of-control pass rate + response times from fire-drills, plus SLA state."""
    from datetime import datetime, timezone
    from bson import ObjectId
    drills = await db.fire_drills.find({"org_id": org_id}, {"_id": 0}).sort("at", -1).to_list(1000)
    now = datetime.now(timezone.utc)
    yy, mm, keys = now.year, now.month, []
    for _ in range(6):
        keys.append((yy, mm)); mm -= 1
        if mm == 0:
            mm = 12; yy -= 1
    keys = keys[::-1]
    b = {f"{a:04d}-{c:02d}": {"drills": 0, "controlled": 0, "sus": [], "res": []} for (a, c) in keys}
    for d in drills:
        k = (d.get("at") or "")[:7]
        if k in b:
            b[k]["drills"] += 1
            if d.get("controlled"):
                b[k]["controlled"] += 1
            if d.get("suspend_ms") is not None:
                b[k]["sus"].append(d["suspend_ms"])
            if d.get("resume_ms") is not None:
                b[k]["res"].append(d["resume_ms"])
    monthly = []
    for (a, c) in keys:
        key = f"{a:04d}-{c:02d}"
        v = b[key]
        monthly.append({
            "month": f"{c:02d}/{str(a)[2:]}", "key": key, "drills": v["drills"], "controlled": v["controlled"],
            "pass_rate": round(100 * v["controlled"] / v["drills"]) if v["drills"] else None,
            "avg_suspend_ms": round(sum(v["sus"]) / len(v["sus"])) if v["sus"] else None,
            "avg_resume_ms": round(sum(v["res"]) / len(v["res"])) if v["res"] else None})
    total = len(drills)
    controlled = sum(1 for d in drills if d.get("controlled"))
    all_sus = [d["suspend_ms"] for d in drills if d.get("suspend_ms") is not None]
    all_res = [d["resume_ms"] for d in drills if d.get("resume_ms") is not None]
    streak = 0
    for d in drills:
        if d.get("controlled"):
            streak += 1
        else:
            break
    org = await db.organizations.find_one(
        {"_id": ObjectId(org_id)}, {"control_assurance_sla_enabled": 1, "control_assurance_sla_min": 1}) or {}
    cur_key = f"{now.year:04d}-{now.month:02d}"
    cur = next((m for m in monthly if m["key"] == cur_key), None)
    sla_min = int(org.get("control_assurance_sla_min") or 90)
    sla_enabled = bool(org.get("control_assurance_sla_enabled", False))
    cur_rate = cur["pass_rate"] if cur else None
    breached = bool(sla_enabled and cur_rate is not None and cur_rate < sla_min)
    return {"monthly": monthly, "total": total, "controlled": controlled,
            "pass_rate": round(100 * controlled / total) if total else None, "streak": streak,
            "avg_suspend_ms": round(sum(all_sus) / len(all_sus)) if all_sus else None,
            "avg_resume_ms": round(sum(all_res) / len(all_res)) if all_res else None,
            "last_at": drills[0]["at"] if drills else None,
            "scheduled_count": sum(1 for d in drills if d.get("scheduled")),
            "sla": {"enabled": sla_enabled, "min": sla_min, "current_rate": cur_rate, "breached": breached},
            "recent": drills[:15]}


@agents_router.get("/runtime/control-assurance")
async def control_assurance(admin: dict = Depends(require_roles("admin"))):
    return await _compute_control_assurance(admin["org_id"])


@agents_router.get("/runtime/control-assurance-report.pdf")
async def control_assurance_report(admin: dict = Depends(require_roles("admin"))):
    """Board-ready, sealed Control Assurance report — the monthly kill-switch pass-rate trend as a branded PDF."""
    import json as _json, hashlib as _hl
    from io import BytesIO
    from datetime import datetime, timezone
    from fastapi.responses import StreamingResponse
    from reports import _build_pdf
    from agent_reports import _control_assurance_chart_page, _stamp_verified_seal
    from bson import ObjectId
    d = await _compute_control_assurance(admin["org_id"])
    org = await db.organizations.find_one({"_id": ObjectId(admin["org_id"])}, {"name": 1}) or {}
    now = datetime.now(timezone.utc)
    EMD = "\u2014"
    prtxt = EMD if d["pass_rate"] is None else f"{d['pass_rate']}%"
    lines = ["## Kill-Switch Control Assurance",
             f"Generated {now.strftime('%B %d, %Y %H:%M UTC')} \u00b7 proof-of-control pass rate {prtxt} across {d['total']} fire-drill(s) "
             f"\u00b7 current confirmed streak {d['streak']}.",
             f"Average enforcement dispatch: suspend {d['avg_suspend_ms'] or EMD} ms, resume {d['avg_resume_ms'] or EMD} ms.", ""]
    if d["sla"]["enabled"]:
        cr = "\u2014" if d["sla"]["current_rate"] is None else f"{d['sla']['current_rate']}%"
        lines += [f"SLA: minimum {d['sla']['min']}% \u2014 this month {cr} ({'BREACHED' if d['sla']['breached'] else 'within SLA'}).", ""]
    lines.append("## Monthly pass rate")
    for m in d["monthly"]:
        row = "no drills" if m["pass_rate"] is None else f"{m['pass_rate']}% ({m['controlled']}/{m['drills']})"
        if m["avg_suspend_ms"] is not None:
            row += f" \u00b7 suspend {m['avg_suspend_ms']}ms \u00b7 resume {m['avg_resume_ms']}ms"
        lines.append(f"{m['month']}: {row}")
    lines += ["", "## Recent fire-drills"]
    for r in d["recent"][:12]:
        lines.append(f"{(r.get('at') or '')[:16].replace('T', ' ')} \u2014 {r.get('agent_name')} ({r.get('agent_ref')}): "
                     f"{'CONTROL CONFIRMED' if r.get('controlled') else 'NOT CONFIRMED'} \u00b7 suspend {r.get('suspend_ms')}ms "
                     f"\u00b7 resume {r.get('resume_ms')}ms \u00b7 {'signed' if r.get('signed') else 'unsigned'}")
    seal = _hl.sha256(_json.dumps(d, sort_keys=True, default=str).encode()).hexdigest()
    buf = _build_pdf("\n".join(lines), "Control Assurance Report", cover=True, org_name=org.get("name"),
                     exec_summary=f"Kill-switch reliability {prtxt} over {d['total']} fire-drill(s) \u2014 "
                                  f"{d['controlled']} control-confirmed, current streak {d['streak']}.")
    pdf = buf.getvalue()
    page = _control_assurance_chart_page(d["monthly"])
    if page:
        from pypdf import PdfReader, PdfWriter
        w = PdfWriter()
        for p in PdfReader(BytesIO(pdf)).pages:
            w.add_page(p)
        for p in PdfReader(BytesIO(page)).pages:
            w.add_page(p)
        o = BytesIO(); w.write(o); pdf = o.getvalue()
    pdf = _stamp_verified_seal(pdf, seal)
    stamp = now.strftime("%Y%m%d-%H%M")
    return StreamingResponse(BytesIO(pdf), media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="obserra-control-assurance-{stamp}.pdf"'})


async def _run_scheduled_fire_drills():
    """Daily cron: orgs with fire_drill_enabled get one kill-replay drill on their configured day-of-month."""
    import calendar
    now = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
    ym = now.strftime("%Y-%m")
    orgs = await db.organizations.find({"fire_drill_enabled": True}).to_list(1000)
    for org in orgs:
        try:
            oid = str(org["_id"])
            day = min(int(org.get("fire_drill_day") or 1), calendar.monthrange(now.year, now.month)[1])
            if now.day != day or org.get("fire_drill_last_run") == ym:
                continue
            ref = org.get("fire_drill_agent_ref")
            if not ref:
                a = await db.ai_agents.find_one({"org_id": oid, "status": {"$ne": "killed"}}, {"ref": 1})
                ref = a and a.get("ref")
            if not ref:
                continue
            await _run_fire_drill(oid, "cron:fire-drill", ref, notify=True, scheduled=True)
            await db.organizations.update_one({"_id": org["_id"]}, {"$set": {"fire_drill_last_run": ym}})
        except Exception:
            pass


async def _run_control_assurance_sla_check():
    """Daily cron: alert (chat + email) once per month if this month's kill-switch pass rate dips below the org's SLA."""
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    ym = now.strftime("%Y-%m")
    orgs = await db.organizations.find({"control_assurance_sla_enabled": True}).to_list(1000)
    for org in orgs:
        try:
            oid = str(org["_id"])
            if org.get("control_assurance_sla_last_alert") == ym:
                continue
            d = await _compute_control_assurance(oid)
            if not d["sla"]["breached"]:
                continue
            rate, mn = d["sla"]["current_rate"], d["sla"]["min"]
            title = f"\u26a0\ufe0f Control Assurance SLA breach \u2014 {rate}% (min {mn}%)"
            body = (f"This month's kill-switch proof-of-control pass rate is {rate}%, below the {mn}% SLA. "
                    f"Run a fire-drill and check agent-runtime connectivity.")
            try:
                from self_scan import _post_chat_alert
                await _post_chat_alert(oid, title, body)
            except Exception:
                pass
            recips = org.get("board_digest_recipients") or [
                u["email"] for u in await db.users.find(
                    {"org_id": oid, "role": {"$in": ["admin", "executive"]}}, {"_id": 0, "email": 1}).to_list(200) if u.get("email")]
            html = (f"<div style='font-family:Arial;max-width:560px'><h2 style='color:#dc2626'>Control Assurance SLA breach</h2>"
                    f"<p style='font:400 14px Arial;color:#374151'>{body}</p></div>")
            for em in recips:
                try:
                    await notifications.send_email(em, title, html)
                except Exception:
                    pass
            await db.organizations.update_one({"_id": org["_id"]}, {"$set": {"control_assurance_sla_last_alert": ym}})
        except Exception:
            pass


# ---- Board Proof-of-Control (fresh signed receipt + sealed evidence pack → one auditor link) ----
@agents_router.post("/runtime/proof-of-control")
async def proof_of_control(admin: dict = Depends(require_roles("admin"))):
    import os, secrets
    from datetime import datetime, timezone, timedelta
    from bson import ObjectId
    org = await db.organizations.find_one({"_id": ObjectId(admin["org_id"])}) or {}
    webhook = org.get("agent_runtime_webhook")
    if not webhook:
        raise HTTPException(400, "No runtime connected. Enable the Live Enforcement Simulator or wire an agent-runtime webhook first.")
    receipt = await _dispatch_webhook(
        webhook, org.get("agent_runtime_webhook_secret"),
        {"agent_ref": "PROOF-OF-CONTROL", "action": "test", "mode": "noop", "org_id": admin["org_id"],
         "event": "obserra.runtime.proof", "at": _now()}, attempts=2)
    snap = await _evidence_snapshot(admin["org_id"])
    managed = org.get("agent_runtime_webhook_managed") == "simulator"
    ok = bool(receipt.get("ok"))
    extra_md = "\n".join([
        "## Proof of Control — Live Kill-Switch Receipt",
        f"At {_now()} Obserra dispatched a signed enforcement command to the connected agent runtime "
        f"({'built-in enforcement simulator' if managed else 'external agent-runtime webhook'}) and received a "
        f"{'verified' if ok else 'FAILED'} response — demonstrating that the kill-switch actually fires.",
        f"Runtime response: HTTP {receipt.get('status_code') or 'no response'}",
        f"Round-trip latency: {receipt.get('latency_ms')} ms",
        f"Signature: {'HMAC-SHA256 signed' if receipt.get('signed') else 'unsigned'}",
        f"Delivery attempts: {receipt.get('attempts')}", ""])
    token = secrets.token_urlsafe(16)
    now = datetime.now(timezone.utc)
    expires = (now + timedelta(days=14)).isoformat()
    snap_hash = _canonical_snapshot_hash(snap)
    await db.evidence_rooms.insert_one({
        "token": token, "org_id": admin["org_id"], "snapshot": snap, "snapshot_sha256": snap_hash,
        "extra_md": extra_md, "proof_of_control": receipt, "kind": "proof-of-control",
        "created_at": now.isoformat(), "created_by": admin["email"], "expires_at": expires, "opens": 0})
    await _log_audit(admin["org_id"], admin["email"], "agent.proof_of_control",
                     f"Board Proof-of-Control link created (runtime {'confirmed' if ok else 'unreachable'})")
    frontend = os.environ.get("FRONTEND_URL", "").rstrip("/")
    return {"token": token, "url": f"{frontend}/audit-room/{token}", "expires_at": expires,
            "receipt": receipt, "controlled": ok}


@agents_router.get("/runtime/enforcement-log")
async def enforcement_log(user: dict = Depends(get_current_user)):
    """Live feed of every runtime enforcement (suspend / kill / resume) — who, when, which agent,
    via advisor / bulk-neutralise / manual, and the runtime receipt."""
    rows = await db.agent_enforcements.find({"org_id": user["org_id"]}, {"_id": 0}).sort("at", -1).to_list(50)
    return {"events": rows}


@agents_router.get("/runtime/enforcement-log/export")
async def export_enforcement_log(format: str = "csv", user: dict = Depends(get_current_user)):
    """Export the runtime enforcement (Kill) audit trail as CSV or a board / auditor PDF."""
    import io
    from datetime import datetime, timezone
    from fastapi.responses import StreamingResponse
    rows = await db.agent_enforcements.find({"org_id": user["org_id"]}, {"_id": 0}).sort("at", -1).to_list(1000)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M")
    if format == "pdf":
        from bson import ObjectId
        from reports import _build_pdf
        org = await db.organizations.find_one({"_id": ObjectId(user["org_id"])}, {"name": 1}) or {}
        lines = ["## Runtime Enforcement Audit Trail",
                 f"Generated {datetime.now(timezone.utc).strftime('%B %d, %Y %H:%M UTC')} · {len(rows)} enforcement event(s)", ""]
        for e in rows:
            rc = e.get("receipt") or {}
            runtime = ("runtime OK" if e.get("external_ok") else
                       ("runtime UNREACHABLE" if e.get("runtime") == "external-webhook" else "control-plane"))
            lines.append(f"## {e.get('name') or e.get('ref')} — {(e.get('verb') or e.get('action') or '').upper()}")
            lines += [f"When: {e.get('at')}", f"By: {e.get('by')} · via {e.get('source')}",
                      f"Agent: {e.get('ref')} · mode {e.get('mode')} · status {e.get('status')}",
                      "Runtime: " + runtime + (f" · HTTP {rc.get('status_code')} · {rc.get('latency_ms')}ms · "
                      f"{rc.get('attempts')} attempt(s) · {'signed' if rc.get('signed') else 'unsigned'}" if rc else ""), ""]
        buf = _build_pdf("\n".join(lines), "Runtime Enforcement Audit Trail", cover=True, org_name=org.get("name"))
        return StreamingResponse(buf, media_type="application/pdf",
                                 headers={"Content-Disposition": f'attachment; filename="obserra-enforcement-audit-{stamp}.pdf"'})
    import csv
    sbuf = io.StringIO()
    w = csv.writer(sbuf)
    w.writerow(["at", "agent_ref", "agent_name", "action", "status", "mode", "by", "source",
                "runtime", "external_ok", "http_status", "latency_ms", "attempts", "signed"])
    for e in rows:
        rc = e.get("receipt") or {}
        w.writerow([e.get("at"), e.get("ref"), e.get("name"), e.get("action"), e.get("status"),
                    e.get("mode"), e.get("by"), e.get("source"), e.get("runtime"), e.get("external_ok"),
                    rc.get("status_code"), rc.get("latency_ms"), rc.get("attempts"), rc.get("signed")])
    return StreamingResponse(io.BytesIO(sbuf.getvalue().encode()), media_type="text/csv",
                             headers={"Content-Disposition": f'attachment; filename="obserra-enforcement-audit-{stamp}.csv"'})


@agents_router.get("/runtime/evidence-pack.pdf")
async def evidence_pack(admin: dict = Depends(require_roles("admin"))):
    """One-tap auditor evidence pack — bundles the enforcement audit trail + runtime receipts + a live
    AI-agent toxicity snapshot into a single board-grade PDF an auditor can trust."""
    from datetime import datetime, timezone
    from bson import ObjectId
    from fastapi.responses import StreamingResponse
    from reports import _build_pdf
    org = await db.organizations.find_one(
        {"_id": ObjectId(admin["org_id"])},
        {"name": 1, "agent_runtime_webhook": 1, "agent_runtime_webhook_secret": 1}) or {}
    agents = await db.ai_agents.find({"org_id": admin["org_id"]}, {"_id": 0}).to_list(500)
    events = await db.agent_enforcements.find({"org_id": admin["org_id"]}, {"_id": 0}).sort("at", -1).to_list(1000)
    toxic = [a for a in agents if _is_toxic(a)]
    signed = "HMAC-signed" if org.get("agent_runtime_webhook_secret") else "unsigned"
    connector = f"connected ({signed})" if org.get("agent_runtime_webhook") else "control-plane only"
    lines = [
        "## Attestation",
        f"This evidence pack was generated by Obserra — Agentic AI Security Control & Governance for "
        f"{org.get('name') or 'the organization'} on {datetime.now(timezone.utc).strftime('%B %d, %Y at %H:%M UTC')}. "
        f"Runtime connector: {connector}. Every enforcement below carries a runtime receipt.", "",
        "## AI Agent Toxicity Snapshot",
        f"{len(agents)} governed agent(s) · {len(toxic)} with a toxic capability combination · "
        f"{sum(1 for a in agents if a.get('status') == 'killed')} killed · "
        f"{sum(1 for a in agents if a.get('status') == 'restricted')} restricted.", ""]
    for a in agents:
        tv = _tool_violations(a)
        lines.append(f"## {a.get('name')} ({a.get('ref')})")
        lines += [f"Status: {a.get('status')} · authority: {a.get('authority', '—')}",
                  "Toxic combination: " + (("YES — " + ", ".join(tv)) if tv else "none detected"), ""]
    lines += ["## Runtime Enforcement Audit Trail", f"{len(events)} enforcement event(s) recorded.", ""]
    for e in events:
        rc = e.get("receipt") or {}
        runtime = ("runtime OK" if e.get("external_ok") else
                   ("runtime UNREACHABLE" if e.get("runtime") == "external-webhook" else "control-plane"))
        lines.append(f"## {e.get('name') or e.get('ref')} — {(e.get('verb') or e.get('action') or '').upper()}")
        lines += [f"When: {e.get('at')} · by {e.get('by')} · via {e.get('source')}",
                  "Receipt: " + runtime + (f" · HTTP {rc.get('status_code')} · {rc.get('latency_ms')}ms · "
                  f"{rc.get('attempts')} attempt(s) · {'signed' if rc.get('signed') else 'unsigned'}" if rc else ""), ""]
    buf = _build_pdf("\n".join(lines), "AI Enforcement Evidence Pack", cover=True, org_name=org.get("name"),
                     exec_summary=(f"{len(agents)} governed agents, {len(toxic)} toxic; {len(events)} runtime "
                                   f"enforcement actions with verifiable receipts. Runtime connector: {connector}."))
    from io import BytesIO
    seal_src = {"org": org.get("name"),
                "agents": [{"ref": a.get("ref"), "status": a.get("status")} for a in agents],
                "events": len(events)}
    buf = BytesIO(_stamp_verified_seal(buf.getvalue(), _canonical_snapshot_hash(seal_src)))
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M")
    return StreamingResponse(buf, media_type="application/pdf",
                             headers={"Content-Disposition": f'attachment; filename="obserra-evidence-pack-{stamp}.pdf"'})


# ── Auditor room — shareable, expiring, read-only evidence pack (no login) ────
class EvidenceRoomBody(BaseModel):
    days: int = 14


@agents_router.post("/runtime/evidence-room")
async def create_evidence_room(body: EvidenceRoomBody, admin: dict = Depends(require_roles("admin"))):
    import os, secrets
    from datetime import datetime, timezone, timedelta
    snap = await _evidence_snapshot(admin["org_id"])
    token = secrets.token_urlsafe(16)
    days = max(1, min(90, int(body.days or 14)))
    now = datetime.now(timezone.utc)
    expires = (now + timedelta(days=days)).isoformat()
    snap_hash = _canonical_snapshot_hash(snap)
    await db.evidence_rooms.insert_one({"token": token, "org_id": admin["org_id"], "snapshot": snap,
        "snapshot_sha256": snap_hash,
        "created_at": now.isoformat(), "created_by": admin["email"], "expires_at": expires, "opens": 0})
    await _log_audit(admin["org_id"], admin["email"], "agent.evidence_room",
                     f"Read-only auditor room created (expires {expires[:10]})")
    frontend = os.environ.get("FRONTEND_URL", "").rstrip("/")
    return {"token": token, "url": f"{frontend}/audit-room/{token}", "expires_at": expires, "days": days}


@agents_router.get("/runtime/evidence-rooms")
async def list_evidence_rooms(admin: dict = Depends(require_roles("admin"))):
    import os
    from datetime import datetime, timezone, timedelta
    from bson import ObjectId
    frontend = os.environ.get("FRONTEND_URL", "").rstrip("/")
    now = datetime.now(timezone.utc)
    now_iso = now.isoformat()
    org = await db.organizations.find_one({"_id": ObjectId(admin["org_id"])}) or {}
    rooms = []
    async for d in db.evidence_rooms.find({"org_id": admin["org_id"]}).sort("created_at", -1):
        token = d["token"]
        snap = d.get("snapshot") or {}
        sagents = snap.get("agents") or []
        counts = snap.get("counts") or {}
        toxic_active = sum(1 for a in sagents if a.get("toxic") and a.get("status") not in ("killed", "restricted"))
        qs = await db.evidence_room_comments.find(
            {"token": token}, {"_id": 0, "status": 1, "at": 1, "priority": 1}).to_list(500)
        open_q = 0
        overdue_q = 0
        for q in qs:
            if q.get("status") == "Resolved":
                continue
            open_q += 1
            try:
                if q.get("at") and now > datetime.fromisoformat(q["at"]) + timedelta(hours=_sla_for(org, q.get("priority"))):
                    overdue_q += 1
            except Exception:
                pass
        expired = bool(d.get("expires_at") and now_iso > d["expires_at"])
        days_left = None
        try:
            if d.get("expires_at"):
                days_left = max(0, (datetime.fromisoformat(d["expires_at"]) - now).days)
        except Exception:
            days_left = None
        risk = min(100, toxic_active * 20 + overdue_q * 12 + max(0, open_q - overdue_q) * 4
                   + (10 if (days_left is not None and days_left <= 2 and not expired) else 0))
        rating = "Critical" if risk >= 80 else "High" if risk >= 60 else "Medium" if risk >= 40 else "Low"
        rooms.append({
            "token": token,
            "url": f"{frontend}/audit-room/{token}",
            "created_at": d.get("created_at"),
            "created_by": d.get("created_by"),
            "expires_at": d.get("expires_at"),
            "opens": d.get("opens", 0),
            "downloads": d.get("downloads", 0),
            "comments": len(qs),
            "expired": expired,
            "readiness": {
                "risk_score": risk, "rating": rating, "toxic_active": toxic_active,
                "open_questions": open_q, "overdue_questions": overdue_q, "days_left": days_left,
                "agents": counts.get("agents", len(sagents)), "killed": counts.get("killed", 0),
                "events": counts.get("events", 0), "org_name": snap.get("org_name"),
                "subscribers": len([e for e in (d.get("digest_subscribers") or []) if e]),
            },
        })
    return {"rooms": rooms}


class RoomRevokeBody(BaseModel):
    token: str


@agents_router.post("/runtime/evidence-room/revoke")
async def revoke_evidence_room(body: RoomRevokeBody, admin: dict = Depends(require_roles("admin"))):
    res = await db.evidence_rooms.delete_one({"token": body.token, "org_id": admin["org_id"]})
    if not res.deleted_count:
        raise HTTPException(404, "Auditor room not found.")
    await _log_audit(admin["org_id"], admin["email"], "agent.evidence_room_revoke",
                     f"Read-only auditor room revoked ({body.token[:8]}…)")
    return {"revoked": True}


@agents_router.get("/public/evidence-room/{token}")
async def public_evidence_room(token: str, request: Request = None):
    from datetime import datetime, timezone
    doc = await db.evidence_rooms.find_one({"token": token}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "This auditor room link is invalid.")
    if doc.get("expires_at") and datetime.now(timezone.utc).isoformat() > doc["expires_at"]:
        raise HTTPException(410, "This auditor room link has expired.")
    now = datetime.now(timezone.utc).isoformat()
    ip = ""
    try:
        ip = (request.headers.get("x-forwarded-for", "").split(",")[0].strip()
              or (request.client.host if request and request.client else ""))
    except Exception:
        ip = ""
    sha = doc.get("snapshot_sha256")
    if not sha:
        sha = _canonical_snapshot_hash(doc.get("snapshot") or {})
        await db.evidence_rooms.update_one({"token": token}, {"$set": {"snapshot_sha256": sha}})
    await db.evidence_rooms.update_one({"token": token},
        {"$inc": {"opens": 1}, "$set": {"last_opened_at": now}})
    await db.evidence_room_access.insert_one({"token": token, "org_id": doc.get("org_id"),
        "kind": "open", "who": None, "ip": ip, "at": now})
    import asyncio
    asyncio.create_task(_instant_suspicious_check(doc.get("org_id"), token, ip, "", "open", None, now))
    return {"snapshot": doc["snapshot"], "created_at": doc.get("created_at"),
            "expires_at": doc.get("expires_at"), "snapshot_sha256": sha,
            "digest_subscribed": bool(doc.get("digest_subscribers"))}


@agents_router.get("/public/evidence-room/{token}/pack.pdf")
async def public_evidence_room_pdf(token: str, who: str = "", request: Request = None):
    from datetime import datetime, timezone
    from fastapi.responses import StreamingResponse
    from reports import _build_pdf
    import io
    doc = await db.evidence_rooms.find_one({"token": token}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "This auditor room link is invalid.")
    if doc.get("expires_at") and datetime.now(timezone.utc).isoformat() > doc["expires_at"]:
        raise HTTPException(410, "This auditor room link has expired.")
    snap = doc["snapshot"]
    c = snap.get("counts", {})
    brand = None
    try:
        from bson import ObjectId as _OID
        from reports import _resolve_brand
        _org = await db.organizations.find_one({"_id": _OID(doc.get("org_id"))}) if doc.get("org_id") else None
        brand = _resolve_brand(_org)
    except Exception:
        brand = None
    _md = _evidence_markdown(snap)
    if doc.get("extra_md"):
        _md += "\n" + doc["extra_md"]
    buf = _build_pdf(_md, "AI Enforcement Evidence Pack", cover=True,
                     org_name=snap.get("org_name"), brand=brand,
                     exec_summary=f"{c.get('agents', 0)} governed agents, {c.get('toxic', 0)} toxic; "
                                  f"{c.get('events', 0)} runtime enforcement actions with verifiable receipts.")
    raw = buf.getvalue()
    try:
        _rows = await _room_access_geo(token, doc.get("org_id"))
        raw = _append_custody_map_page(raw, _rows)
    except Exception:
        pass
    seal = doc.get("snapshot_sha256") or _canonical_snapshot_hash(snap)
    # Tamper-evident provenance watermark — org logo + QR back to the live room + downloader stamp.
    try:
        import os as _os
        auditor = (who or "").strip()[:120] or "External auditor"
        access = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        room_url = f"{_os.environ.get('FRONTEND_URL', '').rstrip('/')}/audit-room/{token}"
        raw = await _brand_watermark_pdf(
            raw, org_id=doc.get("org_id"), room_url=room_url,
            subtext=f"Downloaded by {auditor} · {access} · link expires {(doc.get('expires_at') or '')[:10]}")
        raw = _stamp_verified_seal(raw, seal)
        ip = ""
        try:
            ip = (request.headers.get("x-forwarded-for", "").split(",")[0].strip()
                  or (request.client.host if request and request.client else ""))
        except Exception:
            ip = ""
        await db.evidence_rooms.update_one(
            {"token": token},
            {"$inc": {"downloads": 1},
             "$set": {"last_downloaded_at": datetime.now(timezone.utc).isoformat(), "last_downloaded_by": auditor}})
        _room_dl_now = datetime.now(timezone.utc).isoformat()
        await db.evidence_room_access.insert_one({"token": token, "org_id": doc.get("org_id"),
            "kind": "download", "who": auditor, "ip": ip, "at": _room_dl_now})
        import asyncio
        asyncio.create_task(_instant_suspicious_check(doc.get("org_id"), token, ip, "", "download", auditor, _room_dl_now))
    except Exception:
        pass
    return StreamingResponse(io.BytesIO(raw), media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="obserra-evidence-pack.pdf"'})


# ── Shareable card evidence — mint an expiring, watermarked auditor link for a single detail card ──
class CardShareBody(BaseModel):
    title: str = "Detail card"
    ref: str = ""
    kind: str = ""
    rating: str | None = None
    score: float | None = None
    ale: float | None = None
    compliance_pct: float | None = None
    connectors: list = []
    facets: list = []
    recommendations: list = []
    compliance_refs: list = []
    summary: str = ""
    days: int = 14


def _fmt_money(n):
    if n is None:
        return "\u2014"
    n = float(n)
    if n >= 1e6:
        return f"${n / 1e6:.2f}M"
    if n >= 1e3:
        return f"${round(n / 1e3)}k"
    return f"${round(n)}"


def _card_markdown(snap: dict) -> str:
    lines = []
    if snap.get("ref"):
        lines.append(f"**Reference:** {snap['ref']}")
    scoreline = []
    if snap.get("rating"):
        scoreline.append(f"{snap['rating']} risk")
    if snap.get("score") is not None:
        scoreline.append(f"score {snap['score']}/100")
    if snap.get("ale") is not None:
        scoreline.append(f"ALE {_fmt_money(snap['ale'])}")
    if scoreline:
        lines.append("**Risk & rating:** " + " \u00b7 ".join(scoreline))
    if snap.get("compliance_refs"):
        pct = f" ({snap['compliance_pct']}% area coverage)" if snap.get("compliance_pct") is not None else ""
        lines.append(f"**Compliance alignment{pct}:** " + ", ".join(str(c) for c in snap["compliance_refs"]))
    if snap.get("summary"):
        lines.append("## AI strategic brief")
        lines.append(snap["summary"])
    if snap.get("facets"):
        lines.append("## Details")
        for f in snap["facets"]:
            if isinstance(f, dict) and f.get("label"):
                lines.append(f"- **{f.get('label')}:** {f.get('value', '—')}")
    if snap.get("connectors"):
        lines.append("## Connectors & data sources")
        for c in snap["connectors"]:
            if isinstance(c, dict):
                extra = " \u00b7 ".join([str(x) for x in [c.get("detail"), c.get("status")] if x])
                lines.append(f"- {c.get('name', '')}" + (f" ({extra})" if extra else ""))
            else:
                lines.append(f"- {c}")
    if snap.get("recommendations"):
        lines.append("## Recommendations & fixes")
        for r in snap["recommendations"]:
            lines.append(f"- {r}")
    return "\n".join(lines)


@agents_router.post("/runtime/card-share")
async def create_card_share(body: CardShareBody, admin: dict = Depends(require_roles("admin"))):
    import os, secrets
    from datetime import datetime, timezone, timedelta
    from bson import ObjectId
    org = await db.organizations.find_one({"_id": ObjectId(admin["org_id"])}) or {}
    snap = {
        "title": body.title, "ref": body.ref, "kind": body.kind,
        "rating": body.rating, "score": body.score, "ale": body.ale,
        "compliance_pct": body.compliance_pct,
        "connectors": body.connectors or [], "facets": body.facets or [],
        "recommendations": body.recommendations or [], "compliance_refs": body.compliance_refs or [],
        "summary": body.summary or "", "org_name": org.get("name") or "Organization",
        "generated_at": _now(), "shared_by": admin["email"],
    }
    token = secrets.token_urlsafe(16)
    days = max(1, min(90, int(body.days or 14)))
    now = datetime.now(timezone.utc)
    expires = (now + timedelta(days=days)).isoformat()
    snap_hash = _canonical_snapshot_hash(snap)
    await db.card_shares.insert_one({
        "token": token, "org_id": admin["org_id"], "snapshot": snap, "snapshot_sha256": snap_hash,
        "created_at": now.isoformat(), "created_by": admin["email"], "expires_at": expires,
        "opens": 0, "downloads": 0})
    await _log_audit(admin["org_id"], admin["email"], "agent.card_share",
                     f"Detail card shared: {body.title} (expires {expires[:10]})")
    frontend = os.environ.get("FRONTEND_URL", "").rstrip("/")
    return {"token": token, "url": f"{frontend}/card/{token}", "expires_at": expires, "days": days}


@agents_router.get("/public/card-share/{token}")
async def public_card_share(token: str, request: Request = None):
    from datetime import datetime, timezone
    doc = await db.card_shares.find_one({"token": token}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "This shared card link is invalid.")
    if doc.get("expires_at") and datetime.now(timezone.utc).isoformat() > doc["expires_at"]:
        raise HTTPException(410, "This shared card link has expired.")
    now = datetime.now(timezone.utc).isoformat()
    sha = doc.get("snapshot_sha256") or _canonical_snapshot_hash(doc.get("snapshot") or {})
    ip = ""
    ua = ""
    try:
        ip = (request.headers.get("x-forwarded-for", "").split(",")[0].strip()
              or (request.client.host if request and request.client else ""))
        ua = (request.headers.get("user-agent", "") if request else "")[:400]
    except Exception:
        ip = ip or ""
    await db.card_shares.update_one({"token": token},
        {"$inc": {"opens": 1}, "$set": {"last_opened_at": now}})
    await db.card_share_access.insert_one({"token": token, "org_id": doc.get("org_id"),
        "kind": "open", "who": None, "ip": ip, "ua": ua, "at": now})
    await _card_engage_alert(token, doc, "open")
    await _card_anomaly_autocheck(token, doc.get("org_id"), ip, ua, "open")
    import asyncio
    asyncio.create_task(_instant_suspicious_check(doc.get("org_id"), token, ip, ua, "open", None, now))
    return {"snapshot": doc["snapshot"], "created_at": doc.get("created_at"),
            "created_by": doc.get("created_by"), "expires_at": doc.get("expires_at"), "snapshot_sha256": sha}


@agents_router.get("/public/card-share/{token}/card.pdf")
async def public_card_share_pdf(token: str, who: str = "", request: Request = None):
    from datetime import datetime, timezone
    from fastapi.responses import StreamingResponse
    from reports import _build_pdf, _resolve_brand
    import io, os as _os
    from bson import ObjectId as _OID
    doc = await db.card_shares.find_one({"token": token}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "This shared card link is invalid.")
    if doc.get("expires_at") and datetime.now(timezone.utc).isoformat() > doc["expires_at"]:
        raise HTTPException(410, "This shared card link has expired.")
    snap = doc["snapshot"]
    brand = None
    try:
        _org = await db.organizations.find_one({"_id": _OID(doc.get("org_id"))}) if doc.get("org_id") else None
        brand = _resolve_brand(_org)
    except Exception:
        brand = None
    md = _card_markdown(snap)
    buf = _build_pdf(md, snap.get("title") or "Detail card evidence", cover=True,
                     org_name=snap.get("org_name"), brand=brand,
                     exec_summary=snap.get("summary") or None)
    raw = buf.getvalue()
    seal = doc.get("snapshot_sha256") or _canonical_snapshot_hash(snap)
    try:
        auditor = (who or "").strip()[:120] or "External auditor"
        access = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        card_url = f"{_os.environ.get('FRONTEND_URL', '').rstrip('/')}/card/{token}"
        raw = await _brand_watermark_pdf(raw, org_id=doc.get("org_id"), room_url=card_url,
            subtext=f"Downloaded by {auditor} \u00b7 {access} \u00b7 link expires {(doc.get('expires_at') or '')[:10]}")
        raw = _stamp_verified_seal(raw, seal)
        ip = ""
        ua = ""
        try:
            ip = (request.headers.get("x-forwarded-for", "").split(",")[0].strip()
                  or (request.client.host if request and request.client else ""))
            ua = (request.headers.get("user-agent", "") if request else "")[:400]
        except Exception:
            ip = ip or ""
        _dl_now = datetime.now(timezone.utc).isoformat()
        await db.card_shares.update_one({"token": token},
            {"$inc": {"downloads": 1},
             "$set": {"last_downloaded_at": _dl_now, "last_downloaded_by": auditor}})
        await db.card_share_access.insert_one({"token": token, "org_id": doc.get("org_id"),
            "kind": "download", "who": auditor, "ip": ip, "ua": ua, "at": _dl_now})
        await _card_engage_alert(token, doc, "download", who=auditor)
        await _card_anomaly_autocheck(token, doc.get("org_id"), ip, ua, "download", who=auditor)
        import asyncio
        asyncio.create_task(_instant_suspicious_check(doc.get("org_id"), token, ip, ua, "download", auditor, _dl_now))
    except Exception:
        pass
    return StreamingResponse(io.BytesIO(raw), media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="obserra-detail-card.pdf"'})


# ── Share Center — admin management of every shared detail-card link ──
@agents_router.get("/runtime/card-shares")
async def list_card_shares(admin: dict = Depends(require_roles("admin"))):
    import os
    from datetime import datetime, timezone
    frontend = os.environ.get("FRONTEND_URL", "").rstrip("/")
    now_iso = datetime.now(timezone.utc).isoformat()
    out = []
    async for d in db.card_shares.find({"org_id": admin["org_id"]}).sort("created_at", -1):
        snap = d.get("snapshot") or {}
        out.append({
            "token": d["token"], "url": f"{frontend}/card/{d['token']}",
            "title": snap.get("title") or "Detail card", "ref": snap.get("ref") or "",
            "rating": snap.get("rating"), "created_at": d.get("created_at"), "created_by": d.get("created_by"),
            "expires_at": d.get("expires_at"),
            "expired": bool(d.get("expires_at") and now_iso > d["expires_at"]),
            "opens": d.get("opens", 0), "downloads": d.get("downloads", 0),
            "last_opened_at": d.get("last_opened_at"), "last_downloaded_at": d.get("last_downloaded_at"),
            "attach_to_board": bool(d.get("attach_to_board")),
        })
    return {"cards": out}


class CardTokenBody(BaseModel):
    token: str


@agents_router.post("/runtime/card-share/revoke")
async def revoke_card_share(body: CardTokenBody, admin: dict = Depends(require_roles("admin"))):
    res = await db.card_shares.delete_one({"token": body.token, "org_id": admin["org_id"]})
    if not res.deleted_count:
        raise HTTPException(404, "Shared card not found.")
    await _log_audit(admin["org_id"], admin["email"], "agent.card_share_revoke",
                     f"Shared card revoked ({body.token[:8]}\u2026)")
    return {"revoked": True}


class CardAttachBody(BaseModel):
    token: str
    attach: bool = True


@agents_router.post("/runtime/card-share/attach")
async def attach_card_share(body: CardAttachBody, admin: dict = Depends(require_roles("admin"))):
    res = await db.card_shares.update_one({"token": body.token, "org_id": admin["org_id"]},
        {"$set": {"attach_to_board": bool(body.attach)}})
    if not res.matched_count:
        raise HTTPException(404, "Shared card not found.")
    return {"attach_to_board": bool(body.attach)}


@agents_router.get("/runtime/card-share/{token}/stats")
async def card_share_stats(token: str, admin: dict = Depends(require_roles("admin"))):
    d = await db.card_shares.find_one({"token": token, "org_id": admin["org_id"]}, {"_id": 0})
    if not d:
        raise HTTPException(404, "Shared card not found.")
    return {"opens": d.get("opens", 0), "downloads": d.get("downloads", 0),
            "last_opened_at": d.get("last_opened_at"), "last_downloaded_at": d.get("last_downloaded_at"),
            "expires_at": d.get("expires_at"), "attach_to_board": bool(d.get("attach_to_board"))}


async def _card_engage_alert(token, doc, event, who=None):
    """Ping org admins/execs the FIRST time a shared card is opened/downloaded (best-effort, once per event).
    Gated by the org's engagement cadence — only fires when cadence == 'instant'."""
    import html as _html, os as _os
    from bson import ObjectId
    org = await db.organizations.find_one(
        {"_id": ObjectId(doc.get("org_id"))}, {"card_engagement_cadence": 1}) if doc.get("org_id") else None
    if ((org or {}).get("card_engagement_cadence") or "instant") != "instant":
        return
    flag = f"alerted_{event}"
    if doc.get(flag):
        return
    res = await db.card_shares.update_one({"token": token, flag: {"$ne": True}}, {"$set": {flag: True}})
    if not res.modified_count:
        return
    snap = doc.get("snapshot") or {}
    frontend = _os.environ.get("FRONTEND_URL", "").rstrip("/")
    url = f"{frontend}/card/{token}"
    title = _html.escape(snap.get("title") or "Detail card")
    ref = f" ({_html.escape(snap.get('ref'))})" if snap.get("ref") else ""
    actor = _html.escape(who or "An auditor")
    verb = "downloaded the signed PDF of" if event == "download" else "opened"
    subject = "Shared card downloaded — Obserra" if event == "download" else "Shared card opened — Obserra"
    html = (f"<div style='font:400 14px Arial;color:#1f2937;max-width:560px;margin:auto'>"
            f"<h2 style='color:#0f1e3d'>Your shared evidence landed</h2>"
            f"<p><strong>{actor}</strong> just {verb} the shared detail card <strong>{title}</strong>{ref}.</p>"
            f"<p><a href='{url}' style='color:#12b4d6'>{url}</a></p>"
            f"<p style='font-size:11px;color:#9ca3af'>Obserra — Agentic AI Security Control & Governance · Share Center · Engagement alerts</p></div>")
    await _notify_org_staff(doc.get("org_id"), subject, html,
        "Shared card engagement", f"{who or 'An auditor'} {verb} \u201c{snap.get('title') or 'a detail card'}\u201d.",
        dedupe_key=f"card-engage:{token}:{event}")


class CardRenewBody(BaseModel):
    token: str
    days: int = 14


@agents_router.post("/runtime/card-share/renew")
async def renew_card_share(body: CardRenewBody, admin: dict = Depends(require_roles("admin"))):
    import os
    from datetime import datetime, timezone, timedelta
    days = max(1, min(90, int(body.days or 14)))
    expires = (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()
    res = await db.card_shares.update_one({"token": body.token, "org_id": admin["org_id"]},
        {"$set": {"expires_at": expires}})
    if not res.matched_count:
        raise HTTPException(404, "Shared card not found.")
    await _log_audit(admin["org_id"], admin["email"], "agent.card_share_renew",
                     f"Shared card renewed ({body.token[:8]}\u2026 \u2192 {expires[:10]})")
    frontend = os.environ.get("FRONTEND_URL", "").rstrip("/")
    return {"ok": True, "token": body.token, "url": f"{frontend}/card/{body.token}",
            "expires_at": expires, "days": days}


def _parse_ua(ua: str) -> str:
    """Best-effort browser + OS label from a User-Agent string (offline, no external calls)."""
    if not ua:
        return ""
    u = ua.lower()
    if any(b in u for b in ("bot", "crawl", "spider", "curl", "wget", "python-", "httpx", "http-client")):
        browser = "Bot/Script"
    elif "edg/" in u:
        browser = "Edge"
    elif "chrome" in u and "chromium" not in u:
        browser = "Chrome"
    elif "firefox" in u:
        browser = "Firefox"
    elif "safari" in u:
        browser = "Safari"
    else:
        browser = "Browser"
    if "iphone" in u or "ipad" in u or "ios" in u:
        os_name = "iOS"
    elif "android" in u:
        os_name = "Android"
    elif "mac os" in u or "macintosh" in u:
        os_name = "macOS"
    elif "windows" in u:
        os_name = "Windows"
    elif "linux" in u:
        os_name = "Linux"
    else:
        os_name = ""
    return f"{browser} on {os_name}" if os_name else browser


async def _geo_lookup_many(ips):
    """Best-effort city/country + lat/lon per public IP via keyless ip-api.com batch (silent on failure)."""
    import httpx
    out = {}
    valid = [ip for ip in ips if ip and ":" not in ip
             and not ip.startswith(("10.", "127.", "192.168.", "172.16.", "172.17.", "172.18.",
                                     "172.19.", "172.2", "172.30.", "172.31.", "169.254."))]
    if not valid:
        return out
    try:
        payload = [{"query": ip, "fields": "status,country,city,lat,lon,query"} for ip in valid[:100]]
        async with httpx.AsyncClient(timeout=4.0) as client:
            r = await client.post("http://ip-api.com/batch", json=payload)
        if r.status_code == 200:
            for item in r.json():
                if item.get("status") == "success":
                    loc = ", ".join([x for x in [item.get("city"), item.get("country")] if x])
                    out[item.get("query")] = {"loc": loc, "lat": item.get("lat"), "lon": item.get("lon")}
    except Exception:
        pass
    return out


async def _card_access_enriched(token, org_id):
    """Access rows enriched with device (offline UA parse), best-effort geo + lat/lon (cached back),
    and a 'new country/device' anomaly flag relative to the card's own earlier history."""
    d = await db.card_shares.find_one({"token": token, "org_id": org_id}, {"_id": 0})
    if not d:
        return None, []
    from bson import ObjectId as _OID
    _org = await db.organizations.find_one({"_id": _OID(org_id)}, {"trusted_countries": 1, "trusted_ip_ranges": 1}) if org_id else None
    _trusted = {(c or "").strip().lower() for c in ((_org or {}).get("trusted_countries") or [])}
    _trusted_ips = (_org or {}).get("trusted_ip_ranges") or []
    rows = await db.card_share_access.find(
        {"token": token, "org_id": org_id}, {"_id": 0}).sort("at", -1).to_list(500)
    need = sorted({r.get("ip") for r in rows if r.get("ip") and r.get("geo_lat") is None})
    geo_map = await _geo_lookup_many(need) if need else {}
    for r in rows:
        g = geo_map.get(r.get("ip"))
        if g and r.get("geo_lat") is None:
            r["geo"] = r.get("geo") or g.get("loc") or ""
            r["geo_lat"] = g.get("lat")
            r["geo_lon"] = g.get("lon")
            try:
                await db.card_share_access.update_one(
                    {"token": token, "org_id": org_id, "ip": r["ip"], "at": r["at"]},
                    {"$set": {"geo": r["geo"], "geo_lat": r["geo_lat"], "geo_lon": r["geo_lon"]}})
            except Exception:
                pass
        r["device"] = _parse_ua(r.get("ua") or "")
    seen_c, seen_dev = set(), set()
    for r in sorted(rows, key=lambda x: x.get("at") or ""):
        country = (r.get("geo") or "").split(",")[-1].strip() if r.get("geo") else ""
        device = r.get("device") or ""
        reasons = []
        if country:
            if seen_c and country not in seen_c and country.strip().lower() not in _trusted:
                reasons.append("new country")
            seen_c.add(country)
        if device:
            if seen_dev and device not in seen_dev:
                reasons.append("new device")
            seen_dev.add(device)
        if _ip_in_ranges(r.get("ip"), _trusted_ips):
            reasons = []
        r["anomaly"] = bool(reasons)
        r["anomaly_reason"] = " \u00b7 ".join(reasons)
    return d, rows


def _map_clusters(rows):
    """Aggregate geo-located access rows into location clusters with counts (for the heat map)."""
    clusters = {}
    for r in rows:
        lat, lon = r.get("geo_lat"), r.get("geo_lon")
        if not isinstance(lat, (int, float)) or not isinstance(lon, (int, float)):
            continue
        key = f"{round(lat, 1)},{round(lon, 1)}"
        c = clusters.get(key)
        if not c:
            c = {"lat": lat, "lon": lon, "count": 0, "downloads": 0, "anomaly": False, "label": r.get("geo") or ""}
            clusters[key] = c
        c["count"] += 1
        if r.get("kind") == "download":
            c["downloads"] += 1
        if r.get("anomaly"):
            c["anomaly"] = True
    return list(clusters.values())


_MAP_CONTINENTS = [
    [(-168, 66), (-95, 68), (-52, 60), (-80, 25), (-105, 20), (-125, 40), (-140, 60)],
    [(-80, 10), (-60, 5), (-35, -8), (-40, -23), (-65, -55), (-75, -45), (-82, -5)],
    [(-10, 60), (0, 50), (15, 55), (30, 60), (40, 48), (20, 40), (0, 43), (-9, 44)],
    [(-17, 35), (10, 37), (35, 32), (51, 12), (40, -15), (20, -35), (10, -20), (-5, 5), (-16, 15)],
    [(30, 60), (60, 70), (100, 72), (140, 66), (170, 66), (145, 45), (120, 30), (100, 10), (78, 8), (60, 25), (45, 40), (35, 45)],
    [(113, -22), (130, -12), (145, -15), (153, -28), (146, -39), (130, -32), (115, -35)],
]


def _render_world_png(rows, width=1000, height=500):
    """Render a dark equirectangular world map PNG with heat-sized dots for the custody PDF."""
    from PIL import Image, ImageDraw
    import io, math
    def proj(lon, lat):
        return (int((lon + 180) / 360 * width), int((90 - lat) / 180 * height))
    img = Image.new("RGB", (width, height), (10, 17, 32))
    d = ImageDraw.Draw(img, "RGBA")
    for i in range(1, 4):
        y = height // 4 * i
        d.line([(0, y), (width, y)], fill=(60, 80, 110, 90), width=1)
    for i in range(1, 6):
        x = width // 6 * i
        d.line([(x, 0), (x, height)], fill=(60, 80, 110, 90), width=1)
    for cont in _MAP_CONTINENTS:
        d.polygon([proj(lon, lat) for (lon, lat) in cont], fill=(70, 85, 110, 150), outline=(90, 110, 140, 200))
    for c in _map_clusters(rows):
        x, y = proj(c["lon"], c["lat"])
        r = min(int(6 + 5 * math.sqrt(c["count"])), 34)
        col = (239, 68, 68) if c["anomaly"] else (34, 200, 235) if c["downloads"] else (52, 211, 120)
        d.ellipse([x - r, y - r, x + r, y + r], fill=col + (70,))
        d.ellipse([x - 4, y - 4, x + 4, y + 4], fill=col + (255,))
    out = io.BytesIO()
    img.save(out, format="PNG")
    return out.getvalue()


async def _room_access_geo(token, org_id):
    """Evidence-room access rows enriched with best-effort geo lat/lon (cached back) for the custody map."""
    rows = await db.evidence_room_access.find(
        {"token": token, "org_id": org_id}, {"_id": 0}).sort("at", -1).to_list(500)
    need = sorted({r.get("ip") for r in rows if r.get("ip") and r.get("geo_lat") is None})
    geo_map = await _geo_lookup_many(need) if need else {}
    for r in rows:
        g = geo_map.get(r.get("ip"))
        if g and r.get("geo_lat") is None:
            r["geo"] = r.get("geo") or g.get("loc") or ""
            r["geo_lat"] = g.get("lat")
            r["geo_lon"] = g.get("lon")
            try:
                await db.evidence_room_access.update_one(
                    {"token": token, "org_id": org_id, "ip": r["ip"], "at": r["at"]},
                    {"$set": {"geo": r["geo"], "geo_lat": r["geo_lat"], "geo_lon": r["geo_lon"]}})
            except Exception:
                pass
    return rows


def _append_custody_map_page(raw, rows, title="Where this evidence was accessed"):
    """Append a dark equirectangular world-map custody page (heat-sized dots) to a PDF when geo rows exist."""
    try:
        if any(isinstance(r.get("geo_lat"), (int, float)) for r in rows):
            import pymupdf
            png = _render_world_png(rows)
            pdfdoc = pymupdf.open(stream=raw, filetype="pdf")
            page = pdfdoc.new_page(width=612, height=430)
            page.insert_text((40, 46), title, fontsize=13, color=(0.06, 0.12, 0.24))
            page.insert_image(pymupdf.Rect(40, 64, 572, 330), stream=png)
            page.insert_text((40, 350),
                             f"{len(_map_clusters(rows))} location(s) \u00b7 dot size = number of accesses \u00b7 "
                             f"green = open \u00b7 cyan = download \u00b7 red = anomaly",
                             fontsize=8, color=(0.4, 0.45, 0.5))
            raw = pdfdoc.tobytes()
            pdfdoc.close()
    except Exception:
        pass
    return raw


def _ip_in_ranges(ip, ranges):
    """True if `ip` falls within any trusted CIDR / exact IP in `ranges` (best-effort)."""
    if not ip or not ranges:
        return False
    import ipaddress
    try:
        addr = ipaddress.ip_address(ip)
    except Exception:
        return False
    for cidr in ranges:
        cidr = (cidr or "").strip()
        if not cidr:
            continue
        try:
            if "/" in cidr:
                if addr in ipaddress.ip_network(cidr, strict=False):
                    return True
            elif ipaddress.ip_address(cidr) == addr:
                return True
        except Exception:
            continue
    return False


def _access_suspicious(r, trusted_countries, trusted_ips, trusted_auditors):
    """A located access is 'suspicious' when it's outside every trusted zone AND not from a trusted auditor."""
    who = (r.get("who") or "").strip().lower()
    if who and who in trusted_auditors:
        return False
    if _ip_in_ranges(r.get("ip"), trusted_ips):
        return False
    geo = r.get("geo") or ""
    country = geo.split(",")[-1].strip() if geo else ""
    if not country or country.lower() in trusted_countries:
        return False
    return True


async def _card_anomaly_autocheck(token, org_id, ip, ua, kind, who=None):
    """Immediately alert org staff when THIS access is from a new country/device vs the card's history.
    Fires regardless of engagement cadence (unless cadence == 'off'). Best-effort; dedup per token+ip+kind."""
    try:
        import html as _html, os as _os
        from bson import ObjectId
        geo = ""
        lat = lon = None
        if ip:
            g = (await _geo_lookup_many([ip])).get(ip)
            if g:
                geo = g.get("loc") or ""
                lat, lon = g.get("lat"), g.get("lon")
                try:
                    await db.card_share_access.update_one(
                        {"token": token, "org_id": org_id, "ip": ip, "geo_lat": None},
                        {"$set": {"geo": geo, "geo_lat": lat, "geo_lon": lon}})
                except Exception:
                    pass
        country = geo.split(",")[-1].strip() if geo else ""
        device = _parse_ua(ua or "")
        rows = await db.card_share_access.find({"token": token, "org_id": org_id}, {"_id": 0}).to_list(500)
        prior = sorted(rows, key=lambda x: x.get("at") or "")[:-1]
        seen_c, seen_dev = set(), set()
        for r in prior:
            gg = r.get("geo") or ""
            if gg:
                seen_c.add(gg.split(",")[-1].strip())
            dv = _parse_ua(r.get("ua") or "")
            if dv:
                seen_dev.add(dv)
        org = await db.organizations.find_one({"_id": ObjectId(org_id)}, {"card_engagement_cadence": 1, "trusted_countries": 1, "trusted_ip_ranges": 1}) if org_id else None
        if _ip_in_ranges(ip, (org or {}).get("trusted_ip_ranges") or []):
            return
        trusted = {(c or "").strip().lower() for c in ((org or {}).get("trusted_countries") or [])}
        reasons = []
        if country and seen_c and country not in seen_c and country.strip().lower() not in trusted:
            reasons.append("new country")
        if device and seen_dev and device not in seen_dev:
            reasons.append("new device")
        if not reasons:
            return
        if ((org or {}).get("card_engagement_cadence") or "instant") == "off":
            return
        doc = await db.card_shares.find_one({"token": token}, {"_id": 0, "snapshot": 1})
        snap = (doc or {}).get("snapshot") or {}
        frontend = _os.environ.get("FRONTEND_URL", "").rstrip("/")
        url = f"{frontend}/card/{token}"
        title = _html.escape(snap.get("title") or "Detail card")
        actor = _html.escape(who or "An auditor")
        where = _html.escape(geo or ip or "an unknown location")
        dev = _html.escape(device or "an unknown device")
        reason_txt = " and ".join(reasons)
        verb = "downloaded" if kind == "download" else "opened"
        html = (f"<div style='font:400 14px Arial;color:#1f2937;max-width:560px;margin:auto'>"
                f"<h2 style='color:#b91c1c'>\u26a0 Unusual shared-card access</h2>"
                f"<p><strong>{actor}</strong> just {verb} the shared detail card <strong>{title}</strong> "
                f"from <strong>{where}</strong> on <strong>{dev}</strong> — flagged as <strong>{reason_txt}</strong> "
                f"versus this card's earlier access.</p>"
                f"<p><a href='{url}' style='color:#12b4d6'>{url}</a></p>"
                f"<p style='font-size:11px;color:#9ca3af'>Obserra — Share Center · Anomaly auto-alert</p></div>")
        await _notify_org_staff(org_id, "\u26a0 Unusual shared-card access — Obserra", html,
            "Unusual shared-card access",
            f"{actor} {verb} \u201c{snap.get('title') or 'a card'}\u201d from {geo or ip} ({reason_txt}).",
            dedupe_key=f"card-anomaly:{token}:{ip}:{kind}")
    except Exception:
        pass


@agents_router.get("/runtime/card-share/{token}/access-log")
async def card_share_access_log(token: str, admin: dict = Depends(require_roles("admin"))):
    d, rows = await _card_access_enriched(token, admin["org_id"])
    if not d:
        raise HTTPException(404, "Shared card not found.")
    return {"opens": d.get("opens", 0), "downloads": d.get("downloads", 0),
            "last_downloaded_by": d.get("last_downloaded_by"), "access": rows}


@agents_router.get("/runtime/card-share/{token}/access-log.csv")
async def card_share_access_log_csv(token: str, admin: dict = Depends(require_roles("admin"))):
    import io, csv
    from fastapi.responses import StreamingResponse
    d, rows = await _card_access_enriched(token, admin["org_id"])
    if not d:
        raise HTTPException(404, "Shared card not found.")
    snap = d.get("snapshot") or {}
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["Obserra — shared card chain of custody"])
    w.writerow(["Card", snap.get("title") or "Detail card", "Ref", snap.get("ref") or ""])
    w.writerow(["Opens", d.get("opens", 0), "Downloads", d.get("downloads", 0)])
    w.writerow([])
    w.writerow(["Event", "Who", "IP", "Location", "Device", "Anomaly", "Timestamp (UTC)"])
    for r in rows:
        w.writerow([r.get("kind"), r.get("who") or "", r.get("ip") or "", r.get("geo") or "",
                    r.get("device") or "", ("\u26a0 " + r["anomaly_reason"]) if r.get("anomaly") else "",
                    r.get("at") or ""])
    return StreamingResponse(io.BytesIO(buf.getvalue().encode("utf-8")), media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="obserra-card-access-log.csv"'})


@agents_router.get("/runtime/card-share/{token}/access-log.pdf")
async def card_share_access_log_pdf(token: str, admin: dict = Depends(require_roles("admin"))):
    import io
    from fastapi.responses import StreamingResponse
    from reports import _build_pdf, _resolve_brand
    from bson import ObjectId as _OID
    d, rows = await _card_access_enriched(token, admin["org_id"])
    if not d:
        raise HTTPException(404, "Shared card not found.")
    snap = d.get("snapshot") or {}
    brand = None
    try:
        _org = await db.organizations.find_one({"_id": _OID(admin["org_id"])})
        brand = _resolve_brand(_org)
    except Exception:
        brand = None
    lines = [f"**Card:** {snap.get('title') or 'Detail card'}" + (f" ({snap.get('ref')})" if snap.get("ref") else ""),
             f"**Engagement:** {d.get('opens', 0)} open(s) \u00b7 {d.get('downloads', 0)} download(s)",
             "## Chain of custody"]
    if not rows:
        lines.append("No access recorded yet.")
    for r in rows:
        who = r.get("who") or ("opened" if r.get("kind") == "open" else "download")
        bits = " \u00b7 ".join([str(x) for x in [r.get("ip"), r.get("geo"), r.get("device")] if x])
        flag = f" \u26a0 {r['anomaly_reason']}" if r.get("anomaly") else ""
        lines.append(f"- **{r.get('kind')}** — {who}" + (f" \u00b7 {bits}" if bits else "") + flag + f" \u00b7 {r.get('at')}")
    buf = _build_pdf("\n".join(lines), "Shared card — chain of custody", cover=True,
                     org_name=snap.get("org_name"), brand=brand)
    raw = buf.getvalue()
    try:
        if any(isinstance(r.get("geo_lat"), (int, float)) for r in rows):
            import pymupdf
            png = _render_world_png(rows)
            pdfdoc = pymupdf.open(stream=raw, filetype="pdf")
            page = pdfdoc.new_page(width=612, height=430)
            page.insert_text((40, 46), "Where this evidence was accessed", fontsize=13, color=(0.06, 0.12, 0.24))
            page.insert_image(pymupdf.Rect(40, 64, 572, 330), stream=png)
            page.insert_text((40, 350), f"{len(_map_clusters(rows))} location(s) \u00b7 dot size = number of accesses \u00b7 red = anomaly",
                             fontsize=8, color=(0.4, 0.45, 0.5))
            raw = pdfdoc.tobytes()
            pdfdoc.close()
    except Exception:
        pass
    try:
        seal = _canonical_snapshot_hash({"token": token, "rows": rows})
        raw = await _brand_watermark_pdf(raw, org_id=admin["org_id"], room_url="",
            subtext=f"Chain of custody \u00b7 {d.get('opens', 0)} opens \u00b7 {d.get('downloads', 0)} downloads")
        raw = _stamp_verified_seal(raw, seal)
    except Exception:
        pass
    return StreamingResponse(io.BytesIO(raw), media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="obserra-card-access-log.pdf"'})


# ── Auditor notes — external auditors leave read-only questions on the public room ──
class RoomCommentBody(BaseModel):
    author: str = ""
    email: str | None = ""
    text: str = ""
    priority: str = "normal"


async def _notify_org_staff(org_id, subject, html, kind_title, kind_body, dedupe_key=None):
    """In-app + email admins/execs of an org (best-effort)."""
    try:
        await notifications.create(org_id, "system", kind_title, kind_body,
                                   ref="agentic-ai-security", dedupe_key=dedupe_key)
    except Exception:
        pass
    try:
        recips = await db.users.find({"org_id": org_id, "role": {"$in": ["admin", "executive"]}},
                                     {"_id": 0, "email": 1}).to_list(200)
        for rr in recips:
            try:
                await notifications.send_email(rr["email"], subject, html)
            except Exception:
                pass
    except Exception:
        pass


async def _instant_suspicious_check(org_id, token, ip, ua, kind, who=None, at=None):
    """Fire-and-forget: if instant suspicious-access alerts are ON and this access is from OUTSIDE every
    trusted zone (and not a trusted auditor), ping admins/execs by email + in-app + Slack/Teams immediately."""
    try:
        from bson import ObjectId
        org = await db.organizations.find_one(
            {"_id": ObjectId(org_id)},
            {"instant_suspicious_alerts": 1, "trusted_countries": 1, "trusted_ip_ranges": 1,
             "trusted_auditors": 1}) if org_id else None
        if not org or not org.get("instant_suspicious_alerts"):
            return
        tc = {(c or "").strip().lower() for c in (org.get("trusted_countries") or [])}
        tips = org.get("trusted_ip_ranges") or []
        tauds = {(a or "").strip().lower() for a in (org.get("trusted_auditors") or [])}
        if not (tc or tips):
            return
        if (who or "").strip().lower() in tauds or _ip_in_ranges(ip, tips):
            return
        geo = ""
        if ip:
            g = (await _geo_lookup_many([ip])).get(ip)
            if g:
                geo = g.get("loc") or ""
        if not _access_suspicious({"ip": ip, "ua": ua, "who": who, "geo": geo}, tc, tips, tauds):
            return
        loc = geo or ip or "an unknown location"
        device = _parse_ua(ua or "") or "unknown device"
        actor = who or "an anonymous viewer"
        html = (f"<div style='font:400 14px Arial;color:#1f2937;max-width:600px;margin:auto'>"
                f"<h2 style='color:#0f1e3d'>\u26a0 Unusual evidence access</h2>"
                f"<p>A <strong>{kind}</strong> of shared evidence just came from <strong>outside every trusted "
                f"country / network</strong>:</p><ul style='padding-left:18px'>"
                f"<li><strong>Location:</strong> {loc}</li><li><strong>Who:</strong> {actor}</li>"
                f"<li><strong>Device:</strong> {device}</li><li><strong>IP:</strong> {ip or '—'}</li>"
                f"<li><strong>When:</strong> {(at or '')[:19].replace('T', ' ')} UTC</li></ul>"
                f"<p style='font-size:12px;color:#6b7280'>Open the Control Assurance access globe "
                f"(filter \u2192 Suspicious) to investigate. If expected, add the location or auditor to your Trusted access rules.</p></div>")
        dk = f"instant-suspicious:{org_id}:{ip}:{token}:{kind}:{(at or '')[:16]}"
        await _notify_org_staff(org_id, "\u26a0 Unusual evidence access — outside your trusted zones", html,
                                "Unusual evidence access",
                                f"{kind} from {loc} ({actor}) — outside your trusted zones.", dedupe_key=dk)
        try:
            from self_scan import _post_chat_alert
            await _post_chat_alert(org_id, "\u26a0 Unusual evidence access",
                f"A *{kind}* of shared evidence came from *{loc}* ({actor}, {device}, {ip or 'no IP'}) — outside every trusted zone.")
        except Exception:
            pass
    except Exception:
        pass


async def _run_card_engagement_weekly_digest():
    """Monday: email admins/execs a summary of which shared detail cards auditors opened/downloaded
    in the last 7 days. Skips orgs with zero engagement. Hooked into the weekly-drift-digest cron."""
    import os
    from datetime import datetime, timezone, timedelta
    now = datetime.now(timezone.utc)
    since = (now - timedelta(days=7)).isoformat()
    frontend = os.environ.get("FRONTEND_URL", "").rstrip("/")
    org_ids = await db.card_share_access.distinct("org_id", {"at": {"$gte": since}})
    for oid in org_ids:
        try:
            from bson import ObjectId
            org = await db.organizations.find_one(
                {"_id": ObjectId(oid)}, {"card_engagement_cadence": 1}) if oid else None
            if ((org or {}).get("card_engagement_cadence") or "instant") != "weekly":
                continue
            events = await db.card_share_access.find(
                {"org_id": oid, "at": {"$gte": since}}, {"_id": 0}).to_list(5000)
            if not events:
                continue
            by_token = {}
            for e in events:
                agg = by_token.setdefault(e.get("token"), {"opens": 0, "downloads": 0})
                agg["opens" if e.get("kind") == "open" else "downloads"] += 1
            cards = await db.card_shares.find({"token": {"$in": list(by_token.keys())}}, {"_id": 0}).to_list(500)
            cmap = {c["token"]: c for c in cards}
            total_o = sum(v["opens"] for v in by_token.values())
            total_d = sum(v["downloads"] for v in by_token.values())
            rows_html = []
            for t, v in sorted(by_token.items(), key=lambda kv: kv[1]["opens"] + kv[1]["downloads"], reverse=True):
                snap = (cmap.get(t) or {}).get("snapshot") or {}
                url = f"{frontend}/card/{t}"
                rows_html.append(
                    f"<li style='margin-bottom:6px'><strong>{snap.get('title', 'Detail card')}</strong> "
                    f"<span style='color:#6b7280'>({snap.get('ref', '')})</span> — "
                    f"<span style='color:#12b4d6'>{v['opens']} view(s) \u00b7 {v['downloads']} download(s)</span><br>"
                    f"<a href='{url}' style='color:#12b4d6;font-size:12px'>{url}</a></li>")
            html = (f"<div style='font:400 14px Arial;color:#1f2937;max-width:600px;margin:auto'>"
                    f"<h2 style='color:#0f1e3d'>Weekly shared-card engagement</h2>"
                    f"<p>In the last 7 days your shared detail cards were opened <strong>{total_o}</strong> time(s) "
                    f"and downloaded <strong>{total_d}</strong> time(s) across {len(by_token)} card(s):</p>"
                    f"<ul style='padding-left:18px'>{''.join(rows_html)}</ul>"
                    f"<p style='font-size:11px;color:#9ca3af'>Obserra — Agentic AI Security Control & Governance · Share Center · Weekly engagement digest</p></div>")
            await _notify_org_staff(oid, "Weekly shared-card engagement — Obserra", html,
                "Weekly shared-card engagement",
                f"{total_o} view(s) \u00b7 {total_d} download(s) across {len(by_token)} card(s) last week.",
                dedupe_key=f"card-weekly:{oid}:{now.strftime('%Y-%W')}")
        except Exception:
            pass


async def _run_unusual_access_watchlist():
    """Weekly: for orgs with trusted countries/networks configured, summarise evidence accesses from
    OUTSIDE those trusted zones (last 7 days) as an 'unusual access' board note. Located accesses only
    (private/blank-geo opens are skipped to avoid noise). Hooked into the weekly-drift-digest cron."""
    from datetime import datetime, timezone, timedelta
    now = datetime.now(timezone.utc)
    since = (now - timedelta(days=7)).isoformat()
    orgs = await db.organizations.find(
        {"$or": [{"trusted_countries": {"$exists": True, "$ne": []}},
                 {"trusted_ip_ranges": {"$exists": True, "$ne": []}}]},
        {"_id": 1, "trusted_countries": 1, "trusted_ip_ranges": 1, "trusted_auditors": 1,
         "unusual_access_threshold": 1}).to_list(1000)
    for org in orgs:
        try:
            oid = str(org["_id"])
            trusted = {(c or "").strip().lower() for c in (org.get("trusted_countries") or [])}
            tips = org.get("trusted_ip_ranges") or []
            tauds = {(a or "").strip().lower() for a in (org.get("trusted_auditors") or [])}
            threshold = max(1, int(org.get("unusual_access_threshold") or 1))
            rows = (await db.card_share_access.find({"org_id": oid, "at": {"$gte": since}}, {"_id": 0}).to_list(5000)) \
                + (await db.evidence_room_access.find({"org_id": oid, "at": {"$gte": since}}, {"_id": 0}).to_list(5000))
            sus = [r for r in rows if _access_suspicious(r, trusted, tips, tauds)]
            if len(sus) < threshold:
                continue
            by_loc = {}
            for r in sus:
                loc = r.get("geo") or (r.get("ip") or "unknown")
                by_loc[loc] = by_loc.get(loc, 0) + 1
            top = sorted(by_loc.items(), key=lambda kv: kv[1], reverse=True)[:8]
            rows_html = "".join(
                f"<li style='margin-bottom:4px'><strong>{l}</strong> "
                f"<span style='color:#dc2626'>{n} access(es)</span></li>" for l, n in top)
            html = (f"<div style='font:400 14px Arial;color:#1f2937;max-width:600px;margin:auto'>"
                    f"<h2 style='color:#0f1e3d'>\u26a0 Unusual access watchlist</h2>"
                    f"<p>In the last 7 days, <strong style='color:#dc2626'>{len(sus)}</strong> evidence access(es) "
                    f"came from <strong>outside your trusted countries / networks</strong>, across {len(by_loc)} location(s):</p>"
                    f"<ul style='padding-left:18px'>{rows_html}</ul>"
                    f"<p style='font-size:12px;color:#6b7280'>Review these on the Control Assurance access globe "
                    f"(filter \u2192 Suspicious). Add legitimate locations to your Trusted access rules to silence future alerts.</p>"
                    f"<p style='font-size:11px;color:#9ca3af'>Obserra — Agentic AI Security Control & Governance · Chain-of-custody watchlist</p></div>")
            await _notify_org_staff(oid, "\u26a0 Unusual access watchlist — Obserra", html,
                "Unusual access watchlist",
                f"{len(sus)} access(es) from outside your trusted zones last week, across {len(by_loc)} location(s).",
                dedupe_key=f"unusual-access:{oid}:{now.strftime('%Y-%W')}")
        except Exception:
            pass


@agents_router.post("/public/evidence-room/{token}/comment")
async def evidence_room_comment(token: str, body: RoomCommentBody):
    """Public — an external auditor asks a read-only question on the portal; lands in the admin inbox."""
    from datetime import datetime, timezone
    import secrets, html as _html
    doc = await db.evidence_rooms.find_one({"token": token})
    if not doc:
        raise HTTPException(404, "This auditor room link is invalid.")
    if doc.get("expires_at") and datetime.now(timezone.utc).isoformat() > doc["expires_at"]:
        raise HTTPException(410, "This auditor room link has expired.")
    text = (body.text or "").strip()
    if not text:
        raise HTTPException(400, "A question is required.")
    author = (body.author or "").strip()[:120] or "External auditor"
    author_email = (body.email or "").strip()[:200]
    priority = (body.priority or "normal").strip().lower()
    if priority not in ("low", "normal", "high", "urgent"):
        priority = "normal"
    org_id = doc["org_id"]
    cid = secrets.token_urlsafe(9)
    now_iso = _now()
    await db.evidence_room_comments.insert_one({
        "id": cid, "token": token, "org_id": org_id, "author": author, "author_email": author_email,
        "text": text[:2000], "priority": priority, "at": now_iso, "status": "Open",
        "reply": None, "reply_by": None, "reply_at": None,
        "messages": [{"role": "auditor", "by": author, "text": text[:2000], "at": now_iso, "attachment": None}]})
    await db.evidence_rooms.update_one({"token": token}, {"$inc": {"comments": 1}})
    html = (f"<div style='font:400 14px Arial;color:#1f2937;max-width:560px;margin:auto'>"
            f"<h2 style='color:#0f1e3d'>New auditor question</h2>"
            f"<p><strong>{_html.escape(author)}</strong> asked a question in your AI Enforcement Evidence auditor room:</p>"
            f"<blockquote style='border-left:3px solid #12b4d6;margin:0;padding:6px 14px;color:#374151'>{_html.escape(text[:1000])}</blockquote>"
            f"<p style='font-size:11px;color:#9ca3af'>Obserra — Agentic AI Security Control & Governance · Defensibility · Auditor questions</p></div>")
    await _notify_org_staff(org_id, "New auditor question — Obserra", html,
                            "New auditor question", f"{author}: {text[:200]}", dedupe_key=f"auditor-q:{cid}")
    return {"ok": True, "id": cid}


@agents_router.get("/public/evidence-room/{token}/comments")
async def public_evidence_room_comments(token: str):
    """Public — the threaded Q&A shown on the portal (admin identities / emails are never exposed)."""
    doc = await db.evidence_rooms.find_one({"token": token}, {"_id": 1})
    if not doc:
        raise HTTPException(404, "This auditor room link is invalid.")
    rows = await db.evidence_room_comments.find({"token": token}, {"_id": 0}).sort("at", 1).to_list(200)
    out = []
    for r in rows:
        msgs = r.get("messages")
        if not msgs:
            msgs = [{"role": "auditor", "by": r.get("author"), "text": r.get("text"), "at": r.get("at"), "attachment": None}]
            if r.get("reply"):
                msgs.append({"role": "admin", "by": "Governance team", "text": r.get("reply"), "at": r.get("reply_at"), "attachment": None})
        pub_msgs = [{"role": m.get("role"),
                     "by": (m.get("by") if m.get("role") == "auditor" else "Governance team"),
                     "text": m.get("text"), "at": m.get("at"), "attachment": m.get("attachment")} for m in msgs]
        out.append({"id": r.get("id"), "author": r.get("author"), "text": r.get("text"),
                    "at": r.get("at"), "status": r.get("status"), "reply": r.get("reply"),
                    "reply_at": r.get("reply_at"), "messages": pub_msgs})
    return {"comments": out}


@agents_router.get("/runtime/evidence-room-comments")
async def list_evidence_room_comments(admin: dict = Depends(require_roles("admin"))):
    from datetime import datetime, timezone, timedelta
    from bson import ObjectId
    org = await db.organizations.find_one({"_id": ObjectId(admin["org_id"])}) or {}
    now = datetime.now(timezone.utc)
    rows = await db.evidence_room_comments.find({"org_id": admin["org_id"]}, {"_id": 0}).sort("at", -1).to_list(200)
    for r in rows:
        pri = (r.get("priority") or "normal").lower()
        r["priority"] = pri
        sla_h = _sla_for(org, pri)
        r["sla_hours"] = sla_h
        overdue = False
        if r.get("status") != "Resolved" and r.get("at"):
            try:
                overdue = now > (datetime.fromisoformat(r["at"]) + timedelta(hours=sla_h))
            except Exception:
                overdue = False
        r["overdue"] = overdue
    return {"comments": rows, "sla_hours": _sla_for(org, "normal"),
            "sla_by_priority": {p: _sla_for(org, p) for p in ("urgent", "high", "normal", "low")}}


class RoomReplyBody(BaseModel):
    id: str
    reply: str
    attach_pdf: bool = False


@agents_router.post("/runtime/evidence-room-comments/reply")
async def reply_evidence_room_comment(body: RoomReplyBody, admin: dict = Depends(require_roles("admin"))):
    import html as _html, base64
    reply = (body.reply or "").strip()
    if not reply:
        raise HTTPException(400, "A reply is required.")
    doc = await db.evidence_room_comments.find_one({"id": body.id, "org_id": admin["org_id"]}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Question not found.")
    now_iso = _now()
    msg = {"role": "admin", "by": admin["email"], "text": reply[:2000], "at": now_iso,
           "attachment": ("AI Enforcement Evidence Pack (PDF)" if body.attach_pdf else None)}
    await db.evidence_room_comments.update_one(
        {"id": body.id, "org_id": admin["org_id"]},
        {"$set": {"reply": reply[:2000], "reply_by": admin["email"], "reply_at": now_iso, "status": "Answered"},
         "$push": {"messages": msg}})
    try:
        em = (doc or {}).get("author_email") or ""
        if em and "@" in em:
            att = None
            if body.attach_pdf:
                try:
                    snap = await _evidence_snapshot(admin["org_id"])
                    att = [{"filename": "obserra-ai-enforcement-evidence.pdf",
                            "content": base64.b64encode(_evidence_pdf(snap).getvalue()).decode()}]
                except Exception:
                    att = None
            html = (f"<div style='font:400 14px Arial;color:#1f2937;max-width:560px;margin:auto'>"
                    f"<h2 style='color:#0f1e3d'>Reply to your audit question</h2>"
                    f"<p>The AI governance team replied:</p>"
                    f"<blockquote style='border-left:3px solid #12b4d6;margin:0;padding:6px 14px;color:#374151'>{_html.escape(reply[:1000])}</blockquote>"
                    + ("<p style='font-size:12px;color:#0f766e'>&#128206; The signed AI Enforcement Evidence Pack is attached.</p>" if att else "")
                    + f"<p style='font-size:12px;color:#6b7280'>Your question: {_html.escape((doc.get('text') or '')[:300])}</p>"
                    f"<p style='font-size:11px;color:#9ca3af'>Obserra — Agentic AI Security Control & Governance</p></div>")
            await notifications.send_email(em, "Reply to your audit question — Obserra", html, attachments=att)
    except Exception:
        pass
    return {"ok": True}


# ── Room renewal + expiry reminders (folded into the daily cron) ──────────────
class RoomRenewBody(BaseModel):
    token: str
    days: int = 14


@agents_router.post("/runtime/evidence-room/renew")
async def renew_evidence_room(body: RoomRenewBody, admin: dict = Depends(require_roles("admin"))):
    import os
    from datetime import datetime, timezone, timedelta
    days = max(1, min(90, int(body.days or 14)))
    expires = (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()
    res = await db.evidence_rooms.update_one(
        {"token": body.token, "org_id": admin["org_id"]},
        {"$set": {"expires_at": expires}, "$unset": {"expiry_reminder_sent": ""}})
    if not res.matched_count:
        raise HTTPException(404, "Auditor room not found.")
    frontend = os.environ.get("FRONTEND_URL", "").rstrip("/")
    await _log_audit(admin["org_id"], admin["email"], "agent.evidence_room_renew",
                     f"Auditor room renewed ({body.token[:8]}… → {expires[:10]})")
    return {"ok": True, "token": body.token, "url": f"{frontend}/audit-room/{body.token}",
            "expires_at": expires, "days": days}


async def _run_agent_room_expiry_reminders(within_days: int = 3):
    """Folded into the daily cron: email admins/execs a few days before each Auditor Room link expires."""
    import os
    from datetime import datetime, timezone, timedelta
    from bson import ObjectId
    now = datetime.now(timezone.utc)
    nowiso = now.isoformat()
    horizon = (now + timedelta(days=within_days)).isoformat()
    rooms = await db.evidence_rooms.find({"expires_at": {"$gt": nowiso, "$lte": horizon}}).to_list(1000)
    frontend = os.environ.get("FRONTEND_URL", "").rstrip("/")
    for room in rooms:
        try:
            if room.get("expiry_reminder_sent"):
                continue
            token = room["token"]; org_id = room["org_id"]; exp = room.get("expires_at", "")
            days_left = max(0, (datetime.fromisoformat(exp) - now).days) if exp else 0
            org = await db.organizations.find_one({"_id": ObjectId(org_id)}) or {}
            oname = org.get("name") or "your organization"
            link = f"{frontend}/app/agentic-ai-security"
            html = (f"<div style='font:400 14px Arial;color:#1f2937;max-width:560px;margin:auto'>"
                    f"<h2 style='color:#b45309'>Auditor Room link expiring soon</h2>"
                    f"<p>A read-only AI Enforcement auditor room for <strong>{oname}</strong> expires on "
                    f"<strong>{exp[:10]}</strong> — about {days_left} day(s) away.</p>"
                    f"<p style='margin:18px 0'><a href='{link}' style='background:#12b4d6;color:#04121a;text-decoration:none;padding:11px 18px;border-radius:8px;font-weight:700' target='_blank'>Open the Defensibility tab to renew</a></p>"
                    f"<p style='font-size:12px;color:#6b7280'>In the <strong>Read-only Auditor Room</strong> card, click <strong>Renew</strong> to extend it in one click — so your audit doesn't stall on a dead link.</p>"
                    f"<p style='font-size:11px;color:#9ca3af'>Obserra — Agentic AI Security Control & Governance</p></div>")
            await _notify_org_staff(org_id, "Auditor Room link expiring soon — Obserra", html,
                                    "Auditor Room link expiring soon",
                                    f"An Auditor Room for {oname} expires on {exp[:10]} ({days_left}d). Renew it to keep auditor access live.",
                                    dedupe_key=f"agent-room-expiry:{token}")
            await db.evidence_rooms.update_one({"token": token}, {"$set": {"expiry_reminder_sent": nowiso}})
        except Exception:
            pass


# ── Board Evidence Digest — one-tap / scheduled rollup of kills & sanctions + signed PDF ──
async def _run_board_evidence_digest(org_id=None, on_demand=False, scheduled=False):
    """Email admins/execs (or configured recipients) a rollup of the last 30 days of AI enforcement +
    current toxic estate + sanctioned/shadow AI systems + the auditor Q&A trail, with the signed Evidence
    Pack PDF attached. Scheduled (daily cron) self-gates per org to its configured day-of-month (deduped
    per month); on-demand fires immediately from the Defensibility tab."""
    import calendar
    from datetime import datetime, timezone
    from bson import ObjectId
    if org_id:
        org = await db.organizations.find_one({"_id": ObjectId(org_id)})
        orgs = [org] if org else []
    else:
        orgs = await db.organizations.find({}).to_list(1000)
    now = datetime.now(timezone.utc)
    ym = now.strftime("%Y-%m")
    total_sent = 0
    for org in orgs:
        if not org:
            continue
        oid = str(org["_id"])
        try:
            if scheduled:
                if not org.get("board_digest_enabled", True):
                    continue
                target = min(int(org.get("board_digest_day") or 1), calendar.monthrange(now.year, now.month)[1])
                if now.day != target or org.get("board_digest_last_sent") == ym:
                    continue
            d = await _build_board_digest(org)
            if not on_demand and d["nothing"]:
                continue
            try:
                import base64 as _b64
                map_raw, map_sum = await _build_board_access_map_pdf(oid, org)
                if map_sum.get("located"):
                    d["att"] = (d.get("att") or []) + [{"filename": "obserra-board-access-map.pdf",
                                                        "content": _b64.b64encode(map_raw).decode()}]
            except Exception:
                pass
            for rr in d["recips"]:
                try:
                    await notifications.send_email(rr["email"], d["subject"], d["html"], attachments=d["att"])
                    total_sent += 1
                except Exception:
                    pass
            if scheduled:
                await db.organizations.update_one({"_id": ObjectId(oid)}, {"$set": {"board_digest_last_sent": ym}})
            try:
                await notifications.create(oid, "system", "Board Evidence Digest sent", d["summary"], ref="agentic-ai-security")
            except Exception:
                pass
        except Exception:
            pass
    return {"sent": total_sent}


@agents_router.post("/runtime/board-evidence-digest/send")
async def send_board_evidence_digest(admin: dict = Depends(require_roles("admin"))):
    result = await _run_board_evidence_digest(org_id=admin["org_id"], on_demand=True)
    await _log_audit(admin["org_id"], admin["email"], "agent.board_evidence_digest",
                     f"Board evidence digest emailed ({result.get('sent', 0)} recipient(s))")
    return result


@agents_router.get("/runtime/snapshot-status")
async def snapshot_status(admin: dict = Depends(require_roles("admin"))):
    """How much SNAPSHOT demo data remains + whether a genuinely live enterprise source is connected (gate)."""
    oid = admin["org_id"]
    incidents = await db.ai_incidents.count_documents({"org_id": oid, "demo_label": "SNAPSHOT"})
    live = await db.connectors.find_one({"org_id": oid, "status": "connected",
                                         "sync_mode": {"$nin": ["SNAPSHOT", None, ""]}})
    return {"snapshot_incidents": incidents, "live_source_connected": bool(live),
            "live_source": (live or {}).get("name") or (live or {}).get("provider") or ""}


@agents_router.post("/runtime/retire-snapshots")
async def retire_snapshots(admin: dict = Depends(require_roles("admin"))):
    """Purge SNAPSHOT-tagged demo seed data — GATED: refuses until a genuinely live enterprise source is
    connected, so dashboards are never emptied before real data flows in (the 'all live' directive)."""
    oid = admin["org_id"]
    live = await db.connectors.find_one({"org_id": oid, "status": "connected",
                                         "sync_mode": {"$nin": ["SNAPSHOT", None, ""]}})
    if not live:
        raise HTTPException(409, "Connect and verify a live enterprise source (e.g. Microsoft Entra) before retiring the demo snapshot data.")
    res = await db.ai_incidents.delete_many({"org_id": oid, "demo_label": "SNAPSHOT"})
    src = (live or {}).get("name") or (live or {}).get("provider") or "source"
    await _log_audit(oid, admin["email"], "agent.retire_snapshots",
                     f"Retired {res.deleted_count} SNAPSHOT demo record(s) after live source '{src}' confirmed")
    return {"retired": res.deleted_count, "live_source": src}


# ── Auditor question SLA (org setting + overdue nudge, folded into the daily cron) ──
async def _question_sla_hours(org_id):
    from bson import ObjectId
    try:
        org = await db.organizations.find_one({"_id": ObjectId(org_id)}, {"auditor_question_sla_hours": 1}) or {}
        return int(org.get("auditor_question_sla_hours") or 48)
    except Exception:
        return 48


async def _run_auditor_question_sla_nudge():
    """Folded into the daily cron: nudge admins/execs about auditor questions still open past the org SLA."""
    import os
    from datetime import datetime, timezone, timedelta
    from bson import ObjectId
    now = datetime.now(timezone.utc)
    pending = await db.evidence_room_comments.find(
        {"status": {"$ne": "Resolved"}, "sla_nudged": {"$exists": False}}, {"_id": 0}).to_list(5000)
    by_org = {}
    org_cache = {}
    for q in pending:
        try:
            if not q.get("at"):
                continue
            oid = q["org_id"]
            if oid not in org_cache:
                org_cache[oid] = await db.organizations.find_one({"_id": ObjectId(oid)}) or {}
            sla = _sla_for(org_cache[oid], q.get("priority"))
            if now <= datetime.fromisoformat(q["at"]) + timedelta(hours=sla):
                continue
            by_org.setdefault(oid, []).append(q)
        except Exception:
            pass
    frontend = os.environ.get("FRONTEND_URL", "").rstrip("/")
    for oid, qs in by_org.items():
        try:
            org = await db.organizations.find_one({"_id": ObjectId(oid)}) or {}
            oname = org.get("name") or "your organization"
            rows = "".join(
                f"<tr><td style='padding:6px 0;border-bottom:1px solid #eee;font:400 13px Arial;color:#1f2937'>"
                f"<b>{(q.get('author') or 'Auditor')}</b>: {(q.get('text') or '')[:160]}</td></tr>" for q in qs[:20])
            html = (f"<div style='font:400 14px Arial;color:#1f2937;max-width:560px;margin:auto'>"
                    f"<h2 style='color:#b45309'>Auditor questions past SLA</h2>"
                    f"<p><strong>{len(qs)}</strong> auditor question(s) for <strong>{oname}</strong> are still unanswered beyond your target response time.</p>"
                    f"<table width='100%'>{rows}</table>"
                    f"<p style='margin:18px 0'><a href='{frontend}/app/agentic-ai-security' style='background:#12b4d6;color:#04121a;text-decoration:none;padding:11px 18px;border-radius:8px;font-weight:700' target='_blank'>Open the Auditor questions inbox</a></p>"
                    f"<p style='font-size:11px;color:#9ca3af'>Obserra — Agentic AI Security Control & Governance</p></div>")
            await _notify_org_staff(oid, "Auditor questions past SLA — Obserra", html,
                                    "Auditor questions past SLA",
                                    f"{len(qs)} auditor question(s) unanswered past your SLA — respond to keep the audit moving.",
                                    dedupe_key=f"auditor-sla:{oid}:{now.strftime('%Y-%m-%d')}")
            await db.evidence_room_comments.update_many(
                {"id": {"$in": [q["id"] for q in qs]}}, {"$set": {"sla_nudged": now.isoformat()}})
        except Exception:
            pass


async def _run_auditor_question_escalation():
    """Folded into the daily cron: if a question stays open past its per-priority escalation threshold
    (per-priority SLA × the org multiplier, default 2×), escalate to the weekly on-call approver
    (rotation), else the configured second approver, else executives — so nothing slips."""
    import os
    from datetime import datetime, timezone, timedelta
    from bson import ObjectId
    now = datetime.now(timezone.utc)
    pending = await db.evidence_room_comments.find(
        {"status": {"$ne": "Resolved"}, "escalated": {"$exists": False}}, {"_id": 0}).to_list(5000)
    org_cache = {}
    by_org = {}
    for q in pending:
        try:
            if not q.get("at"):
                continue
            oid = q["org_id"]
            if oid not in org_cache:
                org_cache[oid] = await db.organizations.find_one({"_id": ObjectId(oid)}) or {}
            org = org_cache[oid]
            esc_h = _escalation_hours_for(org, q.get("priority"))
            if now <= datetime.fromisoformat(q["at"]) + timedelta(hours=esc_h):
                continue
            to = _oncall_recipient(org) or (org.get("auditor_question_escalation_to") or "")
            bucket = by_org.setdefault(oid, {"qs": [], "to": to})
            bucket["qs"].append(q)
        except Exception:
            pass
    frontend = os.environ.get("FRONTEND_URL", "").rstrip("/")
    for oid, info in by_org.items():
        try:
            qs = info["qs"]
            to = (info["to"] or "").strip()
            org = org_cache.get(oid) or await db.organizations.find_one({"_id": ObjectId(oid)}) or {}
            oname = org.get("name") or "your organization"
            rows = "".join(
                f"<tr><td style='padding:6px 0;border-bottom:1px solid #eee;font:400 13px Arial;color:#1f2937'>"
                f"<b>{(q.get('author') or 'Auditor')}</b> <span style='color:#b91c1c;font-weight:700'>[{(q.get('priority') or 'normal').upper()}]</span>: {(q.get('text') or '')[:160]}</td></tr>" for q in qs[:20])
            html = (f"<div style='font:400 14px Arial;color:#1f2937;max-width:560px;margin:auto'>"
                    f"<h2 style='color:#b91c1c'>Escalation — auditor questions unanswered</h2>"
                    f"<p><strong>{len(qs)}</strong> auditor question(s) for <strong>{oname}</strong> have passed the escalation threshold and need a second approver's attention.</p>"
                    f"<table width='100%'>{rows}</table>"
                    f"<p style='margin:18px 0'><a href='{frontend}/app/agentic-ai-security' style='background:#12b4d6;color:#04121a;text-decoration:none;padding:11px 18px;border-radius:8px;font-weight:700' target='_blank'>Open the Auditor questions inbox</a></p>"
                    f"<p style='font-size:11px;color:#9ca3af'>Obserra — Agentic AI Security Control & Governance</p></div>")
            try:
                await notifications.create(oid, "system", "Auditor questions ESCALATED",
                                           f"{len(qs)} auditor question(s) past the escalation threshold — needs a second approver.",
                                           ref="agentic-ai-security", dedupe_key=f"auditor-esc:{oid}:{now.strftime('%Y-%m-%d')}")
            except Exception:
                pass
            if to and "@" in to:
                recips = [{"email": to}]
            else:
                recips = await db.users.find({"org_id": oid, "role": "executive"}, {"_id": 0, "email": 1}).to_list(200) \
                    or await db.users.find({"org_id": oid, "role": "admin"}, {"_id": 0, "email": 1}).to_list(200)
            for rr in recips:
                try:
                    await notifications.send_email(rr["email"], "Auditor questions escalated — Obserra", html)
                except Exception:
                    pass
            await db.evidence_room_comments.update_many(
                {"id": {"$in": [q["id"] for q in qs]}}, {"$set": {"escalated": now.isoformat()}})
        except Exception:
            pass


# ── Public auditor follow-up (two-way thread) + admin status ──────────────────
class RoomFollowupBody(BaseModel):
    author: str = ""
    text: str = ""


@agents_router.post("/public/evidence-room/{token}/comment/{cid}/message")
async def evidence_room_followup(token: str, cid: str, body: RoomFollowupBody):
    from datetime import datetime, timezone
    import html as _html
    room = await db.evidence_rooms.find_one({"token": token})
    if not room:
        raise HTTPException(404, "This auditor room link is invalid.")
    if room.get("expires_at") and datetime.now(timezone.utc).isoformat() > room["expires_at"]:
        raise HTTPException(410, "This auditor room link has expired.")
    text = (body.text or "").strip()
    if not text:
        raise HTTPException(400, "A message is required.")
    doc = await db.evidence_room_comments.find_one({"id": cid, "token": token}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Question thread not found.")
    author = (body.author or doc.get("author") or "External auditor").strip()[:120]
    now_iso = _now()
    await db.evidence_room_comments.update_one(
        {"id": cid, "token": token},
        {"$set": {"status": "Open"},
         "$push": {"messages": {"role": "auditor", "by": author, "text": text[:2000], "at": now_iso, "attachment": None}}})
    html = (f"<div style='font:400 14px Arial;color:#1f2937;max-width:560px;margin:auto'>"
            f"<h2 style='color:#0f1e3d'>New auditor follow-up</h2>"
            f"<p><strong>{_html.escape(author)}</strong> added a follow-up to their question:</p>"
            f"<blockquote style='border-left:3px solid #12b4d6;margin:0;padding:6px 14px;color:#374151'>{_html.escape(text[:1000])}</blockquote>"
            f"<p style='font-size:11px;color:#9ca3af'>Obserra — Agentic AI Security Control & Governance · Auditor questions</p></div>")
    await _notify_org_staff(doc["org_id"], "New auditor follow-up — Obserra", html,
                            "New auditor follow-up", f"{author}: {text[:200]}",
                            dedupe_key=f"auditor-followup:{cid}:{now_iso}")
    return {"ok": True}


class CommentStatusBody(BaseModel):
    id: str
    status: str | None = None
    priority: str | None = None


@agents_router.post("/runtime/evidence-room-comments/status")
async def set_evidence_comment_status(body: CommentStatusBody, admin: dict = Depends(require_roles("admin"))):
    upd = {}
    if body.status is not None:
        upd["status"] = body.status if body.status in ("Open", "Answered", "Resolved") else "Open"
    if body.priority is not None:
        p = (body.priority or "normal").strip().lower()
        upd["priority"] = p if p in ("low", "normal", "high", "urgent") else "normal"
    if not upd:
        raise HTTPException(400, "Nothing to update.")
    res = await db.evidence_room_comments.update_one(
        {"id": body.id, "org_id": admin["org_id"]}, {"$set": upd})
    if not res.matched_count:
        raise HTTPException(404, "Question not found.")
    return {"ok": True, **upd}


# ── Governance settings — board-digest schedule/recipients + auditor-question SLA ──
class GovSettingsBody(BaseModel):
    board_digest_day: int | None = None
    board_digest_recipients: list[str] | None = None
    board_digest_enabled: bool | None = None
    auditor_question_sla_hours: int | None = None
    auditor_question_escalation_hours: int | None = None
    auditor_question_escalation_to: str | None = None
    auditor_question_sla_by_priority: dict | None = None
    auditor_question_escalation_multiplier: float | None = None
    auditor_oncall_rotation: list[str] | None = None
    fire_drill_enabled: bool | None = None
    fire_drill_day: int | None = None
    fire_drill_agent_ref: str | None = None
    control_assurance_sla_enabled: bool | None = None
    control_assurance_sla_min: int | None = None
    card_engagement_cadence: str | None = None
    trusted_countries: list[str] | None = None
    trusted_ip_ranges: list[str] | None = None
    trusted_auditors: list[str] | None = None
    unusual_access_threshold: int | None = None
    instant_suspicious_alerts: bool | None = None


@agents_router.get("/runtime/governance-settings")
async def get_governance_settings(admin: dict = Depends(require_roles("admin"))):
    from bson import ObjectId
    org = await db.organizations.find_one({"_id": ObjectId(admin["org_id"])}) or {}
    sla = int(org.get("auditor_question_sla_hours") or 48)
    return {"board_digest_day": int(org.get("board_digest_day") or 1),
            "board_digest_recipients": org.get("board_digest_recipients") or [],
            "board_digest_enabled": bool(org.get("board_digest_enabled", True)),
            "auditor_question_sla_hours": sla,
            "auditor_question_escalation_hours": int(org.get("auditor_question_escalation_hours") or sla * 2),
            "auditor_question_escalation_to": org.get("auditor_question_escalation_to") or "",
            "auditor_question_sla_by_priority": {p: _sla_for(org, p) for p in ("urgent", "high", "normal", "low")},
            "auditor_question_escalation_multiplier": float(org.get("auditor_question_escalation_multiplier") or 2),
            "auditor_oncall_rotation": org.get("auditor_oncall_rotation") or [],
            "fire_drill_enabled": bool(org.get("fire_drill_enabled", False)),
            "fire_drill_day": int(org.get("fire_drill_day") or 1),
            "fire_drill_agent_ref": org.get("fire_drill_agent_ref") or "",
            "control_assurance_sla_enabled": bool(org.get("control_assurance_sla_enabled", False)),
            "control_assurance_sla_min": int(org.get("control_assurance_sla_min") or 90),
            "card_engagement_cadence": org.get("card_engagement_cadence") or "instant",
            "trusted_countries": org.get("trusted_countries") or [],
            "trusted_ip_ranges": org.get("trusted_ip_ranges") or [],
            "trusted_auditors": org.get("trusted_auditors") or [],
            "unusual_access_threshold": int(org.get("unusual_access_threshold") or 1),
            "instant_suspicious_alerts": bool(org.get("instant_suspicious_alerts"))}


@agents_router.put("/runtime/governance-settings")
async def set_governance_settings(body: GovSettingsBody, admin: dict = Depends(require_roles("admin"))):
    from bson import ObjectId
    upd = {}
    if body.board_digest_day is not None:
        upd["board_digest_day"] = max(1, min(28, int(body.board_digest_day)))
    if body.board_digest_recipients is not None:
        upd["board_digest_recipients"] = [e.strip() for e in body.board_digest_recipients if e and "@" in e][:50]
    if body.board_digest_enabled is not None:
        upd["board_digest_enabled"] = bool(body.board_digest_enabled)
    if body.auditor_question_sla_hours is not None:
        upd["auditor_question_sla_hours"] = max(1, min(720, int(body.auditor_question_sla_hours)))
    if body.auditor_question_escalation_hours is not None:
        upd["auditor_question_escalation_hours"] = max(1, min(2160, int(body.auditor_question_escalation_hours)))
    if body.auditor_question_escalation_to is not None:
        to = (body.auditor_question_escalation_to or "").strip()
        upd["auditor_question_escalation_to"] = to if "@" in to else ""
    if body.auditor_question_sla_by_priority is not None:
        clean = {}
        for p in ("urgent", "high", "normal", "low"):
            v = body.auditor_question_sla_by_priority.get(p)
            if v is not None:
                try:
                    clean[p] = max(1, min(4320, int(v)))
                except Exception:
                    pass
        upd["auditor_question_sla_by_priority"] = clean
    if body.auditor_question_escalation_multiplier is not None:
        upd["auditor_question_escalation_multiplier"] = max(1.0, min(20.0, float(body.auditor_question_escalation_multiplier)))
    if body.auditor_oncall_rotation is not None:
        upd["auditor_oncall_rotation"] = [e.strip() for e in body.auditor_oncall_rotation if e and "@" in e][:50]
    if body.fire_drill_enabled is not None:
        upd["fire_drill_enabled"] = bool(body.fire_drill_enabled)
    if body.fire_drill_day is not None:
        upd["fire_drill_day"] = max(1, min(28, int(body.fire_drill_day)))
    if body.fire_drill_agent_ref is not None:
        upd["fire_drill_agent_ref"] = (body.fire_drill_agent_ref or "").strip()
    if body.control_assurance_sla_enabled is not None:
        upd["control_assurance_sla_enabled"] = bool(body.control_assurance_sla_enabled)
    if body.control_assurance_sla_min is not None:
        upd["control_assurance_sla_min"] = max(1, min(100, int(body.control_assurance_sla_min)))
    if body.card_engagement_cadence is not None:
        upd["card_engagement_cadence"] = body.card_engagement_cadence if body.card_engagement_cadence in ("off", "weekly", "instant") else "instant"
    if body.trusted_countries is not None:
        seen = []
        for cty in body.trusted_countries:
            cty = (cty or "").strip()
            if cty and cty not in seen:
                seen.append(cty)
        upd["trusted_countries"] = seen[:60]
    if body.trusted_ip_ranges is not None:
        import ipaddress
        clean_ip = []
        for cidr in body.trusted_ip_ranges:
            cidr = (cidr or "").strip()
            if not cidr or cidr in clean_ip:
                continue
            try:
                if "/" in cidr:
                    ipaddress.ip_network(cidr, strict=False)
                else:
                    ipaddress.ip_address(cidr)
                clean_ip.append(cidr)
            except Exception:
                continue
        upd["trusted_ip_ranges"] = clean_ip[:60]
    if body.trusted_auditors is not None:
        seen_a = []
        for em in body.trusted_auditors:
            em = (em or "").strip().lower()
            if em and em not in seen_a:
                seen_a.append(em)
        upd["trusted_auditors"] = seen_a[:100]
    if body.unusual_access_threshold is not None:
        try:
            upd["unusual_access_threshold"] = max(1, min(1000, int(body.unusual_access_threshold)))
        except Exception:
            pass
    if body.instant_suspicious_alerts is not None:
        upd["instant_suspicious_alerts"] = bool(body.instant_suspicious_alerts)
    _prev = await db.organizations.find_one({"_id": ObjectId(admin["org_id"])},
                                            {"trusted_countries": 1, "trusted_ip_ranges": 1, "trusted_auditors": 1}) or {}
    if upd:
        await db.organizations.update_one({"_id": ObjectId(admin["org_id"])}, {"$set": upd})
    await _log_audit(admin["org_id"], admin["email"], "agent.governance_settings", "Updated AI governance settings")
    try:
        changes = []
        for _lbl, _key in (("countries", "trusted_countries"), ("networks", "trusted_ip_ranges"), ("auditors", "trusted_auditors")):
            if _key not in upd:
                continue
            _old, _new = set(_prev.get(_key) or []), set(upd.get(_key) or [])
            _added, _removed = sorted(_new - _old), sorted(_old - _new)
            if _added or _removed:
                _seg = _lbl
                if _added:
                    _seg += f" +[{', '.join(_added)}]"
                if _removed:
                    _seg += f" -[{', '.join(_removed)}]"
                changes.append(_seg)
        if changes:
            await _log_audit(admin["org_id"], admin["email"], "agent.trusted_rules_changed",
                             "Trusted access rules changed \u2014 " + "; ".join(changes))
    except Exception:
        pass
    return await get_governance_settings(admin)


@agents_router.get("/runtime/board-evidence-digest/preview")
async def preview_board_evidence_digest(admin: dict = Depends(require_roles("admin"))):
    from bson import ObjectId
    org = await db.organizations.find_one({"_id": ObjectId(admin["org_id"])})
    if not org:
        raise HTTPException(404, "Organization not found.")
    d = await _build_board_digest(org)
    return {"html": d["html"], "subject": d["subject"], "counts": d["counts"],
            "recipients": [r["email"] for r in d["recips"]], "nothing": d["nothing"]}


@agents_router.get("/runtime/board-evidence-digest/preview.pdf")
async def preview_board_evidence_digest_pdf(admin: dict = Depends(require_roles("admin"))):
    from bson import ObjectId
    from fastapi.responses import StreamingResponse
    import io
    org = await db.organizations.find_one({"_id": ObjectId(admin["org_id"])})
    if not org:
        raise HTTPException(404, "Organization not found.")
    d = await _build_board_digest(org)
    return StreamingResponse(io.BytesIO(d["pdf_bytes"]), media_type="application/pdf",
        headers={"Content-Disposition": 'inline; filename="obserra-board-digest-preview.pdf"'})


@agents_router.get("/runtime/evidence-room/{token}/access-log")
async def evidence_room_access_log(token: str, admin: dict = Depends(require_roles("admin"))):
    room = await db.evidence_rooms.find_one({"token": token, "org_id": admin["org_id"]}, {"_id": 0})
    if not room:
        raise HTTPException(404, "Auditor room not found.")
    rows = await db.evidence_room_access.find(
        {"token": token, "org_id": admin["org_id"]}, {"_id": 0}).sort("at", -1).to_list(500)
    return {"opens": room.get("opens", 0), "downloads": room.get("downloads", 0),
            "last_downloaded_by": room.get("last_downloaded_by"), "access": rows}


async def _gather_access_globe(org_id, days=None):
    """Aggregate every card-share + evidence-room access (geo-enriched, cached back) into drilldown points.
    Optional `days` (7/30/90) scopes to accesses within that recent window."""
    _match = {"org_id": org_id}
    if days:
        from datetime import datetime, timezone, timedelta
        _match["at"] = {"$gte": (datetime.now(timezone.utc) - timedelta(days=int(days))).isoformat()}
    card_rows = await db.card_share_access.find(_match, {"_id": 0}).sort("at", -1).to_list(2000)
    room_rows = await db.evidence_room_access.find(_match, {"_id": 0}).sort("at", -1).to_list(2000)
    need = sorted({r.get("ip") for r in (card_rows + room_rows)
                   if r.get("ip") and r.get("geo_lat") is None})
    geo_map = await _geo_lookup_many(need) if need else {}

    async def _cache(rows, coll):
        for r in rows:
            g = geo_map.get(r.get("ip"))
            if g and r.get("geo_lat") is None:
                r["geo"] = r.get("geo") or g.get("loc") or ""
                r["geo_lat"] = g.get("lat")
                r["geo_lon"] = g.get("lon")
                try:
                    await coll.update_one(
                        {"token": r.get("token"), "org_id": org_id, "ip": r["ip"], "at": r["at"]},
                        {"$set": {"geo": r["geo"], "geo_lat": r["geo_lat"], "geo_lon": r["geo_lon"]}})
                except Exception:
                    pass
    await _cache(card_rows, db.card_share_access)
    await _cache(room_rows, db.evidence_room_access)
    for r in card_rows:
        r["source"] = "card"
    for r in room_rows:
        r["source"] = "room"
    all_rows = card_rows + room_rows
    from bson import ObjectId as _OID2
    _org = await db.organizations.find_one({"_id": _OID2(org_id)}, {"trusted_countries": 1, "trusted_ip_ranges": 1, "trusted_auditors": 1}) if org_id else None
    _tc = {(c or "").strip().lower() for c in ((_org or {}).get("trusted_countries") or [])}
    _tips = (_org or {}).get("trusted_ip_ranges") or []
    _tauds = {(a or "").strip().lower() for a in ((_org or {}).get("trusted_auditors") or [])}
    _has_trust = bool(_tc or _tips)
    tokens = list({r.get("token") for r in all_rows if r.get("token")})
    label_map = {}
    if tokens:
        for cd in await db.card_shares.find({"org_id": org_id, "token": {"$in": tokens}}, {"_id": 0, "token": 1, "snapshot": 1}).to_list(2000):
            snap = cd.get("snapshot") or {}
            label_map[cd["token"]] = (snap.get("title") or "Detail card") + (f" ({snap.get('ref')})" if snap.get("ref") else "")
        for rd in await db.evidence_rooms.find({"org_id": org_id, "token": {"$in": tokens}}, {"_id": 0, "token": 1}).to_list(2000):
            label_map.setdefault(rd["token"], "Auditor room")
    points, countries = [], set()
    for r in all_rows:
        lat, lon = r.get("geo_lat"), r.get("geo_lon")
        if isinstance(lat, (int, float)) and isinstance(lon, (int, float)):
            title = label_map.get(r.get("token")) or ("Detail card" if r.get("source") == "card" else "Auditor room")
            _ctry = r["geo"].split(",")[-1].strip() if r.get("geo") else ""
            _susp = bool(_has_trust and _access_suspicious(r, _tc, _tips, _tauds))
            points.append({"lat": lat, "lon": lon, "kind": r.get("kind") or "open",
                           "anomaly": bool(r.get("anomaly")), "suspicious": _susp, "label": r.get("geo") or "",
                           "who": r.get("who") or "", "device": _parse_ua(r.get("ua") or "") or "",
                           "ip": r.get("ip") or "", "at": r.get("at") or "",
                           "source": r.get("source"), "title": title, "token": r.get("token") or ""})
            if _ctry:
                countries.add(_ctry)
    summary = {"total": len(all_rows),
               "opens": sum(1 for r in all_rows if r.get("kind") == "open"),
               "downloads": sum(1 for r in all_rows if r.get("kind") == "download"),
               "located": len(points), "countries": sorted(c for c in countries if c),
               "suspicious": sum(1 for p in points if p.get("suspicious")), "has_trust": _has_trust,
               "cards": len(card_rows), "rooms": len(room_rows)}
    return points, summary, all_rows


@agents_router.get("/runtime/access-globe")
async def access_globe(days: int | None = None, admin: dict = Depends(require_roles("admin"))):
    """Org-wide evidence-access globe with per-point drilldown (who / device / source / card|room).
    Optional ?days=7|30|90 scopes the pins to a recent window (default: all-time)."""
    d = days if days in (1, 7, 30, 90) else None
    points, summary, _ = await _gather_access_globe(admin["org_id"], days=d)
    return {"points": points, **summary, "days": d}


@agents_router.get("/runtime/watchtower")
async def watchtower(admin: dict = Depends(require_roles("admin"))):
    """Live count of suspicious (outside-trusted) evidence accesses in the last 24h — for the sidebar badge."""
    from datetime import datetime, timezone, timedelta
    from bson import ObjectId
    oid = admin["org_id"]
    org = await db.organizations.find_one(
        {"_id": ObjectId(oid)},
        {"trusted_countries": 1, "trusted_ip_ranges": 1, "trusted_auditors": 1}) or {}
    tc = {(c or "").strip().lower() for c in (org.get("trusted_countries") or [])}
    tips = org.get("trusted_ip_ranges") or []
    tauds = {(a or "").strip().lower() for a in (org.get("trusted_auditors") or [])}
    if not (tc or tips):
        return {"count": 0, "has_trust": False}
    since = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
    rows = (await db.card_share_access.find({"org_id": oid, "at": {"$gte": since}}, {"_id": 0}).to_list(5000)) \
        + (await db.evidence_room_access.find({"org_id": oid, "at": {"$gte": since}}, {"_id": 0}).to_list(5000))
    count = sum(1 for r in rows if _access_suspicious(r, tc, tips, tauds))
    return {"count": count, "has_trust": True}


async def _build_board_access_map_pdf(org_id, org=None):
    """Board Access Map PDF bytes — worldwide evidence-access map + locations list, branded + sealed.
    Returns (raw_bytes, summary)."""
    import json as _json, hashlib as _hl
    from datetime import datetime, timezone
    from reports import _build_pdf, _resolve_brand
    from agent_reports import _stamp_verified_seal
    from bson import ObjectId
    _points, summary, all_rows = await _gather_access_globe(org_id)
    if org is None:
        org = await db.organizations.find_one({"_id": ObjectId(org_id)}) or {}
    try:
        brand = _resolve_brand(org)
    except Exception:
        brand = None
    now = datetime.now(timezone.utc)
    geo_rows = [r for r in all_rows if isinstance(r.get("geo_lat"), (int, float)) and isinstance(r.get("geo_lon"), (int, float))]
    clusters = sorted(_map_clusters(geo_rows), key=lambda c: c["count"], reverse=True)
    lines = [f"Generated {now.strftime('%B %d, %Y %H:%M UTC')} \u2014 every place your shared detail-cards and auditor rooms have been accessed.",
             f"**Total accesses:** {summary['total']} ({summary['opens']} opens \u00b7 {summary['downloads']} downloads) "
             f"\u00b7 **located:** {summary['located']} \u00b7 **countries:** {len(summary['countries'])} "
             f"\u00b7 **sources:** {summary['cards']} card / {summary['rooms']} room.", ""]
    if summary.get("has_trust"):
        lines += [f"**Unusual (outside trusted zones):** {summary.get('suspicious', 0)} access(es).", ""]
    if summary["countries"]:
        lines += ["**Countries:** " + ", ".join(summary["countries"]), ""]
    lines.append("## Access locations")
    if clusters:
        for c in clusters:
            lines.append(f"- **{c.get('label') or 'Unknown location'}** \u2014 {c['count']} access(es)"
                         + (f", {c['downloads']} download(s)" if c.get("downloads") else "")
                         + (" \u00b7 \u26a0 anomaly seen" if c.get("anomaly") else ""))
    else:
        lines.append("No geo-located access recorded yet.")
    buf = _build_pdf("\n".join(lines), "Board Access Map", cover=True, org_name=org.get("name"), brand=brand,
                     exec_summary=f"Evidence opened from {len(summary['countries'])} countr(y/ies) across {summary['located']} geo-located access event(s).")
    raw = buf.getvalue()
    raw = _append_custody_map_page(raw, geo_rows, title="Evidence access map \u2014 worldwide")
    seal = _hl.sha256(_json.dumps(summary, sort_keys=True, default=str).encode()).hexdigest()
    try:
        raw = await _brand_watermark_pdf(raw, org_id=org_id, room_url="",
            subtext=f"Board Access Map \u00b7 {summary['total']} accesses \u00b7 {len(summary['countries'])} countries")
        raw = _stamp_verified_seal(raw, seal)
    except Exception:
        pass
    return raw, summary


@agents_router.get("/runtime/access-globe.pdf")
async def access_globe_pdf(admin: dict = Depends(require_roles("admin"))):
    """Board Access Map — a branded, sealed PDF of everywhere this org's evidence has been opened worldwide."""
    import io
    from datetime import datetime, timezone
    from fastapi.responses import StreamingResponse
    raw, _summary = await _build_board_access_map_pdf(admin["org_id"])
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M")
    return StreamingResponse(io.BytesIO(raw), media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="obserra-board-access-map-{stamp}.pdf"'})


@agents_router.get("/runtime/webhook/playbooks")
async def runtime_webhook_playbooks(admin: dict = Depends(require_roles("admin"))):
    """Reference templates showing how to translate the signed Obserra enforcement webhook into each
    runtime's stop/pause/resume API — prefilled with this org's own webhook URL + signing secret."""
    from bson import ObjectId
    org = await db.organizations.find_one(
        {"_id": ObjectId(admin["org_id"])},
        {"agent_runtime_webhook": 1, "agent_runtime_webhook_secret": 1, "agent_runtime_webhook_managed": 1}) or {}
    return {"payload": {"agent_ref": "AGT-001", "action": "kill|suspend|resume", "mode": "hard|soft",
                        "org_id": "<org>", "event": "obserra.runtime.enforce", "at": "<iso8601>"},
            "headers": {"X-Obserra-Signature": "sha256=<hmac of the raw body>", "X-Obserra-Timestamp": "<iso8601>"},
            "webhook_url": org.get("agent_runtime_webhook") or "",
            "signing_secret": org.get("agent_runtime_webhook_secret") or "",
            "managed": org.get("agent_runtime_webhook_managed") or "",
            "playbooks": _RUNTIME_PLAYBOOKS}


# ── Branded, tamper-evident watermark (org logo + QR back to the live room) ────
# ---- One-tap bulk 'Neutralise' from the Toxicity Map ----
class BulkEnforceBody(BaseModel):
    action: str = "suspend"      # suspend | kill
    selector: str = "toxic"      # toxic | all
    refs: list[str] | None = None


@agents_router.post("/runtime/enforce-bulk")
async def enforce_bulk(body: BulkEnforceBody, admin: dict = Depends(require_roles("admin"))):
    """Neutralise every red-flagged agent in one tap. Enforces `action` (suspend or kill) on the given
    `refs`, or on all currently-toxic agents (selector='toxic'), or every live agent (selector='all')."""
    action = (body.action or "suspend").lower()
    if action not in ("suspend", "kill"):
        raise HTTPException(400, "Bulk action must be 'suspend' or 'kill'.")
    agents = await db.ai_agents.find({"org_id": admin["org_id"]}, {"_id": 0}).to_list(500)
    if body.refs:
        wanted = set(body.refs)
        targets = [a for a in agents if a.get("ref") in wanted and a.get("status") != "killed"]
    elif body.selector == "all":
        targets = [a for a in agents if a.get("status") != "killed"]
    else:
        targets = [a for a in agents if _is_toxic(a)]
    results = []
    for a in targets:
        try:
            res = await _do_enforce(admin["org_id"], admin["email"], a["ref"], action, source="bulk-neutralise")
            results.append({"ref": a["ref"], "name": a.get("name"), "status": res["agent"]["status"]})
        except Exception:
            pass
    return {"ok": True, "count": len(results), "action": action, "agents": results}


# ---- AI Security Executive Board Brief (Resend email + cron cadence) ----
_DANGER_TOOLS = {"shell.exec", "cloud.admin", "iam.write"}
_ACTION_TOKENS = (".write", ".send", ".exec", ".admin", ".delete", ".create", ".update",
                  "shell", "deploy", "publish", "approve", "payment")


def _is_action_tool(t):
    t = str(t).lower()
    return any(tok in t for tok in _ACTION_TOKENS)


def _guard_pct(a):
    g = a.get("guardrails") or {}
    keys = ["input_filtering", "output_filtering", "tool_allowlist", "human_in_loop"]
    return round(sum(1 for k in keys if g.get(k)) / len(keys) * 100)


def _agent_authority(a):
    if a.get("status") == "killed":
        return "Disabled"
    action = [t for t in (a.get("tools") or []) if _is_action_tool(t)]
    human = bool((a.get("guardrails") or {}).get("human_in_loop"))
    if action and not human:
        return "Autonomous"
    if action and human:
        return "Approval Required"
    if a.get("tools"):
        return "Tool Assisted"
    return "Observe"


def _is_toxic(a):
    g = a.get("guardrails") or {}
    tools = a.get("tools") or []
    if a.get("status") == "killed":
        return False
    dangerous = [t for t in tools if t in _DANGER_TOOLS]
    action = [t for t in tools if _is_action_tool(t)]
    if dangerous and not g.get("tool_allowlist"):
        return True
    if action and not g.get("human_in_loop") and not g.get("tool_allowlist"):
        return True
    return False


def _agent_risk(a):
    if a.get("status") == "killed":
        return 0
    base = {"Critical": 90, "High": 74, "Medium": 52, "Low": 28}.get(a.get("risk_class"), 50)
    g = a.get("guardrails") or {}
    gaps = sum(1 for k in ["input_filtering", "output_filtering", "tool_allowlist", "human_in_loop"] if not g.get(k))
    base += gaps * 4 + min(12, len(_tool_violations(a)) * 8)
    if _agent_authority(a) == "Autonomous":
        base += 10
    if a.get("status") == "shadow":
        base += 8
    return max(0, min(100, round(base)))


async def _brief_rollup(org_id):
    agents = await db.ai_agents.find({"org_id": org_id}, {"_id": 0}).to_list(500)
    systems = await db.ai_systems.find({"org_id": org_id}, {"_id": 0}).to_list(500)
    incidents = await db.ai_incidents.find({"org_id": org_id}, {"_id": 0}).to_list(500)
    total = len(agents)
    top = sorted(agents, key=_agent_risk, reverse=True)[:5]
    return {"total": total,
            "avg_risk": round(sum(_agent_risk(a) for a in agents) / total) if total else 0,
            "autonomous": sum(1 for a in agents if _agent_authority(a) == "Autonomous"),
            "toxic": sum(1 for a in agents if _is_toxic(a)),
            "weak_guardrails": sum(1 for a in agents if _guard_pct(a) < 75),
            "tool_violations": sum(1 for a in agents if _tool_violations(a)),
            "shadow_ai": sum(1 for s in systems if s.get("status") == "shadow"),
            "open_incidents": sum(1 for i in incidents if str(i.get("status", "")).lower() not in ("resolved", "closed", "remediated")),
            "top": [{"ref": a["ref"], "name": a["name"], "risk": _agent_risk(a),
                     "authority": _agent_authority(a), "risk_class": a.get("risk_class")} for a in top]}


def _brief_html(org_name, r):
    rows = "".join(
        f'<tr><td style="padding:6px 8px;border-bottom:1px solid #eee;font:400 13px Arial">{t["name"]} '
        f'<span style="color:#6b7280;font-size:11px">{t["ref"]}</span></td>'
        f'<td style="padding:6px 8px;border-bottom:1px solid #eee;font:700 13px Arial;color:#0f1e3d;text-align:right">{t["risk"]}/100</td>'
        f'<td style="padding:6px 8px;border-bottom:1px solid #eee;font:400 12px Arial;color:#6b7280;text-align:right">{t["authority"]}</td></tr>'
        for t in r["top"]) or '<tr><td style="padding:8px;font:400 13px Arial;color:#6b7280">No agents registered</td></tr>'

    def kpi(label, val, color="#0f1e3d"):
        return (f'<td style="padding:10px;text-align:center;border:1px solid #eef">'
                f'<div style="font:800 24px Arial;color:{color}">{val}</div>'
                f'<div style="font:400 10px Arial;color:#6b7280;text-transform:uppercase;letter-spacing:.06em">{label}</div></td>')
    return (
        '<div style="font:400 14px Arial;color:#1f2937;max-width:640px;margin:auto">'
        '<h2 style="color:#0f1e3d;margin:0">Agentic AI Security — Executive Brief</h2>'
        f'<div style="font:400 12px Arial;color:#6b7280;margin:4px 0 16px">{org_name} · machine authority intelligence</div>'
        '<table style="width:100%;border-collapse:collapse;margin-bottom:6px"><tr>'
        + kpi("Agents", r["total"]) + kpi("Avg risk", f'{r["avg_risk"]}/100', "#b45309")
        + kpi("Autonomous", r["autonomous"], "#dc2626") + kpi("Toxic combos", r["toxic"], "#dc2626")
        + '</tr><tr>' + kpi("Shadow AI", r["shadow_ai"], "#dc2626")
        + kpi("Guardrail gaps", r["weak_guardrails"], "#b45309")
        + kpi("Tool violations", r["tool_violations"], "#dc2626")
        + kpi("Open incidents", r["open_incidents"], "#b45309") + '</tr></table>'
        '<h3 style="color:#0f1e3d;margin:18px 0 4px;font-size:15px">Highest-risk AI agents</h3>'
        f'<table style="width:100%;border-collapse:collapse">{rows}</table>'
        '<p style="font:400 11px Arial;color:#9ca3af;margin-top:16px">Agent risk scores and delegated authority tiers '
        'are modelled from live Obserra agent records. Sign in to the Agentic AI Security Control & Governance for the full '
        'toxicity map, guardrail red-team evidence and one-click runtime enforcement.</p>'
        '<p style="font-size:11px;color:#9ca3af">Obserra — Executive Protection &amp; Intelligence LLC</p></div>')


async def _send_ai_brief(org_id):
    from bson import ObjectId
    org = await db.organizations.find_one({"_id": ObjectId(org_id)}) or {}
    r = await _brief_rollup(org_id)
    html = _brief_html(org.get("name") or "Obserra", r)
    recips = await db.users.find({"org_id": org_id, "role": {"$in": ["admin", "executive"]}},
                                 {"_id": 0, "email": 1}).to_list(200)
    for u in recips:
        await notifications.send_email(u["email"], "Agentic AI Security — Executive Brief", html)
    await notifications.create(org_id, "report", "AI security brief delivered",
                               f"Agentic AI Security executive brief emailed to {len(recips)} recipient(s).",
                               ref="agentic-ai-security")
    return len(recips)


class BriefSchedule(BaseModel):
    enabled: bool | None = None
    cadence: str | None = None


@agents_router.get("/board-brief/schedule")
async def get_brief_schedule(user: dict = Depends(get_current_user)):
    from bson import ObjectId
    org = await db.organizations.find_one({"_id": ObjectId(user["org_id"])}, {"ai_brief_schedule": 1}) or {}
    sch = org.get("ai_brief_schedule") or {}
    return {"enabled": bool(sch.get("enabled")), "cadence": sch.get("cadence") or "monthly"}


@agents_router.put("/board-brief/schedule")
async def set_brief_schedule(body: BriefSchedule, admin: dict = Depends(require_roles("admin"))):
    from bson import ObjectId
    sch = {"enabled": bool(body.enabled),
           "cadence": body.cadence if body.cadence in ("weekly", "monthly") else "monthly"}
    await db.organizations.update_one({"_id": ObjectId(admin["org_id"])}, {"$set": {"ai_brief_schedule": sch}})
    return sch


@agents_router.post("/board-brief/send")
async def send_brief_now(admin: dict = Depends(require_roles("admin"))):
    sent = await _send_ai_brief(admin["org_id"])
    return {"ok": True, "sent": sent}


async def _run_ai_board_brief(cadence):
    orgs = await db.organizations.find({"ai_brief_schedule.enabled": True}).to_list(1000)
    for org in orgs:
        sch = org.get("ai_brief_schedule") or {}
        if (sch.get("cadence") or "monthly") != cadence:
            continue
        try:
            await _send_ai_brief(str(org["_id"]))
        except Exception:
            pass


@agents_router.get("/public/evidence-room/{token}/integrity")
async def public_evidence_room_integrity(token: str):
    """Public tamper-evidence check — re-hash the stored evidence snapshot and compare to the hash
    captured when the room was created. Green when untampered."""
    from datetime import datetime, timezone
    doc = await db.evidence_rooms.find_one({"token": token}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "This auditor room link is invalid.")
    if doc.get("expires_at") and datetime.now(timezone.utc).isoformat() > doc["expires_at"]:
        raise HTTPException(410, "This auditor room link has expired.")
    stored = doc.get("snapshot_sha256")
    live = _canonical_snapshot_hash(doc.get("snapshot") or {})
    if not stored:
        stored = live
        await db.evidence_rooms.update_one({"token": token}, {"$set": {"snapshot_sha256": stored}})
    return {"verified": (stored == live), "algorithm": "SHA-256", "sha256": live, "short": live[:12],
            "created_at": doc.get("created_at"), "checked_at": datetime.now(timezone.utc).isoformat()}


class RoomSubscribeBody(BaseModel):
    email: str = ""


@agents_router.post("/public/evidence-room/{token}/subscribe")
async def subscribe_evidence_room_digest(token: str, body: RoomSubscribeBody):
    """Public opt-in — an auditor subscribes their email to a weekly summary of new evidence and
    answered questions in this room."""
    from datetime import datetime, timezone
    email = (body.email or "").strip().lower()[:200]
    if "@" not in email:
        raise HTTPException(400, "A valid email is required.")
    doc = await db.evidence_rooms.find_one({"token": token}, {"_id": 1, "expires_at": 1})
    if not doc:
        raise HTTPException(404, "This auditor room link is invalid.")
    if doc.get("expires_at") and datetime.now(timezone.utc).isoformat() > doc["expires_at"]:
        raise HTTPException(410, "This auditor room link has expired.")
    await db.evidence_rooms.update_one({"token": token}, {"$addToSet": {"digest_subscribers": email}})
    return {"ok": True, "subscribed": email}
