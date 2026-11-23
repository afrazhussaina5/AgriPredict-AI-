"""Request and response schemas for the authentication flow (Phase 4).

``OtpRequestResponse`` has a ``dev_code`` field that is ONLY ever populated when
the development mock SMS adapter is active. The route builds the response
through :func:`build_otp_request_response`, which strips the field otherwise, so
a production deployment physically cannot return an OTP.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ..models import UserRole

from ..models import LocaleCode, UserStatus
from .user import normalize_phone_e164


def _reject_admin_role(value: UserRole | None) -> UserRole | None:
    """Refuse a self-selected administrator role before it reaches the service."""
    if value is UserRole.ADMIN:
        raise ValueError(
            "Administrator access cannot be self-assigned. Contact the platform administrator."
        )
    return value


class PhoneRequest(BaseModel):
    """Start of the login flow.

    ``role`` is the role the person picks on the very first sign-in screen, so
    the role is decided **at sign-in** rather than later. It is only ever
    *applied* after the code is verified - see ``/auth/otp/verify``.
    """

    phone: str = Field(
        description="Indian mobile number; accepts 10 digits, +91, 91 or a leading 0.",
        examples=["9876543210"],
    )
    role: UserRole | None = Field(
        default=None,
        description=(
            "Role chosen at sign-in (farmer, buyer, transport_provider, "
            "storage_provider). Applied only after the code is verified; admin "
            "is never self-assigned."
        ),
    )

    @field_validator("phone")
    @classmethod
    def _normalize(cls, value: str) -> str:
        return normalize_phone_e164(value)

    @field_validator("role")
    @classmethod
    def _no_admin(cls, value: UserRole | None) -> UserRole | None:
        return _reject_admin_role(value)


class OtpRequestResponse(BaseModel):
    """Result of requesting a code.

    ``dev_code`` is present only in development/test with the mock provider.
    """

    message: str
    phone_masked: str
    expires_in_seconds: int
    resend_after_seconds: int
    dev_code: str | None = Field(
        default=None,
        description="Development only. Always null outside development/test.",
    )


class OtpVerifyRequest(BaseModel):
    phone: str
    code: str = Field(min_length=4, max_length=10, description="Numeric OTP")
    role: UserRole | None = Field(
        default=None,
        description="The role picked on the sign-in screen, applied on success.",
    )

    @field_validator("phone")
    @classmethod
    def _normalize(cls, value: str) -> str:
        return normalize_phone_e164(value)

    @field_validator("role")
    @classmethod
    def _no_admin(cls, value: UserRole | None) -> UserRole | None:
        return _reject_admin_role(value)

    @field_validator("code")
    @classmethod
    def _digits_only(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned.isdigit():
            raise ValueError("The verification code must contain digits only.")
        return cleaned


class SessionUser(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    display_name: str | None = None
    phone_masked: str | None = None
    status: UserStatus
    preferred_locale: LocaleCode
    roles: list[UserRole] = Field(default_factory=list)
    phone_verified: bool = False
    onboarding_complete: bool = False


class TokenResponse(BaseModel):
    """Issued after a successful OTP verification."""

    access_token: str
    token_type: str = "bearer"
    expires_at: datetime
    user: SessionUser


class RoleSelectionRequest(BaseModel):
    """Role chosen during onboarding.

    ``admin`` is accepted by the schema for a clear validation message, but the
    service refuses it: admin is granted only by a controlled process in Phase 15.
    """

    role: UserRole


class OnboardingRequest(BaseModel):
    """Profile details captured at the end of onboarding."""

    display_name: str = Field(min_length=2, max_length=120)
    preferred_locale: LocaleCode = LocaleCode.EN


class LogoutResponse(BaseModel):
    message: str


class MessageResponse(BaseModel):
    message: str


def build_otp_request_response(
    *,
    message: str,
    phone_masked: str,
    expires_in_seconds: int,
    resend_after_seconds: int,
    dev_code: str | None,
    mock_enabled: bool,
) -> OtpRequestResponse:
    """Build the OTP response, dropping the code unless the mock is active."""
    return OtpRequestResponse(
        message=message,
        phone_masked=phone_masked,
        expires_in_seconds=expires_in_seconds,
        resend_after_seconds=resend_after_seconds,
        dev_code=dev_code if mock_enabled else None,
    )