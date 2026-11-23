"""Reference data service (Phase 5).

Two responsibilities:

1. **Read** — cascading State → District → Mandi/Locality lookups plus
   commodities, varieties, grades and units. Every returned row carries its
   source so the UI can show provenance.
2. **Import** — validated, duplicate-aware CSV ingestion. Nothing is invented
   here: the importer only stores rows it was given, always stamped with the
   source the operator declared.

Duplicate handling rules
-----------------------
* A row whose natural key already exists **updates** the existing record
  (idempotent re-import), and is counted as ``updated``.
* A row that is identical to what is stored is counted as ``skipped``.
* A row that cannot be parsed or that references a missing parent is counted as
  ``rejected`` with a reason, and never inserted.

Imports default to ``dry_run=True`` so an operator sees exactly what would
change before anything is written.
"""

import csv
import io
from collections.abc import Sequence
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.logging import get_logger
from ..models import (
    Commodity,
    CommodityGrade,
    CommodityVariety,
    District,
    Locality,
    LocalityKind,
    Mandi,
    MeasurementUnit,
    ReferenceImportLog,
    ReferenceSource,
    State,
    UnitDimension,
    VerificationStatus,
    utcnow,
)

logger = get_logger(__name__)

MAX_ROWS = 50_000
MAX_REPORTED_REASONS = 10


class ImportValidationError(Exception):
    """Raised when the file itself cannot be used (not a per-row problem)."""


@dataclass
class ImportReport:
    entity_type: str
    dry_run: bool = True
    row_count: int = 0
    inserted_count: int = 0
    updated_count: int = 0
    skipped_count: int = 0
    rejected_count: int = 0
    reasons: list[str] = field(default_factory=list)

    def reject(self, reason: str) -> None:
        self.rejected_count += 1
        if len(self.reasons) < MAX_REPORTED_REASONS and reason not in self.reasons:
            self.reasons.append(reason)


# --------------------------------------------------------------------- helpers


