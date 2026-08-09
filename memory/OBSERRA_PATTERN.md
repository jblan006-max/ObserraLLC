# Obserra Standard — reusable product pattern (SAVE & REUSE for every app)

Obserra is the company/brand. Every app we build must be **brand-consistent** and match this
functional standard. Keep the same design system, logos, fonts, dark theme, and interaction model.

## The core interaction pattern ("everything is live, cards open, AI recommends how to fix, actions to DO")
1. **Every dashboard** has an auto-running **AI Analyst card at the top** (grounded in that page's LIVE data).
   - Obserra: `components/AIInsight.jsx` → `POST /advisor/insight` (cached 180s).
   - SAP UAC: `components/SapInsight.jsx` → `GET /api/sap/insight` (cached 180s per org+focus).
   - Returns `{ headline, insights:[{text,kind}], actions:[str], model, generated_at }`.
2. **Every list card/row is clickable** → opens a **detail modal/drawer** (never a dead-end static card).
3. **Inside each detail view**, an **AI risk-rating + "how to fix"** block:
   - Obserra: `components/AIFix.jsx` → `POST /advisor/fix {entity, ref}`.
   - SAP UAC: `components/SapAIFix.jsx` → `POST /api/sap/fix {entity, ref}` (cached 180s per entity).
   - Returns `{ rating (Critical|High|Medium|Low), score (0-100), rationale:[str] ("why this rating"),
     recommendation (str, imperative <=220 chars), steps:[str] (2-4 concrete steps), model }`.
   - Rating/score/rationale are computed **server-side, grounded in live data (No-Mock)**;
     recommendation + steps are AI-written with a **deterministic fallback** so it never blanks.
4. **Action buttons that actually DO the thing** live in the detail view (and inline on rows), wired to
   real endpoints and stamped to the audit trail / ServiceNow workflow. Examples in SAP UAC:
   - Identity lifecycle: `POST /api/sap/activation/set` (activate/suspend/resume/deactivate).
   - Account: `POST /api/sap/accounts/{ref}/action`, bulk `POST /api/sap/accounts/bulk-action`.
   - Privileged: `POST /api/sap/privileged/{ref}/action` (revoke_privileged/lock/recertify).
   - Role: `POST /api/sap/roles/{ref}/action`. SoD: `POST /api/sap/sod/conflicts/mitigate`.
   - Autonomous engine controls: `components/AutoActions.jsx` (toggles + run-now buttons).
5. **Confirm dialog** for any state-changing action (reason/work-note + optional notify), then toast with
   the resulting ServiceNow ticket number(s).

## No-Mock rule
All numbers/ratings recompute LIVE from stored records every request (SAP: `_correlate(org_id)`).
Snapshots are realistic seed data with full source provenance; real connectors slot in later without
changing the API contract. Never fabricate values in the UI.

## Performance (must match Obserra snappiness)
- LLM cards stream async and never block page render.
- Cache LLM endpoints (insight 180s per dashboard, fix 180s per entity). Cold ~5s → cached ~0.1s.
- Keep pure-data endpoints < ~150ms.

## SapAIFix `/api/sap/fix` supported entities
`identity` (person ref), `conflict` (conflict_ref), `role` (role ref), `account` (account ref).
Add new entity types by extending `_sap_fix_grounding` + `_sap_fix_fallback` in `backend/sap_uac.py`.

## Reusable pieces to copy into the next app
- Top AI card: `AIInsight`/`SapInsight`.
- Detail AI fix: `AIFix`/`SapAIFix`.
- Action controls: `AutoActions`, per-entity action bars with a shared confirm dialog.
- Shared dash primitives: `components/dash.jsx` (StatCard, CardShell, Spinner), `badges.jsx`.
- Every interactive/critical element carries a unique `data-testid`.
