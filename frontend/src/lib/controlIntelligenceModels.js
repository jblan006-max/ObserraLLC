const STATUS_RANK = {
  Failing: 4,
  "Evidence Stale": 3,
  Drifting: 2,
  Passing: 1,
};

export function clamp(value, min = 0, max = 100) {
  return Math.min(max, Math.max(min, value));
}

export function toNumber(value, fallback = 0) {
  const number = Number(value);
  return Number.isFinite(number) ? number : fallback;
}

export function evidenceState(control = {}) {
  if (control.stale || toNumber(control.days_to_expiry, 999) < 0) {
    return "Expired";
  }
  if (toNumber(control.days_to_expiry, 999) <= 14) {
    return "Expiring";
  }
  if (toNumber(control.days_to_expiry, 999) <= 30) {
    return "Watch";
  }
  return "Fresh";
}

export function controlPriorityScore(control = {}) {
  const status = STATUS_RANK[control.status] || 1;
  const effectiveness = clamp(toNumber(control.effectiveness));
  const maturity = clamp(toNumber(control.maturity) * 20);
  const evidence = evidenceState(control);
  const evidencePenalty =
    evidence === "Expired" ? 28 : evidence === "Expiring" ? 18 : evidence === "Watch" ? 8 : 0;
  const driftPenalty = control.drift ? 18 : 0;
  const statusPenalty = status * 12;
  const effectivenessPenalty = (100 - effectiveness) * 0.35;
  const maturityPenalty = (100 - maturity) * 0.12;

  return Math.round(
    clamp(
      statusPenalty +
        evidencePenalty +
        driftPenalty +
        effectivenessPenalty +
        maturityPenalty,
      0,
      100
    )
  );
}

export function normalizeControl(control = {}) {
  const frameworks = control.frameworks || {};
  const frameworkCount = Object.keys(frameworks).filter(
    (key) => Array.isArray(frameworks[key]) ? frameworks[key].length > 0 : Boolean(frameworks[key])
  ).length;

  return {
    ...control,
    evidence_state: evidenceState(control),
    priority_score: controlPriorityScore(control),
    framework_count: frameworkCount,
  };
}

export function normalizeControls(controls = []) {
  return controls
    .map(normalizeControl)
    .sort((a, b) => {
      if (b.priority_score !== a.priority_score) {
        return b.priority_score - a.priority_score;
      }
      return toNumber(a.effectiveness) - toNumber(b.effectiveness);
    });
}

export function controlSummary(controls = []) {
  const normalized = normalizeControls(controls);
  const total = normalized.length;
  const count = (predicate) => normalized.filter(predicate).length;
  const avg = (selector) =>
    total
      ? Math.round(
          normalized.reduce((sum, item) => sum + toNumber(selector(item)), 0) / total
        )
      : 0;

  const passing = count((control) => control.status === "Passing");
  const failing = count((control) => control.status === "Failing");
  const drifting = count((control) => control.status === "Drifting");
  const stale = count((control) => control.evidence_state === "Expired");
  const expiring = count((control) => control.evidence_state === "Expiring");
  const criticalAttention = count((control) => control.priority_score >= 70);
  const averageEffectiveness = avg((control) => control.effectiveness);
  const averageMaturity = total
    ? Math.round(
        (normalized.reduce((sum, item) => sum + toNumber(item.maturity), 0) / total) *
          10
      ) / 10
    : 0;

  const healthScore = total
    ? Math.round(
        clamp(
          averageEffectiveness * 0.5 +
            (passing / total) * 100 * 0.25 +
            ((total - stale - expiring) / total) * 100 * 0.15 +
            (averageMaturity / 5) * 100 * 0.1
        )
      )
    : 0;

  return {
    total,
    passing,
    failing,
    drifting,
    stale,
    expiring,
    criticalAttention,
    averageEffectiveness,
    averageMaturity,
    healthScore,
    attention: count(
      (control) =>
        control.status !== "Passing" ||
        control.evidence_state === "Expired" ||
        control.evidence_state === "Expiring" ||
        Boolean(control.drift)
    ),
  };
}

export function effectivenessBuckets(controls = []) {
  const normalized = normalizeControls(controls);
  return [
    { name: "90-100", min: 90, max: 100 },
    { name: "75-89", min: 75, max: 89.999 },
    { name: "55-74", min: 55, max: 74.999 },
    { name: "0-54", min: 0, max: 54.999 },
  ].map((bucket) => ({
    ...bucket,
    value: normalized.filter((control) => {
      const value = toNumber(control.effectiveness);
      return value >= bucket.min && value <= bucket.max;
    }).length,
  }));
}

