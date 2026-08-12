const SEVERITY_WEIGHT = {
  Critical: 100,
  High: 76,
  Medium: 52,
  Low: 28,
  Info: 10,
};

export function toNumber(value, fallback = 0) {
  const number = Number(value);
  return Number.isFinite(number) ? number : fallback;
}

export function money(value, digits = 1) {
  const number = toNumber(value);
  const abs = Math.abs(number);
  if (abs >= 1_000_000_000) return `$${(number / 1_000_000_000).toFixed(digits)}B`;
  if (abs >= 1_000_000) return `$${(number / 1_000_000).toFixed(digits)}M`;
  if (abs >= 1_000) return `$${(number / 1_000).toFixed(0)}k`;
  return `$${Math.round(number).toLocaleString()}`;
}

export function activeIncidents(incidents = []) {
  return incidents.filter((incident) => {
    const status = String(incident.status || "").toLowerCase();
    return !["resolved", "closed", "remediated"].includes(status);
  });
}

export function highestSeverity(incidents = [], risks = []) {
  const severities = activeIncidents(incidents)
    .map((incident) => incident.severity)
    .filter(Boolean);

  if (severities.includes("Critical")) return "Critical";
  if (severities.includes("High")) return "High";
  if (severities.includes("Medium")) return "Medium";

  const maxResidual = Math.max(0, ...risks.map((risk) => toNumber(risk.residual)));
  if (maxResidual >= 16) return "Critical";
  if (maxResidual >= 10) return "High";
  if (maxResidual >= 5) return "Medium";
  return incidents.length || risks.length ? "Low" : "None";
}

export function portfolioExposure(risks = [], strategic = {}) {
  const riskAle = risks.reduce(
    (sum, risk) => sum + Math.max(0, toNumber(risk.residual_ale)),
    0
  );
  if (riskAle > 0) return riskAle;
  return toNumber(strategic?.portfolio?.residual_ale);
}

export function affectedRiskCount(risks = []) {
  return risks.filter(
    (risk) =>
      String(risk.status || "").toLowerCase() !== "remediated" &&
      toNumber(risk.residual) >= 10
  ).length;
}

export function controlFailureSummary(controls = []) {
  const failing = controls.filter((control) => control.status === "Failing");
  const drifting = controls.filter(
    (control) => Boolean(control.drift) || control.status === "Drifting"
  );
  const stale = controls.filter(
    (control) => Boolean(control.stale) || control.status === "Evidence Stale"
  );
  return {
    failing: failing.length,
    drifting: drifting.length,
    stale: stale.length,
    totalAttention: new Set(
      [...failing, ...drifting, ...stale].map((control) => control.control_id)
    ).size,
  };
}

export function actionSummary(actions = []) {
  const count = (status) => actions.filter((action) => action.status === status).length;
  const complete = actions.filter((action) =>
    ["Verified", "Complete"].includes(action.status)
  );
  const progress = actions.length
    ? Math.round((complete.length / actions.length) * 100)
    : 0;

  return {
    total: actions.length,
    open: actions.filter((action) => !["Verified", "Complete"].includes(action.status)).length,
    awaitingApproval: count("Awaiting Approval"),
    approved: count("Approved"),
    executing: count("Executing"),
    verified: count("Verified") + count("Complete"),
    failed: count("Failed"),
    blocked: count("Blocked"),
    progress,
  };
}

export function crisisScore({ incidents = [], risks = [], controls = [], actions = [] }) {
  const incident = activeIncidents(incidents).length
    ? Math.max(
        ...activeIncidents(incidents).map(
          (item) => SEVERITY_WEIGHT[item.severity] || 40
        )
      )
    : 0;
  const risk = Math.min(100, Math.max(0, ...risks.map((item) => toNumber(item.residual) * 5)));
  const control = controlFailureSummary(controls);
  const controlScore = Math.min(
    100,
    control.failing * 15 + control.drifting * 8 + control.stale * 4
  );
  const response = actionSummary(actions);
  const responsePenalty = response.total ? 100 - response.progress : 50;

  return Math.round(
    incident * 0.35 + risk * 0.25 + controlScore * 0.2 + responsePenalty * 0.2
  );
}

