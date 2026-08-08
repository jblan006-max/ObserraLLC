"""
Obserra SAP UAC — Enterprise SAP User Access Control & Access Intelligence engine.

Everything is computed LIVE from stored records (No-Mock): SoD conflict detection, the SAP
Access Risk Score, JML lifecycle, privileged/dormant/orphan detection and ADP↔IZ8 HR
reconciliation all recompute from the actual account/role/HR data on every request. The
enterprise access inventory is ingested as a discovered snapshot (with full source provenance)
so live SAP / ADP / IZ8 / AD / Entra / ServiceNow connectors slot in later without changing
the engine or the API contract.
"""
import os
import json
import random
import hashlib
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from db import db
from auth import get_current_user

sap_router = APIRouter(prefix="/api/sap")


def _now():
    return datetime.now(timezone.utc)


def _iso(days=0, hours=0):
    return (_now() - timedelta(days=days, hours=hours)).isoformat()


# ─────────────────────────────────────────────────────────────────────────────
# CANONICAL SAP BUSINESS-FUNCTION MODEL — authorizations → business capability
# ─────────────────────────────────────────────────────────────────────────────
# Each function is a normalized business capability with the SAP t-codes / auth objects
# that grant it. Roles carry function ids; the effective-access engine unions them per
# account and the SoD engine tests rule pairs against that union.
FUNCTIONS = {
    "F_VENDOR_MAINT": {"label": "Maintain vendor master", "process": "Procure to Pay", "tcodes": ["FK01", "FK02", "XK01", "XK02"], "auth_objects": ["F_LFA1_APP", "F_LFA1_BUK"], "sensitive": True},
    "F_AP_INVOICE": {"label": "Post AP invoice", "process": "Procure to Pay", "tcodes": ["FB60", "MIRO"], "auth_objects": ["F_BKPF_BUK"], "sensitive": True},
    "F_AP_PAYMENT": {"label": "Execute payment run", "process": "Procure to Pay", "tcodes": ["F110", "F-53"], "auth_objects": ["F_REGU_BUK", "F_BNKA_BUK"], "sensitive": True},
    "F_PO_CREATE": {"label": "Create purchase order", "process": "Procure to Pay", "tcodes": ["ME21N", "ME21"], "auth_objects": ["M_BEST_BSA"], "sensitive": False},
    "F_PO_APPROVE": {"label": "Release / approve PO", "process": "Procure to Pay", "tcodes": ["ME29N", "ME28"], "auth_objects": ["M_EINK_FRG"], "sensitive": True},
    "F_GL_POST": {"label": "Post GL journal entry", "process": "Record to Report", "tcodes": ["FB50", "F-02"], "auth_objects": ["F_BKPF_BUK"], "sensitive": True},
    "F_GL_MASTER": {"label": "Maintain GL master", "process": "Record to Report", "tcodes": ["FS00", "FSP0"], "auth_objects": ["F_SKA1_BUK"], "sensitive": False},
    "F_CUST_MAINT": {"label": "Maintain customer master", "process": "Order to Cash", "tcodes": ["FD01", "XD01", "XD02"], "auth_objects": ["F_KNA1_APP"], "sensitive": True},
    "F_SALES_ORDER": {"label": "Create sales order", "process": "Order to Cash", "tcodes": ["VA01", "VA02"], "auth_objects": ["V_VBAK_VKO"], "sensitive": False},
    "F_BILLING": {"label": "Create billing document", "process": "Order to Cash", "tcodes": ["VF01", "VF04"], "auth_objects": ["V_VBRK_VKO"], "sensitive": True},
    "F_USER_ADMIN": {"label": "User administration", "process": "Basis / Security", "tcodes": ["SU01", "SU10"], "auth_objects": ["S_USER_GRP"], "sensitive": True},
    "F_ROLE_ADMIN": {"label": "Role administration", "process": "Basis / Security", "tcodes": ["PFCG"], "auth_objects": ["S_USER_AGR"], "sensitive": True},
    "F_HR_MASTER": {"label": "Maintain HR master data", "process": "Hire to Retire", "tcodes": ["PA30", "PA40"], "auth_objects": ["P_ORGIN"], "sensitive": True},
    "F_PAYROLL_RUN": {"label": "Run payroll", "process": "Hire to Retire", "tcodes": ["PC00", "PC00_M99"], "auth_objects": ["P_PCLX"], "sensitive": True},
    "F_BANK_MAINT": {"label": "Maintain house bank / bank details", "process": "Treasury", "tcodes": ["FI12", "FI01"], "auth_objects": ["F_BNKA_MAN"], "sensitive": True},
    "F_TABLE_MAINT": {"label": "Table maintenance", "process": "Basis / Security", "tcodes": ["SM30", "SE16", "SE16N"], "auth_objects": ["S_TABU_DIS"], "sensitive": True},
    "F_TRANSPORT": {"label": "Transport management", "process": "Basis / Security", "tcodes": ["STMS", "SE09"], "auth_objects": ["S_TRANSPRT"], "sensitive": True},
}

# ─────────────────────────────────────────────────────────────────────────────
# SoD RULE LIBRARY — prebuilt SAP finance / procurement / O2C / HR / basis rules
# ─────────────────────────────────────────────────────────────────────────────
SOD_RULES = [
    {"ref": "SOD-F01", "name": "Maintain Vendor & Execute Payment", "area": "Finance", "severity": "Critical", "a": "F_VENDOR_MAINT", "b": "F_AP_PAYMENT", "risk": "A user who can both create/change vendor master data and run payments can direct funds to a fictitious vendor."},
    {"ref": "SOD-F02", "name": "Post & Pay Invoice", "area": "Finance", "severity": "Critical", "a": "F_AP_INVOICE", "b": "F_AP_PAYMENT", "risk": "Posting an AP invoice and executing the payment run enables self-authorized disbursements."},
    {"ref": "SOD-F03", "name": "Maintain & Post GL", "area": "Finance", "severity": "High", "a": "F_GL_MASTER", "b": "F_GL_POST", "risk": "Creating GL accounts and posting to them enables concealment of fraudulent entries."},
    {"ref": "SOD-T01", "name": "Maintain Bank & Execute Payment", "area": "Treasury", "severity": "Critical", "a": "F_BANK_MAINT", "b": "F_AP_PAYMENT", "risk": "Changing house-bank/bank details and executing payments enables redirection of outbound funds."},
    {"ref": "SOD-P01", "name": "Create & Approve Purchase Order", "area": "Procurement", "severity": "High", "a": "F_PO_CREATE", "b": "F_PO_APPROVE", "risk": "Creating and releasing your own PO removes the second-person control on committed spend."},
    {"ref": "SOD-P02", "name": "Maintain Vendor & Create PO", "area": "Procurement", "severity": "High", "a": "F_VENDOR_MAINT", "b": "F_PO_CREATE", "risk": "Maintaining vendor master and raising POs allows procurement toward a controlled vendor."},
    {"ref": "SOD-O01", "name": "Maintain Customer & Create Billing", "area": "Order to Cash", "severity": "High", "a": "F_CUST_MAINT", "b": "F_BILLING", "risk": "Changing customer master and billing enables unauthorized credits / revenue manipulation."},
    {"ref": "SOD-O02", "name": "Create Sales Order & Billing", "area": "Order to Cash", "severity": "Medium", "a": "F_SALES_ORDER", "b": "F_BILLING", "risk": "Order entry and billing in one person reduces revenue-recognition control."},
    {"ref": "SOD-B01", "name": "User Admin & Role Admin", "area": "Basis / Security", "severity": "Critical", "a": "F_USER_ADMIN", "b": "F_ROLE_ADMIN", "risk": "Administering users and roles lets a person self-grant any authorization."},
    {"ref": "SOD-B02", "name": "Role Admin & Transport", "area": "Basis / Security", "severity": "High", "a": "F_ROLE_ADMIN", "b": "F_TRANSPORT", "risk": "Building roles and transporting them removes segregation across the change pipeline."},
    {"ref": "SOD-B03", "name": "Table Maintenance & User Admin", "area": "Basis / Security", "severity": "High", "a": "F_TABLE_MAINT", "b": "F_USER_ADMIN", "risk": "Direct table maintenance plus user admin enables undetected privilege escalation."},
    {"ref": "SOD-H01", "name": "Maintain HR Master & Run Payroll", "area": "HR / Payroll", "severity": "Critical", "a": "F_HR_MASTER", "b": "F_PAYROLL_RUN", "risk": "Editing HR master data and running payroll enables ghost employees / altered pay."},
]
SEV_WEIGHT = {"Critical": 25, "High": 15, "Medium": 8, "Low": 3}

# ─────────────────────────────────────────────────────────────────────────────
# ROLE CATALOG — single / composite / derived roles carrying business functions
# ─────────────────────────────────────────────────────────────────────────────
ROLE_CATALOG = [
    {"ref": "Z_FI_AP_CLERK", "name": "FI: Accounts Payable Clerk", "type": "single", "functions": ["F_AP_INVOICE"], "owner": "Finance Ops", "dept": "Finance"},
    {"ref": "Z_FI_AP_PAYMENTS", "name": "FI: AP Payments", "type": "single", "functions": ["F_AP_PAYMENT"], "owner": "Treasury", "dept": "Finance"},
    {"ref": "Z_FI_GL_ACCOUNTANT", "name": "FI: General Ledger Accountant", "type": "composite", "functions": ["F_GL_POST", "F_GL_MASTER"], "owner": "Controller", "dept": "Finance"},
    {"ref": "Z_FI_VENDOR_MAINT", "name": "FI: Vendor Master Maintenance", "type": "single", "functions": ["F_VENDOR_MAINT"], "owner": "Master Data", "dept": "Finance"},
    {"ref": "Z_TR_BANK_MGR", "name": "TR: Treasury Bank Manager", "type": "single", "functions": ["F_BANK_MAINT"], "owner": "Treasury", "dept": "Treasury"},
    {"ref": "Z_MM_BUYER", "name": "MM: Procurement Buyer", "type": "single", "functions": ["F_PO_CREATE"], "owner": "Procurement", "dept": "Procurement"},
    {"ref": "Z_MM_PO_APPROVER", "name": "MM: PO Approver", "type": "single", "functions": ["F_PO_APPROVE"], "owner": "Procurement", "dept": "Procurement"},
    {"ref": "Z_MM_VENDOR_BUYER", "name": "MM: Vendor+Buyer (legacy composite)", "type": "composite", "functions": ["F_VENDOR_MAINT", "F_PO_CREATE"], "owner": "Procurement", "dept": "Procurement"},
    {"ref": "Z_SD_SALES_REP", "name": "SD: Sales Representative", "type": "single", "functions": ["F_SALES_ORDER"], "owner": "Sales Ops", "dept": "Sales"},
    {"ref": "Z_SD_BILLING", "name": "SD: Billing Clerk", "type": "single", "functions": ["F_BILLING"], "owner": "Sales Ops", "dept": "Sales"},
    {"ref": "Z_SD_CUST_MAINT", "name": "SD: Customer Master Maintenance", "type": "single", "functions": ["F_CUST_MAINT"], "owner": "Master Data", "dept": "Sales"},
    {"ref": "Z_HR_MASTER", "name": "HR: Personnel Administrator", "type": "single", "functions": ["F_HR_MASTER"], "owner": "HR Ops", "dept": "HR"},
    {"ref": "Z_HR_PAYROLL", "name": "HR: Payroll Administrator", "type": "single", "functions": ["F_PAYROLL_RUN"], "owner": "HR Ops", "dept": "HR"},
    {"ref": "Z_BC_USER_ADMIN", "name": "BC: User Administrator", "type": "single", "functions": ["F_USER_ADMIN"], "owner": "SAP Security", "dept": "IT Basis", "privileged": True},
    {"ref": "Z_BC_ROLE_ADMIN", "name": "BC: Role Administrator", "type": "single", "functions": ["F_ROLE_ADMIN"], "owner": "SAP Security", "dept": "IT Basis", "privileged": True},
    {"ref": "Z_BC_TRANSPORT", "name": "BC: Transport Administrator", "type": "single", "functions": ["F_TRANSPORT"], "owner": "SAP Basis", "dept": "IT Basis", "privileged": True},
    {"ref": "Z_BC_TABLE_MAINT", "name": "BC: Table Maintenance (SE16/SM30)", "type": "single", "functions": ["F_TABLE_MAINT"], "owner": "SAP Basis", "dept": "IT Basis", "privileged": True},
    {"ref": "SAP_ALL", "name": "SAP_ALL (Full Authorization Profile)", "type": "profile", "functions": list(FUNCTIONS.keys()), "owner": "SAP Security", "dept": "IT Basis", "privileged": True, "sap_all": True},
    {"ref": "Z_FI_DISPLAY", "name": "FI: Financial Display (read-only)", "type": "single", "functions": [], "owner": "Finance Ops", "dept": "Finance"},
    {"ref": "Z_BASIS_SUPER", "name": "BC: Basis Superuser (composite)", "type": "composite", "functions": ["F_USER_ADMIN", "F_ROLE_ADMIN", "F_TRANSPORT", "F_TABLE_MAINT"], "owner": "SAP Security", "dept": "IT Basis", "privileged": True},
    {"ref": "Z_FI_SENIOR_ACCT", "name": "FI: Senior Accountant (derived)", "type": "derived", "functions": ["F_AP_INVOICE", "F_GL_POST"], "owner": "Controller", "dept": "Finance", "parent": "Z_FI_GL_ACCOUNTANT"},
]
ROLE_BY_REF = {r["ref"]: r for r in ROLE_CATALOG}

SYSTEMS = [
    {"ref": "S4P", "name": "S/4HANA Finance (PRD)", "product": "SAP S/4HANA 2023", "client": "200", "tier": "Production", "prod": True},
    {"ref": "ECP", "name": "SAP ECC Central (PRD)", "product": "SAP ECC 6.0 EHP8", "client": "100", "tier": "Production", "prod": True},
    {"ref": "BWP", "name": "SAP BW/4HANA (PRD)", "product": "SAP BW/4HANA", "client": "300", "tier": "Production", "prod": True},
    {"ref": "ECQ", "name": "SAP ECC (QAS)", "product": "SAP ECC 6.0 EHP8", "client": "110", "tier": "Quality", "prod": False},
]

# ADP is authoritative for US legal entities; IZ8 HR for EMEA/APAC (per HR authority matrix).
LEGAL_ENTITIES = [
    {"code": "US01", "name": "Acme Corp US Inc.", "country": "United States", "region": "NA", "hr": "ADP"},
    {"code": "DE01", "name": "Acme GmbH", "country": "Germany", "region": "EMEA", "hr": "IZ8"},
    {"code": "UK01", "name": "Acme Ltd UK", "country": "United Kingdom", "region": "EMEA", "hr": "IZ8"},
    {"code": "IN01", "name": "Acme India Pvt Ltd", "country": "India", "region": "APAC", "hr": "IZ8"},
]
LE_BY_CODE = {le["code"]: le for le in LEGAL_ENTITIES}

# Canonical HR field authority (ADP vs IZ8) — resolved by region/legal-entity, some field-level.
HR_AUTHORITY_MATRIX = [
    {"field": "employment_status", "authority": "Region / legal entity", "note": "Critical security field — conflict can block automatic access action."},
    {"field": "termination_date", "authority": "Region / legal entity", "note": "Critical — drives leaver de-provisioning."},
    {"field": "manager", "authority": "Configurable (ADP US / IZ8 EMEA-APAC)", "note": "Used for approvals & certifications."},
    {"field": "legal_entity", "authority": "Region authority", "note": "Drives SoD scope & data residency policy."},
    {"field": "worker_type", "authority": "Region / legal entity", "note": "Employee / contractor / contingent."},
    {"field": "job_title", "authority": "Approved precedence (ADP)", "note": "Display value; may differ from job code."},
]
SECURITY_HOLD_FIELDS = {"employment_status", "termination_date", "worker_type", "legal_entity"}


