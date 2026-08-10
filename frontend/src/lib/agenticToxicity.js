import { isActionTool, normalizeAgents } from "@/lib/agenticAIModels";

const DANGER_TOOLS = ["shell.exec", "cloud.admin", "iam.write"];
const WRITE_TOKENS = [
  ".write", ".delete", ".admin", ".exec", ".send", ".create", ".update",
  "shell", "deploy", "publish", "approve", "payment",
];

// Map a tool name to the resource domain it can reach.
export function toolResource(tool = "") {
  const t = String(tool).toLowerCase();
  if (t.includes("shell") || t.includes("exec")) return "Runtime / OS";
  if (t.includes("iam") || t.includes("admin")) return "Identity & Access";
  if (t.includes("cloud") || t.includes("deploy")) return "Cloud Infra";
  if (t.includes("sql") || t.includes("db") || t.includes("erp") || t.includes("finance")) return "Databases & ERP";
  if (t.includes("email") || t.includes("send") || t.includes("message") || t.includes("slack")) return "Communications";
  if (t.includes("payment") || t.includes("billing")) return "Payments";
  if (t.includes("ticket") || t.includes("itsm")) return "ITSM";
  if (t.includes("kb") || t.includes("doc") || t.includes("read")) return "Knowledge & Docs";
  return "Other";
}

export function toolPermission(tool = "") {
  const t = String(tool).toLowerCase();
  return WRITE_TOKENS.some((w) => t.includes(w)) ? "write" : "read";
}

// Blast-radius severity (0-100) for one agent's exposure to a resource domain.
export function cellScore(edges = [], resource) {
  const es = (edges || []).filter((e) => e.resource === resource);
  if (!es.length) return 0;
  if (es.some((e) => e.danger)) return 100;
  if (es.some((e) => e.permission === "write")) return 65;
  return 30;
}

// Classify the toxic capability combinations for one agent.
export function agentToxicity(agent = {}) {
  const g = agent.guardrails || {};
  const tools = agent.tools || [];
  const danger = tools.filter((t) => DANGER_TOOLS.includes(t));
  const action = tools.filter(isActionTool);
  if (agent.status === "killed") {
    return { toxic: false, level: "none", score: 0, reasons: [], danger, action };
  }
  const reasons = [];
  if (danger.length && !g.tool_allowlist) reasons.push(`Dangerous tool (${danger.join(", ")}) with no tool allowlist`);
  if (action.length && !g.human_in_loop) reasons.push(`${action.length} action-capable tool(s) with no human approval`);
  if (action.length && !g.output_filtering) reasons.push("Action tools with no output filtering (exfiltration risk)");
  if ((agent.tool_violations || []).length) reasons.push("Recorded dangerous tool-governance violation");
  const level =
    danger.length && !g.tool_allowlist && !g.human_in_loop ? "critical"
      : reasons.length >= 2 ? "high"
        : reasons.length === 1 ? "medium" : "none";
  const score = { critical: 100, high: 72, medium: 45, none: 0 }[level];
  return { toxic: level !== "none", level, score, reasons, danger, action };
}

// Build the Agent -> Tool -> Permission -> Resource graph model.
export function toxicityModel(agents = []) {
  const nodes = normalizeAgents(agents)
    .map((a) => {
      const toxicity = agentToxicity(a);
      const edges = (a.tools || []).map((tool) => ({
        tool,
        permission: toolPermission(tool),
        resource: toolResource(tool),
        action: isActionTool(tool),
        danger: DANGER_TOOLS.includes(tool),
      }));
      return { ...a, toxicity, edges };
    })
    .sort((x, y) => y.toxicity.score - x.toxicity.score);
  return {
    nodes,
    toxic: nodes.filter((n) => n.toxicity.toxic).length,
    critical: nodes.filter((n) => n.toxicity.level === "critical").length,
  };
}
