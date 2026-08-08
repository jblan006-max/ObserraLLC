"""Reset the SAP UAC discovered snapshot to a clean, consistent state (re-seeds on next access)."""
from pymongo import MongoClient

env = {}
for line in open("/app/backend/.env"):
    s = line.strip()
    if "=" in s and not s.startswith("#"):
        k, v = s.split("=", 1)
        env[k] = v.strip().strip('"')

client = MongoClient(env["MONGO_URL"])
db = client[env["DB_NAME"]]
cols = ["sap_persons", "sap_accounts", "sap_systems", "sap_roles", "sap_connectors", "sap_meta",
        "sap_activation", "sap_activation_events", "sap_snow_tickets", "sap_mitigations",
        "sap_hr_decisions", "sap_access_requests", "sap_certifications", "sap_cert_items"]
for c in cols:
    db[c].drop()
print("SAP UAC state reset — will re-seed a fresh snapshot on next access.")
