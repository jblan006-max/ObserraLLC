# Obserra EIOS — CHANGELOG

## 2026-06
- **Official branding everywhere** (only logo used): `/public/brand-mark.png`, `brand-wordmark.png` (cropped from official lockup), `brand-lockup.png`. Regen: `/app/scripts/gen_brand.py`.
- **PWA**: install banner (animation + 7-day "Later" snooze), branded splash, maskable icons, adaptive favicons, iOS splash (portrait + landscape iPad).
- **Onboarding tour**: role-aware (exec/ops), spotlight on `[data-testid=mode-toggle]`, a11y (role=dialog/aria/Esc/non-persist backdrop), per-user persistence, Replay from Settings.
- **Board report PDFs** (`reports.py`): badge + watermark + footer on all exports. Board report adds cover page, **light/dark theme**, **exposure trend line** + **top-risks bar chart**, **AI Executive Summary** callout, auto **Key Takeaways**.
- **Quarterly Deck** (`layout:"deck"`): 5 landscape slides (cover, KPI snapshot, trend, risks, takeaways), theme-aware. Frontend "Deck" button + Dark/Light toggle in Board Report modal.
- **Report Recipients**: admin-only `GET/PUT /api/reports/recipients` (email-validated) → `org.report_recipients`; monthly cron emails branded PDF to admins/execs + extras.
- **Send Test Email**: `POST /api/reports/test-email` (admin/exec) generates + emails the branded PDF to self; Settings "Send me a test now" button.
- **Per-org Rebranding**: `GET/PUT /api/reports/branding` (admin) — custom company name + logo (base64, ≤~1.5MB) on all board outputs; defaults to Obserra. `_resolve_brand(org)` threads a brand object through `_build_pdf` + deck; Obserra watermark dropped when custom. Settings "Report Branding" card.
- Scheduled board PDF: cron attaches branded PDF (cover + charts + takeaways).

## Verified
- iteration_14.json frontend 6/6 PASS.
- iteration_15.json: backend 16/16 PASS + frontend 100% (report/deck × light/dark, recipients GET/PUT + 403, branding GET/PUT + 403 + reset, test-email + 403, Settings cards, modal PDF/Deck downloads). No bugs. Regression suite: /app/backend/tests/test_iter15_board_reports.py.

## Notes / gotchas
- Twice, large `search_replace` edits to `reports.py` went stale in-memory (404s); fix = re-apply + `sudo supervisorctl restart backend`, verify via curl.
- Board branding logo b64 payload uses /app/frontend/public/logo-mark-192.png in tests — keep that asset.
- Non-blocking polish backlog: validate logo MIME/magic bytes; return dropped invalid emails to UI; explicit "Remove logo"; consider splitting reports.py PDF helpers.

## 2026-08-07 — Sidebar categories + Owner all-access
- Left nav regrouped into labeled sections: 6 paid categories (AI Governance, Cyber Risk, Third-Party Risk, Asset Intelligence, Audit & Evidence, Reporting & Board) each rendered with a distinct accent color header (ai/crit/high/primary/med/low), colored dot, and a matching colored left-border wrapping the nested dashboards to signal dependency. Plus muted General "Dashboards", "Admin", "Account" sections. (`AppShell.jsx` NAV_SECTIONS + CAT_STYLE)
- Owner full unrestricted access: `OWNER_EMAILS` (default jblan2026@gmail.com) in `auth.py`. `is_owner()` forces role=admin in get_current_user, bypasses require_active_subscription, and `/api/subscription` + `/api/modules` return enterprise plan + all entitlements + all modules owned — hardcoded on login, no payment ever required.

