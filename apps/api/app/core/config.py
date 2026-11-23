"""Application settings for the AgriPredict AI API.

Configuration comes from environment variables and an optional local ``.env``
file. Secrets are never printed, never included in ``repr()``, and production
fails closed when a signing secret is missing.
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

EnvironmentName = Literal["development", "staging", "production", "test"]


class Settings(BaseSettings):
    """Typed application settings with secure defaults."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    APP_NAME: str = "AgriPredict AI API"
    APP_VERSION: str = "1.0.0"
    ENVIRONMENT: EnvironmentName = "development"
    DEBUG: bool = True
    LOG_LEVEL: str = "INFO"

    # Signing secret for tokens (Phase 4+). repr=False keeps it out of logs.
    SECRET_KEY: str = Field(default="", repr=False)

    # Comma separated browser origins allowed to call the API.
    CORS_ORIGINS_STR: str = "http://localhost:5173,http://127.0.0.1:5173"

    # --- Phase 3: database ---
    # POSTGRES_DSN is a single secret-bearing variable (postgresql+asyncpg://).
    # repr=False keeps it out of logs, traces and error messages.
    POSTGRES_DSN: str = Field(default="", repr=False)
    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 5
    DB_POOL_TIMEOUT_SECONDS: int = 10
    DB_ECHO: bool = False
    # "test" forces an isolated in-memory SQLite database and blocks any
    # external connection. See app.core.database.resolve_engine_url.
    TEST_DATABASE_URL: str = Field(default="sqlite+aiosqlite:///:memory:", repr=False)

    # --- Phase 4: authentication ---
    # Access token lifetime. Deliberately short; a fresh token is issued after
    # each successful OTP verification rather than using long-lived sessions.
    ACCESS_TOKEN_TTL_MINUTES: int = 60
    # OTP shape. A 6-digit code is the Indian-market norm.
    OTP_LENGTH: int = 6
    OTP_TTL_MINUTES: int = 5
    # Minimum seconds between two OTP requests for the same phone number.
    OTP_RESEND_COOLDOWN_SECONDS: int = 30
    # Failed verification attempts allowed before the challenge is burned.
    OTP_MAX_ATTEMPTS: int = 5
    # Hard cap on OTP requests per phone number per rolling hour.
    OTP_MAX_REQUESTS_PER_HOUR: int = 5

    # --- Phase 4: SMS provider ---
    # "mock" is a DEVELOPMENT-ONLY adapter that returns the code in the API
    # response instead of sending an SMS. Production refuses to start with it;
    # see validate_settings() and app/services/sms/.
    SMS_PROVIDER: str = "mock"
    SMS_SENDER_ID: str = "AGRIPD"

    @field_validator("ENVIRONMENT", mode="before")
    @classmethod
    def normalize_environment(cls, value: object) -> object:
        """Accept mixed case values from the environment."""
        if isinstance(value, str):
            return value.strip().lower()
        return value

    @property
    def cors_origins(self) -> list[str]:
        """Parsed CORS allow-list (never a wildcard by default)."""
        return [origin.strip() for origin in self.CORS_ORIGINS_STR.split(",") if origin.strip()]

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"

    @property
    def is_test(self) -> bool:
        return self.ENVIRONMENT == "test"

    @property
    def mock_sms_enabled(self) -> bool:
        """True only when the development mock SMS adapter may be used."""
        return self.SMS_PROVIDER == "mock" and self.ENVIRONMENT in {"development", "test"}

    @property
    def requires_real_sms(self) -> bool:
        """Production must have a real provider; the mock is never acceptable."""
        return self.ENVIRONMENT in {"production", "staging"}

    @property
    def database_required(self) -> bool:
        """Production must have a database; dev/test may run without one."""
        return self.ENVIRONMENT in {"production", "staging"}


def describe_database_target(settings: Settings) -> str:
    """Return a SAFE description of the configured database.

    Used by the verification command and the readiness probe. It deliberately
    exposes only host, port and database name - never the user, password,
    query parameters or the full connection string.
    """
    dsn = settings.TEST_DATABASE_URL if settings.is_test else settings.POSTGRES_DSN
    if not dsn.strip():
        return "not configured"
    try:
        from sqlalchemy.engine import make_url

        url = make_url(dsn)
    except Exception:
        # A malformed DSN must not leak its contents through an error page.
        return "configured (unparsable)"
    return (
        f"{url.get_backend_name()}://{url.host or 'localhost'}"
        f":{url.port or 0}/{url.database or '?'}"
    )


def validate_settings(settings: Settings) -> None:
    """Fail closed on unsafe configuration.

    Raises:
        RuntimeError: when production is selected without a signing secret.
    """
    if settings.is_production and not settings.SECRET_KEY.strip():
        raise RuntimeError(
            "Unsafe configuration: SECRET_KEY must be set when ENVIRONMENT=production."
        )
    if settings.database_required and not settings.POSTGRES_DSN.strip():
        raise RuntimeError(
            "Unsafe configuration: POSTGRES_DSN must be set when "
            f"ENVIRONMENT={settings.ENVIRONMENT}."
        )
    if settings.is_production and settings.SMS_PROVIDER == "mock":
        # Fail closed: never run production with an adapter that returns OTPs
        # in the HTTP response instead of sending an SMS.
        raise RuntimeError(
            "Unsafe configuration: SMS_PROVIDER='mock' is not allowed when "
            "ENVIRONMENT=production. Configure a real SMS provider."
        )


@lru_cache
def get_settings() -> Settings:
    """Return cached settings. Call ``clear_settings_cache()`` in tests."""
    return Settings()


def clear_settings_cache() -> None:
    """Reset the settings cache (used by tests that change the environment)."""
    get_settings.cache_clear()
