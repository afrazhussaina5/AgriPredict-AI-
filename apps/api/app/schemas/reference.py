"""Schemas for reference data (Phase 5).

Read models always carry provenance: ``source_key`` and ``source_name`` travel
with the data so a screen can show where a place name came from.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from ..models import LocalityKind, UnitDimension, VerificationStatus


class ReferenceSourceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    source_key: str
    name: str
    url: str | None = None
    publisher: str | None = None
    is_official: bool
    license_notes: str | None = None
    status: VerificationStatus
    last_imported_at: datetime | None = None
    notes: str | None = None


class _ReferenceBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    name_hi: str | None = None
    name_te: str | None = None
    status: VerificationStatus = VerificationStatus.IMPORTED
    is_active: bool = True
    source_key: str
    source_name: str
    source_is_official: bool = False
    imported_at: datetime | None = None


class StateOut(_ReferenceBase):
    code: str


class DistrictOut(_ReferenceBase):
    code: str
    state_id: int


class LocalityOut(_ReferenceBase):
    kind: LocalityKind
    district_id: int
    # Present only when the source supplied coordinates. Never a road distance.
    latitude: float | None = None
    longitude: float | None = None


class MandiOut(_ReferenceBase):
    code: str
    district_id: int
    state_id: int
    has_storage: bool | None = None


class CommodityOut(_ReferenceBase):
    code: str
    category: str | None = None


class VarietyOut(_ReferenceBase):
    code: str
    commodity_id: int


class GradeOut(_ReferenceBase):
    code: str
    commodity_id: int | None = None


class UnitOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    name: str
    name_hi: str | None = None
    name_te: str | None = None
    dimension: UnitDimension
    to_base_kg: float | None = None
    source_key: str
    source_name: str
    status: VerificationStatus = VerificationStatus.IMPORTED


class ReferenceCounts(BaseModel):
    states: int = 0
    districts: int = 0
    localities: int = 0
    mandis: int = 0
    commodities: int = 0
    varieties: int = 0
    grades: int = 0
    units: int = 0


class ReferenceStatus(BaseModel):
    """What reference data actually exists right now.

    The frontend uses ``is_populated`` to show an honest "not loaded yet" state
    instead of an empty dropdown that looks broken.
    """

    is_populated: bool
    counts: ReferenceCounts
    sources: list[ReferenceSourceOut] = Field(default_factory=list)
    # Earliest source import date, or null when nothing has been imported.
    oldest_import_at: datetime | None = None
    newest_import_at: datetime | None = None
    note: str = (
        "Reference data is empty until an admin imports a verified dataset "
        "and records its source. No official directory is bundled."
    )


class ImportResult(BaseModel):
    """Outcome of one import run, including what was rejected."""

    entity_type: str
    dry_run: bool
    row_count: int
    inserted_count: int
    updated_count: int
    skipped_count: int
    rejected_count: int
    rejection_reasons: list[str] = Field(default_factory=list)