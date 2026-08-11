# Obserra Control Intelligence

**Continuous Control Effectiveness & Assurance.**

Control Intelligence is an Obserra application that turns your live control telemetry into
board-ready assurance. It measures control effectiveness, evidence freshness, framework
coverage and drift — and separates source **facts** from **modelled** calculations and
**AI recommendations** so every number is defensible.

- **App route:** `/app/control-intelligence` (sidebar → *Control Intelligence*)
- **Backend:** reuses the existing Obserra Control Monitoring services — **no new backend
  service or database collection is introduced.**
- **Strict rule:** everything is live. No mockups, no placeholders. If a source is
  unavailable it is shown as *UNAVAILABLE*, never substituted with fake data.

## Data lineage (live feeds)

Every panel is derived from a live Obserra endpoint:

| Panel / Dashboard | Live source |
| --- | --- |
| KPIs, health distribution, domain effectiveness, weaknesses, drift, evidence freshness | `GET /api/controls` |
| Control coverage, framework readiness, gaps | `GET /api/controls/compliance` |
| Cross-framework convergence, crosswalk matrix | `GET /api/controls/crosswalk` |
| Control history (detail modal) | `GET /api/controls/{id}/history` |
| Add to control log (admin) | `POST /api/controls/{id}/notes` |
| Data source / connector status | `GET /api/connectors/health` |
| Evidence Pack PDF | `POST /api/reports/evidence-pack` |
| Control Log PDF | `GET /api/reports/control-log/{id}.pdf` |
| Executive Assurance Brief PDF | `POST /api/studio/report/pdf` |
| AI advisor & explanations | live Obserra Advisor (`/api/sap/insight`, `/api/advisor/explain`) |

## Data classification

Every metric is tagged:

- **FACT** — returned directly by the Obserra backend (status, effectiveness, maturity,
  evidence expiry, framework coverage, crosswalk mappings, history).
- **MODELLED** — calculated client-side (control health score, priority score, assurance
  index, evidence-state grouping, cross-framework convergence). Never presented as a source fact.
- **AI RECOMMENDATION** — Obserra Advisor explanations, recommended actions and fixes.

## Dashboards

1. **Mission Control** — KPIs, effectiveness by domain, health distribution, framework
   coverage, evidence freshness, top weaknesses, recent activity, remediation progress,
   drift detection, assurance score, quick actions and the executive assurance footer.
2. **Control Effectiveness** — searchable/filterable inventory of every control with status,
   effectiveness, maturity, evidence and modelled priority.
3. **Framework Intelligence** — framework readiness cards, cross-framework convergence and
   the full control crosswalk matrix. Click any framework for a full detail card.
4. **Evidence Assurance** — evidence-expiry queue with one-click Evidence Pack and Control Log PDFs.
5. **Remediation & Drift** — prioritized remediation queue and the framework gap feed.
6. **Defensibility** — live data-source status, evidence classification and connector health context.

## Standard detail card format

Every control card (and every framework card) opens a standard detail view that always contains:

1. **Details** — identity, owner, domain, status, evidence and expiry.
2. **Risk** — modelled risk level, criticality, drift and related risk.
3. **Scoring** — effectiveness, maturity and priority score.
4. **Control alignment** — the frameworks (and references) this item maps to, tying the
   controls and framework dashboards together through the live feed.
5. **Recommendations & fixes** — Obserra Advisor AI explanation with recommended actions.

See `GETTING_STARTED.md` for a walkthrough and `REPORTS.md` for the export/reporting guide.
