"""Request and response schemas for the buyer / matching flow (Phase 7)."""

from datetime import date

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ..models import ProfileStatus, UserRole
from .user import normalize_phone_e164

# A purchase requirement is an endorsement the buyer posts. It carries every
# fact a farmer needs to know before deciding whether to sell into it.
MIN_REQUIRED_VALUE = "0.001"


class RequirementOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    buyer_id: int
    commodity_id: int
    grade_id: int | None = None
    min_required_value: str
    delivery_window_days: int
    created_at: date | None = None

    @field_validator("min_required_value")
    @classmethod
    def _format(cls, value: str) -> str:
        return str(value)


class RequirementRequest(BaseModel):
    commodity_id: int = Field(description="Which crop you are looking to buy.")
    grade_id: int | None = Field(
        default=None, description="Required quality grade. Omit for any."
    )
    min_required_value: str = Field(
        default="0.001", description="Minimum quantity you will buy."
    )
    delivery_window_days: int = Field(
        default=3, description="Days you will wait for the lot."
    )

    @field_validator("min_required_value")
    @classmethod
    def _value(cls, value: str) -> str:
        try:
            Decimal(value)
        except Exception as exc:  # noqa: BLE001
            raise ValueError("min_required_value must be a decimal string.") from exc
        return value

    @field_validator("delivery_window_days")
    @classmethod
    def _days(cls, value: int) -> int:
        if not (1 <= value <= 30):
            raise ValueError("delivery_window_days must be between 1 and 30.")
        return value


class RequirementCreated(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    buyer_id: int
    commodity_id: int
    grade_id: int | None = None
    min_required_value: str
    delivery_window_days: int
    created_at: date | None = None


class BuyerProfileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    business_name: str
    contact_person_name: str | None = None
    business_type: str | None = None
    gst_number: str | None = None
    preferred_language: str
    state_id: int | None = None
    district_id: int | None = None
    address_line: str | None = None
    contact_phone_visible: bool
    completion_percent: int
    status: ProfileStatus
    created_at: date | None = None


class BuyerProfileCreate(BaseModel):
    business_name: str = Field(min_length=2, max_length=200)
    contact_person_name: str | None = Field(default=None, max_length=150)
    business_type: str | None = Field(default=None, max_length=80)
    gst_number: str | None = Field(default=None, max_length=20)
    preferred_language: str = "en"
    state_id: int | None = None
    district_id: int | None = None
    address_line: str | None = Field(default=None, max_length=300)
    contact_phone_visible: bool = False

    @field_validator("gst_number")
    @classmethod
    def _gst(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip().upper()
        if not cleaned:
            return None
        if not cleaned.replace(" ", "").replace("-", "").isalnum():
            raise ValueError("gst_number must be alphanumeric.")
        return cleaned


class BuyerPhoneRequest(BaseModel):
    phone: str

    @field_validator("phone")
    @classmethod
    def _normalize(cls, value: str) -> str:
        return normalize_phone_e164(value)


class MatchDetail(BaseModel):
    lot_id: int
    commodity_id: int
    commodity_name: str | None = None
    grade_id: int | None = None
    quantity: str | None = None
    criteria: dict[str, bool]


class MatchResponse(BaseModel):
    matched_count: int
    total_candidates: int
    hits: list[MatchDetail]
