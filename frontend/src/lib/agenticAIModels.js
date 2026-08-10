const RISK_BASE = {
  Critical: 90,
  High: 74,
  Medium: 52,
  Low: 28,
};

const ACTIVE_ACTION_TOKENS = [
  ".write",
  ".send",
  ".exec",
  ".admin",
  ".delete",
  ".create",
  ".update",
  "shell",
  "deploy",
  "publish",
  "approve",
  "payment",
];

export function clamp(value, min = 0, max = 100) {
  return Math.min(max, Math.max(min, value));
}

export function isActionTool(tool = "") {
  const t = String(tool).toLowerCase();
  return ACTIVE_ACTION_TOKENS.some((token) => t.includes(token));
}

export function guardrailCoverage(agent = {}) {
  const guardrails = agent.guardrails || {};
  const keys = [
    "input_filtering",
    "output_filtering",
    "tool_allowlist",
    "human_in_loop",
  ];
  const active = keys.filter((key) => Boolean(guardrails[key])).length;
  return {
    active,
    total: keys.length,
    pct: Math.round((active / keys.length) * 100),
    gaps: keys.filter((key) => !guardrails[key]),
  };
}

export function authorityTier(agent = {}) {
  if (agent.status === "killed") return "Disabled";

  const tools = agent.tools || [];
  const actionTools = tools.filter(isActionTool);
  const human = Boolean(agent.guardrails?.human_in_loop);

  if (actionTools.length > 0 && !human) return "Autonomous";
  if (actionTools.length > 0 && human) return "Approval Required";
  if (tools.length > 0) return "Tool Assisted";
  return "Observe";
}

export function riskFactors(agent = {}) {
  const factors = [];
  const coverage = guardrailCoverage(agent);
  const actionTools = (agent.tools || []).filter(isActionTool);

  if (coverage.gaps.includes("tool_allowlist")) factors.push("Tool allowlist missing");
  if (coverage.gaps.includes("human_in_loop")) factors.push("Human approval missing");
  if (coverage.gaps.includes("input_filtering")) factors.push("Input filtering missing");
  if (coverage.gaps.includes("output_filtering")) factors.push("Output filtering missing");
  if ((agent.tool_violations || []).length) factors.push("Dangerous tool violation");
  if (actionTools.length) factors.push(`${actionTools.length} action-capable tool(s)`);
  if (agent.status === "shadow") factors.push("Shadow or unsanctioned");
  if (agent.last_redteam && agent.last_redteam.score < 80) factors.push("Red-team baseline below 80%");

  return factors;
}

export function modeledAgentRiskScore(agent = {}) {
  if (agent.status === "killed") return 0;

  let score = RISK_BASE[agent.risk_class] ?? 50;
  const coverage = guardrailCoverage(agent);
  const tier = authorityTier(agent);

  score += coverage.gaps.length * 4;
  score += Math.min(12, (agent.tool_violations || []).length * 8);
  if (tier === "Autonomous") score += 10;
  if (tier === "Approval Required") score += 3;
  if (agent.status === "shadow") score += 8;
  if (agent.status === "restricted") score -= 5;
  if (agent.status === "sanctioned") score -= 3;
  if (agent.last_redteam?.score != null) {
    score += Math.max(0, (80 - Number(agent.last_redteam.score)) * 0.18);
  }

  return Math.round(clamp(score));
}

export function normalizeAgent(agent = {}) {
  const coverage = guardrailCoverage(agent);
  const authority = authorityTier(agent);
  const modeledRisk = modeledAgentRiskScore(agent);
  const actionTools = (agent.tools || []).filter(isActionTool);

  return {
    ...agent,
    guardrailCoverage: coverage,
    authority,
    modeledRisk,
    riskFactors: riskFactors(agent),
    actionTools,
  };
}

export function normalizeAgents(agents = []) {
  return agents
    .map(normalizeAgent)
    .sort((a, b) => b.modeledRisk - a.modeledRisk);
}

