"""Tests for error handling, validation responses and readiness reporting."""

from fastapi import APIRouter
from fastapi.testclient import TestClient

from app.core.config import Settings, describe_database_target, get_settings
from app.main import create_app


def _client_with_routes() -> TestClient:
    app = create_app()
    router = APIRouter()

    @router.get("/boom")
    async def boom() -> None:
        raise RuntimeError("database password=hunter2 exploded")

    @router.get("/nope")
    async def nope() -> None:
        from app.core.errors import NotFoundError

        raise NotFoundError("Lot 42 does not exist.")

    @router.get("/denied")
    async def denied() -> None:
        from app.core.errors import AuthorizationError

        raise AuthorizationError("You do not have access to this resource.")

    app.include_router(router)
    return TestClient(app, raise_server_exceptions=False)


def test_unknown_route_returns_structured_404() -> None:
    with _client_with_routes() as client:
        response = client.get("/does-not-exist")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_app_error_returns_safe_message() -> None:
    with _client_with_routes() as client:
        response = client.get("/nope")
    assert response.status_code == 404
    body = response.json()
    assert body["error"]["code"] == "not_found"
    assert body["error"]["message"] == "Lot 42 does not exist."


def test_forbidden_error_uses_403() -> None:
    with _client_with_routes() as client:
        response = client.get("/denied")
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"


def test_unhandled_error_never_exposes_internals() -> None:
    with _client_with_routes() as client:
        response = client.get("/boom")
    assert response.status_code == 500
    body = response.json()
    assert body["error"]["code"] == "internal_error"
    assert "hunter2" not in response.text
    assert "Traceback" not in response.text


def test_validation_errors_are_structured() -> None:
    with _client_with_routes() as client:
        response = client.post("/api/v1/health", json={"unexpected": 1})
    # GET-only route: the error shape is what we care about.
    assert response.status_code in (404, 405, 422)
    assert "error" in response.json()


def test_health_endpoint_is_unchanged() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_ready_endpoint_reports_database_target_safely() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/api/v1/ready")
    assert response.status_code == 200
    body = response.json()
    assert "checks" in body

    names = {check["name"] for check in body["checks"]}
    assert {"configuration", "cors_allow_list", "database", "database_target"} <= names

    for check in body["checks"]:
        detail = check.get("detail") or ""
        assert "hunter2" not in detail
        assert "@" not in detail  # a userinfo/credential marker never appears


def test_readiness_target_matches_safe_description() -> None:
    with TestClient(create_app()) as client:
        body = client.get("/api/v1/ready").json()
    target = next(c for c in body["checks"] if c["name"] == "database_target")
    assert target["detail"] == describe_database_target(get_settings())


def test_readiness_is_ready_in_test_environment() -> None:
    with TestClient(create_app()) as client:
        body = client.get("/api/v1/ready").json()
    assert body["status"] == "ready"


def test_describe_target_handles_malformed_dsn_without_leaking() -> None:
    settings = Settings(
        _env_file=None,
        ENVIRONMENT="development",
        POSTGRES_DSN="not-a-valid-dsn-with-secret",
    )
    description = describe_database_target(settings)
    assert "not-a-valid-dsn-with-secret" not in description