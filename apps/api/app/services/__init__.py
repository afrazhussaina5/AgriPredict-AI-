"""Business-logic services.

Services orchestrate repositories and models. They never build SQL directly
and never import FastAPI request objects, which keeps them testable in isolation.
"""

from .otp_service import OtpService, upsert_user_for_phone

__all__ = ["OtpService", "upsert_user_for_phone"]