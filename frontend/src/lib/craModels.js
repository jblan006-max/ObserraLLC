export function cls(product) {
  return product?.classification?.classification || "Unclassified";
}

export function clsStatus(product) {
  return product?.classification?.classification_status || "Not Reviewed";
}

export function assessmentStats(assessment = {}) {
  const answers = assessment.answers || [];
  const count = (status) => answers.filter((item) => item.status === status).length;
  return {
    total: answers.length,
    conforming: count("Conforming"),
    partial: count("Partial"),
    nonconforming: count("Nonconforming"),
    notAssessed: count("Not Assessed"),
    notApplicable: count("Not Applicable"),
    score: assessment.score || 0,
  };
}

export function productReadiness(product, assessments = [], external = []) {
  const assessment = assessments
    .filter((item) => item.product_ref === product.ref)
    .sort((a, b) => String(b.updated_at).localeCompare(String(a.updated_at)))[0];
  const ext = external.filter((item) => item.product_ref === product.ref);
  return {
    assessment,
    score: assessment?.score || 0,
    thirdPartyRequired:
      product?.classification?.pathway?.notified_body_required === true,
    externalConforming: ext.some((item) => item.decision === "Conforming"),
    classification: cls(product),
    classificationApproved: clsStatus(product) === "Approved",
    ceReady: product.ce_status === "Ready",
  };
}

export function vulnerabilityDeadline(vuln) {
  const stages = vuln?.clock?.stages || [];
  return (
    stages
      .filter((stage) => !stage.submitted)
      .sort((a, b) => new Date(a.deadline) - new Date(b.deadline))[0] || null
  );
}

export function reportBlocks(data) {
  const dashboard = data.dashboard || {};
  const products = data.products || [];
  const vulnerabilities = data.vulnerabilities || [];
  return [
    {
      heading: "EU CRA Governance Posture",
      lines: [
        `Products governed: ${dashboard.products || 0}`,
        `Average readiness: ${dashboard.average_readiness || 0}%`,
        `Classification approvals: ${dashboard.classification_approved || 0}`,
        `CE ready products: ${dashboard.ce_ready || 0}`,
        `Open external assessments: ${dashboard.open_external_assessments || 0}`,
        `Overdue Article 14 workflows: ${dashboard.reporting_overdue || 0}`,
      ],
    },
    {
      heading: "Product Classification",
      lines: products.map(
        (product) =>
          `[${product.ref}] ${product.name} ${product.version || ""} | ${cls(product)} | ${clsStatus(product)}`
      ),
    },
    {
      heading: "Article 14 Reporting",
      lines: vulnerabilities.map((item) => {
        const next = vulnerabilityDeadline(item);
        return `[${item.ref}] ${item.title} | ${item.product_name} | next ${
          next ? `${next.stage} ${next.deadline}` : "no open deadline"
        }`;
      }),
    },
    {
      heading: "Legal Traceability",
      lines: [
        "Regulation (EU) 2024/2847 Cyber Resilience Act",
        "Commission Implementing Regulation (EU) 2025/2392 technical product-category descriptions",
        "Reporting obligations effective 11 September 2026",
        "General CRA application date 11 December 2027",
      ],
    },
  ];
}
