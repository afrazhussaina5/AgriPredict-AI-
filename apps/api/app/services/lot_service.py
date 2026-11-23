"""Produce lot business rules (Phase 6).

This module is the authority on two things the database cannot express:

1. **The lifecycle.** ``ALLOWED_LOT_TRANSITIONS`` in the models defines the
   legal moves; this service is the only place that consults it, so there is
   exactly one answer to "can this farmer pause this lot right now?".
2. **What other people may see.** A published lot is filtered field by field
   through :func:`build_public_lot`, so a hidden price is absent from the
   response body instead of being transmitted and ignored by the client.

Ownership is checked on every read and every write. A lot belonging to someone
else is reported as *not found*, never as *forbidden*, because a 403 would
confirm the lot exists to anyone who guesses an id.
"""

from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from ..core.errors import NotFoundError, ValidationError
from ..models import (
    ALLOWED_LOT_TRANSITIONS,
    EDITABLE_LOT_STATUSES,
    Commodity,
    CommodityGrade,
    CommodityVariety,
    District,
    LotStatus,
    Mandi,
    MeasurementUnit,
    ProduceLot,
    ProduceLotStatusHistory,
    User,
    UserRole,
    utcnow,
)
from ..repositories import AuditRepository, LotRepository
from ..schemas.farmer import LotCreate, LotPublicOut, LotUpdate

# How far ahead a farmer may date a lot. Beyond this it is almost certainly a
# typo, and a wrong ready_date silently breaks every downstream comparison.
MAX_READY_DATE_DAYS = 730


