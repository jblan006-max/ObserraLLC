from dotenv import load_dotenv
from pathlib import Path
load_dotenv(Path(__file__).parent / ".env", override=False)

import os
import logging
from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.gzip import GZipMiddleware

from db import db, client
from auth import auth_router, seed_admin
from routes import api as domain_api
from ai_advisor import advisor_router
from hallucination import hallucination_router
from payments import payments_router, setup_catalog
from reports import reports_router
from kernel.routes import kernel_router
from scheduled import scheduled_router
from enterprise import enterprise_router
from live_connectors import live_connectors_router
from agents import agents_router
from tpr import tpr_router
from insights import insights_router
from cyber import cyber_router
from studio import studio_router
from metrics import metrics_router
from social_auth import social_router
from sso_config import sso_config_router
from push import push_router
from deploy import deploy_router
from self_scan import self_scan_router
from dashboards import dash_router
from risk_engine import risk_engine_router
from connectors_catalog import connectors_router
from control_intelligence import ci_router
import ci_demo  # noqa: F401 — registers demo-journey routes on ci_router
import ci_auditor  # noqa: F401 — registers auditor-link / brief-delivery / nudge-pref routes
import ci_recap  # noqa: F401 — registers engagement follow-up / recap / timeline routes
from sap_uac import sap_router, seed_sap_uac
from starlette.middleware.sessions import SessionMiddleware

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = FastAPI(title="Obserra EIOS")

app.include_router(auth_router)
app.include_router(domain_api)
app.include_router(advisor_router)
app.include_router(hallucination_router)
app.include_router(payments_router)
app.include_router(reports_router)
app.include_router(kernel_router)
app.include_router(scheduled_router)
app.include_router(ci_router)
app.include_router(enterprise_router)
app.include_router(agents_router)
app.include_router(tpr_router)
app.include_router(insights_router)
app.include_router(cyber_router)
app.include_router(studio_router)
app.include_router(live_connectors_router)
app.include_router(metrics_router)
app.include_router(social_router)
app.include_router(sso_config_router)
app.include_router(push_router)
app.include_router(deploy_router)
app.include_router(self_scan_router)
app.include_router(dash_router)
app.include_router(connectors_router)
app.include_router(risk_engine_router)
app.include_router(sap_router)

# Obserra Cyber Crisis Commander domain
from crisis_commander import api as crisis_commander_api
app.include_router(crisis_commander_api)

# Obserra EU Cyber Resilience Act (CRA) Governance domain
from cra_governance import cra_router, cra_public_router, ensure_cra_indexes
app.include_router(cra_router)
app.include_router(cra_public_router)

_cors = os.environ.get("CORS_ORIGINS", "*").strip()
_cors_kwargs = {"allow_origin_regex": ".*"} if _cors == "*" else {"allow_origins": [o.strip() for o in _cors.split(",") if o.strip()]}
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    **_cors_kwargs,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Compress large JSON/text responses (e.g. the 67KB connector catalog, correlation payloads) so
# they transfer + parse faster in the browser. Browsers set Accept-Encoding automatically.
app.add_middleware(GZipMiddleware, minimum_size=1024)


# Signed session cookie for OAuth state/nonce (Apple form_post + OIDC via Authlib).
app.add_middleware(SessionMiddleware, secret_key=os.environ["JWT_SECRET"],
                   https_only=True, same_site="lax", max_age=600)


# Security hardening — response headers aligned to NIST 800-53 (SC-8/SC-18/SI-10),
# ISO 27001 A.8.x, SOC 2 CC6/CC7 and CISA CPGs. Applied to all API responses.
@app.middleware("http")
async def security_headers(request, call_next):
    resp = await call_next(request)
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["X-Frame-Options"] = "DENY"
    resp.headers["Referrer-Policy"] = "no-referrer"
    resp.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    resp.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    # Backend-rendered public HTML pages (the auditor Audit Room portal, verification page) carry their
    # own inline scripts/styles and data:/https logos, so they need a scoped CSP. Every JSON/PDF API
    # response keeps the strictest 'default-src none'. (The React admin app HTML is served by the frontend.)
    if resp.headers.get("content-type", "").startswith("text/html"):
        resp.headers["Content-Security-Policy"] = (
            "default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; "
            "img-src 'self' data: https:; connect-src 'self'; form-action 'self'; "
            "base-uri 'none'; frame-ancestors 'none'"
        )
    else:
        resp.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'; base-uri 'none'"
    resp.headers["Cross-Origin-Opener-Policy"] = "same-origin"
    resp.headers["Cache-Control"] = resp.headers.get("Cache-Control", "no-store")
    return resp