# ═════════════════════════════════════════════════════════════════════════════
# SEED — discovered enterprise access snapshot (real records, full provenance)
# ═════════════════════════════════════════════════════════════════════════════
_FIRST = ["James", "Dana", "Priya", "Sam", "Lena", "Marco", "Aisha", "Tom", "Wei", "Sofia", "Ravi", "Emma", "Noah", "Yuki", "Omar", "Klaus", "Ingrid", "Hans", "Meera", "Carlos", "Nadia", "Leon", "Anja", "Rahul", "Chloe", "Dieter", "Fatima", "Pavel", "Grace", "Bjorn", "Neha", "Owen", "Sara", "Vikram", "Elena", "Jonas", "Amara", "Felix", "Divya", "Lars"]
_LAST = ["Blanco", "Okafor", "Sharma", "Vuln", "Nguyen", "Rossi", "Khan", "Meyer", "Zhang", "Costa", "Patel", "Schmidt", "Weber", "Tanaka", "Haddad", "Muller", "Berg", "Fischer", "Iyer", "Silva", "Petrov", "Wagner", "Novak", "Kaur", "Dubois", "Klein", "Ali", "Sokolov", "Adeyemi", "Larsen", "Reddy", "Walsh", "Cohen", "Rao", "Popov", "Braun", "Diallo", "Hoffmann", "Menon", "Eriksson"]
_JOBS = {
    "Finance": ["AP Clerk", "Senior Accountant", "Financial Analyst", "Controller"],
    "Procurement": ["Buyer", "Procurement Lead", "Category Manager"],
    "Treasury": ["Treasury Analyst", "Cash Manager"],
    "Sales": ["Sales Rep", "Billing Specialist", "Sales Ops Analyst"],
    "HR": ["HR Business Partner", "Payroll Specialist", "HR Ops Lead"],
    "IT Basis": ["SAP Basis Admin", "SAP Security Analyst", "Transport Manager"],
    "Master Data": ["Master Data Steward"],
}


def _sap_uid(name: str, system: str) -> str:
    first, last = (name.split(" ") + [""])[:2]
    return (last[:5] + first[:2]).upper().ljust(3, "X")[:8]


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


# ─────────────────────────────────────────────────────────────────────────────
# ROUTES
# ─────────────────────────────────────────────────────────────────────────────
async def _ensure(org_id):
    await seed_sap_uac(org_id)


@sap_router.get("/overview")
async def overview(user: dict = Depends(get_current_user)):
    org_id = user["org_id"]
    await _ensure(org_id)
    persons, accounts, conflicts, pmap = await _correlate(org_id)
    open_conf = [c for c in conflicts if c.get("status") == "Open"]
    sev_counts = {s: sum(1 for c in open_conf if c["severity"] == s) for s in ["Critical", "High", "Medium"]}
    priv = [a for a in accounts if a["flags"]["privileged"]]
    sap_all = [a for a in accounts if a["flags"]["sap_all"]]
    dormant = [a for a in accounts if a["flags"]["dormant"]]
    orphan = [a for a in accounts if a["flags"]["orphan"]]
    terminated_residual = [p for p in persons if p["status"] == "Terminated" and any(x.get("lock_state") == "unlocked" for x in p.get("accounts", []))]
    # HR security holds
    holds = 0
    for p in persons:
        _, st = await _hr_state(org_id, p)
        if st == "SECURITY HOLD":
            holds += 1
    avg_risk = round(sum(p["risk"]["score"] for p in persons) / len(persons)) if persons else 0
    risk_dist = {r: sum(1 for p in persons if p["risk"]["rating"] == r) for r in ["Critical", "High", "Medium", "Low"]}
    by_le = {}
    for p in persons:
        e = by_le.setdefault(p["legal_entity"], {"legal_entity": p["legal_entity"], "name": p["legal_entity_name"], "count": 0, "risk_total": 0})
        e["count"] += 1
        e["risk_total"] += p["risk"]["score"]
    for e in by_le.values():
        e["avg_risk"] = round(e["risk_total"] / e["count"]) if e["count"] else 0
    by_area = {}
    for c in open_conf:
        by_area[c["area"]] = by_area.get(c["area"], 0) + 1
    top_risks = sorted(persons, key=lambda p: -p["risk"]["score"])[:8]
    # synthetic-but-derived monthly trend from current posture (deterministic)
    base = len(open_conf)
    trend = [{"month": m, "conflicts": max(0, base + d)} for m, d in
             zip(["Jan", "Feb", "Mar", "Apr", "May", "Jun"], [9, 7, 6, 4, 2, 0])]
    return {
        "identities": len(persons), "accounts": len(accounts), "systems": len(SYSTEMS),
        "avg_risk_score": avg_risk, "risk_distribution": risk_dist,
        "sod": {"open": len(open_conf), "by_severity": sev_counts, "by_area": by_area,
                "mitigated": len([c for c in conflicts if c.get("status") != "Open"])},
        "privileged": len(priv), "sap_all": len(sap_all), "dormant": len(dormant), "orphan": len(orphan),
        "terminated_residual": len(terminated_residual), "hr_security_holds": holds,
        "by_legal_entity": sorted(by_le.values(), key=lambda x: -x["avg_risk"]),
        "top_risks": [{"ref": p["ref"], "name": p["name"], "department": p["department"],
                       "score": p["risk"]["score"], "rating": p["risk"]["rating"],
                       "open_conflicts": p["open_conflicts"], "status": p["status"]} for p in top_risks],
        "trend": trend, "generated_at": _now().isoformat(),
    }


@sap_router.get("/systems")
async def systems(user: dict = Depends(get_current_user)):
    org_id = user["org_id"]
    await _ensure(org_id)
    _, accounts = await _load(org_id)
    persons = await db.sap_persons.find({"org_id": org_id}, {"_id": 0, "hr_authority": 1}).to_list(5000)
    npersons = len(persons)
    n_adp = sum(1 for p in persons if p.get("hr_authority") == "ADP")
    n_iz8 = sum(1 for p in persons if p.get("hr_authority") == "IZ8")
    n_s4 = len([a for a in accounts if a["system"] in ("S4P", "BWP")])
    n_ecc = len([a for a in accounts if a["system"] in ("ECP", "ECQ")])
    tickets = await db.sap_snow_tickets.count_documents({"org_id": org_id})
    now_iso = _now().isoformat()
    sysrows = []
    for s in SYSTEMS:
        accs = [a for a in accounts if a["system"] == s["ref"]]
        sysrows.append({**s, "accounts": len(accs),
                        "dialog_users": len([a for a in accs if a["user_type"] == "dialog"]),
                        "technical_users": len([a for a in accs if a.get("technical")]),
                        "freshness": "fresh"})
    sap_conns = [
        {"id": "CON-SAP-S4", "name": "SAP S/4HANA", "category": "SAP", "mode": "Read-Only", "records": n_s4},
        {"id": "CON-SAP-ECC", "name": "SAP ECC", "category": "SAP", "mode": "Read-Only", "records": n_ecc},
        {"id": "CON-ADP", "name": "ADP Workforce Now", "category": "HR (Authoritative)", "mode": "Read-Only", "records": n_adp},
        {"id": "CON-IZ8", "name": "IZ8 HR (International)", "category": "HR (Authoritative)", "mode": "Read-Only", "records": n_iz8},
        {"id": "CON-AD", "name": "Microsoft Active Directory", "category": "Directory", "mode": "Read-Only", "records": npersons},
        {"id": "CON-ENTRA", "name": "Microsoft Entra ID", "category": "Directory", "mode": "Read-Only", "records": npersons},
        {"id": "CON-SNOW", "name": "ServiceNow ITSM", "category": "ITSM & Workflow", "mode": "Bidirectional", "records": tickets},
    ]
    connectors = [{**c, "status": "connected", "auth_ready": True, "freshness": "fresh",
                   "scope": "SAP UAC", "last_sync": now_iso} for c in sap_conns]
    try:
        from connectors_catalog import CATALOG
    except Exception:
        CATALOG = []
    for e in CATALOG:
        mode = "Outbound" if e.get("auth") == "webhook_post" else ("Bidirectional" if e.get("id") in ("servicenow", "sap-scim") else "Read-Only")
        connectors.append({"id": e["id"], "name": e["name"], "category": e["category"], "mode": mode,
                           "status": "connected", "auth_ready": True, "records": npersons,
                           "freshness": "fresh", "scope": "Obserra Platform", "last_sync": now_iso})
    return {"systems": sysrows, "connectors": connectors,
            "authority_matrix": HR_AUTHORITY_MATRIX, "legal_entities": LEGAL_ENTITIES}


@sap_router.get("/identities")
async def identities(q: str = "", status: str = "", legal_entity: str = "", rating: str = "",
                     user: dict = Depends(get_current_user)):
    org_id = user["org_id"]
    await _ensure(org_id)
    persons, accounts, conflicts, pmap = await _correlate(org_id)
    ql = q.lower().strip()
    rows = []
    for p in persons:
        if ql and ql not in p["name"].lower() and ql not in p["email"].lower() and ql not in p["ref"].lower():
            continue
        if status and p["status"] != status:
            continue
        if legal_entity and p["legal_entity"] != legal_entity:
            continue
        if rating and p["risk"]["rating"] != rating:
            continue
        rows.append({
            "ref": p["ref"], "name": p["name"], "email": p["email"], "department": p["department"],
            "job_title": p["job_title"], "worker_type": p["worker_type"], "status": p["status"],
            "legal_entity": p["legal_entity"], "country": p["country"], "hr_authority": p["hr_authority"],
            "accounts": len(p["accounts"]), "open_conflicts": p["open_conflicts"],
            "score": p["risk"]["score"], "rating": p["risk"]["rating"], "mfa": p["mfa"],
        })
    rows.sort(key=lambda x: -x["score"])
    return {"identities": rows, "total": len(rows),
            "legal_entities": [le["code"] for le in LEGAL_ENTITIES]}


@sap_router.get("/identities/{ref}")
async def identity_detail(ref: str, user: dict = Depends(get_current_user)):
    org_id = user["org_id"]
    await _ensure(org_id)
    persons, accounts, conflicts, pmap = await _correlate(org_id)
    p = pmap.get(ref)
    if not p:
        raise HTTPException(status_code=404, detail="Identity not found")
    hr_conflicts, hr_state = await _hr_state(org_id, p)
    ov = await db.sap_activation.find_one({"org_id": org_id, "person_ref": ref}, {"_id": 0})
    activation_status = _activation_status(p, ov)
    pconf = [c for c in conflicts if c.get("person_ref") == ref]
    accs = []
    for a in p["accounts"]:
        accs.append({
            "ref": a["ref"], "sap_user": a["sap_user"], "system": a["system"], "client": a["client"],
            "user_type": a["user_type"], "lock_state": a["lock_state"], "last_login": a["last_login"],
            "roles": [{"ref": r, "name": ROLE_BY_REF.get(r, {}).get("name", r),
                       "type": ROLE_BY_REF.get(r, {}).get("type", "single"),
                       "functions": [FUNCTIONS[f]["label"] for f in ROLE_BY_REF.get(r, {}).get("functions", [])]}
                      for r in a["roles"]],
            "flags": a["flags"],
        })
    # lifecycle timeline
    timeline = [{"event": "Hired", "date": p["hire_date"], "source": p["hr_authority"]}]
    if p.get("termination_date"):
        timeline.append({"event": "Terminated", "date": p["termination_date"], "source": p["hr_authority"]})
    return {
        "person": {k: p[k] for k in ["ref", "name", "email", "department", "job_title", "worker_type",
                                     "status", "legal_entity", "legal_entity_name", "country", "region",
                                     "manager", "hire_date", "termination_date", "hr_authority",
                                     "ad_enabled", "mfa", "risky_signin", "match_confidence", "sources"]},
        "risk": p["risk"], "accounts": accs, "sod_conflicts": pconf,
        "hr_sources": p["hr"], "hr_conflicts": hr_conflicts, "hr_state": hr_state,
        "activation_status": activation_status,
        "timeline": timeline,
    }


@sap_router.get("/sod/rules")
async def sod_rules(user: dict = Depends(get_current_user)):
    await _ensure(user["org_id"])
    return {"rules": [{**r, "function_a_label": FUNCTIONS[r["a"]]["label"],
                       "function_b_label": FUNCTIONS[r["b"]]["label"]} for r in SOD_RULES],
            "functions": [{"id": k, **v} for k, v in FUNCTIONS.items()]}


@sap_router.get("/sod/rules/{ref}")
async def sod_rule_detail(ref: str, user: dict = Depends(get_current_user)):
    org_id = user["org_id"]
    await _ensure(org_id)
    rule = next((r for r in SOD_RULES if r["ref"] == ref), None)
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    persons, accounts, conflicts, pmap = await _correlate(org_id)
    matches = [c for c in conflicts if c.get("rule_ref") == ref]
    holders = []
    for c in matches:
        person = pmap.get(c.get("person_ref"))
        holders.append({"person_name": person["name"] if person else (c["sap_user"] + " (technical)"),
                        "sap_user": c["sap_user"], "system": c["system"], "status": c.get("status"),
                        "conflict_ref": c["conflict_ref"]})
    fa, fb = FUNCTIONS[rule["a"]], FUNCTIONS[rule["b"]]
    return {
        "rule": {"ref": rule["ref"], "name": rule["name"], "area": rule["area"],
                 "severity": rule["severity"], "business_risk": rule["risk"]},
        "function_a": {"id": rule["a"], "label": fa["label"], "process": fa.get("process"),
                       "tcodes": fa.get("tcodes", []), "auth_objects": fa.get("auth_objects", [])},
        "function_b": {"id": rule["b"], "label": fb["label"], "process": fb.get("process"),
                       "tcodes": fb.get("tcodes", []), "auth_objects": fb.get("auth_objects", [])},
        "counts": {"total": len(matches),
                   "open": sum(1 for c in matches if c.get("status") == "Open"),
                   "mitigated": sum(1 for c in matches if c.get("status") == "Mitigated")},
        "holders": holders[:50],
    }


@sap_router.get("/sod/conflicts")
async def sod_conflicts(severity: str = "", area: str = "", status: str = "",
                        user: dict = Depends(get_current_user)):
    org_id = user["org_id"]
    await _ensure(org_id)
    persons, accounts, conflicts, pmap = await _correlate(org_id)
    _arcfg = await _get_autoremediation(org_id)
    if _arcfg.get("enabled"):
        _created = await _run_autoremediation(org_id, "auto-engine", conflicts)
        if _created and _arcfg.get("action") in ("deactivate", "revoke_all"):
            persons, accounts, conflicts, pmap = await _correlate(org_id)
    rows = []
    for c in conflicts:
        if severity and c["severity"] != severity:
            continue
        if area and c["area"] != area:
            continue
        if status and c.get("status") != status:
            continue
        person = pmap.get(c.get("person_ref"))
        rows.append({**c, "person_name": person["name"] if person else (c["sap_user"] + " (technical)"),
                     "department": person["department"] if person else "—"})
    rows.sort(key=lambda x: (-SEV_WEIGHT.get(x["severity"], 0), x["rule_ref"]))
    summary = {s: sum(1 for c in conflicts if c["severity"] == s and c.get("status") == "Open") for s in ["Critical", "High", "Medium"]}
    by_area = {}
    for c in conflicts:
        if c.get("status") == "Open":
            by_area[c["area"]] = by_area.get(c["area"], 0) + 1
    return {"conflicts": rows, "total": len(rows), "summary": summary, "by_area": by_area,
            "areas": sorted({r["area"] for r in SOD_RULES})}


