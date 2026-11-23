"""Reference data models (Phase 3/5).

Every table in this module is a *reference entity*: a stable, source-stamped
value (State, District, Locality, Mandi, Commodity, Variety, Grade, Unit) that
the public board, the reference API and the import pipeline consume together.
Nothing here is a price observation: prices live in :mod:`app.models.market`.

The column set, constraint names and enum types mirror alembic migration
``0003_reference`` exactly, because the ORM runs against a schema that
migration created - a column the model declares but the database lacks makes
every INSERT fail on PostgreSQL.

Design rules enforced here rather than by convention:

* Every row carries ``source_id``: no reference value exists without a
  recorded provenance, so the UI can always say where a name came from.
* ``status`` defaults to ``imported`` - nothing becomes ``verified``
  automatically. Verification is an explicit, audited act.
* ``is_active`` defaults to True; deactivation (not deletion) is how bad data
  is retired, so historical lots keep resolving their labels.
* Money and quantity are Decimal, never float, wherever they appear.
"""
from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import TYPE_CHECKING

from .base import TimestampMixin, sa_enum
from ..core.database import Base

if TYPE_CHECKING:  # Imported for typing only; avoids a circular import at runtime.
    from .identity import User
    from .market import MarketPrice


class VerificationStatus(StrEnum):
    """Lifecycle of a reference row, from import to human verification.

    ``disputed`` and ``retired`` exist so bad data can be walked back without
    being deleted - the row keeps resolving, but the UI says why it is not
    trusted any more.
    """

    IMPORTED = "imported"
    VERIFIED = "verified"
    DISPUTED = "disputed"
    RETIRED = "retired"


class LocalityKind(StrEnum):
    """Admissible locality kinds shipped by the reference importers."""

    CITY = "city"
    TOWN = "town"
    VILLAGE = "village"


class UnitDimension(StrEnum):
    """Dimension of a measurement unit. Mass units carry a to_base_kg factor."""

    MASS = "mass"
    VOLUME = "volume"
    COUNT = "count"
    BAG = "bag"


