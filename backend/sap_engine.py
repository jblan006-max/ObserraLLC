"""SAP UAC — live No-Mock compute engine.

Seeds the discovered enterprise access snapshot and recomputes SoD detection, the SAP
Access Risk Score, account flags, ADP<->IZ8 HR reconciliation and correlation from the
stored records on every request."""
import random
import hashlib
from datetime import datetime, timezone, timedelta

from db import db
from sap_data import (FUNCTIONS, SOD_RULES, SEV_WEIGHT, ROLE_CATALOG, ROLE_BY_REF,
                      SYSTEMS, LEGAL_ENTITIES, LE_BY_CODE, SECURITY_HOLD_FIELDS,
                      _FIRST, _LAST, _JOBS, _sap_uid)

def _now():
    return datetime.now(timezone.utc)


def _iso(days=0, hours=0):
    return (_now() - timedelta(days=days, hours=hours)).isoformat()


async def seed_sap_uac(org_id: str):
    """Idempotently ingest the discovered enterprise access snapshot for an org."""
    if await db.sap_persons.find_one({"org_id": org_id}):
        return
    rnd = random.Random(int(hashlib.sha256(org_id.encode()).hexdigest(), 16) % (2**31))

    # Connectors (source contracts) — snapshot-imported now; live API adds credentials later.
    connectors = [
        {"id": "CON-SAP-S4", "name": "SAP S/4HANA", "category": "SAP", "mode": "Read-Only", "status": "connected", "auth_ready": False, "records": 0, "freshness": "fresh"},
        {"id": "CON-SAP-ECC", "name": "SAP ECC", "category": "SAP", "mode": "Read-Only", "status": "connected", "auth_ready": False, "records": 0, "freshness": "fresh"},
        {"id": "CON-ADP", "name": "ADP Workforce Now", "category": "HR (Authoritative)", "mode": "Read-Only", "status": "connected", "auth_ready": False, "records": 0, "freshness": "fresh"},
        {"id": "CON-IZ8", "name": "IZ8 HR (International)", "category": "HR (Authoritative)", "mode": "Read-Only", "status": "connected", "auth_ready": False, "records": 0, "freshness": "fresh"},
        {"id": "CON-AD", "name": "Microsoft Active Directory", "category": "Directory", "mode": "Read-Only", "status": "connected", "auth_ready": False, "records": 0, "freshness": "fresh"},
        {"id": "CON-ENTRA", "name": "Microsoft Entra ID", "category": "Directory", "mode": "Read-Only", "status": "connected", "auth_ready": False, "records": 0, "freshness": "stale"},
        {"id": "CON-SNOW", "name": "ServiceNow ITSM", "category": "ITSM", "mode": "Bidirectional", "status": "credentials_required", "auth_ready": False, "records": 0, "freshness": "n/a"},
    ]

    persons, accounts = [], []
    used_names = set()

    def _mkname():
        for _ in range(200):
            n = f"{rnd.choice(_FIRST)} {rnd.choice(_LAST)}"
            if n not in used_names:
                used_names.add(n)
                return n
        return f"User {len(used_names)}"

    # ---- Scenario-driven persons (the "interesting" governance cases) ----
    scen = [
        # (dept, status, worker_type, roles, flags)
        {"dept": "Finance", "status": "Active", "wt": "Employee", "roles": ["Z_FI_VENDOR_MAINT", "Z_FI_AP_PAYMENTS"], "le": "US01"},   # SOD-F01 critical
        {"dept": "Finance", "status": "Active", "wt": "Employee", "roles": ["Z_FI_AP_CLERK", "Z_FI_AP_PAYMENTS"], "le": "US01"},        # SOD-F02 critical
        {"dept": "Treasury", "status": "Active", "wt": "Employee", "roles": ["Z_TR_BANK_MGR", "Z_FI_AP_PAYMENTS"], "le": "DE01"},        # SOD-T01 critical
        {"dept": "Procurement", "status": "Active", "wt": "Contractor", "roles": ["Z_MM_VENDOR_BUYER", "Z_MM_PO_APPROVER"], "le": "UK01"},  # SOD-P01/P02
        {"dept": "HR", "status": "Active", "wt": "Employee", "roles": ["Z_HR_MASTER", "Z_HR_PAYROLL"], "le": "US01"},                   # SOD-H01 critical
        {"dept": "IT Basis", "status": "Active", "wt": "Employee", "roles": ["Z_BASIS_SUPER"], "le": "IN01", "priv": True},             # SOD-B01/B02/B03
        {"dept": "IT Basis", "status": "Active", "wt": "Employee", "roles": ["SAP_ALL"], "le": "US01", "priv": True},                   # SAP_ALL holder
        {"dept": "Finance", "status": "Terminated", "wt": "Employee", "roles": ["Z_FI_AP_CLERK", "Z_FI_AP_PAYMENTS"], "le": "US01", "residual": True},  # leaver w/ residual access
        {"dept": "Sales", "status": "Terminated", "wt": "Contractor", "roles": ["Z_SD_BILLING"], "le": "UK01", "residual": True},
        {"dept": "Sales", "status": "Active", "wt": "Employee", "roles": ["Z_SD_CUST_MAINT", "Z_SD_BILLING"], "le": "DE01"},            # SOD-O01
        {"dept": "Finance", "status": "Leave", "wt": "Employee", "roles": ["Z_FI_GL_ACCOUNTANT"], "le": "US01"},
        {"dept": "Procurement", "status": "Active", "wt": "Employee", "roles": ["Z_MM_BUYER"], "le": "IN01", "dormant": True},          # dormant privileged? no — dormant normal
        {"dept": "IT Basis", "status": "Active", "wt": "Employee", "roles": ["Z_BC_USER_ADMIN", "Z_BC_TABLE_MAINT"], "le": "DE01", "priv": True, "dormant": True},  # dormant privileged (SOD-B03)
        {"dept": "Finance", "status": "Active", "wt": "Employee", "roles": ["Z_FI_SENIOR_ACCT", "Z_FI_AP_PAYMENTS"], "le": "US01"},      # derived role → SOD-F02
    ]
    idx = 0
    for s in scen:
        idx += 1
        name = _mkname()
        le = LE_BY_CODE[s["le"]]
        hire_days = rnd.randint(400, 2400)
        p = _build_person(org_id, idx, name, s["dept"], s["status"], s["wt"], le, rnd, hire_days,
                          residual=s.get("residual"), priv=s.get("priv"))
        persons.append(p)
        sysrefs = ["S4P"] if s["dept"] in ("Finance", "Treasury", "Sales", "Procurement", "Master Data") else ["ECP", "S4P"]
        for sysref in sysrefs:
            accounts.append(_build_account(org_id, p, sysref, s["roles"], rnd,
                                            dormant=s.get("dormant"),
                                            locked=(s["status"] == "Terminated" and not s.get("residual"))))

    # ---- Filler population (varied depts, mostly clean) ----
    for _ in range(30):
        idx += 1
        dept = rnd.choice(list(_JOBS.keys()))
        status = rnd.choices(["Active", "Active", "Active", "Active", "Leave", "Terminated"], k=1)[0]
        wt = rnd.choices(["Employee", "Employee", "Employee", "Contractor"], k=1)[0]
        le = rnd.choice(LEGAL_ENTITIES)
        recent_joiner = rnd.random() < 0.12
        hire_days = rnd.randint(2, 18) if recent_joiner else rnd.randint(200, 3000)
        name = _mkname()
        p = _build_person(org_id, idx, name, dept, status, wt, le, rnd, hire_days)
        persons.append(p)
        # assign 1-2 non-conflicting roles by dept
        dept_roles = [r["ref"] for r in ROLE_CATALOG if r.get("dept") == dept and not r.get("sap_all")]
        roles = rnd.sample(dept_roles, k=min(len(dept_roles), rnd.randint(1, 2))) if dept_roles else ["Z_FI_DISPLAY"]
        sysref = "S4P" if dept in ("Finance", "Treasury", "Sales", "Procurement", "Master Data") else "ECP"
        accounts.append(_build_account(org_id, p, sysref, roles, rnd,
                                        dormant=(rnd.random() < 0.15),
                                        locked=(status == "Terminated")))

    # ---- Orphan / technical / service accounts (no person owner) ----
    tech = [
        {"user": "RFC_MDM", "type": "communication", "roles": ["Z_FI_VENDOR_MAINT", "Z_SD_CUST_MAINT"], "owner": None, "sys": "S4P"},
        {"user": "BATCH_FI", "type": "system", "roles": ["Z_FI_AP_PAYMENT" if False else "Z_FI_AP_PAYMENTS", "Z_FI_AP_CLERK"], "owner": None, "sys": "S4P"},
        {"user": "DDIC", "type": "system", "roles": ["SAP_ALL"], "owner": "SAP Basis", "sys": "ECP"},
        {"user": "FIREFIGHT1", "type": "emergency", "roles": ["Z_BASIS_SUPER"], "owner": "SAP Security", "sys": "S4P"},
    ]
    for t in tech:
        accounts.append({
            "org_id": org_id, "ref": f"A-TECH-{t['user']}", "person_ref": None, "sap_user": t["user"],
            "system": t["sys"], "client": next(s["client"] for s in SYSTEMS if s["ref"] == t["sys"]),
            "user_type": t["type"], "lock_state": "unlocked", "valid_from": _iso(days=900),
            "valid_to": None, "last_login": _iso(days=rnd.randint(1, 40)), "roles": t["roles"],
            "owner": t["owner"], "technical": True, "source": t["sys"], "discovered_at": _iso(hours=6),
        })

    # provenance record counts
    for c in connectors:
        if c["id"] in ("CON-SAP-S4", "CON-SAP-ECC"):
            c["records"] = len([a for a in accounts if (a["system"] in ("S4P", "BWP") if c["id"] == "CON-SAP-S4" else a["system"] in ("ECP", "ECQ"))])
        elif c["id"] == "CON-ADP":
            c["records"] = len([p for p in persons if p["hr_authority"] == "ADP"])
        elif c["id"] == "CON-IZ8":
            c["records"] = len([p for p in persons if p["hr_authority"] == "IZ8"])
        elif c["id"] in ("CON-AD", "CON-ENTRA"):
            c["records"] = len(persons)
        c["last_sync"] = _iso(hours=rnd.randint(1, 5))
        c["org_id"] = org_id

    await db.sap_persons.insert_many(persons)
    await db.sap_accounts.insert_many(accounts)
    await db.sap_systems.insert_many([{**s, "org_id": org_id} for s in SYSTEMS])
    await db.sap_roles.insert_many([{**r, "org_id": org_id, "system": "S4P"} for r in ROLE_CATALOG])
    await db.sap_connectors.insert_many(connectors)
    await db.sap_meta.insert_one({"org_id": org_id, "seeded_at": _now().isoformat()})


