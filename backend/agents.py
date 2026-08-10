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
    external_ok, runtime, receipt = None, "obserra-control-plane", None
    if webhook:
        import time as _time
        runtime = "external-webhook"
        t0 = _time.perf_counter()
        try:
            async with httpx.AsyncClient(timeout=10) as c:
                r = await c.post(webhook, json={"agent_ref": ref, "action": action,
                                                "mode": m["mode"], "org_id": org_id})
            external_ok = 200 <= r.status_code < 300
            receipt = {"status_code": r.status_code, "latency_ms": round((_time.perf_counter() - t0) * 1000),
                       "response": (r.text or "")[:280], "ok": external_ok, "at": _now(), "url": webhook}
        except Exception as e:
            external_ok = False
            receipt = {"status_code": None, "latency_ms": round((_time.perf_counter() - t0) * 1000),
                       "response": "", "error": str(e)[:200], "ok": False, "at": _now(), "url": webhook}
    note = ("Enforcement dispatched to the connected agent-runtime webhook." if webhook
            else "Enforced in the Obserra control plane — the agent governance status changed and every "
                 "downstream policy check now honours it. Wire an agent-runtime webhook to push this to an "
                 "external execution environment.")
    enforcement = {"enforced": enforced, "mode": m["mode"], "action": action,
                   "runtime": runtime, "external_ok": external_ok, "note": note,
                   "receipt": receipt, "at": _now(), "by": actor, "source": source}
    await db.ai_agents.update_one({"_id": a["_id"]},
        {"$set": {"status": m["status"], "enforced": enforced, "enforcement": enforcement}})
    await _log_audit(org_id, actor, "agent.enforce",
                     f"{ref} {m['verb']} (mode {m['mode']}, via {source})")
    try:
        await db.agent_enforcements.insert_one({
            "org_id": org_id, "ref": ref, "name": a.get("name"), "action": action,
            "verb": m["verb"], "mode": m["mode"], "status": m["status"], "source": source,
            "by": actor, "runtime": runtime, "external_ok": external_ok, "receipt": receipt,
            "at": enforcement["at"]})
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


@agents_router.get("/runtime/webhook")
async def get_runtime_webhook(user: dict = Depends(get_current_user)):
    from bson import ObjectId
    org = await db.organizations.find_one({"_id": ObjectId(user["org_id"])}, {"agent_runtime_webhook": 1}) or {}
    return {"webhook": org.get("agent_runtime_webhook") or ""}


@agents_router.put("/runtime/webhook")
async def set_runtime_webhook(body: WebhookBody, admin: dict = Depends(require_roles("admin"))):
    from bson import ObjectId
    url = (body.webhook or "").strip()
    if url and not url.lower().startswith(("http://", "https://")):
        raise HTTPException(400, "Webhook must be a valid http(s) URL.")
    await db.organizations.update_one({"_id": ObjectId(admin["org_id"])},
                                      {"$set": {"agent_runtime_webhook": url}})
    await _log_audit(admin["org_id"], admin["email"], "agent.runtime_webhook",
                     "Set agent runtime webhook" if url else "Cleared agent runtime webhook")
    return {"webhook": url}


@agents_router.post("/runtime/webhook/test")
async def test_runtime_webhook(admin: dict = Depends(require_roles("admin"))):
    """Send a synthetic 'test' event to the configured agent-runtime webhook so an admin can confirm
    their execution environment actually receives Obserra enforcement before relying on it."""
    from bson import ObjectId
    import httpx, time as _time
    org = await db.organizations.find_one({"_id": ObjectId(admin["org_id"])}, {"agent_runtime_webhook": 1}) or {}
    webhook = org.get("agent_runtime_webhook")
    if not webhook:
        raise HTTPException(400, "No agent runtime webhook configured. Save a webhook URL first.")
    payload = {"agent_ref": "TEST-PING", "action": "test", "mode": "noop",
               "org_id": admin["org_id"], "event": "obserra.runtime.test", "at": _now()}
    t0 = _time.perf_counter()
    try:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.post(webhook, json=payload)
        latency = round((_time.perf_counter() - t0) * 1000)
        await _log_audit(admin["org_id"], admin["email"], "agent.runtime_webhook_test",
                         f"Test event → HTTP {r.status_code} ({latency}ms)")
        return {"ok": 200 <= r.status_code < 300, "status_code": r.status_code,
                "latency_ms": latency, "response": (r.text or "")[:280], "url": webhook}
    except Exception as e:
        latency = round((_time.perf_counter() - t0) * 1000)
        return {"ok": False, "status_code": None, "latency_ms": latency,
                "error": str(e)[:200], "url": webhook}


@agents_router.get("/runtime/enforcement-log")
async def enforcement_log(user: dict = Depends(get_current_user)):
    """Live feed of every runtime enforcement (suspend / kill / resume) — who, when, which agent,
    via advisor / bulk-neutralise / manual, and the runtime receipt."""
    rows = await db.agent_enforcements.find({"org_id": user["org_id"]}, {"_id": 0}).sort("at", -1).to_list(50)
    return {"events": rows}


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
