"""Response schemas for the health and readiness endpoints."""

from datetime import datetime

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """Liveness payload returned by ``GET /api/v1/health``."""

    status: str = Field(description="Always 'ok' when the process is running.")
    service: str = Field(description="Service name.")
    version: str = Field(description="Application version.")
    environment: str = Field(
        description="Active environment (development/staging/production/test)."
    )
    timestamp: datetime = Field(description="Server time in UTC (ISO-8601).")


class ReadinessCheck(BaseModel):
    """A single readiness check result."""

    name: str = Field(description="Check name, e.g. 'configuration'.")
    status: str = Field(description="'ok' or 'failed'.")
    detail: str | None = Field(default=None, description="Safe, non-sensitive explanation.")


class ReadinessResponse(BaseModel):
    """Readiness payload returned by ``GET /api/v1/ready``.

    Since Phase 3 this includes a database connectivity check and a
    credential-free description of the configured database target.
    """

    status: str = Field(description="'ready' or 'not_ready'.")
    checks: list[ReadinessCheck] = Field(default_factory=list)
    timestamp: datetime = Field(description="Server time in UTC (ISO-8601).")
