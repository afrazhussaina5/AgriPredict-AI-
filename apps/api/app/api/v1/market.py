"""Public market (mandi) price board (Phase 6).

Every user sees the same live prices: grades A/B/C are part of the payload
and the source, date and freshness travel with each row so nothing is passed
off as verified when it is not.

Every route here is read-only and public. Nothing in this file writes: the
only way prices arrive is the offline importer,
``python -m scripts.import_market --apply``, which fetches the government
resource, upserts on the business-day key and stamps the freshness row this
board reports.
"""

from fastapi import APIRouter, Query

from ...core.dependencies import DbSession
from ...services.market_service import MarketService

router = APIRouter(prefix="/market", tags=["market"])

# A page shows one row per commodity+grade+district so the board can be
# pivoted by grade or district without keeping the raw table denormalised.


@router.get("/prices", response_model=list[dict])
async def public_prices(
    session: DbSession,
    commodity_id: int | None = Query(default=None, description="Filter by commodity."),
    grade_id: int | None = Query(default=None, description="Filter by grade (A/B/C)."),
    district_id: int | None = Query(default=None, description="Filter by district."),
) -> list[dict]:
    return await MarketService().public_rows(
        session,
        commodity_id=commodity_id,
        grade_id=grade_id,
        district_id=district_id,
    )


@router.get("/commodities", response_model=list[dict])
async def market_commodities(session: DbSession) -> list[dict]:
    return await MarketService().list_commodities(session)


@router.get("/grades", response_model=list[dict])
async def market_grades(session: DbSession) -> list[dict]:
    return await MarketService().list_grades(session)


@router.get("/mandi/{mandi_id}/prices", response_model=list[dict])
async def mandi_prices(mandi_id: int, session: DbSession) -> list[dict]:
    return await MarketService().mandi_rows(session, mandi_id)


@router.get("/freshness", response_model=dict)
async def freshness(session: DbSession) -> dict:
    """Last successful import timestamp, so the board can label stale rows."""
    return {"last_imported_at": await MarketService().import_dates(session)}


@router.get("/source", response_model=dict)
async def source_info() -> dict:
    return {
        "source_name": "data.gov.in / India Ministry of Agriculture (Agmarknet)",
        "resource": "variety-wise daily market prices",
        "access_policy": "public - no authentication required",
    }


@router.get("/schema", response_model=dict)
async def schema_info() -> dict:
    """Contract for the price row the UI renders.

    No database access - the schema is stable by construction, which is what
    lets every user (including unauthenticated ones) render the board without
    a role probe.
    """
    return {
        "rows": [
            {"field": "commodity", "type": "string", "label": "Crop"},
            {"field": "grade", "type": "string", "label": "Quality grade (A/B/C)"},
            {"field": "mandi", "type": "string", "label": "Market"},
            {"field": "district", "type": "string", "label": "District"},
            {"field": "state", "type": "string", "label": "State"},
            {"field": "date", "type": "date", "label": "Market day"},
            {"field": "price", "type": "number", "label": "Modal price (stock)"},
            {"field": "unit", "type": "string", "label": "Unit"},
            {"field": "arrivals", "type": "number", "label": "Arrivals in the mandi"},
            {"field": "source", "type": "string", "label": "Original data source"},
            {
                "field": "imported_at",
                "type": "datetime",
                "label": "When this row was ingested",
            },
        ],
        "grading_note": (
            'Grade A is the top tier, Grade B the middle, Grade C the floor. '
            'Rows with a missing grade are shown as "not graded".'
        ),
    }
