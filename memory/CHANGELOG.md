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
