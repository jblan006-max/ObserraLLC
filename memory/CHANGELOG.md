# Obserra EIOS — CHANGELOG

## 2026-06
- **Official branding everywhere** (only logo used): `/public/brand-mark.png`, `brand-wordmark.png` (cropped from official lockup for exact font), `brand-lockup.png`. Regen: `/app/scripts/gen_brand.py`. Used on Auth, sidebar, header, advisor, install banner, splash, favicon, PWA/maskable icons, iOS splash (21, portrait + landscape iPad), onboarding-tour badge.
- **PWA**: install banner (animation + 7-day "Later" snooze + dismiss), branded splash, maskable icons (52% safe zone), adaptive favicons.
- **Onboarding tour** (`OnboardingTour.jsx`): role-aware (exec vs operational), spotlight on `[data-testid=mode-toggle]`, a11y (role=dialog/aria-modal/aria-labelledby, Esc, non-persisting backdrop dismiss), per-user persistence, Replay from Settings.
- **Board report PDFs** (`reports.py`, all exports get badge + watermark + footer). Board report (`/api/reports/pdf`) adds:
  - branded **cover page** with **light/dark theme** (`theme` param; light uses `brand-lockup-dark.png`),
  - **exposure trend line chart** + **Top Risks bar chart** (reportlab graphics),
  - **AI Executive Summary** callout (extracted from the report's Executive Summary section) at the top,
  - auto **Key Takeaways & Recommended Actions** from live metrics.
  - Reusable `_board_metrics()`, `build_board_report_pdf()`.
- **Quarterly Deck** (`build_board_deck_pdf`, `layout:"deck"`): 5 landscape slides — cover, Enterprise Snapshot (KPI cards), Exposure Trend, Top Risks, Key Takeaways. Frontend "Deck" button in Board Report modal.
- **Report Recipients**: `GET/PUT /api/reports/recipients` (admin-only, email-validated) stored on `org.report_recipients`; Settings "Board Report Recipients" card. Monthly cron emails branded PDF to admins/execs **plus** extra recipients.
- **Scheduled board PDF**: monthly cron attaches the branded PDF (cover + charts + takeaways), not just HTML.
- **Frontend**: Board Report modal has Dark/Light cover toggle + PDF + Deck download buttons.

## Verified
- iteration_14.json frontend 6/6 PASS.
- Board report + deck (dark & light) rendered and visually confirmed: covers, exec-summary callout, trend line, risk bars, KPI slide, takeaways, watermark, footer.
- Recipients GET/PUT verified via curl (validation drops bad emails).

## Notes / gotchas
- Twice during this session, large `search_replace` edits to `reports.py` silently reverted (stale in-memory module → 404s). Fix: re-apply + `sudo supervisorctl restart backend`. Verify new routes with a curl after restart.
