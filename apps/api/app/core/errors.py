"""Application error types and consistent JSON error responses.

Rules:
- Clients never receive stack traces, SQL, DSNs or internal exception text.
- Unexpected exceptions are logged (redacted) and reported as a generic 500.
"""

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from .config import Settings, get_settings
from .logging import get_logger

logger = get_logger(__name__)


class AppError(Exception):
    """Base class for expected, safe-to-report application errors."""

    status_code: int = status.HTTP_400_BAD_REQUEST
    code: str = "bad_request"

    def __init__(self, message: str, *, details: dict | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class NotFoundError(AppError):
    status_code = status.HTTP_404_NOT_FOUND
    code = "not_found"


class ConflictError(AppError):
    status_code = status.HTTP_409_CONFLICT
    code = "conflict"


class AuthenticationError(AppError):
    status_code = status.HTTP_401_UNAUTHORIZED
    code = "unauthorized"


class AuthorizationError(AppError):
    status_code = status.HTTP_403_FORBIDDEN
    code = "forbidden"


class RateLimitError(AppError):
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    code = "rate_limited"


class ValidationError(AppError):
    """Business-rule validation failure (distinct from request parsing)."""

    status_code = status.HTTP_400_BAD_REQUEST
    code = "invalid_request"


def _payload(code: str, message: str, details: dict | None = None) -> dict:
    body: dict = {"error": {"code": code, "message": message}}
    if details:
        body["error"]["details"] = details
    return body


def register_exception_handlers(app: FastAPI) -> None:
    """Install uniform error handling on the application."""

    @app.exception_handler(AppError)
    async def _app_error(_request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code, content=_payload(exc.code, exc.message, exc.details)
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_error(
        _request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        # Field-level messages only; no input echo beyond the field path.
        fields = [
            {
                "field": ".".join(str(part) for part in error.get("loc", [])[1:]) or "body",
                "message": error.get("msg", "invalid value"),
                "type": error.get("type", "value_error"),
            }
            for error in exc.errors()
        ]
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=_payload("validation_error", "Request validation failed.", {"fields": fields}),
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(_request: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = "not_found" if exc.status_code == 404 else "http_error"
        return JSONResponse(
            status_code=exc.status_code, content=_payload(code, str(exc.detail))
        )

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
        settings: Settings = get_settings()
        logger.exception("Unhandled error on %s %s: %s", request.method, request.url.path,
                         type(exc).__name__)
        message = (
            "An internal error occurred. The incident was logged."
            if not settings.DEBUG
            else f"Internal error ({type(exc).__name__}). No details are exposed in production."
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=_payload("internal_error", message),
        )