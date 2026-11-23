"""Reference data endpoints (Phase 5).

Read endpoints are public (place names are not private). Import is admin-only
and always defaults to a dry run.

Honesty rule: an empty database returns ``200`` with an empty list, and
``/reference/status`` reports ``is_populated: false``. The frontend shows a
"not loaded yet" message rather than an empty dropdown that looks broken.
"""

from fastapi import APIRouter, Query

from ...core.dependencies import DbSession
from ...core.errors import NotFoundError
from ...models import State
from ...schemas.reference import (
    CommodityOut,
    DistrictOut,
    GradeOut,
    LocalityOut,
    MandiOut,
    ReferenceCounts,
    ReferenceSourceOut,
    ReferenceStatus,
    StateOut,
    UnitOut,
    VarietyOut,
)
from ...services.reference_service import ReferenceService

router = APIRouter(prefix="/reference", tags=["reference"])


@router.get("/status", response_model=ReferenceStatus, summary="Reference data availability")
async def reference_status(session: DbSession) -> ReferenceStatus:
    """Report what reference data exists and where it came from."""
    service = ReferenceService(session)
    counts = await service.counts()
    sources = await service.list_sources()
    oldest, newest = await service.import_dates()
    return ReferenceStatus(
        is_populated=counts["states"] > 0 and counts["districts"] > 0,
        counts=ReferenceCounts(**counts),
        sources=[ReferenceSourceOut.model_validate(source) for source in sources],
        oldest_import_at=oldest,
        newest_import_at=newest,
    )


@router.get("/states", response_model=list[StateOut], summary="List states")
async def list_states(session: DbSession) -> list[StateOut]:
    rows = await ReferenceService(session).list_states()
    return [StateOut(**row) for row in rows]


@router.get(
    "/states/{state_id}/districts",
    response_model=list[DistrictOut],
    summary="List districts in a state",
)
async def list_districts(state_id: int, session: DbSession) -> list[DistrictOut]:
    exists = await session.get(State, state_id)
    if exists is None:
        raise NotFoundError("That state does not exist.")
    rows = await ReferenceService(session).list_districts(state_id)
    return [DistrictOut(**row) for row in rows]


@router.get(
    "/districts/{district_id}/localities",
    response_model=list[LocalityOut],
    summary="List cities, towns and villages in a district",
)
async def list_localities(district_id: int, session: DbSession) -> list[LocalityOut]:
    from ...models import District

    exists = await session.get(District, district_id)
    if exists is None:
        raise NotFoundError("That district does not exist.")
    rows = await ReferenceService(session).list_localities(district_id)
    return [LocalityOut(**row) for row in rows]


@router.get("/mandis", response_model=list[MandiOut], summary="List mandis")
async def list_mandis(
    session: DbSession,
    district_id: int | None = Query(default=None, description="Filter by district."),
) -> list[MandiOut]:
    rows = await ReferenceService(session).list_mandis(district_id=district_id)
    return [MandiOut(**row) for row in rows]


@router.get("/commodities", response_model=list[CommodityOut], summary="List commodities")
async def list_commodities(session: DbSession) -> list[CommodityOut]:
    rows = await ReferenceService(session).list_commodities()
    return [CommodityOut(**row) for row in rows]


@router.get(
    "/commodities/{commodity_id}/varieties",
    response_model=list[VarietyOut],
    summary="List varieties of a commodity",
)
async def list_varieties(commodity_id: int, session: DbSession) -> list[VarietyOut]:
    from ...models import Commodity

    exists = await session.get(Commodity, commodity_id)
    if exists is None:
        raise NotFoundError("That commodity does not exist.")
    rows = await ReferenceService(session).list_varieties(commodity_id)
    return [VarietyOut(**row) for row in rows]


@router.get("/grades", response_model=list[GradeOut], summary="List grades")
async def list_grades(
    session: DbSession,
    commodity_id: int | None = Query(default=None, description="Filter by commodity."),
) -> list[GradeOut]:
    rows = await ReferenceService(session).list_grades(commodity_id)
    return [GradeOut(**row) for row in rows]


@router.get("/units", response_model=list[UnitOut], summary="List measurement units")
async def list_units(session: DbSession) -> list[UnitOut]:
    rows = await ReferenceService(session).list_units()
    return [UnitOut(**row) for row in rows]


__all__ = ["router"]