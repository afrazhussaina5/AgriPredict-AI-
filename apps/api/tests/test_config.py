"""Tests for configuration loading, validation, and secret handling."""

import pytest
from pydantic import ValidationError

from app.core.config import Settings, clear_settings_cache, get_settings, validate_settings


def test_default_settings_load() -> None:
    # ENVIRONMENT is passed explicitly: the test suite sets ENVIRONMENT=test in
    # the process environment (see conftest.py), and init kwargs win over it.
    settings = Settings(_env_file=None, ENVIRONMENT="development")
    assert settings.ENVIRONMENT == "development"
    assert settings.APP_NAME == "AgriPredict AI API"
    assert settings.cors_origins, "CORS allow-list must not be empty by default"
    assert "http://localhost:5173" in settings.cors_origins


def test_environment_value_is_normalized() -> None:
    settings = Settings(_env_file=None, ENVIRONMENT="  PRODUCTION ")
    assert settings.ENVIRONMENT == "production"
    assert settings.is_production is True


def test_invalid_environment_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, ENVIRONMENT="banana")


def test_cors_allow_list_is_parsed_and_trimmed() -> None:
    settings = Settings(
        _env_file=None,
        CORS_ORIGINS_STR="https://a.example , https://b.example,",
    )
    assert settings.cors_origins == ["https://a.example", "https://b.example"]


def test_wildcard_cors_is_not_the_default() -> None:
    settings = Settings(_env_file=None)
    assert "*" not in settings.cors_origins


def test_secret_is_excluded_from_repr_and_str() -> None:
    secret = "super-secret-value-do-not-log"
    settings = Settings(_env_file=None, SECRET_KEY=secret)
    assert secret not in repr(settings)
    assert secret not in str(settings)


def test_production_without_secret_fails_closed() -> None:
    settings = Settings(_env_file=None, ENVIRONMENT="production", SECRET_KEY="")
    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        validate_settings(settings)


def test_production_with_secret_and_database_is_accepted() -> None:
    settings = Settings(
        _env_file=None,
        ENVIRONMENT="production",
        SECRET_KEY="x" * 32,
        POSTGRES_DSN="postgresql+asyncpg://u:p@db.example.supabase.co:5432/postgres",
        SMS_PROVIDER="msg91",
    )
    validate_settings(settings)  # must not raise


def test_production_with_secret_but_no_database_is_rejected() -> None:
    """Phase 3 added this requirement on top of the secret requirement."""
    settings = Settings(_env_file=None, ENVIRONMENT="production", SECRET_KEY="x" * 32)
    with pytest.raises(RuntimeError, match="POSTGRES_DSN"):
        validate_settings(settings)


def test_development_without_secret_is_accepted() -> None:
    settings = Settings(
        _env_file=None, ENVIRONMENT="development", SECRET_KEY="", POSTGRES_DSN=""
    )
    validate_settings(settings)  # must not raise


def test_settings_are_cached_until_cleared() -> None:
    assert get_settings() is get_settings()
    clear_settings_cache()
    assert get_settings() is not None
