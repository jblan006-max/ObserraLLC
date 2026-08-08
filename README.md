# Obserra — Executive Protection & Intelligence (v1)

A continuous **AI control plane** for enterprise cyber-risk, AI governance, and board-defensible
financials. Dual-mode (Executive / Operational) dashboards, a Unified Risk Correlation Engine, a
universal deep-dive on every card (live risk rating/score, grounded AI recommendations, honest
"$ at stake / reduction if fixed", and one-click **Add to remediation plan**), FAIR-style
Monte-Carlo scenario ranges, and high-fidelity Board / CFO / SOC report generation.

> **Live-only, No-Mock:** the platform runs purely on live data and real provider calls. There is
> no seeded demo data — sparse lists are expected until live scans/connectors populate them.

## Tech stack
- **Frontend:** React + Tailwind + shadcn/ui (PWA — installable "Add to Home Screen" on desktop & mobile)
- **Backend:** FastAPI (Python), all routes prefixed with `/api`
- **Database:** MongoDB
- **Integrations:** Emergent LLM key (OpenAI / Anthropic / Gemini), Stripe (billing), Slack/Teams
  webhooks, and live SaaS connectors (Microsoft 365 / Intune, GitHub, ServiceNow CMDB, etc.)

## Project layout
```
backend/     FastAPI app (server.py + routers: risk_engine, ai_advisor, studio, reports, ...)
frontend/    React app (src/pages dashboards, src/components shared UI, src/context providers)
scripts/     Utility scripts
tests/       Test helpers
memory/      Product docs (PRD.md, changelog)
```

## Run locally (self-host)
This is a cloud web app — it requires a backend server, a MongoDB instance, and internet access to
the configured cloud APIs. It is **not** an offline/USB installer.

1. **Backend**
   ```bash
   cd backend
   pip install -r requirements.txt
   cp .env.example .env   # then fill in the values
   uvicorn server:app --host 0.0.0.0 --port 8001
   ```
2. **Frontend**
   ```bash
   cd frontend
   yarn install
   cp .env.example .env   # set REACT_APP_BACKEND_URL
   yarn start
   ```
3. Open the frontend URL in any browser. To "install" it like an app, use the browser's
   **Install app / Add to Home Screen** option.

## Environment variables
See `backend/.env.example` and `frontend/.env.example`. Never commit real secrets — `.env` files are
git-ignored.

## Deploy (recommended release path)
Deploy from Emergent (Publish) to get a live URL that works on any device with **zero install**.
That live URL is the intended v1 distribution — share it by link, email, or QR; users can then
Install it as a PWA.

---
© Obserra — Executive Protection & Intelligence LLC.