def _build_person(org_id, idx, name, dept, status, wt, le, rnd, hire_days, residual=False, priv=False):
    ref = f"P-{idx:04d}"
    first, last = (name.split(" ") + [""])[:2]
    email = f"{first.lower()}.{last.lower()}@acme-corp.com"
    hire_date = _iso(days=hire_days)
    term_date = _iso(days=rnd.randint(1, 40)) if status == "Terminated" else None
    job = rnd.choice(_JOBS.get(dept, ["Analyst"]))
    manager = f"{rnd.choice(_FIRST)} {rnd.choice(_LAST)}"
    mfa = rnd.random() > (0.35 if priv else 0.12)
    risky_signin = rnd.random() < 0.1
    # HR sources — ADP + IZ8 both carry a record; inject conflicts on a subset.
    adp = {"employment_status": status, "termination_date": term_date, "manager": manager,
           "legal_entity": le["code"], "worker_type": wt, "job_title": job,
           "source_id": f"ADP-{rnd.randint(100000, 999999)}", "observed": _iso(hours=rnd.randint(2, 20))}
    iz8 = {"employment_status": status, "termination_date": term_date, "manager": manager,
           "legal_entity": le["code"], "worker_type": wt, "job_title": job,
           "source_id": f"IZ8-{rnd.randint(100000, 999999)}", "observed": _iso(hours=rnd.randint(2, 30))}
    conflict_kind = None
    # Deliberate ADP↔IZ8 disagreements on ~18% of population (weighted toward security-critical fields)
    r = rnd.random()
    if r < 0.06 and status == "Terminated":
        iz8["employment_status"] = "Active"          # IZ8 still shows active → SECURITY HOLD
        iz8["termination_date"] = None
        conflict_kind = "employment_status"
    elif r < 0.10:
        iz8["termination_date"] = _iso(days=rnd.randint(1, 20))  # differing term date
        conflict_kind = "termination_date"
    elif r < 0.14:
        iz8["manager"] = f"{rnd.choice(_FIRST)} {rnd.choice(_LAST)}"
        conflict_kind = "manager"
    elif r < 0.18:
        iz8["worker_type"] = "Contractor" if wt == "Employee" else "Employee"
        conflict_kind = "worker_type"
    return {
        "org_id": org_id, "ref": ref, "name": name, "email": email, "department": dept,
        "job_title": job, "worker_type": wt, "status": status, "legal_entity": le["code"],
        "legal_entity_name": le["name"], "country": le["country"], "region": le["region"],
        "manager": manager, "hire_date": hire_date, "termination_date": term_date,
        "hr_authority": le["hr"], "sources": ["ADP" if le["hr"] == "ADP" else "IZ8", "AD", "Entra", "SAP"],
        "hr": {"adp": adp, "iz8": iz8}, "_conflict_seed": conflict_kind,
        "ad_enabled": (status != "Terminated") or residual, "mfa": mfa, "risky_signin": risky_signin,
        "match_confidence": round(rnd.uniform(0.86, 0.99), 2), "discovered_at": _iso(hours=4),
    }


