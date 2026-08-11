# Getting Started — Obserra Control Intelligence

## 1. Access & sign in

Control Intelligence runs inside the existing Obserra web app — there is nothing to install.

1. Open the Obserra app URL in a browser.
2. Sign in with your Obserra account (email + password, Google, Apple, Enterprise SSO or a
   passwordless QR sign-in). The login screen is branded **Control Intelligence —
   Continuous Control Effectiveness & Assurance**.
3. In the left sidebar choose **Control Intelligence** (top of the navigation), or go
   directly to `/app/control-intelligence`.

**Roles**

- **Admin** — full access, including adding entries to a control log and exporting the
  Control Log PDF.
- **Executive / Operational** — the mode toggle in the top bar switches the narrative
  between executive-assurance language and operational detail. Both are fully live.

## 2. First 5 minutes (walkthrough)

1. **Mission Control** loads first. Read the six KPI cards (FACT): overall effectiveness,
   total controls, effective, at-risk, ineffective and control coverage.
2. Scan **Effectiveness by domain** and **Control health distribution** to see where control
   strength is concentrated. Each domain / series has its own color.
3. Open the **AI Control Advisor** panel and click **Ask AI Advisor** for a live analysis.
4. Click any **Top control weakness** → the standard detail card opens with details, risk,
   scoring, control alignment and AI fixes.
5. Switch to **Framework Intelligence** and click a framework card → see coverage, risk,
   scoring and the exact controls mapped to that framework (live).
6. Go to **Evidence Assurance** and generate an **Evidence Pack** or **Control Log** PDF.
7. Finish on **Mission Control** → **Executive Assurance Report** to download the board brief.

## 3. Tabs

| Tab | What you do there |
| --- | --- |
| Mission Control | Executive overview and quick actions |
| Control Effectiveness | Inspect / search / filter every control |
| Framework Intelligence | Framework readiness, convergence, crosswalk |
| Evidence Assurance | Evidence freshness queue + PDF exports |
| Remediation & Drift | Prioritized remediation + gap feed |
| Defensibility | Live source status + evidence classification |

## 4. Refresh & freshness

Use **Refresh** (top-right) to re-pull every live feed. The Mission Control footer shows the
last data refresh time, connected data sources, active frameworks, controls monitored and open gaps.

## 5. Environment (for operators)

- Frontend: React (served on port 3000, hot-reload).
- Backend: FastAPI on port 8001; all routes are prefixed with `/api`.
- The frontend always calls the backend via `REACT_APP_BACKEND_URL`.
- No environment variables need to change to use Control Intelligence — it composes on the
  existing Control Monitoring endpoints.