## 2026-08-07 — 15-char passwords, self-serve SSO, team access roles, collapsible nav
- Password policy raised to 15-char minimum (auth.py PASSWORD_POLICY_MSG + validate_password_policy). Frontend hints added on register (Auth.jsx) and forced reset (ForcePasswordReset.jsx, min check 8→15). Verified: 12-char register → 400, 15-char → 200.
- Self-service Apple + Enterprise SSO config: new security.py (Fernet, APP_SETTINGS_KEK) + sso_config.py (GET/PUT /api/admin/sso, admin-gated, secrets encrypted at rest in app_config/_id=sso). social_auth.py now resolves Apple/OIDC creds from DB with env fallback; /api/auth/providers reflects DB config. New SsoCard.jsx in Settings (admin) for Team/Service/Key IDs + .p8, OIDC discovery/client id+secret, SAML metadata URL. Verified PUT/GET/clear + providers toggle.
- Team access roles: POST /api/auth/team/{id}/access sets per-user module_access (null=all). team_members returns module_access. /api/subscription computes effective per-user entitlements + `restricted` flag; AppShell owns() no longer grants enterprise bypass when restricted. Team.jsx: Access column + modal with 6 category checkboxes / All-access toggle.
- Collapsible sidebar: every named section header is a toggle (chevron) with per-section state persisted to localStorage (obserra-nav-collapsed); 6 paid categories keep their accent colors.

## 2026-08-07 — SSO test, access presets, invite-with-access, collapse-all, billing seats
- Test SSO Connection: POST /api/admin/sso/test (admin) validates an OIDC discovery URL (fetch + endpoint check) or an Apple key (ES256 client-secret build). "Test connection" buttons added in SsoCard. Verified good→ok, bad→friendly error.
- Access Presets: org-level presets (auth.py GET/POST/DELETE /api/auth/access-presets). Team access modal gets "Apply preset" dropdown + "Save as preset"; invite form gets a preset/custom selector.
- Invite With Access: InviteBody + team_invite accept module_access; invite form lets admins pick All / a preset / custom categories up front.
- Collapse All: sidebar top control toggles all sections collapsed/expanded (ChevronUp/Down), persisted to localStorage.
- Billing Seats & Access: GET /api/billing/access-summary (admin) → per-pack owned + seat_count/total_members; new card on Billing lists all 6 packs with "X of N teammates". Verified via curl + screenshot.

## 2026-08-07 — Preset manager, seat drill-down, access history, bulk access, access-change emails
- Preset Manager: Team page "Access Presets" card lists saved presets with rename (POST new + DELETE old) and delete.
- Bulk Access: member selection checkboxes (desktop + mobile) + a bulk bar; POST /api/auth/team/bulk-access applies an access preset/all to many teammates at once.
- Access Audit Trail: _log_audit now stores a `target` field; GET /api/auth/team/{id}/access-history returns team.access/team.invite entries for that member, shown as "Recent changes" in the access modal.
- Seat Drill-Down: Billing seats rows are expandable to show the exact teammates who hold each pack's access (uses access-summary `seats`).
- Access-change emails: _notify_access_change emails the teammate (managed Resend) + in-app notification whenever their dashboard access changes (single or bulk). Verified via curl (set/bulk/history) + screenshots.

## 2026-08-07 — Preset inline edit, history PDF export, notify toggle, seat search
- Preset On Invite Reuse: Preset Manager chips now have an inline category editor (SlidersHorizontal → modal with 6 checkboxes / all-access) plus rename & delete — no need to open a teammate.
- History Export: GET /api/reports/access-history/{id}.pdf builds a branded ReportLab PDF of a teammate's access changes; "Export PDF" button in the access modal (verified: application/pdf, ~213KB).
- Notify Toggle: AccessBody + BulkAccessBody now accept notify (default true); access modal has "Email this teammate about the change" and the bulk bar has "Email teammates" so admins can run quiet migrations. Verified bulk notify:false via curl.
- Seat Search: Billing "Seats & Access" card has a search box that filters/auto-expands packs to show which packs a specific teammate can reach.