def _build_account(org_id, person, sysref, roles, rnd, dormant=False, locked=False):
    sysrec = next(s for s in SYSTEMS if s["ref"] == sysref)
    last_login = _iso(days=rnd.randint(120, 400)) if dormant else _iso(days=rnd.randint(0, 25))
    if person["status"] == "Terminated":
        last_login = _iso(days=rnd.randint(20, 90))
    return {
        "org_id": org_id, "ref": f"A-{person['ref']}-{sysref}", "person_ref": person["ref"],
        "sap_user": _sap_uid(person["name"], sysref), "system": sysref, "client": sysrec["client"],
        "user_type": "dialog", "lock_state": "locked" if locked else "unlocked",
        "valid_from": person["hire_date"], "valid_to": None,
        "last_login": last_login, "roles": roles, "technical": False,
        "source": sysref, "discovered_at": _iso(hours=4),
    }


# ═════════════════════════════════════════════════════════════════════════════
# LIVE ENGINE — computes everything from the stored records on every request
# ═════════════════════════════════════════════════════════════════════════════
async def _load(org_id):
    persons = await db.sap_persons.find({"org_id": org_id}, {"_id": 0}).to_list(2000)
    accounts = await db.sap_accounts.find({"org_id": org_id}, {"_id": 0}).to_list(5000)
    return persons, accounts


