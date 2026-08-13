"""Obserra EU Cyber Resilience Act Governance Platform.

Production-oriented first increment for:
- Multi-tenant CRA product governance
- Regulation-mapped readiness assessments
- Proposed Class I / Class II / Critical classification
- Conformity pathway determination
- Secure third-party Certification Portal
- External laboratory / notified-body sign-off workflow
- Tamper-evident Internal Regulatory Ledger
- CycloneDX / SPDX SBOM generation
- CRA Article 14 / ENISA reporting workflow clocks
- EU Declaration of Conformity and CE readiness

This module supports regulatory workflow and traceability. It does not replace
legal advice, a manufacturer's legal responsibility, or a notified body's
conformity assessment.
"""
from __future__ import annotations

import calendar
import hashlib
import json
import re
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Literal
from xml.etree import ElementTree as ET

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from pymongo import ReturnDocument

from auth import get_current_user, require_roles
from db import db

cra_router = APIRouter(prefix="/api/cra", tags=["EU CRA Governance"])
cra_public_router = APIRouter(prefix="/api/cra-public", tags=["EU CRA Certification Portal"])

CRA_VERSION = "EU-CRA-2024-2847"
CLASSIFICATION_VERSION = "EU-2025-2392"
REPORTING_EFFECTIVE_DATE = "2026-09-11"
GENERAL_APPLICATION_DATE = "2027-12-11"

CLASS_I = {
    "I-01": "Identity management systems and privileged access management software and hardware, including authentication and access control readers, including biometric readers",
    "I-02": "Standalone and embedded browsers",
    "I-03": "Password managers",
    "I-04": "Software that searches for, removes, or quarantines malicious software",
    "I-05": "Products with digital elements with the function of virtual private network (VPN)",
    "I-06": "Network management systems",
    "I-07": "Security information and event management (SIEM) systems",
    "I-08": "Boot managers",
    "I-09": "Public key infrastructure and digital certificate issuance software",
    "I-10": "Physical and virtual network interfaces",
    "I-11": "Operating systems",
    "I-12": "Routers, modems intended for the connection to the internet, and switches",
    "I-13": "Microprocessors with security-related functionalities",
    "I-14": "Microcontrollers with security-related functionalities",
    "I-15": "Application specific integrated circuits (ASIC) and field-programmable gate arrays (FPGA) with security-related functionalities",
    "I-16": "Smart home general purpose virtual assistants",
    "I-17": "Smart home products with security functionalities, including smart door locks, security cameras, baby monitoring systems and alarm systems",
    "I-18": "Internet connected toys with social interactive or location tracking features covered by Directive 2009/48/EC",
    "I-19": "Personal wearable health-monitoring products outside Regulations (EU) 2017/745 and 2017/746, or personal wearables intended for children",
}

CLASS_II = {
    "II-01": "Hypervisors and container runtime systems that support virtualised execution of operating systems and similar environments",
    "II-02": "Firewalls, intrusion detection and prevention systems",
    "II-03": "Tamper-resistant microprocessors",
    "II-04": "Tamper-resistant microcontrollers",
}

CRITICAL = {
    "CRIT-01": "Hardware devices with security boxes",
    "CRIT-02": "Smart meter gateways within smart metering systems and other devices for advanced security purposes, including secure cryptoprocessing",
    "CRIT-03": "Smartcards or similar devices, including secure elements",
}

HEURISTIC_TERMS = {
    "I-01": ["identity management", "privileged access", "pam", "authentication", "access control", "biometric"],
    "I-02": ["browser", "web browser", "embedded browser"],
    "I-03": ["password manager", "credential manager"],
    "I-04": ["antivirus", "anti-malware", "malware quarantine", "endpoint protection"],
    "I-05": ["vpn", "virtual private network"],
    "I-06": ["network management", "network manager"],
    "I-07": ["siem", "security information and event management"],
    "I-08": ["boot manager", "secure boot manager"],
    "I-09": ["public key infrastructure", "pki", "certificate issuance", "certificate authority"],
    "I-10": ["network interface", "virtual network interface", "nic"],
    "I-11": ["operating system", "embedded os"],
    "I-12": ["router", "internet modem", "network switch"],
    "I-13": ["security microprocessor", "secure microprocessor"],
    "I-14": ["security microcontroller", "secure microcontroller"],
    "I-15": ["security asic", "security fpga", "field-programmable gate array"],
    "I-16": ["smart home assistant", "virtual home assistant"],
    "I-17": ["smart lock", "security camera", "baby monitor", "alarm system", "smart home security"],
    "I-18": ["connected toy", "internet toy", "location tracking toy"],
    "I-19": ["wearable health monitor", "child wearable", "health tracking wearable"],
    "II-01": ["hypervisor", "container runtime", "virtual machine monitor"],
    "II-02": ["firewall", "intrusion detection", "intrusion prevention", "ids", "ips"],
    "II-03": ["tamper-resistant microprocessor", "tamper resistant microprocessor"],
    "II-04": ["tamper-resistant microcontroller", "tamper resistant microcontroller"],
    "CRIT-01": ["hardware security box", "hardware device with security box"],
    "CRIT-02": ["smart meter gateway", "secure cryptoprocessing", "advanced security device"],
    "CRIT-03": ["smartcard", "smart card", "secure element"],
}

REGULATORY_REQUIREMENTS = [
    {"requirement_id":"CRA-SCOPE-01","domain":"Scope and Product Governance","title":"Product with digital elements scope determination","legal_refs":["Article 2","Article 3"],"evidence_types":["scope memo","product description","market placement evidence"]},
    {"requirement_id":"CRA-RISK-01","domain":"Risk Assessment","title":"Comprehensive cybersecurity risk assessment informs planning, design, development, production, delivery and maintenance","legal_refs":["Article 13(2)","Article 13(3)","Annex VII"],"evidence_types":["cybersecurity risk assessment","threat model","design review","test results"]},
    {"requirement_id":"CRA-ANNEX-I-1","domain":"Essential Cybersecurity Requirements","title":"Product is designed, developed and produced to ensure an appropriate level of cybersecurity based on risks","legal_refs":["Article 6","Annex I Part I"],"evidence_types":["security architecture","risk acceptance","verification evidence"]},
    {"requirement_id":"CRA-ANNEX-I-2","domain":"Essential Cybersecurity Requirements","title":"Product security properties address secure-by-default configuration, confidentiality, integrity, availability and attack-surface reduction","legal_refs":["Article 6","Annex I Part I"],"evidence_types":["secure configuration","encryption evidence","availability testing","attack surface review"]},
    {"requirement_id":"CRA-COMP-01","domain":"Third-Party Components","title":"Third-party components are selected and integrated with cybersecurity due diligence","legal_refs":["Article 13(5)","Article 13(6)"],"evidence_types":["supplier assessment","component approval","supplier notification record"]},
    {"requirement_id":"CRA-SUPPORT-01","domain":"Support Period","title":"Support period is determined, documented and communicated","legal_refs":["Article 13(8)"],"evidence_types":["support period decision","expected use analysis","support policy"]},
    {"requirement_id":"CRA-SBOM-01","domain":"Vulnerability Handling","title":"Components and vulnerabilities are identified and documented, including an SBOM in a commonly used machine-readable format covering at least top-level dependencies","legal_refs":["Annex I Part II(1)"],"evidence_types":["CycloneDX SBOM","SPDX SBOM","component inventory"]},
    {"requirement_id":"CRA-VULN-01","domain":"Vulnerability Handling","title":"Vulnerabilities are identified and documented without delay","legal_refs":["Annex I Part II"],"evidence_types":["vulnerability register","CVE records","triage evidence"]},
    {"requirement_id":"CRA-VULN-02","domain":"Vulnerability Handling","title":"Vulnerabilities are addressed and remediated, including through security updates where appropriate","legal_refs":["Annex I Part II"],"evidence_types":["patch record","security update","remediation test"]},
    {"requirement_id":"CRA-VDP-01","domain":"Vulnerability Disclosure","title":"Coordinated vulnerability disclosure policy and contact process are maintained","legal_refs":["Article 13(8)","Annex I Part II"],"evidence_types":["VDP","security contact","coordinated disclosure procedure"]},
    {"requirement_id":"CRA-REPORT-01","domain":"Regulatory Reporting","title":"Actively exploited vulnerabilities and severe incidents are reported through the CRA reporting process within required timelines","legal_refs":["Article 14","Article 16"],"evidence_types":["24-hour early warning","72-hour notification","final report","submission receipt"]},
    {"requirement_id":"CRA-TECHDOC-01","domain":"Technical Documentation","title":"Technical documentation demonstrates conformity and includes the cybersecurity risk assessment","legal_refs":["Article 31","Annex VII"],"evidence_types":["technical file","risk assessment","architecture","test report"]},
    {"requirement_id":"CRA-CLASS-01","domain":"Classification","title":"Important and critical product classification is determined from core functionality","legal_refs":["Article 7","Article 8","Annex III","Annex IV","Implementing Regulation (EU) 2025/2392"],"evidence_types":["classification decision","technical-description mapping","legal approval"]},
    {"requirement_id":"CRA-CONFORM-01","domain":"Conformity Assessment","title":"Applicable conformity assessment route is selected and completed","legal_refs":["Article 32","Annex VIII"],"evidence_types":["Module A record","EU-type examination","Module C record","Module H assessment","EU certification evidence"]},
    {"requirement_id":"CRA-NB-01","domain":"External Conformity Assessment","title":"Where third-party conformity assessment is required, the assessment is performed by an appropriately notified conformity assessment body","legal_refs":["Articles 35-51","Article 43","Article 32"],"evidence_types":["notified body record","NANDO reference","assessment report","certificate"]},
    {"requirement_id":"CRA-DOC-01","domain":"EU Declaration","title":"EU Declaration of Conformity is prepared after applicable conformity assessment is complete","legal_refs":["Article 28","Annex V","Annex VI"],"evidence_types":["EU Declaration of Conformity","signatory approval"]},
    {"requirement_id":"CRA-CE-01","domain":"Market Placement","title":"CE marking readiness is established before placing the product on the Union market","legal_refs":["Article 29","Article 30"],"evidence_types":["CE marking approval","label artwork","market release approval"]},
    {"requirement_id":"CRA-USERINFO-01","domain":"User Information","title":"Required information and instructions are supplied to users","legal_refs":["Article 13","Annex II"],"evidence_types":["user instructions","support contact","security update information"]},
]

def utcnow() -> datetime:
    return datetime.now(timezone.utc)

def iso(value: datetime | None = None) -> str:
    return (value or utcnow()).isoformat()

def token_hash(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()

async def next_ref(org_id: str, counter_name: str, prefix: str) -> str:
    doc = await db.counters.find_one_and_update(
        {"_id": f"cra:{counter_name}:{org_id}"},
        {"$inc": {"seq": 1}},
        upsert=True,
        return_document=ReturnDocument.AFTER,
    )
    return f"{prefix}-{str(doc['seq']).zfill(5)}"

async def audit(org_id: str, actor: str, action: str, detail: str = "", target: str | None = None) -> None:
    await db.audit_logs.insert_one({"org_id": org_id,"actor": actor,"action": action,"detail": detail,"target": target,"ts": iso()})

async def ledger_append(org_id: str, actor: str, event_type: str, object_type: str, object_ref: str, legal_refs: list[str], data: dict[str, Any]) -> dict:
    previous = await db.cra_regulatory_ledger.find_one({"org_id": org_id}, sort=[("sequence", -1)])
    sequence_doc = await db.counters.find_one_and_update(
        {"_id": f"cra:ledger:{org_id}"},{"$inc":{"seq":1}},upsert=True,return_document=ReturnDocument.AFTER
    )
    payload = {
        "org_id": org_id,
        "sequence": int(sequence_doc["seq"]),
        "event_type": event_type,
        "object_type": object_type,
        "object_ref": object_ref,
        "legal_refs": legal_refs,
        "data": data,
        "actor": actor,
        "ts": iso(),
        "prev_hash": (previous or {}).get("record_hash",""),
        "regulation_version": CRA_VERSION,
        "classification_version": CLASSIFICATION_VERSION,
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",",":"), default=str)
    record = {**payload, "record_hash": hashlib.sha256(canonical.encode("utf-8")).hexdigest()}
    await db.cra_regulatory_ledger.insert_one(record)
    record.pop("_id", None)
    return record

def class_name_for_code(code: str) -> str:
    if code in CRITICAL: return "Critical"
    if code in CLASS_II: return "Class II"
    if code in CLASS_I: return "Class I"
    return "Default"

def category_name(code: str) -> str:
    return CRITICAL.get(code) or CLASS_II.get(code) or CLASS_I.get(code) or ""

def conformity_pathway(classification: str, harmonised_route_complete: bool = False) -> dict:
    if classification == "Default":
        return {"pathway":"Manufacturer Self-Assessment","procedures":["Module A internal control"],"notified_body_required":False,"legal_refs":["Article 32(1)","Annex VIII"]}
    if classification == "Class I":
        if harmonised_route_complete:
            return {"pathway":"Conditional Manufacturer Self-Assessment","procedures":["Module A internal control"],"notified_body_required":False,"condition":"Applicable harmonised standards, common specifications, or qualifying EU cybersecurity certification route fully applied","legal_refs":["Article 32(2)","Annex VIII"]}
        return {"pathway":"Third-Party Conformity Assessment","procedures":["Module B + Module C","Module H"],"notified_body_required":True,"legal_refs":["Article 32(2)","Annex VIII"]}
    if classification == "Class II":
        return {"pathway":"Third-Party Conformity Assessment","procedures":["Module B + Module C","Module H","Applicable EU cybersecurity certification scheme at assurance level at least substantial"],"notified_body_required":True,"legal_refs":["Article 32(3)","Annex VIII"]}
    return {"pathway":"Critical Product Conformity Assessment","procedures":["European cybersecurity certification scheme where required under Article 8(1)","Otherwise Article 32(3) procedures"],"notified_body_required":True,"legal_refs":["Article 8","Article 32(4)","Annex IV","Annex VIII"]}

def classify_product_record(product: dict) -> dict:
    explicit_codes = [code for code in product.get("category_codes",[]) if code in CLASS_I or code in CLASS_II or code in CRITICAL]
    source = "explicit_category_selection"
    confidence = 100 if explicit_codes else 0
    matches = []
    if explicit_codes:
        for code in explicit_codes:
            matches.append({"code":code,"category":category_name(code),"classification":class_name_for_code(code),"match_type":"explicit","score":100})
    else:
        source = "heuristic_core_functionality"
        haystack = " ".join([str(product.get("name","")),str(product.get("description","")),str(product.get("core_functionality",""))," ".join(product.get("functional_tags",[]) or [])]).lower()
        for code, terms in HEURISTIC_TERMS.items():
            score = sum(1 for term in terms if term.lower() in haystack)
            if score:
                matches.append({"code":code,"category":category_name(code),"classification":class_name_for_code(code),"match_type":"heuristic","score":score})
        matches.sort(key=lambda x: ({"Critical":3,"Class II":2,"Class I":1}.get(x["classification"],0),x["score"]), reverse=True)
        confidence = min(90,45 + (matches[0]["score"] * 12)) if matches else 35
    classes = {m["classification"] for m in matches}
    classification = "Critical" if "Critical" in classes else "Class II" if "Class II" in classes else "Class I" if "Class I" in classes else "Default"
    return {
        "classification": classification,
        "classification_status": "Proposed",
        "source": source,
        "confidence": confidence,
        "manual_regulatory_review_required": source != "explicit_category_selection",
        "matches": matches,
        "legal_refs":["Article 7","Article 8","Annex III","Annex IV","Commission Implementing Regulation (EU) 2025/2392"],
        "pathway": conformity_pathway(classification, bool(product.get("harmonised_route_complete"))),
        "classified_at": iso(),
        "regulation_version": CRA_VERSION,
        "classification_version": CLASSIFICATION_VERSION,
    }

def add_month(value: datetime) -> datetime:
    year = value.year + (1 if value.month == 12 else 0)
    month = 1 if value.month == 12 else value.month + 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return value.replace(year=year, month=month, day=day)

def parse_dt(value):
    if value is None: return None
    dt = value if isinstance(value, datetime) else datetime.fromisoformat(str(value).replace("Z","+00:00"))
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)

def reporting_clock(record: dict) -> dict:
    awareness = parse_dt(record.get("awareness_at"))
    if not awareness: return {}
    early = awareness + timedelta(hours=24)
    full = awareness + timedelta(hours=72)
    correction = parse_dt(record.get("corrective_measure_available_at"))
    vuln_final = correction + timedelta(days=14) if correction and record.get("actively_exploited") else None
    incident_final = add_month(full) if record.get("severe_incident") else None
    now = utcnow()
    def stage(name, deadline):
        if not deadline: return None
        submission = (record.get("submissions") or {}).get(name,{})
        submitted = bool(submission.get("submitted_at"))
        return {"stage":name,"deadline":deadline.isoformat(),"submitted":submitted,"submitted_at":submission.get("submitted_at"),"receipt_id":submission.get("receipt_id"),"overdue":(not submitted) and now > deadline,"hours_remaining":round((deadline-now).total_seconds()/3600,1)}
    stages = [stage("early_warning",early),stage("notification_72h",full),stage("final_vulnerability_report",vuln_final),stage("final_incident_report",incident_final)]
    return {"awareness_at":awareness.isoformat(),"stages":[x for x in stages if x],"legal_refs":["Article 14","Article 16"],"reporting_effective_date":REPORTING_EFFECTIVE_DATE}

def parse_manifest(manifest_type: str, manifest_text: str) -> list[dict]:
    kind = (manifest_type or "").lower().strip()
    components = []
    if kind in {"requirements.txt","requirements"}:
        for raw in manifest_text.splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or line.startswith("-"): continue
            match = re.match(r"^([A-Za-z0-9_.-]+)\s*(?:==|>=|~=|<=|>|<)?\s*([^\s;]+)?", line)
            if match: components.append({"name":match.group(1),"version":match.group(2) or "unspecified","type":"library","ecosystem":"PyPI"})
        return components
    if kind in {"package.json","package-lock.json","npm"}:
        data = json.loads(manifest_text)
        if kind == "package-lock.json" and isinstance(data.get("packages"),dict):
            for _, meta in data["packages"].items():
                if meta.get("name"): components.append({"name":meta["name"],"version":meta.get("version","unspecified"),"type":"library","ecosystem":"npm"})
        else:
            merged = {}
            merged.update(data.get("dependencies") or {})
            merged.update(data.get("devDependencies") or {})
            for name, version in merged.items(): components.append({"name":name,"version":str(version).lstrip("^~"),"type":"library","ecosystem":"npm"})
        return components
    if kind in {"pom.xml","maven"}:
        root = ET.fromstring(manifest_text)
        for dep in root.findall(".//{*}dependency"):
            group = dep.findtext("{*}groupId") or ""
            artifact = dep.findtext("{*}artifactId") or ""
            version = dep.findtext("{*}version") or "unspecified"
            if artifact: components.append({"name":f"{group}:{artifact}" if group else artifact,"version":version,"type":"library","ecosystem":"Maven"})
        return components
    raise HTTPException(400,"Unsupported manifest type. Use requirements.txt, package.json, package-lock.json, or pom.xml.")

def component_purl(component: dict) -> str:
    ecosystem = (component.get("ecosystem") or "generic").lower()
    ptype = {"pypi":"pypi","npm":"npm","maven":"maven"}.get(ecosystem,"generic")
    name = str(component.get("name","")).replace(" ","%20")
    return f"pkg:{ptype}/{name}@{component.get('version','unspecified')}"

def cyclonedx_document(product: dict, components: list[dict]) -> dict:
    return {
        "bomFormat":"CycloneDX","specVersion":"1.6","serialNumber":f"urn:uuid:{uuid.uuid4()}","version":1,
        "metadata":{"timestamp":iso(),"component":{"type":"application","name":product["name"],"version":product.get("version") or "unspecified"},"properties":[{"name":"obserra:cra:product_ref","value":product["ref"]},{"name":"obserra:cra:regulation","value":CRA_VERSION}]},
        "components":[{"type":c.get("type","library"),"name":c["name"],"version":c.get("version","unspecified"),"purl":component_purl(c)} for c in components],
    }

def spdx_document(product: dict, components: list[dict]) -> dict:
    packages = [{"SPDXID":"SPDXRef-Product","name":product["name"],"versionInfo":product.get("version") or "unspecified","downloadLocation":"NOASSERTION","filesAnalyzed":False}]
    relationships = []
    for i,c in enumerate(components,1):
        sid = f"SPDXRef-Component-{i}"
        packages.append({"SPDXID":sid,"name":c["name"],"versionInfo":c.get("version","unspecified"),"downloadLocation":"NOASSERTION","filesAnalyzed":False,"externalRefs":[{"referenceCategory":"PACKAGE-MANAGER","referenceType":"purl","referenceLocator":component_purl(c)}]})
        relationships.append({"spdxElementId":"SPDXRef-Product","relationshipType":"DEPENDS_ON","relatedSpdxElement":sid})
    return {"spdxVersion":"SPDX-2.3","dataLicense":"CC0-1.0","SPDXID":"SPDXRef-DOCUMENT","name":f"{product['name']}-{product.get('version') or 'unspecified'}","documentNamespace":f"https://obserra.invalid/spdx/{product['ref']}/{uuid.uuid4()}","creationInfo":{"created":utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),"creators":["Tool: Obserra CRA Governance Platform"]},"packages":packages,"relationships":relationships}