## 2026-08-07 — Access diff email, bulk-from-directory, preset usage count, history filters
- Access Diff Email: _notify_access_change now takes old_ma and shows added (green) vs removed (red) packs in the teammate email; set/bulk endpoints pass the pre-change access.
- Bulk From Directory: Team page "Quick select role" buttons (Operational/Executive/Admin) select every member of a role in one click, then apply a preset via the bulk bar.
- Preset Usage Count: each Preset Manager chip shows "N in use" (teammates whose access exactly matches the preset).
- History Filters: the access modal's Change History has actor + since/until date filters (client-side); Export PDF forwards them as query params to GET /api/reports/access-history/{id}.pdf (actor/since/until). Verified: filtered PDF returns valid 213KB.

## 2026-08-07 — Preset sync, audit-log filters, CSV import, access expiry, monthly access review
- Sync Preset Members: pin a teammate to a preset (AccessBody.pin / bulk pin_preset, user.preset_pin); editing a preset auto-updates every pinned teammate's access + emails them. Access modal has a "Sync: <preset>" dropdown; member rows show a pin badge.
- History In Audit Log: AuditLog page now has actor + since/until filters over /api/audit-logs (which now carries `target`), surfacing all team.access/invite/preset events.
- CSV Team Import: POST /api/auth/team/import bulk-invites from name,email,role,preset rows (emails each teammate); Team page has a paste-CSV card.
- Access Expiry: AccessBody.expires_on stores an expiry + revert value; daily-drift-digest cron runs _run_access_expiry to auto-revert lapsed grants (clears pin) and email the teammate. Access modal has an expiry date picker; member rows show an expiry badge.
- Monthly Access Review digest: monthly-board-report cron runs _run_access_review, emailing admins a per-pack seat snapshot.
- Fix: repaired a corrupted duplicated tail in auth.py seed_admin (IndentationError) and re-applied team_members/set_member_access.

## 2026-08-07 — Connectors auto-connect on save (no blocking test)
- All 5 live connectors (M365, Copilot, ChatGPT/OpenAI, Teams, SAML/SSO) now go LIVE/READY the instant an admin saves credentials — `live_connectors.py` PUT handlers always set `live=True`/`valid=True`. Real data (Graph user/risky counts, Copilot seats, OpenAI model count, SAML entity_id) is still pulled best-effort but wrapped in try/except so an unreachable/failed check never blocks the connection. Status text now "Connected — …".
- Frontend `AvailableConnectors.jsx`: buttons relabeled "Save & connect" / "Connecting…"; toasts report "connected" (no more "NOT LIVE"/"Invalid" error path for saved creds).
- Apple + Enterprise OIDC + SAML in Settings (`SsoCard.jsx`) already save-and-enable instantly (Test connection is optional); `/api/auth/providers` reflects configured state immediately.
- Catalog connectors (Okta/AWS/Azure/CrowdStrike/Splunk/ServiceNow/Wiz) remain one-click MOCKED demos (no credential fields).
- Verified iteration_28: frontend 100% — all pills flip LIVE/READY on save with dummy creds, disconnect reverts to NOT SET, Settings SSO badges show Connected without Test. Owner org left clean.

## Jun 2026 — Owner/Board crons + Ticket Deep-Link + "Assigned to me" lens + SoD state consolidation (iteration_72)
- Backend crons verified: `run_sap_owner_digest` (weekly per-owner SoD email) + `run_sap_board_pack` (monthly exec pack + analytics PDF) — script `_t_crons.py` passed (log created, digest sent, no errors).
- Ticket Deep-Link: watchlist ticket badge → modal with full ServiceNow stage timeline via `GET /api/sap/ticket/{number}`.
- "Assigned to me" watchlist lens: `watchlist-mine-toggle` filters pinned areas to owner == logged-in email (`useAuth`).
- State consolidation refactor: new `context/SodContext.jsx` (`SodProvider`/`useSod`) replaces 50+ prop pass-throughs to the 5 SoD cards. Regression clean (iteration_72 frontend 100%).


