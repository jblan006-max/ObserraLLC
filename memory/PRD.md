# Obserra EIOS — PRD

## Product
Enterprise SaaS "continuous AI control plane" with Dual-Mode dashboards (Executive $-impact vs Operational counts), a Shared Cybersecurity Kernel, live connectors (M365/Copilot/ChatGPT/Teams/SSO), Compliance Posture, Web-Push, JIT provisioning, and a fully installable PWA. Frontend: React + Tailwind. Backend: FastAPI + MongoDB. Language: English.

## Official Branding (source of truth)
- User-provided official assets used everywhere (transparent, so they blend on any background):
  - `/public/brand-mark.png` — official eye + keyhole symbol
  - `/public/brand-wordmark.png` — official "OBSERRA / Executive Protection & Intelligence LLC" wordmark (cropped from the official lockup, so the font matches exactly)
  - `/public/brand-lockup.png` — official horizontal lockup (sidebar/header)
- Generated from the official mark: PWA icons (`logo-mark-*`), maskable icons (`logo-maskable-*`, 52% safe zone), favicons (`favicon-16/32/48.png`), and 21 iOS `apple-touch-startup-image` splash PNGs (portrait + landscape iPad) in `/public/ios/`.
- Regeneration script: `/app/scripts/gen_brand.py` (reads /tmp/off_2.png + /tmp/off_1.webp).
- Auth page: symbol on top + large wordmark below (desktop h-16 xl:h-20, mobile h-14). Splash + sidebar + header all use the same official assets → brand matches on every page. **User approved the look.**

## Implemented (2026-06)
- HD official logo across Auth/PWA; transparent blend (no navy box).
- PWA: install banner (`InstallBanner`, beforeinstallprompt, gentle animation + "Later" 7-day snooze + dismiss), branded launch `Splash`, iOS splash (portrait + landscape iPad), maskable icons, adaptive favicons.
- Onboarding Tour (`OnboardingTour`, mounted in AppShell):
  - Role-aware: EXEC_STEPS (admin/exec) vs OPS_STEPS (operational).
  - 3 steps, progress bar + dots, Back/Next/Skip/Get started; persists per-user (`obserra-tour-done-<id>`).
  - Spotlight: dims screen and pulses a ring around the real `[data-testid=mode-toggle]` on the mode steps.
  - Replay from Settings ("Replay tour", data-testid `replay-tour`) via `obserra-replay-tour` event.
- Prior session: Dual-mode split, Available Connectors page, Compliance Posture + cron Teams digest, mobile nav drawer, Web-Push, JIT provisioning, security hardening, Auth overhaul (Passwordless/Apple/SSO gated).

## Test status
- iteration_14.json: frontend 6/6 PASS (brand consistency + exec/ops tour + spotlight + replay). Fixed missing Settings icon imports.
- Credentials in `/app/memory/test_credentials.md`.

## Backlog / Roadmap
- P1 (blocked): Apple Sign-In + Enterprise SSO — awaiting user IdP metadata/Apple keys (logic wired, buttons gated by `/api/auth/providers`).
- P2: a11y on tour modal (role=dialog/aria), backdrop-click should not persist done key, landscape iPhone splash, tour spotlight for operational nav items.
