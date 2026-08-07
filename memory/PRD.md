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
- Tablet + mobile UX pass (Jun 2026): tablet 2-up breakpoints (Overview exec+operational KPIs `md:col-span-2`, operational quarter charts 2-up); Advisor first-time hint anchored just above the FAB and clamped to viewport width; Risk Register filter bar sticky (`top-16`); mobile card views for data-heavy tables (Risk Register `risk-cards-mobile`, Control Monitoring `control-cards-mobile`) with desktop tables `hidden md:block`; guide auto-refresh (POST /api/deploy/regenerate-guides admin + startup regen + Settings "Regenerate guides" button). Verified iteration_20 (backend 5/5, frontend 100%).
- Mobile responsiveness pass (Jun 2026): global `overflow-x-hidden` + `min-w-0` on main content with mobile bottom padding (clears floating Advisor); Enterprise/tab rows made horizontally scrollable; Situation Room rows use min-w-0/truncate + shrink-0 badges; Kernel KPI + Evidence modal grids made responsive. Verified 0 horizontal overflow (scrollWidth==clientWidth at 390px) across Enterprise, Situation Room, Kernel, Controls, Risk Register, AI Governance.
- P1 (blocked): Apple Sign-In + Enterprise SSO — awaiting user IdP metadata/Apple keys (wired, gated by `/api/auth/providers`).
- P2: landscape iPhone splash; per-role nav spotlight; hide Google/Apple buttons if user wants zero 3rd-party logos; report cover date/version options.