_APP_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _app_version():
    try:
        with open(os.path.join(_APP_ROOT, "VERSION")) as f:
            return f.read().strip() or "1.0.0"
    except Exception:
        return "1.0.0"


@app.get("/api/health")
async def health():
    """Liveness/readiness + deep checks for install.sh, load balancers and uptime dashboards."""
    import time
    checks = {}
    t0 = time.perf_counter()
    db_ok = True
    try:
        await client.admin.command("ping")
    except Exception:
        db_ok = False
    checks["db"] = {"ok": db_ok, "latency_ms": round((time.perf_counter() - t0) * 1000, 1)}
    try:
        checks["organizations"] = await db.organizations.count_documents({})
    except Exception:
        checks["organizations"] = None
    try:
        total = await db.sap_connectors.count_documents({})
        connected = await db.sap_connectors.count_documents({"status": "connected"})
        checks["connectors"] = {"connected": connected, "total": total}
    except Exception:
        checks["connectors"] = None
    try:
        last = await db.audit_logs.find_one(sort=[("ts", -1)])
        checks["scheduler"] = {"cron_configured": bool(os.environ.get("WEBHOOK_CRON_SECRET")),
                               "last_activity": (last or {}).get("ts")}
    except Exception:
        checks["scheduler"] = None
    return {"status": "ok" if db_ok else "degraded", "service": "obserra-sap-uac",
            "version": _app_version(), "db": db_ok, "checks": checks}


@app.on_event("startup")
async def startup():
    await db.users.create_index("email", unique=True)
    await db.login_attempts.create_index("identifier")
    await db.risks.create_index([("org_id", 1), ("ref", 1)])
    await db.ai_systems.create_index([("org_id", 1), ("ref", 1)])
    await db.audit_logs.create_index([("org_id", 1), ("ts", -1)])
    await db.qr_sessions.create_index("expireAt", expireAfterSeconds=0)
    await db.notifications.create_index([("org_id", 1), ("created_at", -1)])
    await db.notifications.create_index([("org_id", 1), ("dedupe_key", 1)])
    await seed_admin()
    try:
        await ensure_cra_indexes()
        logger.info("EU CRA governance indexes ready")
    except Exception as e:
        logger.warning(f"CRA index setup skipped: {e}")
    try:
        orgs = await db.organizations.find({}, {"_id": 1}).to_list(1000)
        for o in orgs:
            await seed_sap_uac(str(o["_id"]))
        logger.info("SAP UAC access snapshot ready")
    except Exception as e:
        logger.warning(f"SAP UAC seed skipped: {e}")
    try:
        from deploy import regenerate_guides
        regenerate_guides()
        logger.info("Install/User guides regenerated")
    except Exception as e:
        logger.warning(f"Guide regeneration skipped: {e}")
    try:
        setup_catalog()
        logger.info("Stripe catalog ready")
    except Exception as e:
        logger.warning(f"Stripe catalog setup skipped: {e}")
    # First one-click-install boot: go live on THIS endpoint (record it, enable the
    # daily autonomous engine, run an initial live scan). Backgrounded so startup isn't blocked.
    try:
        import asyncio
        from self_scan import bootstrap_first_install, _finalize_applied_jobs
        asyncio.create_task(bootstrap_first_install())
        asyncio.create_task(_finalize_applied_jobs())
    except Exception as e:
        logger.warning(f"First-install bootstrap skipped: {e}")


@app.on_event("shutdown")
async def shutdown():
    client.close()
