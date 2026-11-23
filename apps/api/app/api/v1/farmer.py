"""Farmer profile and produce lot endpoints (Phase 6).

Access rules, enforced here and again in the service:

* Every endpoint requires the ``farmer`` role.
* Every lot query is scoped to the caller. Another farmer's lot answers **404**,
  not 403 - a 403 would confirm the lot exists to anyone guessing ids.
* Status moves go through ``POST /lots/{id}/status`` and nowhere else, so each
  transition is validated in exactly one place and lands in the history.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from ...core.dependencies import DbSession, require_farmer
from ...core.errors import NotFoundError, ValidationError
from ...models import District, FarmerProfile, LotStatus, Mandi, State, User, UserRole
from ...repositories import AuditRepository, FarmerRepository
from ...schemas.auth import MessageResponse
from ...schemas.farmer import (
    FarmerProfileOut,
    FarmerProfileUpdate,
    LotCreate,
    LotDetailOut,
    LotHistoryEntry,
    LotListOut,
    LotOut,
    LotStatusChange,
    LotUpdate,
)
from ...services.lot_service import LotService

router = APIRouter(tags=["farmer", "lots"])

FarmerUser = Annotated[User, Depends(require_farmer)]

# Phase 6 has no marketplace browser yet (that is Phase 7), so pagination is
# simple and bounded: no unbounded queries, per requirement N6.
MAX_PAGE_SIZE = 100
DEFAULT_PAGE_SIZE = 20


def _with_names(
    profile: FarmerProfile,
    state_name: str | None,
    district_name: str | None,
    mandi_name: str | None,
) -> FarmerProfileOut:
    """Attach resolved reference names so the client needs no extra fetches."""
    out = FarmerProfileOut.model_validate(profile)
    out.state_name = state_name
    out.district_name = district_name
    out.mandi_name = mandi_name
    return out


async def _load_owned_profile(session: DbSession, user: User) -> FarmerProfileOut:
    """Load the caller's profile, or report that it has not been created yet."""
    repository = FarmerRepository(session)
    profile = await repository.get_by_user_id(user.id)
    if profile is None:
        raise NotFoundError(
            "You do not have a farmer profile yet. Complete farmer setup first."
        )

    state_name = district_name = mandi_name = None
    if profile.state_id is not None:
        state = await session.get(State, profile.state_id)
        state_name = state.name if state else None
    if profile.district_id is not None:
        district = await session.get(District, profile.district_id)
        district_name = district.name if district else None
    if profile.mandi_id is not None:
        mandi = await session.get(Mandi, profile.mandi_id)
        mandi_name = mandi.name if mandi else None

    return _with_names(profile, state_name, district_name, mandi_name)


@router.get(
    "/farmer/profile",
    response_model=FarmerProfileOut,
    summary="My farmer profile",
)
async def read_farmer_profile(user: FarmerUser, session: DbSession) -> FarmerProfileOut:
    """Return the calling farmer's own profile and resolved location names."""
    return await _load_owned_profile(session, user)


@router.patch(
    "/farmer/profile",
    response_model=FarmerProfileOut,
    summary="Update my farmer profile",
)
async def update_farmer_profile(
    payload: FarmerProfileUpdate,
    user: FarmerUser,
    session: DbSession,
) -> FarmerProfileOut:
    """Partially update the calling farmer's profile, creating it on first save.

    Phase 4 onboarding creates the account and the role but not a farmer
    profile, so "no profile yet" is the normal first-run state rather than an
    error. This endpoint creates the profile from what the farmer typed; no
    name is ever invented for them.

    Location ids are validated against the loaded reference data so a profile
    cannot point at a district that was never imported.
    """
    repository = FarmerRepository(session)
    profile = await repository.get_by_user_id(user.id)
    created = profile is None

    if profile is None:
        if not payload.full_name:
            raise ValidationError("Enter your name to create your farmer profile.")
        profile = await repository.create_for_user(
            user.id,
            full_name=payload.full_name,
            preferred_language=user.preferred_locale.value,
        )

    changes = payload.model_dump(exclude_unset=True)
    for key, value in list(changes.items()):
        if key == "full_name":
            # Already applied above on the create path, and setattr below
            # handles it on the update path.
            continue
        if value is None:
            del changes[key]
        elif value == "" and key in ("bio", "organisation_name", "village_or_town"):
            changes[key] = None

    state_id = changes.get("state_id", profile.state_id)
    district_id = changes.get("district_id", profile.district_id)
    mandi_id = changes.get("mandi_id", profile.mandi_id)

    if state_id is not None:
        state = await session.get(State, state_id)
        if state is None or not state.is_active:
            raise ValidationError("That state is not available.")

    if district_id is not None:
        district = await session.get(District, district_id)
        if district is None or not district.is_active:
            raise ValidationError("That district is not available.")
        if state_id is not None and district.state_id != state_id:
            raise ValidationError("That district is not in the chosen state.")

    if mandi_id is not None:
        if district_id is None:
            raise ValidationError("Choose the district before choosing a mandi.")
        mandi = await session.get(Mandi, mandi_id)
        if mandi is None or not mandi.is_active:
            raise ValidationError("That mandi is not available.")
        if mandi.district_id != district_id:
            raise ValidationError("That mandi is not in the chosen district.")

    for key, value in changes.items():
        setattr(profile, key, value)

    # Completion is a plain count of what the farmer has filled in, so it can
    # never claim more progress than the data actually supports.
    profile.completion_percent = _completion_percent(profile)

    session.add(profile)
    await AuditRepository(session).record(
        action="farmer.profile_created" if created else "farmer.profile_updated",
        entity_type="farmer_profile",
        entity_id=profile.id,
        actor_user_id=user.id,
        actor_role=UserRole.FARMER,
        details={"fields": sorted(changes.keys())},
    )
    await session.commit()
    return await _load_owned_profile(session, user)


