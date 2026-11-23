"""Fast2SMS free-tier SMS provider adapter.

Fast2SMS used to publish a generous free tier (up to 100 messages/day per
registration) that fits a small Indian agri-platform: a handful of OTPs per day
are the norm for login flows, and the free plan never expires as long as you
stay within the daily message cap. It returns a clear 429 when the cap is hit,
so the abuse counters in ``otp_service`` still protect the account.

Usage:
    SMS_PROVIDER=fast2sms
    FAST2SMS_API_KEY=<your-key>

The implementation is intentionally small: an OTP is one message, the provider
returns 200/201 with an ``id``/``MessageId`` and any 4xx/5xx becomes a
``SmsDeliveryError``. Credentials are never logged.
"""

import json
import os
from typing import Any

import aiohttp

from .base import SmsResult, SmsDeliveryError

FAST2SMS_SEND_OTP_URL = "https://www.fast2sms.com/dev/bulkSms"


class Fast2SmsProvider:
    """Send OTPs through Fast2SMS's free bulk-SMS endpoint."""

    name = "fast2sms"

    def __init__(self, session: aiohttp.ClientSession | None = None) -> None:
        self._session = session or aiohttp.ClientSession()
        self._api_key = os.environ.get("FAST2SMS_API_KEY", "").strip()
        if not self._api_key:
            raise RuntimeError(
                "SMS_PROVIDER='fast2sms' requires FAST2SMS_API_KEY in the environment."
            )

    async def send_otp(self, phone_e164: str, code: str) -> SmsResult:
        if not self._api_key:
            raise RuntimeError(
                "SMS_PROVIDER='fast2sms' is misconfigured: FAST2SMS_API_KEY is empty."
            )

        payload = {
            "authorization": self._api_key,
            "message": f"AgriPredict AI OTP: {code}. Please do not share it.",
            "language": "english",
            "route": "otp",
            "numbers": phone_e164.replace("+91", ""),
        }

        try:
            async with self._session.post(
                FAST2SMS_SEND_OTP_URL, data=payload, timeout=aiohttp.ClientTimeout(total=15)
            ) as response:
                body = await response.text()
                if response.status in {200, 201}:
                    # Fast2SMS returns a JSON envelope with MessageId / id.
                    try:
                        parsed: Any = json.loads(body)
                        message_id = parsed.get("id") or parsed.get("MessageId")
                    except Exception:
                        message_id = body[:60]
                    return SmsResult(
                        provider_name=self.name, message_id=str(message_id or "ok"), delivered=True
                    )

                raise SmsDeliveryError(f"Fast2SMS returned HTTP {response.status}: {body[:160]}")
        except Exception as exc:  # noqa: BLE001 - surface any network failure
            raise SmsDeliveryError(f"Fast2SMS request failed: {exc}") from None

    async def close(self) -> None:
        if self._session is not None:
            await self._session.close()


__all__ = ["Fast2SmsProvider"]