class ReferenceSource(Base, TimestampMixin):
    """One import source that stamped the reference rows it wrote."""

    __tablename__ = "reference_sources"
    __table_args__ = (
        UniqueConstraint("source_key", name="uq_reference_sources_key"),
        CheckConstraint("length(trim(source_key)) > 0", name="ck_reference_sources_key"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_key: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    publisher: Mapped[str | None] = mapped_column(String(200), nullable=True)
    is_official: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=func.false()
    )
    license_notes: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status: Mapped[VerificationStatus] = mapped_column(
        sa_enum(VerificationStatus, "verification_status"),
        nullable=False,
        default=VerificationStatus.IMPORTED,
        server_default="imported",
    )
    last_imported_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    notes: Mapped[str | None] = mapped_column(String(500), nullable=True)

    states: Mapped[list[State]] = relationship(
        back_populates="source", cascade="all, delete-orphan"
    )
    districts: Mapped[list[District]] = relationship(
        back_populates="source", cascade="all, delete-orphan"
    )
    localities: Mapped[list[Locality]] = relationship(
        back_populates="source", cascade="all, delete-orphan"
    )
    mandis: Mapped[list[Mandi]] = relationship(
        back_populates="source", cascade="all, delete-orphan"
    )
    commodities: Mapped[list[Commodity]] = relationship(
        back_populates="source", cascade="all, delete-orphan"
    )
    commodity_varieties: Mapped[list[CommodityVariety]] = relationship(
        back_populates="source", cascade="all, delete-orphan"
    )
    commodity_grades: Mapped[list[CommodityGrade]] = relationship(
        back_populates="source", cascade="all, delete-orphan"
    )
    units: Mapped[list[MeasurementUnit]] = relationship(
        back_populates="source", cascade="all, delete-orphan"
    )
    reference_import_logs: Mapped[list[ReferenceImportLog]] = relationship(
        back_populates="source", cascade="all, delete-orphan"
    )


class State(Base, TimestampMixin):
    """One Indian state, the root of the reference hierarchy."""

    __tablename__ = "reference_states"
    __table_args__ = (
        UniqueConstraint("code", name="uq_reference_states_code"),
        Index("ix_reference_states_status", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(8), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    name_hi: Mapped[str | None] = mapped_column(String(200), nullable=True)
    name_te: Mapped[str | None] = mapped_column(String(200), nullable=True)
    source_id: Mapped[int] = mapped_column(
        ForeignKey("reference_sources.id", ondelete="RESTRICT"), nullable=False
    )
    status: Mapped[VerificationStatus] = mapped_column(
        sa_enum(VerificationStatus, "verification_status"),
        nullable=False,
        default=VerificationStatus.IMPORTED,
        server_default="imported",
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=func.true()
    )

    districts: Mapped[list[District]] = relationship(
        back_populates="state", cascade="all, delete-orphan"
    )
    source: Mapped[ReferenceSource] = relationship(back_populates="states")


class District(Base, TimestampMixin):
    """One administrative district, scoped to a single state."""

    __tablename__ = "reference_districts"
    __table_args__ = (
        UniqueConstraint("state_id", "code", name="uq_reference_districts_state_code"),
        Index("ix_reference_districts_state", "state_id", "is_active"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    state_id: Mapped[int] = mapped_column(
        ForeignKey("reference_states.id", ondelete="CASCADE"), nullable=False, index=True
    )
    code: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    name_hi: Mapped[str | None] = mapped_column(String(200), nullable=True)
    name_te: Mapped[str | None] = mapped_column(String(200), nullable=True)
    source_id: Mapped[int] = mapped_column(
        ForeignKey("reference_sources.id", ondelete="RESTRICT"), nullable=False
    )
    status: Mapped[VerificationStatus] = mapped_column(
        sa_enum(VerificationStatus, "verification_status"),
        nullable=False,
        default=VerificationStatus.IMPORTED,
        server_default="imported",
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=func.true()
    )

    state: Mapped[State] = relationship(back_populates="districts", lazy="joined")
    mandis: Mapped[list[Mandi]] = relationship(
        back_populates="district", cascade="all, delete-orphan"
    )
    localities: Mapped[list[Locality]] = relationship(
        back_populates="district", cascade="all, delete-orphan"
    )
    source: Mapped[ReferenceSource] = relationship(back_populates="districts")


class Locality(Base, TimestampMixin):
    """A geo-place inside one district, addressable by kind."""

    __tablename__ = "reference_localities"
    __table_args__ = (
        UniqueConstraint("district_id", "kind", "name", name="uq_reference_localities_name"),
        Index("ix_reference_localities_district", "district_id", "is_active"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    district_id: Mapped[int] = mapped_column(
        ForeignKey("reference_districts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    kind: Mapped[LocalityKind] = mapped_column(
        sa_enum(LocalityKind, "locality_kind"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    name_hi: Mapped[str | None] = mapped_column(String(200), nullable=True)
    name_te: Mapped[str | None] = mapped_column(String(200), nullable=True)
    latitude: Mapped[float | None] = mapped_column(Numeric(9, 6), nullable=True)
    longitude: Mapped[float | None] = mapped_column(Numeric(9, 6), nullable=True)
    source_id: Mapped[int] = mapped_column(
        ForeignKey("reference_sources.id", ondelete="RESTRICT"), nullable=False
    )
    status: Mapped[VerificationStatus] = mapped_column(
        sa_enum(VerificationStatus, "verification_status"),
        nullable=False,
        default=VerificationStatus.IMPORTED,
        server_default="imported",
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=func.true()
    )

    district: Mapped[District] = relationship(back_populates="localities", lazy="joined")
    source: Mapped[ReferenceSource] = relationship(back_populates="localities")


class Mandi(Base, TimestampMixin):
    """One official market where wholesale trade happens."""

    __tablename__ = "reference_mandis"
    __table_args__ = (
        UniqueConstraint("code", name="uq_reference_mandis_code"),
        Index("ix_reference_mandis_district", "district_id", "is_active"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    district_id: Mapped[int] = mapped_column(
        ForeignKey("reference_districts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    code: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    name_hi: Mapped[str | None] = mapped_column(String(200), nullable=True)
    name_te: Mapped[str | None] = mapped_column(String(200), nullable=True)
    has_storage: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    source_id: Mapped[int] = mapped_column(
        ForeignKey("reference_sources.id", ondelete="RESTRICT"), nullable=False
    )
    status: Mapped[VerificationStatus] = mapped_column(
        sa_enum(VerificationStatus, "verification_status"),
        nullable=False,
        default=VerificationStatus.IMPORTED,
        server_default="imported",
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=func.true()
    )

    district: Mapped[District] = relationship(back_populates="mandis", lazy="joined")
    source: Mapped[ReferenceSource] = relationship(back_populates="mandis")
    market_prices: Mapped[list[MarketPrice]] = relationship(
        back_populates="mandi", cascade="all, delete-orphan"
    )


class Commodity(Base, TimestampMixin):
    """One tradeable commodity (COT, TOMATO, ONION, ...).

    The public board is commodity-centric, so this is the widest entity and
    the one most importers seed.
    """

    __tablename__ = "reference_commodities"
    __table_args__ = (
        UniqueConstraint("code", name="uq_reference_commodities_code"),
        Index("ix_reference_commodities_status", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    name_hi: Mapped[str | None] = mapped_column(String(200), nullable=True)
    name_te: Mapped[str | None] = mapped_column(String(200), nullable=True)
    category: Mapped[str | None] = mapped_column(String(80), nullable=True)
    source_id: Mapped[int] = mapped_column(
        ForeignKey("reference_sources.id", ondelete="RESTRICT"), nullable=False
    )
    status: Mapped[VerificationStatus] = mapped_column(
        sa_enum(VerificationStatus, "verification_status"),
        nullable=False,
        default=VerificationStatus.IMPORTED,
        server_default="imported",
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=func.true()
    )

    varieties: Mapped[list[CommodityVariety]] = relationship(
        back_populates="commodity", cascade="all, delete-orphan"
    )
    grades: Mapped[list[CommodityGrade]] = relationship(
        back_populates="commodity", cascade="all, delete-orphan"
    )
    market_prices: Mapped[list[MarketPrice]] = relationship(
        back_populates="commodity", cascade="all, delete-orphan"
    )
    source: Mapped[ReferenceSource] = relationship(back_populates="commodities")


class CommodityVariety(Base, TimestampMixin):
    """A named variety of one commodity (e.g. BOMI over COT)."""

    __tablename__ = "reference_commodity_varieties"
    __table_args__ = (
        UniqueConstraint(
            "commodity_id", "code", name="uq_reference_varieties_commodity_code"
        ),
        Index(
            "ix_reference_varieties_commodity", "commodity_id", "is_active"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    commodity_id: Mapped[int] = mapped_column(
        ForeignKey("reference_commodities.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    code: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    name_hi: Mapped[str | None] = mapped_column(String(200), nullable=True)
    name_te: Mapped[str | None] = mapped_column(String(200), nullable=True)
    source_id: Mapped[int] = mapped_column(
        ForeignKey("reference_sources.id", ondelete="RESTRICT"), nullable=False
    )
    status: Mapped[VerificationStatus] = mapped_column(
        sa_enum(VerificationStatus, "verification_status"),
        nullable=False,
        default=VerificationStatus.IMPORTED,
        server_default="imported",
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=func.true()
    )

    commodity: Mapped[Commodity] = relationship(back_populates="varieties", lazy="joined")
    source: Mapped[ReferenceSource] = relationship(back_populates="commodity_varieties")


class CommodityGrade(Base, TimestampMixin):
    """A grade a commodity is graded into on the market (A/B/C, or universal)."""

    __tablename__ = "reference_commodity_grades"
    __table_args__ = (
        # A universal grade (commodity_id NULL) is shared by every commodity,
        # so the pair - not the code alone - is the natural key.
        UniqueConstraint(
            "commodity_id", "code", name="uq_reference_grades_commodity_code"
        ),
        Index("ix_reference_grades_commodity", "commodity_id", "is_active"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # Null = commodity-agnostic grade ("A" applies to whatever is being sold).
    commodity_id: Mapped[int | None] = mapped_column(
        ForeignKey("reference_commodities.id", ondelete="CASCADE"), nullable=True, index=True
    )
    code: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    name_hi: Mapped[str | None] = mapped_column(String(200), nullable=True)
    name_te: Mapped[str | None] = mapped_column(String(200), nullable=True)
    source_id: Mapped[int] = mapped_column(
        ForeignKey("reference_sources.id", ondelete="RESTRICT"), nullable=False
    )
    status: Mapped[VerificationStatus] = mapped_column(
        sa_enum(VerificationStatus, "verification_status"),
        nullable=False,
        default=VerificationStatus.IMPORTED,
        server_default="imported",
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=func.true()
    )

    commodity: Mapped[Commodity | None] = relationship(
        back_populates="grades", lazy="joined"
    )
    source: Mapped[ReferenceSource] = relationship(back_populates="commodity_grades")
    market_prices: Mapped[list[MarketPrice]] = relationship(
        back_populates="grade", cascade="all, delete-orphan"
    )


class MeasurementUnit(Base, TimestampMixin):
    """One unit the platform understands (kg, quintal, pcs, ...).

    The class name is singular because ``app.models`` imports it as
    ``MeasurementUnit``; the table is ``reference_units`` because that is what
    migration 0003 created.
    """

    __tablename__ = "reference_units"
    __table_args__ = (
        UniqueConstraint("code", name="uq_reference_units_code"),
        CheckConstraint(
            "dimension <> 'mass' OR to_base_kg IS NOT NULL",
            name="ck_reference_units_mass_requires_conversion",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(24), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    name_hi: Mapped[str | None] = mapped_column(String(80), nullable=True)
    name_te: Mapped[str | None] = mapped_column(String(80), nullable=True)
    dimension: Mapped[UnitDimension] = mapped_column(
        sa_enum(UnitDimension, "unit_dimension"), nullable=False
    )
    # Kilograms represented by one of this unit. NULL for non-mass units.
    to_base_kg: Mapped[float | None] = mapped_column(Numeric(12, 4), nullable=True)
    source_id: Mapped[int] = mapped_column(
        ForeignKey("reference_sources.id", ondelete="RESTRICT"), nullable=False
    )
    status: Mapped[VerificationStatus] = mapped_column(
        sa_enum(VerificationStatus, "verification_status"),
        nullable=False,
        default=VerificationStatus.IMPORTED,
        server_default="imported",
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=func.true()
    )

    market_prices: Mapped[list[MarketPrice]] = relationship(
        back_populates="unit", cascade="all, delete-orphan"
    )
    source: Mapped[ReferenceSource] = relationship(back_populates="units")


class ReferenceImportLog(Base):
    """One row per import run: what it claimed, what it actually did.

    Deliberately not a ``TimestampMixin`` table: migration 0003 gives it a
    single ``imported_at`` stamp and no ``updated_at``, because a finished run
    is immutable - it is re-run, never edited.
    """

    __tablename__ = "reference_import_logs"
    __table_args__ = (
        Index("ix_reference_import_logs_source", "source_id", "imported_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_id: Mapped[int] = mapped_column(
        ForeignKey("reference_sources.id", ondelete="CASCADE"), nullable=False, index=True
    )
    entity_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    filename: Mapped[str | None] = mapped_column(String(300), nullable=True)
    row_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    inserted_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    updated_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    skipped_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    rejected_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    rejection_summary: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    dry_run: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=func.true()
    )
    performed_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    imported_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    source: Mapped[ReferenceSource] = relationship(
        back_populates="reference_import_logs"
    )
    performed_by: Mapped[User | None] = relationship(
        foreign_keys=[performed_by_user_id]
    )


__all__ = [
    "Commodity",
    "CommodityGrade",
    "CommodityVariety",
    "District",
    "Locality",
    "LocalityKind",
    "MeasurementUnit",
    "Mandi",
    "ReferenceImportLog",
    "ReferenceSource",
    "State",
    "UnitDimension",
    "VerificationStatus",
]
