"""
Echelon FastAPI Application Factory

Entry point for the API container. Creates and configures the FastAPI app,
registers routers, sets up middleware, and initializes the database connection.
"""
import logging
from contextlib import asynccontextmanager

_config_logger = logging.getLogger(__name__)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.config import settings
from app.database import engine
from app.routers import auth, convergence, signals, copilot, alerts, health, evidence, export, cyber, events, imagery, investigations

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
        version="0.2.0",
        lifespan=lifespan,
        docs_url="/api/docs" if settings.debug else None,
        redoc_url="/api/redoc" if settings.debug else None,
        openapi_url="/api/openapi.json" if settings.debug else None,
    )

    # SECURITY: reject wildcard origins with credentials — browsers block this
    # anyway, but guard against misconfiguration
    cors_origins = [o for o in settings.allowed_origins if o != "*"]
    if len(cors_origins) != len(settings.allowed_origins):
        _config_logger.warning("CORS: removed '*' from allowed_origins — wildcard is incompatible with allow_credentials=True")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "DELETE", "PATCH"],
        allow_headers=[
            "Content-Type",
            "Authorization",
            "X-LLM-Key",
            "X-Anthropic-Key",
            "X-Shodan-Key",
            "X-Censys-Id",
            "X-Censys-Secret",
            "X-WiGLE-Name",
            "X-WiGLE-Token",
        ],
    )

    # Register slowapi rate-limit handler (used by copilot endpoint)
    from app.routers.copilot import limiter
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
    app.include_router(convergence.router, prefix="/api/convergence", tags=["convergence"])
    app.include_router(signals.router, prefix="/api/signals", tags=["signals"])
    app.include_router(copilot.router, prefix="/api/copilot", tags=["copilot"])
    app.include_router(alerts.router, prefix="/api/alerts", tags=["alerts"])
    app.include_router(health.router, prefix="/api/health", tags=["health"])
    app.include_router(evidence.router, prefix="/api/evidence", tags=["evidence"])
    app.include_router(export.router, prefix="/api/export", tags=["export"])
    app.include_router(cyber.router, prefix="/api/cyber", tags=["cyber"])
    app.include_router(events.router, prefix="/api/events", tags=["events"])
    app.include_router(imagery.router, prefix="/api/imagery", tags=["imagery"])
    app.include_router(investigations.router, prefix="/api/investigations", tags=["investigations"])

    return app


app = create_app()
