"""Full control catalogs per framework (every individual control/safeguard/requirement).

IDs are the real published identifiers; group is the real family/domain/requirement
title. Used by the compliance crosswalk to show, for every control in a framework,
whether Obserra's controls align to it (aligned / gap / not assessed).
"""

# NIST SP 800-53 Rev.5 base-control families: (family code, family name, base-control count)
_NIST_FAM = [
    ("AC", "Access Control", 25), ("AT", "Awareness and Training", 6),
    ("AU", "Audit and Accountability", 16), ("CA", "Assessment, Authorization, and Monitoring", 9),
    ("CM", "Configuration Management", 14), ("CP", "Contingency Planning", 13),
    ("IA", "Identification and Authentication", 12), ("IR", "Incident Response", 10),
    ("MA", "Maintenance", 7), ("MP", "Media Protection", 8),
    ("PE", "Physical and Environmental Protection", 23), ("PL", "Planning", 11),
    ("PM", "Program Management", 32), ("PS", "Personnel Security", 9),
    ("PT", "PII Processing and Transparency", 8), ("RA", "Risk Assessment", 10),
    ("SA", "System and Services Acquisition", 23), ("SC", "System and Communications Protection", 51),
    ("SI", "System and Information Integrity", 23), ("SR", "Supply Chain Risk Management", 12),
]

# CIS Critical Security Controls v8: (control number, name, safeguard count) — 153 safeguards total
_CIS = [
    ("1", "Inventory and Control of Enterprise Assets", 5), ("2", "Inventory and Control of Software Assets", 7),
    ("3", "Data Protection", 14), ("4", "Secure Configuration of Enterprise Assets and Software", 12),
    ("5", "Account Management", 6), ("6", "Access Control Management", 8),
    ("7", "Continuous Vulnerability Management", 7), ("8", "Audit Log Management", 12),
    ("9", "Email and Web Browser Protections", 7), ("10", "Malware Defenses", 7),
    ("11", "Data Recovery", 5), ("12", "Network Infrastructure Management", 8),
    ("13", "Network Monitoring and Defense", 11), ("14", "Security Awareness and Skills Training", 9),
    ("15", "Service Provider Management", 7), ("16", "Application Software Security", 14),
    ("17", "Incident Response Management", 9), ("18", "Penetration Testing", 5),
]

# ISO/IEC 27001:2022 Annex A themes: (clause, theme name, control count) — 93 controls total
_ISO = [("5", "Organizational controls", 37), ("6", "People controls", 8),
        ("7", "Physical controls", 14), ("8", "Technological controls", 34)]

# SOC 2 Trust Services Criteria — Common Criteria counts
_SOC2_CC = {"CC1": 5, "CC2": 3, "CC3": 4, "CC4": 2, "CC5": 3, "CC6": 8, "CC7": 5, "CC8": 1, "CC9": 2}
_SOC2_PRIV = ["P1.1", "P2.1", "P3.1", "P3.2", "P4.1", "P4.2", "P4.3", "P5.1", "P5.2",
              "P6.1", "P6.2", "P6.3", "P6.4", "P6.5", "P6.6", "P6.7", "P7.1", "P8.1"]

# NIST SSDF (SP 800-218) tasks — 42 tasks across 4 practice groups
_SSDF = {
    "Prepare the Organization (PO)": ["PO.1.1", "PO.1.2", "PO.1.3", "PO.2.1", "PO.2.2", "PO.2.3",
                                       "PO.3.1", "PO.3.2", "PO.3.3", "PO.4.1", "PO.4.2", "PO.5.1", "PO.5.2"],
    "Protect the Software (PS)": ["PS.1.1", "PS.2.1", "PS.3.1", "PS.3.2"],
    "Produce Well-Secured Software (PW)": ["PW.1.1", "PW.1.2", "PW.1.3", "PW.2.1", "PW.4.1", "PW.4.2",
                                           "PW.4.4", "PW.5.1", "PW.6.1", "PW.6.2", "PW.7.1", "PW.7.2",
                                           "PW.8.1", "PW.8.2", "PW.9.1", "PW.9.2"],
    "Respond to Vulnerabilities (RV)": ["RV.1.1", "RV.1.2", "RV.1.3", "RV.2.1", "RV.2.2",
                                        "RV.3.1", "RV.3.2", "RV.3.3", "RV.3.4"],
}

# PCI DSS v4.0 — 12 requirements: (requirement number, title, granular sub-requirement count)
_PCI = [
    ("1", "Install and Maintain Network Security Controls", 25),
    ("2", "Apply Secure Configurations to All System Components", 12),
    ("3", "Protect Stored Account Data", 40),
    ("4", "Protect Cardholder Data with Strong Cryptography During Transmission", 7),
    ("5", "Protect All Systems and Networks from Malicious Software", 14),
    ("6", "Develop and Maintain Secure Systems and Software", 30),
    ("7", "Restrict Access to System Components and Cardholder Data by Business Need to Know", 12),
    ("8", "Identify Users and Authenticate Access to System Components", 28),
    ("9", "Restrict Physical Access to Cardholder Data", 22),
    ("10", "Log and Monitor All Access to System Components and Cardholder Data", 30),
    ("11", "Test Security of Systems and Networks Regularly", 20),
    ("12", "Support Information Security with Organizational Policies and Programs", 37),
]


def _nist():
    return [{"id": f"{code}-{i}", "group": name}
            for code, name, n in _NIST_FAM for i in range(1, n + 1)]


def _cis():
    return [{"id": f"{c}.{i}", "group": f"CIS {c} — {name}"}
            for c, name, n in _CIS for i in range(1, n + 1)]


def _iso():
    return [{"id": f"A.{c}.{i}", "group": name}
            for c, name, n in _ISO for i in range(1, n + 1)]


def _soc2():
    out = []
    for k, n in _SOC2_CC.items():
        out += [{"id": f"{k}.{i}", "group": "Common Criteria"} for i in range(1, n + 1)]
    out += [{"id": f"A1.{i}", "group": "Availability"} for i in range(1, 4)]
    out += [{"id": f"C1.{i}", "group": "Confidentiality"} for i in range(1, 3)]
    out += [{"id": f"PI1.{i}", "group": "Processing Integrity"} for i in range(1, 6)]
    out += [{"id": p, "group": "Privacy"} for p in _SOC2_PRIV]
    return out


def _ssdf():
    return [{"id": t, "group": g} for g, ts in _SSDF.items() for t in ts]


def _pci():
    return [{"id": f"{r}.{i}", "group": f"Req {r} — {title}"}
            for r, title, n in _PCI for i in range(1, n + 1)]


CATALOGS = {
    "NIST 800-53": _nist(),
    "CIS v8": _cis(),
    "SOC 2": _soc2(),
    "SSDF": _ssdf(),
    "PCI DSS": _pci(),
    "ISO 27001": _iso(),
}

CATALOG_COUNTS = {k: len(v) for k, v in CATALOGS.items()}
