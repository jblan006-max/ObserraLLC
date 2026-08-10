import { Bot, Database, KeyRound, ShieldCheck, UserCheck, Wrench } from "lucide-react";
import { agentToxicity } from "@/lib/agenticToxicity";

const RATING_FROM_SCORE = (score = 0) =>
  score >= 80 ? "Critical" : score >= 60 ? "High" : score >= 40 ? "Medium" : "Low";

// Universal deep-dive item for an AI agent — matches the platform RiskDetailModal shape.
export function agentDeepDive(agent = {}) {
  const tox = agent.toxicity || agentToxicity(agent);
  const rating = agent.risk_class || RATING_FROM_SCORE(agent.modeledRisk || 0);
  return {
    accent: "330 81% 60%",
    refLabel: agent.ref,
    title: agent.name,
    rating,
    score: agent.modeledRisk,
    facets: [
      { label: "Owner", value: agent.owner, icon: UserCheck },
      { label: "Model", value: agent.model, icon: Bot },
      { label: "Authority", value: agent.authority },
      { label: "Governance status", value: agent.status },
      { label: "Guardrail coverage", value: `${agent.guardrailCoverage?.pct ?? "—"}%`, icon: ShieldCheck },
      { label: "Action-capable tools", value: (agent.actionTools || []).length, icon: Wrench },
      { label: "Permissions", value: (agent.permissions || []).join(", ") || "None", icon: KeyRound },
      { label: "Toxic combinations", value: tox.toxic ? `${tox.level} · ${tox.reasons.length} pattern(s)` : "None", icon: Database },
      ...(agent.enforcement?.receipt
        ? [{
            label: "Runtime receipt",
            value: agent.enforcement.receipt.status_code != null
              ? `HTTP ${agent.enforcement.receipt.status_code} · ${agent.enforcement.receipt.latency_ms}ms`
              : "no response",
            icon: ShieldCheck,
          }]
        : []),
    ],
    complianceRefs: ["NIST AI RMF", "OWASP LLM Top 10", "ISO 42001", "EU AI Act"],
    compliancePct: agent.guardrailCoverage?.pct,
    recommendedActions: [
      ...(tox.reasons || []),
      agent.guardrails?.human_in_loop
        ? "Maintain human approval on all high-impact actions."
        : "Enable human-in-the-loop approval for action-capable tools.",
      "Open the agent in the Control Plane to run the red-team baseline or apply a runtime enforcement action (Suspend / Kill).",
    ],
    explainTitle: `${agent.name} AI agent security`,
    explainKind: "agentic ai security delegated authority tools permissions guardrails toxicity",
    explainContext: {
      ref: agent.ref, name: agent.name, owner: agent.owner, model: agent.model,
      risk_class: agent.risk_class, modeled_risk: agent.modeledRisk, authority: agent.authority,
      status: agent.status, enforced: agent.enforced, tools: agent.tools,
      permissions: agent.permissions, guardrails: agent.guardrails,
      tool_violations: agent.tool_violations, toxic_combinations: tox.reasons,
      redteam: agent.last_redteam,
      enforcement: agent.enforcement,
    },
  };
}

export function systemDeepDive(system = {}) {
  return {
    accent: "0 84% 60%",
    refLabel: system.ref || system.id || "AI-SYSTEM",
    title: system.name || system.system || "AI system",
    rating: system.risk_class,
    facets: [
      { label: "Provider", value: system.provider || "Unknown" },
      { label: "Model", value: system.model || "—" },
      { label: "Status", value: system.status },
      { label: "Owner", value: system.owner || "Unassigned" },
      { label: "Use case", value: system.use_case || "—" },
      { label: "Source", value: system.source || "Inventory" },
    ],
    complianceRefs: ["NIST AI RMF", "EU AI Act", "GDPR"],
    recommendedActions: [
      system.status === "shadow"
        ? "Sanction this system to bring it under governance, or block it if it is unapproved."
        : "Maintain governance evidence and schedule a periodic review.",
      "Assign an accountable owner and document the use case and data flows.",
    ],
    explainTitle: `${system.name || "AI system"} governance`,
    explainKind: "ai system inventory shadow ai governance",
    explainContext: system,
  };
}

export function incidentDeepDive(incident = {}) {
  return {
    accent: "15 80% 55%",
    refLabel: incident.ref || incident.id || "AI-INCIDENT",
    title: incident.title || incident.name || "AI security incident",
    rating: incident.severity,
    facets: [
      { label: "Severity", value: incident.severity || "Unknown" },
      { label: "Containment mode", value: incident.mode || "Observe" },
      { label: "Status", value: incident.status || "Open" },
      { label: "System", value: incident.system || "—" },
    ],
    complianceRefs: ["NIST AI RMF MANAGE", "SOC 2"],
    recommendedActions: [
      "Confirm the containment mode and assign an incident owner.",
      "Trace the responsible agent or system and apply a runtime enforcement action if it is still active.",
    ],
    explainTitle: `${incident.title || "AI incident"} response`,
    explainKind: "ai security incident response",
    explainContext: incident,
  };
}
