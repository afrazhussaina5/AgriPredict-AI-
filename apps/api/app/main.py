"""AgriPredict AI FastAPI application factory.

Phase 1: application shell, CORS, versioned health/readiness routes.
Phase 3: database engine lifecycle and uniform error handling.
Authentication, marketplace and ML arrive in later phases.
"""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.v1.router import api_router
from .core.config import Settings, get_settings, validate_settings
from .core.database import dispose_engine, init_engine
from .core.errors import register_exception_handlers
from .core.logging import configure_logging

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Log safe startup/shutdown information (no secrets, ever)."""
    settings: Settings = app.state.settings
    logger.info(
        "Starting %s v%s | environment=%s | docs=%s",
        settings.APP_NAME,
        settings.APP_VERSION,
        settings.ENVIRONMENT,
        app.docs_url,
    )
    # Non-fatal in development: the API can serve without a database.
    # Production already failed closed in validate_settings().
    init_engine(settings)
    yield
    await dispose_engine()
    logger.info("Shutting down %s", settings.APP_NAME)


def create_app() -> FastAPI:
    """Build and configure the FastAPI application."""
    settings = get_settings()
    validate_settings(settings)
    configure_logging(settings.LOG_LEVEL)

    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description=(
            "AgriPredict AI backend. Phase 1 exposes health and readiness; "
            "Phase 3 adds the database foundation. Authentication, marketplace "
            "and forecasting arrive in later phases."
        ),
        lifespan=lifespan,
    )
    app.state.settings = settings
    register_exception_handlers(app)

    # Explicit allow-list. Wildcard origins are never allowed (secure default).
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "Accept-Language"],
    )

    app.include_router(api_router, prefix="/api/v1")

    @app.get("/", include_in_schema=False)
    async def index() -> dict[str, str]:
        """Service index - intentionally contains no sensitive data."""
        return {
            "service": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "environment": settings.ENVIRONMENT,
            "docs": "/docs",
            "health": "/api/v1/health",
            "readiness": "/api/v1/ready",
        }

    return app


app = create_app()
