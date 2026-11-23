"""Farmer profiles and produce lots (Phase 6).

A **produce lot** is one batch of produce that a farmer intends to sell. It is
the first thing a farmer creates after signing in, and the unit of everything
downstream: offers (Phase 8), transport (Phase 9), storage (Phase 10) and net
realization (Phase 13) all hang off a lot.

Design rules enforced here rather than by convention:

* **Ownership is a column, not a convention.** ``farmer_id`` is a real foreign
  key to ``users.id``; the service layer additionally refuses any operation on a
  lot the caller does not own.
* **The lifecycle is a closed state machine.** ``draft -> published -> paused ->
  closed -> archived``. ``archived`` is terminal. The allowed transitions live
  in ``ALLOWED_LOT_TRANSITIONS`` and are enforced in the service, not here, so
  the error message can be farmer-readable.
* **Privacy defaults are the safe setting.** Expected price, exact pickup point
  and notes are all hidden by default. A farmer has to opt in, per lot.
* **Money and quantity are Decimal, never float.** Float arithmetic on rupees
  loses cents, and the whole product promise is an honest number.
* A lot is never hard-deleted. ``archived`` is the tombstone, so the status
  history and the audit trail stay meaningful.
"""

from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..core.database import Base
from .base import TimestampMixin, sa_enum, utcnow


class LotStatus(StrEnum):
    """Where a lot is in its life. Ordered by how visible it is, not by time."""

    DRAFT = "draft"
    PUBLISHED = "published"
    PAUSED = "paused"
    CLOSED = "closed"
    ARCHIVED = "archived"


# The complete, closed set of legal moves. Anything not listed here is refused
# by the service layer with a message the farmer can act on.
ALLOWED_LOT_TRANSITIONS: dict[LotStatus, frozenset[LotStatus]] = {
    LotStatus.DRAFT: frozenset({LotStatus.PUBLISHED, LotStatus.ARCHIVED}),
    LotStatus.PUBLISHED: frozenset(
        {LotStatus.PAUSED, LotStatus.CLOSED, LotStatus.ARCHIVED}
    ),
    LotStatus.PAUSED: frozenset(
        {LotStatus.PUBLISHED, LotStatus.CLOSED, LotStatus.ARCHIVED}
    ),
    LotStatus.CLOSED: frozenset({LotStatus.ARCHIVED}),
    # Terminal: an archived lot can never move again. Un-archiving is a
    # moderation action (Phase 15), not something a farmer can do.
    LotStatus.ARCHIVED: frozenset(),
}

# Statuses in which the farmer may still change what is being sold. Publishing
# locks the content so buyers never see a lot mutate under them.
EDITABLE_LOT_STATUSES: frozenset[LotStatus] = frozenset(
    {LotStatus.DRAFT, LotStatus.PAUSED}
)


