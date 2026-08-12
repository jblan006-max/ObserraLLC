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
    }

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


async def _run_cra_analyst_weekly_digest():
    import logging
    from kernel import notifications
    logger = logging.getLogger("obserra.cra")
    orgs = await db.organizations.find({}).to_list(1000)
    for org in orgs:
        org_id = str(org["_id"])
        try:
            if not await db.cra_products.find_one({"org_id": org_id}, {"_id": 0, "ref": 1}):
                continue
            recipients = await db.users.find(
                {"org_id": org_id, "role": {"$in": ["admin", "executive"]}},
                {"_id": 0, "email": 1, "digest_cadence": 1}).to_list(200)
            recipients = [r for r in recipients if r.get("digest_cadence", "weekly") == "weekly"]
            if not recipients:
                continue
            ctx = await _cra_insight_context(org_id)
            insight = await compute_cra_insight(org_id, use_cache=False)
            html = _cra_analyst_digest_html(org.get("name", "Your organization"), insight, ctx)
            for r in recipients:
                await notifications.send_email(r["email"], "CRA AI Analyst — your weekly EU CRA briefing", html)
            await notifications.create(
                org_id, "report", "CRA AI Analyst weekly briefing sent",
                f"Emailed the EU CRA executive briefing to {len(recipients)} recipient(s).", ref="cra-analyst-digest")
            logger.info(f"CRA analyst digest sent for org {org_id}: {len(recipients)} recipient(s)")
        except Exception as e:
            logger.error(f"CRA analyst digest failed for org {org_id}: {e}")