def _clean(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _parse_decimal(value: Any) -> Decimal | None:
    text = _clean(value)
    if text is None:
        return None
    try:
        return Decimal(text)
    except InvalidOperation as exc:
        raise ImportValidationError(f"'{text}' is not a number") from exc


def _provenance_columns() -> tuple[Any, ...]:
    """Columns joined onto every read so responses carry their source."""
    return (
        ReferenceSource.source_key.label("source_key"),
        ReferenceSource.name.label("source_name"),
        ReferenceSource.is_official.label("source_is_official"),
    )


_SOURCE_LABELS = ("source_key", "source_name", "source_is_official")


def _decorate(rows: Sequence[Any], model: Any) -> list[dict[str, Any]]:
    """Flatten a result row into a plain dict.

    SQLAlchemy keys the selected ORM entity by its class name, so the entity's
    own columns have to be unpacked explicitly and merged with the labelled
    provenance columns.
    """
    from sqlalchemy import inspect as sa_inspect

    if not rows:
        return []
    column_keys = [attr.key for attr in sa_inspect(model).mapper.column_attrs]
    entity_key = model.__name__

    output: list[dict[str, Any]] = []
    for row in rows:
        mapping = row._mapping
        entity = mapping[entity_key]
        data: dict[str, Any] = {key: getattr(entity, key) for key in column_keys}
        for label in _SOURCE_LABELS:
            if label in mapping:
                data[label] = mapping[label]
        # Optional joined column (used by the mandi query to surface the state).
        if "state_id" in mapping and "state_id" not in data:
            data["state_id"] = mapping["state_id"]
        # `imported_at` is the row's own creation time, which is when it landed.
        data.setdefault("imported_at", getattr(entity, "created_at", None))
        output.append(data)
    return output


class ReferenceService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ------------------------------------------------------------------ reads

    async def list_states(self, *, active_only: bool = True) -> list[dict[str, Any]]:
        stmt = (
            select(State, *_provenance_columns())
            .join(ReferenceSource, State.source_id == ReferenceSource.id)
            .order_by(State.name)
        )
        if active_only:
            stmt = stmt.where(State.is_active.is_(True))
        return _decorate((await self.session.execute(stmt)).all(), State)

    async def list_districts(
        self, state_id: int, *, active_only: bool = True
    ) -> list[dict[str, Any]]:
        stmt = (
            select(District, *_provenance_columns())
            .join(ReferenceSource, District.source_id == ReferenceSource.id)
            .where(District.state_id == state_id)
            .order_by(District.name)
        )
        if active_only:
            stmt = stmt.where(District.is_active.is_(True))
        return _decorate((await self.session.execute(stmt)).all(), District)

    async def list_localities(
        self, district_id: int, *, active_only: bool = True
    ) -> list[dict[str, Any]]:
        stmt = (
            select(Locality, *_provenance_columns())
            .join(ReferenceSource, Locality.source_id == ReferenceSource.id)
            .where(Locality.district_id == district_id)
            .order_by(Locality.name)
        )
        if active_only:
            stmt = stmt.where(Locality.is_active.is_(True))
        return _decorate((await self.session.execute(stmt)).all(), Locality)

    async def list_mandis(
        self,
        *,
        district_id: int | None = None,
        active_only: bool = True,
    ) -> list[dict[str, Any]]:
        stmt = (
            select(Mandi, District.state_id, *_provenance_columns())
            .join(ReferenceSource, Mandi.source_id == ReferenceSource.id)
            .join(District, Mandi.district_id == District.id)
            .order_by(Mandi.name)
        )
        if district_id is not None:
            stmt = stmt.where(Mandi.district_id == district_id)
        if active_only:
            stmt = stmt.where(Mandi.is_active.is_(True))
        return _decorate((await self.session.execute(stmt)).all(), Mandi)

    async def list_commodities(self, *, active_only: bool = True) -> list[dict[str, Any]]:
        stmt = (
            select(Commodity, *_provenance_columns())
            .join(ReferenceSource, Commodity.source_id == ReferenceSource.id)
            .order_by(Commodity.name)
        )
        if active_only:
            stmt = stmt.where(Commodity.is_active.is_(True))
        return _decorate((await self.session.execute(stmt)).all(), Commodity)

    async def list_varieties(self, commodity_id: int) -> list[dict[str, Any]]:
        stmt = (
            select(CommodityVariety, *_provenance_columns())
            .join(
                ReferenceSource, CommodityVariety.source_id == ReferenceSource.id
            )
            .where(
                CommodityVariety.commodity_id == commodity_id,
                CommodityVariety.is_active.is_(True),
            )
            .order_by(CommodityVariety.name)
        )
        return _decorate((await self.session.execute(stmt)).all(), CommodityVariety)

    async def list_grades(self, commodity_id: int | None) -> list[dict[str, Any]]:
        """Grades for one commodity plus the commodity-agnostic ones."""
        conditions: list[Any] = [CommodityGrade.is_active.is_(True)]
        if commodity_id is not None:
            conditions.append(
                (CommodityGrade.commodity_id == commodity_id)
                | (CommodityGrade.commodity_id.is_(None))
            )
        else:
            conditions.append(CommodityGrade.commodity_id.is_(None))
        stmt = (
            select(CommodityGrade, *_provenance_columns())
            .join(ReferenceSource, CommodityGrade.source_id == ReferenceSource.id)
            .where(*conditions)
            .order_by(CommodityGrade.name)
        )
        return _decorate((await self.session.execute(stmt)).all(), CommodityGrade)

    async def list_units(self) -> list[dict[str, Any]]:
        stmt = (
            select(MeasurementUnit, *_provenance_columns())
            .join(ReferenceSource, MeasurementUnit.source_id == ReferenceSource.id)
            .where(MeasurementUnit.is_active.is_(True))
            .order_by(MeasurementUnit.dimension, MeasurementUnit.code)
        )
        return _decorate((await self.session.execute(stmt)).all(), MeasurementUnit)

    async def list_sources(self) -> list[ReferenceSource]:
        result = await self.session.execute(
            select(ReferenceSource).order_by(ReferenceSource.name)
        )
        return list(result.scalars().all())

    async def counts(self) -> dict[str, int]:
        async def _count(model: Any) -> int:
            result = await self.session.execute(
                select(func.count()).select_from(model).where(model.is_active.is_(True))
            )
            return int(result.scalar_one())

        return {
            "states": await _count(State),
            "districts": await _count(District),
            "localities": await _count(Locality),
            "mandis": await _count(Mandi),
            "commodities": await _count(Commodity),
            "varieties": await _count(CommodityVariety),
            "grades": await _count(CommodityGrade),
            "units": await _count(MeasurementUnit),
        }

    async def import_dates(self) -> tuple[Any, Any]:
        result = await self.session.execute(
            select(func.min(ReferenceSource.last_imported_at), func.max(
                ReferenceSource.last_imported_at
            ))
        )
        row = result.one()
        return (row[0], row[1])

    # ----------------------------------------------------------------- imports

    async def ensure_source(
        self,
        source_key: str,
        name: str,
        *,
        url: str | None = None,
        publisher: str | None = None,
        is_official: bool = False,
        license_notes: str | None = None,
    ) -> tuple[ReferenceSource, bool]:
        """Return ``(source, created)``. Create if missing, touch fields otherwise."""
        result = await self.session.execute(
            select(ReferenceSource).where(ReferenceSource.source_key == source_key)
        )
        source = result.scalar_one_or_none()
        created = source is None
        if source is None:
            source = ReferenceSource(source_key=source_key, name=name)
            self.session.add(source)
        source.name = name
        source.url = url
        source.publisher = publisher
        source.is_official = is_official
        source.license_notes = license_notes
        self.session.add(source)
        await self.session.flush()
        return source, created

    async def _resolve_parent_id(self, model: Any, column: Any, value: str) -> int | None:
        result = await self.session.execute(
            select(model.id).where(column == value).limit(1)
        )
        return result.scalar_one_or_none()

    async def import_rows(
        self,
        entity_type: str,
        csv_text: str,
        source: ReferenceSource,
        *,
        dry_run: bool = True,
        performed_by_user_id: int | None = None,
        filename: str | None = None,
    ) -> ImportReport:
        """Validate and (optionally) apply a CSV import."""
        if entity_type not in SUPPORTED_ENTITIES:
            raise ImportValidationError(f"Unknown entity type '{entity_type}'.")

        reader = csv.DictReader(io.StringIO(csv_text))
        if reader.fieldnames is None:
            raise ImportValidationError("The file has no header row.")

        report = ImportReport(entity_type=entity_type, dry_run=dry_run)
        rows = list(reader)
        if len(rows) > MAX_ROWS:
            raise ImportValidationError(
                f"Refusing to import more than {MAX_ROWS} rows in one file."
            )

        # The whole file runs in ONE transaction. Savepoints are deliberately
        # NOT used: with the pysqlite/aiosqlite driver "RELEASE SAVEPOINT" acts
        # as a COMMIT, which would make a dry run permanently write rows.
        # Row-level isolation comes from validating and de-duplicating in Python
        # before anything is written, so a bad row never reaches the database.
        if not self.session.in_transaction():
            self.session.begin()

        # Captured up front: a rollback expires every ORM object, and touching
        # source.id afterwards would trigger an async lazy-load that fails.
        source_id = source.id
        seen_keys: set[str] = set()

        # Persist the source BEFORE any row is written. A caller may have
        # created it earlier in this same transaction (the admin API does
        # exactly that, with no commit in between). The dry-run branch below
        # rolls the transaction back, which would discard that source and leave
        # the reference_import_logs row pointing at a source that no longer
        # exists - a foreign-key violation that PostgreSQL rejects outright.
        # Committing here persists the source and nothing else, because no
        # imported row has been written yet.
        await self.session.commit()

        handler = SUPPORTED_ENTITIES[entity_type]
        for index, row in enumerate(rows, start=2):  # row 1 is the header
            report.row_count += 1
            try:
                outcome = await handler(self, row, source, seen_keys)
            except ImportValidationError as exc:
                report.reject(f"row {index}: {exc}")
                continue
            except Exception as exc:  # noqa: BLE001 - one bad row must not stop the file
                logger.warning(
                    "Reference import row %s failed: %s", index, type(exc).__name__
                )
                report.reject(f"row {index}: unexpected {type(exc).__name__}")
                continue
            if outcome == "inserted":
                report.inserted_count += 1
            elif outcome == "updated":
                report.updated_count += 1
            else:
                report.skipped_count += 1

        if dry_run:
            # Discard every row change, then record the dry run itself so the
            # attempt is still auditable.
            await self.session.rollback()
            self.session.add(
                self._build_log(report, source_id, performed_by_user_id, filename)
            )
            await self.session.commit()
        else:
            try:
                await self.session.flush()
            except IntegrityError as exc:
                # Nothing is imported if any row breaks a database constraint.
                # Reference data is all-or-nothing on purpose.
                await self.session.rollback()
                detail = str(getattr(exc, "orig", exc)).splitlines()[0][:200]
                raise ImportValidationError(
                    "a row violated a database constraint, so nothing was "
                    f"imported: {detail}"
                ) from exc
            self.session.add(
                self._build_log(report, source_id, performed_by_user_id, filename)
            )
            source.last_imported_at = utcnow()
            self.session.add(source)
            await self.session.commit()
        return report

    def _build_log(
        self,
        report: ImportReport,
        source_id: int,
        performed_by_user_id: int | None,
        filename: str | None,
    ) -> ReferenceImportLog:
        return ReferenceImportLog(
            source_id=source_id,
            entity_type=report.entity_type,
            filename=filename,
            row_count=report.row_count,
            inserted_count=report.inserted_count,
            updated_count=report.updated_count,
            skipped_count=report.skipped_count,
            rejected_count=report.rejected_count,
            rejection_summary=", ".join(report.reasons)[:1000] or None,
            dry_run=report.dry_run,
            performed_by_user_id=performed_by_user_id,
        )


# --------------------------------------------------------------- row handlers


def _reject_duplicate(seen: set[str], key: str) -> None:
    """Refuse a natural key that already appeared in this file.

    Duplicate detection happens in Python rather than relying on a database
    constraint, so a repeated row is rejected cleanly instead of aborting the
    whole file.
    """
    if key in seen:
        raise ImportValidationError(f"duplicate row for {key} in this file")
    seen.add(key)


def _apply(model_instance: Any, values: dict[str, Any]) -> str:
    """Apply ``values`` to an instance and classify the change."""
    changed = False
    for field_name, value in values.items():
        current = getattr(model_instance, field_name)
        if current != value:
            setattr(model_instance, field_name, value)
            changed = True
    return "updated" if changed else "skipped"


async def _handle_state(
    service: ReferenceService,
    row: dict[str, Any],
    source: ReferenceSource,
    seen: set[str],
) -> str:
    code = _clean(row.get("code"))
    name = _clean(row.get("name"))
    if not code or not name:
        raise ImportValidationError("'code' and 'name' are required")
    _reject_duplicate(seen, f"state:{code}")
    result = await service.session.execute(select(State).where(State.code == code))
    instance = result.scalar_one_or_none()
    values = {
        "name": name,
        "name_hi": _clean(row.get("name_hi")),
        "name_te": _clean(row.get("name_te")),
        "source_id": source.id,
    }
    if instance is None:
        service.session.add(State(code=code, **values))
        await service.session.flush()
        return "inserted"
    return _apply(instance, values)


async def _handle_district(
    service: ReferenceService,
    row: dict[str, Any],
    source: ReferenceSource,
    seen: set[str],
) -> str:
    state_code = _clean(row.get("state_code"))
    code = _clean(row.get("code"))
    name = _clean(row.get("name"))
    if not state_code or not code or not name:
        raise ImportValidationError("'state_code', 'code' and 'name' are required")
    state_id = await service._resolve_parent_id(State, State.code, state_code)
    if state_id is None:
        raise ImportValidationError(f"unknown state_code '{state_code}'")
    _reject_duplicate(seen, f"district:{state_id}:{code}")
    result = await service.session.execute(
        select(District).where(
            District.state_id == state_id, District.code == code
        )
    )
    instance = result.scalar_one_or_none()
    values = {
        "name": name,
        "name_hi": _clean(row.get("name_hi")),
        "name_te": _clean(row.get("name_te")),
        "source_id": source.id,
    }
    if instance is None:
        service.session.add(District(state_id=state_id, code=code, **values))
        await service.session.flush()
        return "inserted"
    return _apply(instance, values)


async def _handle_mandi(
    service: ReferenceService,
    row: dict[str, Any],
    source: ReferenceSource,
    seen: set[str],
) -> str:
    district_code = _clean(row.get("district_code"))
    code = _clean(row.get("code"))
    name = _clean(row.get("name"))
    if not district_code or not code or not name:
        raise ImportValidationError("'district_code', 'code' and 'name' are required")
    result = await service.session.execute(
        select(District, State.code)
        .join(State, District.state_id == State.id)
        .where(District.code == district_code)
        .limit(1)
    )
    pair = result.first()
    if pair is None:
        raise ImportValidationError(f"unknown district_code '{district_code}'")
    _reject_duplicate(seen, f"mandi:{code}")
    district: District = pair[0]
    mandi_result = await service.session.execute(select(Mandi).where(Mandi.code == code))
    instance = mandi_result.scalar_one_or_none()
    has_storage = _clean(row.get("has_storage"))
    storage_flag: bool | None = {"true": True, "false": False}.get(
        (has_storage or "").lower()
    )
    values = {
        "name": name,
        "name_hi": _clean(row.get("name_hi")),
        "name_te": _clean(row.get("name_te")),
        "has_storage": storage_flag,
        "source_id": source.id,
    }
    if instance is None:
        service.session.add(Mandi(district_id=district.id, code=code, **values))
        await service.session.flush()
        return "inserted"
    return _apply(instance, values)


async def _handle_locality(
    service: ReferenceService,
    row: dict[str, Any],
    source: ReferenceSource,
    seen: set[str],
) -> str:
    district_code = _clean(row.get("district_code"))
    name = _clean(row.get("name"))
    kind_text = (_clean(row.get("kind")) or "").lower()
    if not district_code or not name or kind_text not in set(LocalityKind):
        raise ImportValidationError(
            "'district_code', 'name' and a valid 'kind' (city/town/village) are required"
        )
    district_id = await service._resolve_parent_id(District, District.code, district_code)
    if district_id is None:
        raise ImportValidationError(f"unknown district_code '{district_code}'")
    _reject_duplicate(seen, f"locality:{district_id}:{kind_text}:{name}")
    kind = LocalityKind(kind_text)
    result = await service.session.execute(
        select(Locality).where(
            Locality.district_id == district_id,
            Locality.kind == kind,
            Locality.name == name,
        )
    )
    instance = result.scalar_one_or_none()
    latitude = _parse_decimal(row.get("latitude"))
    longitude = _parse_decimal(row.get("longitude"))
    if latitude is not None and not (-90 <= latitude <= 90):
        raise ImportValidationError("'latitude' must be between -90 and 90")
    if longitude is not None and not (-180 <= longitude <= 180):
        raise ImportValidationError("'longitude' must be between -180 and 180")
    values = {
        "name_hi": _clean(row.get("name_hi")),
        "name_te": _clean(row.get("name_te")),
        "latitude": latitude,
        "longitude": longitude,
        "source_id": source.id,
    }
    if instance is None:
        service.session.add(
            Locality(district_id=district_id, kind=kind, name=name, **values)
        )
        await service.session.flush()
        return "inserted"
    return _apply(instance, values)


async def _handle_commodity(
    service: ReferenceService,
    row: dict[str, Any],
    source: ReferenceSource,
    seen: set[str],
) -> str:
    code = _clean(row.get("code"))
    name = _clean(row.get("name"))
    if not code or not name:
        raise ImportValidationError("'code' and 'name' are required")
    _reject_duplicate(seen, f"commodity:{code}")
    result = await service.session.execute(
        select(Commodity).where(Commodity.code == code)
    )
    instance = result.scalar_one_or_none()
    values = {
        "name": name,
        "name_hi": _clean(row.get("name_hi")),
        "name_te": _clean(row.get("name_te")),
        "category": _clean(row.get("category")),
        "source_id": source.id,
    }
    if instance is None:
        service.session.add(Commodity(code=code, **values))
        await service.session.flush()
        return "inserted"
    return _apply(instance, values)


async def _handle_variety(
    service: ReferenceService,
    row: dict[str, Any],
    source: ReferenceSource,
    seen: set[str],
) -> str:
    commodity_code = _clean(row.get("commodity_code"))
    code = _clean(row.get("code"))
    name = _clean(row.get("name"))
    if not commodity_code or not code or not name:
        raise ImportValidationError("'commodity_code', 'code' and 'name' are required")
    commodity_id = await service._resolve_parent_id(Commodity, Commodity.code, commodity_code)
    if commodity_id is None:
        raise ImportValidationError(f"unknown commodity_code '{commodity_code}'")
    _reject_duplicate(seen, f"variety:{commodity_id}:{code}")
    result = await service.session.execute(
        select(CommodityVariety).where(
            CommodityVariety.commodity_id == commodity_id, CommodityVariety.code == code
        )
    )
    instance = result.scalar_one_or_none()
    values = {
        "name": name,
        "name_hi": _clean(row.get("name_hi")),
        "name_te": _clean(row.get("name_te")),
        "source_id": source.id,
    }
    if instance is None:
        service.session.add(
            CommodityVariety(commodity_id=commodity_id, code=code, **values)
        )
        await service.session.flush()
        return "inserted"
    return _apply(instance, values)


async def _handle_grade(
    service: ReferenceService,
    row: dict[str, Any],
    source: ReferenceSource,
    seen: set[str],
) -> str:
    code = _clean(row.get("code"))
    name = _clean(row.get("name"))
    if not code or not name:
        raise ImportValidationError("'code' and 'name' are required")
    commodity_code = _clean(row.get("commodity_code"))
    commodity_id: int | None = None
    if commodity_code:
        commodity_id = await service._resolve_parent_id(
            Commodity, Commodity.code, commodity_code
        )
        if commodity_id is None:
            raise ImportValidationError(f"unknown commodity_code '{commodity_code}'")

    _reject_duplicate(seen, f"grade:{commodity_id}:{code}")
    conditions = [CommodityGrade.code == code]
    conditions.append(
        CommodityGrade.commodity_id == commodity_id
        if commodity_id is not None
        else CommodityGrade.commodity_id.is_(None)
    )
    result = await service.session.execute(
        select(CommodityGrade).where(*conditions)
    )
    instance = result.scalar_one_or_none()
    values = {
        "name": name,
        "name_hi": _clean(row.get("name_hi")),
        "name_te": _clean(row.get("name_te")),
        "source_id": source.id,
    }
    if instance is None:
        service.session.add(
            CommodityGrade(code=code, commodity_id=commodity_id, **values)
        )
        await service.session.flush()
        return "inserted"
    return _apply(instance, values)


async def _handle_unit(
    service: ReferenceService,
    row: dict[str, Any],
    source: ReferenceSource,
    seen: set[str],
) -> str:
    code = _clean(row.get("code"))
    name = _clean(row.get("name"))
    dimension_text = (_clean(row.get("dimension")) or "").lower()
    if not code or not name or dimension_text not in set(UnitDimension):
        raise ImportValidationError(
            "'code', 'name' and a valid 'dimension' (mass/volume/count/bag) are required"
        )
    dimension = UnitDimension(dimension_text)
    to_base_kg = _parse_decimal(row.get("to_base_kg"))
    if dimension is UnitDimension.MASS and (to_base_kg is None or to_base_kg <= 0):
        raise ImportValidationError("mass units require a positive 'to_base_kg'")

    _reject_duplicate(seen, f"unit:{code}")
    result = await service.session.execute(
        select(MeasurementUnit).where(MeasurementUnit.code == code)
    )
    instance = result.scalar_one_or_none()
    values = {
        "name": name,
        "name_hi": _clean(row.get("name_hi")),
        "name_te": _clean(row.get("name_te")),
        "dimension": dimension,
        "to_base_kg": to_base_kg,
        "source_id": source.id,
    }
    if instance is None:
        service.session.add(MeasurementUnit(code=code, **values))
        await service.session.flush()
        return "inserted"
    return _apply(instance, values)


SUPPORTED_ENTITIES: dict[str, Any] = {
    "states": _handle_state,
    "districts": _handle_district,
    "mandis": _handle_mandi,
    "localities": _handle_locality,
    "commodities": _handle_commodity,
    "varieties": _handle_variety,
    "grades": _handle_grade,
    "units": _handle_unit,
}

__all__ = [
    "ImportReport",
    "ImportValidationError",
    "MAX_ROWS",
    "ReferenceService",
    "SUPPORTED_ENTITIES",
    "VerificationStatus",
]