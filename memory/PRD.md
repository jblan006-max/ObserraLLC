# Obserra EIOS — PRD

## Product
Enterprise SaaS "continuous AI control plane" with Dual-Mode dashboards (Executive $-impact vs Operational counts), Shared Cybersecurity Kernel, live connectors (M365/Copilot/ChatGPT/Teams/SSO), Compliance Posture, Web-Push, JIT provisioning, installable PWA. React + Tailwind / FastAPI + MongoDB. English only.

## Official Branding (source of truth — the ONLY logo used anywhere)
- User-provided official assets (transparent so they blend on any background):
  - `/public/brand-mark.png` — eye + keyhole symbol
  - `/public/brand-wordmark.png` — "OBSERRA / Executive Protection & Intelligence LLC" (cropped from the official lockup so the font matches exactly)
  - `/public/brand-lockup.png` — horizontal lockup (sidebar/header)
- Generated from official mark: PWA icons, maskable icons (52% safe zone), favicons, 21 iOS splash PNGs (portrait + landscape iPad). Script: `/app/scripts/gen_brand.py`.
- Used on: Auth (symbol + large wordmark), sidebar, header, advisor, install banner, splash, favicon, onboarding tour badge. No third-party logos except required Google/Apple sign-in button marks.

## Board Report PDFs (reports.py `_build_pdf`)
- Branded on every export (board report, studio report, evidence pack): top-left badge, subtle centered watermark, footer "Obserra — Executive Protection & Intelligence LLC · Confidential".
- Board report (`POST /api/reports/pdf`, cover=True) adds:
  - Branded **cover page** (navy + full lockup + title + org name + date + confidential banner).
  - **Portfolio Residual Exposure ($M) line chart** (reportlab graphics) from health history + residual ALE.
  - Auto **Key Takeaways & Recommended Actions** derived from metrics (exposure/reduction %, critical risks, pending recs).
- Backend brand assets: `/app/backend/assets/` (brand-badge.png, brand-watermark.png, brand-lockup.png).
- Email HTML report also carries the logo (public asset URL).

## Onboarding Tour (OnboardingTour.jsx, mounted in AppShell)
- Role-aware: Executive (admin) vs Operational steps. 3 steps, progress bar + dots, Back/Next/Skip/Get started.
- Only the official mark shown in the step badge.
- Spotlight: dims screen + pulses ring around real `[data-testid=mode-toggle]` on mode steps.
- a11y: role=dialog, aria-modal, aria-labelledby, Escape closes; backdrop click dismisses WITHOUT persisting done flag.
- Persist per-user (`obserra-tour-done-<id>`); Replay from Settings ("Replay tour", `obserra-replay-tour` event).

## Test status
- iteration_14.json: frontend 6/6 PASS (brand consistency + exec/ops tour + spotlight + replay).
- Board PDF verified via render (doc-verification skill): cover + chart + takeaways + watermark/footer all correct.
- Credentials in `/app/memory/test_credentials.md`.

