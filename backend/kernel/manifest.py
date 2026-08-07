"""Obserra shared cybersecurity kernel — subsystem manifest.

Each standalone application (Cyber Risk Register, Executive Dashboard,
AI Governance Suite, ...) sits ABOVE this kernel and composes its services.
"""

SUBSYSTEMS = [
    {"id": "tenant", "name": "Tenant Management", "layer": "Foundation",
     "desc": "Org provisioning, plans, entitlements & multi-tenant isolation.", "impl": "auth.organizations"},
    {"id": "identity", "name": "Identity & RBAC", "layer": "Foundation",
     "desc": "JWT + QR auth, roles (admin/executive/operational), least-privilege gating.", "impl": "auth.py"},
    {"id": "asset_model", "name": "Enterprise Asset Model", "layer": "Data",
     "desc": "Canonical inventory of systems, data stores, vendors & AI systems.", "impl": "routes.assets"},
    {"id": "knowledge_graph", "name": "Enterprise Knowledge Graph", "layer": "Data",
     "desc": "BU↔AI↔data↔vendor↔risk↔regulation dependency graph + NL traversal.", "impl": "routes._build_graph"},
    {"id": "evidence_store", "name": "Evidence Store", "layer": "Data",
     "desc": "Source→observation→recommendation→decision→action evidence lineage.", "impl": "routes.evidence"},
    {"id": "risk_engine", "name": "Risk Engine", "layer": "Analytics",
     "desc": "Inherent/residual scoring, FAIR ALE quantification & heatmap.", "impl": "routes.risks"},
    {"id": "control_engine", "name": "Control Engine", "layer": "Analytics",
     "desc": "Control effectiveness, maturity, evidence freshness & drift detection.", "impl": "routes.controls"},
    {"id": "policy_engine", "name": "Policy Engine", "layer": "Analytics",
     "desc": "Codified governance policies evaluated continuously against controls.", "impl": "kernel.policy"},
    {"id": "workflow_engine", "name": "Workflow Engine", "layer": "Orchestration",
     "desc": "Multi-step workflows — onboarding, remediation approvals, decisions.", "impl": "kernel.workflow"},
    {"id": "connector_framework", "name": "Connector Framework", "layer": "Orchestration",
     "desc": "Governed connectors (Entra ID, Tenable, Defender/CASB) + one-click remediation.", "impl": "routes.integrations"},
    {"id": "ai_context_engine", "name": "AI Context Engine", "layer": "Intelligence",
     "desc": "Assembles evidence-grounded org context for every AI call.", "impl": "ai_advisor._build_context"},
    {"id": "audit_ledger", "name": "Audit Ledger", "layer": "Assurance",
     "desc": "Immutable, org-scoped audit trail of every action & decision.", "impl": "db.audit_logs"},
    {"id": "reporting_engine", "name": "Reporting Engine", "layer": "Assurance",
     "desc": "Board/audit/regulatory packets — PDF export + scheduled email.", "impl": "reports.py"},
    {"id": "notification_engine", "name": "Notification Engine", "layer": "Assurance",
     "desc": "In-app alerts + transactional email (drift alerts, onboarding, reports).", "impl": "kernel.notification"},
    {"id": "obserrian_ai", "name": "Obserrian AI", "layer": "Intelligence",
     "desc": "Evidence-grounded advisor & worker (Claude Sonnet 5 · Gemini 3 Pro).", "impl": "ai_advisor.py"},
]
