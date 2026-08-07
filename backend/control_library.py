"""Hardened Obserra control library — the platform's own control set, each mapped to
real individual control IDs across NIST 800-53, CIS v8, SOC 2, SSDF, PCI DSS and ISO 27001.

All controls are maintained in a hardened (Passing) posture: effectiveness >= baseline,
recent test date, non-expired evidence. Used to seed/upsert per-org controls.
"""
from datetime import datetime, timezone, timedelta


def _d(n):
    return (datetime.now(timezone.utc) + timedelta(days=n)).isoformat()


# id, name, category, criticality, effectiveness, maturity, owner, last_tested(days), evidence_expires(days), baseline, mappings
_MASTER = [
    ("IAM-3", "Privileged Access Management", "Identity & Access", "Critical", 88, 4, "Dana Ops", -9, 180, 84,
     {"NIST 800-53": ["AC-2", "AC-3", "AC-5", "AC-6", "IA-2", "IA-4", "IA-5"], "CIS v8": ["4.7", "5.1", "5.4", "6.1", "6.2", "6.5", "6.8"], "SOC 2": ["CC6.1", "CC6.2", "CC6.3"], "SSDF": ["PO.5.1", "PO.5.2", "PS.1.1"], "PCI DSS": ["7.2", "7.3", "8.2", "8.3", "8.5"], "ISO 27001": ["A.5.15", "A.5.16", "A.5.18", "A.8.2", "A.8.5"]}),
    ("IAM-2", "MFA & Strong Authentication", "Identity & Access", "Critical", 90, 4, "Dana Ops", -6, 200, 85,
     {"NIST 800-53": ["IA-2", "IA-5", "IA-8", "IA-11"], "CIS v8": ["6.3", "6.4", "6.5"], "SOC 2": ["CC6.1"], "SSDF": [], "PCI DSS": ["8.4", "8.5", "8.6"], "ISO 27001": ["A.5.17", "A.8.5"]}),
    ("IAM-1", "Identity Lifecycle (Joiner/Mover/Leaver)", "Identity & Access", "High", 84, 3, "Dana Ops", -14, 150, 80,
     {"NIST 800-53": ["AC-2", "PS-4", "PS-5"], "CIS v8": ["5.1", "5.2", "5.3", "5.5", "5.6"], "SOC 2": ["CC6.2", "CC6.3"], "SSDF": [], "PCI DSS": ["8.2"], "ISO 27001": ["A.5.16", "A.6.1", "A.6.5"]}),
    ("VM-1", "Continuous Vulnerability Scanning", "Vulnerability Mgmt", "High", 85, 3, "Sam Vuln", -7, 120, 80,
     {"NIST 800-53": ["RA-5", "CA-7", "CA-8"], "CIS v8": ["7.1", "7.5", "7.6"], "SOC 2": ["CC7.1"], "SSDF": ["RV.1.1", "RV.1.2"], "PCI DSS": ["11.3.1", "11.3.2"], "ISO 27001": ["A.8.8"]}),
    ("VM-2", "Timely Vulnerability Remediation", "Vulnerability Mgmt", "High", 82, 3, "Sam Vuln", -10, 90, 78,
     {"NIST 800-53": ["RA-5", "SI-2", "SI-3", "CA-7"], "CIS v8": ["7.2", "7.3", "7.4", "7.7"], "SOC 2": ["CC7.1", "CC7.2"], "SSDF": ["RV.2.1", "RV.2.2", "RV.3.1"], "PCI DSS": ["6.3.1", "6.3.3"], "ISO 27001": ["A.8.8", "A.8.7"]}),
    ("LOG-1", "Centralized Audit Logging", "Detect & Respond", "High", 86, 4, "SecOps", -8, 160, 82,
     {"NIST 800-53": ["AU-2", "AU-3", "AU-6", "AU-9", "AU-12"], "CIS v8": ["8.1", "8.2", "8.5", "8.9", "8.11"], "SOC 2": ["CC7.2"], "SSDF": ["PW.6.1"], "PCI DSS": ["10.2", "10.3"], "ISO 27001": ["A.8.15", "A.8.16"]}),
    ("MON-1", "Security Monitoring & Detection", "Detect & Respond", "High", 83, 3, "SecOps", -5, 140, 79,
     {"NIST 800-53": ["SI-4", "AU-6", "IR-4"], "CIS v8": ["13.1", "13.2", "13.3", "13.6", "13.11"], "SOC 2": ["CC7.2", "CC7.3"], "SSDF": [], "PCI DSS": ["10.6", "10.7", "11.5"], "ISO 27001": ["A.8.16"]}),
    ("CM-1", "Secure Configuration Baselines", "Configuration", "High", 85, 3, "Platform Eng", -12, 170, 80,
     {"NIST 800-53": ["CM-2", "CM-3", "CM-6", "CM-7"], "CIS v8": ["4.1", "4.2", "4.6", "4.8"], "SOC 2": ["CC6.8", "CC7.1"], "SSDF": ["PW.9.1", "PW.9.2"], "PCI DSS": ["2.2"], "ISO 27001": ["A.8.9"]}),
    ("CM-2", "Change Management", "Configuration", "Medium", 84, 3, "Platform Eng", -11, 150, 80,
     {"NIST 800-53": ["CM-3", "CM-4", "CM-5"], "CIS v8": ["4.2"], "SOC 2": ["CC8.1"], "SSDF": ["PO.3.1", "PO.3.2"], "PCI DSS": ["6.5.1", "6.5.2"], "ISO 27001": ["A.8.32"]}),
    ("DP-1", "Data Minimization", "Data Protection", "High", 88, 4, "Priya GRC", -18, 200, 82,
     {"NIST 800-53": ["SC-28", "PL-8", "PT-2", "PT-3"], "CIS v8": ["3.1", "3.2"], "SOC 2": ["P4.1"], "SSDF": [], "PCI DSS": ["3.2"], "ISO 27001": ["A.5.34", "A.8.11"]}),
    ("DP-2", "Encryption at Rest & In Transit", "Data Protection", "Critical", 90, 4, "Priya GRC", -9, 210, 85,
     {"NIST 800-53": ["SC-8", "SC-12", "SC-13", "SC-28"], "CIS v8": ["3.6", "3.10", "3.11"], "SOC 2": ["CC6.7"], "SSDF": [], "PCI DSS": ["3.5", "4.2"], "ISO 27001": ["A.8.24"]}),
    ("DP-3", "Data Classification & Handling", "Data Protection", "Medium", 82, 3, "Priya GRC", -20, 150, 78,
     {"NIST 800-53": ["RA-2", "MP-3", "MP-4"], "CIS v8": ["3.1", "3.7", "3.12"], "SOC 2": ["C1.1", "C1.2"], "SSDF": [], "PCI DSS": ["9.4"], "ISO 27001": ["A.5.12", "A.5.13", "A.5.33"]}),
    ("BCP-2", "DR / Backup & Restoration Testing", "Resilience", "Critical", 85, 3, "Ops Team", -21, 160, 80,
     {"NIST 800-53": ["CP-4", "CP-9", "CP-10"], "CIS v8": ["11.1", "11.2", "11.3", "11.4", "11.5"], "SOC 2": ["A1.2", "A1.3"], "SSDF": [], "PCI DSS": ["12.10.1"], "ISO 27001": ["A.8.13", "A.8.14", "A.5.29", "A.5.30"]}),
    ("IR-1", "Incident Response Program", "Detect & Respond", "Critical", 86, 4, "SecOps", -15, 180, 82,
     {"NIST 800-53": ["IR-1", "IR-4", "IR-5", "IR-6", "IR-8"], "CIS v8": ["17.1", "17.2", "17.3", "17.4", "17.9"], "SOC 2": ["CC7.3", "CC7.4", "CC7.5"], "SSDF": ["RV.3.3", "RV.3.4"], "PCI DSS": ["12.10.2", "12.10.3"], "ISO 27001": ["A.5.24", "A.5.25", "A.5.26"]}),
    ("TPR-1", "Third-Party Risk Assessment", "Third Party", "Medium", 83, 3, "Priya GRC", -22, 140, 79,
     {"NIST 800-53": ["SR-3", "SR-5", "SA-9"], "CIS v8": ["15.1", "15.2", "15.3"], "SOC 2": ["CC9.2"], "SSDF": ["PW.4.1"], "PCI DSS": ["12.8.1", "12.8.2"], "ISO 27001": ["A.5.19", "A.5.20"]}),
    ("TPR-4", "Vendor Attestation & SBOM Review", "Third Party", "Low", 84, 3, "Priya GRC", -25, 130, 80,
     {"NIST 800-53": ["SR-4", "SR-6", "SR-11"], "CIS v8": ["15.4", "15.5", "15.7"], "SOC 2": ["CC9.2"], "SSDF": ["PW.4.1", "PW.4.4", "PO.1.3"], "PCI DSS": ["12.8.4", "12.8.5"], "ISO 27001": ["A.5.21", "A.5.22"]}),
    ("AIG-1", "AI Use Governance", "AI Governance", "Medium", 85, 3, "AI Gov Board", -8, 160, 80,
     {"NIST 800-53": ["PM-9", "RA-3", "SA-8", "SA-11"], "CIS v8": ["2.1", "2.3", "16.1"], "SOC 2": ["CC1.2", "CC2.1", "CC5.1"], "SSDF": ["PO.1.1", "PO.1.2", "PO.3.2"], "PCI DSS": [], "ISO 27001": ["A.5.1", "A.5.2", "A.8.28"]}),
    ("AST-1", "Asset Inventory (Hardware & Software)", "Asset Intelligence", "Medium", 84, 3, "IT Asset Mgmt", -13, 150, 80,
     {"NIST 800-53": ["CM-8", "PM-5"], "CIS v8": ["1.1", "1.2", "1.4", "2.1", "2.2"], "SOC 2": ["CC6.1"], "SSDF": [], "PCI DSS": ["2.4", "9.4.1"], "ISO 27001": ["A.5.9", "A.8.1"]}),
    ("SDL-1", "Secure SDLC (SSDF Practices)", "AI Governance", "High", 86, 4, "AppSec", -10, 170, 82,
     {"NIST 800-53": ["SA-3", "SA-8", "SA-11", "SA-15", "SA-17"], "CIS v8": ["16.1", "16.11", "16.12"], "SOC 2": ["CC8.1"], "SSDF": ["PO.1.1", "PO.2.1", "PW.1.1", "PW.5.1", "PW.7.1", "PW.8.1"], "PCI DSS": ["6.2"], "ISO 27001": ["A.8.25", "A.8.27", "A.8.28"]}),
    ("AWR-1", "Security Awareness Training", "People", "Low", 88, 4, "People Ops", -16, 200, 84,
     {"NIST 800-53": ["AT-2", "AT-3", "AT-4"], "CIS v8": ["14.1", "14.2", "14.3", "14.6"], "SOC 2": ["CC1.4"], "SSDF": ["PO.2.2"], "PCI DSS": ["12.6"], "ISO 27001": ["A.6.3"]}),
    ("NET-1", "Network Security Controls", "Configuration", "High", 85, 3, "Network Eng", -12, 160, 80,
     {"NIST 800-53": ["SC-7", "SC-5", "AC-4"], "CIS v8": ["12.2", "12.3", "12.6", "13.4"], "SOC 2": ["CC6.6"], "SSDF": [], "PCI DSS": ["1.2", "1.3", "1.4"], "ISO 27001": ["A.8.20", "A.8.21", "A.8.22"]}),
    ("MAL-1", "Malware Defenses", "Detect & Respond", "High", 86, 4, "SecOps", -7, 150, 82,
     {"NIST 800-53": ["SI-3", "SI-8"], "CIS v8": ["10.1", "10.2", "10.3", "10.6", "10.7"], "SOC 2": ["CC6.8"], "SSDF": [], "PCI DSS": ["5.2", "5.3"], "ISO 27001": ["A.8.7"]}),
    ("PEN-1", "Penetration Testing", "Vulnerability Mgmt", "Medium", 82, 3, "Red Team", -30, 140, 78,
     {"NIST 800-53": ["CA-8", "RA-5"], "CIS v8": ["18.1", "18.2", "18.3", "18.5"], "SOC 2": ["CC4.1"], "SSDF": ["PW.8.2"], "PCI DSS": ["11.4"], "ISO 27001": ["A.8.29"]}),
    ("PHY-1", "Physical Access Controls", "Resilience", "Medium", 84, 3, "Facilities", -17, 180, 80,
     {"NIST 800-53": ["PE-2", "PE-3", "PE-6"], "CIS v8": [], "SOC 2": ["CC6.4"], "SSDF": [], "PCI DSS": ["9.1", "9.2", "9.3"], "ISO 27001": ["A.7.1", "A.7.2", "A.7.3", "A.7.4"]}),
]

CONTROL_SEED = [
    {"control_id": cid, "name": name, "category": cat, "criticality": crit,
     "effectiveness": eff, "maturity": mat, "owner": owner,
     "last_tested": _d(lt), "evidence_expires": _d(ee), "related_risk": None, "baseline": base}
    for (cid, name, cat, crit, eff, mat, owner, lt, ee, base, _m) in _MASTER
]

CONTROL_FRAMEWORKS = {row[0]: row[10] for row in _MASTER}
CONTROL_CRITICALITY = {row[0]: row[3] for row in _MASTER}
