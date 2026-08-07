"""Policy Engine — codified governance policies evaluated against controls."""
from datetime import datetime, timezone

from db import db

DEFAULT_THRESHOLDS = {"evidence_days": 14, "effectiveness_floor": 55, "drift_pts": 8}

POLICY_SEED = [
    {"policy_id": "POL-EVID-FRESH", "name": "Evidence Freshness", "framework": "SOC 2 · ISO 27001",
     "statement": "Control evidence must be re-attested before its expiry date; stale evidence auto-flags the owner.",
     "severity": "High", "enforced": True, "threshold": 14},
    {"policy_id": "POL-CTRL-EFFECT", "name": "Minimum Control Effectiveness", "framework": "NIST CSF 2.0",
     "statement": "Every control must maintain effectiveness at or above the floor or be remediated.",
     "severity": "High", "enforced": True, "threshold": 55},
    {"policy_id": "POL-CTRL-DRIFT", "name": "Control Drift Guardrail", "framework": "NIST SP 800-53",
     "statement": "A control that drifts more than the threshold below its baseline is escalated.",
     "severity": "Medium", "enforced": True, "threshold": 8},
    {"policy_id": "POL-AI-HIGHRISK", "name": "High-Risk AI Human Oversight", "framework": "EU AI Act · NIST AI RMF",
     "statement": "High or critical-risk AI systems require sanctioned status and human-in-the-loop oversight.",
     "severity": "Critical", "enforced": True, "threshold": None},
    {"policy_id": "POL-IDENTITY-PW", "name": "First-Login Password Reset", "framework": "ISO 27001 A.9",
     "statement": "Invited users must set their own password on first login; temporary credentials expire on use.",
     "severity": "Medium", "enforced": True, "threshold": None},
]

SEVERITIES = {"Low", "Medium", "High", "Critical"}


class PolicyEngine:
    async def ensure_seed(self, org_id):
        if await db.policies.count_documents({"org_id": org_id}) == 0:
            await db.policies.insert_many([{**p, "org_id": org_id} for p in POLICY_SEED])

    async def list(self, org_id):
        await self.ensure_seed(org_id)
        return await db.policies.find({"org_id": org_id}, {"_id": 0}).to_list(100)

    async def thresholds(self, org_id):
        t = dict(DEFAULT_THRESHOLDS)
        for p in await self.list(org_id):
            if p.get("threshold") is None or not p.get("enforced"):
                continue
            if p["policy_id"] == "POL-EVID-FRESH":
                t["evidence_days"] = p["threshold"]
            elif p["policy_id"] == "POL-CTRL-EFFECT":
                t["effectiveness_floor"] = p["threshold"]
            elif p["policy_id"] == "POL-CTRL-DRIFT":
                t["drift_pts"] = p["threshold"]
        return t

    def evaluate_control(self, c, thresholds=None):
        t = thresholds or DEFAULT_THRESHOLDS
        v = []
        if c.get("stale"):
            v.append(("POL-EVID-FRESH", f"Evidence expired {abs(c['days_to_expiry'])}d ago"))
        elif c.get("days_to_expiry", 99) < t["evidence_days"]:
            v.append(("POL-EVID-FRESH", f"Evidence expires in {c['days_to_expiry']}d"))
        if c.get("effectiveness", 100) < t["effectiveness_floor"]:
            v.append(("POL-CTRL-EFFECT", f"Effectiveness {c['effectiveness']}% below {t['effectiveness_floor']}% floor"))
        if c.get("drift_delta", 0) <= -t["drift_pts"]:
            v.append(("POL-CTRL-DRIFT", f"Drifted {abs(c.get('drift_delta', 0))} pts below baseline"))
        return v

    async def create(self, org_id, data):
        n = await db.policies.count_documents({"org_id": org_id}) + 1
        policy_id = f"POL-CUSTOM-{n:03d}"
        doc = {"org_id": org_id, "policy_id": policy_id, "name": data["name"],
               "statement": data["statement"], "framework": data.get("framework", "Custom"),
               "severity": data.get("severity", "Medium"), "enforced": data.get("enforced", True),
               "threshold": data.get("threshold"), "created_at": datetime.now(timezone.utc).isoformat()}
        await db.policies.insert_one(doc)
        doc.pop("_id", None)
        return doc

    async def update(self, org_id, policy_id, changes):
        clean = {k: v for k, v in changes.items() if v is not None}
        if not clean:
            return None
        await db.policies.update_one({"org_id": org_id, "policy_id": policy_id}, {"$set": clean})
        return await db.policies.find_one({"org_id": org_id, "policy_id": policy_id}, {"_id": 0})