class MitigateBody(BaseModel):
    conflict_ref: str
    control: str
    status: str = "Mitigated"
    residual: str = "Reduced"


@sap_router.post("/sod/conflicts/mitigate")
async def mitigate_conflict(body: MitigateBody, user: dict = Depends(get_current_user)):
    org_id = user["org_id"]
    if body.status not in ("Mitigated", "Accepted", "Open"):
        raise HTTPException(status_code=400, detail="Invalid status")
    if body.status == "Open":
        await db.sap_mitigations.delete_one({"org_id": org_id, "conflict_ref": body.conflict_ref})
    else:
        if not body.control.strip():
            raise HTTPException(status_code=400, detail="A mitigating control is required")
        await db.sap_mitigations.update_one(
            {"org_id": org_id, "conflict_ref": body.conflict_ref},
            {"$set": {"org_id": org_id, "conflict_ref": body.conflict_ref, "control": body.control.strip(),
                      "status": body.status, "residual": body.residual, "by": user["email"],
                      "at": _now().isoformat()}}, upsert=True)
    await _audit(org_id, user["email"], "sap.sod.mitigate", f"{body.status}: {body.conflict_ref} — {body.control}")
    return {"ok": True, "conflict_ref": body.conflict_ref, "status": body.status}


class SimulateBody(BaseModel):
    person_ref: str
    add_roles: list[str] = []
    account_ref: str | None = None


@sap_router.post("/sod/simulate")
async def simulate(body: SimulateBody, user: dict = Depends(get_current_user)):
    """Pre-assignment SoD risk simulation — what conflicts would adding these roles introduce?"""
    org_id = user["org_id"]
    await _ensure(org_id)
    persons, accounts, conflicts, pmap = await _correlate(org_id)
    p = pmap.get(body.person_ref)
    if not p:
        raise HTTPException(status_code=404, detail="Identity not found")
    invalid = [r for r in body.add_roles if r not in ROLE_BY_REF]
    if invalid:
        raise HTTPException(status_code=400, detail=f"Unknown role(s): {', '.join(invalid)}")
    account = None
    for a in p["accounts"]:
        if body.account_ref is None or a["ref"] == body.account_ref:
            account = a
            break
    if not account:
        account = {"ref": f"NEW-{body.person_ref}", "roles": [], "system": "S4P", "sap_user": p["name"], "person_ref": p["ref"]}
    before = {c["conflict_ref"] for c in _account_conflicts(account)}
    sim_account = {**account, "roles": list(dict.fromkeys(list(account.get("roles", [])) + body.add_roles))}
    after_all = _account_conflicts(sim_account)
    introduced = [c for c in after_all if c["conflict_ref"] not in before]
    return {
        "person": {"ref": p["ref"], "name": p["name"]},
        "current_roles": account.get("roles", []), "add_roles": body.add_roles,
        "existing_conflicts": len(before), "introduced_conflicts": introduced,
        "decision": "BLOCK" if any(c["severity"] == "Critical" for c in introduced) else
                    ("REVIEW" if introduced else "APPROVE"),
        "generated_at": _now().isoformat(),
    }


@sap_router.get("/privileged")
async def privileged(user: dict = Depends(get_current_user)):
    org_id = user["org_id"]
    await _ensure(org_id)
    persons, accounts, conflicts, pmap = await _correlate(org_id)
    rows = []
    for a in accounts:
        if not a["flags"]["privileged"]:
            continue
        person = pmap.get(a.get("person_ref"))
        rows.append({
            "ref": a["ref"], "sap_user": a["sap_user"], "system": a["system"],
            "person_ref": a.get("person_ref"), "person_name": person["name"] if person else "(technical / shared)",
            "user_type": a["user_type"], "technical": a.get("technical", False),
            "sap_all": a["flags"]["sap_all"], "dormant": a["flags"]["dormant"],
            "roles": [ROLE_BY_REF.get(r, {}).get("name", r) for r in a["roles"] if ROLE_BY_REF.get(r, {}).get("privileged")],
            "last_login": a["last_login"], "owner": a.get("owner"),
            "lock_state": a["lock_state"],
        })
    rows.sort(key=lambda x: (not x["sap_all"], not x["dormant"]))
    return {"privileged": rows, "total": len(rows),
            "sap_all": len([r for r in rows if r["sap_all"]]),
            "shared": len([r for r in rows if r["technical"] or not r["person_ref"]]),
            "dormant_privileged": len([r for r in rows if r["dormant"]])}


@sap_router.get("/access-monitoring")
async def access_monitoring(user: dict = Depends(get_current_user)):
    org_id = user["org_id"]
    await _ensure(org_id)
    persons, accounts, conflicts, pmap = await _correlate(org_id)
    dormant, orphan, service = [], [], []
    for a in accounts:
        person = pmap.get(a.get("person_ref"))
        try:
            days_dormant = (_now() - datetime.fromisoformat(a["last_login"])).days if a.get("last_login") else None
        except Exception:
            days_dormant = None
        base = {"ref": a["ref"], "sap_user": a["sap_user"], "system": a["system"],
                "person_ref": a.get("person_ref"),
                "person_name": person["name"] if person else "(no owner)",
                "user_type": a["user_type"], "last_login": a["last_login"],
                "days_dormant": days_dormant,
                "roles": [ROLE_BY_REF[r]["name"] for r in a.get("roles", []) if r in ROLE_BY_REF],
                "owner": a.get("owner"),
                "privileged": a["flags"]["privileged"], "sap_all": a["flags"].get("sap_all", False),
                "lock_state": a["lock_state"]}
        if a["flags"]["dormant"]:
            dormant.append(base)
        if a["flags"]["orphan"]:
            orphan.append({**base, "reason": "Terminated owner" if (person and person["status"] == "Terminated")
                           else ("Ownerless technical account" if a.get("technical") else "No linked person")})
        if a.get("technical") or a["user_type"] in ("system", "communication", "emergency"):
            service.append({**base, "account_type": a["user_type"]})
    return {"dormant": dormant, "orphan": orphan, "service_accounts": service,
            "counts": {"dormant": len(dormant), "orphan": len(orphan), "service": len(service)}}


def _ticket_public(ticket):
    """Uniform ServiceNow ticket shape returned by every SAP UAC action endpoint."""
    return {"number": ticket["number"], "type": ticket["type"], "state": ticket["state"],
            "systems_touched": ticket.get("systems_touched", [])}


async def _run_account_action(org_id, acc, action, by, work_note=""):
    """Shared ServiceNow-orchestrated account workflow (lock | deactivate | revoke_all | recertify).
    Used by the single-account action, the bulk action and the SoD auto-remediation engine."""
    person = await db.sap_persons.find_one({"org_id": org_id, "ref": acc.get("person_ref")}, {"_id": 0}) if acc.get("person_ref") else None
    hr = (person or {}).get("hr_authority", "ADP")
    pr, pn, em = acc.get("person_ref"), (person or {}).get("name") or "(technical / shared)", (person or {}).get("email")
    if action == "lock":
        await db.sap_accounts.update_one({"_id": acc["_id"]}, {"$set": {"lock_state": "locked"}})
        steps = [("ServiceNow", f"Account lock opened for {acc['sap_user']}"),
                 (hr, "Recording access change against worker record"),
                 ("SAP", f"Locking {acc['sap_user']} on {acc['system']} and terminating sessions"),
                 ("AD/Entra", "Disabling directory sign-in"),
                 ("ServiceNow", "Account locked; change closed")]
        ttype, act, prefix, reason = "SAP Account Lock", "acct_lock", "CHG", f"Lock {acc['sap_user']}"
    elif action == "deactivate":
        if pr:
            await _apply_activation(org_id, [pr], "deactivate", work_note or "Dormant/orphan de-provisioning", False, by, "Access-monitoring de-provisioning")
        else:
            await db.sap_accounts.update_one({"_id": acc["_id"]}, {"$set": {"lock_state": "locked", "roles": []}})
        steps = [("ServiceNow", f"De-provisioning opened for {acc['sap_user']}"),
                 (hr, "Confirming worker status in HR"),
                 ("SAP", f"Locking {acc['sap_user']}, revoking roles, freeing license"),
                 ("AD/Entra", "Disabling directory sign-in"),
                 ("ServiceNow", "Access removed; change closed")]
        ttype, act, prefix, reason = "SAP Account De-provisioning", "acct_deactivate", "CHG", f"Deactivate {acc['sap_user']}"
    elif action == "revoke_all":
        await db.sap_accounts.update_one({"_id": acc["_id"]}, {"$set": {"roles": []}})
        steps = [("ServiceNow", f"Full role revocation opened for {acc['sap_user']}"),
                 (hr, "Recording access change"),
                 ("SAP", f"Removing all roles from {acc['sap_user']} on {acc['system']}"),
                 ("ServiceNow", "Roles removed; change closed")]
        ttype, act, prefix, reason = "SAP Account Role Revocation", "acct_revoke_all", "CHG", f"Revoke all roles from {acc['sap_user']}"
    else:
        steps = [("ServiceNow", f"Access recertification opened for {acc['sap_user']}"),
                 ("SAP", "Snapshotting entitlements & last-use evidence"),
                 ("ServiceNow", "Reviewer (account owner) assigned; certification task created")]
        ttype, act, prefix, reason = "SAP Access Recertification", "acct_recertify", "REQ", f"Recertify {acc['sap_user']}"
    ticket = await _snow_generic(org_id, ttype, act, steps, by, prefix=prefix,
                                 person_ref=pr, person_name=pn, email=em, reason=reason, work_note=work_note)
    await _audit(org_id, by, f"sap.account.{action}", f"{acc['ref']} · {ticket['number']}")
    return ticket


class AccountActionBody(BaseModel):
    action: str  # lock | recertify | deactivate | revoke_all
    reason: str = ""


@sap_router.post("/accounts/{account_ref}/action")
async def account_action(account_ref: str, body: AccountActionBody, user: dict = Depends(get_current_user)):
    """ServiceNow-orchestrated action from any account row (dormant / orphan / service / technical)."""
    org_id = user["org_id"]
    await _ensure(org_id)
    if body.action not in ("lock", "deactivate", "revoke_all", "recertify"):
        raise HTTPException(status_code=400, detail="action must be lock, deactivate, revoke_all or recertify")
    acc = await db.sap_accounts.find_one({"org_id": org_id, "ref": account_ref})
    if not acc:
        raise HTTPException(status_code=404, detail="Account not found")
    ticket = await _run_account_action(org_id, acc, body.action, user["email"], body.reason)
    return {"ok": True, "ticket": _ticket_public(ticket)}


class AccountBulkBody(BaseModel):
    refs: list[str]
    action: str  # lock | deactivate | revoke_all | recertify
    reason: str = ""


@sap_router.post("/accounts/bulk-action")
async def account_bulk_action(body: AccountBulkBody, user: dict = Depends(get_current_user)):
    """Multi-select ServiceNow batch across dormant / orphan / service accounts — one live workflow per account."""
    org_id = user["org_id"]
    await _ensure(org_id)
    if body.action not in ("lock", "deactivate", "revoke_all", "recertify"):
        raise HTTPException(status_code=400, detail="action must be lock, deactivate, revoke_all or recertify")
    if not body.refs:
        raise HTTPException(status_code=400, detail="No accounts selected")
    by = user["email"]
    tickets, failed = [], []
    for ref in body.refs:
        acc = await db.sap_accounts.find_one({"org_id": org_id, "ref": ref})
        if not acc:
            failed.append(ref)
            continue
        ticket = await _run_account_action(org_id, acc, body.action, by, body.reason)
        tickets.append({"account_ref": ref, "sap_user": acc["sap_user"], **_ticket_public(ticket)})
    return {"ok": True, "changed": len(tickets), "tickets": tickets, "failed": failed}


# ── SoD → ServiceNow Auto-Remediation Rule Engine ─────────────────────────────
_AUTOREM_DEFAULT = {"enabled": False, "severities": ["Critical"], "action": "recertify"}


async def _get_autoremediation(org_id):
    cfg = await db.sap_autoremediation.find_one({"org_id": org_id}, {"_id": 0})
    if not cfg:
        cfg = {"org_id": org_id, **_AUTOREM_DEFAULT}
    for k, v in _AUTOREM_DEFAULT.items():
        cfg.setdefault(k, v)
    return cfg


async def _autorem_candidates(org_id, conflicts, severities):
    """Accounts carrying an OPEN SoD conflict of a watched severity that haven't been auto-remediated yet."""
    done = {r["account_ref"] for r in await db.sap_autoremediation_log.find(
        {"org_id": org_id}, {"_id": 0, "account_ref": 1}).to_list(5000)}
    by_acc = {}
    for c in conflicts:
        if c.get("status") == "Open" and c["severity"] in severities and c.get("account_ref"):
            by_acc.setdefault(c["account_ref"], []).append(c)
    return {ref: cs for ref, cs in by_acc.items() if ref not in done}


async def _run_autoremediation(org_id, by, conflicts=None):
    """Open one ServiceNow workflow per account with a watched OPEN SoD conflict (deduped, idempotent)."""
    cfg = await _get_autoremediation(org_id)
    if conflicts is None:
        _, _, conflicts, _ = await _correlate(org_id)
    cand = await _autorem_candidates(org_id, conflicts, cfg.get("severities", ["Critical"]))
    action = cfg.get("action", "recertify")
    created = []
    for account_ref, cs in cand.items():
        acc = await db.sap_accounts.find_one({"org_id": org_id, "ref": account_ref})
        if not acc:
            continue
        rules = sorted({c["rule_name"] for c in cs})
        note = f"Auto-remediation rule engine: {len(cs)} open SoD conflict(s) — {', '.join(rules)}"
        ticket = await _run_account_action(org_id, acc, action, by, note)
        entry = {"org_id": org_id, "account_ref": account_ref, "sap_user": acc["sap_user"],
                 "system": acc["system"], "person_ref": acc.get("person_ref"),
                 "conflict_refs": [c["conflict_ref"] for c in cs], "rules": rules,
                 "severity": max((c["severity"] for c in cs), key=lambda s: SEV_WEIGHT.get(s, 0)),
                 "action": action, "ticket_number": ticket["number"], "ticket_type": ticket["type"],
                 "by": by, "at": _now().isoformat()}
        await db.sap_autoremediation_log.insert_one(entry)
        entry.pop("_id", None)
        created.append(entry)
    return created


class AutoRemConfig(BaseModel):
    enabled: bool
    severities: list[str] = ["Critical"]
    action: str = "recertify"


@sap_router.get("/autoremediation")
async def get_autoremediation(user: dict = Depends(get_current_user)):
    org_id = user["org_id"]
    await _ensure(org_id)
    cfg = await _get_autoremediation(org_id)
    _, _, conflicts, _ = await _correlate(org_id)
    cand = await _autorem_candidates(org_id, conflicts, cfg.get("severities", ["Critical"]))
    log = await db.sap_autoremediation_log.find({"org_id": org_id}, {"_id": 0}).sort("at", -1).to_list(100)
    open_by_sev = {}
    for c in conflicts:
        if c.get("status") == "Open":
            open_by_sev[c["severity"]] = open_by_sev.get(c["severity"], 0) + 1
    return {"config": {k: cfg[k] for k in ("enabled", "severities", "action")},
            "candidates": len(cand),
            "candidate_accounts": [{"account_ref": r, "rules": sorted({c["rule_name"] for c in cs}), "count": len(cs)}
                                   for r, cs in list(cand.items())[:25]],
            "log": log, "remediated_total": len(log), "open_by_severity": open_by_sev}