export function summarizeAgents(agents = []) {
  const normalized = normalizeAgents(agents);
  const count = (predicate) => normalized.filter(predicate).length;
  const averageRisk = normalized.length
    ? Math.round(normalized.reduce((sum, item) => sum + item.modeledRisk, 0) / normalized.length)
    : 0;

  return {
    total: normalized.length,
    averageRisk,
    critical: count((a) => a.risk_class === "Critical"),
    high: count((a) => a.risk_class === "High"),
    shadow: count((a) => a.status === "shadow"),
    restricted: count((a) => a.status === "restricted"),
    sanctioned: count((a) => a.status === "sanctioned"),
    autonomous: count((a) => a.authority === "Autonomous"),
    approvalRequired: count((a) => a.authority === "Approval Required"),
    toolAssisted: count((a) => a.authority === "Tool Assisted"),
    observe: count((a) => a.authority === "Observe"),
    killed: count((a) => a.status === "killed"),
    toolViolations: count((a) => (a.tool_violations || []).length > 0),
    weakGuardrails: count((a) => a.guardrailCoverage.pct < 75),
    noHumanApproval: count((a) => !a.guardrails?.human_in_loop),
    lowRedteam: count((a) => a.last_redteam && a.last_redteam.score < 80),
  };
}

export function authorityDistribution(agents = []) {
  const normalized = normalizeAgents(agents);
  const tiers = [
    "Autonomous",
    "Approval Required",
    "Tool Assisted",
    "Observe",
    "Disabled",
  ];

  return tiers.map((name) => ({
    name,
    value: normalized.filter((agent) => agent.authority === name).length,
  }));
}

export function guardrailDistribution(agents = []) {
  const total = agents.length || 0;
  const keys = [
    ["input_filtering", "Input filtering"],
    ["output_filtering", "Output filtering"],
    ["tool_allowlist", "Tool allowlist"],
    ["human_in_loop", "Human approval"],
  ];

  return keys.map(([key, label]) => {
    const active = agents.filter((agent) => Boolean(agent.guardrails?.[key])).length;
    return {
      key,
      label,
      active,
      total,
      pct: total ? Math.round((active / total) * 100) : 0,
    };
  });
}

export function systemSummary(systems = []) {
  const count = (status) => systems.filter((system) => system.status === status).length;
  return {
    total: systems.length,
    sanctioned: count("sanctioned"),
    shadow: count("shadow"),
    restricted: count("restricted"),
  };
}

export function incidentSummary(incidents = []) {
  const open = incidents.filter((incident) => {
    const status = String(incident.status || "").toLowerCase();
    return !["closed", "resolved", "remediated"].includes(status);
  });

  return {
    total: incidents.length,
    open: open.length,
    critical: open.filter((incident) => incident.severity === "Critical").length,
    high: open.filter((incident) => incident.severity === "High").length,
    blocking: open.filter((incident) =>
      String(incident.mode || "").toLowerCase().includes("block")
    ).length,
  };
}

export function boardReportBlocks({ agents = [], systems = [], incidents = [], analytics = {} }) {
  const summary = summarizeAgents(agents);
  const sys = systemSummary(systems);
  const inc = incidentSummary(incidents);
  const guards = guardrailDistribution(agents);

  return [
    {
      heading: "Executive AI Agent Security Posture",
      lines: [
        `Registered agents: ${summary.total}`,
        `Modeled average agent risk score: ${summary.averageRisk}/100`,
        `Autonomous agents: ${summary.autonomous}`,
        `Agents requiring approval: ${summary.approvalRequired}`,
        `Shadow AI systems: ${sys.shadow}`,
        `Open AI incidents: ${inc.open}`,
      ],
    },
    {
      heading: "Delegated Machine Authority",
      lines: [
        `Autonomous: ${summary.autonomous}`,
        `Approval Required: ${summary.approvalRequired}`,
        `Tool Assisted: ${summary.toolAssisted}`,
        `Observe: ${summary.observe}`,
        `Disabled governance state: ${summary.killed}`,
      ],
    },
    {
      heading: "Guardrail Coverage",
      lines: guards.map(
        (guard) => `${guard.label}: ${guard.active}/${guard.total} (${guard.pct}%)`
      ),
    },
    {
      heading: "Risk Signals",
      lines: [
        `Agents with dangerous tool violations: ${summary.toolViolations}`,
        `Agents below 75% guardrail coverage: ${summary.weakGuardrails}`,
        `Agents without human approval: ${summary.noHumanApproval}`,
        `Agents with heuristic red-team baseline below 80%: ${summary.lowRedteam}`,
        `Recorded AI queries: ${(analytics?.totals?.queries || 0).toLocaleString()}`,
      ],
    },
    {
      heading: "Defensibility Note",
      lines: [
        "Agent risk scores and delegated authority tiers are MODELLED client-side interpretations of existing Obserra agent records.",
        "Current red-team results are the existing deterministic heuristic baseline, not live runtime adversarial testing.",
        "Runtime enforcement is not implied by a governance status change unless a connected execution control explicitly verifies enforcement.",
      ],
    },
  ];
}