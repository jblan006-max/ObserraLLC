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
