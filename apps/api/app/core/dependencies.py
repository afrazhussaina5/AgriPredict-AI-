"""FastAPI dependencies for authentication and role-based access control.

Security properties:

* A missing, malformed or expired token yields 401 with no detail about why.
* A valid token for the wrong role yields 403 - never 404, never a hint that
  the resource exists.
* Roles come from the signed token AND are re-checked against the database, so
  a revoked role takes effect immediately instead of at token expiry.
"""

from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import User, UserRole, UserStatus
from ..repositories import AuditRepository, UserRepository
from .config import Settings, get_settings
from .database import get_db
from .errors import AuthenticationError, AuthorizationError
from .security import decode_access_token

# auto_error=False so a missing header produces our own consistent error shape.
bearer_scheme = HTTPBearer(auto_error=False, description="JWT access token")

DbSession = Annotated[AsyncSession, Depends(get_db)]
AppSettings = Annotated[Settings, Depends(get_settings)]


async def get_current_user(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    session: DbSession,
    settings: AppSettings,
) -> User:
    """Resolve the authenticated user, or raise 401."""
    if credentials is None or not credentials.credentials:
        raise AuthenticationError("Authentication required.")

    claims = decode_access_token(settings=settings, token=credentials.credentials)
    try:
        user_id = int(claims.get("sub", ""))
    except (TypeError, ValueError) as exc:
        raise AuthenticationError("Invalid authentication token.") from exc

    user = await UserRepository(session).get_by_id(user_id)
    if user is None:
        raise AuthenticationError("Invalid authentication token.")

    if user.status is not UserStatus.ACTIVE:
        raise AuthorizationError(
            "This account is not active. Please contact support."
        )

    request.state.user = user
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_roles(*allowed: UserRole):
    """Build a dependency that admits only the listed roles.

    Roles are read from the database rather than from the token claims, so
    revoking a role takes effect immediately instead of at token expiry.
    """

    async def _dependency(user: CurrentUser, session: DbSession) -> User:
        roles = await UserRepository(session).list_roles(user.id)
        if not roles.intersection(allowed):
            raise AuthorizationError("You do not have access to this resource.")
        return user

    return _dependency


# Convenience aliases for the most common guards.
require_farmer = require_roles(UserRole.FARMER)
require_buyer = require_roles(UserRole.BUYER)
require_admin = require_roles(UserRole.ADMIN)
require_provider = require_roles(UserRole.TRANSPORT_PROVIDER, UserRole.STORAGE_PROVIDER)


__all__ = [
    "AppSettings",
    "AuditRepository",
    "CurrentUser",
    "DbSession",
    "UserRepository",
    "get_current_user",
    "require_admin",
    "require_buyer",
    "require_farmer",
    "require_provider",
    "require_roles",
]