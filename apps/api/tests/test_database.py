"""Tests for database configuration safety and readiness reporting."""

import pytest

from app.core.config import Settings, describe_database_target
from app.core.database import check_connection, resolve_engine_url
from app.models import User


def test_development_without_dsn_returns_no_url() -> None:
    settings = Settings(_env_file=None, ENVIRONMENT="development", POSTGRES_DSN="")
    assert resolve_engine_url(settings) is None


def test_production_requires_a_dsn() -> None:
    from app.core.config import validate_settings

    settings = Settings(
        _env_file=None, ENVIRONMENT="production", POSTGRES_DSN="", SECRET_KEY="x" * 32
    )
    with pytest.raises(RuntimeError, match="POSTGRES_DSN"):
        validate_settings(settings)


def test_staging_requires_a_dsn() -> None:
    from app.core.config import validate_settings

    settings = Settings(_env_file=None, ENVIRONMENT="staging", POSTGRES_DSN="")
    with pytest.raises(RuntimeError, match="POSTGRES_DSN"):
        validate_settings(settings)


def test_test_environment_never_uses_the_supabase_dsn() -> None:
    """A leftover production DSN must not be picked up by the test suite."""
    settings = Settings(
        _env_file=None,
        ENVIRONMENT="test",
        POSTGRES_DSN="postgresql+asyncpg://user:secret@db.supabase.co:5432/postgres",
    )
    url = resolve_engine_url(settings)
    assert url is not None
    assert "supabase" not in url
    assert url.startswith("sqlite")


def test_a_misconfigured_test_url_cannot_escape_to_a_real_database() -> None:
    """Even TEST_DATABASE_URL pointing at PostgreSQL is ignored in test mode."""
    settings = Settings(
        _env_file=None,
        ENVIRONMENT="test",
        POSTGRES_DSN="",
        TEST_DATABASE_URL="postgresql+asyncpg://u:p@db.supabase.co:5432/postgres",
    )
    url = resolve_engine_url(settings)
    assert url == "sqlite+aiosqlite:///:memory:"


def test_target_description_never_contains_credentials() -> None:
    secret = "hunter2-password"
    settings = Settings(
        _env_file=None,
        ENVIRONMENT="development",
        POSTGRES_DSN=f"postgresql+asyncpg://postgres:{secret}@db.abc.supabase.co:5432/postgres",
    )
    description = describe_database_target(settings)
    assert secret not in description
    assert "postgres:postgres" not in description
    assert "supabase.co" in description
    assert description.endswith("/postgres")


def test_target_description_for_unconfigured_database() -> None:
    settings = Settings(_env_file=None, ENVIRONMENT="development", POSTGRES_DSN="")
    assert describe_database_target(settings) == "not configured"


def test_dsn_is_excluded_from_repr() -> None:
    dsn = "postgresql+asyncpg://u:secretpass@host:5432/db"
    settings = Settings(_env_file=None, ENVIRONMENT="development", POSTGRES_DSN=dsn)
    assert "secretpass" not in repr(settings)


async def test_check_connection_succeeds_against_test_database(engine) -> None:
    """The probe must succeed once the test engine exists."""
    ok, detail = await check_connection()
    assert ok is True
    assert detail is None


async def test_check_connection_fails_when_not_configured(monkeypatch) -> None:
    import app.core.database as database

    monkeypatch.setattr(database, "_engine", None)
    ok, detail = await check_connection()
    assert ok is False
    assert detail == "Database is not configured."


def test_all_expected_tables_are_registered() -> None:
    from app.core.database import Base
    import app.models  # noqa: F401 - registers tables

    expected = {
        "users",
        "user_roles",
        "farmer_profiles",
        "buyer_profiles",
        "otp_verifications",
        "audit_logs",
    }
    assert expected <= set(Base.metadata.tables)


def test_user_model_has_unique_phone_index() -> None:
    table = User.__table__
    assert any(
        constraint.name == "uq_users_phone_e164"
        for constraint in table.constraints
        if constraint.__class__.__name__ == "UniqueConstraint"
    )