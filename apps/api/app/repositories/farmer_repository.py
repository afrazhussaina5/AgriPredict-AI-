"""Data access for farmer profiles."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import FarmerProfile, User


class FarmerRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_user_id(self, user_id: int) -> FarmerProfile | None:
        result = await self.session.execute(
            select(FarmerProfile).where(FarmerProfile.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def create_for_user(
        self,
        user_id: int,
        *,
        full_name: str,
        preferred_language: str = "en",
    ) -> FarmerProfile:
        """Create the profile if it does not exist yet, and return it.

        Idempotent on purpose: onboarding may call this more than once, and a
        farmer must never end up with two profiles for one account.
        """
        existing = await self.get_by_user_id(user_id)
        if existing is not None:
            return existing

        profile = FarmerProfile(
            user_id=user_id,
            full_name=full_name,
            preferred_language=preferred_language,
        )
        self.session.add(profile)
        await self.session.flush()
        return profile

    async def exists_for_user(self, user_id: int) -> bool:
        result = await self.session.execute(
            select(FarmerProfile.id).where(FarmerProfile.user_id == user_id)
        )
        return result.scalar_one_or_none() is not None

    async def get_display_name(self, user_id: int) -> str | None:
        result = await self.session.execute(
            select(User.display_name).where(User.id == user_id)
        )
        return result.scalar_one_or_none()


__all__ = ["FarmerRepository"]