def _account_functions(account):
    fns = set()
    for rref in account.get("roles", []):
        role = ROLE_BY_REF.get(rref)
        if role:
            fns.update(role.get("functions", []))
    return fns


def _functions_provenance(account):
    """Which role grants which function — for the SoD 'access path'."""
    prov = {}
    for rref in account.get("roles", []):
        role = ROLE_BY_REF.get(rref)
        if role:
            for f in role.get("functions", []):
                prov.setdefault(f, []).append(rref)
    return prov


def _account_conflicts(account):
    """Live SoD detection for a single account against the full rule library."""
    fns = _account_functions(account)
    prov = _functions_provenance(account)
    out = []
    for rule in SOD_RULES:
        if rule["a"] in fns and rule["b"] in fns:
            out.append({
                "conflict_ref": f"{rule['ref']}:{account['ref']}",
                "rule_ref": rule["ref"], "rule_name": rule["name"], "area": rule["area"],
                "severity": rule["severity"], "business_risk": rule["risk"],
                "account_ref": account["ref"], "system": account["system"], "sap_user": account["sap_user"],
                "person_ref": account.get("person_ref"),
                "function_a": FUNCTIONS[rule["a"]]["label"], "function_b": FUNCTIONS[rule["b"]]["label"],
                "a_via_roles": prov.get(rule["a"], []), "b_via_roles": prov.get(rule["b"], []),
            })
    return out


