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


## Session 2026-06 (Cyber Risk + Studio + Advisor upgrade) — verified iteration_9.json (backend 14/14, frontend 100%)
- **Cyber Risk** (3rd kernel-native app, /app/cyber-risk): posture score, risk-mitigation %, control coverage, open/total risks, composition badges, top residual risk table; admin "Treat" opens a remediation workflow + cyber_risk alert (kernel loop). Endpoints GET /api/cyber/overview, POST /api/cyber/risks/{ref}/treat.
- **Studio** (/app/studio): Dashboard Builder (toggle live kernel-metric widgets, saved per-user via /api/studio/dashboard) + Report Builder (pick sections → POST /api/studio/report/compose → AI Executive Narrative via Claude Opus 4.8 + section blocks).
- **AI Advisor upgrade**: model upgraded to **Claude Opus 4.8** (executive+operational routes); new **Deep analysis mode** (advisor-deep-toggle → structured Signals/Analysis/Recommendation, deep flag on /api/advisor/chat); **slim always-visible header input bar** (header-advisor-input) that expands & sends to the advisor; advisor **auto-opens once per session** on login (cleared on logout). Obserra /logo.png retained as the advisor avatar.

## Session 2026-06 (Studio Report Export + Advisor Cost Guardrails)
- **Report Export**: Studio composed reports export to branded PDF (POST /api/studio/report/pdf, reuses reportlab _build_pdf) and email to the board = org admins+execs (POST /api/studio/report/email, managed Resend). UI buttons on Report Builder output.
- **Advisor Cost Guardrails**: per-query token/cost estimated by provider/model rate table and stored in advisor_logs.usage; /api/advisor/chat done-event returns usage; GET /api/advisor/usage (admin) aggregates queries/total_tokens/total_cost/today_cost. Advisor header shows running spend chip + each answer shows its own token/cost (admin-only). Opus 4.8 rate $15/$75 per Mtok.

## STILL MOCKED / BLOCKED (need user creds)
- Live M365 connector OAuth — needs Azure app client_id/client_secret/tenant_id + redirect URI
- True SSO/SAML + SCIM — needs IdP metadata URL/XML + signing cert

## Session 2026-06 (Spend Budget Alerts + Scheduled Studio Reports)
- **Spend Budget Alerts**: admins set a monthly advisor budget (PUT /api/advisor/budget, stored on organizations.advisor_budget_usd). GET /api/advisor/usage now returns month_cost, budget, budget_pct, budget_status (off/ok/warning≥80%/over≥100%). Advisor panel shows a colored budget bar + inline cap editor (admin-only). Crossing 80%/100% creates a deduped in-app notification (advisor_budget) per month via _check_budget after each query.
- **Scheduled Studio Reports**: admins toggle a monthly auto-email in Studio Report Builder (GET/PUT /api/studio/schedule → organizations.studio_schedule {enabled,title,sections}). New cron POST /api/cron/monthly-studio-report (1st, 09:00 UTC in .emergent/crons.yml) composes each enabled org's report (reuses _compose_report) and emails admins+execs via managed Resend + creates a delivery notification. compose_report refactored into reusable _compose_report(org_id,title,sections).

## Session 2026-06 (Budget Auto-Pause + Schedule Cadence)
- **Budget Auto-Pause**: org flag advisor_auto_pause; PUT /api/advisor/budget accepts optional auto_pause; when on and month spend ≥ cap, /api/advisor/chat returns 429 (_is_paused guard). /api/advisor/usage returns auto_pause + paused. Advisor panel adds an "Auto-pause at cap" On/Off toggle + paused banner; UI catches 429 and shows the paused message. Verified: paused=true → chat 429.
- **Schedule Cadence**: studio_schedule.cadence (weekly/monthly/quarterly). _run_studio_reports(cadences) filters orgs by cadence. Monthly cron (1st 09:00) runs {monthly} + {quarterly} on Jan/Apr/Jul/Oct; new weekly cron (Mon 09:00) runs {weekly} — both in .emergent/crons.yml. Report Builder adds a Weekly/Monthly/Quarterly selector. Verified: weekly cron 200 + delivery notification.

