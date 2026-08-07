from dotenv import load_dotenv
from pathlib import Path
load_dotenv(Path(__file__).parent / ".env")

import os
import logging
from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware

from db import db, client
from auth import auth_router, seed_admin
from routes import api as domain_api
from ai_advisor import advisor_router
from payments import payments_router, setup_catalog
from reports import reports_router
from kernel.routes import kernel_router
from scheduled import scheduled_router
from enterprise import enterprise_router
from agents import agents_router
from tpr import tpr_router
from insights import insights_router

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

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=[os.environ.get("FRONTEND_URL", "http://localhost:3000"), "http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)


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
        setup_catalog()
        logger.info("Stripe catalog ready")
    except Exception as e:
        logger.warning(f"Stripe catalog setup skipped: {e}")


@app.on_event("shutdown")
async def shutdown():
    client.close()