async def _all_conflicts(org_id, accounts=None):
    if accounts is None:
        _, accounts = await _load(org_id)
    conflicts = []
    for a in accounts:
        conflicts.extend(_account_conflicts(a))
    # merge stored mitigations
    mits = {m["conflict_ref"]: m for m in await db.sap_mitigations.find({"org_id": org_id}, {"_id": 0}).to_list(5000)}
    for c in conflicts:
        m = mits.get(c["conflict_ref"])
        if m:
            c["status"] = m.get("status", "Mitigated")
            c["mitigating_control"] = m.get("control")
            c["mitigated_by"] = m.get("by")
            c["residual"] = m.get("residual", "Reduced")
        else:
            c["status"] = "Open"
            c["mitigating_control"] = None
            c["residual"] = c["severity"]
    return conflicts


def _account_flags(account, person):
    """Privileged / dormant / orphan classification — computed live."""
    fns = _account_functions(account)
    roles = account.get("roles", [])
    sap_all = any(ROLE_BY_REF.get(r, {}).get("sap_all") for r in roles)
    privileged = sap_all or any(ROLE_BY_REF.get(r, {}).get("privileged") for r in roles) or \
        bool({"F_USER_ADMIN", "F_ROLE_ADMIN", "F_TRANSPORT", "F_TABLE_MAINT"} & fns)
    # dormant: > 90 days since last login (and not locked)
    dormant = False
    try:
        dormant = (_now() - datetime.fromisoformat(account["last_login"])).days > 90 and account.get("lock_state") != "locked"
    except Exception:
        dormant = False
    orphan = (account.get("person_ref") is None and not account.get("owner")) or \
             (person is not None and person.get("status") == "Terminated" and account.get("lock_state") != "locked") or \
             (account.get("technical") and account.get("owner") is None)
    return {"privileged": privileged, "sap_all": sap_all, "dormant": dormant, "orphan": orphan}


def _person_risk(person, person_accounts, conflicts_by_person):
    """Obserra SAP Access Risk Score (0-100) with explainable factors — deterministic, live."""
    factors = []
    score = 0
    pconf = conflicts_by_person.get(person["ref"], [])
    open_conf = [c for c in pconf if c.get("status") == "Open"]
    if open_conf:
        sod_pts = min(45, sum(SEV_WEIGHT.get(c["severity"], 5) for c in open_conf))
        score += sod_pts
        crit = sum(1 for c in open_conf if c["severity"] == "Critical")
        factors.append({"factor": "Segregation of Duties", "points": sod_pts,
                        "detail": f"{len(open_conf)} open SoD conflict(s), {crit} critical"})
    flags = [_account_flags(a, person) for a in person_accounts]
    if any(f["sap_all"] for f in flags):
        score += 30
        factors.append({"factor": "Privilege severity", "points": 30, "detail": "Holds SAP_ALL / full authorization profile"})
    elif any(f["privileged"] for f in flags):
        score += 15
        factors.append({"factor": "Privilege severity", "points": 15, "detail": "Holds privileged (Basis / security-admin) access"})
    unlocked = any(a.get("lock_state") == "unlocked" for a in person_accounts)
    if person["status"] == "Terminated" and unlocked:
        score += 40
        factors.append({"factor": "Employment state", "points": 40, "detail": "Terminated worker retains active (unlocked) SAP access — residual access"})
    elif person["status"] == "Leave" and unlocked:
        score += 12
        factors.append({"factor": "Employment state", "points": 12, "detail": "Worker on leave of absence retains active access"})
    if any(f["dormant"] and f["privileged"] for f in flags):
        score += 15
        factors.append({"factor": "Dormancy", "points": 15, "detail": "Privileged access dormant >90 days"})
    elif any(f["dormant"] for f in flags):
        score += 8
        factors.append({"factor": "Dormancy", "points": 8, "detail": "Access unused >90 days"})
    if any(f["orphan"] for f in flags):
        score += 12
        factors.append({"factor": "Orphan / ownerless", "points": 12, "detail": "Account has no active owner / sponsor"})
    if not person.get("mfa"):
        score += 10
        factors.append({"factor": "Identity assurance", "points": 10, "detail": "MFA not enforced on the linked identity"})
    if person.get("risky_signin"):
        score += 8
        factors.append({"factor": "Identity threat", "points": 8, "detail": "Risky sign-in detected (Entra ID)"})
    if person.get("_hr_hold"):
        score += 10
        factors.append({"factor": "HR data conflict", "points": 10, "detail": "ADP↔IZ8 security-hold conflict on a material field"})
    score = min(100, score)
    rating = "Critical" if score >= 70 else "High" if score >= 45 else "Medium" if score >= 25 else "Low"
    return {"score": score, "rating": rating, "factors": factors}