class ProduceLot(Base, TimestampMixin):
    """One batch of produce offered for sale by one farmer."""

    __tablename__ = "produce_lots"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_produce_lots_quantity_positive"),
        CheckConstraint(
            "expected_price_per_unit IS NULL OR expected_price_per_unit >= 0",
            name="ck_produce_lots_price_not_negative",
        ),
        CheckConstraint(
            "min_expected_price_per_unit IS NULL "
            "OR expected_price_per_unit IS NULL "
            "OR min_expected_price_per_unit <= expected_price_per_unit",
            name="ck_produce_lots_price_range_ordered",
        ),
        CheckConstraint(
            "(pickup_mandi_id IS NULL OR pickup_district_id IS NOT NULL)",
            name="ck_produce_lots_mandi_requires_district",
        ),
        # The farmer's own list view: "my lots, newest first".
        Index("ix_produce_lots_farmer", "farmer_id", "status", "created_at"),
        # The public marketplace view for Phase 7: published lots by ready date.
        Index("ix_produce_lots_public", "status", "ready_date"),
        Index("ix_produce_lots_commodity", "commodity_id", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # The owning farmer. ON DELETE CASCADE matches the user's right to erasure;
    # the audit log keeps a pseudonymous actor id afterwards.
    farmer_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )

    # What is being sold. Only the commodity is mandatory: a farmer who does not
    # know the variety or grade should still be able to list their produce
    # rather than be blocked by a missing reference row.
    commodity_id: Mapped[int] = mapped_column(
        ForeignKey("reference_commodities.id", ondelete="RESTRICT"), nullable=False
    )
    variety_id: Mapped[int | None] = mapped_column(
        ForeignKey("reference_commodity_varieties.id", ondelete="RESTRICT"),
        nullable=True,
    )
    grade_id: Mapped[int | None] = mapped_column(
        ForeignKey("reference_commodity_grades.id", ondelete="RESTRICT"), nullable=True
    )

    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    unit_id: Mapped[int] = mapped_column(
        ForeignKey("reference_units.id", ondelete="RESTRICT"), nullable=False
    )

    # Coarse public pickup area. The district is the public granularity; the
    # exact point is only ever described in free text and only when the farmer
    # opts in below.
    pickup_district_id: Mapped[int | None] = mapped_column(
        ForeignKey("reference_districts.id", ondelete="RESTRICT"), nullable=True
    )
    pickup_mandi_id: Mapped[int | None] = mapped_column(
        ForeignKey("reference_mandis.id", ondelete="RESTRICT"), nullable=True
    )
    pickup_area_label: Mapped[str | None] = mapped_column(String(150), nullable=True)

    ready_date: Mapped[date] = mapped_column(Date, nullable=False)

    # Money. Optional on purpose: many farmers would rather negotiate than
    # anchor a price in public. Null means "not stated", never "zero".
    expected_price_per_unit: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 2), nullable=True
    )
    min_expected_price_per_unit: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 2), nullable=True
    )

    # Privacy controls. Every one of these defaults to the private setting;
    # publishing a lot must not silently expose a farmer's floor price.
    show_expected_price: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    show_pickup_area: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    show_notes: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Free-text the farmer writes for buyers. Never shown unless show_notes.
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    status: Mapped[LotStatus] = mapped_column(
        sa_enum(LotStatus, "lot_status"), nullable=False, default=LotStatus.DRAFT
    )
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    closed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    archived_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # Why a lot was closed, in the farmer's own words. Shown to nobody else.
    closed_reason: Mapped[str | None] = mapped_column(String(300), nullable=True)

    farmer = relationship("User", foreign_keys=[farmer_id])
    commodity = relationship("Commodity", lazy="joined")
    variety = relationship("CommodityVariety", lazy="joined")
    grade = relationship("CommodityGrade", lazy="joined")
    unit = relationship("MeasurementUnit", lazy="joined")
    pickup_district = relationship("District", lazy="joined")
    pickup_mandi = relationship("Mandi", lazy="joined")
    history = relationship(
        "ProduceLotStatusHistory",
        back_populates="lot",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="ProduceLotStatusHistory.id",
    )


class ProduceLotStatusHistory(Base):
    """Append-only record of every lifecycle move on a lot.

    Separate from ``audit_logs`` on purpose: this is a farmer-facing timeline
    ("you published this on Tuesday, then paused it"), so it must stay
    readable even after an admin account is retired.
    """

    __tablename__ = "produce_lot_status_history"
    __table_args__ = (
        Index("ix_produce_lot_history_lot", "lot_id", "id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    lot_id: Mapped[int] = mapped_column(
        ForeignKey("produce_lots.id", ondelete="CASCADE"), nullable=False
    )
    # Null only for the very first entry (lot creation).
    from_status: Mapped[LotStatus | None] = mapped_column(
        sa_enum(LotStatus, "lot_status"), nullable=True
    )
    to_status: Mapped[LotStatus] = mapped_column(
        sa_enum(LotStatus, "lot_status"), nullable=False
    )
    # The farmer who made the move. SET NULL keeps the history if the account
    # is erased for DPDP compliance.
    changed_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    note: Mapped[str | None] = mapped_column(String(300), nullable=True)
    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )

    lot = relationship("ProduceLot", back_populates="history")


__all__ = [
    "ALLOWED_LOT_TRANSITIONS",
    "EDITABLE_LOT_STATUSES",
    "LotStatus",
    "ProduceLot",
    "ProduceLotStatusHistory",
]