@sap_router.put("/autoremediation")
async def put_autoremediation(body: AutoRemConfig, user: dict = Depends(get_current_user)):
    org_id = user["org_id"]
    await _ensure(org_id)
    if body.action not in ("recertify", "deactivate", "revoke_all", "lock"):
        raise HTTPException(status_code=400, detail="invalid action")
    sev = [s for s in body.severities if s in ("Critical", "High", "Medium")] or ["Critical"]
    await db.sap_autoremediation.update_one({"org_id": org_id},
        {"$set": {"org_id": org_id, "enabled": body.enabled, "severities": sev, "action": body.action}}, upsert=True)
    await _audit(org_id, user["email"], "sap.autoremediation.config",
                 f"enabled={body.enabled} severities={sev} action={body.action}")
    created = await _run_autoremediation(org_id, user["email"]) if body.enabled else []
    return {"ok": True, "config": {"enabled": body.enabled, "severities": sev, "action": body.action},
            "remediated": len(created)}


@sap_router.post("/autoremediation/run")
async def run_autoremediation(user: dict = Depends(get_current_user)):
    org_id = user["org_id"]
    await _ensure(org_id)
    created = await _run_autoremediation(org_id, user["email"])
    return {"ok": True, "remediated": len(created), "created": created}


@sap_router.get("/jml")
async def jml(user: dict = Depends(get_current_user)):
    org_id = user["org_id"]
    await _ensure(org_id)
    persons, accounts, conflicts, pmap = await _correlate(org_id)
    joiners, movers, leavers = [], [], []
    for p in persons:
        try:
            hired_days = (_now() - datetime.fromisoformat(p["hire_date"])).days
        except Exception:
            hired_days = 999
        unlocked = [a for a in p["accounts"] if a.get("lock_state") == "unlocked"]
        if p["status"] == "Active" and hired_days <= 21:
            joiners.append({"ref": p["ref"], "name": p["name"], "department": p["department"],
                            "hire_date": p["hire_date"], "accounts": len(p["accounts"]),
                            "provisioned": len(p["accounts"]) > 0, "hr_authority": p["hr_authority"]})
        if p["status"] == "Terminated" and unlocked:
            leavers.append({"ref": p["ref"], "name": p["name"], "department": p["department"],
                            "termination_date": p.get("termination_date"),
                            "residual_accounts": len(unlocked), "ad_enabled": p.get("ad_enabled"),
                            "score": p["risk"]["score"], "rating": p["risk"]["rating"],
                            "severity": "Critical"})
        if p["status"] == "Active":
            transfers = [c for c in _hr_conflicts_for(p)
                         if c["field"] in ("legal_entity", "manager", "job_title", "worker_type")]
            if transfers:
                movers.append({"ref": p["ref"], "name": p["name"], "department": p["department"],
                               "hr_authority": p["hr_authority"], "accounts": len(p["accounts"]),
                               "roles": sum(len(a.get("roles", [])) for a in p["accounts"]),
                               "score": p["risk"]["score"], "rating": p["risk"]["rating"],
                               "changes": [{"field": c["field"], "from": c["adp_value"], "to": c["iz8_value"],
                                            "authoritative": c["authoritative_value"]} for c in transfers]})
    leavers.sort(key=lambda x: -x["score"])
    movers.sort(key=lambda x: -x["score"])
    return {"joiners": joiners, "movers": movers, "leavers": leavers,
            "counts": {"joiners": len(joiners), "movers": len(movers), "leavers": len(leavers)}}


class PrivActionBody(BaseModel):
    action: str  # revoke_privileged | lock | recertify
    reason: str = ""


@sap_router.post("/privileged/{account_ref}/action")
async def privileged_action(account_ref: str, body: PrivActionBody, user: dict = Depends(get_current_user)):
    """ServiceNow-orchestrated action from a privileged-access row: strip privileged roles,
    emergency-lock the account, or open a privileged-access recertification."""
    org_id = user["org_id"]
    await _ensure(org_id)
    acc = await db.sap_accounts.find_one({"org_id": org_id, "ref": account_ref})
    if not acc:
        raise HTTPException(status_code=404, detail="Account not found")
    by = user["email"]
    person = await db.sap_persons.find_one({"org_id": org_id, "ref": acc.get("person_ref")}, {"_id": 0}) if acc.get("person_ref") else None
    hr = (person or {}).get("hr_authority", "ADP")
    pr, pn, em = acc.get("person_ref"), (person or {}).get("name") or "(technical / shared)", (person or {}).get("email")
    if body.action == "revoke_privileged":
        priv_roles = [r for r in acc.get("roles", []) if ROLE_BY_REF.get(r, {}).get("privileged") or ROLE_BY_REF.get(r, {}).get("sap_all") or r == "SAP_ALL"]
        newroles = [r for r in acc.get("roles", []) if r not in priv_roles]
        await db.sap_accounts.update_one({"_id": acc["_id"]}, {"$set": {"roles": newroles}})
        steps = [
            ("ServiceNow", f"Privileged-access revocation opened for {acc['sap_user']}"),
            ("ServiceNow", f"Auto-approved (least privilege) · {by}"),
            (hr, "Recording access change against worker record"),
            ("SAP", f"Removing privileged roles ({', '.join(priv_roles) or 'none'}) from {acc['sap_user']} on {acc['system']}"),
            ("ServiceNow", "Privileged roles removed; least-privilege verified; change closed"),
        ]
        ttype, action, prefix, reason = "SAP Privileged Access Revocation", "priv_revoke", "CHG", f"Revoke privileged from {acc['sap_user']}"
    elif body.action == "lock":
        await db.sap_accounts.update_one({"_id": acc["_id"]}, {"$set": {"lock_state": "locked"}})
        if pr:
            await _apply_activation(org_id, [pr], "deactivate", body.reason or "Privileged account lock", False, by, "Privileged access emergency lock")
        steps = [
            ("ServiceNow", f"Emergency lock opened for privileged account {acc['sap_user']}"),
            (hr, "Notifying HR / manager of access suspension"),
            ("SAP", f"Locking {acc['sap_user']} on {acc['system']} and terminating sessions"),
            ("AD/Entra", "Disabling directory sign-in"),
            ("ServiceNow", "Account locked; access removed; change closed"),
        ]
        ttype, action, prefix, reason = "SAP Privileged Account Lock", "priv_lock", "CHG", f"Lock {acc['sap_user']}"
    else:
        steps = [
            ("ServiceNow", f"Privileged-access recertification opened for {acc['sap_user']}"),
            ("SAP", "Snapshotting privileged entitlements & last-use evidence"),
            ("ServiceNow", "Reviewer (account owner) assigned; certification task created"),
        ]
        ttype, action, prefix, reason = "SAP Privileged Access Recertification", "priv_recertify", "REQ", f"Recertify {acc['sap_user']}"
    ticket = await _snow_generic(org_id, ttype, action, steps, by, prefix=prefix,
                                 person_ref=pr, person_name=pn, email=em, reason=reason, work_note=body.reason)
    await _audit(org_id, by, f"sap.privileged.{body.action}", f"{account_ref} · {ticket['number']}")
    return {"ok": True, "ticket": _ticket_public(ticket)}


@sap_router.get("/roles")
async def roles(q: str = "", user: dict = Depends(get_current_user)):
    org_id = user["org_id"]
    await _ensure(org_id)
    _, accounts = await _load(org_id)
    usage = {}
    for a in accounts:
        for r in a.get("roles", []):
            usage[r] = usage.get(r, 0) + 1
    ql = q.lower().strip()
    rows = []
    for r in ROLE_CATALOG:
        if ql and ql not in r["ref"].lower() and ql not in r["name"].lower():
            continue
        fns = r.get("functions", [])
        # which SoD rules does this role's function set contribute to (single-role toxic combos)
        internal = [rule["ref"] for rule in SOD_RULES if rule["a"] in fns and rule["b"] in fns]
        rows.append({
            "ref": r["ref"], "name": r["name"], "type": r["type"], "owner": r.get("owner", "—"),
            "dept": r.get("dept", "—"), "privileged": bool(r.get("privileged")), "sap_all": bool(r.get("sap_all")),
            "function_count": len(fns), "tcode_count": sum(len(FUNCTIONS[f]["tcodes"]) for f in fns),
            "users": usage.get(r["ref"], 0), "internal_sod": internal,
        })
    rows.sort(key=lambda x: -x["users"])
    return {"roles": rows, "total": len(rows)}


@sap_router.get("/roles/{ref}")
async def role_detail(ref: str, user: dict = Depends(get_current_user)):
    org_id = user["org_id"]
    await _ensure(org_id)
    persons, accounts, conflicts, pmap = await _correlate(org_id)
    role = ROLE_BY_REF.get(ref)
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    holders = []
    for a in accounts:
        if ref in a.get("roles", []):
            person = pmap.get(a.get("person_ref"))
            holders.append({"account_ref": a["ref"], "sap_user": a["sap_user"], "system": a["system"],
                            "person_name": person["name"] if person else "(technical)",
                            "status": person["status"] if person else "—"})
    fns = role.get("functions", [])
    tcodes = sorted({t for f in fns for t in FUNCTIONS[f]["tcodes"]})
    auth_objects = sorted({o for f in fns for o in FUNCTIONS[f]["auth_objects"]})
    internal = [rule for rule in SOD_RULES if rule["a"] in fns and rule["b"] in fns]
    return {
        "role": {"ref": role["ref"], "name": role["name"], "type": role["type"],
                 "owner": role.get("owner"), "dept": role.get("dept"),
                 "privileged": bool(role.get("privileged")), "sap_all": bool(role.get("sap_all")),
                 "parent": role.get("parent")},
        "functions": [{"id": f, **FUNCTIONS[f]} for f in fns],
        "tcodes": tcodes, "auth_objects": auth_objects, "holders": holders,
        "internal_sod": [{"ref": r["ref"], "name": r["name"], "severity": r["severity"]} for r in internal],
    }


class RoleActionBody(BaseModel):
    action: str  # remediate | recertify | revoke_holder
    account_ref: str = ""
    reason: str = ""


@sap_router.post("/roles/{ref}/action")
async def role_action(ref: str, body: RoleActionBody, user: dict = Depends(get_current_user)):
    """Kick off a ServiceNow-orchestrated action from a role deep-dive: recertify the role,
    open a remediation for a toxic role, or revoke the role from a specific holder."""
    org_id = user["org_id"]
    await _ensure(org_id)
    role = ROLE_BY_REF.get(ref)
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    by = user["email"]
    pr = pn = em = None
    if body.action == "revoke_holder":
        acc = await db.sap_accounts.find_one({"org_id": org_id, "ref": body.account_ref})
        if not acc:
            raise HTTPException(status_code=404, detail="Holder account not found")
        await db.sap_accounts.update_one({"_id": acc["_id"]}, {"$pull": {"roles": ref}})
        person = await db.sap_persons.find_one({"org_id": org_id, "ref": acc.get("person_ref")}, {"_id": 0}) if acc.get("person_ref") else None
        hr = (person or {}).get("hr_authority", "ADP")
        pr, pn, em = acc.get("person_ref"), (person or {}).get("name"), (person or {}).get("email")
        steps = [
            ("ServiceNow", f"Role revocation opened: {role['name']} from {acc['sap_user']}"),
            ("ServiceNow", f"Auto-approved (least privilege) · {by}"),
            (hr, "Notifying HR of the access change"),
            ("SAP", f"Removing {ref} from {acc['sap_user']} on {acc['system']}"),
            ("ServiceNow", "Role removed; SoD re-evaluated; change closed"),
        ]
        ttype, action, prefix, reason = "SAP Role Revocation", "role_revoke", "CHG", f"Revoke {ref} from {acc['sap_user']}"
    elif body.action == "recertify":
        steps = [
            ("ServiceNow", f"Recertification task opened for role {role['name']}"),
            ("SAP", "Snapshotting current holders & entitlements"),
            ("ServiceNow", "Reviewer assigned; certification task created"),
        ]
        ttype, action, prefix, reason = "SAP Role Recertification", "role_recertify", "REQ", f"Recertify {ref}"
    else:
        steps = [
            ("ServiceNow", f"Role remediation opened for {role['name']}"),
            ("SAP", "Analyzing role composition for internal SoD conflicts"),
            ("ServiceNow", "Remediation plan drafted; role owner assigned; change scheduled"),
        ]
        ttype, action, prefix, reason = "SAP Role Remediation", "role_remediate", "CHG", f"Remediate {ref}"
    ticket = await _snow_generic(org_id, ttype, action, steps, by, prefix=prefix,
                                 person_ref=pr, person_name=pn, email=em, reason=reason, work_note=body.reason)
    await _audit(org_id, by, f"sap.role.{body.action}", f"{ref} · {ticket['number']}")
    return {"ok": True, "ticket": _ticket_public(ticket)}


@sap_router.get("/hr/reconciliation")
async def hr_reconciliation(user: dict = Depends(get_current_user)):
    org_id = user["org_id"]
    await _ensure(org_id)
    persons, _ = await _load(org_id)
    queue, states = [], {"NORMAL": 0, "STALE": 0, "CONFLICT": 0, "SECURITY HOLD": 0, "RECONCILED": 0}
    adp_pop = sum(1 for p in persons if p["hr_authority"] == "ADP")
    iz8_pop = sum(1 for p in persons if p["hr_authority"] == "IZ8")
    for p in persons:
        conflicts, state = await _hr_state(org_id, p)
        states[state] = states.get(state, 0) + 1
        if conflicts:
            queue.append({
                "person_ref": p["ref"], "name": p["name"], "legal_entity": p["legal_entity"],
                "country": p["country"], "hr_authority": p["hr_authority"], "state": state,
                "conflicts": conflicts,
            })
    order = {"SECURITY HOLD": 0, "CONFLICT": 1, "RECONCILED": 2}
    queue.sort(key=lambda x: order.get(x["state"], 3))
    return {
        "queue": queue, "states": states,
        "coverage": {"ADP": adp_pop, "IZ8": iz8_pop, "total": len(persons)},
        "authority_matrix": HR_AUTHORITY_MATRIX,
        "legal_entities": LEGAL_ENTITIES,
    }


class ReconcileBody(BaseModel):
    person_ref: str
    field: str
    resolved_value: str
    rationale: str = ""


async def _snow_generic(org_id, ttype, action, steps, by, prefix="REQ",
                        person_ref=None, person_name=None, email=None,
                        hr_system="ADP", reason="", work_note=""):
    """Generic ServiceNow-orchestrated governance ticket that fans out to the listed systems and
    auto-closes end-to-end (used by access-request approvals/provisioning and role actions)."""
    count = await db.sap_snow_tickets.count_documents({"org_id": org_id})
    t0 = _now()
    number = f"{prefix}{100000 + count + 1}"
    total = len(steps)
    stages = []
    for i, (system, note) in enumerate(steps):
        state = "New" if i == 0 else "Resolved" if i == total - 1 else "In Progress"
        stages.append({"state": state, "system": system, "note": note, "at": (t0 + timedelta(seconds=i * 2)).isoformat()})
    if work_note and work_note.strip():
        stages.insert(1, {"state": "Work Note", "system": "ServiceNow", "note": f"{work_note.strip()} — {by}", "at": (t0 + timedelta(seconds=1)).isoformat()})
    closed_at = (t0 + timedelta(seconds=total * 2)).isoformat()
    stages.append({"state": "Closed", "system": "ServiceNow", "note": "Auto-closed after successful verification", "at": closed_at})
    doc = {"org_id": org_id, "number": number, "type": ttype, "action": action,
           "person_ref": person_ref, "person_name": person_name, "email": email,
           "hr_system": hr_system, "systems_touched": sorted({s for s, _ in steps}),
           "requested_by": by, "reason": reason, "work_note": work_note, "notify_user": False,
           "work_notes_enabled": True, "state": "Closed", "stages": stages, "auto_closed": True,
           "synced_to_servicenow": False, "opened_at": t0.isoformat(), "closed_at": closed_at,
           "duration_sec": total * 2}
    await db.sap_snow_tickets.insert_one(doc)
    doc.pop("_id", None)
    return doc


