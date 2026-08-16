M365 Verifier

This verifier runs deterministic checks against Microsoft Entra ID (Microsoft Graph) and writes structured evidence to MongoDB (collection: connector_evidence).

Required Azure AD app permissions (application permissions) for full functionality:
- Directory.Read.All
- Policy.Read.All
- Reports.Read.All
- IdentityRiskEvent.Read.All (for risky users)

Notes:
- Register an Azure AD app, grant the above application permissions and grant admin consent.
- Provide tenant_id, client_id and client_secret in the organization's live M365 connector (Settings → Connectors) or in a connector record.
- The verifier performs safe, read-only queries: token exchange, users count, identityProtection risky users count, and conditional access policies enumeration.

Impact on compliance mapping
- The verifier persists evidence records which are surfaced by the NIST mapping engine. This allows the compliance mapping to be driven by deterministic checks rather than keyword heuristics.

Operational guidance
- Expect throttling for very large tenants; consider running the verifier during low-load windows and caching results.
- If some Graph endpoints are not accessible due to missing permissions, the verifier will record structured failures in evidence.details and mapping will reflect unmet controls until evidence is present.
