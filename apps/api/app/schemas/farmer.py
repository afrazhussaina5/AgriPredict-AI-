"""Schemas for farmer profiles and produce lots (Phase 6).

Two ideas drive the shapes here:

* **Nothing is implicit.** A price the farmer did not state is ``None``, never
  ``0``. A farmer who hides their floor price must not be represented as
  offering produce for nothing.
* **The owner sees everything; others see only what was shared.** ``LotOut``
  is always the owner's view. ``LotPublicOut`` is what anybody else may see,
  and it physically has no price, notes or exact pickup fields - so a
  forgotten filter cannot leak them.
"""

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ..models import LotStatus, ProfileStatus

# Prices and quantities are bounded so a typo cannot store an absurd number that
# only shows up later inside a net-realization calculation.
PRICE_MIN = Decimal("0")
PRICE_MAX = Decimal("100000000")
QUANTITY_MIN = Decimal("0.001")
QUANTITY_MAX = Decimal("100000000")


# --------------------------------------------------------------------------
# Farmer profile
# --------------------------------------------------------------------------


class FarmerProfileUpdate(BaseModel):
    """Fields a farmer may change about their own profile.

    Every field is optional so a partial save works. ``None`` means "leave this
    alone"; to clear an optional field send an explicit empty string, which the
    service normalises to NULL.
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    full_name: str | None = Field(default=None, min_length=2, max_length=150)
    organisation_name: str | None = Field(default=None, max_length=150)
    village_or_town: str | None = Field(default=None, max_length=150)
    bio: str | None = Field(default=None, max_length=1000)
    state_id: int | None = None
    district_id: int | None = None
    mandi_id: int | None = None
    show_exact_location_to_buyers: bool | None = None
    contact_phone_visible: bool | None = None


class FarmerProfileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    full_name: str
    organisation_name: str | None = None
    preferred_language: str
    state_id: int | None = None
    district_id: int | None = None
    mandi_id: int | None = None
    village_or_town: str | None = None
    bio: str | None = None
    show_exact_location_to_buyers: bool = False
    contact_phone_visible: bool = False
    completion_percent: int = 0
    status: ProfileStatus
    created_at: datetime | None = None
    updated_at: datetime | None = None
    # Human-readable names resolved from the reference tables, so the UI does
    # not have to join tables it already fetched in Phase 5.
    state_name: str | None = None
    district_name: str | None = None
    mandi_name: str | None = None


# --------------------------------------------------------------------------
# Produce lots
# --------------------------------------------------------------------------


class LotBase(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    commodity_id: int = Field(description="Required. Which crop is being sold.")
    variety_id: int | None = Field(
        default=None, description="Optional. Leave empty if the farmer is not sure."
    )
    grade_id: int | None = Field(default=None, description="Optional quality grade.")
    quantity: Decimal = Field(
        ge=QUANTITY_MIN, le=QUANTITY_MAX, description="Must be greater than zero."
    )
    unit_id: int = Field(description="Unit the quantity is counted in.")
    ready_date: date = Field(description="The day the produce will be available.")
    pickup_district_id: int | None = None
    pickup_mandi_id: int | None = None
    pickup_area_label: str | None = Field(default=None, max_length=150)
    expected_price_per_unit: Decimal | None = Field(
        default=None, ge=PRICE_MIN, le=PRICE_MAX
    )
    min_expected_price_per_unit: Decimal | None = Field(
        default=None, ge=PRICE_MIN, le=PRICE_MAX
    )
    notes: str | None = Field(default=None, max_length=2000)
    show_expected_price: bool = False
    show_pickup_area: bool = False
    show_notes: bool = False

    @model_validator(mode="after")
    def _check_consistency(self) -> "LotBase":
        # A mandi always belongs to a district, so a mandi without a district is
        # meaningless. Fail here rather than storing an inconsistent row.
        if self.pickup_mandi_id is not None and self.pickup_district_id is None:
            raise ValueError("pickup_district_id is required when a mandi is selected.")
        if (
            self.expected_price_per_unit is not None
            and self.min_expected_price_per_unit is not None
            and self.min_expected_price_per_unit > self.expected_price_per_unit
        ):
            raise ValueError(
                "min_expected_price_per_unit cannot be greater than "
                "expected_price_per_unit."
            )
        # Opting in to showing a price that was never stated would advertise
        # an empty price. Refuse rather than render a blank.
        if self.show_expected_price and self.expected_price_per_unit is None:
            raise ValueError(
                "Cannot show an expected price when no expected price is set."
            )
        if self.show_pickup_area and not (
            self.pickup_area_label or self.pickup_district_id is not None
        ):
            raise ValueError("Cannot show a pickup area when no pickup area is set.")
        if self.show_notes and not self.notes:
            raise ValueError("Cannot show notes when no notes are set.")
        return self


class LotCreate(LotBase):
    """Create a new lot. It always starts as a draft."""


class LotUpdate(BaseModel):
    """Partial update. Only ``None`` fields are left untouched.

    Status is deliberately absent: a lot moves status through
    ``POST /lots/{id}/status``, never through an edit, so every transition is
    validated in one place and recorded in the history.
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    commodity_id: int | None = None
    variety_id: int | None = None
    grade_id: int | None = None
    quantity: Decimal | None = Field(default=None, ge=QUANTITY_MIN, le=QUANTITY_MAX)
    unit_id: int | None = None
    ready_date: date | None = None
    pickup_district_id: int | None = None
    pickup_mandi_id: int | None = None
    pickup_area_label: str | None = Field(default=None, max_length=150)
    expected_price_per_unit: Decimal | None = Field(
        default=None, ge=PRICE_MIN, le=PRICE_MAX
    )
    min_expected_price_per_unit: Decimal | None = Field(
        default=None, ge=PRICE_MIN, le=PRICE_MAX
    )
    notes: str | None = Field(default=None, max_length=2000)
    show_expected_price: bool | None = None
    show_pickup_area: bool | None = None
    show_notes: bool | None = None