export function evidenceBuckets(controls = []) {
  const normalized = normalizeControls(controls);
  return ["Fresh", "Watch", "Expiring", "Expired"].map((name) => ({
    name,
    value: normalized.filter((control) => control.evidence_state === name).length,
  }));
}

export function frameworkSummary(compliance = {}) {
  const frameworks = Array.isArray(compliance)
    ? compliance
    : compliance?.frameworks || [];

  return frameworks
    .map((framework) => ({
      ...framework,
      gap_count: Math.max(
        0,
        toNumber(framework.controls) - toNumber(framework.passing)
      ),
    }))
    .sort((a, b) => toNumber(a.coverage) - toNumber(b.coverage));
}

export function crosswalkRows(crosswalk = {}) {
  return Array.isArray(crosswalk?.rows) ? crosswalk.rows : [];
}

export function frameworkNames(crosswalk = {}, compliance = {}) {
  if (Array.isArray(crosswalk?.frameworks) && crosswalk.frameworks.length) {
    return crosswalk.frameworks;
  }
  return frameworkSummary(compliance).map((framework) => framework.framework);
}

export function mappedFrameworkCount(row = {}, frameworkNames = []) {
  const candidates = [
    row.frameworks,
    row.mapping,
    row.mappings,
    row.framework_map,
    row.framework_refs,
  ].filter(Boolean);

  for (const candidate of candidates) {
    if (typeof candidate !== "object") continue;
    return frameworkNames.filter((framework) => {
      const value = candidate[framework];
      if (Array.isArray(value)) return value.length > 0;
      return Boolean(value);
    }).length;
  }

  return frameworkNames.filter((framework) => {
    const value = row[framework];
    if (Array.isArray(value)) return value.length > 0;
    return Boolean(value);
  }).length;
}

export function convergenceLeaders(crosswalk = {}, compliance = {}) {
  const names = frameworkNames(crosswalk, compliance);
  return crosswalkRows(crosswalk)
    .map((row) => ({
      ...row,
      convergence_count: mappedFrameworkCount(row, names),
    }))
    .sort((a, b) => b.convergence_count - a.convergence_count)
    .slice(0, 10);
}

export function boardReportBlocks({ controls = [], compliance = {}, crosswalk = {} }) {
  const summary = controlSummary(controls);
  const frameworks = frameworkSummary(compliance);
  const leaders = convergenceLeaders(crosswalk, compliance);

  return [
    {
      heading: "Executive Control Posture",
      lines: [
        `Control health score: ${summary.healthScore}/100`,
        `Controls: ${summary.total}`,
        `Passing: ${summary.passing}`,
        `Need attention: ${summary.attention}`,
        `Average effectiveness: ${summary.averageEffectiveness}%`,
        `Average maturity: ${summary.averageMaturity}/5`,
        `Expired evidence: ${summary.stale}`,
      ],
    },
    {
      heading: "Framework Readiness",
      lines: frameworks.length
        ? frameworks.map(
            (framework) =>
              `${framework.framework}: ${framework.coverage}% coverage, ${framework.passing}/${framework.controls} passing, ${framework.gap_count} gap(s)`
          )
        : ["No compliance framework coverage is currently returned."],
    },
    {
      heading: "Highest Priority Control Gaps",
      lines: normalizeControls(controls)
        .filter((control) => control.priority_score >= 50)
        .slice(0, 10)
        .map(
          (control) =>
            `[${control.control_id}] ${control.name}: priority ${control.priority_score}/100, effectiveness ${control.effectiveness}%, status ${control.status}, evidence ${control.evidence_state}`
        ),
    },
    {
      heading: "Cross-Framework Convergence",
      lines: leaders.length
        ? leaders.map(
            (row) =>
              `[${row.control_id || row.id || "CONTROL"}] ${row.name || row.control_name || "Control"}: mapped across ${row.convergence_count} framework(s)`
          )
        : ["Crosswalk data is not currently available."],
    },
    {
      heading: "Defensibility",
      lines: [
        "Control status, effectiveness, maturity, evidence freshness and framework mappings are FACT values returned by the existing Obserra backend.",
        "Control health score, control priority score and convergence ranking are MODELLED client-side interpretations.",
        "AI recommendations are separated from source facts.",
      ],
    },
  ];
}
