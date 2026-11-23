"""Market price and cache models (Phase 6).

These two tables are the persistent form of the official government daily
market-price resource. Nothing here is verified by default: rows are
`IMPORTED` when the ingestion pipeline first writes them and are only ever
promoted to `VERIFIED` by an explicit verification step that compares a
sample against a second source. The public board therefore reports what the
ingestion pipeline has written, never an opinion about whether that data is
true.

Design rules
------------
* Money and quantity are Decimal (not float). A mandi quote is a public
  commitment to a number, and the UI must never display a rounding artefact.
* `grade` may be NULL when the source row carries no grade; the UI renders
  "not graded". Grades A/B/C are stored uppercase exactly as the source ships.
* The unique key is commodity+grade+mandi+district+state+date+unit so that a
  re-import of the same business day is an upsert, never a duplicate.
* A cache blob stores the last successful *extract*, so the freshness
  endpoint can report when the pipeline last touched upstream without a full
  table scan.
"""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import func

from ..core.database import Base
from .base import TimestampMixin


class MarketPrice(Base, TimestampMixin):
    """One row per official daily price observation per commodity+grade+mandi.

    The phase-6 maps share the package ``Base`` with the phase-3 reference
    maps, so nothing in this module declares a second ``Base``. The unique
    constraint names are pre-fitted with the ``market_prices`` prefix so
    Alembic autogenerate does not collide with the reference module's
    ``reference_...`` names.
    """

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
        ForeignKey("reference_commodities.id", ondelete="RESTRICT"), nullable=False
    )
    grade_id: Mapped[int | None] = mapped_column(
        ForeignKey("reference_commodity_grades.id", ondelete="RESTRICT"), nullable=True
    )
    mandi_id: Mapped[int] = mapped_column(
        ForeignKey("reference_mandis.id", ondelete="RESTRICT"), nullable=False
    )
    district_id: Mapped[int] = mapped_column(
        ForeignKey("reference_districts.id", ondelete="RESTRICT"), nullable=False
    )
    state_id: Mapped[int] = mapped_column(
        ForeignKey("reference_states.id", ondelete="RESTRICT"), nullable=False
    )
    unit_id: Mapped[int] = mapped_column(
        ForeignKey("reference_units.id", ondelete="RESTRICT"), nullable=False
    )
    market_date: Mapped[date] = mapped_column("market_date", Date, nullable=False)
    modal_price: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    arrivals: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_id: Mapped[int] = mapped_column(
        ForeignKey("reference_sources.id", ondelete="RESTRICT"), nullable=False
    )
    imported_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    cache_key: Mapped[str | None] = mapped_column(String(80), nullable=True)

    commodity = relationship("Commodity", lazy="joined", back_populates="market_prices")
    grade = relationship("CommodityGrade", lazy="joined")
    mandi = relationship("Mandi", lazy="joined", back_populates="market_prices")
    district = relationship("District", lazy="joined")
    state = relationship("State", lazy="joined")
    unit = relationship("MeasurementUnit", lazy="joined", back_populates="market_prices")
    source = relationship("ReferenceSource", lazy="joined")


class MarketPriceCache(Base, TimestampMixin):
    """Metadata blob for the last successful extract, so freshness is cheap."""

    __tablename__ = "market_price_cache"
    __table_args__ = (UniqueConstraint("key", name="uq_market_price_cache_key"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    key: Mapped[str] = mapped_column(String(80), nullable=False)
    # A JSON document serialised as text: the last extract's metadata (fetch
    # time, row sample, errors). Stored as text rather than a JSON column so
    # the same row reads identically on SQLite (tests) and PostgreSQL.
    value: Mapped[str] = mapped_column(Text, nullable=False)