class LotService:
    """Create, edit and move produce lots through their lifecycle."""

    def __init__(self, session: AsyncSession, actor: User) -> None:
        self.session = session
        self.actor = actor
        self.lots = LotRepository(session)
        self.audit = AuditRepository(session)

    # ------------------------------------------------------------------
    # Reads
    # ------------------------------------------------------------------

    async def list_owned(
        self,
        *,
        status: LotStatus | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[ProduceLot], int]:
        """Only ever returns lots belonging to the calling farmer."""
        return await self.lots.list_for_farmer(
            self.actor.id, status=status, limit=limit, offset=offset
        )

    async def get_owned_or_404(self, lot_id: int) -> ProduceLot:
        """Fetch the caller's own lot, or raise a 404 that leaks nothing."""
        lot = await self.lots.get_owned(lot_id, self.actor.id)
        if lot is None:
            # Deliberately the same message whether the lot does not exist or
            # belongs to someone else.
            raise NotFoundError("That lot does not exist.")
        return lot

    def allowed_transitions(self, status: LotStatus) -> list[LotStatus]:
        return sorted(ALLOWED_LOT_TRANSITIONS.get(status, frozenset()),
                      key=lambda item: item.value)

    # ------------------------------------------------------------------
    # Writes
    # ------------------------------------------------------------------

    async def create(self, payload: LotCreate) -> ProduceLot:
        """Create a draft lot owned by the calling farmer."""
        await self._validate_reference_ids(
            commodity_id=payload.commodity_id,
            variety_id=payload.variety_id,
            grade_id=payload.grade_id,
            unit_id=payload.unit_id,
            district_id=payload.pickup_district_id,
            mandi_id=payload.pickup_mandi_id,
        )
        self._validate_ready_date(payload.ready_date)
        self._validate_price_range(
            payload.expected_price_per_unit, payload.min_expected_price_per_unit
        )

        lot = ProduceLot(
            farmer_id=self.actor.id,
            commodity_id=payload.commodity_id,
            variety_id=payload.variety_id,
            grade_id=payload.grade_id,
            quantity=payload.quantity,
            unit_id=payload.unit_id,
            pickup_district_id=payload.pickup_district_id,
            pickup_mandi_id=payload.pickup_mandi_id,
            pickup_area_label=payload.pickup_area_label or None,
            ready_date=payload.ready_date,
            expected_price_per_unit=payload.expected_price_per_unit,
            min_expected_price_per_unit=payload.min_expected_price_per_unit,
            notes=payload.notes or None,
            show_expected_price=payload.show_expected_price,
            show_pickup_area=payload.show_pickup_area,
            show_notes=payload.show_notes,
            status=LotStatus.DRAFT,
        )
        self.lots.add(lot)
        await self.session.flush()

        # The first history row has no "from": the lot did not exist before.
        self.lots.add_history(
            ProduceLotStatusHistory(
                lot_id=lot.id,
                from_status=None,
                to_status=LotStatus.DRAFT,
                changed_by_user_id=self.actor.id,
                note="Lot created.",
            )
        )
        await self.audit.record(
            action="lot.created",
            entity_type="produce_lot",
            entity_id=lot.id,
            actor_user_id=self.actor.id,
            actor_role=UserRole.FARMER,
            details={
                "commodity_id": lot.commodity_id,
                "quantity": str(lot.quantity),
                "status": LotStatus.DRAFT.value,
            },
        )
        await self.session.flush()
        return lot

    async def update(self, lot: ProduceLot, payload: LotUpdate) -> ProduceLot:
        """Edit a lot's content.

        Refused unless the lot is draft or paused: a published lot must be
        paused first so that a buyer never watches the quantity or grade change
        underneath an offer they are considering.
        """
        if lot.status not in EDITABLE_LOT_STATUSES:
            raise ValidationError(
                "A published or closed lot cannot be edited. "
                "Pause it first, then make your changes."
            )

        # exclude_unset keeps "not mentioned" distinct from "set to nothing".
        # An explicit null means "leave this alone"; an empty string is the only
        # way to clear a free-text field.
        changes = payload.model_dump(exclude_unset=True)
        for field, value in list(changes.items()):
            if value is None:
                del changes[field]
            elif value == "" and field in ("notes", "pickup_area_label"):
                changes[field] = None

        for field, value in changes.items():
            setattr(lot, field, value)

        await self._validate_reference_ids(
            commodity_id=lot.commodity_id,
            variety_id=lot.variety_id,
            grade_id=lot.grade_id,
            unit_id=lot.unit_id,
            district_id=lot.pickup_district_id,
            mandi_id=lot.pickup_mandi_id,
        )

        if "ready_date" in changes:
            self._validate_ready_date(lot.ready_date)
        if "quantity" in changes and lot.quantity <= 0:
            raise ValidationError("Quantity must be greater than zero.")

        self._validate_price_range(
            lot.expected_price_per_unit, lot.min_expected_price_per_unit
        )
        self._validate_visibility_choices(lot)

        self.session.add(lot)
        await self.audit.record(
            action="lot.updated",
            entity_type="produce_lot",
            entity_id=lot.id,
            actor_user_id=self.actor.id,
            actor_role=UserRole.FARMER,
            details={"fields": sorted(changes.keys())},
        )
        await self.session.flush()
        return lot

    async def change_status(
        self, lot: ProduceLot, new_status: LotStatus, reason: str | None = None
    ) -> ProduceLot:
        """Move a lot to ``new_status`` if the lifecycle allows it.

        The client may only *ask*. Whether the move is legal is decided here.
        """
        if new_status == lot.status:
            raise ValidationError(f"This lot is already {new_status.value}.")

        allowed = ALLOWED_LOT_TRANSITIONS.get(lot.status, frozenset())
        if new_status not in allowed:
            raise ValidationError(
                f"A {lot.status.value} lot cannot be changed to {new_status.value}. "
                "Allowed next steps: "
                + (
                    ", ".join(sorted(item.value for item in allowed))
                    if allowed
                    else "none, this status is final"
                )
                + "."
            )

        # Publishing is the moment a lot becomes visible, so this is the moment
        # worth checking that it is actually complete.
        if new_status is LotStatus.PUBLISHED:
            self._require_publishable(lot)

        previous = lot.status
        now = utcnow()
        lot.status = new_status
        if new_status is LotStatus.PUBLISHED:
            lot.published_at = lot.published_at or now
        elif new_status is LotStatus.CLOSED:
            lot.closed_at = now
            lot.closed_reason = reason or None
        elif new_status is LotStatus.ARCHIVED:
            lot.archived_at = now

        self.session.add(lot)
        self.lots.add_history(
            ProduceLotStatusHistory(
                lot_id=lot.id,
                from_status=previous,
                to_status=new_status,
                changed_by_user_id=self.actor.id,
                note=reason or None,
            )
        )
        await self.audit.record(
            action=f"lot.{new_status.value}",
            entity_type="produce_lot",
            entity_id=lot.id,
            actor_user_id=self.actor.id,
            actor_role=UserRole.FARMER,
            details={"from": previous.value, "to": new_status.value},
        )
        await self.session.flush()
        return lot

    # ------------------------------------------------------------------
    # Validation helpers
    # ------------------------------------------------------------------

    def _require_publishable(self, lot: ProduceLot) -> None:
        """Refuse to publish a lot that cannot be acted on by a buyer."""
        if lot.quantity is None or lot.quantity <= 0:
            raise ValidationError("Set a quantity greater than zero before publishing.")
        if lot.commodity_id is None:
            raise ValidationError("Choose a commodity before publishing.")
        if lot.unit_id is None:
            raise ValidationError("Choose a unit before publishing.")
        if lot.ready_date is None:
            raise ValidationError("Set a ready date before publishing.")

    async def _validate_reference_ids(
        self,
        *,
        commodity_id: int,
        unit_id: int,
        variety_id: int | None,
        grade_id: int | None,
        district_id: int | None,
        mandi_id: int | None,
    ) -> None:
        """Check every foreign key actually points at an active reference row.

        Checked in Python rather than left to the database so the farmer gets a
        message that names the field instead of an opaque integrity error.
        """
        commodity = await self.session.get(Commodity, commodity_id)
        if commodity is None or not commodity.is_active:
            raise ValidationError("Choose a commodity from the loaded list.")

        unit = await self.session.get(MeasurementUnit, unit_id)
        if unit is None or not unit.is_active:
            raise ValidationError("Choose a unit from the loaded list.")

        if variety_id is not None:
            variety = await self.session.get(CommodityVariety, variety_id)
            if variety is None or not variety.is_active:
                raise ValidationError("That variety is not available.")
            # A variety of a different crop would produce nonsense comparisons
            # later, so refuse it now rather than at Phase 12.
            if variety.commodity_id != commodity_id:
                raise ValidationError("That variety does not belong to this commodity.")

        if grade_id is not None:
            grade = await self.session.get(CommodityGrade, grade_id)
            if grade is None or not grade.is_active:
                raise ValidationError("That grade is not available.")
            # A null commodity_id on a grade means "applies to every commodity",
            # which is legal. Anything else must match.
            if grade.commodity_id is not None and grade.commodity_id != commodity_id:
                raise ValidationError("That grade does not belong to this commodity.")

        if district_id is not None:
            district = await self.session.get(District, district_id)
            if district is None or not district.is_active:
                raise ValidationError("That district is not available.")

        if mandi_id is not None:
            if district_id is None:
                raise ValidationError(
                    "Choose the district before choosing a mandi."
                )
            mandi = await self.session.get(Mandi, mandi_id)
            if mandi is None or not mandi.is_active:
                raise ValidationError("That mandi is not available.")
            if mandi.district_id != district_id:
                raise ValidationError("That mandi is not in the chosen district.")

    @staticmethod
    def _validate_ready_date(ready_date: date) -> None:
        if ready_date > date.today() + timedelta(days=MAX_READY_DATE_DAYS):
            raise ValidationError(
                "The ready date is more than two years away. Please check the year."
            )

    @staticmethod
    def _validate_price_range(
        expected: Decimal | None, minimum: Decimal | None
    ) -> None:
        if expected is None and minimum is not None:
            raise ValidationError(
                "A minimum price needs an expected price to compare against."
            )
        if expected is not None and minimum is not None and minimum > expected:
            raise ValidationError(
                "The minimum price cannot be greater than the expected price."
            )

    @staticmethod
    def _validate_visibility_choices(lot: ProduceLot) -> None:
        """A 'show this' flag on an empty field would advertise nothing."""
        if lot.show_expected_price and lot.expected_price_per_unit is None:
            raise ValidationError(
                "Set an expected price before choosing to show it."
            )
        if lot.show_pickup_area and not (
            lot.pickup_area_label or lot.pickup_district_id is not None
        ):
            raise ValidationError("Set a pickup area before choosing to show it.")
        if lot.show_notes and not lot.notes:
            raise ValidationError("Write some notes before choosing to show them.")


