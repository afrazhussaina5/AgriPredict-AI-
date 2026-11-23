"""Tests for the OTP service lifecycle rules (Phase 4)."""

from datetime import timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.errors import AuthenticationError, RateLimitError
from app.models import OtpPurpose, OtpStatus, utcnow
from app.services.otp_service import OtpService
from app.services.sms import MockSmsProvider, build_sms_provider

SECRET = "b" * 48


def _settings(**overrides) -> Settings:
    base = {
        "_env_file": None,
        "ENVIRONMENT": "development",
        "SECRET_KEY": SECRET,
        "OTP_RESEND_COOLDOWN_SECONDS": 30,
        "OTP_TTL_MINUTES": 5,
        "OTP_MAX_ATTEMPTS": 3,
        "OTP_MAX_REQUESTS_PER_HOUR": 3,
    }
    base.update(overrides)
    return Settings(**base)  # type: ignore[arg-type]


@pytest.fixture()
def provider() -> MockSmsProvider:
    return MockSmsProvider()


def _service(session, settings, provider) -> OtpService:
    return OtpService(session, settings, provider)


async def _request(service, user, phone="+919000000011"):
    return await service.request_otp(phone, purpose=OtpPurpose.LOGIN, user=user)


# ------------------------------------------------------------------- happy path


async def test_request_then_verify_succeeds(session: AsyncSession, make_user, provider) -> None:
    settings = _settings()
    user = await make_user("9000000011")
    service = _service(session, settings, provider)

    record, result, code = await _request(service, user)
    await session.commit()

    assert record.status is OtpStatus.PENDING
    assert result.delivered is True
    assert provider.last_code_for(user.phone_e164) == code

    verified = await service.verify_otp(user.id, code)
    assert verified.status is OtpStatus.VERIFIED
    assert verified.consumed_at is not None


async def test_plaintext_code_is_never_stored(session: AsyncSession, make_user, provider) -> None:
    settings = _settings()
    user = await make_user("9000000012")
    service = _service(session, settings, provider)

    record, _result, code = await _request(service, user)
    await session.commit()

    assert record.code_hash != code
    assert code not in record.code_hash
    assert code not in record.salt


# -------------------------------------------------------------------- failures


async def test_wrong_code_is_rejected(session: AsyncSession, make_user, provider) -> None:
    settings = _settings()
    user = await make_user("9000000013")
    service = _service(session, settings, provider)
    await _request(service, user)
    await session.commit()

    with pytest.raises(AuthenticationError):
        await service.verify_otp(user.id, "000000")


async def test_failed_attempts_are_counted(session: AsyncSession, make_user, provider) -> None:
    settings = _settings()
    user = await make_user("9000000014")
    service = _service(session, settings, provider)
    record, _result, code = await _request(service, user)
    await session.commit()

    for _ in range(2):
        with pytest.raises(AuthenticationError):
            await service.verify_otp(user.id, "000000")

    assert record.attempt_count == 2
    assert record.status is OtpStatus.PENDING

    # The correct code still works while attempts remain.
    await service.verify_otp(user.id, code)
    assert record.status is OtpStatus.VERIFIED


async def test_challenge_is_burned_after_max_attempts(session: AsyncSession, make_user,
                                                       provider) -> None:
    settings = _settings(OTP_MAX_ATTEMPTS=2)
    user = await make_user("9000000015")
    service = _service(session, settings, provider)
    record, _result, code = await _request(service, user)
    await session.commit()

    for _ in range(2):
        with pytest.raises(AuthenticationError):
            await service.verify_otp(user.id, "000000")

    assert record.status is OtpStatus.FAILED
    # Even the correct code no longer works.
    with pytest.raises(AuthenticationError):
        await service.verify_otp(user.id, code)


async def test_expired_code_is_rejected(session: AsyncSession, make_user, provider) -> None:
    settings = _settings(OTP_TTL_MINUTES=5)
    user = await make_user("9000000016")
    service = _service(session, settings, provider)
    record, _result, code = await _request(service, user)
    await session.commit()

    record.expires_at = utcnow() - timedelta(minutes=1)
    await session.commit()

    with pytest.raises(AuthenticationError, match="expired"):
        await service.verify_otp(user.id, code)
    assert record.status is OtpStatus.EXPIRED


async def test_code_is_single_use(session: AsyncSession, make_user, provider) -> None:
    settings = _settings()
    user = await make_user("9000000017")
    service = _service(session, settings, provider)
    _record, _result, code = await _request(service, user)
    await session.commit()

    await service.verify_otp(user.id, code)
    with pytest.raises(AuthenticationError):
        await service.verify_otp(user.id, code)  # replay