class LotStatusChange(BaseModel):
    """Request a lifecycle move.

    The client asks for the new status. The server decides whether it is legal -
    the client cannot assert its own transition.
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    status: LotStatus
    reason: str | None = Field(
        default=None,
        max_length=300,
        description="Optional, kept for the farmer's own history.",
    )


class LotHistoryEntry(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    from_status: LotStatus | None = None
    to_status: LotStatus
    note: str | None = None
    changed_at: datetime


class _LotNames(BaseModel):
    """Resolved reference names, so the UI never has to join tables itself."""

    commodity_name: str | None = None
    variety_name: str | None = None
    grade_name: str | None = None
    unit_name: str | None = None
    unit_code: str | None = None
    pickup_district_name: str | None = None
    pickup_mandi_name: str | None = None


class LotOut(_LotNames):
    """The owner's view of a lot. Carries every field, hidden or not."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    farmer_id: int
    commodity_id: int
    variety_id: int | None = None
    grade_id: int | None = None
    quantity: Decimal
    unit_id: int
    pickup_district_id: int | None = None
    pickup_mandi_id: int | None = None
    pickup_area_label: str | None = None
    ready_date: date
    expected_price_per_unit: Decimal | None = None
    min_expected_price_per_unit: Decimal | None = None
    show_expected_price: bool = False
    show_pickup_area: bool = False
    show_notes: bool = False
    notes: str | None = None
    status: LotStatus
    published_at: datetime | None = None
    closed_at: datetime | None = None
    archived_at: datetime | None = None
    closed_reason: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class LotPublicOut(BaseModel):
    """What a buyer or another farmer may see.

    Built by a dedicated function rather than by hiding fields on ``LotOut``,
    so a hidden value is absent from the payload entirely instead of being sent
    and ignored by the client.
    """

    id: int
    farmer_id: int
    commodity_id: int
    commodity_name: str | None = None
    variety_name: str | None = None
    grade_name: str | None = None
    quantity: Decimal | None = None
    unit_name: str | None = None
    unit_code: str | None = None
    # District-level granularity only. The exact pickup point is never included.
    pickup_district_name: str | None = None
    pickup_mandi_name: str | None = None
    ready_date: date | None = None
    expected_price_per_unit: Decimal | None = None
    notes: str | None = None
    status: LotStatus
    published_at: datetime | None = None


class LotListOut(BaseModel):
    """A page of the farmer's own lots."""

    items: list[LotOut]
    total: int
    limit: int
    offset: int


class LotDetailOut(LotOut):
    """The owner's view plus the full status timeline."""

    history: list[LotHistoryEntry] = Field(default_factory=list)
    allowed_transitions: list[LotStatus] = Field(default_factory=list)


__all__ = [
    "FarmerProfileOut",
    "FarmerProfileUpdate",
    "LotBase",
    "LotCreate",
    "LotDetailOut",
    "LotHistoryEntry",
    "LotListOut",
    "LotOut",
    "LotPublicOut",
    "LotStatusChange",
    "LotUpdate",
]