## Session 2026-06 (Spend Trend Sparkline + Per-User Spend + Auto-Pause Email)
- **Spend Trend Sparkline**: /api/advisor/usage now returns `trend` (last 6 months of advisor cost via _last_n_months) — rendered as a 6-bar sparkline beside the advisor budget bar (admin-only).
- **Per-User Spend**: /api/advisor/usage returns `by_user` (current-month cost + query count per teammate, desc) — rendered as a "This month by teammate" list in the advisor.
- **Auto-Pause Email**: when month spend crosses 100% and auto_pause is on, _check_budget emails admins/execs a heads-up (once per month via organizations.advisor_pause_notified; reuses Resend). set_budget $unset's the notified flag so a future breach re-notifies. (Email path wired + compiles; live send not explicitly triggered.)

## Session 2026-06 (Configurable Spend Alert Threshold + CSV Export)
- **Spend Alert Threshold**: org flag advisor_alert_threshold (default 80). Advisor budget panel adds 75/80/90% buttons; PUT /api/advisor/budget accepts alert_threshold; /api/advisor/usage returns alert_threshold and computes warning status at the chosen %. _check_budget now fires the warning notification AND a heads-up email to admins/execs at the threshold (deduped per month via advisor_alert_notified), plus the existing 100% auto-pause email. set_budget $unset's both notified flags on change.
- **Exportable Usage Report**: GET /api/advisor/usage/export → CSV (Month, Teammate, Queries, Tokens, Cost) of current-month per-teammate advisor spend + TOTAL row. "Download spend CSV" button in the advisor.

## Session 2026-06 (Teammate Drilldown + Full-History CSV)
- **Teammate Drilldown**: GET /api/advisor/usage/prompts?member=<email> (admin) returns a teammate's 15 most recent advisor prompts (prompt, ts, model, cost, tokens, response snippet). Clicking a teammate in the advisor spend list expands an inline drilldown of their recent prompts.
- **Full-History CSV**: GET /api/advisor/usage/export now accepts ?scope=all → aggregates spend per (month, teammate) across all history with an ALL/TOTAL row. Advisor shows two buttons: "This month" and "All months".

## Session 2026-06 (Auto-Emailed Spend Report + Prompt Search)
- **Auto-Emailed Spend Report**: new cron POST /api/cron/monthly-spend-report (1st, 09:30 UTC in crons.yml) emails each org's admins/execs a full per-teammate advisor spend HTML table (email pipeline is HTML-only, no file attachments) via managed Resend + creates a notification. Reuses spend_rows(org_id, scope) (also backs the CSV export). Verified: cron 200 + "Advisor spend report emailed" notification.
- **Prompt Search**: GET /api/advisor/prompts/search?q=<term> (admin) regex-searches all advisor prompts in the org (case-insensitive, 30 max). Advisor panel adds a "Search all advisor prompts…" box (Enter to run) listing matches with teammate + date + cost. Verified: q=risk → 11 matches, UI renders.

## Session 2026-06 (CSV Email Attachment + Prompt Insights)
- **CSV Email Attachment**: confirmed the managed Resend proxy accepts Resend-style attachments ([{filename, content(base64)}], returns 202). notifications.send_email now takes an optional `attachments` param; the monthly-spend-report cron attaches a real advisor-spend-all.csv so finance can open it in Excel. Verified: cron 200 + "Advisor spend report emailed" log.
- **Prompt Insights**: GET /api/advisor/prompts/insights (admin) tokenizes org prompts (stopword-filtered) and returns the top 12 recurring terms with counts. Advisor shows "Top prompt themes" chips; clicking a chip runs the prompt search. Verified: top·9, sentence·4, etc.; theme-click search works.

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
