# Obserra EIOS — CHANGELOG

## 2026-06
- **Official branding everywhere**: user-provided assets are the only logo used — `/public/brand-mark.png` (symbol), `/public/brand-wordmark.png` (name, cropped from official lockup for exact font match), `/public/brand-lockup.png` (horizontal). Regen: `/app/scripts/gen_brand.py`. Auth (symbol + large wordmark), sidebar, header, advisor, install banner, splash, favicon, PWA/maskable icons, iOS splash (21, portrait + landscape iPad), onboarding-tour badge.
- **PWA**: install banner (beforeinstallprompt, animation + 7-day "Later" snooze + dismiss), branded splash, maskable icons (52% safe zone), adaptive favicons.
- **Onboarding tour** (`OnboardingTour.jsx`): role-aware (exec vs operational), spotlight on real `[data-testid=mode-toggle]`, a11y (role=dialog/aria-modal/aria-labelledby, Esc, non-persisting backdrop dismiss), per-user persistence, Replay from Settings.
- **Board report PDFs** (`reports.py`): branded on all exports (badge + watermark + footer). Board report (`/api/reports/pdf`, cover=True) adds:
  - branded **cover page** with **light/dark theme** option (`theme` param; light uses `brand-lockup-dark.png`),
  - **Portfolio Residual Exposure ($M)** line chart + **Top Risks by Residual Score (/25)** bar chart (reportlab graphics),
  - auto **Key Takeaways & Recommended Actions** from live metrics.
  - Reusable `build_board_report_pdf(org_id, report, title, theme)`.
- **Scheduled board PDF**: monthly cron (`_run_monthly_board_reports`) now emails the branded PDF as an attachment (cover + charts + takeaways), not just HTML.
- **Frontend**: Board Report modal has a Dark/Light cover toggle (`data-testid` theme-dark / theme-light) driving the export.

## Verified
- iteration_14.json frontend 6/6 PASS. Board PDFs (dark + light) rendered & visually confirmed: cover, trend line, risk bars, takeaways, watermark, footer.