def _completion_percent(profile: FarmerProfile) -> int:
    """Percent of the recommended profile fields that are filled in."""
    checks = (
        bool(profile.full_name),
        profile.state_id is not None,
        profile.district_id is not None,
        bool(profile.village_or_town),
        profile.mandi_id is not None,
        bool(profile.bio),
    )
    return round(100 * sum(1 for check in checks if check) / len(checks))


# --------------------------------------------------------------------------
# Produce lots
# --------------------------------------------------------------------------


@router.get(
    "/lots",
    response_model=LotListOut,
    summary="My produce lots",
)
async def list_my_lots(
    user: FarmerUser,
    session: DbSession,
    status_filter: Annotated[
        LotStatus | None, Query(alias="status", description="Filter by lifecycle status.")
    ] = None,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = DEFAULT_PAGE_SIZE,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> LotListOut:
    """List the calling farmer's own lots, newest first."""
    items, total = await LotService(session, user).list_owned(
        status=status_filter, limit=limit, offset=offset
    )
    return LotListOut(
        items=[_lot_out(lot) for lot in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post(
    "/lots",
    response_model=LotOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create a produce lot",
)
async def create_lot(
    payload: LotCreate,
    user: FarmerUser,
    session: DbSession,
) -> LotOut:
    """Create a lot in the ``draft`` status.

    A new lot is never published automatically: the farmer reviews it first,
    then publishes deliberately.
    """
    lot = await LotService(session, user).create(payload)
    await session.commit()
    await session.refresh(lot)
    return _lot_out(lot)


@router.get(
    "/lots/{lot_id}",
    response_model=LotDetailOut,
    summary="One of my lots",
)
async def read_my_lot(lot_id: int, user: FarmerUser, session: DbSession) -> LotDetailOut:
    """Return a lot with its status timeline and the moves available next."""
    service = LotService(session, user)
    lot = await service.get_owned_or_404(lot_id)
    history = await service.lots.list_history(lot_id)

    detail = LotDetailOut.model_validate(_lot_out(lot).model_dump())
    detail.history = [LotHistoryEntry.model_validate(row) for row in history]
    detail.allowed_transitions = service.allowed_transitions(lot.status)
    return detail


@router.patch(
    "/lots/{lot_id}",
    response_model=LotOut,
    summary="Edit one of my lots",
)
async def update_lot(
    lot_id: int,
    payload: LotUpdate,
    user: FarmerUser,
    session: DbSession,
) -> LotOut:
    """Edit a draft or paused lot. Published and closed lots are refused."""
    service = LotService(session, user)
    lot = await service.get_owned_or_404(lot_id)
    await service.update(lot, payload)
    await session.commit()
    await session.refresh(lot)
    return _lot_out(lot)


@router.post(
    "/lots/{lot_id}/status",
    response_model=LotDetailOut,
    summary="Move a lot to a new lifecycle status",
)
async def change_lot_status(
    lot_id: int,
    payload: LotStatusChange,
    user: FarmerUser,
    session: DbSession,
) -> LotDetailOut:
    """Publish, pause, resume, close or archive a lot.

    The server decides whether the move is legal; the client only asks.
    """
    service = LotService(session, user)
    lot = await service.get_owned_or_404(lot_id)
    await service.change_status(lot, payload.status, reason=payload.reason)
    await session.commit()
    await session.refresh(lot)

    history = await service.lots.list_history(lot_id)
    detail = LotDetailOut.model_validate(_lot_out(lot).model_dump())
    detail.history = [LotHistoryEntry.model_validate(row) for row in history]
    detail.allowed_transitions = service.allowed_transitions(lot.status)
    return detail


@router.delete(
    "/lots/{lot_id}",
    response_model=MessageResponse,
    summary="Archive a lot",
)
async def archive_lot(
    lot_id: int,
    user: FarmerUser,
    session: DbSession,
) -> MessageResponse:
    """Archive a lot instead of deleting it.

    Lots are never hard-deleted: the status history and the audit trail have to
    stay meaningful after a farmer removes something from their list.
    """
    service = LotService(session, user)
    lot = await service.get_owned_or_404(lot_id)
    if lot.status is LotStatus.ARCHIVED:
        raise ValidationError("This lot is already archived.")
    await service.change_status(lot, LotStatus.ARCHIVED, reason="Archived by the farmer.")
    await session.commit()
    return MessageResponse(message="Lot archived.")


def _lot_out(lot) -> LotOut:
    """Build the owner's view, filling in reference names from the loaded rows."""
    out = LotOut.model_validate(lot)
    out.commodity_name = getattr(lot.commodity, "name", None)
    out.variety_name = getattr(lot.variety, "name", None)
    out.grade_name = getattr(lot.grade, "name", None)
    out.unit_name = getattr(lot.unit, "name", None)
    out.unit_code = getattr(lot.unit, "code", None)
    out.pickup_district_name = getattr(lot.pickup_district, "name", None)
    out.pickup_mandi_name = getattr(lot.pickup_mandi, "name", None)
    return out


__all__ = ["router"]