def build_public_lot(lot: ProduceLot) -> LotPublicOut:
    """Project a lot into the view another user is allowed to see.

    Only a **published** lot is ever visible; every other status returns None
    so a paused or draft lot cannot leak through a filtered list endpoint.
    """
    if lot.status is not LotStatus.PUBLISHED:
        return None  # type: ignore[return-value]

    return LotPublicOut(
        id=lot.id,
        farmer_id=lot.farmer_id,
        commodity_id=lot.commodity_id,
        commodity_name=_name(lot.commodity),
        variety_name=_name(lot.variety),
        grade_name=_name(lot.grade),
        # Quantity and unit are core facts a buyer needs, never hidden.
        quantity=lot.quantity,
        unit_name=_name(lot.unit),
        unit_code=lot.unit.code if lot.unit is not None else None,
        # District-level granularity is public. The exact pickup point is not,
        # and the free-text area label is only public when the farmer opted in.
        pickup_district_name=_name(lot.pickup_district),
        pickup_mandi_name=(
            _name(lot.pickup_mandi) if lot.show_pickup_area else None
        ),
        ready_date=lot.ready_date,
        expected_price_per_unit=(
            lot.expected_price_per_unit if lot.show_expected_price else None
        ),
        notes=lot.notes if lot.show_notes else None,
        status=lot.status,
        published_at=lot.published_at,
    )


def _name(row: object) -> str | None:
    """Read a reference row's display name, tolerating a missing row."""
    return getattr(row, "name", None)


__all__ = ["LotService", "build_public_lot"]