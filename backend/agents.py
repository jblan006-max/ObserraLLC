"""AI Agent Governance — the first standalone app composed on the kernel.

Composes: Asset Model (agent inventory) · Policy Engine (tool/permission
governance) · Obserrian AI + AI Context Engine (red-team) · Workflow Engine
(finding remediation) · Notification Engine (alerts) · Audit Ledger.

Red-team scoring is heuristic/deterministic (MOCKED evaluation) — it inspects
each agent's guardrails rather than calling a live model, so runs are fast,
free and reproducible.
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from auth import get_current_user, require_roles, _log_audit
from db import db
from kernel import notifications, workflows

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
        f"This evidence pack was generated by Obserra — Agentic AI Security Control Plane for "
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
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M")
    return StreamingResponse(buf, media_type="application/pdf",
                             headers={"Content-Disposition": f'attachment; filename="obserra-evidence-pack-{stamp}.pdf"'})


# ── Auditor room — shareable, expiring, read-only evidence pack (no login) ────
async def _evidence_snapshot(org_id):
    from datetime import datetime, timezone
    from bson import ObjectId
    org = await db.organizations.find_one(
        {"_id": ObjectId(org_id)}, {"name": 1, "agent_runtime_webhook": 1, "agent_runtime_webhook_secret": 1}) or {}
    agents = await db.ai_agents.find({"org_id": org_id}, {"_id": 0}).to_list(500)
    events = await db.agent_enforcements.find({"org_id": org_id}, {"_id": 0}).sort("at", -1).to_list(1000)
    for a in agents:
        a["tool_violations"] = _tool_violations(a)
        a["toxic"] = _is_toxic(a)
    signed = "HMAC-signed" if org.get("agent_runtime_webhook_secret") else "unsigned"
    connector = f"connected ({signed})" if org.get("agent_runtime_webhook") else "control-plane only"
    return {"org_name": org.get("name"), "connector": connector,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "agents": agents, "events": events,
            "counts": {"agents": len(agents), "toxic": sum(1 for a in agents if a["toxic"]),
                       "killed": sum(1 for a in agents if a.get("status") == "killed"),
                       "restricted": sum(1 for a in agents if a.get("status") == "restricted"),
                       "events": len(events)}}


def _evidence_markdown(snap):
    c = snap.get("counts", {})
    lines = [
        "## Attestation",
        f"Generated by Obserra — Agentic AI Security Control Plane for {snap.get('org_name') or 'the organization'} "
        f"on {snap.get('generated_at')}. Runtime connector: {snap.get('connector')}. Every enforcement below "
        "carries a runtime receipt.", "",
        "## AI Agent Toxicity Snapshot",
        f"{c.get('agents', 0)} governed agent(s) · {c.get('toxic', 0)} toxic · {c.get('killed', 0)} killed · "
        f"{c.get('restricted', 0)} restricted.", ""]
    for a in snap.get("agents", []):
        tv = a.get("tool_violations") or []
        lines.append(f"## {a.get('name')} ({a.get('ref')})")
        lines += [f"Status: {a.get('status')} · authority: {a.get('authority', '—')}",
                  "Toxic combination: " + (("YES — " + ", ".join(tv)) if tv else "none detected"), ""]
    lines += ["## Runtime Enforcement Audit Trail", f"{c.get('events', 0)} enforcement event(s) recorded.", ""]
    for e in snap.get("events", []):
        rc = e.get("receipt") or {}
        runtime = ("runtime OK" if e.get("external_ok") else
                   ("runtime UNREACHABLE" if e.get("runtime") == "external-webhook" else "control-plane"))
        lines.append(f"## {e.get('name') or e.get('ref')} — {(e.get('verb') or e.get('action') or '').upper()}")
        lines += [f"When: {e.get('at')} · by {e.get('by')} · via {e.get('source')}",
                  "Receipt: " + runtime + (f" · HTTP {rc.get('status_code')} · {rc.get('latency_ms')}ms · "
                  f"{rc.get('attempts')} attempt(s) · {'signed' if rc.get('signed') else 'unsigned'}" if rc else ""), ""]
    return "\n".join(lines)


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
    await db.evidence_rooms.insert_one({"token": token, "org_id": admin["org_id"], "snapshot": snap,
        "created_at": now.isoformat(), "created_by": admin["email"], "expires_at": expires, "opens": 0})
    await _log_audit(admin["org_id"], admin["email"], "agent.evidence_room",
                     f"Read-only auditor room created (expires {expires[:10]})")
    frontend = os.environ.get("FRONTEND_URL", "").rstrip("/")
    return {"token": token, "url": f"{frontend}/audit-room/{token}", "expires_at": expires, "days": days}


@agents_router.get("/runtime/evidence-rooms")
async def list_evidence_rooms(admin: dict = Depends(require_roles("admin"))):
    import os
    from datetime import datetime, timezone
    frontend = os.environ.get("FRONTEND_URL", "").rstrip("/")
    now = datetime.now(timezone.utc).isoformat()
    rooms = []
    async for d in db.evidence_rooms.find({"org_id": admin["org_id"]}).sort("created_at", -1):
        rooms.append({
            "token": d["token"],
            "url": f"{frontend}/audit-room/{d['token']}",
            "created_at": d.get("created_at"),
            "created_by": d.get("created_by"),
            "expires_at": d.get("expires_at"),
            "opens": d.get("opens", 0),
            "expired": bool(d.get("expires_at") and now > d["expires_at"]),
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
async def public_evidence_room(token: str):
    from datetime import datetime, timezone
    doc = await db.evidence_rooms.find_one({"token": token}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "This auditor room link is invalid.")
    if doc.get("expires_at") and datetime.now(timezone.utc).isoformat() > doc["expires_at"]:
        raise HTTPException(410, "This auditor room link has expired.")
    await db.evidence_rooms.update_one({"token": token},
        {"$inc": {"opens": 1}, "$set": {"last_opened_at": datetime.now(timezone.utc).isoformat()}})
    return {"snapshot": doc["snapshot"], "created_at": doc.get("created_at"), "expires_at": doc.get("expires_at")}


@agents_router.get("/public/evidence-room/{token}/pack.pdf")
async def public_evidence_room_pdf(token: str, who: str = ""):
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
    buf = _build_pdf(_evidence_markdown(snap), "AI Enforcement Evidence Pack", cover=True,
                     org_name=snap.get("org_name"),
                     exec_summary=f"{c.get('agents', 0)} governed agents, {c.get('toxic', 0)} toxic; "
                                  f"{c.get('events', 0)} runtime enforcement actions with verifiable receipts.")
    raw = buf.getvalue()
    # Tamper-evident provenance watermark — who downloaded it, when, and the link expiry.
    try:
        from deploy import _watermark_pdf
        auditor = (who or "").strip()[:120] or "External auditor"
        access = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        raw = _watermark_pdf(raw, "AUDITOR ROOM COPY",
                             f"Downloaded by {auditor} · {access} · link expires {(doc.get('expires_at') or '')[:10]}")
        await db.evidence_rooms.update_one(
            {"token": token},
            {"$inc": {"downloads": 1},
             "$set": {"last_downloaded_at": datetime.now(timezone.utc).isoformat(), "last_downloaded_by": auditor}})
    except Exception:
        pass
    return StreamingResponse(io.BytesIO(raw), media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="obserra-evidence-pack.pdf"'})


# ── Auditor notes — external auditors leave read-only questions on the public room ──
class RoomCommentBody(BaseModel):
    author: str = ""
    email: str | None = ""
    text: str = ""


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
    org_id = doc["org_id"]
    cid = secrets.token_urlsafe(9)
    await db.evidence_room_comments.insert_one({
        "id": cid, "token": token, "org_id": org_id, "author": author, "author_email": author_email,
        "text": text[:2000], "at": _now(), "status": "Open", "reply": None, "reply_by": None, "reply_at": None})
    await db.evidence_rooms.update_one({"token": token}, {"$inc": {"comments": 1}})
    html = (f"<div style='font:400 14px Arial;color:#1f2937;max-width:560px;margin:auto'>"
            f"<h2 style='color:#0f1e3d'>New auditor question</h2>"
            f"<p><strong>{_html.escape(author)}</strong> asked a question in your AI Enforcement Evidence auditor room:</p>"
            f"<blockquote style='border-left:3px solid #12b4d6;margin:0;padding:6px 14px;color:#374151'>{_html.escape(text[:1000])}</blockquote>"
            f"<p style='font-size:11px;color:#9ca3af'>Obserra — Agentic AI Security Control Plane · Defensibility · Auditor questions</p></div>")
    await _notify_org_staff(org_id, "New auditor question — Obserra", html,
                            "New auditor question", f"{author}: {text[:200]}", dedupe_key=f"auditor-q:{cid}")
    return {"ok": True, "id": cid}


@agents_router.get("/public/evidence-room/{token}/comments")
async def public_evidence_room_comments(token: str):
    """Public — the thread of questions + governance replies shown on the portal (no PII beyond author name)."""
    doc = await db.evidence_rooms.find_one({"token": token}, {"_id": 1})
    if not doc:
        raise HTTPException(404, "This auditor room link is invalid.")
    rows = await db.evidence_room_comments.find(
        {"token": token}, {"_id": 0, "org_id": 0, "author_email": 0, "reply_by": 0}).sort("at", 1).to_list(200)
    return {"comments": rows}


@agents_router.get("/runtime/evidence-room-comments")
async def list_evidence_room_comments(admin: dict = Depends(require_roles("admin"))):
    rows = await db.evidence_room_comments.find({"org_id": admin["org_id"]}, {"_id": 0}).sort("at", -1).to_list(200)
    return {"comments": rows}


class RoomReplyBody(BaseModel):
    id: str
    reply: str


@agents_router.post("/runtime/evidence-room-comments/reply")
async def reply_evidence_room_comment(body: RoomReplyBody, admin: dict = Depends(require_roles("admin"))):
    import html as _html
    reply = (body.reply or "").strip()
    if not reply:
        raise HTTPException(400, "A reply is required.")
    res = await db.evidence_room_comments.update_one(
        {"id": body.id, "org_id": admin["org_id"]},
        {"$set": {"reply": reply[:2000], "reply_by": admin["email"], "reply_at": _now(), "status": "Resolved"}})
    if not res.matched_count:
        raise HTTPException(404, "Question not found.")
    try:
        doc = await db.evidence_room_comments.find_one({"id": body.id, "org_id": admin["org_id"]}, {"_id": 0})
        em = (doc or {}).get("author_email") or ""
        if em and "@" in em:
            html = (f"<div style='font:400 14px Arial;color:#1f2937;max-width:560px;margin:auto'>"
                    f"<h2 style='color:#0f1e3d'>Reply to your audit question</h2>"
                    f"<p>The AI governance team replied to your question:</p>"
                    f"<blockquote style='border-left:3px solid #12b4d6;margin:0;padding:6px 14px;color:#374151'>{_html.escape(reply[:1000])}</blockquote>"
                    f"<p style='font-size:12px;color:#6b7280'>Your question: {_html.escape((doc.get('text') or '')[:300])}</p>"
                    f"<p style='font-size:11px;color:#9ca3af'>Obserra — Agentic AI Security Control Plane</p></div>")
            await notifications.send_email(em, "Reply to your audit question — Obserra", html)
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
                    f"<p style='font-size:11px;color:#9ca3af'>Obserra — Agentic AI Security Control Plane</p></div>")
            await _notify_org_staff(org_id, "Auditor Room link expiring soon — Obserra", html,
                                    "Auditor Room link expiring soon",
                                    f"An Auditor Room for {oname} expires on {exp[:10]} ({days_left}d). Renew it to keep auditor access live.",
                                    dedupe_key=f"agent-room-expiry:{token}")
            await db.evidence_rooms.update_one({"token": token}, {"$set": {"expiry_reminder_sent": nowiso}})
        except Exception:
            pass


# ── Board Evidence Digest — one-tap / monthly rollup of kills & sanctions + signed PDF ──
async def _run_board_evidence_digest(org_id=None, on_demand=False):
    """Email admins/execs a rollup of the last 30 days of AI enforcement (kills/suspends) + current toxic
    estate + sanctioned/shadow AI systems, with the signed Evidence Pack PDF attached. Monthly via cron
    (auto-skips orgs with nothing to report) or on-demand from the Defensibility tab."""
    import base64
    from datetime import datetime, timezone, timedelta
    from bson import ObjectId
    from reports import _build_pdf
    if org_id:
        org = await db.organizations.find_one({"_id": ObjectId(org_id)})
        orgs = [org] if org else []
    else:
        orgs = await db.organizations.find({}).to_list(1000)
    since = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    total_sent = 0
    for org in orgs:
        if not org:
            continue
        oid = str(org["_id"])
        try:
            events = await db.agent_enforcements.find(
                {"org_id": oid, "at": {"$gte": since}}, {"_id": 0}).to_list(2000)
            kills = sum(1 for e in events if e.get("action") == "kill")
            suspends = sum(1 for e in events if e.get("action") == "suspend")
            resumes = sum(1 for e in events if e.get("action") == "resume")
            snap = await _evidence_snapshot(oid)
            c = snap.get("counts", {})
            systems = await db.ai_systems.find({"org_id": oid}, {"_id": 0}).to_list(500)
            sanctioned_sys = sum(1 for s in systems if s.get("status") == "sanctioned")
            shadow_sys = sum(1 for s in systems if s.get("status") == "shadow")
            if not on_demand and (kills + suspends + resumes) == 0 and c.get("toxic", 0) == 0:
                continue
            buf = _build_pdf(_evidence_markdown(snap), "AI Enforcement Evidence Pack", cover=True,
                             org_name=snap.get("org_name"),
                             exec_summary=f"{c.get('agents', 0)} governed agents, {c.get('toxic', 0)} toxic; "
                                          f"{c.get('events', 0)} runtime enforcement actions with verifiable receipts.")
            att = [{"filename": "obserra-ai-enforcement-evidence.pdf",
                    "content": base64.b64encode(buf.getvalue()).decode()}]
            oname = org.get("name") or "your organization"
            row = lambda k, v, col: (f"<tr><td style='padding:8px 12px;border-bottom:1px solid #eef2f7;font:600 13px Arial;color:#374151'>{k}</td>"
                                     f"<td style='padding:8px 12px;border-bottom:1px solid #eef2f7;font:800 15px Arial;color:{col};text-align:right'>{v}</td></tr>")
            html = (f"<div style='font:400 14px Arial;color:#1f2937;max-width:600px;margin:auto'>"
                    f"<h2 style='color:#0f1e3d;margin-bottom:2px'>AI Security — Board Evidence Digest</h2>"
                    f"<div style='font:400 12px Arial;color:#6b7280;margin-bottom:14px'>{oname} · last 30 days · {datetime.now(timezone.utc).strftime('%B %Y')}</div>"
                    f"<table width='100%' cellspacing='0' cellpadding='0' style='border:1px solid #eef2f7;border-radius:10px;overflow:hidden'>"
                    f"{row('Agents killed', kills, '#dc2626')}"
                    f"{row('Agents suspended', suspends, '#d97706')}"
                    f"{row('Agents resumed', resumes, '#16a34a')}"
                    f"{row('Toxic agents (current)', c.get('toxic', 0), '#dc2626')}"
                    f"{row('Governed agents', c.get('agents', 0), '#0f1e3d')}"
                    f"{row('Sanctioned AI systems', sanctioned_sys, '#16a34a')}"
                    f"{row('Shadow AI systems', shadow_sys, '#dc2626')}"
                    f"</table>"
                    f"<p style='font:400 13px Arial;color:#374151;margin-top:14px'>The full, signed AI Enforcement Evidence Pack — with every runtime enforcement receipt and the live toxicity snapshot — is attached as a PDF for the board / audit committee.</p>"
                    f"<p style='font-size:11px;color:#9ca3af'>Obserra — Agentic AI Security Control Plane · Defensibility Ledger</p></div>")
            recips = await db.users.find({"org_id": oid, "role": {"$in": ["admin", "executive"]}},
                                         {"_id": 0, "email": 1}).to_list(200)
            for rr in recips:
                try:
                    await notifications.send_email(rr["email"], f"AI Security — Board Evidence Digest ({datetime.now(timezone.utc).strftime('%b %Y')})", html, attachments=att)
                    total_sent += 1
                except Exception:
                    pass
            try:
                await notifications.create(oid, "system", "Board Evidence Digest sent",
                                           f"{kills} kills · {suspends} suspends · {c.get('toxic', 0)} toxic agents (30d) — emailed to admins/execs with the signed PDF.",
                                           ref="agentic-ai-security")
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
        'are modelled from live Obserra agent records. Sign in to the Agentic AI Security Control Plane for the full '
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
