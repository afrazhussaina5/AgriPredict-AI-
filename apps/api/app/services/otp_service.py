"""OTP request and verification (Phase 4).

Abuse controls enforced here, all backed by the database so they survive a
restart and work across multiple workers:

* resend cooldown per phone number,
* hard hourly request cap per phone number,
* maximum failed verification attempts per challenge,
* single use (a verified challenge is consumed and can never be replayed),
* expiry.

The plaintext OTP exists only in memory for the duration of
:meth:`request_otp`. It is hashed before the transaction commits and is never
logged or returned in production.
"""

from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import Settings
from ..core.errors import AuthenticationError, RateLimitError
from ..core.security import (
    generate_otp,
    generate_salt,
    hash_otp,
    require_usable_secret,
    verify_otp,
)
from ..models import OtpPurpose, OtpStatus, OtpVerification, User, utcnow
from ..schemas.user import normalize_phone_e164
from .sms import SmsProvider, SmsResult

ONE_HOUR = timedelta(hours=1)


class OtpService:
    def __init__(
        self,
        session: AsyncSession,
        settings: Settings,
        provider: SmsProvider,
    ) -> None:
        self.session = session
        self.settings = settings
        self.provider = provider

    # ------------------------------------------------------------------ query

    async def _find_active(
        self, user_id: int, purpose: OtpPurpose
    ) -> OtpVerification | None:
        result = await self.session.execute(
            select(OtpVerification).where(
                OtpVerification.user_id == user_id,
                OtpVerification.purpose == purpose,
            )
        )
        return result.scalar_one_or_none()

    async def _requests_in_last_hour(
        self, record: OtpVerification | None, now: datetime
    ) -> int:
        """Requests issued in the current one-hour window.

        Counted from the per-record sliding window rather than by counting rows,
        because a resend updates the same row instead of inserting a new one.
        """
        if record is None:
            return 0
        started = record.window_started_at
        if started.tzinfo is None:
            started = started.replace(tzinfo=UTC)
        if now - started >= ONE_HOUR:
            return 0  # the previous window has expired
        return record.window_request_count

    # ---------------------------------------------------------------- request

    async def request_otp(
        self,
        phone_e164: str,
        *,
        purpose: OtpPurpose = OtpPurpose.LOGIN,
        user: User | None = None,
    ) -> tuple[OtpVerification, SmsResult, str]:
        """Create or refresh a challenge and send the code.

        Returns the stored record, the provider result and the plaintext code.
        The caller must NOT return the plaintext code to the client unless the
        mock development adapter is enabled.

        Raises:
            RateLimitError: when the cooldown or the hourly cap is exceeded.
        """
        now = utcnow()

        existing = None
        if user is not None:
            existing = await self._find_active(user.id, purpose)
        else:
            result = await self.session.execute(
                select(OtpVerification)
                .where(
                    OtpVerification.phone_e164 == phone_e164,
                    OtpVerification.purpose == purpose,
                )
                .order_by(OtpVerification.id.desc())
                .limit(1)
            )
            existing = result.scalar_one_or_none()

        # Rate limit is checked BEFORE the cooldown so a determined caller who
        # waits out each cooldown still stops at the hourly cap.
        if await self._requests_in_last_hour(existing, now) >= (
            self.settings.OTP_MAX_REQUESTS_PER_HOUR
        ):
            raise RateLimitError(
                "Too many verification codes requested. Please try again later."
            )

        if existing is not None:
            cooldown_until = existing.cooldown_until
            if cooldown_until.tzinfo is None:
                cooldown_until = cooldown_until.replace(tzinfo=UTC)
            remaining = int((cooldown_until - now).total_seconds())
            if remaining > 0:
                raise RateLimitError(
                    f"Please wait {remaining} seconds before requesting another code."
                )

        code = generate_otp(self.settings.OTP_LENGTH)
        salt = generate_salt()
        secret = require_usable_secret(self.settings)

        if existing is not None:
            existing.code_hash = hash_otp(code, salt, secret)
            existing.salt = salt
            existing.status = OtpStatus.PENDING
            existing.expires_at = now + timedelta(minutes=self.settings.OTP_TTL_MINUTES)
            existing.cooldown_until = now + timedelta(
                seconds=self.settings.OTP_RESEND_COOLDOWN_SECONDS
            )
            existing.attempt_count = 0
            existing.consumed_at = None
            record = existing
            started = existing.window_started_at
            if started.tzinfo is None:
                started = started.replace(tzinfo=UTC)
            if now - started >= ONE_HOUR:
                existing.window_started_at = now
                existing.window_request_count = 1
            else:
                existing.window_request_count += 1
        else:
            record = OtpVerification(
                phone_e164=phone_e164,
                purpose=purpose,
                code_hash=hash_otp(code, salt, secret),
                salt=salt,
                status=OtpStatus.PENDING,
                expires_at=now + timedelta(minutes=self.settings.OTP_TTL_MINUTES),
                cooldown_until=now + timedelta(
                    seconds=self.settings.OTP_RESEND_COOLDOWN_SECONDS
                ),
                attempt_count=0,
                max_attempts=self.settings.OTP_MAX_ATTEMPTS,
                window_started_at=now,
                window_request_count=1,
            )
            if user is not None:
                record.user_id = user.id
            self.session.add(record)

        # Send BEFORE committing, so a delivery failure leaves no active
        # challenge that the user could never receive.
        sms_result = await self.provider.send_otp(phone_e164, code)
        record.provider_name = sms_result.provider_name
        record.provider_message_id = sms_result.message_id

        return record, sms_result, code

    async def _record_failure(self, record: OtpVerification, *, burn: bool) -> None:
        """Persist an attempt counter in its own transaction.

        This MUST commit rather than flush. The request raises afterwards, and
        ``get_db`` rolls the session back on any exception - which would erase
        the counter and let an attacker guess the code forever. The security
        counter is deliberately written outside the request transaction.
        """
        record.attempt_count += 1
        if burn or record.attempt_count >= record.max_attempts:
            record.status = OtpStatus.FAILED
        await self.session.commit()

    async def _expire(self, record: OtpVerification) -> None:
        """Mark a challenge expired in its own transaction (see _record_failure)."""
        record.status = OtpStatus.EXPIRED
        await self.session.commit()

    # ------------------------------------------------------------- verification

    async def verify_otp(
        self,
        user_id: int,
        code: str,
        *,
        purpose: OtpPurpose = OtpPurpose.LOGIN,
    ) -> OtpVerification:
        """Validate a code and consume the challenge.

        Raises:
            AuthenticationError: for an unknown, expired, exhausted or wrong
                code. The message is intentionally uniform so the endpoint does
                not leak whether the phone number exists.
        """
        record = await self._find_active(user_id, purpose)
        generic_failure = AuthenticationError(
            "That code is not valid. Please request a new one."
        )

        if record is None:
            raise generic_failure

        now = utcnow()
        if record.status is not OtpStatus.PENDING:
            raise generic_failure

        expires_at = record.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
        if expires_at <= now:
            await self._expire(record)
            raise AuthenticationError("That code has expired. Please request a new one.")

        if record.attempt_count >= record.max_attempts:
            record.status = OtpStatus.FAILED
            await self.session.commit()
            raise AuthenticationError(
                "Too many incorrect attempts. Please request a new code."
            )

        secret = require_usable_secret(self.settings)
        if not verify_otp(code, record.salt, secret, record.code_hash):
            await self._record_failure(record, burn=False)
            raise generic_failure

        # Success: single use.
        record.status = OtpStatus.VERIFIED
        record.consumed_at = now
        await self.session.flush()
        return record


async def upsert_user_for_phone(session: AsyncSession, phone_e164: str) -> User:
    """Return the existing user for a phone number, creating one if needed."""
    result = await session.execute(
        select(User).where(User.phone_e164 == phone_e164)
    )
    user = result.scalar_one_or_none()
    if user is None:
        user = User(phone_e164=phone_e164)
        session.add(user)
        await session.flush()
    return user


__all__ = ["OtpService", "normalize_phone_e164", "upsert_user_for_phone"]