async def get_product(org_id: str, ref: str) -> dict:
    row = await db.cra_products.find_one({"org_id":org_id,"ref":ref},{"_id":0})
    if not row: raise HTTPException(404,"CRA product not found")
    return row

async def get_assessment(org_id: str, ref: str) -> dict:
    row = await db.cra_assessments.find_one({"org_id":org_id,"ref":ref},{"_id":0})
    if not row: raise HTTPException(404,"CRA assessment not found")
    return row

async def issue_portal_token(org_id, product_ref, role, assessment_ref, provider_ref, invited_email, expires_hours, actor):
    raw = secrets.token_urlsafe(40)
    expires = utcnow() + timedelta(hours=max(1,min(expires_hours,720)))
    await db.cra_portal_tokens.insert_one({"org_id":org_id,"product_ref":product_ref,"role":role,"assessment_ref":assessment_ref,"provider_ref":provider_ref,"invited_email":invited_email.lower().strip(),"token_hash":token_hash(raw),"created_at":utcnow(),"expires_at":expires,"revoked_at":None,"created_by":actor})
    return {"token":raw,"expires_at":expires.isoformat(),"role":role}

async def verify_portal_token(raw_token: str) -> dict:
    row = await db.cra_portal_tokens.find_one({"token_hash":token_hash(raw_token),"revoked_at":None,"expires_at":{"$gt":utcnow()}},{"_id":0})
    if not row: raise HTTPException(401,"Certification Portal link is invalid or expired")
    return row

async def ensure_cra_indexes() -> None:
    await db.cra_products.create_index([("org_id",1),("ref",1)],unique=True)
    await db.cra_assessments.create_index([("org_id",1),("ref",1)],unique=True)
    await db.cra_sboms.create_index([("org_id",1),("product_ref",1),("created_at",-1)])
    await db.cra_vulnerabilities.create_index([("org_id",1),("ref",1)],unique=True)
    await db.cra_providers.create_index([("org_id",1),("ref",1)],unique=True)
    await db.cra_external_assessments.create_index([("org_id",1),("ref",1)],unique=True)
    await db.cra_regulatory_ledger.create_index([("org_id",1),("sequence",1)],unique=True)
    await db.cra_portal_tokens.create_index("expires_at",expireAfterSeconds=0)
    await db.cra_portal_tokens.create_index("token_hash",unique=True)
    await db.cra_control_owners.create_index([("org_id",1),("requirement_id",1)],unique=True)

class ProductCreate(BaseModel):
    name: str = Field(min_length=2,max_length=180)
    version: str = Field(default="",max_length=80)
    manufacturer_name: str = Field(min_length=2,max_length=220)
    description: str = Field(default="",max_length=6000)
    core_functionality: str = Field(default="",max_length=5000)
    functional_tags: list[str] = Field(default_factory=list)
    category_codes: list[str] = Field(default_factory=list)
    support_period_years: int = Field(default=5,ge=1,le=30)
    expected_use_years: float | None = Field(default=None,ge=0.1,le=50)
    open_source: bool = False
    harmonised_route_complete: bool = False
    eu_market: bool = True

class ClassificationApproval(BaseModel):
    decision: Literal["Approve","Override"]
    override_classification: Literal["Default","Class I","Class II","Critical"] | None = None
    rationale: str = Field(min_length=5,max_length=4000)

class AssessmentAnswer(BaseModel):
    requirement_id: str
    status: Literal["Conforming","Partial","Nonconforming","Not Applicable","Not Assessed"]
    evidence_refs: list[str] = Field(default_factory=list)
    comment: str = Field(default="",max_length=4000)

class AssessmentUpdate(BaseModel):
    answers: list[AssessmentAnswer]

class PortalInviteCreate(BaseModel):
    product_ref: str
    role: Literal["vendor","external_assessor"]
    assessment_ref: str | None = None
    provider_ref: str | None = None
    invited_email: str = ""
    expires_hours: int = Field(default=168,ge=1,le=720)

class ProviderCreate(BaseModel):
    name: str = Field(min_length=2,max_length=220)
    provider_type: Literal["testing_lab","notified_body","certification_body"]
    country: str = ""
    nando_id: str = ""
    scope: list[str] = Field(default_factory=list)
    contact_email: str = ""
    integration_mode: Literal["secure_portal","api","secure_file_exchange","manual"] = "secure_portal"
    nando_verified_at: str | None = None
    verification_evidence_ref: str = ""

class ExternalAssessmentCreate(BaseModel):
    product_ref: str
    provider_ref: str
    module: Literal["Module B+C","Module H","EU Cybersecurity Certification","Testing Evidence"]
    scope: str = "CRA conformity assessment"
    due_at: str | None = None

class ExternalSignoff(BaseModel):
    decision: Literal["Conforming","Conditional","Nonconforming"]
    assessor_name: str = Field(min_length=2,max_length=180)
    provider_reference: str = ""
    findings: list[str] = Field(default_factory=list)
    artifact_refs: list[str] = Field(default_factory=list)
    comment: str = ""

class SBOMComponent(BaseModel):
    name: str
    version: str = "unspecified"
    type: str = "library"
    ecosystem: str = "generic"

class SBOMGenerate(BaseModel):
    format: Literal["cyclonedx-json","spdx-json"] = "cyclonedx-json"
    manifest_type: str = ""
    manifest_text: str = ""
    components: list[SBOMComponent] = Field(default_factory=list)

class VulnerabilityCreate(BaseModel):
    product_ref: str
    title: str = Field(min_length=3,max_length=220)
    cve: str = ""
    description: str = ""
    severity: Literal["Low","Medium","High","Critical"] = "High"
    actively_exploited: bool = False
    severe_incident: bool = False
    awareness_at: str
    corrective_measure_available_at: str | None = None

class SubmissionUpdate(BaseModel):
    stage: Literal["early_warning","notification_72h","final_vulnerability_report","final_incident_report"]
    state: Literal["Draft","Legal Review","Authorized","Submitted","Receipt Recorded"]
    submitted_at: str | None = None
    receipt_id: str = ""
    comment: str = ""

class DeclarationApproval(BaseModel):
    signatory_name: str = Field(min_length=2,max_length=180)
    signatory_title: str = Field(min_length=2,max_length=180)
    declaration_reference: str = ""


@cra_router.get("/regulation")
async def regulation_map(user: dict = Depends(get_current_user)):
    return {
        "regulation": CRA_VERSION,
        "classification_implementing_regulation": CLASSIFICATION_VERSION,
        "reporting_effective_date": REPORTING_EFFECTIVE_DATE,
        "general_application_date": GENERAL_APPLICATION_DATE,
        "requirements": REGULATORY_REQUIREMENTS,
        "categories": {
            "class_i": [{"code":code,"name":name} for code,name in CLASS_I.items()],
            "class_ii": [{"code":code,"name":name} for code,name in CLASS_II.items()],
            "critical": [{"code":code,"name":name} for code,name in CRITICAL.items()],
        },
    }

@cra_router.get("/dashboard")
async def dashboard(user: dict = Depends(get_current_user)):
    org_id = user["org_id"]
    products = await db.cra_products.find({"org_id":org_id},{"_id":0}).to_list(1000)
    assessments = await db.cra_assessments.find({"org_id":org_id},{"_id":0}).to_list(1000)
    vulnerabilities = await db.cra_vulnerabilities.find({"org_id":org_id},{"_id":0}).to_list(1000)
    external = await db.cra_external_assessments.find({"org_id":org_id},{"_id":0}).to_list(1000)
    by_class = {"Default":0,"Class I":0,"Class II":0,"Critical":0}
    approved = ce_ready = overdue = 0
    for product in products:
        classification = (product.get("classification") or {}).get("classification","Default")
        by_class[classification] = by_class.get(classification,0) + 1
        approved += 1 if (product.get("classification") or {}).get("classification_status") == "Approved" else 0
        ce_ready += 1 if product.get("ce_status") == "Ready" else 0
    for vulnerability in vulnerabilities:
        overdue += 1 if any(stage.get("overdue") for stage in reporting_clock(vulnerability).get("stages",[])) else 0
    scores = [a.get("score",0) for a in assessments if a.get("score") is not None]
    return {
        "products":len(products),
        "classifications":by_class,
        "classification_approved":approved,
        "average_readiness":round(sum(scores)/len(scores)) if scores else 0,
        "ce_ready":ce_ready,
        "open_external_assessments":sum(1 for x in external if x.get("status") not in {"Conforming","Closed"}),
        "reporting_overdue":overdue,
        "reporting_effective_date":REPORTING_EFFECTIVE_DATE,
        "general_application_date":GENERAL_APPLICATION_DATE,
        "next_deadline":_cra_next_deadline(),
    }

NIST_CSF_FUNCTIONS = [("GV", "Govern"), ("ID", "Identify"), ("PR", "Protect"), ("DE", "Detect"), ("RS", "Respond"), ("RC", "Recover")]

# Maps each EU CRA requirement to NIST CSF 2.0 functions/categories and NIST SP 800-218 (SSDF) practices.
NIST_ALIGNMENT = {
    "CRA-SCOPE-01":    {"csf": ["GV"], "categories": ["GV.OC", "GV.SC"], "ssdf": ["PO.1"]},
    "CRA-RISK-01":     {"csf": ["ID", "GV"], "categories": ["ID.RA", "GV.RM"], "ssdf": ["PO.1", "PW.1"]},
    "CRA-ANNEX-I-1":   {"csf": ["PR"], "categories": ["PR.PS", "PR.AA"], "ssdf": ["PW.4", "PW.5"]},
    "CRA-ANNEX-I-2":   {"csf": ["PR"], "categories": ["PR.PS", "PR.DS"], "ssdf": ["PW.4", "PW.9"]},
    "CRA-COMP-01":     {"csf": ["GV", "ID"], "categories": ["GV.SC", "ID.RA"], "ssdf": ["PW.4", "PO.3"]},
    "CRA-SUPPORT-01":  {"csf": ["GV"], "categories": ["GV.RM", "GV.OC"], "ssdf": ["RV.3"]},
    "CRA-SBOM-01":     {"csf": ["ID"], "categories": ["ID.AM"], "ssdf": ["PS.3", "PW.4"]},
    "CRA-VULN-01":     {"csf": ["ID", "PR"], "categories": ["ID.RA", "PR.PS"], "ssdf": ["RV.1", "PW.7"]},
    "CRA-VULN-02":     {"csf": ["DE"], "categories": ["DE.CM", "DE.AE"], "ssdf": ["RV.1", "RV.2"]},
    "CRA-VDP-01":      {"csf": ["RS"], "categories": ["RS.CO"], "ssdf": ["RV.1"]},
    "CRA-REPORT-01":   {"csf": ["RS"], "categories": ["RS.CO", "RS.MA"], "ssdf": ["RV.2"]},
    "CRA-TECHDOC-01":  {"csf": ["GV"], "categories": ["GV.OC", "GV.PO"], "ssdf": ["PS.3", "PO.2"]},
    "CRA-CLASS-01":    {"csf": ["ID"], "categories": ["ID.AM", "ID.RA"], "ssdf": ["PO.1"]},
    "CRA-CONFORM-01":  {"csf": ["GV"], "categories": ["GV.OV"], "ssdf": ["PS.1"]},
    "CRA-NB-01":       {"csf": ["GV"], "categories": ["GV.OV", "GV.SC"], "ssdf": ["PS.1"]},
    "CRA-DOC-01":      {"csf": ["GV"], "categories": ["GV.OC"], "ssdf": ["PO.2"]},
    "CRA-CE-01":       {"csf": ["GV"], "categories": ["GV.OC", "GV.OV"], "ssdf": ["PO.2"]},
    "CRA-USERINFO-01": {"csf": ["PR", "GV"], "categories": ["PR.AT", "GV.OC"], "ssdf": ["PW.9", "RV.3"]},
}
_RISK_ORDER = {"Unknown": 0, "Low": 1, "Medium": 2, "High": 3}


async def _compute_controls(org_id: str) -> dict:
    products = await db.cra_products.find({"org_id":org_id},{"_id":0,"ref":1,"name":1}).to_list(1000)
    name_by_ref = {p["ref"]: p.get("name", p["ref"]) for p in products}
    assessments = await db.cra_assessments.find({"org_id":org_id},{"_id":0}).to_list(1000)
    owners = {o["requirement_id"]: {"owner":o.get("owner",""),"due_date":o.get("due_date"),"status":o.get("status","Open"),
                                    "note":o.get("note",""),"updated_at":o.get("updated_at"),"updated_by":o.get("updated_by")}
              for o in await db.cra_control_owners.find({"org_id":org_id},{"_id":0}).to_list(1000)}
    latest = {}
    for a in sorted(assessments, key=lambda x: x.get("updated_at",""), reverse=True):
        latest.setdefault(a.get("product_ref"), a)
    latest_list = list(latest.values())
    controls = []
    total_points = total_cells = 0
    implemented = partial_ct = gaps = not_started = high_risk = 0
    for req in REGULATORY_REQUIREMENTS:
        rid = req["requirement_id"]
        c = {"Conforming":0,"Partial":0,"Nonconforming":0,"Not Applicable":0,"Not Assessed":0}
        product_status = []
        for a in latest_list:
            st = "Not Assessed"
            for ans in a.get("answers",[]):
                if ans.get("requirement_id") == rid:
                    st = ans.get("status","Not Assessed"); break
            c[st] = c.get(st,0) + 1
            product_status.append({"ref":a.get("product_ref"),"name":name_by_ref.get(a.get("product_ref"),a.get("product_ref")),"status":st})
        assessed = c["Conforming"] + c["Partial"] + c["Nonconforming"]
        points = c["Conforming"]*1.0 + c["Partial"]*0.5
        total_points += points; total_cells += assessed
        rate = round(points/assessed*100) if assessed else None
        if assessed == 0:
            status, risk = "Not Started", "Unknown"; not_started += 1
        elif rate == 100:
            status, risk = "Implemented", "Low"; implemented += 1
        elif rate == 0:
            status, risk = "Gap", "High"; gaps += 1
        else:
            status = "Partial"; risk = "Medium" if rate >= 50 else "High"; partial_ct += 1
        if c["Nonconforming"] > 0 and risk != "High":
            risk = "High"
        if risk == "High":
            high_risk += 1
        controls.append({"requirement_id":rid,"domain":req["domain"],"title":req["title"],
                         "legal_refs":req["legal_refs"],"assessed":assessed,"products_total":len(products),
                         "conforming":c["Conforming"],"partial":c["Partial"],"nonconforming":c["Nonconforming"],
                         "not_applicable":c["Not Applicable"],"not_assessed":c["Not Assessed"],
                         "compliance_rate":rate,"status":status,"risk":risk,"product_status":product_status,
                         "assignment":owners.get(rid),"nist":NIST_ALIGNMENT.get(rid, {"csf":[],"categories":[],"ssdf":[]})})
    overall = round(total_points/total_cells*100) if total_cells else 0
    return {"overall":{"percentage":overall,"requirements_total":len(REGULATORY_REQUIREMENTS),
                       "implemented":implemented,"partial":partial_ct,"gaps":gaps,"not_started":not_started,
                       "high_risk":high_risk,"products_assessed":len(latest_list),"products_total":len(products)},
            "controls":controls}


@cra_router.get("/controls")
async def controls_dashboard(user: dict = Depends(get_current_user)):
    return await _compute_controls(user["org_id"])


async def _compute_nist(org_id: str) -> dict:
    computed = await _compute_controls(org_id)
    functions = []
    for code, name in NIST_CSF_FUNCTIONS:
        mapped = [c for c in computed["controls"] if code in (c.get("nist") or {}).get("csf", [])]
        cats = sorted({cat for c in mapped for cat in (c.get("nist") or {}).get("categories", []) if cat.startswith(code)})
        sconf = sum(c["conforming"] for c in mapped)
        spart = sum(c["partial"] for c in mapped)
        sass = sum(c["assessed"] for c in mapped)
        comp = round((sconf + 0.5 * spart) / sass * 100) if sass else None
        risk = "Unknown"
        for c in mapped:
            if _RISK_ORDER.get(c["risk"], 0) > _RISK_ORDER.get(risk, 0):
                risk = c["risk"]
        functions.append({"code": code, "name": name, "categories": cats, "mapped": len(mapped),
                          "compliance_rate": comp, "risk": risk,
                          "implemented": sum(1 for c in mapped if c["status"] == "Implemented"),
                          "partial": sum(1 for c in mapped if c["status"] == "Partial"),
                          "gaps": sum(1 for c in mapped if c["status"] == "Gap"),
                          "not_started": sum(1 for c in mapped if c["status"] == "Not Started"),
                          "controls": [{"requirement_id": c["requirement_id"], "title": c["title"],
                                        "compliance_rate": c["compliance_rate"], "status": c["status"], "risk": c["risk"],
                                        "categories": (c.get("nist") or {}).get("categories", []),
                                        "ssdf": (c.get("nist") or {}).get("ssdf", [])} for c in mapped]})
    aligned = sum(1 for f in functions if f["compliance_rate"] == 100)
    return {"overall": {"alignment_percentage": computed["overall"]["percentage"], "functions_total": len(functions),
                        "functions_aligned": aligned, "framework": "NIST CSF 2.0 · SP 800-218 (SSDF)"},
            "functions": functions}


@cra_router.get("/nist")
async def nist_dashboard(user: dict = Depends(get_current_user)):
    return await _compute_nist(user["org_id"])

@cra_router.get("/products")
async def list_products(user: dict = Depends(get_current_user)):
    return await db.cra_products.find({"org_id":user["org_id"]},{"_id":0}).sort("updated_at",-1).to_list(1000)

@cra_router.post("/products")
async def create_product(body: ProductCreate, user: dict = Depends(get_current_user)):
    org_id = user["org_id"]
    ref = await next_ref(org_id,"product","CRA-PROD")
    product = {
        "org_id":org_id,"ref":ref,**body.model_dump(),"classification":{},"ce_status":"Not Ready",
        "declaration":None,"created_at":iso(),"updated_at":iso(),"created_by":user.get("email","unknown")
    }
    await db.cra_products.insert_one(product)
    product.pop("_id",None)
    await ledger_append(org_id,user.get("email","unknown"),"product.created","product",ref,["Article 13","Article 31"],{"name":body.name,"version":body.version})
    await audit(org_id,user.get("email","unknown"),"cra.product.create",body.name,ref)
    return product

@cra_router.post("/products/{ref}/classify")
async def classify_product(ref: str, user: dict = Depends(get_current_user)):
    org_id = user["org_id"]
    product = await get_product(org_id,ref)
    result = classify_product_record(product)
    await db.cra_products.update_one({"org_id":org_id,"ref":ref},{"$set":{"classification":result,"updated_at":iso()}})
    await ledger_append(org_id,user.get("email","unknown"),"classification.proposed","product",ref,result["legal_refs"],result)
    return result

@cra_router.post("/products/{ref}/classification/approve")
async def approve_classification(ref: str, body: ClassificationApproval, admin: dict = Depends(require_roles("admin"))):
    org_id = admin["org_id"]
    product = await get_product(org_id,ref)
    current = product.get("classification") or classify_product_record(product)
    classification = current.get("classification","Default")
    if body.decision == "Override":
        if not body.override_classification:
            raise HTTPException(400,"override_classification is required")
        classification = body.override_classification
    approved = {
        **current,
        "classification":classification,
        "classification_status":"Approved",
        "approval_type":body.decision,
        "approval_rationale":body.rationale,
        "approved_at":iso(),
        "approved_by":admin.get("email","unknown"),
        "pathway":conformity_pathway(classification,bool(product.get("harmonised_route_complete"))),
    }
    await db.cra_products.update_one({"org_id":org_id,"ref":ref},{"$set":{"classification":approved,"updated_at":iso()}})
    await ledger_append(org_id,admin.get("email","unknown"),"classification.approved","product",ref,approved["legal_refs"],approved)
    return approved

@cra_router.get("/products/{ref}/pathway")
async def get_pathway(ref: str, user: dict = Depends(get_current_user)):
    product = await get_product(user["org_id"],ref)
    classification = (product.get("classification") or {}).get("classification","Default")
    return conformity_pathway(classification,bool(product.get("harmonised_route_complete")))

def assessment_score(answers: list[dict]) -> int:
    applicable = [a for a in answers if a.get("status") not in {"Not Applicable","Not Assessed"}]
    if not applicable: return 0
    points = sum(1.0 if a.get("status") == "Conforming" else 0.5 if a.get("status") == "Partial" else 0 for a in applicable)
    return round((points/len(applicable))*100)

