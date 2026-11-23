"""Tests for the health/readiness endpoints and the application shell."""

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings, get_settings

ALLOWED_ENVIRONMENTS = {"development", "staging", "production", "test"}


def test_root_index_returns_service_info(client: TestClient) -> None:
    response = client.get("/")
    assert response.status_code == 200
    payload = response.json()
    assert payload["service"] == "AgriPredict AI API"
    assert payload["health"] == "/api/v1/health"
    assert payload["environment"] in ALLOWED_ENVIRONMENTS
    assert "SECRET_KEY" not in payload


def test_health_endpoint_reports_ok(client: TestClient) -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["service"]
    assert payload["version"]
    assert payload["environment"] in ALLOWED_ENVIRONMENTS
    assert payload["timestamp"]


def test_health_response_never_contains_the_secret(client: TestClient) -> None:
    settings = get_settings()
    if not settings.SECRET_KEY:
        return  # nothing to leak in a default development setup
    assert settings.SECRET_KEY not in client.get("/api/v1/health").text
    assert settings.SECRET_KEY not in client.get("/api/v1/ready").text


def test_ready_endpoint_reports_checks(client: TestClient) -> None:
    response = client.get("/api/v1/ready")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ready"
    names = {check["name"] for check in payload["checks"]}
    assert {"configuration", "cors_allow_list"} <= names
    assert all(check["status"] == "ok" for check in payload["checks"])


def test_unknown_v1_route_returns_404(client: TestClient) -> None:
    assert client.get("/api/v1/does-not-exist").status_code == 404


def test_app_refuses_unsafe_production_config(monkeypatch: pytest.MonkeyPatch) -> None:
    """Production without a signing secret must fail closed at startup."""
    from app.main import create_app as build_app

    unsafe = Settings(_env_file=None, ENVIRONMENT="production", SECRET_KEY="")
    monkeypatch.setattr("app.main.get_settings", lambda: unsafe)
    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        build_app()

    # A properly configured production settings object is accepted.
    safe = Settings(
        _env_file=None,
        ENVIRONMENT="production",
        SECRET_KEY="x" * 32,
        POSTGRES_DSN="postgresql+asyncpg://u:p@db.example.supabase.co:5432/postgres",
        SMS_PROVIDER="msg91",
    )
    monkeypatch.setattr("app.main.get_settings", lambda: safe)
    assert build_app() is not None


def test_production_without_database_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    """Phase 3: staging/production must not start without a database."""
    from app.main import create_app as build_app

    unsafe = Settings(
        _env_file=None, ENVIRONMENT="production", SECRET_KEY="x" * 32, POSTGRES_DSN=""
    )
    monkeypatch.setattr("app.main.get_settings", lambda: unsafe)
    with pytest.raises(RuntimeError, match="POSTGRES_DSN"):
        build_app()
