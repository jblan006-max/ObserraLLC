# Reports & Assurance — Obserra Control Intelligence

All exports are generated live by the existing Obserra reporting services. No content is mocked.

## 1. Evidence Pack (per control)

- **Where:** Evidence Assurance tab → *Evidence Pack*, or any control detail card.
- **Source:** `POST /api/reports/evidence-pack` `{ "control_id": "<id>" }`
- **Output:** `obserra-evidence-pack-<control_id>.pdf`
- **Contents:** the control's evidence context assembled from live control data.

## 2. Control Log (per control)

- **Where:** Evidence Assurance tab → *Control Log*, or any control detail card.
- **Source:** `GET /api/reports/control-log/{control_id}.pdf`
- **Output:** `obserra-control-log-<control_id>.pdf`
- **Access:** admin.
- **Contents:** the full control history — notes, evidence and remediation entries.

## 3. Executive Assurance Brief (portfolio)

- **Where:** Mission Control header *Executive Brief*, or the footer *Executive Assurance Report*.
- **Source:** `POST /api/studio/report/pdf`
- **Output:** `obserra-control-intelligence-executive-assurance-brief.pdf`
- **Contents (all derived from live feeds):**
  1. Executive Control Intelligence — health score, totals, effectiveness, maturity, expired evidence.
  2. Framework Readiness — coverage, passing counts and gaps per framework.
  3. Highest Priority Control Gaps — modelled priority ranking.
  4. Cross-Framework Convergence — controls mapped across the most frameworks.
  5. Defensibility — a note separating FACT, MODELLED and AI-recommendation data.

## 4. Defensibility statement

Reports explicitly separate:

- **FACT** — control status, effectiveness, maturity, evidence freshness, framework coverage
  and crosswalk mappings returned by the Obserra backend.
- **MODELLED** — control health score, priority scoring and convergence ranking computed client-side.
- **AI RECOMMENDATION** — Obserra Advisor narrative and recommended actions.

This separation is what makes every export audit- and board-defensible.