@cra_router.post("/products/{ref}/assessment/init")
async def init_assessment(ref: str, user: dict = Depends(get_current_user)):
    org_id = user["org_id"]
    product = await get_product(org_id,ref)
    assessment_ref = await next_ref(org_id,"assessment","CRA-ASMT")
    answers = [{"requirement_id":r["requirement_id"],"status":"Not Assessed","evidence_refs":[],"comment":""} for r in REGULATORY_REQUIREMENTS]
    record = {"org_id":org_id,"ref":assessment_ref,"product_ref":ref,"product_name":product["name"],"answers":answers,"score":0,"status":"In Progress","created_at":iso(),"updated_at":iso(),"created_by":user.get("email","unknown")}
    await db.cra_assessments.insert_one(record)
    record.pop("_id",None)
    await ledger_append(org_id,user.get("email","unknown"),"assessment.initialized","assessment",assessment_ref,["Article 6","Article 13","Annex I","Annex VII"],{"product_ref":ref})
    return record

@cra_router.get("/assessments")
async def list_assessments(user: dict = Depends(get_current_user)):
    return await db.cra_assessments.find({"org_id":user["org_id"]},{"_id":0}).sort("updated_at",-1).to_list(1000)

@cra_router.put("/assessments/{ref}")
async def update_assessment(ref: str, body: AssessmentUpdate, user: dict = Depends(get_current_user)):
    org_id = user["org_id"]
    current = await get_assessment(org_id,ref)
    allowed = {x["requirement_id"] for x in REGULATORY_REQUIREMENTS}
    incoming = {a.requirement_id:a.model_dump() for a in body.answers if a.requirement_id in allowed}
    answers = [incoming.get(x["requirement_id"],x) for x in current.get("answers",[])]
    score = assessment_score(answers)
    status = "Complete" if all(a["status"] != "Not Assessed" for a in answers) else "In Progress"
    await db.cra_assessments.update_one({"org_id":org_id,"ref":ref},{"$set":{"answers":answers,"score":score,"status":status,"updated_at":iso()}})
    await ledger_append(org_id,user.get("email","unknown"),"assessment.updated","assessment",ref,["Article 6","Article 13","Annex I"],{"score":score,"status":status})
    return await get_assessment(org_id,ref)

@cra_router.post("/portal/invites")
async def create_portal_invite(body: PortalInviteCreate, admin: dict = Depends(require_roles("admin"))):
    org_id = admin["org_id"]
    await get_product(org_id,body.product_ref)
    if body.assessment_ref: await get_assessment(org_id,body.assessment_ref)
    issued = await issue_portal_token(org_id,body.product_ref,body.role,body.assessment_ref,body.provider_ref,body.invited_email,body.expires_hours,admin.get("email","unknown"))
    await ledger_append(org_id,admin.get("email","unknown"),"portal.invite_issued","product",body.product_ref,["Article 13","Article 32","Articles 35-51"],{"role":body.role,"assessment_ref":body.assessment_ref,"provider_ref":body.provider_ref,"expires_at":issued["expires_at"]})
    return issued

@cra_router.get("/providers")
async def list_providers(user: dict = Depends(get_current_user)):
    return await db.cra_providers.find({"org_id":user["org_id"]},{"_id":0}).sort("name",1).to_list(1000)

@cra_router.post("/providers")
async def create_provider(body: ProviderCreate, admin: dict = Depends(require_roles("admin"))):
    org_id = admin["org_id"]
    ref = await next_ref(org_id,"provider","CRA-CAB")
    record = {"org_id":org_id,"ref":ref,**body.model_dump(),"status":"Active","created_at":iso(),"created_by":admin.get("email","unknown")}
    await db.cra_providers.insert_one(record)
    record.pop("_id",None)
    await ledger_append(org_id,admin.get("email","unknown"),"provider.created","conformity_provider",ref,["Articles 35-51","Article 43"],{"name":body.name,"provider_type":body.provider_type,"nando_id":body.nando_id,"integration_mode":body.integration_mode})
    return record

@cra_router.get("/external-assessments")
async def list_external_assessments(user: dict = Depends(get_current_user)):
    return await db.cra_external_assessments.find({"org_id":user["org_id"]},{"_id":0}).sort("created_at",-1).to_list(1000)

@cra_router.post("/external-assessments")
async def create_external_assessment(body: ExternalAssessmentCreate, admin: dict = Depends(require_roles("admin"))):
    org_id = admin["org_id"]
    product = await get_product(org_id,body.product_ref)
    provider = await db.cra_providers.find_one({"org_id":org_id,"ref":body.provider_ref},{"_id":0})
    if not provider: raise HTTPException(404,"Conformity assessment provider not found")
    ref = await next_ref(org_id,"external_assessment","CRA-EXT")
    record = {"org_id":org_id,"ref":ref,**body.model_dump(),"product_name":product["name"],"provider_name":provider["name"],"status":"Requested","decision":None,"findings":[],"artifact_refs":[],"created_at":iso(),"updated_at":iso(),"created_by":admin.get("email","unknown")}
    await db.cra_external_assessments.insert_one(record)
    record.pop("_id",None)
    await ledger_append(org_id,admin.get("email","unknown"),"external_assessment.requested","external_assessment",ref,["Article 32","Articles 35-51","Annex VIII"],{"product_ref":body.product_ref,"provider_ref":body.provider_ref,"module":body.module})
    return record

@cra_router.post("/products/{ref}/sbom/generate")
async def generate_sbom(ref: str, body: SBOMGenerate, user: dict = Depends(get_current_user)):
    org_id = user["org_id"]
    product = await get_product(org_id,ref)
    components = [x.model_dump() for x in body.components]
    if not components and body.manifest_text:
        components = parse_manifest(body.manifest_type,body.manifest_text)
    if not components: raise HTTPException(400,"Provide components or a supported manifest")
    document = cyclonedx_document(product,components) if body.format == "cyclonedx-json" else spdx_document(product,components)
    sbom_ref = await next_ref(org_id,"sbom","CRA-SBOM")
    record = {"org_id":org_id,"ref":sbom_ref,"product_ref":ref,"product_version":product.get("version"),"format":body.format,"component_count":len(components),"components":components,"document":document,"created_at":iso(),"created_by":user.get("email","unknown"),"legal_refs":["Annex I Part II(1)"]}
    await db.cra_sboms.insert_one(record)
    record.pop("_id",None)
    await ledger_append(org_id,user.get("email","unknown"),"sbom.generated","sbom",sbom_ref,["Annex I Part II(1)"],{"product_ref":ref,"format":body.format,"component_count":len(components)})
    return record

@cra_router.get("/products/{ref}/sboms")
async def list_sboms(ref: str, user: dict = Depends(get_current_user)):
    await get_product(user["org_id"],ref)
    return await db.cra_sboms.find({"org_id":user["org_id"],"product_ref":ref},{"_id":0,"document":0}).sort("created_at",-1).to_list(100)

@cra_router.get("/sboms/{ref}")
async def get_sbom(ref: str, user: dict = Depends(get_current_user)):
    row = await db.cra_sboms.find_one({"org_id":user["org_id"],"ref":ref},{"_id":0})
    if not row: raise HTTPException(404,"SBOM not found")
    return row

@cra_router.get("/vulnerabilities")
async def list_vulnerabilities(user: dict = Depends(get_current_user)):
    rows = await db.cra_vulnerabilities.find({"org_id":user["org_id"]},{"_id":0}).sort("awareness_at",-1).to_list(1000)
    return [{**row,"clock":reporting_clock(row)} for row in rows]

@cra_router.post("/vulnerabilities")
async def create_vulnerability(body: VulnerabilityCreate, user: dict = Depends(get_current_user)):
    org_id = user["org_id"]
    product = await get_product(org_id,body.product_ref)
    ref = await next_ref(org_id,"vulnerability","CRA-VULN")
    record = {"org_id":org_id,"ref":ref,**body.model_dump(),"product_name":product["name"],"status":"Open","submissions":{},"created_at":iso(),"updated_at":iso(),"created_by":user.get("email","unknown")}
    await db.cra_vulnerabilities.insert_one(record)
    record.pop("_id",None)
    await ledger_append(org_id,user.get("email","unknown"),"vulnerability.created","vulnerability",ref,["Article 14","Article 16","Annex I Part II"],{"product_ref":body.product_ref,"actively_exploited":body.actively_exploited,"severe_incident":body.severe_incident,"awareness_at":body.awareness_at})
    return {**record,"clock":reporting_clock(record)}

@cra_router.post("/vulnerabilities/{ref}/submission")
async def update_submission(ref: str, body: SubmissionUpdate, user: dict = Depends(get_current_user)):
    org_id = user["org_id"]
    record = await db.cra_vulnerabilities.find_one({"org_id":org_id,"ref":ref},{"_id":0})
    if not record: raise HTTPException(404,"Vulnerability record not found")
    current = (record.get("submissions") or {}).get(body.stage,{})
    update = {**current,"state":body.state,"comment":body.comment,"updated_at":iso(),"updated_by":user.get("email","unknown")}
    if body.state in {"Submitted","Receipt Recorded"}: update["submitted_at"] = body.submitted_at or current.get("submitted_at") or iso()
    if body.receipt_id: update["receipt_id"] = body.receipt_id
    await db.cra_vulnerabilities.update_one({"org_id":org_id,"ref":ref},{"$set":{f"submissions.{body.stage}":update,"updated_at":iso()}})
    await ledger_append(org_id,user.get("email","unknown"),"regulatory_reporting.updated","vulnerability",ref,["Article 14","Article 16"],{"stage":body.stage,"state":body.state,"receipt_id":body.receipt_id})
    updated = await db.cra_vulnerabilities.find_one({"org_id":org_id,"ref":ref},{"_id":0})
    return {**updated,"clock":reporting_clock(updated)}

@cra_router.get("/vulnerabilities/{ref}/submission-package")
async def submission_package(ref: str, user: dict = Depends(get_current_user)):
    record = await db.cra_vulnerabilities.find_one({"org_id":user["org_id"],"ref":ref},{"_id":0})
    if not record: raise HTTPException(404,"Vulnerability record not found")
    product = await get_product(user["org_id"],record["product_ref"])
    return {
        "submission_target":"CRA Single Reporting Platform",
        "direct_submission_performed":False,
        "manufacturer_action_required":True,
        "legal_refs":["Article 14","Article 16"],
        "product":{"ref":product["ref"],"name":product["name"],"version":product.get("version"),"manufacturer_name":product["manufacturer_name"]},
        "event":{"ref":record["ref"],"title":record["title"],"cve":record.get("cve"),"severity":record["severity"],"description":record.get("description"),"actively_exploited":record.get("actively_exploited"),"severe_incident":record.get("severe_incident"),"awareness_at":record["awareness_at"],"corrective_measure_available_at":record.get("corrective_measure_available_at")},
        "clock":reporting_clock(record),
        "note":"Obserra prepares and tracks the CRA reporting package. Regulatory submission must be performed through the official CRA Single Reporting Platform unless a verified production API integration is configured.",
    }

@cra_router.get("/ledger")
async def regulatory_ledger(object_type: str | None = None, object_ref: str | None = None, limit: int = 250, user: dict = Depends(get_current_user)):
    query = {"org_id":user["org_id"]}
    if object_type: query["object_type"] = object_type
    if object_ref: query["object_ref"] = object_ref
    return await db.cra_regulatory_ledger.find(query,{"_id":0}).sort("sequence",-1).limit(min(max(limit,1),1000)).to_list(1000)

@cra_router.get("/products/{ref}/market-readiness")
async def market_readiness(ref: str, user: dict = Depends(get_current_user)):
    org_id = user["org_id"]
    product = await get_product(org_id,ref)
    blockers, warnings = [], []
    classification = product.get("classification") or {}
    if classification.get("classification_status") != "Approved": blockers.append("CRA classification has not been formally approved")
    assessments = await db.cra_assessments.find({"org_id":org_id,"product_ref":ref},{"_id":0}).sort("updated_at",-1).to_list(100)
    latest = assessments[0] if assessments else None
    if not latest or latest.get("status") != "Complete": blockers.append("Regulation-mapped CRA readiness assessment is incomplete")
    elif latest.get("score",0) < 100: warnings.append(f"Latest CRA readiness assessment score is {latest.get('score',0)}%")
    sbom = await db.cra_sboms.find_one({"org_id":org_id,"product_ref":ref},{"_id":0})
    if not sbom: blockers.append("No CRA SBOM artifact is recorded")
    pathway = conformity_pathway(classification.get("classification","Default"),bool(product.get("harmonised_route_complete")))
    if pathway.get("notified_body_required"):
        external = await db.cra_external_assessments.find_one({"org_id":org_id,"product_ref":ref,"decision":"Conforming"},{"_id":0})
        if not external: blockers.append("Required third-party conformity assessment has not recorded a conforming sign-off")
    vulns = await db.cra_vulnerabilities.find({"org_id":org_id,"product_ref":ref},{"_id":0}).to_list(1000)
    overdue = sum(1 for item in vulns if any(stage.get("overdue") for stage in reporting_clock(item).get("stages",[])))
    if overdue: blockers.append(f"{overdue} CRA Article 14 reporting workflow(s) are overdue")
    if product.get("support_period_years",0) < 5 and not product.get("expected_use_years"): warnings.append("Support period is below five years without an expected-use rationale recorded")
    declaration = product.get("declaration")
    if not declaration or declaration.get("status") != "Approved": blockers.append("EU Declaration of Conformity has not been approved")
    ready = not blockers
    status = "Ready" if ready else "Not Ready"
    await db.cra_products.update_one({"org_id":org_id,"ref":ref},{"$set":{"ce_status":status,"updated_at":iso()}})
    return {"product_ref":ref,"ready":ready,"ce_status":status,"blockers":blockers,"warnings":warnings,"pathway":pathway,"legal_refs":["Article 28","Article 29","Article 30","Article 31","Article 32","Annex V","Annex VII","Annex VIII"]}

@cra_router.post("/products/{ref}/declaration/draft")
async def declaration_draft(ref: str, user: dict = Depends(get_current_user)):
    product = await get_product(user["org_id"],ref)
    classification = product.get("classification") or {}
    external = await db.cra_external_assessments.find_one({"org_id":user["org_id"],"product_ref":ref,"decision":"Conforming"},{"_id":0})
    return {
        "status":"Draft","product_name":product["name"],"product_version":product.get("version"),"manufacturer_name":product["manufacturer_name"],"manufacturer_address":"",
        "unique_product_identification":product["ref"],"statement":"The declaration is issued under the sole responsibility of the manufacturer.",
        "cra_classification":classification.get("classification","Default"),
        "conformity_provider":external.get("provider_name") if external else None,
        "conformity_reference":external.get("provider_reference") if external else None,
        "harmonised_standards_or_common_specifications":[],
        "legal_refs":["Article 28","Annex V","Annex VI"],
    }

@cra_router.post("/products/{ref}/declaration/approve")
async def approve_declaration(ref: str, body: DeclarationApproval, admin: dict = Depends(require_roles("admin"))):
    org_id = admin["org_id"]
    await get_product(org_id,ref)
    declaration = {"status":"Approved",**body.model_dump(),"approved_at":iso(),"approved_by":admin.get("email","unknown"),"legal_refs":["Article 28","Annex V","Annex VI"]}
    await db.cra_products.update_one({"org_id":org_id,"ref":ref},{"$set":{"declaration":declaration,"updated_at":iso()}})
    await ledger_append(org_id,admin.get("email","unknown"),"eu_declaration.approved","product",ref,declaration["legal_refs"],declaration)
    return declaration

@cra_public_router.get("/portal/{raw_token}")
async def public_portal(raw_token: str):
    token = await verify_portal_token(raw_token)
    product = await get_product(token["org_id"],token["product_ref"])
    response = {
        "role":token["role"],"expires_at":token["expires_at"].isoformat(),
        "product":{"ref":product["ref"],"name":product["name"],"version":product.get("version"),"manufacturer_name":product["manufacturer_name"],"description":product.get("description"),"classification":product.get("classification")},
        "regulation":{"regulation":CRA_VERSION,"classification_implementing_regulation":CLASSIFICATION_VERSION,"requirements":REGULATORY_REQUIREMENTS},
    }
    if token.get("assessment_ref"): response["assessment"] = await get_assessment(token["org_id"],token["assessment_ref"])
    if token.get("provider_ref"):
        response["provider"] = await db.cra_providers.find_one({"org_id":token["org_id"],"ref":token["provider_ref"]},{"_id":0,"contact_email":0})
        response["external_assessments"] = await db.cra_external_assessments.find({"org_id":token["org_id"],"product_ref":token["product_ref"],"provider_ref":token["provider_ref"]},{"_id":0}).to_list(100)
    return response

@cra_public_router.put("/portal/{raw_token}/assessment")
async def portal_update_assessment(raw_token: str, body: AssessmentUpdate):
    token = await verify_portal_token(raw_token)
    if token["role"] != "vendor" or not token.get("assessment_ref"): raise HTTPException(403,"Portal link does not permit vendor readiness assessment")
    current = await get_assessment(token["org_id"],token["assessment_ref"])
    allowed = {x["requirement_id"] for x in REGULATORY_REQUIREMENTS}
    incoming = {a.requirement_id:a.model_dump() for a in body.answers if a.requirement_id in allowed}
    answers = [incoming.get(x["requirement_id"],x) for x in current.get("answers",[])]
    score = assessment_score(answers)
    status = "Complete" if all(a["status"] != "Not Assessed" for a in answers) else "In Progress"
    await db.cra_assessments.update_one({"org_id":token["org_id"],"ref":token["assessment_ref"]},{"$set":{"answers":answers,"score":score,"status":status,"updated_at":iso(),"portal_submitted_at":iso()}})
    await ledger_append(token["org_id"],token.get("invited_email") or "external-vendor","portal.assessment_updated","assessment",token["assessment_ref"],["Article 6","Article 13","Annex I"],{"score":score,"status":status})
    return await get_assessment(token["org_id"],token["assessment_ref"])

@cra_public_router.post("/portal/{raw_token}/signoff/{external_ref}")
async def portal_external_signoff(raw_token: str, external_ref: str, body: ExternalSignoff):
    token = await verify_portal_token(raw_token)
    if token["role"] != "external_assessor" or not token.get("provider_ref"): raise HTTPException(403,"Portal link does not permit external conformity sign-off")
    record = await db.cra_external_assessments.find_one({"org_id":token["org_id"],"ref":external_ref,"provider_ref":token["provider_ref"],"product_ref":token["product_ref"]},{"_id":0})
    if not record: raise HTTPException(404,"External assessment request not found")
    update = {"status":body.decision,"decision":body.decision,"assessor_name":body.assessor_name,"provider_reference":body.provider_reference,"findings":body.findings,"artifact_refs":body.artifact_refs,"comment":body.comment,"signed_at":iso(),"updated_at":iso()}
    await db.cra_external_assessments.update_one({"org_id":token["org_id"],"ref":external_ref},{"$set":update})
    await ledger_append(token["org_id"],token.get("invited_email") or body.assessor_name,"external_assessment.signed","external_assessment",external_ref,["Article 32","Articles 35-51","Annex VIII"],update)
    return await db.cra_external_assessments.find_one({"org_id":token["org_id"],"ref":external_ref},{"_id":0})


# ===========================================================================
# CRA-grounded AI Analyst — a concise executive summary of the org's live EU
# CRA posture (classification, overdue Article 14 clocks, CE blockers). Grounded
# strictly in the live CRA records; never mentions unrelated governance domains.
# ===========================================================================
_CRA_INSIGHT_CACHE: dict = {}

# Key statutory CRA milestones (Regulation (EU) 2024/2847) in chronological order.
_CRA_MILESTONES = [
    ("2026-06-11", "conformity-assessment-body notification provisions apply (Chapter IV)"),
    ("2026-09-11", "Article 14 vulnerability & incident reporting obligations apply"),
    ("2027-12-11", "general application — full CRA obligations & CE marking"),
]


def _cra_next_deadline() -> dict | None:
    today = utcnow().date()
    for d, label in _CRA_MILESTONES:
        due = datetime.strptime(d, "%Y-%m-%d").date()
        if due >= today:
            return {"date": d, "label": label, "days_remaining": (due - today).days}
    return None


