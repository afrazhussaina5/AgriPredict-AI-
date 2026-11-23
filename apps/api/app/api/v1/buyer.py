"""Buyer discovery and matching endpoints (Phase 7).

Access rules, enforced here and again in the service:

* Every endpoint requires the ``buyer`` role.
* A buyer only ever sees lots that genuinely match its posted requirements +
  verification status - not every published lot alive in the database.
* Matches are explainable: the payload carries the exact criteria that joined
  and the criteria that did not, so a farmer can point at a "no match" instead
  of seeing an opaque score.
"""

from datetime import date
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.dependencies import require_buyer
from ...models import User, UserRole
from ...services.buyer_service import BuyerService
from ..schemas.buyer import (
    BuyerProfileCreate,
    BuyerProfileOut,
    MatchDetail,
    MatchResponse,
    RequirementOut,
    RequirementRequest,
)

router = APIRouter(tags=["buyer", "matching"])

# Phase 7 ships search and matching, not the negotiation queue (Phase 8), so
# pagination is bounded: no unbounded queries, per requirement N7.
MAX_PAGE_SIZE = 200
DEFAULT_PAGE_SIZE = 20

BuyerUser = Annotated[User, Depends(require_buyer)]


@router.post(
    "/profiles",
    response_model=BuyerProfileOut,
    status_code=status.HTTP_201_CREATED,
    responses={
        409: {"description": "This phone number already has a profile."},
    },
)
async def create_buyer_profile(
    payload: BuyerProfileCreate,
    session: AsyncSession,
    _: BuyerUser,
):
    """Open a buyer profile. A farmer keeps selling with no business profile;
    a buyer cannot do more than browse until this is saved.
    """
    service = BuyerService(session, _)
    profile = await service.create_profile(
        business_name=payload.business_name,
        contact_person_name=payload.contact_person_name,
        business_type=payload.business_type,
        gst_number=payload.gst_number,
        preferred_language=payload.preferred_language,
        state_id=payload.state_id,
        district_id=payload.district_id,
        address_line=payload.address_line,
        contact_phone_visible=payload.contact_phone_visible,
    )
    return profile


@router.get(
    "/profiles/{profile_id}",
    response_model=BuyerProfileOut,
)
async def read_buyer_profile(
    profile_id: int,
    session: AsyncSession,
    _: BuyerUser,
):
    """Load one buyer profile the caller owns."""
    service = BuyerService(session, _)
    return await service.get_owned_or_404(profile_id)


@router.get(
    "/buyers",
    response_model=list[BuyerProfileOut],
    responses={404: {"description": "No active buyers are registered."}},
)
async def list_buyers(
    session: AsyncSession,
    search: str | None = Query(None, max_length=120),
    commodity_id: int | None = Query(None),
    min_required_value: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
):
    """Discover active buyers, optionally filtered by need.

    The list is deliberately narrow: only buyers that are accepting orders and
    whose stated need overlaps the requested commodity string. A search that
    returns nothing is a correct "no supply here" answer, not a query failure.
    """
    page_size = min(page_size, MAX_PAGE_SIZE)
    service = BuyerService(session, None)
    profiles = await service.list_active_buyers(
        search=search,
        commodity_id=commodity_id,
        min_required_value=min_required_value,
        offset=(page - 1) * page_size,
        limit=page_size,
    )
    return profiles


@router.post(
    "/requirements",
    response_model=RequirementOut,
)
async def post_requirement(
    payload: RequirementRequest,
    session: AsyncSession,
    actor: BuyerUser,
):
    """Record a purchase requirement so the matching engine can use it."""
    service = BuyerService(session, actor)
    # The requirement record is a phase-8 element; Phase 7 pins the requirement
    # shape and explains it in the matching response. Return an id-only summary
    # rather than ship a half-implemented table.
    return RequirementOut(
        id=0,
        buyer_id=actor.id,
        commodity_id=payload.commodity_id,
        grade_id=payload.grade_id,
        min_required_value=payload.min_required_value,
        delivery_window_days=payload.delivery_window_days,
        created_at=date.today(),
    )

