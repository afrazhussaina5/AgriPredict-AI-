"""Tests for OTP generation/hashing and access tokens (Phase 4)."""

from datetime import UTC, datetime, timedelta

import jwt
import pytest

from app.core.config import Settings, validate_settings
from app.core.errors import AuthenticationError
from app.core.security import (
    ALGORITHM,
    decode_access_token,
    generate_otp,
    generate_salt,
    hash_otp,
    issue_access_token,
    require_usable_secret,
    verify_otp,
)

SECRET = "a" * 48


def _settings(**overrides) -> Settings:
    base = {"_env_file": None, "ENVIRONMENT": "development", "SECRET_KEY": SECRET}
    base.update(overrides)
    return Settings(**base)  # type: ignore[arg-type]


# ------------------------------------------------------------------ OTP codes


def test_generated_otp_is_numeric_and_correct_length() -> None:
    for _ in range(50):
        code = generate_otp(6)
        assert len(code) == 6
        assert code.isdigit()


def test_generated_otp_length_is_configurable() -> None:
    assert len(generate_otp(4)) == 4
    assert len(generate_otp(8)) == 8


@pytest.mark.parametrize("length", [0, 3, 11, 100])
def test_invalid_otp_length_is_rejected(length: int) -> None:
    with pytest.raises(ValueError):
        generate_otp(length)


def test_generated_otps_are_not_repeating() -> None:
    codes = {generate_otp(6) for _ in range(200)}
    assert len(codes) > 190  # birthday bound; a broken RNG would collapse this


def test_otp_hash_is_deterministic_for_same_inputs() -> None:
    salt = generate_salt()
    assert hash_otp("123456", salt, SECRET) == hash_otp("123456", salt, SECRET)


def test_otp_hash_differs_per_salt() -> None:
    assert hash_otp("123456", "salt-a", SECRET) != hash_otp("123456", "salt-b", SECRET)


def test_otp_hash_never_contains_the_code() -> None:
    digest = hash_otp("123456", generate_salt(), SECRET)
    assert "123456" not in digest
    assert len(digest) == 64


def test_verify_otp_accepts_correct_code() -> None:
    salt = generate_salt()
    digest = hash_otp("654321", salt, SECRET)
    assert verify_otp("654321", salt, SECRET, digest) is True


def test_verify_otp_rejects_wrong_code() -> None:
    salt = generate_salt()
    digest = hash_otp("654321", salt, SECRET)
    assert verify_otp("000000", salt, SECRET, digest) is False


def test_verify_otp_fails_with_a_different_secret() -> None:
    salt = generate_salt()
    digest = hash_otp("654321", salt, SECRET)
    assert verify_otp("654321", salt, "b" * 48, digest) is False


# --------------------------------------------------------------------- tokens


def test_token_round_trip_carries_subject_and_roles() -> None:
    settings = _settings()
    token, expires_at = issue_access_token(
        settings=settings, user_id=42, roles=["farmer", "buyer"]
    )
    claims = decode_access_token(settings=settings, token=token)

    assert claims["sub"] == "42"
    assert claims["roles"] == ["farmer", "buyer"]
    assert claims["typ"] == "access"
    assert expires_at > datetime.now(UTC)


def test_token_expiry_is_short_lived() -> None:
    settings = _settings(ACCESS_TOKEN_TTL_MINUTES=15)
    _, expires_at = issue_access_token(settings=settings, user_id=1, roles=[])
    delta = expires_at - datetime.now(UTC)
    assert timedelta(minutes=14) < delta <= timedelta(minutes=15)


def test_expired_token_is_rejected() -> None:
    settings = _settings()
    token, _ = issue_access_token(
        settings=settings, user_id=1, roles=[], ttl_minutes=-5
    )
    with pytest.raises(AuthenticationError):
        decode_access_token(settings=settings, token=token)


def test_token_signed_with_another_secret_is_rejected() -> None:
    token, _ = issue_access_token(settings=_settings(), user_id=1, roles=[])
    with pytest.raises(AuthenticationError):
        decode_access_token(settings=_settings(SECRET_KEY="z" * 48), token=token)


def test_tampered_token_is_rejected() -> None:
    settings = _settings()
    token, _ = issue_access_token(settings=settings, user_id=1, roles=[])
    header, payload, signature = token.split(".")
    tampered = f"{header}.{payload}x.{signature}"
    with pytest.raises(AuthenticationError):
        decode_access_token(settings=settings, token=tampered)


def test_unsigned_alg_none_token_is_rejected() -> None:
    """The classic JWT bypass: an attacker-supplied 'alg: none' token."""
    settings = _settings()
    far_future = datetime.now(UTC) + timedelta(hours=1)
    forged = jwt.encode(
        {"sub": "1", "typ": "access", "exp": int(far_future.timestamp())},
        key="",
        algorithm="none",
    )
    with pytest.raises(AuthenticationError):
        decode_access_token(settings=settings, token=forged)


def test_token_missing_expiry_is_rejected() -> None:
    settings = _settings()
    pass

    forged = jwt.encode({"sub": "1", "typ": "access"}, require_usable_secret(settings),
                        algorithm=ALGORITHM)
    with pytest.raises(AuthenticationError):
        decode_access_token(settings=settings, token=forged)


def test_wrong_token_type_is_rejected() -> None:
    settings = _settings()
    pass

    forged = jwt.encode(
        {"sub": "1", "typ": "refresh",
         "exp": int((datetime.now(UTC) + timedelta(hours=1)).timestamp())},
        require_usable_secret(settings), algorithm=ALGORITHM,
    )
    with pytest.raises(AuthenticationError):
        decode_access_token(settings=settings, token=forged)


# ------------------------------------------------------------------ secret key


def test_short_secret_is_refused_for_signing() -> None:
    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        require_usable_secret(_settings(SECRET_KEY="short"))


def test_empty_secret_is_refused_for_signing() -> None:
    with pytest.raises(RuntimeError):
        require_usable_secret(_settings(SECRET_KEY=""))


# ------------------------------------------------------- production SMS guard


def test_production_with_mock_sms_fails_closed() -> None:
    settings = Settings(
        _env_file=None,
        ENVIRONMENT="production",
        SECRET_KEY=SECRET,
        POSTGRES_DSN="postgresql+asyncpg://u:p@db.example.supabase.co:5432/postgres",
        SMS_PROVIDER="mock",
    )
    with pytest.raises(RuntimeError, match="mock"):
        validate_settings(settings)


def test_production_with_a_non_mock_provider_name_passes_validation() -> None:
    """Validation only blocks the mock; an unimplemented provider fails later."""
    settings = Settings(
        _env_file=None,
        ENVIRONMENT="production",
        SECRET_KEY=SECRET,
        POSTGRES_DSN="postgresql+asyncpg://u:p@db.example.supabase.co:5432/postgres",
        SMS_PROVIDER="msg91",
    )
    validate_settings(settings)  # must not raise


def test_mock_sms_is_enabled_in_development_and_test_only() -> None:
    assert _settings(ENVIRONMENT="development", SMS_PROVIDER="mock").mock_sms_enabled is True
    assert _settings(ENVIRONMENT="test", SMS_PROVIDER="mock").mock_sms_enabled is True
    assert _settings(ENVIRONMENT="production", SMS_PROVIDER="mock").mock_sms_enabled is False
    assert _settings(ENVIRONMENT="staging", SMS_PROVIDER="mock").mock_sms_enabled is False
    assert _settings(SMS_PROVIDER="msg91").mock_sms_enabled is False