async def test_verify_without_a_challenge_is_rejected(session: AsyncSession, make_user,
                                                      provider) -> None:
    settings = _settings()
    user = await make_user("9000000018")
    service = _service(session, settings, provider)
    with pytest.raises(AuthenticationError):
        await service.verify_otp(user.id, "123456")


# ---------------------------------------------------------------- rate limits


async def test_resend_cooldown_blocks_immediate_second_request(
    session: AsyncSession, make_user, provider
) -> None:
    settings = _settings()
    user = await make_user("9000000019")
    service = _service(session, settings, provider)
    await _request(service, user)
    await session.commit()

    with pytest.raises(RateLimitError, match="wait"):
        await _request(service, user)


async def test_cooldown_expires_then_a_new_code_is_sent(session: AsyncSession, make_user,
                                                         provider) -> None:
    settings = _settings()
    user = await make_user("9000000020")
    service = _service(session, settings, provider)
    record, _result, first_code = await _request(service, user)
    await session.commit()

    record.cooldown_until = utcnow() - timedelta(seconds=1)
    await session.commit()

    _record2, _result2, second_code = await _request(service, user)
    await session.commit()

    assert second_code != first_code
    # The old code must no longer work.
    with pytest.raises(AuthenticationError):
        await service.verify_otp(user.id, first_code)
    await service.verify_otp(user.id, second_code)


async def test_hourly_request_cap_is_enforced(session: AsyncSession, make_user,
                                              provider) -> None:
    settings = _settings(OTP_MAX_REQUESTS_PER_HOUR=2)
    user = await make_user("9000000021")
    service = _service(session, settings, provider)

    for _ in range(2):
        record, _r, _c = await _request(service, user)
        await session.commit()
        # Move past the cooldown so the next request is not blocked by it.
        record.cooldown_until = utcnow() - timedelta(seconds=1)
        await session.commit()

    with pytest.raises(RateLimitError, match="Too many"):
        await _request(service, user)


async def test_hourly_cap_ignores_old_requests(session: AsyncSession, make_user,
                                               provider) -> None:
    settings = _settings(OTP_MAX_REQUESTS_PER_HOUR=2)
    user = await make_user("9000000022")
    service = _service(session, settings, provider)

    for _ in range(2):
        record, _r, _c = await _request(service, user)
        await session.commit()
        record.cooldown_until = utcnow() - timedelta(seconds=1)
        # Age the whole request window past one hour.
        record.window_started_at = utcnow() - timedelta(hours=2)
        await session.commit()

    # The previous window has expired, so a new one starts and is allowed.
    record3, _r3, _c3 = await _request(service, user)
    await session.commit()
    assert record3.status is OtpStatus.PENDING
    assert record3.window_request_count == 1


async def test_request_count_increases_within_one_window(session: AsyncSession, make_user,
                                                        provider) -> None:
    """The window counter must actually accumulate, not stay at 1."""
    settings = _settings(OTP_MAX_REQUESTS_PER_HOUR=10)
    user = await make_user("9000000023")
    service = _service(session, settings, provider)

    for expected in (1, 2, 3):
        record, _r, _c = await _request(service, user)
        await session.commit()
        record.cooldown_until = utcnow() - timedelta(seconds=1)
        await session.commit()
        assert record.window_request_count == expected


# ------------------------------------------------------------------ provider


def test_mock_provider_factory_is_allowed_in_development() -> None:
    provider = build_sms_provider(_settings())
    assert isinstance(provider, MockSmsProvider)


def test_mock_provider_factory_is_refused_for_production() -> None:
    settings = _settings(ENVIRONMENT="production", SMS_PROVIDER="mock")
    with pytest.raises(RuntimeError, match="development-only"):
        build_sms_provider(settings)


def test_unimplemented_provider_is_refused() -> None:
    with pytest.raises(RuntimeError, match="not implemented"):
        build_sms_provider(_settings(SMS_PROVIDER="msg91"))


async def test_mock_provider_history_is_bounded(provider: MockSmsProvider) -> None:
    small = MockSmsProvider(history_limit=3)
    for index in range(10):
        await small.send_otp("+919000000099", f"00000{index}")
    assert len(small._history) == 3
    assert small.last_code_for("+919000000099") == "000009"


async def test_mock_provider_has_no_code_for_unknown_number(provider: MockSmsProvider) -> None:
    assert provider.last_code_for("+919888888888") is None