## Jun 2026 — Owner Leaderboard + Board-Pack on-demand + Ticket live-refresh + Digest deep-links (iteration_73)
- Owner Accountability Leaderboard: `GET /api/sap/watchlist/leaderboard` + `SodOwnerLeaderboard.jsx` — ranked owners by open Critical SoD, unowned-Critical tile, expandable per-area breakdown.
- Board Pack on-demand: `GET /api/sap/board-pack/preview` + admin `POST /api/sap/board-pack/send` + `SodBoardPackCard.jsx` (preview modal + one-tap send; records monthly log).
- Ticket timeline Live Refresh: watchlist ticket modal polls `/sap/ticket/{number}` every 4s while open ("auto-refreshing" chip).
- Owner Digest Deep-Links: `_owner_digest_html` area rows link to `/app/sod?wl=<area>`; watchlist scrolls to + ring-highlights that card.
- Verified frontend 100% (iteration_73). Fixed a transient `cardRef` runtime error from a silent partial edit.


## Jun 2026 — Leaderboard Nudge + Assign-from-Leaderboard + Board-Pack Scheduling + Timeline Toast (iteration_74)
- Leaderboard Nudge: admin `POST /api/sap/watchlist/leaderboard/nudge` + "Nudge all owners" button (confirm-gated) — emails each owner their hot spots now.
- Assign From Leaderboard: leaderboard `unassigned` areas + inline owner-email/Assign → `/sap/watchlist/remediate`, live-refreshes the board.
- Board Pack Scheduling: `sap_board_pack_config` + `GET/PUT /api/sap/board-pack/config`; inline enable/day/recipients editor + header chip; cron gates on enabled AND day-of-month.
- Timeline Toast: ticket modal toasts when a live-refreshing change advances a stage.
- Verified frontend 100% (iteration_74). Baseline reseeded (kept Finance pin).


## Jun 2026 — Walkthroughs & setup guides rebuilt for SAP UAC (with screenshots)
- `scripts/capture_shots.py`: captures 14 live SAP UAC screens (incl. Watchlist/Owner-Leaderboard/Board-Pack). Reinstalled Playwright Chromium 1234.
- `scripts/gen_docs.py`: SAP UAC Install & User Guide → PDF (16 pages) + DOCX (14 images) in `backend/assets/docs/`, verified by rendering.
- `deploy.py` + `Settings.jsx`: SAP UAC download filenames + email/section copy; auto-refresh pipeline unchanged.
- `OnboardingTour.jsx`: EXEC/OPS steps rewritten for SAP UAC (SoD Command Center focus).

## Fix — In-App Tour never mounted (Jun 2026, screenshot-verified)
- Root cause: `OnboardingTour` was defined but never imported/rendered anywhere, so first-login auto-show and the Settings "Replay tour" event had no listener, and the step preview screenshots never appeared.
- Fix: mounted `<OnboardingTour />` in `AppShell.jsx` (beside `<SapAdvisor />`). Restores auto-show on first login, Settings → Replay tour, and the SAP UAC dashboard preview image on every step.
- Verified via screenshot: tour opens on both paths; `tour-preview` image loads (naturalWidth 1440) on step 1 (Welcome) and step 2 (Executive Mode, spotlight on mode toggle).

## Feature — One-click "Regenerate tour images" (Jun 2026, curl + screenshot-verified)
- Admins can recapture the in-app onboarding tour previews (`/tour/{overview,sod,watchlist,monitoring}.jpg`) so they always match the current UI after a redesign.
- `scripts/capture_shots.py`: added `SHOT_TOUR_ONLY=1` mode → captures only the 4 tour-mapped screens then copies to `frontend/public/tour/`.
- `backend/deploy.py`: `regenerate_tour_images()` + `POST /api/deploy/regenerate-tour` (admin-only, runs capture in a threadpool so it doesn't block the event loop; returns the refreshed image list).
- `Settings.jsx`: "Regenerate tour images" button beside "Regenerate guides" (180s client timeout).
- Note: this forked pod had Playwright browser build 1208 but the Python package expects 1234 — reinstalled chromium 1234 to `/pw-browsers`. Endpoint verified: 200, all 4 images refreshed in ~19s.

