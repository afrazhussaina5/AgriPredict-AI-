"""Market price and cache models (Phase 6).

These two tables are the persistent form of the official government daily
market-price resource. Nothing here is verified by default: rows are
`IMPORTED` when the ingestion pipeline first writes them and are only ever
promoted to `VERIFIED` by an explicit verification step that compares a sample
against a second source. The public board therefore reports what the import
pipeline has written, never an opinion about whether that data is true.

Design rules
------------
* Money and quantity are Decimal (not float). A mandi quote is a public
  commitment to a number, and the UI must never display a rounding artefact.
* `grade` may be NULL when the source row carries no grade; the UI renders
  "not graded". Grades A/B/C are stored uppercase exactly as the source ships.
* The unique key is commodity+grade+mandi+district+state+date+unit so that a
  re-import of the same business day is an upsert, never a duplicate.
* A cache blob stores the last successful *extract*, so the freshness endpoint
  can report when the pipeline last touched upstream without a full table scan.
"""

from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Date,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.ext.mutable import MutableDict
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import func

from ..core.database import Base
from .base import TimestampMixin
from .reference import (
    Commodity,
    CommodityGrade,
    District,
    Mandi,
    ReferenceSource,
    State,
    Unit,
)


class MarketPrice(Base, TimestampMixin):
    """One row per official daily price observation per commodity+grade+mandi."""

    __tablename__ = "market_prices"
    __table_args__ = (
        UniqueConstraint(
            "commodity_id",
            "grade_id",
            "mandi_id",
            "district_id",
            "state_id",
            "market_date",
            "unit_id",
            name="uq_market_prices_key",
        ),
        CheckConstraint(
            "modal_price IS NULL OR modal_price >= 0",
            name="ck_market_prices_non_negative",
        ),
        Index("ix_market_prices_state", "state_id", "market_date"),
        Index("ix_market_prices_mandi", "mandi_id", "market_date"),
        Index("ix_market_prices_date", "market_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    commodity_id: Mapped[int] = mapped_column(
        ForeignKey("reference_commodities.id", ondelete="RESTRICT"),
        nullable=False,
    )
    grade_id: Mapped[int | None] = mapped_column(
        ForeignKey("reference_commodity_grades.id", ondelete="RESTRICT"),
        nullable=True,
    )
    mandi_id: Mapped[int] = mapped_column(
        ForeignKey("reference_mandis.id", ondelete="RESTRICT"),
        nullable=False,
    )
    district_id: Mapped[int] = mapped_column(
        ForeignKey("reference_districts.id", ondelete="RESTRICT"),
        nullable=False,
    )
    state_id: Mapped[int] = mapped_column(
        ForeignKey("reference_states.id", ondelete="RESTRICT"),
        nullable=False,
    )
    unit_id: Mapped[int] = mapped_column(
        ForeignKey("reference_units.id", ondelete="RESTRICT"),
        nullable=False,
    )
    market_date: Mapped[date] = mapped_column(
        "market_date", Date, nullable=False, index=True
    )
    modal_price: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    arrivals: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_id: Mapped[int] = mapped_column(
        ForeignKey("reference_sources.id", ondelete="RESTRICT"),
        nullable=False,
    )
    imported_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    cache_key: Mapped[str | None] = mapped_column(String(80), nullable=True)

    commodity: Mapped[Commodity] = relationship(lazy="joined")
    grade: Mapped[CommodityGrade | None] = relationship(lazy="joined")
    mandi: Mapped[Mandi] = relationship(lazy="joined")
    district: Mapped[District] = relationship(lazy="joined")
    state: Mapped[State] = relationship(lazy="joined")
    unit: Mapped[Unit] = relationship(lazy="joined")
    source: Mapped[ReferenceSource] = relationship(lazy="joined")


class MarketPriceCache(Base, TimestampMixin):
    """Metadata blob for the last successful extract, so freshness is cheap."""

    __tablename__ = "market_price_cache"
    __table_args__ = (UniqueConstraint("key", name="uq_market_price_cache_key"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    key: Mapped[str] = mapped_column(String(80), nullable=False)
    value: Mapped[dict[str, Any]] = mapped_column(
        MutableDict.as_mutable(String(1000)), nullable=False
    )
