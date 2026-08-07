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
