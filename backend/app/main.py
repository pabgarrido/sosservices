"""
SOS Services — FastAPI Application Entry Point

Real-time geospatial hazard correlation platform for Portugal.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.api.routes import router as api_router
from app.api.websocket import router as ws_router
from app.ingestion.scheduler import scheduler

# Logging
logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("sosservices")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start ingestion scheduler on startup, stop on shutdown."""
    logger.info("SOS Services starting — initializing data ingestion...")
    await scheduler.start()
    logger.info("Ingestion scheduler started")
    yield
    logger.info("Shutting down ingestion scheduler...")
    await scheduler.stop()


app = FastAPI(
    title="SOS Services",
    description=(
        "Real-time geospatial hazard correlation platform for Portugal. "
        "Aggregates weather, fire, emergency, and event data to detect "
        "compound hazards and surface risk alerts."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

# Parse configured origins
cors_origins = [o.strip() for o in settings.cors_allow_origins.split(",") if o.strip()]
allow_credentials = settings.cors_allow_credentials
if "*" in cors_origins and allow_credentials:
    logger.warning("CORS '*' with credentials is invalid in browsers; forcing allow_credentials=False")
    allow_credentials = False

# CORS — allow frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins or ["http://localhost:3000"],
    allow_credentials=allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount routes
app.include_router(api_router, prefix="/api")
app.include_router(ws_router)


@app.get("/")
async def root():
    return {
        "service": "SOS Services",
        "version": "0.1.0",
        "description": "Portugal Real-Time Hazard Monitor",
        "docs": "/docs",
    }


@app.get("/health")
async def health():
    statuses = scheduler.get_status()
    healthy_count = sum(1 for s in statuses if s.healthy)
    return {
        "status": "ok" if healthy_count > 0 else "degraded",
        "adapters_healthy": healthy_count,
        "adapters_total": len(statuses),
    }