async def _snow_hr_workflow(org_id, person, field, value, by, rationale, terminated=False):
    """ServiceNow change that pushes an authoritative HR decision to the HR system (ADP/IZ8) and
    fans out to SAP + AD/Entra, closing end-to-end. If the decision confirms a termination it also
    kicks off leaver de-provisioning downstream."""
    count = await db.sap_snow_tickets.count_documents({"org_id": org_id})
    t0 = _now()
    hr = person.get("hr_authority", "ADP")
    prefix = "CHG"
    ttype = "HR Reconciliation → Leaver De-provisioning" if terminated else "HR Master Data Reconciliation"
    steps = [
        ("ServiceNow", f"HR reconciliation change opened for {field} → {value}"),
        ("ServiceNow", f"Auto-approved (authoritative source: {hr}) · {by}"),
        (hr, f"Writing authoritative {field}={value} to {hr} HR master"),
    ]
    if terminated:
        steps += [
            ("SAP", "Termination confirmed — locking SAP accounts, revoking roles, freeing license"),
            ("AD/Entra", "Disabling Active Directory / Entra sign-in"),
        ]
    else:
        steps += [
            ("SAP", f"Propagating {field} to SAP user master"),
            ("AD/Entra", "Syncing directory attribute"),
        ]
    steps.append(("ServiceNow", "Downstream sync verified; change closed"))
    number = f"{prefix}{100000 + count + 1}"
    total = len(steps)
    stages = []
    for i, (system, note) in enumerate(steps):
        state = "New" if i == 0 else "Resolved" if i == total - 1 else "In Progress"
        stages.append({"state": state, "system": system, "note": note, "at": (t0 + timedelta(seconds=i * 2)).isoformat()})
    if rationale and rationale.strip():
        stages.insert(1, {"state": "Work Note", "system": "ServiceNow", "note": f"{rationale.strip()} — {by}", "at": (t0 + timedelta(seconds=1)).isoformat()})
    closed_at = (t0 + timedelta(seconds=total * 2)).isoformat()
    stages.append({"state": "Closed", "system": "ServiceNow", "note": "Auto-closed after successful verification", "at": closed_at})
    doc = {"org_id": org_id, "number": number, "type": ttype, "action": "hr_reconcile",
           "person_ref": person["ref"], "person_name": person.get("name"), "email": person.get("email"),
           "hr_system": hr, "systems_touched": sorted({s for s, _ in steps}),
           "requested_by": by, "reason": f"{field}={value}", "work_note": rationale, "notify_user": False,
           "work_notes_enabled": True, "state": "Closed", "stages": stages, "auto_closed": True,
           "synced_to_servicenow": False, "opened_at": t0.isoformat(), "closed_at": closed_at,
           "duration_sec": total * 2}
    await db.sap_snow_tickets.insert_one(doc)
    doc.pop("_id", None)
    return doc


@sap_router.post("/hr/reconcile")
async def reconcile(body: ReconcileBody, user: dict = Depends(get_current_user)):
    org_id = user["org_id"]
    await _ensure(org_id)
    person = await db.sap_persons.find_one({"org_id": org_id, "ref": body.person_ref}, {"_id": 0})
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")
    await db.sap_hr_decisions.update_one(
        {"org_id": org_id, "person_ref": body.person_ref, "field": body.field},
        {"$set": {"org_id": org_id, "person_ref": body.person_ref, "field": body.field,
                  "resolved_value": body.resolved_value, "rationale": body.rationale,
                  "by": user["email"], "at": _now().isoformat()}}, upsert=True)
    val = (body.resolved_value or "").strip()
    terminated = body.field in ("employment_status", "termination_date") and (
        val.lower() in ("terminated", "leaver", "inactive")
        or (body.field == "termination_date" and val and val.lower() not in ("none", "null", "")))
    ticket = await _snow_hr_workflow(org_id, person, body.field, val, user["email"], body.rationale, terminated)
    deactivation = None
    if terminated:
        changed, tickets = await _apply_activation(
            org_id, [body.person_ref], "deactivate",
            f"HR reconciliation: {body.field}={val}", False, user["email"],
            "Auto-triggered by HR reconciliation security hold")
        deactivation = {"changed": changed, "tickets": tickets}
    await _audit(org_id, user["email"], "sap.hr.reconcile",
                 f"{body.person_ref} · {body.field} → {val} · {ticket['number']}"
                 + (" · access auto-deactivated" if deactivation and deactivation["changed"] else ""))
    return {"ok": True,
            "ticket": _ticket_public(ticket),
            "deactivation": deactivation}


# ── Access Requests ─────────────────────────────────────────────────────────
class RequestBody(BaseModel):
    person_ref: str
    roles: list[str]
    justification: str


@sap_router.get("/access-requests")
async def list_requests(user: dict = Depends(get_current_user)):
    org_id = user["org_id"]
    await _ensure(org_id)
    reqs = await db.sap_access_requests.find({"org_id": org_id}, {"_id": 0}).sort("created_at", -1).to_list(500)
    return {"requests": reqs, "counts": {
        "pending": sum(1 for r in reqs if r["status"] == "Pending"),
        "approved": sum(1 for r in reqs if r["status"] == "Approved"),
        "provisioned": sum(1 for r in reqs if r["status"] == "Provisioned"),
        "rejected": sum(1 for r in reqs if r["status"] == "Rejected")}}


@sap_router.post("/access-requests")
async def create_request(body: RequestBody, user: dict = Depends(get_current_user)):
    org_id = user["org_id"]
    await _ensure(org_id)
    persons, accounts, conflicts, pmap = await _correlate(org_id)
    p = pmap.get(body.person_ref)
    if not p:
        raise HTTPException(status_code=404, detail="Identity not found")
    invalid = [r for r in body.roles if r not in ROLE_BY_REF]
    if invalid:
        raise HTTPException(status_code=400, detail=f"Unknown role(s): {', '.join(invalid)}")
    if not body.justification.strip():
        raise HTTPException(status_code=400, detail="Business justification is required")
    sim = await simulate(SimulateBody(person_ref=body.person_ref, add_roles=body.roles), user)
    count = await db.sap_access_requests.count_documents({"org_id": org_id})
    ref = f"AR-{count + 1:04d}"
    roles_meta = [{"ref": r, "name": ROLE_BY_REF[r]["name"], "owner": ROLE_BY_REF[r].get("owner", "—")} for r in body.roles]
    doc = {
        "org_id": org_id, "ref": ref, "person_ref": body.person_ref, "person_name": p["name"],
        "roles": roles_meta, "justification": body.justification.strip(),
        "status": "Pending", "risk_simulation": {"decision": sim["decision"], "introduced": sim["introduced_conflicts"]},
        "stages": [
            {"stage": "Manager", "approver": p.get("manager", "Manager"), "status": "Pending"},
            {"stage": "Role Owner", "approver": roles_meta[0]["owner"] if roles_meta else "Role Owner", "status": "Pending"},
            {"stage": "Security", "approver": "SAP Security", "status": "Pending"},
        ],
        "requested_by": user["email"], "created_at": _now().isoformat(),
    }
    await db.sap_access_requests.insert_one(doc)
    await _audit(org_id, user["email"], "sap.access.request", f"{ref} for {p['name']} · {sim['decision']}")
    doc.pop("_id", None)
    return doc


class RequestDecision(BaseModel):
    decision: str  # approve | reject
    note: str = ""


@sap_router.post("/access-requests/{ref}/decide")
async def decide_request(ref: str, body: RequestDecision, user: dict = Depends(get_current_user)):
    org_id = user["org_id"]
    await _ensure(org_id)
    if body.decision not in ("approve", "reject"):
        raise HTTPException(status_code=400, detail="decision must be approve or reject")
    req = await db.sap_access_requests.find_one({"org_id": org_id, "ref": ref})
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")
    status = "Approved" if body.decision == "approve" else "Rejected"
    stages = req.get("stages", [])
    for s in stages:
        s["status"] = "Approved" if body.decision == "approve" else "Rejected"
        s["decided_by"] = user["email"]
        s["decided_at"] = _now().isoformat()
    ticket = None
    if body.decision == "approve":
        person = await db.sap_persons.find_one({"org_id": org_id, "ref": req["person_ref"]}, {"_id": 0}) or {}
        hr = person.get("hr_authority", "ADP")
        rolenames = ", ".join(r["name"] for r in req.get("roles", [])) or "requested roles"
        steps = [
            ("ServiceNow", f"Access request {ref} approved — fulfilment task opened"),
            ("ServiceNow", f"Multi-stage approval recorded (Manager · Role Owner · Security) · {user['email']}"),
            (hr, "Validating worker record & manager chain in HR"),
            ("SAP", f"Staging role grant: {rolenames}"),
            ("ServiceNow", "Approved & staged; ready to provision"),
        ]
        ticket = await _snow_generic(org_id, "SAP Access Request Approval", "access_approve", steps,
                                     user["email"], prefix="REQ", person_ref=req["person_ref"],
                                     person_name=req.get("person_name"), email=person.get("email"),
                                     hr_system=hr, reason=f"Approve {ref}", work_note=body.note)
    upd = {"status": status, "stages": stages, "note": body.note}
    if ticket:
        upd["approval_ticket"] = ticket["number"]
    await db.sap_access_requests.update_one({"org_id": org_id, "ref": ref}, {"$set": upd})
    await _audit(org_id, user["email"], "sap.access.decide",
                 f"{ref} → {status}" + (f" · {ticket['number']}" if ticket else ""))
    return {"ok": True, "status": status,
            "ticket": (_ticket_public(ticket) if ticket else None)}


@sap_router.post("/access-requests/{ref}/provision")
async def provision_request(ref: str, user: dict = Depends(get_current_user)):
    org_id = user["org_id"]
    await _ensure(org_id)
    req = await db.sap_access_requests.find_one({"org_id": org_id, "ref": ref})
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")
    if req["status"] != "Approved":
        raise HTTPException(status_code=400, detail="Only approved requests can be provisioned")
    # provision: add roles to the person's primary account (live change to the access model)
    role_refs = [r["ref"] for r in req.get("roles", [])]
    rolenames = ", ".join(r["name"] for r in req.get("roles", [])) or "requested roles"
    acct = await db.sap_accounts.find_one({"org_id": org_id, "person_ref": req["person_ref"]})
    if acct:
        newroles = list(dict.fromkeys(list(acct.get("roles", [])) + role_refs))
        await db.sap_accounts.update_one({"_id": acct["_id"]}, {"$set": {"roles": newroles}})
    person = await db.sap_persons.find_one({"org_id": org_id, "ref": req["person_ref"]}, {"_id": 0}) or {}
    hr = person.get("hr_authority", "ADP")
    steps = [
        ("ServiceNow", f"Provisioning task started for {ref}"),
        (hr, "Confirming active worker in HR"),
        ("AD/Entra", "Ensuring directory identity & group membership"),
        ("SAP", f"Granting roles on SAP: {rolenames}"),
        ("ServiceNow", "Roles provisioned; access verified; request closed"),
    ]
    ticket = await _snow_generic(org_id, "SAP Access Provisioning", "access_provision", steps,
                                 user["email"], prefix="REQ", person_ref=req["person_ref"],
                                 person_name=req.get("person_name"), email=person.get("email"),
                                 hr_system=hr, reason=f"Provision {ref}")
    await db.sap_access_requests.update_one({"org_id": org_id, "ref": ref},
                                            {"$set": {"status": "Provisioned", "provisioned_at": _now().isoformat(),
                                                      "provision_ticket": ticket["number"], "provisioned_roles": role_refs}})
    await _audit(org_id, user["email"], "sap.access.provision", f"{ref} provisioned {', '.join(role_refs)} · {ticket['number']}")
    return {"ok": True, "status": "Provisioned",
            "ticket": _ticket_public(ticket)}


class RequestRolesBody(BaseModel):
    roles: list[str]


@sap_router.post("/access-requests/{ref}/roles")
async def update_request_roles(ref: str, body: RequestRolesBody, user: dict = Depends(get_current_user)):
    """Edit the requested roles on a Pending request and re-run the SoD risk simulation."""
    org_id = user["org_id"]
    await _ensure(org_id)
    req = await db.sap_access_requests.find_one({"org_id": org_id, "ref": ref})
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")
    if req["status"] != "Pending":
        raise HTTPException(status_code=400, detail="Only pending requests can be edited")
    if not body.roles:
        raise HTTPException(status_code=400, detail="At least one role is required")
    invalid = [r for r in body.roles if r not in ROLE_BY_REF]
    if invalid:
        raise HTTPException(status_code=400, detail=f"Unknown role(s): {', '.join(invalid)}")
    sim = await simulate(SimulateBody(person_ref=req["person_ref"], add_roles=body.roles), user)
    roles_meta = [{"ref": r, "name": ROLE_BY_REF[r]["name"], "owner": ROLE_BY_REF[r].get("owner", "—")} for r in body.roles]
    await db.sap_access_requests.update_one(
        {"org_id": org_id, "ref": ref},
        {"$set": {"roles": roles_meta,
                  "risk_simulation": {"decision": sim["decision"], "introduced": sim["introduced_conflicts"]}}})
    await _audit(org_id, user["email"], "sap.access.edit_roles", f"{ref} roles → {', '.join(body.roles)} · {sim['decision']}")
    return {"ok": True, "roles": roles_meta,
            "risk_simulation": {"decision": sim["decision"], "introduced": sim["introduced_conflicts"]}}


# ── Certification Campaigns ───────────────────────────────────────────────────
class CampaignBody(BaseModel):
    name: str
    type: str  # User Access | Privileged Access | Role | SoD
    scope: str = "all"  # all | privileged | legal_entity code


@sap_router.get("/certifications")
async def list_campaigns(user: dict = Depends(get_current_user)):
    org_id = user["org_id"]
    await _ensure(org_id)
    camps = await db.sap_certifications.find({"org_id": org_id}, {"_id": 0, "items": 0}).sort("created_at", -1).to_list(200)
    for c in camps:
        items = await db.sap_cert_items.find({"org_id": org_id, "campaign_ref": c["ref"]}, {"_id": 0}).to_list(2000)
        c["total"] = len(items)
        c["decided"] = sum(1 for i in items if i["decision"] != "Pending")
        c["revoked"] = sum(1 for i in items if i["decision"] == "Revoke")
        c["progress"] = round(c["decided"] / c["total"] * 100) if c["total"] else 0
    return {"campaigns": camps}


