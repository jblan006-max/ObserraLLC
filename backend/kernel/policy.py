"""Policy Engine — codified governance policies evaluated against controls."""
from db import db

# Evidence freshness & control-effectiveness thresholds used platform-wide.
EVIDENCE_MAX_AGE_OK_DAYS = 14   # warn window before evidence expiry
EFFECTIVENESS_FLOOR = 55        # below this a control is failing
DRIFT_THRESHOLD = 8             # effectiveness points below baseline = drift

POLICY_SEED = [
    {"policy_id": "POL-EVID-FRESH", "name": "Evidence Freshness", "framework": "SOC 2 · ISO 27001",
     "statement": "Control evidence must be re-attested before its expiry date; stale evidence auto-flags the owner.",
     "severity": "High", "enforced": True},
    {"policy_id": "POL-CTRL-EFFECT", "name": "Minimum Control Effectiveness", "framework": "NIST CSF 2.0",
     "statement": f"Every control must maintain effectiveness at or above {EFFECTIVENESS_FLOOR}% or be remediated.",
     "severity": "High", "enforced": True},
    {"policy_id": "POL-CTRL-DRIFT", "name": "Control Drift Guardrail", "framework": "NIST SP 800-53",
     "statement": f"A control that drifts more than {DRIFT_THRESHOLD} points below its baseline is escalated.",
     "severity": "Medium", "enforced": True},
    {"policy_id": "POL-AI-HIGHRISK", "name": "High-Risk AI Human Oversight", "framework": "EU AI Act · NIST AI RMF",
     "statement": "High or critical-risk AI systems require sanctioned status and human-in-the-loop oversight.",
     "severity": "Critical", "enforced": True},
    {"policy_id": "POL-IDENTITY-PW", "name": "First-Login Password Reset", "framework": "ISO 27001 A.9",
     "statement": "Invited users must set their own password on first login; temporary credentials expire on use.",
     "severity": "Medium", "enforced": True},
]


class PolicyEngine:
    async def ensure_seed(self, org_id):
        if await db.policies.count_documents({"org_id": org_id}) == 0:
            await db.policies.insert_many([{**p, "org_id": org_id} for p in POLICY_SEED])

    async def list(self, org_id):
        await self.ensure_seed(org_id)
        return await db.policies.find({"org_id": org_id}, {"_id": 0}).to_list(100)

    def evaluate_control(self, c):
        """Return list of (policy_id, reason) violations for a control-status dict."""
        v = []
        if c.get("stale"):
            v.append(("POL-EVID-FRESH", f"Evidence expired {abs(c['days_to_expiry'])}d ago"))
        elif c.get("days_to_expiry", 99) < EVIDENCE_MAX_AGE_OK_DAYS:
            v.append(("POL-EVID-FRESH", f"Evidence expires in {c['days_to_expiry']}d"))
        if c.get("effectiveness", 100) < EFFECTIVENESS_FLOOR:
            v.append(("POL-CTRL-EFFECT", f"Effectiveness {c['effectiveness']}% below floor"))
        if c.get("drift"):
            v.append(("POL-CTRL-DRIFT", f"Drifted {abs(c.get('drift_delta', 0))} pts below baseline"))
        return v
