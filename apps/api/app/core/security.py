"""Cryptographic helpers for authentication (Phase 4).

Everything here is deliberately small and dependency-light:

* :func:`generate_otp` uses ``secrets`` (a CSPRNG), never ``random``.
* :func:`hash_otp` derives an HMAC-SHA256 digest keyed with ``SECRET_KEY``.
  The OTP itself is never stored, logged or returned by a production endpoint.
* :func:`issue_access_token` / :func:`decode_access_token` use PyJWT with
  HS256. The payload carries the user id, the roles and an expiry - nothing
  sensitive.
"""

import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt

from .config import Settings
from .errors import AuthenticationError

ALGORITHM = "HS256"
TOKEN_TYPE = "access"
MINIMUM_SECRET_LENGTH = 32


def generate_otp(length: int = 6) -> str:
    """Return a cryptographically random numeric OTP of the requested length."""
    if not 4 <= length <= 10:
        raise ValueError("OTP length must be between 4 and 10 digits.")
    # secrets.randbelow avoids modulo bias for non-power-of-two ranges, which
    # matters because we build a random integer and convert it to fixed digits.
    upper_bound = 10**length
    return f"{secrets.randbelow(upper_bound):0{length}d}"


def generate_salt() -> str:
    """Return a random salt for OTP hashing."""
    return secrets.token_hex(16)


def hash_otp(code: str, salt: str, secret_key: str) -> str:
    """Return a keyed digest of ``code``.

    HMAC (not a bare hash) means that even if the database leaks, an attacker
    cannot brute-force the 6-digit space without also knowing SECRET_KEY.
    """
    message = f"{salt}:{code}".encode()
    return hmac.new(secret_key.encode(), message, hashlib.sha256).hexdigest()


def verify_otp(code: str, salt: str, secret_key: str, expected_hash: str) -> bool:
    """Constant-time comparison of a candidate OTP against a stored digest."""
    candidate = hash_otp(code, salt, secret_key)
    return hmac.compare_digest(candidate, expected_hash)


def require_usable_secret(settings: Settings) -> str:
    """Return SECRET_KEY, refusing to sign anything with a weak secret."""
    secret = settings.SECRET_KEY.strip()
    if len(secret) < MINIMUM_SECRET_LENGTH:
        raise RuntimeError(
            f"SECRET_KEY must be at least {MINIMUM_SECRET_LENGTH} characters to sign "
            "tokens securely. Generate one with: "
            'python -c "import secrets; print(secrets.token_hex(32))"'
        )
    return secret


def issue_access_token(
    *,
    settings: Settings,
    user_id: int,
    roles: list[str],
    token_version: int = 1,
    ttl_minutes: int | None = None,
) -> tuple[str, datetime]:
    """Sign an access token. Returns ``(token, expires_at)``."""
    secret = require_usable_secret(settings)
    minutes = ttl_minutes if ttl_minutes is not None else settings.ACCESS_TOKEN_TTL_MINUTES
    now = datetime.now(UTC)
    expires_at = now + timedelta(minutes=minutes)

    payload: dict[str, Any] = {
        "sub": str(user_id),
        "roles": roles,
        "typ": TOKEN_TYPE,
        "ver": token_version,
        "iat": int(now.timestamp()),
        "exp": int(expires_at.timestamp()),
    }
    token = jwt.encode(payload, secret, algorithm=ALGORITHM)
    return token, expires_at


def decode_access_token(*, settings: Settings, token: str) -> dict[str, Any]:
    """Verify a token and return its claims.

    Raises:
        AuthenticationError: for any invalid, expired or malformed token. The
            message never reveals which check failed.
    """
    secret = require_usable_secret(settings)
    try:
        claims = jwt.decode(
            token,
            secret,
            algorithms=[ALGORITHM],
            options={"require": ["exp", "sub", "typ"]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise AuthenticationError("Your session has expired. Please sign in again.") from exc
    except jwt.InvalidTokenError as exc:
        raise AuthenticationError("Invalid authentication token.") from exc

    if claims.get("typ") != TOKEN_TYPE:
        raise AuthenticationError("Invalid authentication token.")
    return claims