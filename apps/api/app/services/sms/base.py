"""SMS provider abstraction.

The rest of the application depends only on :class:`SmsProvider`, so adding a
real provider (MSG91, Gupshup, Twilio, ...) later means writing one new class
and changing ``SMS_PROVIDER`` - no business logic changes.

Hard rule: the mock adapter is development-only and is refused outright when
``ENVIRONMENT`` is ``staging`` or ``production``.
"""

from dataclasses import dataclass
from typing import Protocol

from ...core.config import Settings
from ...core.errors import AppError


class SmsDeliveryError(AppError):
    """Raised when a provider cannot accept the message."""

    status_code = 502
    code = "sms_delivery_failed"


@dataclass(frozen=True)
class SmsResult:
    """Outcome of a send attempt.

    ``provider_message_id`` is stored for support tracing; the message body and
    the OTP are never stored.
    """

    provider_name: str
    message_id: str
    delivered: bool


class SmsProvider(Protocol):
    name: str

    async def send_otp(self, phone_e164: str, code: str) -> SmsResult:
        """Deliver ``code`` to ``phone_e164``."""
        ...


def build_sms_provider(settings: Settings) -> SmsProvider:
    """Instantiate the configured provider.

    Raises:
        RuntimeError: when the mock provider is requested outside development.
    """
    from .mock import MockSmsProvider

    provider_name = (settings.SMS_PROVIDER or "").strip().lower()

    if provider_name == "mock":
        if not settings.mock_sms_enabled:
            raise RuntimeError(
                "SMS_PROVIDER='mock' is a development-only adapter and is not "
                f"permitted when ENVIRONMENT={settings.ENVIRONMENT}."
            )
        return MockSmsProvider()

    raise RuntimeError(
        f"SMS_PROVIDER={provider_name!r} is not implemented. "
        "Configure a real provider before enabling SMS in production."
    )

    if provider_name == "fast2sms":
        from .fast2sms import Fast2SmsProvider

        return Fast2SmsProvider()

    raise RuntimeError(
        f"SMS_PROVIDER={provider_name!r} is not implemented. "
        "Configure a real provider before enabling SMS in production."
    )