export function mergeTimeline({ caseEvents = [], incidents = [], audit = [] }) {
  const rows = [];

  for (const event of caseEvents) {
    rows.push({
      id: event.event_id,
      ts: event.occurred_at || event.created_at,
      kind: event.kind || "Note",
      title: event.title,
      detail: event.detail || "",
      source: event.source || "Obserra",
      severity: event.severity || "Info",
      classification: "FACT",
    });
  }

  for (const incident of incidents) {
    const ts = incident.opened || incident.created_at || incident.ts;
    if (!ts) continue;
    rows.push({
      id: incident.ref || incident.id || `incident-${rows.length}`,
      ts,
      kind: "Threat",
      title: incident.title || incident.name || "Security incident",
      detail: incident.system ? `System: ${incident.system}` : "",
      source: "Incident",
      severity: incident.severity || "High",
      classification: "FACT",
    });
  }

  for (const entry of audit.slice(0, 50)) {
    if (!entry.ts) continue;
    rows.push({
      id: `${entry.ts}:${entry.action}`,
      ts: entry.ts,
      kind: "Evidence",
      title: entry.action || "Audit event",
      detail: entry.detail || "",
      source: entry.actor || "Audit",
      severity: "Info",
      classification: "FACT",
    });
  }

  return rows.sort(
    (a, b) => new Date(b.ts || 0).getTime() - new Date(a.ts || 0).getTime()
  );
}

export function executiveBriefBlocks({ data, selectedCase, caseDetail }) {
  const response = actionSummary(caseDetail?.actions || []);
  const controls = controlFailureSummary(data.controls || []);
  const exposure = portfolioExposure(data.risks || [], data.strategic || {});

  return [
    {
      heading: "Cyber Crisis Executive Summary",
      lines: [
        `Active crisis: ${selectedCase?.title || "No persistent crisis case selected"}`,
        `Severity: ${selectedCase?.severity || data.severity || "None"}`,
        `Phase: ${selectedCase?.phase || "Not assigned"}`,
        `Modeled enterprise crisis score: ${data.crisisScore}/100`,
        `Current residual cyber exposure: ${money(exposure)}`,
        `Active incidents: ${activeIncidents(data.incidents || []).length}`,
        `High residual risks: ${affectedRiskCount(data.risks || [])}`,
      ],
    },
    {
      heading: "Response Status",
      lines: [
        `Response actions: ${response.total}`,
        `Open actions: ${response.open}`,
        `Awaiting executive approval: ${response.awaitingApproval}`,
        `Executing: ${response.executing}`,
        `Verified or complete: ${response.verified}`,
        `Modeled response progress: ${response.progress}%`,
      ],
    },
    {
      heading: "Control Failure Intelligence",
      lines: [
        `Failing controls: ${controls.failing}`,
        `Drifting controls: ${controls.drifting}`,
        `Stale evidence controls: ${controls.stale}`,
        `Unique controls requiring attention: ${controls.totalAttention}`,
      ],
    },
    {
      heading: "Leadership",
      lines: [
        `Incident commander: ${selectedCase?.incident_commander || "Not assigned"}`,
        `Executive sponsor: ${selectedCase?.executive_sponsor || "Not assigned"}`,
        `Next update: ${selectedCase?.next_update_at || "Not scheduled"}`,
      ],
    },
    {
      heading: "Defensibility",
      lines: [
        "Crisis case, incident, risk, control, decision, audit, workflow and response action records are source facts from Obserra services.",
        "Enterprise crisis score and response progress are modeled decision-support metrics.",
        "Obserra Advisor interpretation is AI recommendation and is not presented as source fact.",
        "External containment is not claimed unless a connected execution system verifies the action.",
      ],
    },
  ];
}