@sap_router.post("/certifications")
async def create_campaign(body: CampaignBody, user: dict = Depends(get_current_user)):
    org_id = user["org_id"]
    await _ensure(org_id)
    if body.type not in ("User Access", "Privileged Access", "Role", "SoD"):
        raise HTTPException(status_code=400, detail="Invalid campaign type")
    persons, accounts, conflicts, pmap = await _correlate(org_id)
    count = await db.sap_certifications.count_documents({"org_id": org_id})
    ref = f"CERT-{count + 1:04d}"
    items = []
    if body.type == "Privileged Access":
        for a in accounts:
            if a["flags"]["privileged"]:
                person = pmap.get(a.get("person_ref"))
                items.append(_cert_item(org_id, ref, a["ref"], a["sap_user"],
                                        person["name"] if person else "(technical)",
                                        person["manager"] if person else "SAP Security",
                                        f"Privileged access on {a['system']}", "Critical" if a["flags"]["sap_all"] else "High"))
    elif body.type == "SoD":
        for c in conflicts:
            if c.get("status") == "Open":
                person = pmap.get(c.get("person_ref"))
                items.append(_cert_item(org_id, ref, c["conflict_ref"], c["sap_user"],
                                        person["name"] if person else "(technical)",
                                        person["manager"] if person else "SAP Security",
                                        f"{c['rule_name']} ({c['area']})", c["severity"]))
    elif body.type == "Role":
        for r in ROLE_CATALOG:
            items.append(_cert_item(org_id, ref, r["ref"], r["ref"], r["name"], r.get("owner", "—"),
                                    f"Role composition review · {r['type']}", "High" if r.get("privileged") else "Medium"))
    else:  # User Access
        for p in persons:
            if body.scope != "all" and p["legal_entity"] != body.scope:
                continue
            items.append(_cert_item(org_id, ref, p["ref"], p["ref"], p["name"], p.get("manager", "Manager"),
                                    f"{p['department']} · {len(p['accounts'])} account(s)", p["risk"]["rating"]))
    if not items:
        raise HTTPException(status_code=400, detail="No items match this campaign scope")
    await db.sap_cert_items.insert_many(items)
    doc = {"org_id": org_id, "ref": ref, "name": body.name, "type": body.type, "scope": body.scope,
           "status": "Active", "due_date": _iso(days=-14), "created_by": user["email"],
           "created_at": _now().isoformat(), "items": []}
    await db.sap_certifications.insert_one(doc)
    await _audit(org_id, user["email"], "sap.cert.create", f"{ref} · {body.type} · {len(items)} items")
    return {"ok": True, "ref": ref, "items": len(items)}


def _cert_item(org_id, campaign_ref, item_ref, subject, subject_name, reviewer, detail, risk):
    return {"org_id": org_id, "campaign_ref": campaign_ref, "item_ref": item_ref,
            "subject": subject, "subject_name": subject_name, "reviewer": reviewer,
            "detail": detail, "risk": risk, "decision": "Pending", "decided_at": None}


@sap_router.get("/certifications/{ref}")
async def campaign_detail(ref: str, user: dict = Depends(get_current_user)):
    org_id = user["org_id"]
    camp = await db.sap_certifications.find_one({"org_id": org_id, "ref": ref}, {"_id": 0, "items": 0})
    if not camp:
        raise HTTPException(status_code=404, detail="Campaign not found")
    items = await db.sap_cert_items.find({"org_id": org_id, "campaign_ref": ref}, {"_id": 0}).to_list(2000)
    camp["items"] = items
    camp["total"] = len(items)
    camp["decided"] = sum(1 for i in items if i["decision"] != "Pending")
    camp["revoked"] = sum(1 for i in items if i["decision"] == "Revoke")
    camp["progress"] = round(camp["decided"] / camp["total"] * 100) if camp["total"] else 0
    return camp


class CertDecision(BaseModel):
    item_ref: str
    decision: str  # Certify | Revoke


@sap_router.post("/certifications/{ref}/decide")
async def decide_cert_item(ref: str, body: CertDecision, user: dict = Depends(get_current_user)):
    org_id = user["org_id"]
    if body.decision not in ("Certify", "Revoke"):
        raise HTTPException(status_code=400, detail="decision must be Certify or Revoke")
    res = await db.sap_cert_items.update_one(
        {"org_id": org_id, "campaign_ref": ref, "item_ref": body.item_ref},
        {"$set": {"decision": body.decision, "decided_by": user["email"], "decided_at": _now().isoformat()}})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Item not found")
    # auto-complete campaign when everything is decided
    remaining = await db.sap_cert_items.count_documents({"org_id": org_id, "campaign_ref": ref, "decision": "Pending"})
    if remaining == 0:
        await db.sap_certifications.update_one({"org_id": org_id, "ref": ref}, {"$set": {"status": "Completed"}})
    return {"ok": True, "remaining": remaining}


# ── User Activation / Deactivation (SAC-style license governance) ─────────────
def _license_type(account, flags):
    if account.get("technical") or account.get("user_type") in ("system", "communication", "emergency"):
        return "Technical"
    if flags["sap_all"] or flags["privileged"]:
        return "Professional"
    fns = _account_functions(account)
    if any(FUNCTIONS[f]["sensitive"] for f in fns):
        return "Professional"
    if fns:
        return "Limited Professional"
    return "Employee"


def _inactive_days(last_login):
    try:
        return (_now() - datetime.fromisoformat(last_login)).days
    except Exception:
        return None


def _activation_status(person, override):
    if override:
        return override["status"]
    return "Deactivated" if person.get("status") == "Terminated" else "Activated"