async def _cra_insight_context(org_id: str) -> dict:
    products = await db.cra_products.find({"org_id": org_id}, {"_id": 0}).to_list(1000)
    assessments = await db.cra_assessments.find({"org_id": org_id}, {"_id": 0}).to_list(1000)
    vulnerabilities = await db.cra_vulnerabilities.find({"org_id": org_id}, {"_id": 0}).to_list(1000)
    sbom_refs = {s.get("product_ref") for s in await db.cra_sboms.find({"org_id": org_id}, {"_id": 0, "product_ref": 1}).to_list(2000)}
    latest_assessment = {}
    for a in sorted(assessments, key=lambda x: x.get("updated_at", ""), reverse=True):
        latest_assessment.setdefault(a.get("product_ref"), a)
    by_class = {"Default": 0, "Class I": 0, "Class II": 0, "Critical": 0}
    approved = ce_ready = 0
    blockers = []
    for p in products:
        cl = p.get("classification") or {}
        cls = cl.get("classification", "Default")
        by_class[cls] = by_class.get(cls, 0) + 1
        if cl.get("classification_status") == "Approved":
            approved += 1
        if p.get("ce_status") == "Ready":
            ce_ready += 1
        prod_blk = []
        if cl.get("classification_status") != "Approved":
            prod_blk.append("classification not approved")
        la = latest_assessment.get(p["ref"])
        if not la or la.get("status") != "Complete":
            prod_blk.append("readiness assessment incomplete")
        if p["ref"] not in sbom_refs:
            prod_blk.append("no SBOM")
        if (p.get("declaration") or {}).get("status") != "Approved":
            prod_blk.append("EU declaration not approved")
        if prod_blk:
            blockers.append({"product": p["name"], "ref": p["ref"], "classification": cls, "blockers": prod_blk})
    overdue = []
    for v in vulnerabilities:
        for st in reporting_clock(v).get("stages", []):
            if st.get("overdue"):
                overdue.append({"product": v.get("product_name"), "vuln": v.get("ref"), "title": v.get("title"),
                                "stage": st["stage"], "hours_overdue": round(-st.get("hours_remaining", 0), 1)})
    scores = [a.get("score", 0) for a in assessments if a.get("score") is not None]
    return {
        "regulation": CRA_VERSION,
        "reporting_effective_date": REPORTING_EFFECTIVE_DATE,
        "general_application_date": GENERAL_APPLICATION_DATE,
        "totals": {"products": len(products), "classification_approved": approved, "ce_ready": ce_ready,
                   "average_readiness": round(sum(scores) / len(scores)) if scores else 0},
        "by_class": by_class,
        "ce_blockers": blockers[:20],
        "overdue_article14": overdue[:20],
        "counts": {"products": len(products), "blocked": len(blockers), "overdue_clocks": len(overdue),
                   "assessments": len(assessments), "vulnerabilities": len(vulnerabilities)},
        "next_deadline": _cra_next_deadline(),
    }


def _cra_insight_fallback(ctx: dict) -> dict:
    t = ctx["totals"]
    insights = [{"text": f"{t['products']} product(s) under CRA governance — {t['classification_approved']} with an approved classification, {t['ce_ready']} CE market-ready. Class split: {ctx['by_class']}.", "kind": "fact"}]
    if ctx["overdue_article14"]:
        top = ctx["overdue_article14"][0]
        insights.append({"text": f"{len(ctx['overdue_article14'])} Article 14 reporting stage(s) are OVERDUE — e.g. {top['product']} · {top['stage']} ({top['hours_overdue']}h past deadline).", "kind": "risk"})
    else:
        insights.append({"text": "No Article 14 reporting stages are currently overdue.", "kind": "fact"})
    if ctx["ce_blockers"]:
        insights.append({"text": f"{len(ctx['ce_blockers'])} product(s) have open CE-marking blockers (classification approval, readiness assessment, SBOM or EU declaration).", "kind": "estimate"})
    insights.append({"text": f"Average regulation-mapped readiness across assessments is {t['average_readiness']}%.", "kind": "estimate"})
    actions = []
    if ctx["overdue_article14"]:
        actions.append("Resolve overdue Article 14 reporting stages first — they carry statutory deadlines.")
    if ctx["ce_blockers"]:
        actions.append("Clear CE-marking blockers: approve classifications, complete assessments, generate SBOMs and approve EU declarations.")
    actions.append("Review products still on a Proposed classification and record formal approval.")
    nd = ctx.get("next_deadline")
    headline = f"{t['products']} products under EU CRA governance · {ctx['counts']['blocked']} with CE blockers · {ctx['counts']['overdue_clocks']} overdue Article 14 clocks"
    if nd:
        headline = f"{nd['days_remaining']} days to the next CRA deadline ({nd['date']} — {nd['label']}): {headline}"
        insights.insert(0, {"text": f"Nearest statutory CRA deadline: {nd['label']} on {nd['date']} — {nd['days_remaining']} days away.",
                            "kind": "risk" if nd["days_remaining"] <= 120 else "fact"})
    return {"headline": headline,
            "insights": insights[:5], "actions": actions[:4], "model": "obserra/cra-grounded", "generated_at": iso()}


async def compute_cra_insight(org_id: str, use_cache: bool = True) -> dict:
    import os
    import asyncio
    ctx = await _cra_insight_context(org_id)
    nd = ctx.get("next_deadline")
    ck = (org_id, ctx["counts"]["products"], ctx["counts"]["blocked"], ctx["counts"]["overdue_clocks"],
          ctx["totals"]["classification_approved"], ctx["totals"]["ce_ready"], ctx["totals"]["average_readiness"])
    if use_cache:
        hit = _CRA_INSIGHT_CACHE.get(ck)
        if hit and (utcnow() - hit["ts"]).total_seconds() < 120:
            return hit["data"]
    if ctx["counts"]["products"] == 0:
        lead = f"{nd['days_remaining']} days to the next CRA deadline ({nd['date']} — {nd['label']}). " if nd else ""
        data = {"headline": f"{lead}No products under EU CRA governance yet.",
                "insights": [{"text": "Register a product with digital elements to begin CRA classification, assessment and CE readiness.", "kind": "fact"}],
                "actions": ["Register your first product from Products & Classification.", "Load sample products to explore the workflow."],
                "next_deadline": nd, "model": "obserra/cra-grounded", "generated_at": iso()}
        _CRA_INSIGHT_CACHE[ck] = {"ts": utcnow(), "data": data}
        return data
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage, TextDelta, StreamDone
        system = (
            "You are the Obserra EU CRA Governance AI Analyst. Read the LIVE EU Cyber Resilience Act posture JSON "
            "and return a concise, executive compliance briefing STRICTLY as JSON: {\"headline\": str, \"insights\": "
            "[{\"text\": str, \"kind\": one of \"fact\"|\"estimate\"|\"risk\"}], \"actions\": [str]}. 3-5 insights, "
            "2-4 actions. OPEN the headline with the countdown to the nearest statutory deadline in next_deadline, "
            "phrased like 'N days to <label> on <date>'. Ground EVERY statement in the data — cite product counts, "
            "classification split, named CE blockers and overdue Article 14 reporting stages with hours overdue. This "
            "is EU CRA (Regulation (EU) 2024/2847) product-compliance guidance: NEVER mention SAP access, SoD "
            "conflicts, cyber-incident crisis data or any unrelated governance domain. Return ONLY the JSON object.")
        chat = LlmChat(api_key=os.environ["EMERGENT_LLM_KEY"], session_id=f"cra-insight-{org_id}",
                       system_message=system).with_model("openai", "gpt-5.4")
        prompt = f"LIVE EU CRA POSTURE (JSON):\n{json.dumps(ctx, default=str)[:9000]}"
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
            data = _cra_insight_fallback(ctx)
        else:
            parsed.setdefault("actions", [])
            if nd and nd["date"] not in (parsed.get("headline") or ""):
                parsed["headline"] = f"{nd['days_remaining']} days to the next CRA deadline ({nd['date']} — {nd['label']}): {parsed.get('headline', '')}".strip()
            parsed["next_deadline"] = nd
            parsed["model"] = "openai/gpt-5.4"
            parsed["generated_at"] = iso()
            data = parsed
    except Exception:
        data = _cra_insight_fallback(ctx)
    data.setdefault("next_deadline", nd)
    _CRA_INSIGHT_CACHE[ck] = {"ts": utcnow(), "data": data}
    return data


@cra_router.get("/insight")
async def cra_insight(user: dict = Depends(get_current_user)):
    return await compute_cra_insight(user["org_id"])


# ===========================================================================
# Sample products — create a small set of REAL, editable CRA product records so
# the dashboard tells a fuller story on first open. Idempotent; marked sample:True.
# ===========================================================================
_SAMPLE_PRODUCTS = [
    {"name": "Aegis Identity Broker", "version": "4.1", "manufacturer_name": "Aegis Security GmbH",
     "description": "Enterprise identity and privileged access management with biometric authentication readers.",
     "core_functionality": "identity management and privileged access management with authentication", "category_codes": ["I-01"], "support_period_years": 8},
    {"name": "Sentinel Web Firewall", "version": "12.0", "manufacturer_name": "Sentinel Networks Ltd",
     "description": "Next-generation firewall with intrusion detection and prevention.",
     "core_functionality": "firewall intrusion detection and prevention system", "category_codes": ["II-02"], "support_period_years": 7},
    {"name": "HomeGuard Smart Lock", "version": "2.3", "manufacturer_name": "HomeGuard IoT S.A.",
     "description": "Connected smart door lock with companion mobile app and security camera integration.",
     "core_functionality": "smart lock and smart home security device", "category_codes": ["I-17"], "support_period_years": 5},
    {"name": "VaultCore Secure Element", "version": "1.0", "manufacturer_name": "VaultCore Microelectronics",
     "description": "Tamper-resistant secure element for cryptographic key storage.",
     "core_functionality": "secure element with secure cryptoprocessing", "category_codes": ["CRIT-03"], "support_period_years": 10},
    {"name": "NoteFlow Productivity Suite", "version": "3.5", "manufacturer_name": "NoteFlow Software Inc.",
     "description": "Team note-taking and productivity application.",
     "core_functionality": "note taking and productivity", "category_codes": [], "support_period_years": 5},
]


async def _seed_sample_product(org_id: str, actor: str, spec: dict) -> dict:
    ref = await next_ref(org_id, "product", "CRA-PROD")
    body = ProductCreate(**spec)
    product = {"org_id": org_id, "ref": ref, **body.model_dump(), "classification": {}, "ce_status": "Not Ready",
               "declaration": None, "sample": True, "created_at": iso(), "updated_at": iso(), "created_by": actor}
    result = classify_product_record(product)
    product["classification"] = result
    await db.cra_products.insert_one(product)
    product.pop("_id", None)
    await ledger_append(org_id, actor, "product.created", "product", ref, ["Article 13", "Article 31"], {"name": body.name, "version": body.version, "sample": True})
    await ledger_append(org_id, actor, "classification.proposed", "product", ref, result["legal_refs"], result)
    return product


@cra_router.post("/demo/seed")
async def seed_sample_products(admin: dict = Depends(require_roles("admin"))):
    org_id = admin["org_id"]
    actor = admin.get("email", "unknown")
    if await db.cra_products.find_one({"org_id": org_id, "sample": True}, {"_id": 0, "ref": 1}):
        return {"ok": True, "created": 0, "note": "Sample products already present."}
    created = []
    for spec in _SAMPLE_PRODUCTS:
        p = await _seed_sample_product(org_id, actor, spec)
        created.append(p["ref"])
    if created:
        first = created[0]
        aref = await next_ref(org_id, "assessment", "CRA-ASMT")
        answers = [{"requirement_id": r["requirement_id"], "status": "Conforming" if i % 3 else "Partial", "evidence_refs": [], "comment": ""} for i, r in enumerate(REGULATORY_REQUIREMENTS)]
        score = assessment_score(answers)
        await db.cra_assessments.insert_one({"org_id": org_id, "ref": aref, "product_ref": first, "product_name": _SAMPLE_PRODUCTS[0]["name"], "answers": answers, "score": score, "status": "In Progress", "sample": True, "created_at": iso(), "updated_at": iso(), "created_by": actor})
        await ledger_append(org_id, actor, "assessment.initialized", "assessment", aref, ["Article 6", "Article 13", "Annex I", "Annex VII"], {"product_ref": first, "sample": True})
        pfirst = await get_product(org_id, first)
        comps = parse_manifest("requirements.txt", "fastapi==0.110\npydantic>=2.0\nmotor==3.4\ncryptography==42.0")
        sref = await next_ref(org_id, "sbom", "CRA-SBOM")
        await db.cra_sboms.insert_one({"org_id": org_id, "ref": sref, "product_ref": first, "product_version": pfirst.get("version"), "format": "cyclonedx-json", "component_count": len(comps), "components": comps, "document": cyclonedx_document(pfirst, comps), "sample": True, "created_at": iso(), "created_by": actor})
        await ledger_append(org_id, actor, "sbom.generated", "sbom", sref, ["Annex I Part II(1)"], {"product_ref": first, "format": "cyclonedx-json", "component_count": len(comps), "sample": True})
    await audit(org_id, actor, "cra.demo.seed", f"{len(created)} sample products")
    return {"ok": True, "created": len(created), "product_refs": created}


@cra_router.delete("/demo/seed")
async def clear_sample_products(admin: dict = Depends(require_roles("admin"))):
    org_id = admin["org_id"]
    refs = [p["ref"] for p in await db.cra_products.find({"org_id": org_id, "sample": True}, {"_id": 0, "ref": 1}).to_list(1000)]
    await db.cra_products.delete_many({"org_id": org_id, "sample": True})
    await db.cra_assessments.delete_many({"org_id": org_id, "sample": True})
    await db.cra_sboms.delete_many({"org_id": org_id, "sample": True})
    await db.cra_vulnerabilities.delete_many({"org_id": org_id, "sample": True})
    await audit(org_id, admin.get("email", "unknown"), "cra.demo.clear", f"{len(refs)} sample products")
    return {"ok": True, "removed": len(refs)}


# ===========================================================================
# Auditor verification link — a one-click, tamper-evident public link a notified
# body can use to independently confirm a product's CRA compliance timeline and
# ledger-chain integrity. The private Internal Regulatory Ledger data is redacted.
# ===========================================================================
async def _verify_ledger_chain(org_id: str):
    rows = await db.cra_regulatory_ledger.find({"org_id": org_id}, {"_id": 0}).sort("sequence", 1).to_list(100000)
    intact, break_at, prev = True, None, ""
    for r in rows:
        payload = {k: v for k, v in r.items() if k != "record_hash"}
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
        recomputed = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        if recomputed != r.get("record_hash", "") or r.get("prev_hash", "") != prev:
            intact, break_at = False, r.get("sequence")
            break
        prev = r.get("record_hash", "")
    return {"chain_intact": intact, "records_verified": len(rows), "break_at_sequence": break_at}, rows


@cra_router.post("/products/{ref}/verification-link")
async def create_verification_link(ref: str, admin: dict = Depends(require_roles("admin"))):
    org_id = admin["org_id"]
    await get_product(org_id, ref)
    active = await db.cra_portal_tokens.count_documents(
        {"org_id": org_id, "product_ref": ref, "role": "auditor", "revoked_at": None, "expires_at": {"$gt": utcnow()}})
    if active >= 5:
        raise HTTPException(429, "This product already has 5 active auditor links. Revoke or wait for existing links to expire before minting more.")
    issued = await issue_portal_token(org_id, ref, "auditor", None, None, "", 720, admin.get("email", "unknown"))
    await ledger_append(org_id, admin.get("email", "unknown"), "verification_link.issued", "product", ref, ["Article 28", "Article 31"], {"expires_at": issued["expires_at"]})
    return {"token": issued["token"], "expires_at": issued["expires_at"], "path": f"/cra-verify/{issued['token']}"}


@cra_public_router.get("/verify/{raw_token}")
async def public_verify(raw_token: str):
    token = await verify_portal_token(raw_token)
    if token.get("role") != "auditor":
        raise HTTPException(403, "This link is not an auditor verification link")
    org_id = token["org_id"]
    product = await get_product(org_id, token["product_ref"])
    integrity, rows = await _verify_ledger_chain(org_id)
    pref = token["product_ref"]
    await db.cra_products.update_one(
        {"org_id": org_id, "ref": pref},
        {"$set": {"last_verification_view_at": iso()}, "$inc": {"verification_view_count": 1}})
    timeline = [
        {"sequence": r["sequence"], "ts": r["ts"], "event_type": r["event_type"], "object_type": r["object_type"],
         "object_ref": r["object_ref"], "legal_refs": r.get("legal_refs", []), "actor": r.get("actor"),
         "record_hash": r.get("record_hash"), "prev_hash": r.get("prev_hash")}
        for r in rows
        if r.get("object_ref") == pref or (isinstance(r.get("data"), dict) and r["data"].get("product_ref") == pref)
    ]
    cl = product.get("classification") or {}
    return {
        "role": "auditor",
        "expires_at": token["expires_at"].isoformat(),
        "regulation": CRA_VERSION,
        "classification_implementing_regulation": CLASSIFICATION_VERSION,
        "verified_at": iso(),
        "product": {"ref": product["ref"], "name": product["name"], "version": product.get("version"),
                    "manufacturer_name": product["manufacturer_name"],
                    "classification": cl.get("classification", "Default"),
                    "classification_status": cl.get("classification_status", "Proposed"),
                    "pathway": (cl.get("pathway") or {}).get("pathway"),
                    "ce_status": product.get("ce_status"),
                    "declaration_status": (product.get("declaration") or {}).get("status")},
        "integrity": integrity,
        "timeline": timeline,
        "note": "Read-only, tamper-evident verification view. The private Internal Regulatory Ledger payloads are not exposed; only event metadata and hash-chain integrity are shown.",
    }


# ===========================================================================
# CRA AI Analyst — weekly executive email digest. Wired into the platform's
# existing weekly cron (see scheduled.py). Only orgs with CRA products are sent.
# ===========================================================================
def _cra_analyst_digest_html(org_name: str, insight: dict, ctx: dict) -> str:
    t = ctx["totals"]
    nd = insight.get("next_deadline") or ctx.get("next_deadline")

    def esc(s):
        return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    tone = {"fact": "#0f1e3d", "estimate": "#12b4d6", "risk": "#dc2626"}
    ins_rows = "".join(
        f'<tr><td style="padding:6px 0;border-bottom:1px solid #eef2f7;font:400 13px Arial;color:#1f2937">'
        f'<span style="font:700 9px Arial;letter-spacing:.05em;color:{tone.get(i.get("kind"), "#0f1e3d")}">'
        f'{esc((i.get("kind") or "fact").upper())}</span><br>{esc(i.get("text", ""))}</td></tr>'
        for i in insight.get("insights", []))
    act_rows = "".join(
        f'<tr><td style="padding:6px 0;font:400 13px Arial;color:#1f2937">&#8226; {esc(a)}</td></tr>'
        for a in insight.get("actions", []))
    deadline_banner = ""
    if nd:
        deadline_banner = (
            '<div style="background:#fff7ed;border:1px solid #fed7aa;border-radius:8px;padding:12px 14px;margin:12px 0;'
            f'font:600 13px Arial;color:#b45309">{nd["days_remaining"]} days to the next CRA deadline &#8212; '
            f'{esc(nd["label"])} on {esc(nd["date"])}.</div>')
    return (
        '<table width="100%" cellpadding="0" cellspacing="0" style="max-width:620px;margin:auto;background:#fff">'
        '<tr><td style="padding:24px">'
        '<div style="font:800 18px Arial;color:#0f1e3d">CRA AI Analyst &#8212; Weekly Briefing</div>'
        f'<div style="font:400 12px Arial;color:#6b7280;margin-bottom:6px">{esc(org_name)} &#183; Obserra EU CRA Governance</div>'
        f'<div style="font:700 15px Arial;color:#0f1e3d;margin:12px 0 4px">{esc(insight.get("headline", ""))}</div>'
        f'{deadline_banner}'
        f'<div style="font:400 12px Arial;color:#374151;margin:8px 0">Products <b>{t["products"]}</b> &#183; CE-ready '
        f'<b>{t["ce_ready"]}</b> &#183; Blocked <b>{ctx["counts"]["blocked"]}</b> &#183; Overdue Art.14 '
        f'<b>{ctx["counts"]["overdue_clocks"]}</b> &#183; Avg readiness <b>{t["average_readiness"]}%</b></div>'
        '<div style="font:700 11px Arial;color:#6b7280;letter-spacing:.05em;margin-top:14px">KEY INSIGHTS</div>'
        f'<table width="100%">{ins_rows}</table>'
        '<div style="font:700 11px Arial;color:#6b7280;letter-spacing:.05em;margin-top:14px">RECOMMENDED ACTIONS</div>'
        f'<table width="100%">{act_rows}</table>'
        '<div style="border-top:1px solid #e5e7eb;margin-top:16px;padding-top:10px;font:400 10px Arial;color:#9ca3af">'
        'Grounded in your live product records. Sign in to Obserra EU CRA Governance for the full board view. '
        'Decision-support only &#8212; not legal advice or a guarantee of CRA conformity.</div>'
        '</td></tr></table>')


