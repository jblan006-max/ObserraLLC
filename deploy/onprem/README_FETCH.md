This directory contains helper scripts to fetch canonical NIST SP 800-53 Rev.5 and EU CRA requirement files.

Scripts:
 - fetch_nist.ps1         : PowerShell script to try common raw GitHub mirrors and save to sp800_53_rev5.json
 - fetch_github_nist.ps1  : PowerShell script to query GitHub tree for JSON files (best-effort)

If the PS scripts cannot find canonical sources (404), use the backend admin endpoint POST /api/nist/auto-import which will attempt additional mirrors, save files to deploy/onprem/, and import them into MongoDB collections (nist_controls and eu_cra_requirements). The endpoint requires an admin JWT.

If you have the canonical JSON files, place them at:
 - deploy/onprem/sp800_53_rev5.json
 - deploy/onprem/eu_cra_requirements.json

Then call POST /api/nist/import-local (admin) to import them into the database.
