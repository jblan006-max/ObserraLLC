from dotenv import load_dotenv
from pathlib import Path
load_dotenv(Path(__file__).parent / ".env")

import os
import logging
from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.gzip import GZipMiddleware

from db import db, client
from auth import auth_router, seed_admin
from routes import api as domain_api
from ai_advisor import advisor_router
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
from starlette.middleware.sessions import SessionMiddleware

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = FastAPI(title="Obserra EIOS")

app.include_router(auth_router)
app.include_router(domain_api)
app.include_router(advisor_router)
app.include_router(payments_router)
app.include_router(reports_router)
app.include_router(kernel_router)
app.include_router(scheduled_router)
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
    resp.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'; base-uri 'none'"
    resp.headers["Cross-Origin-Opener-Policy"] = "same-origin"
    resp.headers["Cache-Control"] = resp.headers.get("Cache-Control", "no-store")
    return resp


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
