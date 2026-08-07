# Obserra EIOS — Product Requirements & Build Log

## Positioning
**Enterprise Intelligence, Two Altitudes.**
- Executive altitude: what matters, why, what it could cost, what to do.
- Governance altitude: the controls, AI systems, risks, evidence, owners, remediation.
A continuous AI control plane (not a static GRC dashboard): discovery → lifecycle → agent governance → runtime assurance → audit evidence → business value.

## Original problem statement
Obserra EIOS — subscription-gated enterprise SaaS. Two flagship apps on one platform: Cyber Risk Register + Executive Dashboard AND AI Governance Suite. Dual-Mode. Clerk was requested but user chose JWT auth. Stripe billing. Multi-provider governed AI. Seeded demo + one connector.

## User choices (locked)
- Auth: JWT email/password + org/role model (+ passwordless QR login added later)
- AI: Emergent Universal LLM key — Claude Sonnet 5 (exec synthesis) + Gemini (long context)
- Payments: Stripe (Flow A sandbox) subscriptions monthly/annual + one-time module add-ons
- Connector: seeded Entra ID-style (MOCKED live sync) + Tenable + Defender/CASB
- Branding: official logo + full legal name "Obserra — Executive Protection & Intelligence LLC" + property/disclaimer footer

## Architecture
- Frontend: React + Tailwind + shadcn/ui + framer-motion + recharts + reactflow + qrcode.react
- Backend: FastAPI (auth.py, routes.py, ai_advisor.py, payments.py, reports.py, seed_data.py, db.py)
- DB: MongoDB, org-scoped multi-tenant, immutable audit_logs, TTL qr_sessions
- Personas: admin, executive, operational

## Implemented (as of 2026-06)
- JWT auth (httpOnly cookies, brute-force lockout), org/role, tenant isolation
- Passwordless QR login (start/approve/poll, 3-min single-use, cross-device)
- Subscription gating: trial(14d)/team/enterprise; access turns OFF when inactive (402 → paywall)
- Dual-Mode shell (Executive/Operational), animated next-gen dashboard (CountUp, gradient area, animated bars)
- Enterprise Health Index w/ transparent component scoring + 6-mo trend
- Cyber Risk Register (inherent/residual/KRI/owner/treatment, status workflow, evidence badges)
- Risk Heatmap (5×5 likelihood×impact, click → evidence lineage)
- Evidence lineage viewer (source→observation→recommendation→decision→action→outcome, ReactFlow)
- AI Governance Suite: inventory + shadow-AI discovery, incidents; **Model Card drill-down** (Overview/Evaluations/**cross-framework mapping** NIST AI RMF·ISO 42001·EU AI Act·OWASP LLM Top 10/**Governance: kill switch, restrict, rollback, sanction**)
- Connected Integrations panel: Entra ID / Tenable / Defender-CASB with **one-click remediation** (actions mutate risk + nudge health + audit) [MOCKED]
- Recommendation engine + Decision register (approvals, rationale, outcomes)
- AI Advisor = **helper + WORKER**: evidence-grounded streaming (citations, fact/estimate/prediction/rec separation), worker chips + inline `ACTION:` execution; logo avatar
- Board Report (Claude) → **PDF export (reportlab)** + **email (managed Resend)**
- Situation Room, Asset Intelligence (8 assets), Evidence & Reporting library
- Dashboard **Marketplace**: buy add-on dashboards (Stripe one-time), entitlement-gated nav with locks
- Every metric carries source / freshness / confidence badges; fact vs estimate vs AI-rec visual distinction
- Footer: "Property of Obserra — Executive Protection & Intelligence LLC" + disclaimer

## Testing
- iteration_2.json: 23/23 new-feature backend tests pass, 45/46 suite (1 expected shadow-AI flake). Reports email 500 (invalid regex) fixed. Stripe checkout verified.

## Backlog (from stakeholder vision — prioritized, NOT yet built)
- P0: Financial risk quantification ($ exposure model), Predictive risk + decision What-if simulation, Enterprise Knowledge Graph (BU↔Assets↔Data↔Vendors↔AI↔Controls↔Risks↔Regs), full clickable Evidence Intelligence (Metric→Calc→Source→Evidence→Control→Risk→Framework→Owner)
- P1: Continuous Control Monitoring (evidence expiry/drift), more native frameworks (NIST CSF 2.0, 800-53, SSDF, ISO 27001, SOC2, HIPAA, PCI, CMMC, GDPR, DORA, MITRE ATLAS), AI agent inventory + permission/tool governance, red-team/prompt-injection testing
- P1: Real connectors (M365/Azure/AWS/GCP/Okta/CrowdStrike/Sentinel/Splunk/ServiceNow/Wiz/Qualys...), Enterprise SSO/SAML + SCIM, ABAC
- P2: White-label, custom dashboards/frameworks/scoring, workflow + report builders, scheduled reports, Excel/Word exports, regulatory examination packages, Teams/Slack alerts, mobile exec view, benchmarking

## 10 headline differentiators (sell these)
Evidence-Grounded Executive Intelligence · Cyber+AI+Enterprise Risk in one · Every metric has source+freshness+confidence · AI system & agent discovery/governance · Enterprise Knowledge Graph · Continuous control & evidence monitoring · Executive AI Advisor · Predictive risk + decision simulation · Financial quantification · One-click Board/Audit/Regulatory reporting

## Credentials
admin: jblan2026@gmail.com / Obserra2026! (enterprise, active) · operational: analyst@obserra.demo / Analyst2026!
