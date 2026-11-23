"""Data access for reference rows created on the fly by ingest pipelines.

The reference CSV importer (Phase 5) writes rows the operator supplied. The
market pipeline (Phase 6) is different: it sees a government payload that
names a state, district, mandi, commodity, grade or unit we may never have
seen before, and it must resolve each name to a row before a price can be
stored. These get-or-create helpers are that resolution step.

Rules enforced here:

* Every row created here is stamped with the source it arrived on - no
  reference value exists without provenance.
* Newly created rows are ``imported``, never ``verified``: seeing a name in a
  government feed is not the same as checking it against a second source.
* Natural keys match migration 0003 (state code, district state+code, mandi
  code, commodity code, variety commodity+code, grade commodity+code, unit
  code), so a re-run of the pipeline updates rather than duplicates.
* ORM queries only (parameterised by SQLAlchemy); payload text never becomes
  SQL.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import (
    Commodity,
    CommodityGrade,
    District,
    Locality,
    LocalityKind,
    Mandi,
    MeasurementUnit,
    ReferenceSource,
    State,
    UnitDimension,
    VerificationStatus,
)


class ReferenceRepository:
    """Get-or-create resolution for reference rows during ingestion."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def _resolve_source(
        self, source_key: str, source_name: str
    ) -> ReferenceSource:
        """Find-or-create the provenance row a new reference row needs."""
        result = await self.session.execute(
            select(ReferenceSource).where(ReferenceSource.source_key == source_key)
        )
        source = result.scalar_one_or_none()
        if source is None:
            source = ReferenceSource(
                source_key=source_key,
                name=source_name,
                # An ingest pipeline source is official by definition of where
                # the rows came from; verification of the rows themselves is
                # still separate (status stays 'imported').
                is_official=True,
                status=VerificationStatus.IMPORTED,
            )
            self.session.add(source)
            await self.session.flush()
        return source

    async def get_or_create_source(
        self, source_key: str, source_name: str
    ) -> ReferenceSource:
        return await self._resolve_source(source_key, source_name)

    async def get_or_create_state(
        self, name: str, code: str | None = None
    ) -> State:
        """Resolve a state by code when known, else by name.

        Agmarknet rows sometimes omit the state code; the name is stable
        enough to join on, and a second row with the same name but a later
        code is treated as the same state rather than a duplicate.
        """
        name = name.strip()
        if not name:
            raise ValueError("state name is required")
        code = (code or name[:8]).strip().upper()

        result = await self.session.execute(
            select(State).where(State.code == code)
        )
        state = result.scalar_one_or_none()
        if state is None:
            by_name = await self.session.execute(
                select(State).where(State.name.ilike(name))
            )
            state = by_name.scalar_one_or_none()
        if state is not None:
            return state

        source = await self._resolve_source(
            "data.gov.in", "India Ministry of Agriculture (Agmarknet)"
        )
        state = State(code=code, name=name, source_id=source.id)
        self.session.add(state)
        await self.session.flush()
        return state

    async def get_or_create_district(
        self, name: str, code: str | None, state: State
    ) -> District:
        name = name.strip()
        if not name:
            raise ValueError("district name is required")
        code = (code or name[:16]).strip().upper()

        result = await self.session.execute(
            select(District).where(
                District.state_id == state.id, District.code == code
            )
        )
        district = result.scalar_one_or_none()
        if district is None:
            by_name = await self.session.execute(
                select(District).where(
                    District.state_id == state.id, District.name.ilike(name)
                )
            )
            district = by_name.scalar_one_or_none()
        if district is not None:
            return district

        source = await self._resolve_source(
            "data.gov.in", "India Ministry of Agriculture (Agmarknet)"
        )
        district = District(
            state_id=state.id, code=code, name=name, source_id=source.id
        )
        self.session.add(district)
        await self.session.flush()
        return district

    async def get_or_create_mandi(
        self,
        name: str,
        code: str | None,
        district: District,
        has_storage: bool | None = None,
    ) -> Mandi:
        name = name.strip()
        if not name:
            raise ValueError("mandi name is required")
        code = (code or name[:32]).strip().upper()

        result = await self.session.execute(
            select(Mandi).where(Mandi.code == code)
        )
        mandi = result.scalar_one_or_none()
        if mandi is None:
            by_name = await self.session.execute(
                select(Mandi).where(
                    Mandi.district_id == district.id, Mandi.name.ilike(name)
                )
            )
            mandi = by_name.scalar_one_or_none()
        if mandi is not None:
            return mandi

        source = await self._resolve_source(
            "data.gov.in", "India Ministry of Agriculture (Agmarknet)"
        )
        mandi = Mandi(
            district_id=district.id,
            code=code,
            name=name,
            has_storage=has_storage,
            source_id=source.id,
        )
        self.session.add(mandi)
        await self.session.flush()
        return mandi

    async def get_or_create_commodity(
        self, name: str, code: str | None = None
    ) -> Commodity:
        name = name.strip()
        if not name:
            raise ValueError("commodity name is required")
        code = (code or name[:32]).strip().upper()

        result = await self.session.execute(
            select(Commodity).where(Commodity.code == code)
        )
        commodity = result.scalar_one_or_none()
        if commodity is None:
            by_name = await self.session.execute(
                select(Commodity).where(Commodity.name.ilike(name))
            )
            commodity = by_name.scalar_one_or_none()
        if commodity is not None:
            return commodity

        source = await self._resolve_source(
            "data.gov.in", "India Ministry of Agriculture (Agmarknet)"
        )
        commodity = Commodity(code=code, name=name, source_id=source.id)
        self.session.add(commodity)
        await self.session.flush()
        return commodity

    async def get_or_create_grade(
        self, code: str | None, commodity: Commodity | None
    ) -> CommodityGrade | None:
        """Resolve a grade; ``None`` means the source row carried no grade.

        A price row with a NULL grade renders as "not graded" - we never
        invent A/B/C for data that did not ship one.
        """
        if code is None or not code.strip():
            return None
        code = code.strip().upper()
        commodity_id = commodity.id if commodity is not None else None

        result = await self.session.execute(
            select(CommodityGrade).where(
                CommodityGrade.commodity_id == commodity_id,
                CommodityGrade.code == code,
            )
        )
        grade = result.scalar_one_or_none()
        if grade is not None:
            return grade

        source = await self._resolve_source(
            "data.gov.in", "India Ministry of Agriculture (Agmarknet)"
        )
        grade = CommodityGrade(
            commodity_id=commodity_id,
            code=code,
            # The source ships the letter only; the readable name mirrors it
            # rather than inventing a description.
            name=code,
            source_id=source.id,
        )
        self.session.add(grade)
        await self.session.flush()
        return grade

    async def get_or_create_unit(
        self, name: str, code: str | None = None
    ) -> MeasurementUnit:
        """Resolve a measurement unit.

        The dimension is inferred from the unit token because Agmarknet rows
        ship a bare label ("Quintal", "kg"). Mass units carry the conversion
        to kilograms required by the table's CHECK constraint; anything that
        is not recognisably mass is recorded as a count rather than guessing
        a conversion.
        """
        name = name.strip()
        if not name:
            raise ValueError("unit name is required")
        code = (code or name[:24]).strip().lower()

        result = await self.session.execute(
            select(MeasurementUnit).where(MeasurementUnit.code == code)
        )
        unit = result.scalar_one_or_none()
        if unit is not None:
            return unit

        dimension, to_base_kg = self._classify_unit(name, code)
        source = await self._resolve_source(
            "data.gov.in", "India Ministry of Agriculture (Agmarknet)"
        )
        unit = MeasurementUnit(
            code=code,
            name=name,
            dimension=dimension,
            to_base_kg=to_base_kg,
            source_id=source.id,
        )
        self.session.add(unit)
        await self.session.flush()
        return unit

    @staticmethod
    def _classify_unit(name: str, code: str) -> tuple[UnitDimension, float | None]:
        """Map a unit token onto (dimension, kilograms per unit)."""
        token = f"{code} {name}".lower()
        mass_factors: list[tuple[tuple[str, ...], float]] = [
            (("quintal", "qtl", "qr"), 100.0),
            (("kilogram", "kgs", "kg", "kilo"), 1.0),
            (("gram", "gm", "g"), 0.001),
            (("tonne", "ton", "mt"), 1000.0),
            (("milligram", "mg"), 0.000001),
            (("pound", "lb"), 0.45359237),
        ]
        for hints, factor in mass_factors:
            if any(hint in token for hint in hints):
                return UnitDimension.MASS, factor
        if any(hint in token for hint in ("litre", "liter", "ltr", "ml", "m litre")):
            return UnitDimension.VOLUME, None
        if any(hint in token for hint in ("bag", "bori", "sack", "packet")):
            return UnitDimension.BAG, None
        return UnitDimension.COUNT, None

    async def get_or_create_locality(
        self,
        name: str,
        kind: LocalityKind,
        district: District,
        latitude: float | None = None,
        longitude: float | None = None,
    ) -> Locality:
        """Resolve a locality inside a district (same key as migration 0003)."""
        name = name.strip()
        if not name:
            raise ValueError("locality name is required")

        result = await self.session.execute(
            select(Locality).where(
                Locality.district_id == district.id,
                Locality.kind == kind,
                Locality.name.ilike(name),
            )
        )
        locality = result.scalar_one_or_none()
        if locality is not None:
            return locality

        source = await self._resolve_source(
            "data.gov.in", "India Ministry of Agriculture (Agmarknet)"
        )
        locality = Locality(
            district_id=district.id,
            kind=kind,
            name=name,
            latitude=latitude,
            longitude=longitude,
            source_id=source.id,
        )
        self.session.add(locality)
        await self.session.flush()
        return locality


__all__ = ["ReferenceRepository"]
