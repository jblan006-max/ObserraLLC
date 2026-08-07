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
- Backend: FastAPI. Shared **cybersecurity kernel** at `/app/backend/kernel/` (manifest.py = 15 subsystems; notification.py, policy.py, workflow.py = 3 new engines; routes.py = kernel API). Domain apps sit above it (auth.py, routes.py, ai_advisor.py, payments.py, reports.py, scheduled.py, seed_data.py, db.py)
- DB: MongoDB, org-scoped multi-tenant, immutable audit_logs, TTL qr_sessions, collections: notifications, policies, workflows, counters
- Personas: admin, executive, operational
- Scheduling: platform cron via `/app/.emergent/crons.yml` → `/api/cron/*` (Bearer WEBHOOK_CRON_SECRET)

## Shared Kernel subsystems (15)
Foundation: Tenant Management · Identity & RBAC | Data: Enterprise Asset Model · Enterprise Knowledge Graph · Evidence Store | Analytics: Risk Engine · Control Engine · **Policy Engine** | Orchestration: **Workflow Engine** · Connector Framework | Intelligence: AI Context Engine · Obserrian AI | Assurance: Audit Ledger · Reporting Engine · **Notification Engine**

## Session 2026-06 (kernel + 4 features) — verified iteration_4.json (backend 13/13, frontend 100%)
- Shared cybersecurity kernel formalized (`kernel/` package) + Platform Kernel admin page (/app/kernel) showing subsystem health, policies, workflows
- Policy Engine: 5 seeded governance policies, evaluated continuously against controls
- Workflow Engine: onboarding workflow (invited→password_set→active)
- Notification Engine: in-app bell + managed Resend email
- Force Password Reset: invited users gated behind first-login "Set your password" screen (POST /api/auth/change-password, must_change_password flag)
- Team Onboarding Email: invite now emails a sign-in link via Resend + starts onboarding workflow
- Scheduled Board Reports: monthly cron (1st, 08:00 UTC) generates + emails board packet to admins/execs per org
- Control Drift Alerts: /controls evaluates policies → deduped in-app notifications to owners

## Session 2026-06 (kernel loop-closers) — verified iteration_5.json (backend 13/13, frontend 100%)
- Remediation Workflows: tap a drift alert in the bell → opens a remediation workflow (accept→assign→resolve); resolving auto-marks the control's drift notifications resolved. Endpoints: POST /notifications/{id}/remediate, POST /workflows/{id}/action, GET /workflows/{id}
- Policy Authoring (admin): New/Edit policy modal on Platform Kernel page (POST /policies, PATCH /policies/{id}); tuning POL-CTRL-EFFECT threshold changes drift flagging; non-admins 403. Custom policy IDs use monotonic db.counters (collision-safe)
- Kernel Health Telemetry: GET /kernel/health returns real per-subsystem records/last_run/error_rate/status; surfaced on each subsystem card
- Weekly Drift Digest: Monday 08:00 UTC cron (POST /cron/weekly-drift-digest) emails admins/execs the open drift alerts (.emergent/crons.yml now has 2 crons)

## Session 2026-06 (enhancements) — verified iteration_6.json (backend 14/14, frontend 100%)
- Remediation SLAs: remediation workflows get due_at (created+7d); RemediationModal + Kernel workflow list show Due/Overdue badges
- Assignee Directory: GET /api/members powers a teammate dropdown in RemediationModal (replaces free text)
- Policy Simulation: POST /api/policies/simulate → live "would flag N of M controls" preview while an admin edits a threshold policy
- Digest Preferences: PATCH /api/auth/preferences (weekly/daily/off) + Settings page; weekly & daily crons filter recipients by cadence; .emergent/crons.yml now has 3 crons

## ROADMAP (P0/P1 — queued by user, in order)
1. First standalone app formally composed on the kernel (prove the layering)
2. Real connectors: M365/Azure/AWS/Okta/CrowdStrike/Splunk/ServiceNow/Wiz; Enterprise SSO/SAML + SCIM; ABAC
3. AI agent inventory + tool/permission governance; red-team / prompt-injection testing

## Session 2026-06 (kernel-native app + enterprise) — verified iteration_7.json (backend 24/24, frontend 100%)
- Remediation KPI Strip: GET /kernel/remediation-kpi (open/overdue/resolved) shown atop Platform Kernel page
- Policy History: PATCH /policies logs {field,from,to,by,at} to policy_history; GET /policies/{id}/history; shown in policy modal
- **AI Agent Governance (first kernel-native standalone app)**: /app/agents — agent inventory (asset model), tool/permission governance + tool_violations, guardrail toggles, deterministic red-team/prompt-injection suite (heuristic MOCKED). Composition proven: a critical red-team failure auto-opens a remediation workflow + agent_risk notification (Workflow + Notification + Audit engines). Endpoints: /api/agents CRUD + /api/agents/{ref}/redteam
- **Enterprise Access** (/app/enterprise, admin): governed connectors (M365/Azure/AWS/Okta/CrowdStrike/Splunk/ServiceNow/Wiz) connect/sync/disconnect; SSO/SAML config; SCIM toggle+token; ABAC rules CRUD. ALL external integration MOCKED (demo-grade).

