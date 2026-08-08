"""SAP UAC — canonical domain model & static reference data (No-Mock).

Business-function model, SoD rule library, role catalog, systems, legal entities,
HR authority matrix and deterministic seed name pools. Pure data, no I/O."""

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


__all__ = ["FUNCTIONS", "SOD_RULES", "SEV_WEIGHT", "ROLE_CATALOG", "ROLE_BY_REF",
           "SYSTEMS", "LEGAL_ENTITIES", "LE_BY_CODE", "HR_AUTHORITY_MATRIX",
           "SECURITY_HOLD_FIELDS", "_FIRST", "_LAST", "_JOBS", "_sap_uid"]
