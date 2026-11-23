"""User-facing schemas for Phase 3.

``UserPublic`` deliberately has no ``phone_e164`` field. Only a masked value is
ever returned, so a leaked response can never reveal a full phone number.
"""

import re
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ..models import LocaleCode, ProfileStatus, UserRole, UserStatus

# Indian mobile numbers: 10 digits starting 6-9, optionally with 0, +91 or 91.
_PHONE_PATTERN = re.compile(r"^(?:\+?91|0)?([6-9]\d{9})$")


def normalize_phone_e164(raw: str) -> str:
    """Normalise an Indian phone number to ``+91XXXXXXXXXX``.

    Raises:
        ValueError: when the input is not a valid Indian mobile number.
    """
    cleaned = re.sub(r"[\s\-()]", "", (raw or "").strip())
    match = _PHONE_PATTERN.match(cleaned)
    if not match:
        raise ValueError("Enter a valid 10-digit Indian mobile number.")
    return f"+91{match.group(1)}"


def mask_phone(phone_e164: str | None) -> str | None:
    """Return a display-safe form such as ``+91 ******1234``."""
    if not phone_e164 or len(phone_e164) < 4:
        return None
    return f"+91 ******{phone_e164[-4:]}"


class UserPublic(BaseModel):
    """Read model for an account. Never contains the full phone number."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    display_name: str | None = None
    phone_masked: str | None = None
    status: UserStatus
    preferred_locale: LocaleCode
    roles: list[UserRole] = Field(default_factory=list)
    phone_verified: bool = False


class RoleAssignmentPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    role: UserRole
    granted_at: datetime


class AuditLogPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    action: str
    entity_type: str
    entity_id: str | None = None
    actor_user_id: int | None = None
    result: str
    created_at: datetime


class FarmerProfileBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    full_name: str = Field(min_length=2, max_length=150)
    organisation_name: str | None = Field(default=None, max_length=150)
    preferred_language: LocaleCode = LocaleCode.EN
    village_or_town: str | None = Field(default=None, max_length=150)
    show_exact_location_to_buyers: bool = False
    contact_phone_visible: bool = False


class FarmerProfilePublic(FarmerProfileBase):
    id: int
    user_id: int
    completion_percent: int
    status: ProfileStatus
    state_id: int | None = None
    district_id: int | None = None


class BuyerProfileBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    business_name: str = Field(min_length=2, max_length=200)
    contact_person_name: str | None = Field(default=None, max_length=150)
    business_type: str | None = Field(default=None, max_length=80)
    preferred_language: LocaleCode = LocaleCode.EN
    contact_phone_visible: bool = False


class BuyerProfilePublic(BuyerProfileBase):
    id: int
    user_id: int
    completion_percent: int
    status: ProfileStatus


class PhoneValidationSample(BaseModel):
    """Schema-only helper used by tests to exercise phone normalisation."""

    phone: str

    @field_validator("phone")
    @classmethod
    def _normalize(cls, value: str) -> str:
        return normalize_phone_e164(value)