## Roadmap remaining (P1/P2)
- Real (live) connector OAuth + true SSO/SAML/SCIM with an IdP; production ABAC enforcement in request path
- Additional kernel-native apps per vertical; benchmarking; white-label; custom dashboards/report builders

## Session 2026-06 (identity + 2nd kernel-native app + white-label) — verified iteration_8.json (backend 20/20, frontend 100%)
- Emergent-managed **Google login** alongside JWT (POST /auth/google/session maps Google email → existing invited user → our JWT session). Live OAuth round-trip is manual-verify; guards tested (400/401).
- **ABAC enforcement in request path**: /enterprise/abac/enforce toggle + /abac/evaluate + /abac/protected-demo (deny precedence, fail-safe default-allow). Enterprise → ABAC tab enforce toggle.
- **Third-Party / Vendor Risk** = 2nd kernel-native app (/app/vendors): vendor inventory + risk scoring; assessing High/Critical opens a remediation workflow + vendor_risk alert (kernel loop).
- **White-label Branding** (/branding GET/PUT, Enterprise → Branding tab: display name/accent/logo) + **Peer Benchmarking** (/benchmark, /app/benchmark) with metrics computed from real controls/agents.
- QUEUED (needs creds): real Microsoft 365 connector OAuth (Azure app client id/secret/tenant); real SAML/SCIM with an enterprise IdP.


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
- iteration_3.json (2026-06): 8/8 session features verified. Backend 16/16 (AI enum 422/200, concurrency-safe DEC-ref counter, team invite/list/delete admin gating, connector sync, controls, evidence-pack PDF, financials/trend, graph-ask). Frontend 100% (login screensaver canvas+logo-pulse, sync ticker, admin-only Team nav+invite+temp password, Control Monitoring, Graph Q&A, ALE Trend, RiskRegister full-row click). Fixed LOW UX: Team.jsx now redirects non-admins to /app on 403.

## Session 2026-06 additions (verified)
- Continuous Control Monitoring page (evidence expiry/drift/maturity/effectiveness + per-control evidence-pack PDF across frameworks)
- Graph Q&A (POST /advisor/graph-ask NL question → answer + node highlight) + presets
- Portfolio ALE Trend chart on Reporting (GET /financials/trend)
- P2 fixes: AISystemUpdate enum validation (field_validator); concurrency-safe DEC-ref via db.counters $inc upsert
- RiskRegister: entire row clickable → evidence lineage (stopPropagation on $ button + status)
- P1 polish: Login Screensaver (animated NetworkBackground canvas + pulsing logo), Connector Sync Ticker (mocked live Entra/Tenable/CASB), Team Invites (admin-only invite/list/remove, inline temp password)

## Backlog (from stakeholder vision — prioritized)
- P0 ✅ DONE (2026-06): Financial risk quantification (FAIR ALE per risk + executive rollup), Decision What-if Simulation, Enterprise Knowledge Graph (BU↔AI↔data↔vendors↔risks↔regs with NL-preset traversal), clickable Evidence Intelligence drill-down (Metric→Calc→Source→Evidence→Control→Risk→Framework→Owner + FAIR ALE)
- P1: Continuous Control Monitoring (evidence expiry/drift), more native frameworks (NIST CSF 2.0, 800-53, SSDF, ISO 27001, SOC2, HIPAA, PCI, CMMC, GDPR, DORA, MITRE ATLAS), AI agent inventory + permission/tool governance, red-team/prompt-injection testing
- P1: Real connectors (M365/Azure/AWS/GCP/Okta/CrowdStrike/Sentinel/Splunk/ServiceNow/Wiz/Qualys...), Enterprise SSO/SAML + SCIM, ABAC
- P2: White-label, custom dashboards/frameworks/scoring, workflow + report builders, scheduled reports, Excel/Word exports, regulatory examination packages, Teams/Slack alerts, mobile exec view, benchmarking

## 10 headline differentiators (sell these)
Evidence-Grounded Executive Intelligence · Cyber+AI+Enterprise Risk in one · Every metric has source+freshness+confidence · AI system & agent discovery/governance · Enterprise Knowledge Graph · Continuous control & evidence monitoring · Executive AI Advisor · Predictive risk + decision simulation · Financial quantification · One-click Board/Audit/Regulatory reporting

## Credentials
admin: jblan2026@gmail.com / Obserra2026! (enterprise, active) · operational: analyst@obserra.demo / Analyst2026!
