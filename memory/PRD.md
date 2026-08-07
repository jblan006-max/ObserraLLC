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

## Backlog / Roadmap
- P1 (blocked): Apple Sign-In + Enterprise SSO — awaiting user IdP metadata/Apple keys (wired, gated by `/api/auth/providers`).
- P2: landscape iPhone splash; per-role nav spotlight; hide Google/Apple buttons if user wants zero 3rd-party logos; report cover date/version options.