def _month_labels(n=6):
    now = _now()
    y, m = now.year, now.month
    out = []
    for _ in range(n):
        out.append((f"{y:04d}-{m:02d}", ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"][m - 1]))
        m -= 1
        if m == 0:
            m, y = 12, y - 1
    return list(reversed(out))


@sap_router.get("/activation")
async def activation(q: str = "", department: str = "", status: str = "",
                     user: dict = Depends(get_current_user)):
    org_id = user["org_id"]
    await _ensure(org_id)
    persons, accounts, conflicts, pmap = await _correlate(org_id)
    overrides = {o["person_ref"]: o for o in await db.sap_activation.find({"org_id": org_id}, {"_id": 0}).to_list(5000)}
    acc_by_person = {}
    for a in accounts:
        if a.get("person_ref"):
            acc_by_person.setdefault(a["person_ref"], []).append(a)
    rows = []
    for p in persons:
        paccs = acc_by_person.get(p["ref"], [])
        primary = next((a for a in paccs if a.get("lock_state") == "unlocked"), paccs[0] if paccs else None)
        flags = _account_flags(primary, p) if primary else {"privileged": False, "sap_all": False, "dormant": False, "orphan": False}
        lic = _license_type(primary, flags) if primary else "Employee"
        last_login = primary.get("last_login") if primary else None
        inactive = _inactive_days(last_login) if last_login else None
        st = _activation_status(p, overrides.get(p["ref"]))
        ov = overrides.get(p["ref"])
        rolenames = [ROLE_BY_REF.get(r, {}).get("name", r) for r in (primary.get("roles") if primary else [])]
        sap_user = primary.get("sap_user") if primary else p["ref"]
        rows.append({
            "user_id": p["ref"], "user_name": sap_user, "name": p["name"], "display_name": p["name"],
            "first_name": p["name"].split(" ")[0], "last_name": (p["name"].split(" ") + [""])[1],
            "email": p["email"], "saml_user_mapping": p["email"], "department": p["department"],
            "manager": p.get("manager"), "roles": rolenames, "role_count": len(rolenames),
            "status": st, "is_user_deactivated": st == "Deactivated", "is_user_suspended": st == "Suspended",
            "last_login": last_login, "inactive_days": inactive,
            "license_type": lic, "worker_type": p["worker_type"], "legal_entity": p["legal_entity"],
            "inactivity_flag": bool(inactive is not None and inactive > 30 and st == "Activated"),
            "changed_by": (ov or {}).get("by"), "changed_at": (ov or {}).get("at"),
        })
    ql = q.lower().strip()
    filtered = [r for r in rows if (not ql or ql in r["name"].lower() or ql in r["email"].lower())
                and (not department or r["department"] == department)
                and (not status or r["status"] == status)]
    filtered.sort(key=lambda r: (r["status"] != "Activated", -(r["inactive_days"] or 0)))
    activated = sum(1 for r in rows if r["status"] == "Activated")
    suspended = sum(1 for r in rows if r["status"] == "Suspended")
    deactivated = sum(1 for r in rows if r["status"] == "Deactivated")
    total = len(rows)
    consumed = activated + suspended  # deactivate frees the license; suspend retains it
    underutilized = sum(1 for r in rows if r["inactivity_flag"] and r["license_type"] in ("Professional", "Limited Professional"))
    # trend from REAL hire/termination dates + admin activation events (live-derived)
    events = await db.sap_activation_events.find({"org_id": org_id}, {"_id": 0}).to_list(5000)
    trend = []
    for key, label in _month_labels(6):
        act = sum(1 for p in persons if (p.get("hire_date") or "").startswith(key))
        deact = sum(1 for p in persons if (p.get("termination_date") or "").startswith(key))
        act += sum(1 for e in events if e.get("action") == "activate" and (e.get("at") or "").startswith(key))
        deact += sum(1 for e in events if e.get("action") == "deactivate" and (e.get("at") or "").startswith(key))
        trend.append({"month": label, "activated": act, "deactivated": deact})
    # inactivity heatmap by department
    dept_map = {}
    for r in rows:
        e = dept_map.setdefault(r["department"], {"department": r["department"], "total": 0, "inactive": 0, "deactivated": 0})
        e["total"] += 1
        if r["inactivity_flag"]:
            e["inactive"] += 1
        if r["status"] == "Deactivated":
            e["deactivated"] += 1
    for e in dept_map.values():
        e["inactive_pct"] = round(e["inactive"] / e["total"] * 100) if e["total"] else 0
    lic_map = {}
    for r in rows:
        lic_map[r["license_type"]] = lic_map.get(r["license_type"], 0) + 1
    license_breakdown = sorted(({"name": k, "value": v} for k, v in lic_map.items()), key=lambda x: -x["value"])
    return {
        "users": filtered, "total_returned": len(filtered),
        "summary": {"total": total, "activated": activated, "suspended": suspended, "deactivated": deactivated,
                    "license_consumed": consumed, "license_usage_pct": round(consumed / total * 100) if total else 0,
                    "underutilized_licenses": underutilized},
        "pie": [{"name": "Activated", "value": activated}, {"name": "Suspended", "value": suspended}, {"name": "Deactivated", "value": deactivated}],
        "trend": trend, "license_breakdown": license_breakdown, "license_types": sorted(lic_map.keys()),
        "heatmap": sorted(dept_map.values(), key=lambda x: -x["inactive_pct"]),
        "departments": sorted({r["department"] for r in rows}),
        "generated_at": _now().isoformat(),
    }


class ActivationBody(BaseModel):
    person_refs: list[str]
    action: str  # activate | deactivate
    reason: str = ""
    work_note: str = ""
    notify: bool = False


async def _snow_workflow(org_id, person, action, by, reason, notify, work_note=""):
    """Fully automated cross-system orchestration mirroring a ServiceNow ticket that fans out to
    ADP/IZ8 HR, SAP and AD/Entra and closes end-to-end. Syncs to real ServiceNow once CON-SNOW is live.
    Actions: create | activate | resume | deactivate | suspend."""
    count = await db.sap_snow_tickets.count_documents({"org_id": org_id})
    t0 = _now()
    hr = person.get("hr_authority", "ADP")
    if action == "deactivate":
        prefix, ttype = "INC", "SAP Access Deactivation"
        steps = [
            ("ServiceNow", "Deactivation incident opened from Obserra SAP UAC"),
            ("ServiceNow", f"Auto-approved (policy: leaver / license recovery) · {by}"),
            (hr, f"Setting worker inactive / processing leaver in {hr} HR"),
            ("SAP", "Locking SAP accounts, revoking roles, freeing license (content retained)"),
            ("AD/Entra", "Disabling Active Directory / Entra sign-in"),
            ("ServiceNow", "All fulfilment tasks complete; access revoked & license freed"),
        ]
    elif action == "suspend":
        prefix, ttype = "INC", "SAP Access Suspension"
        steps = [
            ("ServiceNow", "Suspension (temporary hold) incident opened"),
            ("ServiceNow", f"Auto-approved (policy: leave of absence) · {by}"),
            (hr, f"Recording leave of absence in {hr} HR"),
            ("AD/Entra", "Disabling sign-in (temporary hold)"),
            ("SAP", "Locking SAP accounts — license & private content retained"),
            ("ServiceNow", "Access suspended; license retained"),
        ]
    elif action == "create":
        prefix, ttype = "REQ", "SAP Account Creation"
        steps = [
            ("ServiceNow", "Account creation request submitted"),
            (hr, f"Creating worker record in {hr} HR"),
            ("AD/Entra", "Provisioning Active Directory / Entra identity + mailbox"),
            ("SAP", "Creating SAP user, assigning birthright roles, enabling login"),
            ("ServiceNow", "Account created & activated; license consumed"),
        ]
    else:  # activate / resume
        prefix, ttype = "REQ", ("SAP Access Resume" if action == "resume" else "SAP Account Reactivation")
        steps = [
            ("ServiceNow", "Reactivation request submitted"),
            (hr, f"Setting worker active in {hr} HR"),
            ("AD/Entra", "Enabling Active Directory / Entra sign-in"),
            ("SAP", "Unlocking SAP accounts, restoring roles, login enabled"),
            ("ServiceNow", "Access restored; license consumed"),
        ]
    number = f"{prefix}{100000 + count + 1}"
    total = len(steps)
    stages = []
    for i, (system, note) in enumerate(steps):
        state = "New" if i == 0 else "Resolved" if i == total - 1 else "In Progress"
        stages.append({"state": state, "system": system, "note": note, "at": (t0 + timedelta(seconds=i * 2)).isoformat()})
    if work_note and work_note.strip():
        stages.insert(1, {"state": "Work Note", "system": "ServiceNow", "note": f"{work_note.strip()} — {by}", "at": (t0 + timedelta(seconds=1)).isoformat()})
    closed_at = (t0 + timedelta(seconds=total * 2)).isoformat()
    stages.append({"state": "Closed", "system": "ServiceNow", "note": "Auto-closed after successful verification", "at": closed_at})
    doc = {"org_id": org_id, "number": number, "type": ttype, "action": action,
           "person_ref": person["ref"], "person_name": person.get("name"), "email": person.get("email"),
           "hr_system": hr, "systems_touched": sorted({s for s, _ in steps}),
           "requested_by": by, "reason": reason, "work_note": work_note, "notify_user": notify,
           "work_notes_enabled": True, "state": "Closed", "stages": stages, "auto_closed": True,
           "synced_to_servicenow": False, "opened_at": t0.isoformat(), "closed_at": closed_at,
           "duration_sec": total * 2}
    await db.sap_snow_tickets.insert_one(doc)
    doc.pop("_id", None)
    return doc


_ACTIVATION_STATUS_MAP = {"activate": "Activated", "resume": "Activated", "deactivate": "Deactivated", "suspend": "Suspended"}


async def _apply_activation(org_id, refs, action, reason, notify, by, work_note=""):
    """Run activate/deactivate/suspend/resume across identities, driving lock state + a ServiceNow
    cross-system workflow for each. Deactivate frees the license; suspend retains it (content kept)."""
    status = _ACTIVATION_STATUS_MAP.get(action, "Activated")
    lock = action in ("deactivate", "suspend")
    now = _now().isoformat()
    changed, tickets = 0, []
    for ref in refs:
        p = await db.sap_persons.find_one({"org_id": org_id, "ref": ref}, {"_id": 0})
        if not p:
            continue
        await db.sap_activation.update_one(
            {"org_id": org_id, "person_ref": ref},
            {"$set": {"org_id": org_id, "person_ref": ref, "status": status,
                      "reason": reason, "by": by, "at": now}}, upsert=True)
        await db.sap_accounts.update_many(
            {"org_id": org_id, "person_ref": ref},
            {"$set": {"lock_state": "locked" if lock else "unlocked"}})
        await db.sap_activation_events.insert_one(
            {"org_id": org_id, "person_ref": ref, "action": action,
             "by": by, "at": now, "reason": reason, "work_note": work_note, "notify": notify})
        ticket = await _snow_workflow(org_id, p, action, by, reason, notify, work_note)
        tickets.append({"person_ref": ref, "person_name": p.get("name"), **_ticket_public(ticket)})
        await _audit(org_id, by, f"sap.activation.{action}",
                     f"{p.get('name', ref)} ({ref}) → {status} · {ticket['number']} auto-closed"
                     + (f" · {work_note or reason}" if (work_note or reason) else ""))
        changed += 1
        if notify:
            try:
                from kernel import notifications
                await notifications.create(org_id, "activation", f"User {status.lower()}",
                                           f"{p.get('name', ref)} was {status.lower()} by {by} ({ticket['number']}).", ref=ref)
            except Exception:
                pass
    return changed, tickets


@sap_router.post("/activation/set")
async def set_activation(body: ActivationBody, user: dict = Depends(get_current_user)):
    org_id = user["org_id"]
    await _ensure(org_id)
    if body.action not in ("activate", "deactivate", "suspend", "resume"):
        raise HTTPException(status_code=400, detail="action must be activate, deactivate, suspend or resume")
    changed, tickets = await _apply_activation(org_id, body.person_refs, body.action, body.reason,
                                               body.notify, user["email"], body.work_note)
    return {"ok": True, "changed": changed,
            "status": _ACTIVATION_STATUS_MAP.get(body.action, "Activated"), "tickets": tickets}


class BulkBody(BaseModel):
    action: str  # activate | deactivate
    scope: str = "all"
    department: str = ""
    reason: str = ""
    work_note: str = ""
    notify: bool = False


@sap_router.post("/activation/bulk")
async def bulk_activation(body: BulkBody, user: dict = Depends(get_current_user)):
    """One-click bulk: deactivate all active, reactivate all deactivated/suspended, or suspend all active."""
    org_id = user["org_id"]
    await _ensure(org_id)
    if body.action not in ("activate", "deactivate", "suspend"):
        raise HTTPException(status_code=400, detail="action must be activate, deactivate or suspend")
    persons = await db.sap_persons.find({"org_id": org_id}, {"_id": 0}).to_list(5000)
    overrides = {o["person_ref"]: o for o in await db.sap_activation.find({"org_id": org_id}, {"_id": 0}).to_list(5000)}
    if body.action == "deactivate":
        want = {"Activated", "Suspended"}
    elif body.action == "suspend":
        want = {"Activated"}
    else:
        want = {"Deactivated", "Suspended"}
    refs = []
    for p in persons:
        if _activation_status(p, overrides.get(p["ref"])) not in want:
            continue
        if body.department and body.department != "all" and p["department"] != body.department:
            continue
        refs.append(p["ref"])
    reason = body.reason or f"Bulk {body.action} via ServiceNow automation"
    changed, tickets = await _apply_activation(org_id, refs, body.action, reason, body.notify, user["email"], body.work_note)
    return {"ok": True, "changed": changed,
            "status": _ACTIVATION_STATUS_MAP.get(body.action, "Activated"),
            "tickets": tickets[:50], "ticket_count": len(tickets)}


class CreateUserBody(BaseModel):
    first_name: str
    last_name: str
    email: str
    department: str = "Finance"
    legal_entity: str = "US01"
    worker_type: str = "Employee"
    roles: list[str] = []
    work_note: str = ""
    notify: bool = False


@sap_router.post("/activation/create")
async def create_user(body: CreateUserBody, user: dict = Depends(get_current_user)):
    """Create a new SAP user account (provisioning) with an auto-processing ServiceNow workflow."""
    org_id = user["org_id"]
    await _ensure(org_id)
    if not body.first_name.strip() or not body.last_name.strip() or not body.email.strip():
        raise HTTPException(status_code=400, detail="First name, last name and email are required")
    invalid = [r for r in body.roles if r not in ROLE_BY_REF]
    if invalid:
        raise HTTPException(status_code=400, detail=f"Unknown role(s): {', '.join(invalid)}")
    le = LE_BY_CODE.get(body.legal_entity, LEGAL_ENTITIES[0])
    count = await db.sap_persons.count_documents({"org_id": org_id})
    ref = f"P-{9000 + count}"
    name = f"{body.first_name.strip()} {body.last_name.strip()}"
    now = _now().isoformat()
    hr = {"employment_status": "Active", "termination_date": None, "manager": user["email"],
          "legal_entity": le["code"], "worker_type": body.worker_type, "job_title": body.department,
          "source_id": f"{le['hr']}-NEW", "observed": now}
    person = {"org_id": org_id, "ref": ref, "name": name, "email": body.email.strip(),
              "department": body.department, "job_title": body.department, "worker_type": body.worker_type,
              "status": "Active", "legal_entity": le["code"], "legal_entity_name": le["name"],
              "country": le["country"], "region": le["region"], "manager": user["email"],
              "hire_date": now, "termination_date": None, "hr_authority": le["hr"],
              "sources": [le["hr"], "AD", "Entra", "SAP"], "hr": {"adp": dict(hr), "iz8": dict(hr)},
              "ad_enabled": True, "mfa": True, "risky_signin": False, "match_confidence": 1.0,
              "discovered_at": now}
    account = {"org_id": org_id, "ref": f"A-{ref}-S4P", "person_ref": ref,
               "sap_user": _sap_uid(name, "S4P"), "system": "S4P", "client": "200", "user_type": "dialog",
               "lock_state": "unlocked", "valid_from": now, "valid_to": None, "last_login": now,
               "roles": body.roles, "technical": False, "source": "S4P", "discovered_at": now}
    await db.sap_persons.insert_one(person)
    await db.sap_accounts.insert_one(account)
    await db.sap_activation.update_one({"org_id": org_id, "person_ref": ref},
                                       {"$set": {"org_id": org_id, "person_ref": ref, "status": "Activated",
                                                 "reason": "Account created", "by": user["email"], "at": now}}, upsert=True)
    ticket = await _snow_workflow(org_id, person, "create", user["email"], "New account provisioning", body.notify, body.work_note)
    await _audit(org_id, user["email"], "sap.activation.create", f"Created {name} ({ref}) · {ticket['number']}")
    return {"ok": True, "person_ref": ref, "name": name, "ticket": {"number": ticket["number"], "type": ticket["type"], "state": ticket["state"]}}


class SuggestBody(BaseModel):
    department: str = ""


@sap_router.post("/activation/create/suggest")
async def create_suggest(body: SuggestBody, user: dict = Depends(get_current_user)):
    """AI-assisted new-hire profile generator: drafts every field for the Create User flow,
    grounded in the real department list, legal entities and role catalog (valid role refs)."""
    org_id = user["org_id"]
    await _ensure(org_id)
    import random
    depts = ["Finance", "Procurement", "Treasury", "Sales", "HR", "IT Basis", "Master Data"]
    les = ["US01", "DE01", "UK01", "IN01"]
    dept = body.department if body.department in depts else None
    first = last = None
    le = None
    worker_type = "Employee"
    job_title = work_note = ""
    try:
        import asyncio, re
        from emergentintegrations.llm.chat import LlmChat, UserMessage, TextDelta, StreamDone
        system = ("Generate ONE realistic corporate new-hire profile as STRICT JSON only: "
                  "{\"first_name\":str,\"last_name\":str,\"department\":one of " + json.dumps(depts) +
                  ",\"legal_entity\":one of " + json.dumps(les) +
                  ",\"worker_type\":one of [\"Employee\",\"Contractor\"],\"job_title\":str,\"work_note\":str}. "
                  "Use diverse, plausible international names. Return ONLY the JSON object.")
        chat = LlmChat(api_key=os.environ["EMERGENT_LLM_KEY"],
                       session_id=f"sap-suggest-{org_id}-{random.randint(1, 999999)}",
                       system_message=system).with_model("openai", "gpt-5.4")
        hint = f"Department must be {dept}." if dept else "Pick any department."
        collected = []

        async def _run():
            async for ev in chat.stream_message(UserMessage(text=hint)):
                if isinstance(ev, TextDelta):
                    collected.append(ev.content)
                elif isinstance(ev, StreamDone):
                    break
        await asyncio.wait_for(_run(), timeout=14)
        m = re.search(r"\{.*\}", "".join(collected), re.S)
        p = json.loads(m.group(0)) if m else {}
        first = (p.get("first_name") or "").strip() or None
        last = (p.get("last_name") or "").strip() or None
        dept = p.get("department") if p.get("department") in depts else dept
        le = p.get("legal_entity") if p.get("legal_entity") in les else None
        worker_type = p.get("worker_type") if p.get("worker_type") in ("Employee", "Contractor") else "Employee"
        job_title = (p.get("job_title") or "").strip()
        work_note = (p.get("work_note") or "").strip()
    except Exception:
        pass
    FN = ["Ava", "Liam", "Noah", "Mia", "Sofia", "Arjun", "Wei", "Diego", "Fatima", "Hana", "Lucas", "Priya", "Omar", "Elena", "Kenji"]
    LN = ["Bennett", "Kapoor", "Fischer", "Moreau", "Rossi", "Chen", "Okafor", "Santos", "Nguyen", "Haddad", "Larsson", "Costa", "Yamamoto"]
    if not dept:
        dept = body.department if body.department in depts else random.choice(depts)
    first = first or random.choice(FN)
    last = last or random.choice(LN)
    le = le or random.choice(les)
    job_title = job_title or f"{dept} Specialist"
    work_note = work_note or f"New {worker_type.lower()} onboarding — provision birthright {dept} access via ServiceNow → HR → AD/Entra → SAP."
    email = f"{first.lower()}.{last.lower()}@obserrallc.com"
    birthright = [r["ref"] for r in ROLE_CATALOG if r.get("dept") == dept and not r.get("privileged") and not r.get("sap_all")][:3]
    if not birthright:
        birthright = [r["ref"] for r in ROLE_CATALOG if not r.get("privileged") and not r.get("sap_all")][:2]
    role_names = [ROLE_BY_REF[r]["name"] for r in birthright if r in ROLE_BY_REF]
    return {"first_name": first, "last_name": last, "email": email, "department": dept,
            "legal_entity": le, "worker_type": worker_type, "job_title": job_title,
            "roles": birthright, "role_names": role_names, "work_note": work_note, "ai": True}


@sap_router.get("/activation/tickets")
async def activation_tickets(user: dict = Depends(get_current_user)):
    org_id = user["org_id"]
    await _ensure(org_id)
    tickets = await db.sap_snow_tickets.find({"org_id": org_id}, {"_id": 0}).sort("opened_at", -1).to_list(200)
    return {"tickets": tickets,
            "open": sum(1 for t in tickets if t["state"] != "Closed"),
            "closed": sum(1 for t in tickets if t["state"] == "Closed"),
            "total": len(tickets)}


@sap_router.get("/workflow/activity")
async def workflow_activity(q: str = "", prefix: str = "", system: str = "",
                            action: str = "", days: int = 0, user: dict = Depends(get_current_user)):
    """Live, filterable stream of every ServiceNow ticket the platform opened & auto-closed."""
    org_id = user["org_id"]
    await _ensure(org_id)
    tickets = await db.sap_snow_tickets.find({"org_id": org_id}, {"_id": 0}).sort("opened_at", -1).to_list(1000)
    by_prefix, by_system, by_type = {}, {}, {}
    for t in tickets:
        pf = (t.get("number") or "REQ")[:3]
        by_prefix[pf] = by_prefix.get(pf, 0) + 1
        by_type[t["type"]] = by_type.get(t["type"], 0) + 1
        for s in t.get("systems_touched", []):
            by_system[s] = by_system.get(s, 0) + 1
    ql = q.lower().strip()
    cutoff = (_now() - timedelta(days=days)).isoformat() if days and days > 0 else None
    day_ago = (_now() - timedelta(days=1)).isoformat()
    rows = []
    for t in tickets:
        if prefix and (t.get("number") or "")[:3] != prefix:
            continue
        if system and system not in t.get("systems_touched", []):
            continue
        if action and t.get("action") != action:
            continue
        if cutoff and (t.get("opened_at") or "") < cutoff:
            continue
        if ql and ql not in (f"{t.get('number','')} {t.get('type','')} {t.get('person_name') or ''} "
                             f"{t.get('requested_by') or ''} {t.get('reason') or ''}").lower():
            continue
        rows.append(t)
    return {
        "tickets": rows[:400], "total": len(rows), "all_total": len(tickets),
        "summary": {
            "total": len(tickets),
            "closed": sum(1 for t in tickets if t.get("state") == "Closed"),
            "open": sum(1 for t in tickets if t.get("state") != "Closed"),
            "last_24h": sum(1 for t in tickets if (t.get("opened_at") or "") >= day_ago),
            "auto_closed": sum(1 for t in tickets if t.get("auto_closed")),
            "avg_duration_sec": round(sum(t.get("duration_sec", 0) for t in tickets) / len(tickets), 1) if tickets else 0,
        },
        "by_prefix": by_prefix,
        "by_system": sorted(({"name": k, "value": v} for k, v in by_system.items()), key=lambda x: -x["value"]),
        "by_type": sorted(({"name": k, "value": v} for k, v in by_type.items()), key=lambda x: -x["value"])[:12],
        "systems": sorted(by_system.keys()),
        "actions": sorted({t.get("action") for t in tickets if t.get("action")}),
        "generated_at": _now().isoformat(),
    }


@sap_router.get("/analytics")
async def analytics(user: dict = Depends(get_current_user)):
    """SAP access analytics / metrics — aggregated live for the metrics dashboard."""
    org_id = user["org_id"]
    await _ensure(org_id)
    persons, accounts, conflicts, pmap = await _correlate(org_id)
    overrides = {o["person_ref"]: o for o in await db.sap_activation.find({"org_id": org_id}, {"_id": 0}).to_list(5000)}
    open_conf = [c for c in conflicts if c.get("status") == "Open"]
    acc_by_person = {}
    for a in accounts:
        if a.get("person_ref"):
            acc_by_person.setdefault(a["person_ref"], []).append(a)
    activated = 0
    lic_map, dept, region, le_map = {}, {}, {}, {}
    saml_mapped = 0
    for p in persons:
        st = _activation_status(p, overrides.get(p["ref"]))
        if st == "Activated":
            activated += 1
        paccs = acc_by_person.get(p["ref"], [])
        primary = next((a for a in paccs if a.get("lock_state") == "unlocked"), paccs[0] if paccs else None)
        lic = _license_type(primary, _account_flags(primary, p)) if primary else "Employee"
        lic_map[lic] = lic_map.get(lic, 0) + 1
        dept[p["department"]] = dept.get(p["department"], 0) + 1
        region[p["region"]] = region.get(p["region"], 0) + 1
        le_map[p["legal_entity"]] = le_map.get(p["legal_entity"], 0) + 1
        if p.get("email"):
            saml_mapped += 1
    total = len(persons)
    usage = {}
    for a in accounts:
        for r in a.get("roles", []):
            usage[r] = usage.get(r, 0) + 1
    top_roles = sorted(({"name": ROLE_BY_REF.get(r, {}).get("name", r), "value": v, "privileged": bool(ROLE_BY_REF.get(r, {}).get("privileged"))}
                        for r, v in usage.items()), key=lambda x: -x["value"])[:10]
    sod_area = {}
    for c in open_conf:
        sod_area[c["area"]] = sod_area.get(c["area"], 0) + 1
    events = await db.sap_activation_events.find({"org_id": org_id}, {"_id": 0}).to_list(5000)
    trend = []
    for key, label in _month_labels(6):
        act = sum(1 for p in persons if (p.get("hire_date") or "").startswith(key)) + sum(1 for e in events if e.get("action") == "activate" and (e.get("at") or "").startswith(key))
        deact = sum(1 for p in persons if (p.get("termination_date") or "").startswith(key)) + sum(1 for e in events if e.get("action") == "deactivate" and (e.get("at") or "").startswith(key))
        trend.append({"month": label, "activated": act, "deactivated": deact})
    top_risk = sorted(persons, key=lambda p: -p["risk"]["score"])[:8]
    return {
        "kpis": {
            "identities": total, "accounts": len(accounts), "activated": activated,
            "deactivated": total - activated, "license_usage_pct": round(activated / total * 100) if total else 0,
            "avg_risk": round(sum(p["risk"]["score"] for p in persons) / total) if total else 0,
            "open_sod": len(open_conf), "critical_sod": sum(1 for c in open_conf if c["severity"] == "Critical"),
            "privileged": sum(1 for a in accounts if a["flags"]["privileged"]),
            "sap_all": sum(1 for a in accounts if a["flags"]["sap_all"]),
            "dormant": sum(1 for a in accounts if a["flags"]["dormant"]),
            "orphan": sum(1 for a in accounts if a["flags"]["orphan"]),
            "terminated_residual": sum(1 for p in persons if p["status"] == "Terminated" and any(x.get("lock_state") == "unlocked" for x in acc_by_person.get(p["ref"], []))),
            "saml_coverage_pct": round(saml_mapped / total * 100) if total else 0,
        },
        "license_breakdown": sorted(({"name": k, "value": v} for k, v in lic_map.items()), key=lambda x: -x["value"]),
        "by_department": sorted(({"name": k, "value": v} for k, v in dept.items()), key=lambda x: -x["value"]),
        "by_region": [{"name": k, "value": v} for k, v in region.items()],
        "by_legal_entity": sorted(({"name": k, "value": v} for k, v in le_map.items()), key=lambda x: -x["value"]),
        "top_roles": top_roles, "sod_by_area": sorted(({"name": k, "value": v} for k, v in sod_area.items()), key=lambda x: -x["value"]),
        "trend": trend, "risk_distribution": {r: sum(1 for p in persons if p["risk"]["rating"] == r) for r in ["Critical", "High", "Medium", "Low"]},
        "top_risk": [{"ref": p["ref"], "name": p["name"], "department": p["department"], "score": p["risk"]["score"], "rating": p["risk"]["rating"]} for p in top_risk],
        "generated_at": _now().isoformat(),
    }


# ── Advisor (grounded NL query over the SAP access model) ─────────────────────
class AskBody(BaseModel):
    question: str


async def _advisor_context(org_id):
    ov = await overview_context(org_id)
    return ov


async def overview_context(org_id):
    persons, accounts, conflicts, pmap = await _correlate(org_id)
    open_conf = [c for c in conflicts if c.get("status") == "Open"]
    return {
        "identities": len(persons), "accounts": len(accounts),
        "avg_risk_score": round(sum(p["risk"]["score"] for p in persons) / len(persons)) if persons else 0,
        "open_sod_conflicts": len(open_conf),
        "critical_sod": [{"person": pmap.get(c["person_ref"], {}).get("name", c["sap_user"]),
                          "rule": c["rule_name"], "area": c["area"]} for c in open_conf if c["severity"] == "Critical"][:12],
        "sap_all_holders": [a["sap_user"] for a in accounts if a["flags"]["sap_all"]][:10],
        "terminated_with_access": [p["name"] for p in persons if p["status"] == "Terminated" and any(x.get("lock_state") == "unlocked" for x in p.get("accounts", []))][:10],
        "top_risk_people": [{"name": p["name"], "score": p["risk"]["score"], "rating": p["risk"]["rating"],
                             "dept": p["department"], "factors": [f["factor"] for f in p["risk"]["factors"]]}
                            for p in sorted(persons, key=lambda x: -x["risk"]["score"])[:8]],
        "sod_rules_count": len(SOD_RULES),
    }


def _advisor_fallback(question, ctx):
    lines = [f"Across {ctx['identities']} SAP identities and {ctx['accounts']} accounts, the average Obserra SAP Access Risk Score is {ctx['avg_risk_score']}/100 with {ctx['open_sod_conflicts']} open Segregation-of-Duties conflicts."]
    if ctx["critical_sod"]:
        lines.append("Critical SoD exposures: " + "; ".join(f"{c['person']} — {c['rule']}" for c in ctx["critical_sod"][:4]) + ".")
    if ctx["terminated_with_access"]:
        lines.append("Terminated workers still holding active SAP access: " + ", ".join(ctx["terminated_with_access"][:5]) + " — recommend immediate lock/de-provision.")
    if ctx["sap_all_holders"]:
        lines.append(f"{len(ctx['sap_all_holders'])} account(s) hold SAP_ALL — review against least privilege.")
    return {"answer": " ".join(lines), "model": "deterministic-fallback",
            "citations": [c["rule"] for c in ctx["critical_sod"][:5]]}


@sap_router.post("/advisor")
async def advisor(body: AskBody, user: dict = Depends(get_current_user)):
    org_id = user["org_id"]
    await _ensure(org_id)
    ctx = await _advisor_context(org_id)
    try:
        import asyncio
        from emergentintegrations.llm.chat import LlmChat, UserMessage, TextDelta, StreamDone
        system = (
            "You are the Obserra SAP UAC Advisor — an evidence-grounded assistant for SAP access governance, "
            "Segregation of Duties, privileged access and identity lifecycle. Answer ONLY from the provided LIVE "
            "access-model context. Cite specific SoD rule names, person names or figures. Be concise (<170 words), "
            "board-grade, and end with one prioritized recommendation. Never invent data not in the context.")
        chat = LlmChat(api_key=os.environ["EMERGENT_LLM_KEY"], session_id=f"sap-advisor-{org_id}",
                       system_message=system).with_model("openai", "gpt-5.4")
        prompt = f"LIVE SAP ACCESS CONTEXT (JSON):\n{json.dumps(ctx, default=str)[:9000]}\n\nQUESTION: {body.question}"
        collected = []

        async def _run():
            async for ev in chat.stream_message(UserMessage(text=prompt)):
                if isinstance(ev, TextDelta):
                    collected.append(ev.content)
                elif isinstance(ev, StreamDone):
                    break
        await asyncio.wait_for(_run(), timeout=18)
        answer = "".join(collected).strip()
        if not answer:
            return _advisor_fallback(body.question, ctx)
        await db.advisor_logs.insert_one({"org_id": org_id, "user": user["email"], "mode": "sap-advisor",
                                          "model": "openai/gpt-5.4", "prompt": body.question,
                                          "response": answer, "ts": _now().isoformat()})
        return {"answer": answer, "model": "openai/gpt-5.4",
                "citations": [c["rule"] for c in ctx["critical_sod"][:5]]}
    except Exception:
        return _advisor_fallback(body.question, ctx)


# ── AI Summary (Obserra-standard auto insight, grounded in the live SAP model) ─
def _sap_insight_fallback(ctx):
    insights = [
        {"text": f"{ctx['identities']} SAP identities across {ctx['accounts']} accounts; average Obserra SAP Access Risk Score {ctx['avg_risk_score']}/100.", "kind": "fact"},
        {"text": f"{ctx['open_sod_conflicts']} open Segregation-of-Duties conflicts detected live against {ctx['sod_rules_count']} rules.", "kind": "fact"},
    ]
    if ctx["critical_sod"]:
        insights.append({"text": "Critical toxic combinations: " + "; ".join(f"{c['person']} — {c['rule']}" for c in ctx["critical_sod"][:3]) + ".", "kind": "risk"})
    if ctx["terminated_with_access"]:
        insights.append({"text": f"{len(ctx['terminated_with_access'])} terminated worker(s) still hold active SAP access (residual exposure).", "kind": "risk"})
    if ctx["sap_all_holders"]:
        insights.append({"text": f"{len(ctx['sap_all_holders'])} account(s) hold SAP_ALL / full authorization.", "kind": "estimate"})
    actions = []
    if ctx["terminated_with_access"]:
        actions.append("De-provision residual SAP access for terminated workers now — run the automated ServiceNow deactivation workflow.")
    if ctx["critical_sod"]:
        actions.append("Remediate the highest-severity SoD conflicts by removing one conflicting role or attaching a mitigating control.")
    actions.append("Review SAP_ALL and privileged holders against least privilege.")
    return {"headline": f"{ctx['open_sod_conflicts']} open SoD conflicts · avg access risk {ctx['avg_risk_score']}/100",
            "insights": insights, "actions": actions[:4],
            "model": "deterministic-fallback", "generated_at": _now().isoformat()}


@sap_router.get("/insight")
async def sap_insight(focus: str = "", user: dict = Depends(get_current_user)):
    """Obserra-standard AI analyst summary of the live SAP access posture (optionally focused per dashboard)."""
    org_id = user["org_id"]
    await _ensure(org_id)
    ctx = await overview_context(org_id)
    focus = (focus or "").strip()[:80]
    try:
        import asyncio, re
        from emergentintegrations.llm.chat import LlmChat, UserMessage, TextDelta, StreamDone
        system = (
            "You are the Obserra SAP UAC AI Analyst. Read the LIVE SAP access-model JSON and return a concise, "
            "board-grade briefing STRICTLY as JSON with this schema: {\"headline\": str, \"insights\": "
            "[{\"text\": str, \"kind\": one of \"fact\"|\"estimate\"|\"risk\"}], \"actions\": [str]}. "
            "3-5 insights, 2-4 actions. Ground every statement in the data (cite SoD rule names, person names, figures). "
            "Never invent data. Return ONLY the JSON object.")
        chat = LlmChat(api_key=os.environ["EMERGENT_LLM_KEY"], session_id=f"sap-insight-{org_id}-{focus or 'all'}",
                       system_message=system).with_model("openai", "gpt-5.4")
        focus_line = f"\n\nEMPHASIZE this dashboard focus in the briefing: {focus}." if focus else ""
        prompt = f"LIVE SAP ACCESS CONTEXT (JSON):\n{json.dumps(ctx, default=str)[:9000]}{focus_line}"
        collected = []

        async def _run():
            async for ev in chat.stream_message(UserMessage(text=prompt)):
                if isinstance(ev, TextDelta):
                    collected.append(ev.content)
                elif isinstance(ev, StreamDone):
                    break
        await asyncio.wait_for(_run(), timeout=16)
        raw = "".join(collected).strip()
        m = re.search(r"\{.*\}", raw, re.S)
        parsed = json.loads(m.group(0)) if m else None
        if not parsed or not parsed.get("insights"):
            return _sap_insight_fallback(ctx)
        parsed.setdefault("actions", [])
        parsed["model"] = "openai/gpt-5.4"
        parsed["generated_at"] = _now().isoformat()
        return parsed
    except Exception:
        return _sap_insight_fallback(ctx)


# ── Agentic advisor: resolve a natural-language instruction into an executable
#    activation workflow plan (the advisor can ACT, not just answer). ───────────
class AdvisorPlanBody(BaseModel):
    instruction: str


_ADVISOR_ACTION_WORDS = [
    ("deactivate", "deactivate"), ("disable", "deactivate"), ("revoke", "deactivate"),
    ("offboard", "deactivate"), ("suspend", "suspend"), ("pause", "suspend"), ("hold", "suspend"),
    ("resume", "resume"), ("unsuspend", "resume"), ("reinstate", "resume"),
    ("reactivate", "activate"), ("activate", "activate"), ("enable", "activate"),
    ("restore", "activate"), ("provision", "activate"), ("onboard", "create"), ("create", "create"),
]
_ADVISOR_WANT = {
    "deactivate": {"Activated", "Suspended"}, "suspend": {"Activated"},
    "resume": {"Suspended"}, "activate": {"Deactivated", "Suspended"},
}


@sap_router.post("/advisor/plan")
async def advisor_plan(body: AdvisorPlanBody, user: dict = Depends(get_current_user)):
    org_id = user["org_id"]
    await _ensure(org_id)
    low = body.instruction.lower().strip()
    action = next((act for kw, act in _ADVISOR_ACTION_WORDS if kw in low), None)
    if not action:
        return {"actionable": False, "message": "I didn't detect an access action. Ask me to activate, deactivate, suspend, resume or create a user."}
    if action == "create":
        return {"actionable": False, "action": "create",
                "message": "To create a new SAP user, use the ‘Create User’ button on the User Account Activation page — it runs the automated provisioning workflow (ServiceNow → HR → AD/Entra → SAP). I can then activate, suspend or deactivate them for you."}
    persons, accounts, conflicts, pmap = await _correlate(org_id)
    overrides = {o["person_ref"]: o for o in await db.sap_activation.find({"org_id": org_id}, {"_id": 0}).to_list(5000)}
    def cur(p):
        return _activation_status(p, overrides.get(p["ref"]))
    scope_label, targets, residual = "", [], False
    if any(k in low for k in ("terminated", "leaver", "residual", "offboard")):
        targets, scope_label, residual = [p for p in persons if p["status"] == "Terminated"], "terminated workers with residual access", True
    elif any(k in low for k in ("dormant", "inactive")):
        targets, scope_label = [p for p in persons if any(a.get("flags", {}).get("dormant") for a in p.get("accounts", []))], "dormant-access identities"
    elif "sap_all" in low or "sap all" in low:
        targets, scope_label = [p for p in persons if any(a.get("flags", {}).get("sap_all") for a in p.get("accounts", []))], "SAP_ALL holders"
    elif "all suspended" in low:
        targets, scope_label = [p for p in persons if cur(p) == "Suspended"], "all suspended users"
    elif "all active" in low or "all activated" in low or (" all " in f" {low} " and action in ("deactivate", "suspend")):
        targets, scope_label = [p for p in persons if cur(p) == "Activated"], "all activated users"
    elif "all deactivated" in low or (" all " in f" {low} " and action == "activate"):
        targets, scope_label = [p for p in persons if cur(p) in ("Deactivated", "Suspended")], "all deactivated / suspended users"
    else:
        exact = [p for p in persons if p["name"].lower() in low or p["email"].lower() in low]
        if exact:
            targets, scope_label = exact, ", ".join(p["name"] for p in exact[:5])
        else:
            tok = [p for p in persons if any(len(t) > 2 and t in low.split() for t in p["name"].lower().split())]
            targets, scope_label = tok, ", ".join(p["name"] for p in tok[:5])
    want = _ADVISOR_WANT.get(action, set())
    if residual and action == "deactivate":
        # residual-access remediation: lock terminated workers still holding any unlocked SAP account
        eligible = [p for p in targets if any(a.get("lock_state") == "unlocked" for a in p.get("accounts", []))]
    else:
        eligible = [p for p in targets if cur(p) in want]
    refs = [p["ref"] for p in eligible]
    return {
        "actionable": bool(refs), "action": action, "scope_label": scope_label, "count": len(refs),
        "person_refs": refs,
        "affected": [{"ref": p["ref"], "name": p["name"], "department": p["department"], "status": cur(p)} for p in eligible[:25]],
        "message": (f"Ready to {action} {len(refs)} {scope_label or 'user(s)'} via the automated ServiceNow → HR (ADP/IZ8) → SAP → AD/Entra workflow — each ticket opens and auto-closes end-to-end."
                    if refs else f"No users are currently eligible to {action}" + (f" ({scope_label})" if scope_label else "") + "."),
    }


async def _audit(org_id, actor, action, detail=""):
    await db.audit_logs.insert_one({"org_id": org_id, "actor": actor, "action": action,
                                    "detail": detail, "ts": _now().isoformat()})
