"""Development-only mock SMS provider.

This adapter does NOT send an SMS. It records the message in memory so a
developer can read the code from the API response or the log. It is:

* refused when ENVIRONMENT is staging or production (see build_sms_provider),
* never used by the production OTP response schema - the endpoint strips
  ``dev_code`` unless ``settings.mock_sms_enabled`` is true.

Nothing in this module is safe to enable in production.
"""

import itertools
from datetime import UTC, datetime

from .base import SmsResult


class MockSmsProvider:
    """Keeps sent OTPs in a bounded in-memory list for local testing."""

    name = "mock"

    def __init__(self, *, history_limit: int = 50) -> None:
        self._history: list[dict[str, str]] = []
        self._history_limit = history_limit
        self._counter = itertools.count(1)

    async def send_otp(self, phone_e164: str, code: str) -> SmsResult:
        message_id = f"mock-{next(self._counter):06d}"
        self._history.append(
            {
                "phone_e164": phone_e164,
                "code": code,
                "message_id": message_id,
                "sent_at": datetime.now(UTC).isoformat(),
            }
        )
        del self._history[: max(0, len(self._history) - self._history_limit)]
        return SmsResult(provider_name=self.name, message_id=message_id, delivered=True)

    def last_code_for(self, phone_e164: str) -> str | None:
        """Return the most recent code sent to a number (tests/developer use)."""
        for entry in reversed(self._history):
            if entry["phone_e164"] == phone_e164:
                return entry["code"]
        return None

    def clear(self) -> None:
        self._history.clear()