## Recent polish (Jun 2026)
- Settings: "Remove logo / Reset to Obserra" button; logo type/size validation + dropped-invalid-email recipient feedback.
- AIAdvisor floating button: navy (#0f1e3d) pill, white eye mark; first-time hint bubble + pulse (hint-open analytics in /advisor/usage); in-chat reply avatars use navy eye badge.
- Report Branding: LIVE cover preview (pymupdf GET /api/reports/branding/preview) with Dark/Light toggle; brand accent colour flows into cover org text + trend line + risk bars.
- Board Report modal: branded cover thumbnail preview column (theme-aware).
- **Distribution & docs**: PWA hardened for one-click install (service worker /push-sw.js with offline shell registered on load; manifest id/shortcuts) across desktop/mobile. On-premise Docker package (/app/deploy/onprem: docker-compose, Dockerfiles, nginx.conf, .env.example, INSTALL.md, optional install.sh) downloadable via GET /api/deploy/onprem-package (admin). Auto-generated PDF + Word Install & User Guide with dashboard screenshots (scripts/gen_docs.py → /api/deploy/guide.pdf, /guide.docx, admin). Settings "Deployment & Documentation" card exposes all three downloads. Video walkthrough NOT produced (agent cannot record video) — built-in Guided Tour offered as in-app alternative. Verified iteration_19 (backend 9/9, frontend 100%).

## Backlog / Roadmap
- Filters + weekly cron + two-pane everywhere + recipients book (Jun 2026): search+status/role/tier filters on Team/Vendors/Agents (apply to cards AND tables via shown* arrays); weekly guide-refresh cron (`POST /api/cron/weekly-guide-refresh`, WEBHOOK_CRON_SECRET) — capture offloaded to a DETACHED subprocess so it never blocks the API loop; in crons.yml top-5 (weekly-studio-report bumped below the active-5 line — flagged to user); two-pane detail for Vendors (`vendor-detail-pane`) and Control Monitoring (`control-detail-pane`); IT recipients book (`GET/PUT /api/deploy/recipients`) with Settings chips (save/pick/remove). Verified iteration_22 (backend 100%, frontend 100%; tester fixed 3 crashers: AIAgents missing q/statusF state, Settings missing Bookmark/X imports, Team members.map→shownMembers.map).
- Card views + pipeline + two-pane + email (Jun 2026): mobile card views for Team (`member-cards-mobile`), Third-Party Risk (`vendor-cards-mobile`), AI Agents (`agent-cards-mobile`) with desktop tables `hidden md:block`; Playwright screenshot pipeline `scripts/capture_shots.py` wired to `POST /api/deploy/regenerate-guides?capture=true`; Risk Register tablet/desktop two-pane detail (`risk-detail-pane`, row click sets `selected`, mobile keeps modal); admin email-docs (`POST /api/deploy/email-docs`, PDF+zip attachments via kernel.notifications) with Settings email UI. Verified iteration_21 (backend 7/7, frontend 100%).
- Tablet + mobile UX pass (Jun 2026): tablet 2-up breakpoints (Overview exec+operational KPIs `md:col-span-2`, operational quarter charts 2-up); Advisor first-time hint anchored just above the FAB and clamped to viewport width; Risk Register filter bar sticky (`top-16`); mobile card views for data-heavy tables (Risk Register `risk-cards-mobile`, Control Monitoring `control-cards-mobile`) with desktop tables `hidden md:block`; guide auto-refresh (POST /api/deploy/regenerate-guides admin + startup regen + Settings "Regenerate guides" button). Verified iteration_20 (backend 5/5, frontend 100%).
- Mobile responsiveness pass (Jun 2026): global `overflow-x-hidden` + `min-w-0` on main content with mobile bottom padding (clears floating Advisor); Enterprise/tab rows made horizontally scrollable; Situation Room rows use min-w-0/truncate + shrink-0 badges; Kernel KPI + Evidence modal grids made responsive. Verified 0 horizontal overflow (scrollWidth==clientWidth at 390px) across Enterprise, Situation Room, Kernel, Controls, Risk Register, AI Governance.
- P2 polish — landscape splash, nav spotlight, auth toggle, report cover (Jun 2026, iteration_27 — frontend 100%):
  - **Landscape iPhone Splash**: gen_brand.py now emits portrait+landscape for all 15 devices (30 apple-touch-startup-image tags in index.html).
  - **Role Nav Spotlight**: OnboardingTour steps support a `target` testid; exec tour spotlights `nav-overview`, ops tour spotlights `nav-risk-register`.
  - **Auth Button Toggle**: admin switch (Settings `login-screen-settings` → `PUT /api/settings/auth-ui`, global app_config) hides Google & Apple on the login screen; `/api/auth/providers` returns `hide_social`.
  - **Report Cover Options**: Board Report modal `cover-options` bar (date + version/revision) threaded through `/api/reports/pdf` → `_paint_cover`/deck footer. Cover PDF visually verified.
- PAID DASHBOARD ADD-ONS (Jun 2026 — backend verified via curl + grant sim; extends existing payments.py/Marketplace):
  - **6 packs** (each = one entitlement, monthly+yearly Stripe prices, placeholder pricing): AI Governance ($79/$790), Cyber Risk ($99/$990), Third-Party Risk ($59/$590), Asset Intelligence ($49/$490), Audit & Evidence ($39/$390), Reporting & Board ($69/$690). Enterprise all-access ($2999/mo, $32388/yr) unlocks everything (plan="enterprise").
  - Backend `payments.py`: CATALOG + PACKS + `_PACK_BY_LOOKUP`; `/api/modules` returns packs w/ owned; `/api/modules/checkout` accepts `lookup_keys[]` (multi-line subscription checkout); `_grant` grants entitlement + issues license key (`OBS-XXXX-…`, stored on `org.licenses`) + emails admins; `/api/licenses` lists keys. Stripe sandbox catalog created via setup_catalog.
  - Frontend: Marketplace rewritten (6 pack cards, monthly/yearly toggle, multi-select + "Enable access" bar → multi checkout); `LockedGate.jsx` upgrade screen (per-pack pages + monthly/yearly buy buttons) shown by AppShell when a route's `ent` isn't owned (NAV items now carry pack entitlements); Settings "Add-on License Keys" card (copyable). PaymentSuccess polls status → grant.
  - Tax mode: Stripe-managed (SMP) with automatic-tax fallback (US sandbox).
  - VERIFICATION NOTE: gating UI (LockedGate) not visually shown on the demo org because it is Enterprise/all-access; a trial or per-pack org sees gates. Full Stripe checkout completion needs a real test-card purchase (external Stripe page).
  - **Momentum Digest (email)**: `_run_momentum_digest` wired into the already-scheduled `weekly-drift-digest` cron (Mon 08:00 UTC) — emails admins/execs a one-liner "Risk-reduction score moved X→Y this week" + counts, via `compute_momentum(org_id)` (refactored shared helper in routes.py). Verified: cron 200, notification "score 0 to 66 emailed".
  - **Bulk Log Export**: admin `GET /api/reports/logs-pack.pdf` — one branded "Audit Evidence Binder" PDF (cover page + all control & vendor logs grouped by ref/owner). Settings card `evidence-binder-settings` with download button. PDF layout visually verified.
  - **Owner Auto-Match**: `GET /api/owners` now returns a `suggestion` per owner (exact then first-name match against team members); Settings shows a "Use <email>" button (`owner-suggest-*`) to one-tap fill. Verified: Dana Ops → analyst@obserra.demo.
- Momentum trend + owner directory + log export (Jun 2026, iteration_25 — backend 9/9, frontend 100%):
  - **Momentum Trend**: `/api/remediation/activity` returns `trend[]` (8 weekly points, each a 30-day trailing score); Executive "Remediation Momentum" card renders an area chart (`exec-momentum-trend`) of the trajectory.
  - **Owner Directory**: `GET/PUT /api/owners` (org.owner_directory, name→email, lowercased keys). `_nudge_owner` resolves directory → user-name match → admin fallback. Settings "Owner Directory" card (`owner-directory-settings`) lists distinct control+vendor owners with editable emails. Vendors now carry an `owner` field (seeded per-vendor; existing backfilled to "GRC Team").
  - **Log Export**: admin-only branded PDFs `GET /api/reports/control-log/{id}.pdf` & `/api/reports/vendor-log/{ref}.pdf` (reports.py `_log_pdf`, reuses `_build_pdf`/brand). Detail-pane "Export PDF" buttons (`control-log-export`/`vendor-log-export`) shown for admins when the log is non-empty. PDF layout visually verified (badge, title, owner subtitle, per-entry kind/date/text/author, watermark, footer).
- Remediation log polish — filtering, owner nudges, exec rollup (Jun 2026, iteration_24 — backend 6/6, frontend 100%):
  - **Log Filtering**: Control & Vendor detail-pane logs are filterable by kind (`control-log-kind`/`vendor-log-kind`) and searchable (`control-log-search`/`vendor-log-search`); empty result shows "No matching entries." (client-side `shownHistory`).
  - **Owner Notifications**: Adding a `remediation` note fires `_nudge_owner` (routes.py) — creates an in-app notification and emails the matched owner (by name→user) or falls back to org admins/execs; vendors nudge admins/execs. Non-remediation kinds do NOT notify.
  - **Exec Log Rollup**: `GET /api/remediation/activity` returns a risk-reduction momentum score (`min(100, remediation*12 + evidence*6 + applied_recs*8)`, 30-day window) + recent merged activity. Executive Overview renders a "Remediation Momentum" card (`exec-remediation-momentum`, `exec-risk-reduction-score`, `exec-remediation-activity`), auto-refreshing every 20s.
- Shareable Filters + Recipients One-Tap Send + Two-Pane Deep Actions (Jun 2026, iteration_23 — backend 8/8, frontend 5/5, 100%):
  - **Shareable Filters**: `useUrlState` hook (URL query sync via useSearchParams, replace:true) applied to search/status/category/role/tier filters on Cyber Risk Register (`/app/risks`), Control Monitoring, AI Agents, Team, Third-Party Risk. Filtered views are bookmarkable/shareable; state restored on reload & direct URL.
  - **Recipients One-Tap Send**: `POST /api/deploy/email-docs-all` blasts PDF guide + on-prem zip to all saved `deploy_recipients` (400 when none; swallows per-recipient failures, returns success count). Settings "Deployment & Documentation" card shows "Send to whole IT list (N)" button when the book has entries.
  - **Two-Pane Deep Actions**: Control (`control-detail-pane`) & Vendor (`vendor-detail-pane`) detail panes now embed an inline "Remediation & evidence log" (add + read). Backend: `GET/POST /api/controls/{id}/history|notes` (control_notes) and `GET/POST /api/vendors/{ref}/history|notes` (vendor_notes); kind whitelist remediation/evidence/note, empty text → 400.
- P1 (blocked): Apple Sign-In + Enterprise SSO — awaiting user IdP metadata/Apple keys (wired, gated by `/api/auth/providers`).
- P2: landscape iPhone splash; per-role nav spotlight; hide Google/Apple buttons if user wants zero 3rd-party logos; report cover date/version options.


## Security Scanner + AI Autonomous Remediation + ECG Vitals (Aug 2026, iteration_33 — backend 12/12, frontend 100%)
- **Live pen-test scanner** (`self_scan.py`): probes the REAL public endpoint (`_target_base()` → FRONTEND_URL) through the ingress (not localhost), checks security headers, CORS, and dependency CVEs live via OSV.dev + CISA KEV cross-reference. Score + severity breakdown; results auto-update the compliance crosswalk (`scan_evidence` gaps/aligned).
- **Both MITRE datasets** on every finding: MITRE ATT&CK techniques (`_MITRE`, `mitre[]` + `mitre_techniques[]`) AND MITRE CWE weaknesses (`_CWE`, `cwe[]` + `cwe_ids[]`).
- **AI Autonomous Remediation Engine** (Emergent LLM key + Claude sonnet, `_ai_review`): daily cadence (fanned out from the already-scheduled `daily-drift-digest` cron via `_run_autonomous_all`), pause/resume + enable/disable + auto-apply-config toggle stored on `org.auto_engine`. Auto-applies ONLY safe non-breaking config fixes (`_AUTO_SAFE_IDS`); dependency upgrades ALWAYS notify + wait for admin approval (`scan_approvals`, in-app notifications). Endpoints: GET/PUT `/api/self-scan/engine`, POST `/engine/run`, POST `/upgrade/approve` {approval_id, approve}.
- **First one-click-install bootstrap** (`bootstrap_first_install`, idempotent via `platform_config.installed_at`, scheduled at startup): records the endpoint, enables the daily engine for every org, and runs an initial live scan so the app goes live with THAT endpoint's data.
- **Connected devices & health** (`GET /api/self-scan/assets`): connector sources + health, live Intune managed-device inventory via Microsoft Graph (`_m365_devices`, needs DeviceManagementManagedDevices.Read.All — shows connect note when M365 not connected), and an `overview` {app_health, compliance_pct, security_score}. Devices labelled by name · owner · os/model.
- **ECG heartbeat UI** (`SecurityScanner.jsx` `HeartbeatTrace`): hospital-monitor vitals — pulse (verified/green), slow-warn (stale/degraded/amber), standby (available/cyan idle-blip), flatline (disconnected/grey), each with a numeric health index. 3 primary monitors (App Health, Compliance, Endpoint Security). Auto-polls every 20s so newly connected sources/devices stream in live. Fixed the iter32 `toggleRemediate` ReferenceError.

## Threat-intel continuous sync + AI Autofix + Real Patch Apply + Trends/Alerts/Device drilldown (Aug 2026, iter34 passed 100%)
- Real Patch Apply: approving a dependency upgrade runs a background maintenance job (pip upgrade → re-pin requirements.txt → auto re-scan) that provably confirms the CVE cleared. Success path proven (certifi no-op), graceful no-fix path (ecdsa) works, and incompatible upgrades (starlette 0.47.2 vs FastAPI 0.115.6) stay gated behind approval. Endpoints: POST /api/self-scan/upgrade/approve returns job_id; GET /api/self-scan/maintenance[/id].
- Scan History Trends: GET /api/self-scan/trend feeds a recharts area/line trajectory (score + open findings).
- Slack/Teams Alerts: org.scan_alerts {teams_url, slack_url} (Teams falls back to live_teams webhook). _post_chat_alert fires on every "approval needed" queue + upgrade outcome. GET/PUT /api/self-scan/alerts (empty fields are no-ops so one webhook never wipes the other), POST /alerts/test.
- Live Device Drilldown: GET/POST /api/self-scan/device/{id}/checklist + POST /device/{id}/sync (Graph syncDevice). Non-compliant Intune devices open a one-click remediation checklist modal. Shows connect-note when M365/Intune not connected.
- Continuous threat-intelligence sync (_sync_intel, 6h TTL + on-scan refresh via _load_kev_set + daily cron + install bootstrap): CISA KEV catalog (version/count/released), MITRE ATT&CK release version (attack-stix-data index), OSV (live-per-scan), MITRE CWE (v4.16). GET /api/self-scan/intel shows per-feed last-updated; POST /api/self-scan/intel/refresh = Force update button.
- AI Autofix now: POST /api/self-scan/autofix runs scan+AI review+apply-safe+queue-upgrades immediately (force bypasses engine enabled/paused). Prominent "AI Autofix now" button next to Run live scan.

## Close-loop upgrades + Feed rules + Exploit timeline + Device auto-remediate + Real-time containment (Aug 2026)
- Real Upgrade Close-Loop: _COUPLED map bumps companion packages together (FastAPI↔Starlette, Pydantic→FastAPI); pins all bumped pkgs to installed versions; _smoke_import subprocess check gates job status (success/applied/failed) so a broken coupled framework never silently ships.
- Feed Alert Rules: _sync_intel diffs new KEV entries (added_since_last) and _alert_new_kev_matches pings Teams/Slack + notifications when a newly-added KEV CVE matches a dependency in the org's latest scan.
- Exploit Timeline: KEV dateAdded stored in threat_intel.kev_set.dates; findings carry kev_added; UI shows "In CISA KEV since <date> · Nd to remediate".
- Device Auto-Remediate: POST /api/self-scan/device/{id}/remediate pushes compliance policy via Graph syncDevice + windowsDefenderScan, completes checklist; modal "Auto-remediate (push policy)" button.
- Real-time Threat Containment: containment_events collection; _evaluate_threats runs on every scan + on new-KEV sync; auto-contains actively-exploited deps (advisory) and M365 high-risk users (real revokeSignInSessions when connected). Endpoints GET /api/self-scan/containment, POST /containment/{id}/review {acknowledge|rollback}, POST /containment/scan. UI: "Real-time threat containment" live feed with enforced/advisory tags + Acknowledge/Roll back.