def _cra_exec_brief_pdf(org_name, ctx, insight):
    from io import BytesIO
    from reportlab.lib.pagesizes import LETTER
    from reportlab.lib.units import inch
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable

    def x(s):
        return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    buf = BytesIO()
    styles = getSampleStyleSheet()
    navy = colors.HexColor("#0f1e3d"); ai = colors.HexColor("#12b4d6")
    title = ParagraphStyle("t", parent=styles["Title"], fontSize=18, textColor=navy, spaceAfter=2)
    sub = ParagraphStyle("s", parent=styles["Normal"], fontSize=9, textColor=colors.grey)
    h = ParagraphStyle("h", parent=styles["Heading2"], fontSize=12, textColor=ai, spaceBefore=10, spaceAfter=4)
    body = ParagraphStyle("b", parent=styles["BodyText"], fontSize=10, leading=14)
    t = ctx["totals"]; nd = insight.get("next_deadline") or ctx.get("next_deadline")
    doc = SimpleDocTemplate(buf, pagesize=LETTER, topMargin=0.7 * inch, bottomMargin=0.7 * inch, title="EU CRA Executive Brief")
    story = [Paragraph("EU CRA Governance &#8212; Executive Brief", title),
             Paragraph(f"{x(org_name)} &#183; Regulation (EU) 2024/2847 &#183; {datetime.now().strftime('%d %B %Y')}", sub),
             HRFlowable(width="100%", color=ai), Spacer(1, 8),
             Paragraph(x(insight.get("headline", "")), body)]
    if nd:
        story.append(Paragraph(f"<b>Next statutory deadline:</b> {x(nd['label'])} on {nd['date']} ({nd['days_remaining']} days).", body))
    story.append(Paragraph("Portfolio posture", h))
    rows = [["Products", str(t["products"])], ["Classification approved", str(t["classification_approved"])],
            ["CE-ready", str(t["ce_ready"])], ["CE blockers", str(ctx["counts"]["blocked"])],
            ["Overdue Article 14 clocks", str(ctx["counts"]["overdue_clocks"])], ["Average readiness", f"{t['average_readiness']}%"]]
    tbl = Table(rows, colWidths=[3.2 * inch, 3.0 * inch])
    tbl.setStyle(TableStyle([("FONTSIZE", (0, 0), (-1, -1), 10), ("TEXTCOLOR", (0, 0), (0, -1), navy),
                             ("LINEBELOW", (0, 0), (-1, -1), 0.3, colors.HexColor("#e5e7eb")),
                             ("BOTTOMPADDING", (0, 0), (-1, -1), 5), ("TOPPADDING", (0, 0), (-1, -1), 5)]))
    story += [tbl, Paragraph("Key insights", h)]
    for i in insight.get("insights", [])[:5]:
        story.append(Paragraph(f"<b>{x((i.get('kind') or 'fact').upper())}:</b> {x(i.get('text', ''))}", body))
    story.append(Paragraph("Recommended actions", h))
    for a in insight.get("actions", [])[:5]:
        story.append(Paragraph(f"&#8226; {x(a)}", body))
    story += [Spacer(1, 10), HRFlowable(width="100%", color=colors.HexColor("#e5e7eb")),
              Paragraph("Compiled live from Obserra records. Classifications are proposed until authorised approval. Decision-support only &#8212; not legal advice or a guarantee of CRA conformity.", sub)]
    doc.build(story)
    return buf.getvalue()


async def _cra_digest_recipients(org_id: str) -> list[dict]:
    users = await db.users.find(
        {"org_id": org_id, "role": {"$in": ["admin", "executive"]}},
        {"_id": 0, "email": 1, "cra_digest_optin": 1}).to_list(200)
    return [u for u in users if u.get("cra_digest_optin", True)]


async def _send_cra_digest(org: dict, recipients: list[dict], attach_pdf: bool = True) -> int:
    import base64
    from kernel import notifications
    org_id = str(org["_id"])
    ctx = await _cra_insight_context(org_id)
    insight = await compute_cra_insight(org_id, use_cache=False)
    html = _cra_analyst_digest_html(org.get("name", "Your organization"), insight, ctx)
    att = None
    if attach_pdf:
        try:
            raw = _cra_exec_brief_pdf(org.get("name", "Your organization"), ctx, insight)
            att = [{"filename": "obserra-eu-cra-weekly-brief.pdf", "content": base64.b64encode(raw).decode()}]
        except Exception:
            att = None
    sent = 0
    for r in recipients:
        await notifications.send_email(r["email"], "CRA AI Analyst — your weekly EU CRA briefing", html, attachments=att)
        sent += 1
    return sent


async def _run_cra_analyst_digest_tick():
    """Hourly gate: send each org's weekly CRA briefing at its configured UTC day + hour."""
    import logging
    from kernel import notifications
    logger = logging.getLogger("obserra.cra")
    now = utcnow()
    week_key = now.strftime("%G-W%V")
    orgs = await db.organizations.find({}).to_list(1000)
    for org in orgs:
        org_id = str(org["_id"])
        try:
            cfg = org.get("cra_digest") or {}
            if not cfg.get("enabled", True):
                continue
            if int(cfg.get("day_of_week", 0)) != now.weekday() or int(cfg.get("hour_utc", 8)) != now.hour:
                continue
            if cfg.get("last_sent_week") == week_key:
                continue
            if not await db.cra_products.find_one({"org_id": org_id}, {"_id": 0, "ref": 1}):
                continue
            recipients = await _cra_digest_recipients(org_id)
            if recipients:
                sent = await _send_cra_digest(org, recipients, attach_pdf=True)
                await notifications.create(
                    org_id, "report", "CRA AI Analyst weekly briefing sent",
                    f"Emailed the EU CRA executive briefing to {sent} recipient(s).", ref="cra-analyst-digest")
                logger.info(f"CRA analyst digest sent for org {org_id}: {sent} recipient(s)")
            await db.organizations.update_one({"_id": org["_id"]}, {"$set": {"cra_digest.last_sent_week": week_key}})
        except Exception as e:
            logger.error(f"CRA analyst digest tick failed for org {org_id}: {e}")


class CRADigestSchedule(BaseModel):
    enabled: bool = True
    day_of_week: int = Field(0, ge=0, le=6)
    hour_utc: int = Field(8, ge=0, le=23)


class CRADigestOptin(BaseModel):
    optin: bool


@cra_router.get("/digest/settings")
async def get_digest_settings(user: dict = Depends(get_current_user)):
    from bson import ObjectId
    org = await db.organizations.find_one({"_id": ObjectId(user["org_id"])}, {"_id": 0, "cra_digest": 1})
    cfg = (org or {}).get("cra_digest") or {}
    return {"schedule": {"enabled": cfg.get("enabled", True), "day_of_week": int(cfg.get("day_of_week", 0)), "hour_utc": int(cfg.get("hour_utc", 8))},
            "optin": user.get("cra_digest_optin", True), "is_admin": user.get("role") == "admin",
            "last_sent_week": cfg.get("last_sent_week")}


@cra_router.put("/digest/settings")
async def update_digest_settings(body: CRADigestSchedule, admin: dict = Depends(require_roles("admin"))):
    from bson import ObjectId
    await db.organizations.update_one({"_id": ObjectId(admin["org_id"])}, {"$set": {
        "cra_digest.enabled": body.enabled, "cra_digest.day_of_week": body.day_of_week, "cra_digest.hour_utc": body.hour_utc}})
    return {"ok": True, "schedule": body.model_dump()}


@cra_router.put("/digest/optin")
async def update_digest_optin(body: CRADigestOptin, user: dict = Depends(get_current_user)):
    from bson import ObjectId
    await db.users.update_one({"_id": ObjectId(user["id"])}, {"$set": {"cra_digest_optin": body.optin}})
    return {"ok": True, "optin": body.optin}


@cra_router.post("/digest/send-now")
async def send_digest_now(user: dict = Depends(get_current_user)):
    from bson import ObjectId
    if not await db.cra_products.find_one({"org_id": user["org_id"]}, {"_id": 0, "ref": 1}):
        raise HTTPException(400, "Add or load a CRA product first — there is nothing to brief yet.")
    org = await db.organizations.find_one({"_id": ObjectId(user["org_id"])})
    await _send_cra_digest(org, [{"email": user["email"]}], attach_pdf=True)
    return {"ok": True, "sent_to": user["email"]}


@cra_router.get("/digest/brief.pdf")
async def download_digest_brief(user: dict = Depends(get_current_user)):
    from fastapi.responses import Response
    from bson import ObjectId
    org_id = user["org_id"]
    if not await db.cra_products.find_one({"org_id": org_id}, {"_id": 0, "ref": 1}):
        raise HTTPException(400, "Add or load a CRA product first — there is nothing to brief yet.")
    org = await db.organizations.find_one({"_id": ObjectId(org_id)})
    ctx = await _cra_insight_context(org_id)
    insight = await compute_cra_insight(org_id)
    pdf = _cra_exec_brief_pdf((org or {}).get("name", "Your organization"), ctx, insight)
    return Response(content=pdf, media_type="application/pdf",
                    headers={"Content-Disposition": "attachment; filename=obserra-eu-cra-weekly-brief.pdf"})


@cra_router.post("/scorecard-link")
async def create_scorecard_link(admin: dict = Depends(require_roles("admin"))):
    org_id = admin["org_id"]
    active = await db.cra_portal_tokens.count_documents(
        {"org_id": org_id, "role": "scorecard", "revoked_at": None, "expires_at": {"$gt": utcnow()}})
    if active >= 5:
        raise HTTPException(429, "This organisation already has 5 active scorecard links. Revoke or wait for existing links to expire before minting more.")
    issued = await issue_portal_token(org_id, "", "scorecard", None, None, "", 720, admin.get("email", "unknown"))
    await ledger_append(org_id, admin.get("email", "unknown"), "scorecard_link.issued", "organization", org_id, ["Article 13"], {"expires_at": issued["expires_at"]})
    return {"token": issued["token"], "expires_at": issued["expires_at"], "path": f"/cra-scorecard/{issued['token']}"}


@cra_public_router.get("/scorecard/{raw_token}")
async def public_scorecard(raw_token: str):
    from bson import ObjectId
    token = await verify_portal_token(raw_token)
    if token.get("role") != "scorecard":
        raise HTTPException(403, "This link is not a compliance scorecard link")
    org_id = token["org_id"]
    computed = await _compute_controls(org_id)
    org = await db.organizations.find_one({"_id": ObjectId(org_id)}, {"_id": 0, "name": 1})
    gaps = [{"requirement_id": c["requirement_id"], "domain": c["domain"], "title": c["title"],
             "compliance_rate": c["compliance_rate"], "status": c["status"], "risk": c["risk"],
             "conforming": c["conforming"], "partial": c["partial"], "nonconforming": c["nonconforming"], "assessed": c["assessed"]}
            for c in computed["controls"] if c["status"] in ("Gap", "Partial", "Not Started") or c["risk"] == "High"]
    gaps.sort(key=lambda c: (c["compliance_rate"] if c["compliance_rate"] is not None else -1))
    return {"role": "scorecard", "organization": (org or {}).get("name", "Organization"),
            "regulation": CRA_VERSION, "generated_at": iso(), "expires_at": token["expires_at"].isoformat(),
            "overall": computed["overall"], "top_gaps": gaps[:8], "next_deadline": _cra_next_deadline(),
            "note": "Read-only compliance scorecard. Product names and internal records are not exposed."}


class CRAControlAssignment(BaseModel):
    owner: str = Field(default="", max_length=180)
    due_date: str = Field(default="", max_length=40)
    status: str = Field(default="Open", max_length=20)
    note: str = Field(default="", max_length=1000)


@cra_router.put("/controls/{requirement_id}/assignment")
async def set_control_assignment(requirement_id: str, body: CRAControlAssignment, user: dict = Depends(get_current_user)):
    if requirement_id not in {r["requirement_id"] for r in REGULATORY_REQUIREMENTS}:
        raise HTTPException(404, "Unknown control requirement")
    status = body.status if body.status in ("Open", "In Progress", "Closed") else "Open"
    org_id = user["org_id"]
    doc = {"org_id": org_id, "requirement_id": requirement_id, "owner": body.owner.strip(),
           "due_date": body.due_date.strip(), "status": status, "note": body.note.strip(),
           "updated_at": iso(), "updated_by": user.get("email", "unknown")}
    await db.cra_control_owners.update_one({"org_id": org_id, "requirement_id": requirement_id}, {"$set": doc}, upsert=True)
    await ledger_append(org_id, user.get("email", "unknown"), "control.assignment", "control", requirement_id, [],
                        {"owner": doc["owner"], "due_date": doc["due_date"], "status": doc["status"]})
    return {"ok": True, "assignment": {k: doc[k] for k in ("owner", "due_date", "status", "note", "updated_at", "updated_by")}}


@cra_router.post("/products/{ref}/verification-link/revoke")
async def revoke_verification_links(ref: str, admin: dict = Depends(require_roles("admin"))):
    org_id = admin["org_id"]
    result = await db.cra_portal_tokens.update_many(
        {"org_id": org_id, "product_ref": ref, "role": "auditor", "revoked_at": None},
        {"$set": {"revoked_at": utcnow()}})
    await ledger_append(org_id, admin.get("email", "unknown"), "verification_link.revoked", "product", ref, ["Article 28"], {"revoked": result.modified_count})
    return {"ok": True, "revoked": result.modified_count}


@cra_router.post("/scorecard-link/revoke")
async def revoke_scorecard_links(admin: dict = Depends(require_roles("admin"))):
    org_id = admin["org_id"]
    result = await db.cra_portal_tokens.update_many(
        {"org_id": org_id, "role": "scorecard", "revoked_at": None},
        {"$set": {"revoked_at": utcnow()}})
    return {"ok": True, "revoked": result.modified_count}


