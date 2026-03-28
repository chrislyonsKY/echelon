"""
Echelon FastAPI Application Factory

Entry point for the API container. Creates and configures the FastAPI app,
registers routers, sets up middleware, and initializes the database connection.
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import engine
from app.routers import auth, convergence, signals, copilot, alerts, health, evidence, export, cyber

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan — startup and shutdown."""
    logger.info("Echelon API starting up")
    from app.services.reference_data import load_reference_data
    from app.services.maritime_ref import load_maritime_data
    await load_reference_data()
    await load_maritime_data()
    yield
    logger.info("Echelon API shutting down")
    await engine.dispose()


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="Echelon API",
        description="GEOINT conflict and maritime activity monitoring dashboard",
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "DELETE", "PATCH"],
        allow_headers=["*"],
    )

    app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
    app.include_router(convergence.router, prefix="/api/convergence", tags=["convergence"])
    app.include_router(signals.router, prefix="/api/signals", tags=["signals"])
    app.include_router(copilot.router, prefix="/api/copilot", tags=["copilot"])
    app.include_router(alerts.router, prefix="/api/alerts", tags=["alerts"])
    app.include_router(health.router, prefix="/api/health", tags=["health"])
    app.include_router(evidence.router, prefix="/api/evidence", tags=["evidence"])
    app.include_router(export.router, prefix="/api/export", tags=["export"])
    app.include_router(cyber.router, prefix="/api/cyber", tags=["cyber"])

    return app


app = create_app()