def _hr_conflicts_for(person):
    """Live ADP↔IZ8 field comparison + conflict state machine."""
    adp, iz8 = person["hr"]["adp"], person["hr"]["iz8"]
    le = LE_BY_CODE.get(person["legal_entity"], {})
    authority = le.get("hr", "ADP")
    out = []
    for field in ["employment_status", "termination_date", "manager", "legal_entity", "worker_type", "job_title"]:
        av, iv = adp.get(field), iz8.get(field)
        if av != iv:
            hold = field in SECURITY_HOLD_FIELDS
            out.append({
                "field": field, "adp_value": av, "iz8_value": iv,
                "authority": authority, "authoritative_value": av if authority == "ADP" else iv,
                "state": "SECURITY HOLD" if hold else "CONFLICT",
                "security_hold": hold,
            })
    return out


async def _hr_state(org_id, person):
    """Merge stored reconciliation decisions over the live conflict list."""
    conflicts = _hr_conflicts_for(person)
    decisions = {d["field"]: d for d in await db.sap_hr_decisions.find(
        {"org_id": org_id, "person_ref": person["ref"]}, {"_id": 0}).to_list(50)}
    for c in conflicts:
        d = decisions.get(c["field"])
        if d:
            c["state"] = "RECONCILED"
            c["resolved_value"] = d.get("resolved_value")
            c["resolved_by"] = d.get("by")
            c["resolved_at"] = d.get("at")
            c["rationale"] = d.get("rationale")
    hold = any(c["state"] == "SECURITY HOLD" for c in conflicts)
    if conflicts and all(c["state"] == "RECONCILED" for c in conflicts):
        overall = "RECONCILED"
    elif hold:
        overall = "SECURITY HOLD"
    elif conflicts:
        overall = "CONFLICT"
    else:
        overall = "NORMAL"
    return conflicts, overall


async def _correlate(org_id):
    """One live pass producing everything the dashboards need."""
    persons, accounts = await _load(org_id)
    pmap = {p["ref"]: p for p in persons}
    # attach hr security-hold flag onto persons for risk scoring
    for p in persons:
        p["_hr_hold"] = any(c["security_hold"] for c in _hr_conflicts_for(p))
    conflicts = await _all_conflicts(org_id, accounts)
    conf_by_person = {}
    for c in conflicts:
        if c.get("person_ref"):
            conf_by_person.setdefault(c["person_ref"], []).append(c)
    acc_by_person = {}
    for a in accounts:
        if a.get("person_ref"):
            acc_by_person.setdefault(a["person_ref"], []).append(a)
    # per-person risk
    for p in persons:
        p["risk"] = _person_risk(p, acc_by_person.get(p["ref"], []), conf_by_person)
        p["accounts"] = acc_by_person.get(p["ref"], [])
        p["open_conflicts"] = len([c for c in conf_by_person.get(p["ref"], []) if c.get("status") == "Open"])
    # account flags
    for a in accounts:
        a["flags"] = _account_flags(a, pmap.get(a.get("person_ref")))
    return persons, accounts, conflicts, pmap


async def _ensure(org_id):
    await seed_sap_uac(org_id)


__all__ = ["_now", "_iso", "seed_sap_uac", "_build_person", "_build_account", "_load",
           "_account_functions", "_functions_provenance", "_account_conflicts",
           "_all_conflicts", "_account_flags", "_person_risk", "_hr_conflicts_for",
           "_hr_state", "_correlate", "_ensure"]