def _cra_scorecard_pdf(org_name, payload):
    from io import BytesIO
    from reportlab.lib.pagesizes import LETTER
    from reportlab.lib.units import inch
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable

    def xx(s):
        return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    buf = BytesIO()
    styles = getSampleStyleSheet()
    navy = colors.HexColor("#0f1e3d"); ai = colors.HexColor("#12b4d6")
    title = ParagraphStyle("t", parent=styles["Title"], fontSize=18, textColor=navy, spaceAfter=2)
    sub = ParagraphStyle("s", parent=styles["Normal"], fontSize=9, textColor=colors.grey)
    h = ParagraphStyle("h", parent=styles["Heading2"], fontSize=12, textColor=ai, spaceBefore=10, spaceAfter=4)
    o = payload["overall"]; nd = payload.get("next_deadline")
    doc = SimpleDocTemplate(buf, pagesize=LETTER, topMargin=0.7 * inch, bottomMargin=0.7 * inch, title="EU CRA Compliance Scorecard")
    story = [Paragraph("EU CRA Compliance Scorecard", title),
             Paragraph(f"{xx(org_name)} &#183; {payload['regulation']} &#183; {datetime.now().strftime('%d %B %Y')}", sub),
             HRFlowable(width="100%", color=ai), Spacer(1, 10),
             Paragraph(f"<b>Overall CRA compliance: {o['percentage']}%</b> &#183; {o['products_assessed']}/{o['products_total']} products assessed", styles["BodyText"])]
    if nd:
        story.append(Paragraph(f"Next statutory deadline: {xx(nd['label'])} on {nd['date']} ({nd['days_remaining']} days).", styles["BodyText"]))
    story.append(Paragraph("Posture", h))
    prow = [["Implemented", str(o["implemented"])], ["Partial", str(o["partial"])], ["Gaps", str(o["gaps"])],
            ["Not started", str(o["not_started"])], ["High risk", str(o["high_risk"])], ["Requirements", str(o["requirements_total"])]]
    pt = Table(prow, colWidths=[3.2 * inch, 3.0 * inch])
    pt.setStyle(TableStyle([("FONTSIZE", (0, 0), (-1, -1), 10), ("TEXTCOLOR", (0, 0), (0, -1), navy), ("LINEBELOW", (0, 0), (-1, -1), 0.3, colors.HexColor("#e5e7eb")), ("BOTTOMPADDING", (0, 0), (-1, -1), 5), ("TOPPADDING", (0, 0), (-1, -1), 5)]))
    story += [pt, Paragraph("Top gaps to close", h)]
    rows = [["Control", "Compliance", "Status", "Risk"]]
    for g in payload.get("top_gaps", []):
        rows.append([f"{g['requirement_id']} — {g['title'][:52]}", ("—" if g["compliance_rate"] is None else f"{g['compliance_rate']}%"), g["status"], g["risk"]])
    gt = Table(rows, colWidths=[3.9 * inch, 0.9 * inch, 0.9 * inch, 0.8 * inch])
    gt.setStyle(TableStyle([("FONTSIZE", (0, 0), (-1, -1), 8), ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f1e3d")), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white), ("LINEBELOW", (0, 0), (-1, -1), 0.25, colors.HexColor("#e5e7eb")), ("BOTTOMPADDING", (0, 0), (-1, -1), 4), ("TOPPADDING", (0, 0), (-1, -1), 4)]))
    story += [gt, Spacer(1, 10), HRFlowable(width="100%", color=colors.HexColor("#e5e7eb")),
              Paragraph("Read-only compliance snapshot. Product names and internal records are not exposed. Decision-support only — not legal advice or a guarantee of CRA conformity.", sub)]
    doc.build(story)
    return buf.getvalue()


@cra_public_router.get("/scorecard/{raw_token}/pdf")
async def public_scorecard_pdf(raw_token: str):
    from fastapi.responses import Response
    payload = await public_scorecard(raw_token)
    pdf = _cra_scorecard_pdf(payload.get("organization", "Organization"), payload)
    return Response(content=pdf, media_type="application/pdf",
                    headers={"Content-Disposition": "attachment; filename=obserra-eu-cra-compliance-scorecard.pdf"})


def _past_due(due_date: str, today) -> bool:
    try:
        return datetime.strptime(str(due_date)[:10], "%Y-%m-%d").date() < today
    except Exception:
        return False


def _cra_reassess_html(org_name, stale, overdue):
    def esc(s):
        return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    stale_rows = "".join(f'<tr><td style="padding:5px 0;font:400 13px Arial;color:#1f2937">{esc(n)} &#8212; {esc(reason)}</td></tr>' for n, reason in stale) or '<tr><td style="font:400 13px Arial;color:#6b7280">None</td></tr>'
    gap_rows = "".join(f'<tr><td style="padding:5px 0;font:400 13px Arial;color:#1f2937">{esc(o["requirement_id"])} &#8212; owner {esc(o.get("owner") or "unassigned")} &#183; due {esc(o.get("due_date"))} &#183; {esc(o.get("status"))}</td></tr>' for o in overdue) or '<tr><td style="font:400 13px Arial;color:#6b7280">None</td></tr>'
    return ('<table width="100%" cellpadding="0" cellspacing="0" style="max-width:620px;margin:auto;background:#fff"><tr><td style="padding:24px">'
            '<div style="font:800 18px Arial;color:#0f1e3d">CRA Reassessment Reminder</div>'
            f'<div style="font:400 12px Arial;color:#6b7280;margin-bottom:10px">{esc(org_name)} &#183; Obserra EU CRA Governance</div>'
            '<div style="font:700 11px Arial;color:#6b7280;letter-spacing:.05em;margin-top:8px">STALE PRODUCT ASSESSMENTS (90+ days)</div>'
            f'<table width="100%">{stale_rows}</table>'
            '<div style="font:700 11px Arial;color:#6b7280;letter-spacing:.05em;margin-top:12px">OVERDUE CONTROL GAPS</div>'
            f'<table width="100%">{gap_rows}</table>'
            '<div style="border-top:1px solid #e5e7eb;margin-top:16px;padding-top:10px;font:400 10px Arial;color:#9ca3af">Sign in to Obserra EU CRA Governance to reassess. Decision-support only &#8212; not legal advice.</div>'
            '</td></tr></table>')


async def _run_cra_reassess_reminder_tick():
    import logging
    from kernel import notifications
    logger = logging.getLogger("obserra.cra")
    now = utcnow()
    if now.hour != 9:
        return
    day_key = now.strftime("%Y-%m-%d")
    today = now.date()
    stale_days = 90
    orgs = await db.organizations.find({}).to_list(1000)
    for org in orgs:
        org_id = str(org["_id"])
        try:
            cfg = org.get("cra_reassess") or {}
            if cfg.get("last_sent_day") == day_key:
                continue
            products = await db.cra_products.find({"org_id": org_id}, {"_id": 0, "ref": 1, "name": 1}).to_list(1000)
            if not products:
                continue
            assessments = await db.cra_assessments.find({"org_id": org_id}, {"_id": 0, "product_ref": 1, "updated_at": 1}).to_list(2000)
            latest = {}
            for a in sorted(assessments, key=lambda x: x.get("updated_at", ""), reverse=True):
                latest.setdefault(a.get("product_ref"), a)
            stale = []
            for p in products:
                a = latest.get(p["ref"])
                if not a:
                    stale.append((p.get("name", p["ref"]), "never assessed"))
                    continue
                try:
                    upd = datetime.fromisoformat(str(a.get("updated_at")).replace("Z", "+00:00"))
                    days = (now - upd).days
                    if days >= stale_days:
                        stale.append((p.get("name", p["ref"]), f"last assessed {days} days ago"))
                except Exception:
                    pass
            owners = await db.cra_control_owners.find({"org_id": org_id}, {"_id": 0}).to_list(1000)
            overdue = [o for o in owners if o.get("status") != "Closed" and o.get("due_date") and _past_due(o["due_date"], today)]
            await db.organizations.update_one({"_id": org["_id"]}, {"$set": {"cra_reassess.last_sent_day": day_key}})
            if not stale and not overdue:
                continue
            recipients = set(r["email"] for r in await db.users.find({"org_id": org_id, "role": {"$in": ["admin", "executive"]}}, {"_id": 0, "email": 1}).to_list(200))
            recipients |= {o["owner"] for o in overdue if o.get("owner") and "@" in str(o.get("owner", ""))}
            if not recipients:
                continue
            html = _cra_reassess_html(org.get("name", "Your organization"), stale, overdue)
            for email in recipients:
                await notifications.send_email(email, "CRA reassessment reminder — stale assessments & overdue gaps", html)
            await notifications.create(org_id, "reminder", "CRA reassessment reminder sent",
                                       f"{len(stale)} stale assessment(s), {len(overdue)} overdue control gap(s).", ref="cra-reassess")
            logger.info(f"CRA reassess reminder sent for org {org_id}: {len(recipients)} recipient(s)")
        except Exception as e:
            logger.error(f"CRA reassess reminder failed for org {org_id}: {e}")



# ===========================================================================
# Obserrian CRA Advisor — per-dashboard AI analyst + per-item explain.
# Both are strictly EU CRA (Regulation (EU) 2024/2847) grounded and reuse the
# Emergent LLM key (openai gpt-5.4) with a deterministic fallback.
# ===========================================================================
_CRA_TAB_CACHE = {}
_CRA_EXPLAIN_CACHE = {}

_CRA_TAB_FOCUS = {
    "mission": "the overall EU CRA product-compliance posture and nearest statutory deadline",
    "products": "product registration, the classification split (Default/Class I/Class II/Critical), classification approvals and conformity pathways",
    "certification": "readiness assessments, assessment scores and the secure certification-portal workflow for vendors and external assessors",
    "ledger": "the hash-chained Internal Regulatory Ledger, event integrity and auditor verification links",
    "sbom": "software bill of materials (CycloneDX/SPDX) coverage and component/vulnerability documentation under Annex I Part II(1)",
    "vulnerability": "Article 14 reporting clocks (24h early warning, 72h notification, final report), actively-exploited vulnerabilities, severe incidents and overdue reporting stages",
    "conformity": "testing labs, CRA notified bodies (NANDO), external conformity assessments and module selection (B+C, H)",
    "declaration": "EU Declaration of Conformity approval, CE market-readiness gates and open blockers",
    "regulation": "the authoritative CRA requirement map linking each obligation to Regulation (EU) 2024/2847 and Implementing Regulation (EU) 2025/2392",
    "controls": "the CRA control dashboard — compliance rate per essential requirement, gaps, high-risk controls and gap ownership",
    "nist": "the mapping of EU CRA controls onto the NIST CSF 2.0 functions (GV/ID/PR/DE/RS/RC) and SP 800-218 (SSDF) practices",
    "riskcorrelation": "the correlated EU CRA risk picture — rated risks synthesised from overdue Article 14 reporting, open vulnerabilities, control gaps, CE-marking blockers and AI-grounding drift, each mapped to the CRA essential requirements they threaten",
}


async def _cra_tab_context(org_id: str, tab: str) -> dict:
    base = await _cra_insight_context(org_id)
    t = base["totals"]
    c = base["counts"]

    def _pct(n, d):
        if not d:
            return "0%"
        v = (n / d) * 100
        return f"{v:.1f}%" if abs(v - round(v)) > 0.05 else f"{round(v)}%"

    # Surface the derived ratios/percentages the analyst legitimately cites so the
    # grounding verifier treats correct arithmetic as supported (not a hallucination).
    base["derived_metrics"] = {
        "products_total": t["products"],
        "classification_approved": t["classification_approved"],
        "classification_approved_pct": _pct(t["classification_approved"], t["products"]),
        "classification_approved_ratio": f"{t['classification_approved']}/{t['products']}",
        "products_unapproved": t["products"] - t["classification_approved"],
        "ce_ready": t["ce_ready"],
        "ce_ready_pct": _pct(t["ce_ready"], t["products"]),
        "ce_ready_ratio": f"{t['ce_ready']}/{t['products']}",
        "products_blocked": c["blocked"],
        "products_blocked_pct": _pct(c["blocked"], t["products"]),
        "products_blocked_ratio": f"{c['blocked']}/{t['products']}",
        "average_readiness_pct": f"{t['average_readiness']}%",
    }
    if tab in ("controls", "nist"):
        computed = await _compute_controls(org_id)
        gaps = [c for c in computed["controls"] if c["status"] in ("Gap", "Partial", "Not Started") or c["risk"] == "High"]
        gaps.sort(key=lambda c: (c["compliance_rate"] if c["compliance_rate"] is not None else -1))
        base["control_overall"] = computed["overall"]
        base["top_gaps"] = [{"requirement_id": c["requirement_id"], "title": c["title"], "status": c["status"],
                             "risk": c["risk"], "compliance_rate": c["compliance_rate"]} for c in gaps[:8]]
        if tab == "nist":
            nist = await _compute_nist(org_id)
            base["nist_overall"] = nist["overall"]
            base["nist_functions"] = [{"code": f["code"], "name": f["name"], "compliance_rate": f["compliance_rate"],
                                       "risk": f["risk"], "mapped": f["mapped"], "implemented": f["implemented"],
                                       "gaps": f["gaps"]} for f in nist["functions"]]
    if tab == "riskcorrelation":
        rc = await _compute_risk_correlation(org_id)
        base["risk_overall"] = rc["overall"]
        base["top_risks"] = [{"title": r["title"], "rating": r["rating"], "category": r["category"],
                              "score": r["score"], "drivers": r["drivers"][:2],
                              "mapped_controls": [m["requirement_id"] for m in r["mapped_controls"]]}
                             for r in rc["risks"][:6]]
    base["focus_tab"] = tab
    base["focus"] = _CRA_TAB_FOCUS.get(tab, "EU CRA product compliance")
    return base


class CRATabInsightReq(BaseModel):
    tab: str = "mission"


@cra_router.post("/dashboard-insight")
async def cra_dashboard_insight(body: CRATabInsightReq, user: dict = Depends(get_current_user)):
    import os
    import asyncio
    org_id = user["org_id"]
    tab = body.tab or "mission"
    ctx = await _cra_tab_context(org_id, tab)
    focus = ctx["focus"]
    ck = (org_id, tab, ctx["counts"]["products"], ctx["counts"]["blocked"], ctx["counts"]["overdue_clocks"],
          ctx["totals"]["classification_approved"], ctx["totals"]["ce_ready"], ctx["totals"]["average_readiness"])
    hit = _CRA_TAB_CACHE.get(ck)
    if hit and (utcnow() - hit["ts"]).total_seconds() < 120:
        return hit["data"]
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage, TextDelta, StreamDone
        system = (
            "You are the Obserra EU CRA Governance AI Analyst producing a concise, grounded briefing for the "
            f"'{tab}' dashboard, focused on {focus}. Read the LIVE EU Cyber Resilience Act posture JSON and return "
            "STRICTLY JSON: {\"headline\": str, \"insights\": [{\"text\": str, \"kind\": \"fact\"|\"estimate\"|\"risk\"}], "
            "\"actions\": [str]}. 3-4 insights, 2-3 actions. Ground EVERY statement in the data — cite counts, refs, "
            "compliance rates, named blockers or overdue reporting stages relevant to THIS dashboard's focus. This is "
            "EU CRA (Regulation (EU) 2024/2847) product compliance: NEVER mention SAP access, SoD conflicts, "
            "cyber-crisis or any unrelated governance domain. Return ONLY the JSON object.")
        chat = LlmChat(api_key=os.environ["EMERGENT_LLM_KEY"], session_id=f"cra-tab-{org_id}-{tab}",
                       system_message=system).with_model("openai", "gpt-5.4")
        prompt = f"DASHBOARD: {tab} (focus: {focus})\nLIVE EU CRA POSTURE (JSON):\n{json.dumps(ctx, default=str)[:9000]}"
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
            data = _cra_insight_fallback(ctx)
        else:
            parsed.setdefault("actions", [])
            parsed["model"] = "openai/gpt-5.4"
            parsed["generated_at"] = iso()
            data = parsed
    except Exception:
        data = _cra_insight_fallback(ctx)
    data["focus"] = focus
    data["tab"] = tab
    data.setdefault("model", "obserra/cra-grounded")
    data.setdefault("generated_at", iso())
    _CRA_TAB_CACHE[ck] = {"ts": utcnow(), "data": data}
    return data


class CRAExplainReq(BaseModel):
    title: str = Field(default="", max_length=240)
    kind: str = Field(default="item", max_length=60)
    context: dict = {}


def _cra_explain_fallback(body: "CRAExplainReq") -> dict:
    ctx = body.context or {}
    risk = ctx.get("risk") or ctx.get("risk_level") or ctx.get("classification") or "Medium"
    sev = {"high": "risk", "critical": "risk", "medium": "watch", "low": "opportunity"}.get(str(risk).lower(), "info")
    bits = ", ".join(f"{k}={v}" for k, v in list(ctx.items())[:4]) or "no additional context"
    return {"summary": f"{body.title}: grounded from the live record ({bits}).",
            "severity": sev, "risk": str(risk).title(),
            "risk_detail": "Risk is derived from the current CRA compliance state recorded for this item.",
            "recommendation": "Review the mapped CRA obligation and close any open gap to raise conformity.",
            "steps": ["Open the item's readiness assessment and verify each mapped requirement.",
                      "Assign an owner and due date to any gap on the Control Dashboard.",
                      "Record supporting evidence so the change is written to the Regulatory Ledger."],
            "model": "obserra/cra-grounded", "generated_at": iso()}


@cra_router.post("/explain")
async def cra_explain(body: CRAExplainReq, user: dict = Depends(get_current_user)):
    import os
    import asyncio
    org_id = user["org_id"]
    ckey = (org_id, body.kind, body.title, json.dumps(body.context, default=str, sort_keys=True)[:600])
    hit = _CRA_EXPLAIN_CACHE.get(ckey)
    if hit and (utcnow() - hit["ts"]).total_seconds() < 300:
        return hit["data"]
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage, TextDelta, StreamDone
        system = (
            "You are the Obserra EU CRA Governance AI Advisor. A user clicked a single item on an EU Cyber Resilience "
            "Act dashboard. Using ONLY the supplied live context (never invent numbers, names or refs), return STRICT "
            "JSON: {\"summary\": str (<=240 chars), \"severity\": \"risk\"|\"watch\"|\"opportunity\"|\"info\", "
            "\"risk\": str (a risk level: Critical/High/Medium/Low), \"risk_detail\": str (<=240 chars, why it matters "
            "under the CRA), \"recommendation\": str (one imperative action, <=200 chars), \"steps\": [str] (2-4 "
            "concrete fix steps)}. This is EU CRA (Regulation (EU) 2024/2847) product compliance: NEVER mention SAP, "
            "SoD, cyber-crisis or unrelated domains. Return ONLY the JSON object.")
        chat = LlmChat(api_key=os.environ["EMERGENT_LLM_KEY"], session_id=f"cra-explain-{org_id}",
                       system_message=system).with_model("openai", "gpt-5.4")
        prompt = f"ITEM: {body.title}\nKIND: {body.kind}\nLIVE CONTEXT (JSON):\n{json.dumps(body.context, default=str)[:6000]}"
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
        if not parsed or not parsed.get("summary"):
            data = _cra_explain_fallback(body)
        else:
            parsed.setdefault("steps", [])
            parsed.setdefault("severity", "info")
            parsed.setdefault("risk", "Medium")
            parsed["model"] = "openai/gpt-5.4"
            parsed["generated_at"] = iso()
            data = parsed
    except Exception:
        data = _cra_explain_fallback(body)
    _CRA_EXPLAIN_CACHE[ckey] = {"ts": utcnow(), "data": data}
    return data


async def _compute_risk_correlation(org_id: str) -> dict:
    """Correlate live EU CRA signals into rated risk items mapped to the essential requirements they threaten."""
    ctx = await _cra_insight_context(org_id)
    controls = await _compute_controls(org_id)
    vulns = await db.cra_vulnerabilities.find({"org_id": org_id}, {"_id": 0}).to_list(1000)
    try:
        assurance = await _cra_grounding_summary(org_id)
    except Exception:
        assurance = {}

    req_by_id = {r["requirement_id"]: r for r in REGULATORY_REQUIREMENTS}

    def mc(rid):
        r = req_by_id.get(rid, {})
        n = NIST_ALIGNMENT.get(rid, {})
        return {"requirement_id": rid, "title": r.get("title", rid), "legal_refs": r.get("legal_refs", []), "csf": n.get("csf", [])}

    def rate(score):
        if score >= 20:
            return "Critical"
        if score >= 12:
            return "High"
        if score >= 6:
            return "Medium"
        return "Low"

    risks = []
    SEVMAP = {"Critical": 5, "High": 4, "Medium": 3, "Low": 2}
    CLSSEV = {"Critical": 5, "Class II": 4, "Class I": 3, "Default": 2}

    # 1) Overdue statutory Article 14 reporting
    for v in vulns:
        clock = reporting_clock(v)
        overdue = [s for s in clock.get("stages", []) if s.get("overdue")]
        if not overdue:
            continue
        stage_names = [s["stage"].replace("_", " ") for s in overdue]
        risks.append({
            "title": f"Overdue Article 14 report — {v.get('title') or v.get('ref')}",
            "category": "Statutory Reporting", "severity": 5, "likelihood": 5,
            "drivers": [f"{len(overdue)} reporting stage(s) past deadline: {', '.join(stage_names)}",
                        f"Vulnerability severity: {v.get('severity', 'n/a')}",
                        "Actively exploited" if v.get("actively_exploited") else "Not flagged as actively exploited"],
            "affected": [{"ref": v.get("product_ref"), "name": v.get("product_name") or v.get("product_ref")}],
            "recommendation": "Submit the overdue Article 14 report(s) to ENISA/the CSIRT immediately and record the receipt on the ledger.",
            "fixes": [f"Open Vulnerability & ENISA → {v.get('ref')} and submit the {n} report" for n in stage_names],
            "mapped_controls": [mc("CRA-REPORT-01"), mc("CRA-VULN-02")],
            "deadline": None,
        })

    # 2) Open high-severity / actively-exploited vulnerabilities (not already overdue)
    for v in vulns:
        clock = reporting_clock(v)
        if any(s.get("overdue") for s in clock.get("stages", [])):
            continue
        sev_label = v.get("severity", "High")
        if sev_label not in ("High", "Critical") and not v.get("actively_exploited"):
            continue
        sev = SEVMAP.get(sev_label, 4)
        like = 5 if v.get("actively_exploited") else (4 if v.get("severe_incident") else 3)
        if v.get("corrective_measure_available_at"):
            like = max(2, like - 1)
        risks.append({
            "title": f"Open {str(sev_label).lower()} vulnerability — {v.get('title') or v.get('ref')}",
            "category": "Vulnerability", "severity": sev, "likelihood": like,
            "drivers": [f"Severity {sev_label}" + (f" · CVE {v.get('cve')}" if v.get("cve") else ""),
                        "Actively exploited (KEV-style exposure)" if v.get("actively_exploited") else "Not currently flagged as actively exploited",
                        "Corrective measure available" if v.get("corrective_measure_available_at") else "No corrective measure recorded yet"],
            "affected": [{"ref": v.get("product_ref"), "name": v.get("product_name") or v.get("product_ref")}],
            "recommendation": "Remediate via a security update and confirm the fix, then keep the Article 14 clock evidence current.",
            "fixes": ["Ship/verify the security update for the affected product",
                      "Record the corrective measure and update the vulnerability status",
                      "Confirm no Article 14 reporting stage is approaching its deadline"],
            "mapped_controls": [mc("CRA-VULN-01"), mc("CRA-VULN-02"), mc("CRA-VDP-01")],
            "deadline": None,
        })

    # 3) Control gaps / high-risk essential requirements
    for c in controls["controls"]:
        rate_v = c["compliance_rate"]
        is_risk = c["status"] in ("Gap", "Not Started") or c["risk"] == "High" or (c["status"] == "Partial" and (rate_v or 0) < 50)
        if not is_risk:
            continue
        sev = 5 if c["risk"] == "High" else (3 if c["risk"] == "Medium" else 2)
        like = 5 if (rate_v is None or rate_v == 0) else (4 if rate_v < 50 else 3)
        affected = [{"ref": ps["ref"], "name": ps["name"]} for ps in c.get("product_status", [])
                    if ps["status"] in ("Nonconforming", "Partial", "Not Assessed")][:10]
        risks.append({
            "title": f"Control gap — {c['requirement_id']}: {c['title'][:90]}",
            "category": "Control Gap", "severity": sev, "likelihood": like,
            "drivers": [f"Status {c['status']} · compliance {rate_v if rate_v is not None else 'not assessed'}%",
                        f"{c['risk']} risk control",
                        f"{c['nonconforming']} nonconforming · {c['partial']} partial · {c['not_assessed']} not assessed across products"],
            "affected": affected,
            "recommendation": f"Raise coverage of {c['requirement_id']} — assign an owner and close the gap across affected products.",
            "fixes": ["Assign an owner and due date on the Control Dashboard",
                      "Complete or re-run the readiness assessment for affected products",
                      "Attach conformity evidence so the change is written to the Regulatory Ledger"],
            "mapped_controls": [mc(c["requirement_id"])],
            "deadline": None,
        })

    # 4) CE market-readiness blockers
    BLOCKER_REQ = {"classification not approved": "CRA-CLASS-01", "readiness assessment incomplete": "CRA-RISK-01",
                   "no SBOM": "CRA-SBOM-01", "EU declaration not approved": "CRA-DOC-01"}
    BLOCKER_FIX = {"classification not approved": "Approve the product classification",
                   "readiness assessment incomplete": "Complete the CRA readiness assessment",
                   "no SBOM": "Generate and attach a CycloneDX/SPDX SBOM",
                   "EU declaration not approved": "Approve the EU Declaration of Conformity"}
    nd = ctx.get("next_deadline")
    for b in ctx.get("ce_blockers", []):
        sev = CLSSEV.get(b.get("classification", "Default"), 2)
        blk = b.get("blockers", [])
        like = min(5, 2 + len(blk))
        mapped = [mc(BLOCKER_REQ[x]) for x in blk if x in BLOCKER_REQ]
        risks.append({
            "title": f"CE market-readiness blocked — {b.get('product')}",
            "category": "CE Readiness", "severity": sev, "likelihood": like,
            "drivers": [f"{b.get('classification')} product with {len(blk)} open blocker(s)"] + list(blk),
            "affected": [{"ref": b.get("ref"), "name": b.get("product")}],
            "recommendation": "Clear the open CE-marking blockers so the product can lawfully carry the CE mark.",
            "fixes": [BLOCKER_FIX.get(x, x) for x in blk],
            "mapped_controls": mapped + [mc("CRA-CE-01")],
            "deadline": nd,
        })

    # 5) AI grounding / oversight drift
    if (assurance.get("flagged_total") or 0) > 0 and assurance.get("avg_score") is not None and assurance["avg_score"] < 80:
        sev = 4 if assurance["avg_score"] < 50 else 3
        risks.append({
            "title": "AI grounding drift on CRA analyst answers",
            "category": "AI Oversight", "severity": sev, "likelihood": 3,
            "drivers": [f"{assurance['flagged_total']} flagged AI answer(s)",
                        f"Average grounding score {assurance['avg_score']}% (below the 80% assurance target)"],
            "affected": [],
            "recommendation": "Review flagged AI answers in the AI Assurance monitor and correct any ungrounded guidance before it informs a decision.",
            "fixes": ["Open AI Assurance and inspect the flagged answers",
                      "Correct the underlying data or evidence the answer relied on",
                      "Re-run the analyst and confirm the grounding score recovers"],
            "mapped_controls": [mc("CRA-DOC-01"), mc("CRA-RISK-01")],
            "deadline": None,
        })

    # Dedup mapped controls, score, rate, sort, cap, id + stable key
    import hashlib
    for r in risks:
        seen, dd = set(), []
        for m in r["mapped_controls"]:
            if m["requirement_id"] not in seen:
                seen.add(m["requirement_id"])
                dd.append(m)
        r["mapped_controls"] = dd
        r["score"] = r["severity"] * r["likelihood"]
        r["rating"] = rate(r["score"])
        r["key"] = "rk_" + hashlib.md5(f"{r['category']}|{r['title']}".encode()).hexdigest()[:12]
    risks.sort(key=lambda r: (-r["score"], r["title"]))
    risks = risks[:24]

    owners = {o["risk_key"]: o for o in await db.cra_risk_owners.find(
        {"org_id": org_id, "status": {"$ne": "resolved"}}).to_list(500)}
    for i, r in enumerate(risks):
        r["id"] = f"risk-{i}"
        o = owners.get(r["key"])
        r["owner"] = o.get("owner") if o else None
        r["owner_email"] = o.get("owner_email") if o else None
        r["due_date"] = o.get("due_date") if o else None
        r["owner_note"] = o.get("note") if o else None

    counts = {"Critical": 0, "High": 0, "Medium": 0, "Low": 0}
    for r in risks:
        counts[r["rating"]] += 1
    total = len(risks)
    risk_index = round(100 * sum(r["score"] for r in risks) / (total * 25)) if total else 0
    top_rating = next((k for k in ("Critical", "High", "Medium", "Low") if counts[k] > 0), None)

    ctr, titles = {}, {}
    for r in risks:
        for m in r["mapped_controls"]:
            rid = m["requirement_id"]
            ctr[rid] = ctr.get(rid, 0) + 1
            titles[rid] = m["title"]
    most = None
    if ctr:
        rid = max(ctr, key=lambda k: ctr[k])
        most = {"requirement_id": rid, "title": titles[rid], "count": ctr[rid]}

    top_risks = [{"title": r["title"], "rating": r["rating"], "score": r["score"],
                  "category": r["category"], "owner": r.get("owner"), "due_date": r.get("due_date")}
                 for r in risks[:3]]

    # Zero-touch daily history point so the board risk trend fills in without logins
    try:
        from datetime import datetime as _dt, timezone as _tz
        today = _dt.now(_tz.utc).strftime("%Y-%m-%d")
        await db.cra_risk_history.update_one(
            {"org_id": org_id, "date": today},
            {"$set": {"risk_index": risk_index, "counts": counts, "total": total, "at": iso()}},
            upsert=True)
    except Exception:
        pass

    return {
        "version": CRA_APP_VERSION, "generated_at": iso(),
        "overall": {"total": total, "counts": counts, "risk_index": risk_index,
                    "top_rating": top_rating, "most_correlated_control": most, "top_risks": top_risks},
        "risks": risks,
    }


@cra_router.get("/risk-correlation")
async def cra_risk_correlation(user: dict = Depends(get_current_user)):
    return await _compute_risk_correlation(user["org_id"])


class CRARiskOwnerReq(BaseModel):
    risk_key: str
    risk_title: str = ""
    owner: str = Field(..., max_length=120)
    owner_email: str = Field("", max_length=160)
    due_date: str = Field("", max_length=10)
    note: str = Field("", max_length=400)


@cra_router.post("/risk-owner")
async def assign_risk_owner(body: CRARiskOwnerReq, user: dict = Depends(get_current_user)):
    org_id = user["org_id"]
    now = iso()
    doc = {"owner": body.owner.strip(), "owner_email": body.owner_email.strip(),
           "due_date": body.due_date.strip(), "note": body.note.strip(),
           "risk_title": body.risk_title, "status": "open", "updated_at": now, "assigned_by": user.get("email")}
    await db.cra_risk_owners.update_one(
        {"org_id": org_id, "risk_key": body.risk_key},
        {"$set": doc, "$setOnInsert": {"org_id": org_id, "risk_key": body.risk_key, "created_at": now, "last_reminded": None}},
        upsert=True)
    try:
        await ledger_append(org_id, user.get("email", "unknown"), "risk.owner_assigned", "risk", body.risk_key,
                            ["Article 13"], {"owner": body.owner, "due_date": body.due_date})
    except Exception:
        pass
    return {"ok": True}


@cra_router.delete("/risk-owner/{risk_key}")
async def clear_risk_owner(risk_key: str, user: dict = Depends(get_current_user)):
    await db.cra_risk_owners.update_one({"org_id": user["org_id"], "risk_key": risk_key},
                                        {"$set": {"status": "resolved", "resolved_at": iso()}})
    return {"ok": True}


@cra_router.get("/risk-trend")
async def cra_risk_trend(days: int = 30, user: dict = Depends(get_current_user)):
    from datetime import datetime, timezone, timedelta
    org_id = user["org_id"]
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    since = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")
    rows = await db.cra_risk_history.find({"org_id": org_id, "date": {"$gte": since}}, {"_id": 0}).sort("date", 1).to_list(400)
    if not rows or rows[-1]["date"] != today:
        await _compute_risk_correlation(org_id)
        rows = await db.cra_risk_history.find({"org_id": org_id, "date": {"$gte": since}}, {"_id": 0}).sort("date", 1).to_list(400)
    series = [{"date": r["date"], "risk_index": r.get("risk_index", 0), "counts": r.get("counts", {})} for r in rows]
    first = series[0]["risk_index"] if series else 0
    last = series[-1]["risk_index"] if series else 0
    return {"days": days, "series": series, "change": last - first, "current": last}


@cra_router.get("/risk-register.csv")
async def risk_register_csv(user: dict = Depends(get_current_user)):
    import csv, io
    from fastapi.responses import Response
    rc = await _compute_risk_correlation(user["org_id"])
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["Rating", "Score", "Severity", "Likelihood", "Category", "Risk", "Owner",
                "Owner email", "Due date", "Mapped controls", "NIST CSF", "Recommendation", "Fixes"])
    for r in rc["risks"]:
        w.writerow([r["rating"], r["score"], r["severity"], r["likelihood"], r["category"], r["title"],
                    r.get("owner") or "", r.get("owner_email") or "", r.get("due_date") or "",
                    "; ".join(m["requirement_id"] for m in r["mapped_controls"]),
                    "; ".join(c for m in r["mapped_controls"] for c in m.get("csf", [])),
                    r["recommendation"], " | ".join(r["fixes"])])
    return Response(content=buf.getvalue(), media_type="text/csv",
                    headers={"Content-Disposition": "attachment; filename=obserra-cra-risk-register.csv"})


@cra_router.get("/risk-register.pdf")
async def risk_register_pdf(user: dict = Depends(get_current_user)):
    from bson import ObjectId
    from fastapi.responses import Response
    org = await db.organizations.find_one({"_id": ObjectId(user["org_id"])}, {"_id": 0, "name": 1})
    rc = await _compute_risk_correlation(user["org_id"])
    pdf = _cra_risk_register_pdf((org or {}).get("name", "Your organization"), rc)
    return Response(content=pdf, media_type="application/pdf",
                    headers={"Content-Disposition": "attachment; filename=obserra-cra-risk-register.pdf"})


def _cra_risk_register_pdf(org_name, rc):
    import io
    from reportlab.lib.pagesizes import LETTER, landscape
    from reportlab.lib.units import inch
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=landscape(LETTER), leftMargin=0.5 * inch, rightMargin=0.5 * inch,
                            topMargin=0.6 * inch, bottomMargin=0.5 * inch)
    ss = getSampleStyleSheet()
    NAVY = colors.HexColor("#0f1e3d")
    h1 = ParagraphStyle("rh1", parent=ss["Title"], textColor=NAVY, fontSize=18, spaceAfter=2)
    sub = ParagraphStyle("rsub", parent=ss["Normal"], textColor=colors.HexColor("#6b7280"), fontSize=9)
    small = ParagraphStyle("rsm", parent=ss["Normal"], fontSize=7.5, leading=9, textColor=colors.HexColor("#9ca3af"))
    cellst = ParagraphStyle("rcell", parent=ss["Normal"], fontSize=7.5, leading=9)
    o = rc["overall"]
    story = [Paragraph("EU CRA Risk Register", h1),
             Paragraph(f'{org_name} &#183; Regulation (EU) 2024/2847 &#183; Obserra CRA v{rc["version"]} &#183; {rc["generated_at"][:10]}', sub),
             Spacer(1, 6), HRFlowable(width="100%", color=colors.HexColor("#e5e7eb")), Spacer(1, 8),
             Paragraph(f'<b>Correlated risk index:</b> {o["risk_index"]}/100 &#183; {o["total"]} risk(s) &#183; '
                       f'Critical {o["counts"]["Critical"]} · High {o["counts"]["High"]} · Medium {o["counts"]["Medium"]} · Low {o["counts"]["Low"]}', sub),
             Spacer(1, 8)]
    header = ["Rating", "Score", "Category", "Risk", "Owner", "Due", "Mapped controls", "Recommendation"]
    data = [header]
    RTONE = {"Critical": colors.HexColor("#dc2626"), "High": colors.HexColor("#ea580c"),
             "Medium": colors.HexColor("#ca8a04"), "Low": colors.HexColor("#16a34a")}
    row_tones = []
    for r in rc["risks"]:
        data.append([r["rating"], str(r["score"]), r["category"],
                     Paragraph(r["title"], cellst), Paragraph(r.get("owner") or "&#8212;", cellst),
                     r.get("due_date") or "\u2014",
                     Paragraph(", ".join(m["requirement_id"] for m in r["mapped_controls"]), cellst),
                     Paragraph(r["recommendation"], cellst)])
        row_tones.append(RTONE.get(r["rating"], NAVY))
    tbl = Table(data, colWidths=[0.6 * inch, 0.4 * inch, 0.9 * inch, 2.3 * inch, 0.9 * inch, 0.7 * inch, 1.4 * inch, 2.4 * inch], repeatRows=1)
    tstyle = [("BACKGROUND", (0, 0), (-1, 0), NAVY), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
              ("FONTSIZE", (0, 0), (-1, 0), 8), ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
              ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#e5e7eb")),
              ("VALIGN", (0, 0), (-1, -1), "TOP"), ("FONTSIZE", (0, 1), (-1, -1), 7.5),
              ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")])]
    for i, tone in enumerate(row_tones, start=1):
        tstyle.append(("TEXTCOLOR", (0, i), (0, i), tone))
        tstyle.append(("FONTNAME", (0, i), (0, i), "Helvetica-Bold"))
    tbl.setStyle(TableStyle(tstyle))
    story.append(tbl)
    story.append(Spacer(1, 10))
    story.append(Paragraph("Ratings synthesised from live products, vulnerabilities, assessments, controls and the AI-grounding monitor. Decision-support only — not legal advice or a guarantee of CRA conformity.", small))
    doc.build(story)
    return buf.getvalue()


def _cra_risk_reminder_html(org_name, risk, due, days_left):
    def esc(s):
        return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    when = "overdue" if days_left < 0 else ("due today" if days_left == 0 else f"due in {days_left} day(s)")
    ctrls = ", ".join(m["requirement_id"] for m in risk.get("mapped_controls", []))
    fixes = "".join(f'<li style="margin:2px 0">{esc(f)}</li>' for f in risk.get("fixes", []))
    return (
        '<table width="100%" cellpadding="0" cellspacing="0" style="max-width:600px;margin:auto;background:#fff"><tr><td style="padding:24px">'
        '<div style="font:800 18px Arial;color:#0f1e3d">EU CRA Risk Reminder</div>'
        f'<div style="font:400 12px Arial;color:#6b7280;margin-bottom:10px">{esc(org_name)} &#183; Regulation (EU) 2024/2847</div>'
        f'<div style="background:#fff7ed;border:1px solid #fed7aa;border-radius:8px;padding:12px 14px;font:600 13px Arial;color:#b45309">'
        f'A CRA risk assigned to you is {when} ({esc(due)}).</div>'
        f'<div style="font:700 15px Arial;color:#0f1e3d;margin:14px 0 4px">[{esc(risk["rating"])}] {esc(risk["title"])}</div>'
        f'<div style="font:400 13px Arial;color:#374151">{esc(risk.get("recommendation", ""))}</div>'
        f'<div style="font:700 11px Arial;color:#6b7280;margin-top:10px">MAPPED CONTROLS</div>'
        f'<div style="font:400 12px Arial;color:#1f2937">{esc(ctrls)}</div>'
        + (f'<div style="font:700 11px Arial;color:#6b7280;margin-top:10px">FIXES NEEDED</div><ul style="font:400 12px Arial;color:#1f2937;margin:4px 0 0 16px">{fixes}</ul>' if fixes else '')
        + '<div style="border-top:1px solid #e5e7eb;margin-top:16px;padding-top:10px;font:400 10px Arial;color:#9ca3af">'
        'Sign in to Obserra EU CRA Governance &#8594; Risk Correlation to update or close this risk.</div>'
        '</td></tr></table>')


async def _run_cra_risk_governance_tick():
    """Hourly: snapshot each org's correlated risk index (zero-touch trend) and remind risk owners of due/overdue items."""
    import logging as _lg
    from datetime import datetime, timezone
    from kernel import notifications
    log = _lg.getLogger(__name__)
    now = datetime.now(timezone.utc)
    orgs = await db.organizations.find({}, {"_id": 1, "name": 1}).to_list(1000)
    for org in orgs:
        org_id = str(org["_id"])
        try:
            if not await db.cra_products.find_one({"org_id": org_id}, {"_id": 1}):
                continue
            rc = await _compute_risk_correlation(org_id)  # also upserts today's history point
            active = {r["key"]: r for r in rc["risks"]}
            owners = await db.cra_risk_owners.find({"org_id": org_id, "status": {"$ne": "resolved"}}).to_list(500)
            for o in owners:
                key = o.get("risk_key")
                if key not in active:
                    await db.cra_risk_owners.update_one({"_id": o["_id"]}, {"$set": {"status": "resolved", "resolved_at": iso()}})
                    continue
                due = o.get("due_date")
                if not due or not o.get("owner_email"):
                    continue
                try:
                    due_dt = datetime.strptime(due, "%Y-%m-%d").replace(tzinfo=timezone.utc)
                except Exception:
                    continue
                days_left = (due_dt - now).days
                if days_left > 3:
                    continue
                last = o.get("last_reminded")
                if last:
                    try:
                        if (now - datetime.fromisoformat(last)).total_seconds() < 20 * 3600:
                            continue
                    except Exception:
                        pass
                risk = active[key]
                overdue = days_left < 0
                subject = (("[Overdue] " if overdue else "") + f"CRA risk due: {risk['title'][:70]}")
                html = _cra_risk_reminder_html(org.get("name", "Your organization"), risk, due, days_left)
                await notifications.send_email(o["owner_email"], subject, html)
                await db.cra_risk_owners.update_one({"_id": o["_id"]}, {"$set": {"last_reminded": iso()}})
            log.info(f"CRA risk governance tick done for org {org_id}")
        except Exception as e:
            log.error(f"CRA risk governance tick failed for org {org_id}: {e}")



# ---------------------------------------------------------------------------
# Hallucination monitor + versioning for the Obserrian CRA AI (grounding).
# Reuses the platform grounding verifier (hallucination.ground_answer) so every
# CRA AI answer is scored against the LIVE context that produced it. Grounding is
# a separate, non-blocking call fired by the UI after the answer renders, so it
# never adds latency to the primary AI response.
# ---------------------------------------------------------------------------
CRA_APP_VERSION = "1.0.0"


class CRAGroundReq(BaseModel):
    kind: str = Field(default="insight", max_length=40)   # 'insight' | 'explain'
    tab: str = Field(default="", max_length=40)
    title: str = Field(default="", max_length=240)
    context: dict = {}
    answer: str = Field(default="", max_length=8000)


@cra_router.post("/ground")
async def cra_ground(body: CRAGroundReq, user: dict = Depends(get_current_user)):
    from hallucination import ground_answer, record_grounding
    org_id = user["org_id"]
    if body.kind == "insight" and body.tab:
        ctx = await _cra_tab_context(org_id, body.tab)
        context_str = json.dumps(ctx, default=str)[:12000]
        surface = f"cra:insight:{body.tab}"
        question = f"CRA {body.tab} dashboard analyst briefing"
    else:
        context_str = json.dumps(body.context, default=str)[:12000]
        surface = f"cra:explain:{body.kind}"
        question = body.title or "CRA item explanation"
    result = await ground_answer(body.answer, context_str, use_llm=True)
    await record_grounding(org_id, surface, question, body.answer, result,
                           model="openai/gpt-5.4", user=user.get("email"))
    return {"score": result["score"], "label": result["label"],
            "flagged_count": result["flagged_count"], "flagged": result["flagged"][:6],
            "claims": result["claims"][:12], "method": result["method"],
            "version": CRA_APP_VERSION, "checked_at": iso()}


@cra_router.get("/ai-monitor")
async def cra_ai_monitor(days: int = 30, user: dict = Depends(get_current_user)):
    from datetime import timedelta
    org_id = user["org_id"]
    days = max(1, min(180, int(days or 30)))
    since = (utcnow() - timedelta(days=days)).isoformat()
    rows = await db.ai_grounding_log.find(
        {"org_id": org_id, "surface": {"$regex": "^cra:"}, "at": {"$gte": since}},
        {"_id": 0}).sort("at", -1).to_list(2000)
    scored = [r["score"] for r in rows if isinstance(r.get("score"), int)]
    avg = round(sum(scored) / len(scored)) if scored else None
    flagged_total = sum(1 for r in rows if (r.get("flagged_count") or 0) > 0)
    by_surface = {}
    for r in rows:
        s = r.get("surface") or "cra:other"
        b = by_surface.setdefault(s, {"surface": s, "count": 0, "flagged": 0, "_ss": 0, "_sc": 0})
        b["count"] += 1
        if (r.get("flagged_count") or 0) > 0:
            b["flagged"] += 1
        if isinstance(r.get("score"), int):
            b["_ss"] += r["score"]
            b["_sc"] += 1
    surfaces = sorted([{"surface": v["surface"], "count": v["count"], "flagged": v["flagged"],
                        "avg_score": round(v["_ss"] / v["_sc"]) if v["_sc"] else None}
                       for v in by_surface.values()], key=lambda x: -x["count"])
    recent = [{"at": r.get("at"), "surface": r.get("surface"), "score": r.get("score"),
               "label": r.get("label"), "question": r.get("question"),
               "flagged_count": r.get("flagged_count", 0), "claims": (r.get("claims") or [])[:6]}
              for r in rows[:40]]
    label = "Grounded" if (avg is None or avg >= 80) else ("Partially grounded" if avg >= 50 else "Unverified")
    by_day = {}
    for r in rows:
        dd = (r.get("at") or "")[:10]
        if not dd:
            continue
        bd = by_day.setdefault(dd, {"_ss": 0, "_sc": 0})
        if isinstance(r.get("score"), int):
            bd["_ss"] += r["score"]
            bd["_sc"] += 1
    trend = []
    for i in range(days - 1, -1, -1):
        dk = (utcnow() - timedelta(days=i)).strftime("%Y-%m-%d")
        bd = by_day.get(dk)
        trend.append({"date": dk, "score": round(bd["_ss"] / bd["_sc"]) if (bd and bd["_sc"]) else None,
                      "count": (bd["_sc"] if bd else 0)})
    return {"version": CRA_APP_VERSION, "days": days, "total_checks": len(rows),
            "avg_score": avg, "label": label, "flagged_total": flagged_total,
            "surfaces": surfaces, "recent": recent, "trend": trend}


# ---------------------------------------------------------------------------
# Executive Overview snapshots (month-over-month) + a SEPARATE scheduled
# Executive-Overview board email (own day/time, distinct from the analyst digest).
# ---------------------------------------------------------------------------
async def _cra_exec_kpis(org_id: str) -> dict:
    ctx = await _cra_insight_context(org_id)
    controls = await _compute_controls(org_id)
    nist = await _compute_nist(org_id)
    assurance = await _cra_grounding_summary(org_id)
    t = ctx["totals"]; c = ctx["counts"]; co = controls["overall"]; no = nist["overall"]
    p = t["products"] or 1
    return {
        "products": t["products"],
        "classification_approved": t["classification_approved"],
        "classification_approved_pct": round(t["classification_approved"] / p * 100),
        "ce_ready": t["ce_ready"],
        "ce_ready_pct": round(t["ce_ready"] / p * 100),
        "article14_overdue": c.get("overdue_clocks", 0),
        "control_compliance_pct": co.get("percentage", 0),
        "nist_alignment_pct": no.get("alignment_percentage", 0),
        "ce_blockers": c.get("blocked", 0),
        "average_readiness_pct": t["average_readiness"],
        "ai_grounding_score": assurance.get("avg_score"),
        "ai_checks": assurance.get("total", 0),
        "next_deadline": ctx.get("next_deadline"),
    }


def _snapshot_delta(cur: dict, prev: dict) -> dict:
    d = {}
    for k in ("classification_approved_pct", "ce_ready_pct", "control_compliance_pct",
              "nist_alignment_pct", "ai_grounding_score", "article14_overdue", "ce_blockers", "products"):
        a = cur.get(k); b = prev.get(k)
        if isinstance(a, (int, float)) and isinstance(b, (int, float)):
            d[k] = a - b
    return d


class CRASnapshotReq(BaseModel):
    label: str = Field(default="", max_length=80)


@cra_router.post("/exec-snapshot")
async def save_exec_snapshot(body: CRASnapshotReq, user: dict = Depends(get_current_user)):
    org_id = user["org_id"]
    kpis = await _cra_exec_kpis(org_id)
    doc = {"org_id": org_id, "at": iso(), "label": (body.label or datetime.now().strftime("%b %Y")).strip(),
           "kpis": kpis, "by": user.get("email"), "version": CRA_APP_VERSION}
    res = await db.cra_exec_snapshots.insert_one(doc)
    return {"ok": True, "id": str(res.inserted_id), "at": doc["at"], "label": doc["label"], "kpis": kpis}


@cra_router.get("/exec-snapshots")
async def list_exec_snapshots(user: dict = Depends(get_current_user)):
    org_id = user["org_id"]
    rows = await db.cra_exec_snapshots.find({"org_id": org_id}).sort("at", -1).to_list(24)
    out = [{"id": str(r["_id"]), "at": r.get("at"), "label": r.get("label"),
            "kpis": r.get("kpis", {}), "by": r.get("by")} for r in rows]
    for i, s in enumerate(out):
        older = out[i + 1] if i + 1 < len(out) else None
        s["delta"] = _snapshot_delta(s["kpis"], older["kpis"]) if older else None
    live = await _cra_exec_kpis(org_id)
    return {"current": live, "snapshots": out}


@cra_router.delete("/exec-snapshot/{sid}")
async def delete_exec_snapshot(sid: str, user: dict = Depends(get_current_user)):
    from bson import ObjectId
    try:
        oid = ObjectId(sid)
    except Exception:
        raise HTTPException(400, "Bad snapshot id")
    await db.cra_exec_snapshots.delete_one({"_id": oid, "org_id": user["org_id"]})
    return {"ok": True}


def _cra_exec_overview_html(org_name, kpis, nd, risk=None):
    def esc(s):
        return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    def cell(label, val):
        return (f'<td style="padding:10px 12px;border:1px solid #eef2f7;vertical-align:top">'
                f'<div style="font:700 9px Arial;letter-spacing:.05em;color:#6b7280;text-transform:uppercase">{label}</div>'
                f'<div style="font:800 18px Arial;color:#0f1e3d;margin-top:2px">{val}</div></td>')
    g = kpis.get("ai_grounding_score")
    rows = (
        f'<tr>{cell("Products", kpis.get("products", 0))}{cell("Classification approved", str(kpis.get("classification_approved_pct", 0)) + "%")}'
        f'{cell("CE market-ready", str(kpis.get("ce_ready_pct", 0)) + "%")}{cell("Article 14 overdue", kpis.get("article14_overdue", 0))}</tr>'
        f'<tr>{cell("Control compliance", str(kpis.get("control_compliance_pct", 0)) + "%")}{cell("NIST CSF alignment", str(kpis.get("nist_alignment_pct", 0)) + "%")}'
        f'{cell("CE blockers", kpis.get("ce_blockers", 0))}{cell("AI grounding", (str(g) + "%") if g is not None else "n/a")}</tr>')
    deadline = ""
    if nd:
        deadline = (f'<div style="background:#fff7ed;border:1px solid #fed7aa;border-radius:8px;padding:12px 14px;margin:12px 0;'
                    f'font:600 13px Arial;color:#b45309">{nd["days_remaining"]} days to the next CRA deadline &#8212; {esc(nd["label"])} on {esc(nd["date"])}.</div>')
    risk_html = ""
    if risk:
        rtone = {"Critical": "#dc2626", "High": "#ea580c", "Medium": "#ca8a04", "Low": "#16a34a"}
        idx = risk.get("risk_index", 0)
        cnt = risk.get("counts", {})
        top = "".join(
            f'<tr><td style="padding:5px 0;font:400 12px Arial;color:#1f2937;border-bottom:1px solid #f1f1f1">'
            f'<b style="color:{rtone.get(t.get("rating"), "#0f1e3d")}">{esc(t.get("rating"))}</b> &#183; {esc(t.get("title", ""))}'
            f'{" &#183; owner " + esc(t.get("owner")) if t.get("owner") else ""}</td></tr>'
            for t in (risk.get("top_risks") or []))
        idx_color = "#dc2626" if idx >= 60 else "#ea580c" if idx >= 35 else "#16a34a"
        risk_html = (
            '<div style="font:700 11px Arial;color:#6b7280;letter-spacing:.05em;margin-top:16px">CORRELATED RISK</div>'
            f'<div style="background:#f8fafc;border:1px solid #e5e7eb;border-radius:8px;padding:12px 14px;margin-top:6px">'
            f'<div style="font:800 26px Arial;color:{idx_color}">{idx}<span style="font:400 12px Arial;color:#6b7280"> / 100 risk index</span></div>'
            f'<div style="font:600 12px Arial;color:#6b7280;margin:2px 0 8px">Critical {cnt.get("Critical", 0)} &#183; High {cnt.get("High", 0)} &#183; Medium {cnt.get("Medium", 0)} &#183; Low {cnt.get("Low", 0)}</div>'
            f'<table width="100%">{top}</table></div>')
    return (
        '<table width="100%" cellpadding="0" cellspacing="0" style="max-width:640px;margin:auto;background:#fff"><tr><td style="padding:24px">'
        '<div style="font:800 18px Arial;color:#0f1e3d">EU CRA Executive Overview</div>'
        f'<div style="font:400 12px Arial;color:#6b7280;margin-bottom:6px">{esc(org_name)} &#183; Regulation (EU) 2024/2847 &#183; Obserra CRA v{CRA_APP_VERSION}</div>'
        f'{deadline}'
        f'{risk_html}'
        '<div style="font:700 11px Arial;color:#6b7280;letter-spacing:.05em;margin-top:8px">BOARD KPIs</div>'
        f'<table width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;margin-top:6px">{rows}</table>'
        '<div style="border-top:1px solid #e5e7eb;margin-top:16px;padding-top:10px;font:400 10px Arial;color:#9ca3af">'
        'The attached PDF has the full board rollup incl. NIST alignment and top control gaps. Grounded in live records; the AI grounding score reflects the hallucination monitor. Decision-support only &#8212; not legal advice or a guarantee of CRA conformity.</div>'
        '</td></tr></table>')


async def _send_cra_exec_overview_email(org, recipients) -> int:
    import base64
    from kernel import notifications
    org_id = str(org["_id"])
    ctx = await _cra_insight_context(org_id)
    controls = await _compute_controls(org_id)
    nist = await _compute_nist(org_id)
    assurance = await _cra_grounding_summary(org_id)
    insight = await compute_cra_insight(org_id, use_cache=False)
    kpis = await _cra_exec_kpis(org_id)
    try:
        risk = (await _compute_risk_correlation(org_id))["overall"]
    except Exception:
        risk = None
    html = _cra_exec_overview_html(org.get("name", "Your organization"), kpis, ctx.get("next_deadline"), risk)
    att = None
    try:
        raw = _cra_exec_overview_pdf(org.get("name", "Your organization"), ctx, controls, nist, assurance, insight)
        att = [{"filename": "obserra-eu-cra-executive-overview.pdf", "content": base64.b64encode(raw).decode()}]
    except Exception:
        att = None
    sent = 0
    for r in recipients:
        await notifications.send_email(r["email"], "EU CRA Executive Overview — board briefing", html, attachments=att)
        sent += 1
    return sent


class CRAExecEmailSchedule(BaseModel):
    enabled: bool = False
    day_of_week: int = Field(0, ge=0, le=6)
    hour_utc: int = Field(8, ge=0, le=23)


@cra_router.get("/exec-email/settings")
async def get_exec_email_settings(user: dict = Depends(get_current_user)):
    from bson import ObjectId
    org = await db.organizations.find_one({"_id": ObjectId(user["org_id"])}, {"_id": 0, "cra_exec_email": 1})
    cfg = (org or {}).get("cra_exec_email") or {}
    return {"schedule": {"enabled": cfg.get("enabled", False), "day_of_week": int(cfg.get("day_of_week", 0)), "hour_utc": int(cfg.get("hour_utc", 8))},
            "is_admin": user.get("role") == "admin", "last_sent_week": cfg.get("last_sent_week")}


@cra_router.put("/exec-email/settings")
async def update_exec_email_settings(body: CRAExecEmailSchedule, admin: dict = Depends(require_roles("admin"))):
    from bson import ObjectId
    await db.organizations.update_one({"_id": ObjectId(admin["org_id"])}, {"$set": {
        "cra_exec_email.enabled": body.enabled, "cra_exec_email.day_of_week": body.day_of_week, "cra_exec_email.hour_utc": body.hour_utc}})
    return {"ok": True, "schedule": body.model_dump()}


@cra_router.post("/exec-email/send-now")
async def send_exec_email_now(user: dict = Depends(get_current_user)):
    from bson import ObjectId
    if not await db.cra_products.find_one({"org_id": user["org_id"]}, {"_id": 0, "ref": 1}):
        raise HTTPException(400, "Add or load a CRA product first — there is nothing to brief yet.")
    org = await db.organizations.find_one({"_id": ObjectId(user["org_id"])})
    await _send_cra_exec_overview_email(org, [{"email": user["email"]}])
    return {"ok": True, "sent_to": user["email"]}


@cra_router.get("/exec-email/preview")
async def exec_email_preview(user: dict = Depends(get_current_user)):
    from bson import ObjectId
    org = await db.organizations.find_one({"_id": ObjectId(user["org_id"])}, {"_id": 0, "name": 1})
    kpis = await _cra_exec_kpis(user["org_id"])
    ctx = await _cra_insight_context(user["org_id"])
    try:
        risk = (await _compute_risk_correlation(user["org_id"]))["overall"]
    except Exception:
        risk = None
    html = _cra_exec_overview_html((org or {}).get("name", "Your organization"), kpis, ctx.get("next_deadline"), risk)
    return {"html": html, "subject": "EU CRA Executive Overview — board briefing"}


@cra_router.post("/exec-overview-link")
async def create_exec_overview_link(admin: dict = Depends(require_roles("admin"))):
    org_id = admin["org_id"]
    active = await db.cra_portal_tokens.count_documents(
        {"org_id": org_id, "role": "exec_overview", "revoked_at": None, "expires_at": {"$gt": utcnow()}})
    if active >= 5:
        raise HTTPException(429, "This organisation already has 5 active Executive Overview links. Revoke or wait for existing links to expire before minting more.")
    issued = await issue_portal_token(org_id, "", "exec_overview", None, None, "", 720, admin.get("email", "unknown"))
    await ledger_append(org_id, admin.get("email", "unknown"), "exec_overview_link.issued", "organization", org_id, ["Article 13"], {"expires_at": issued["expires_at"]})
    return {"token": issued["token"], "expires_at": issued["expires_at"], "path": f"/exec-overview/{issued['token']}"}


@cra_router.get("/exec-overview-links")
async def list_exec_overview_links(admin: dict = Depends(require_roles("admin"))):
    org_id = admin["org_id"]
    active = await db.cra_portal_tokens.count_documents(
        {"org_id": org_id, "role": "exec_overview", "revoked_at": None, "expires_at": {"$gt": utcnow()}})
    return {"active": active}


@cra_router.post("/exec-overview-link/revoke")
async def revoke_exec_overview_links(admin: dict = Depends(require_roles("admin"))):
    org_id = admin["org_id"]
    result = await db.cra_portal_tokens.update_many(
        {"org_id": org_id, "role": "exec_overview", "revoked_at": None}, {"$set": {"revoked_at": utcnow()}})
    return {"ok": True, "revoked": result.modified_count}


@cra_public_router.get("/exec-overview/{raw_token}")
async def public_exec_overview(raw_token: str):
    from bson import ObjectId
    token = await verify_portal_token(raw_token)
    if token.get("role") != "exec_overview":
        raise HTTPException(403, "This link is not an Executive Overview link")
    org_id = token["org_id"]
    org = await db.organizations.find_one({"_id": ObjectId(org_id)}, {"_id": 0, "name": 1})
    kpis = await _cra_exec_kpis(org_id)
    controls = await _compute_controls(org_id)
    nist = await _compute_nist(org_id)
    ctx = await _cra_insight_context(org_id)
    try:
        risk = (await _compute_risk_correlation(org_id))["overall"]
    except Exception:
        risk = {}
    snaps = await db.cra_exec_snapshots.find({"org_id": org_id}).sort("at", -1).to_list(1)
    prev = snaps[0] if snaps else None
    snapshot_delta = _snapshot_delta(kpis, prev.get("kpis", {})) if prev else None
    previous_snapshot = {"label": prev.get("label"), "at": prev.get("at")} if prev else None
    return {
        "role": "exec_overview",
        "organization": (org or {}).get("name", "Organization"),
        "regulation": CRA_VERSION,
        "version": CRA_APP_VERSION,
        "generated_at": iso(),
        "expires_at": token["expires_at"].isoformat(),
        "kpis": kpis,
        "classifications": ctx.get("by_class", {}),
        "controls": controls["overall"],
        "nist": {"overall": nist["overall"], "functions": nist["functions"]},
        "next_deadline": _cra_next_deadline(),
        "risk": risk,
        "previous_snapshot": previous_snapshot,
        "snapshot_delta": snapshot_delta,
        "note": "Read-only Executive Overview. Product names and internal records are not exposed.",
    }


async def _run_cra_exec_overview_tick():
    """Hourly gate: send each org's Executive Overview board email at its own configured UTC day + hour."""
    import logging
    from kernel import notifications
    logger = logging.getLogger("obserra.cra")
    now = utcnow()
    week_key = now.strftime("%G-W%V")
    orgs = await db.organizations.find({}).to_list(1000)
    for org in orgs:
        org_id = str(org["_id"])
        try:
            cfg = org.get("cra_exec_email") or {}
            if not cfg.get("enabled", False):
                continue
            if int(cfg.get("day_of_week", 0)) != now.weekday() or int(cfg.get("hour_utc", 8)) != now.hour:
                continue
            if cfg.get("last_sent_week") == week_key:
                continue
            if not await db.cra_products.find_one({"org_id": org_id}, {"_id": 0, "ref": 1}):
                continue
            recipients = await _cra_digest_recipients(org_id)
            if recipients:
                sent = await _send_cra_exec_overview_email(org, recipients)
                await notifications.create(org_id, "report", "CRA Executive Overview board email sent",
                                           f"Emailed the EU CRA Executive Overview to {sent} recipient(s).", ref="cra-exec-overview")
                logger.info(f"CRA exec overview email sent for org {org_id}: {sent} recipient(s)")
            await db.organizations.update_one({"_id": org["_id"]}, {"$set": {"cra_exec_email.last_sent_week": week_key}})
        except Exception as e:
            logger.error(f"CRA exec overview tick failed for org {org_id}: {e}")


# ---------------------------------------------------------------------------
# Executive Overview — richer board PDF + reusable grounding summary/trend.
# ---------------------------------------------------------------------------
async def _cra_grounding_summary(org_id: str, days: int = 30) -> dict:
    """Aggregate CRA AI grounding scores + a continuous per-day trend for sparklines."""
    since = (utcnow() - timedelta(days=days)).isoformat()
    rows = await db.ai_grounding_log.find(
        {"org_id": org_id, "surface": {"$regex": "^cra:"}, "at": {"$gte": since}},
        {"_id": 0, "score": 1, "at": 1, "flagged_count": 1}).to_list(3000)
    scored = [r["score"] for r in rows if isinstance(r.get("score"), int)]
    avg = round(sum(scored) / len(scored)) if scored else None
    flagged = sum(1 for r in rows if (r.get("flagged_count") or 0) > 0)
    by_day = {}
    for r in rows:
        d = (r.get("at") or "")[:10]
        if not d:
            continue
        b = by_day.setdefault(d, {"_ss": 0, "_sc": 0})
        if isinstance(r.get("score"), int):
            b["_ss"] += r["score"]
            b["_sc"] += 1
    trend = []
    for i in range(days - 1, -1, -1):
        day = (utcnow() - timedelta(days=i)).strftime("%Y-%m-%d")
        b = by_day.get(day)
        trend.append({"date": day, "score": round(b["_ss"] / b["_sc"]) if (b and b["_sc"]) else None,
                      "count": (b["_sc"] if b else 0)})
    return {"avg_score": avg, "total": len(rows), "flagged_total": flagged, "trend": trend}


def _cra_exec_overview_pdf(org_name, ctx, controls, nist, assurance, insight):
    from io import BytesIO
    from reportlab.lib.pagesizes import LETTER
    from reportlab.lib.units import inch
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable

    def x(s):
        return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    def bar(p):
        p = max(0, min(100, int(p or 0)))
        filled = round(p / 10)
        return "\u2588" * filled + "\u2591" * (10 - filled)

    buf = BytesIO()
    styles = getSampleStyleSheet()
    navy = colors.HexColor("#0f1e3d"); ai = colors.HexColor("#12b4d6"); grey = colors.HexColor("#e5e7eb")
    title = ParagraphStyle("t", parent=styles["Title"], fontSize=18, textColor=navy, spaceAfter=2)
    sub = ParagraphStyle("s", parent=styles["Normal"], fontSize=9, textColor=colors.grey)
    h = ParagraphStyle("h", parent=styles["Heading2"], fontSize=12, textColor=ai, spaceBefore=10, spaceAfter=4)
    body = ParagraphStyle("b", parent=styles["BodyText"], fontSize=10, leading=14)
    mono = ParagraphStyle("m", parent=styles["Normal"], fontSize=9, fontName="Courier")

    t = ctx["totals"]; cnt = ctx["counts"]; tot = t["products"] or 1
    co = controls.get("overall", {}); no = nist.get("overall", {})
    nd = insight.get("next_deadline") or ctx.get("next_deadline")
    avg = assurance.get("avg_score")

    doc = SimpleDocTemplate(buf, pagesize=LETTER, topMargin=0.7 * inch, bottomMargin=0.7 * inch, title="EU CRA Executive Overview")
    story = [Paragraph("EU CRA Executive Overview", title),
             Paragraph(f"{x(org_name)} &#183; Regulation (EU) 2024/2847 &#183; Obserra CRA v{CRA_APP_VERSION} &#183; {datetime.now().strftime('%d %B %Y')}", sub),
             HRFlowable(width="100%", color=ai), Spacer(1, 8),
             Paragraph(x(insight.get("headline", "")), body)]
    if nd:
        story.append(Paragraph(f"<b>Next statutory deadline:</b> {x(nd['label'])} on {nd['date']} ({nd['days_remaining']} days).", body))

    story.append(Paragraph("Board KPIs", h))
    kpis = [["Products under CRA", str(t["products"])],
            ["Classification approved", f"{t['classification_approved']}/{t['products']} ({round(t['classification_approved']/tot*100)}%)"],
            ["CE market-ready", f"{t['ce_ready']}/{t['products']} ({round(t['ce_ready']/tot*100)}%)"],
            ["Article 14 overdue clocks", str(cnt.get("overdue_clocks", 0))],
            ["Control compliance", f"{co.get('percentage', 0)}% ({co.get('implemented', 0)} implemented, {co.get('partial', 0)} partial)"],
            ["NIST CSF 2.0 alignment", f"{no.get('alignment_percentage', 0)}% ({no.get('functions_aligned', 0)}/{no.get('functions_total', 6)} functions)"],
            ["CE blockers", str(cnt.get("blocked", 0))],
            ["AI grounding score", (f"{avg}%" if avg is not None else "n/a") + f" ({assurance.get('total', 0)} answers checked)"]]
    tbl = Table(kpis, colWidths=[3.0 * inch, 3.4 * inch])
    tbl.setStyle(TableStyle([("FONTSIZE", (0, 0), (-1, -1), 10), ("TEXTCOLOR", (0, 0), (0, -1), navy),
                             ("LINEBELOW", (0, 0), (-1, -1), 0.3, grey),
                             ("BOTTOMPADDING", (0, 0), (-1, -1), 5), ("TOPPADDING", (0, 0), (-1, -1), 5)]))
    story.append(tbl)

    story.append(Paragraph("NIST CSF 2.0 function alignment", h))
    for f in nist.get("functions", []):
        story.append(Paragraph(f"{x(f['code'])} {x(f['name'])} &nbsp; {bar(f.get('compliance_rate'))} &nbsp; {f.get('compliance_rate', 0)}% ({x(f.get('risk', ''))})", mono))

    gaps = sorted([c for c in controls.get("controls", []) if c.get("status") != "Implemented"],
                  key=lambda c: (c.get("compliance_rate") if c.get("compliance_rate") is not None else -1))[:6]
    if gaps:
        story.append(Paragraph("Top control gaps", h))
        grows = [["Requirement", "Status", "%"]] + [[f"{g['requirement_id']} — {g['title'][:52]}", g.get("status", ""), f"{g.get('compliance_rate', 0)}%"] for g in gaps]
        gt = Table(grows, colWidths=[4.4 * inch, 1.3 * inch, 0.7 * inch])
        gt.setStyle(TableStyle([("FONTSIZE", (0, 0), (-1, -1), 8.5), ("TEXTCOLOR", (0, 1), (0, -1), navy),
                                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f1f5f9")),
                                ("LINEBELOW", (0, 0), (-1, -1), 0.3, grey),
                                ("BOTTOMPADDING", (0, 0), (-1, -1), 4), ("TOPPADDING", (0, 0), (-1, -1), 4)]))
        story.append(gt)

    story.append(Paragraph("Recommended actions", h))
    for a in insight.get("actions", [])[:5]:
        story.append(Paragraph(f"&#8226; {x(a)}", body))
    story += [Spacer(1, 10), HRFlowable(width="100%", color=grey),
              Paragraph("Compiled live from Obserra records; every figure is grounded and the AI grounding score reflects the hallucination monitor. Classifications are proposed until authorised approval. Decision-support only &#8212; not legal advice or a guarantee of CRA conformity.", sub)]
    doc.build(story)
    return buf.getvalue()


@cra_router.get("/executive-overview.pdf")
async def download_executive_overview(user: dict = Depends(get_current_user)):
    from fastapi.responses import Response
    from bson import ObjectId
    org_id = user["org_id"]
    if not await db.cra_products.find_one({"org_id": org_id}, {"_id": 0, "ref": 1}):
        raise HTTPException(400, "Add or load a CRA product first — there is nothing to brief yet.")
    org = await db.organizations.find_one({"_id": ObjectId(org_id)})
    ctx = await _cra_insight_context(org_id)
    controls = await _compute_controls(org_id)
    nist = await _compute_nist(org_id)
    insight = await compute_cra_insight(org_id)
    assurance = await _cra_grounding_summary(org_id)
    pdf = _cra_exec_overview_pdf((org or {}).get("name", "Your organization"), ctx, controls, nist, assurance, insight)
    return Response(content=pdf, media_type="application/pdf",
                    headers={"Content-Disposition": "attachment; filename=obserra-eu-cra-executive-overview.pdf"})
