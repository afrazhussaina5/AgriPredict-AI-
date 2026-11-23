"""Health and readiness endpoints (Phase 1)."""

from datetime import UTC, datetime

from fastapi import APIRouter

from ...core.config import describe_database_target, get_settings, validate_settings
from ...core.database import check_connection
from ...schemas.health import HealthResponse, ReadinessCheck, ReadinessResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse, summary="Liveness probe")
def health() -> HealthResponse:
    """Return basic service information. Contains no secrets."""
    settings = get_settings()
    return HealthResponse(
        status="ok",
        service=settings.APP_NAME,
        version=settings.APP_VERSION,
        environment=settings.ENVIRONMENT,
        timestamp=datetime.now(UTC),
    )


@router.get("/ready", response_model=ReadinessResponse, summary="Readiness probe")
async def ready() -> ReadinessResponse:
    """Report whether the service can accept traffic.

    Checks configuration and (Phase 3+) database connectivity. The target is
    described without any credential material.
    """
    settings = get_settings()
    checks: list[ReadinessCheck] = []

    try:
        validate_settings(settings)
        checks.append(ReadinessCheck(name="configuration", status="ok"))
    except RuntimeError as exc:
        # The message is written by us and never contains secret values.
        checks.append(ReadinessCheck(name="configuration", status="failed", detail=str(exc)))

    has_origins = bool(settings.cors_origins)
    checks.append(
        ReadinessCheck(
            name="cors_allow_list",
            status="ok" if has_origins else "failed",
            detail=None if has_origins else "CORS_ORIGINS_STR is empty.",
        )
    )

    db_ok, db_detail = await check_connection()
    checks.append(
        ReadinessCheck(
            name="database",
            status="ok" if db_ok else "failed",
            detail=db_detail,
        )
    )
    checks.append(
        ReadinessCheck(
            name="database_target",
            status="ok",
            detail=describe_database_target(settings),
        )
    )
    all_ok = all(check.status == "ok" for check in checks)
    return ReadinessResponse(
        status="ready" if all_ok else "not_ready",
        checks=checks,
        timestamp=datetime.now(UTC),
    )
