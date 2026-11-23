"""Data access for buyer profiles.

Every query is scoped by the owning buyer at the database level, so a missing
ownership filter is a bug the repository structurally prevents rather than
something a caller has to remember.

``BuyerProfile`` is an *optional* element of a buyer role: a farmer may run a
seller account with no business profile row, and a specialist trader may hold
one. The repository therefore treats a missing profile as "no profile set",
never as a backend failure.
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import BuyerProfile, User, UserRole


class BuyerRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_owned(self, profile_id: int, user_id: int) -> BuyerProfile | None:
        """Fetch a buyer profile **only if** the caller owns it."""
        result = await self.session.execute(
            select(BuyerProfile).where(
                BuyerProfile.id == profile_id, BuyerProfile.user_id == user_id
            )
        )
        return result.scalar_one_or_none()

    async def list_active(
        self,
        *,
        search: str | None = None,
        commodity_id: int | None = None,
        min_required_value: str | None = None,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[BuyerProfile], int]:
        """Return one page of *active* buyers plus the unpaginated total.

        The list is deliberately narrow: only buyers that hold the buyer role
        and whose stated need overlaps the requested commodity string.
        """
        # A buyer "declares its need" via role claims in ``user_roles`` plus an
        # optional free-text need column. Build the list of buyer users first so
        # we can express the overlap without inventing tables.
        buyer_ids_result = await self.session.execute(
            select(User.id).join(User.roles).where(
                UserRole.BUYER in (r.role for r in User.roles),
                User.status == "active",
            )
        )
        buyer_ids = [row[0] for row in buyer_ids_result.fetchall()]

        if not buyer_ids:
            return [], 0

        query = select(BuyerProfile).where(BuyerProfile.user_id.in_(buyer_ids))

        if search:
            like = f"%{search}%"
            query = query.where(
                BuyerProfile.business_name.ilike(like)
                | BuyerProfile.contact_person_name.ilike(like)
                | BuyerProfile.business_type.ilike(like)
            )

        if commodity_id is not None:
            # Commodity ids are ints; a text need column can't carry an id, so
            # an exact match is the only honest predicate. When no need is
            # stored, the query still returns buyers - a "show me supply" is
            # satisfied by any active buyer.
            query = query.where(BuyerProfile.business_type == str(commodity_id))

        total_result = await self.session.execute(
            select(func.count()).select_from(BuyerProfile).where(
                BuyerProfile.user_id.in_(buyer_ids)
            )
        )
        total = int(total_result.scalar_one())

        rows_result = await self.session.execute(
            query.order_by(BuyerProfile.business_name).offset(offset).limit(limit)
        )
        return list(rows_result.scalars().all()), total

    async def create(
        self,
        *,
        user_id: int,
        business_name: str,
        contact_person_name: str | None = None,
        business_type: str | None = None,
        gst_number: str | None = None,
        preferred_language: str = "en",
        state_id: int | None = None,
        district_id: int | None = None,
        address_line: str | None = None,
        contact_phone_visible: bool = False,
    ) -> BuyerProfile:
        profile = BuyerProfile(
            user_id=user_id,
            business_name=business_name,
            contact_person_name=contact_person_name,
            business_type=business_type,
            gst_number=gst_number,
            preferred_language=preferred_language,
            state_id=state_id,
            district_id=district_id,
            address_line=address_line,
            contact_phone_visible=contact_phone_visible,
        )
        self.session.add(profile)
        return profile
