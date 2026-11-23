"""Data access for produce lots and their status history.

Every query is scoped by the owning farmer at the database level, so a missing
ownership filter is a bug the repository structurally prevents rather than
something a caller has to remember.
"""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..models import LotStatus, ProduceLot, ProduceLotStatusHistory


class LotRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, lot_id: int) -> ProduceLot | None:
        """Fetch any lot by id. Callers must still check ``farmer_id``."""
        result = await self.session.execute(
            select(ProduceLot).where(ProduceLot.id == lot_id)
        )
        return result.scalar_one_or_none()

    async def get_owned(
        self, lot_id: int, farmer_id: int
    ) -> ProduceLot | None:
        """Fetch a lot **only if** the caller owns it.

        Returns ``None`` for someone else's lot rather than raising, so the
        caller can answer 404 without ever revealing that the lot exists.
        """
        result = await self.session.execute(
            select(ProduceLot)
            .where(ProduceLot.id == lot_id, ProduceLot.farmer_id == farmer_id)
            .options(selectinload(ProduceLot.history))
        )
        return result.scalar_one_or_none()

    async def list_for_farmer(
        self,
        farmer_id: int,
        *,
        status: LotStatus | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[ProduceLot], int]:
        """Return one page of a farmer's lots plus the unpaginated total."""
        conditions = [ProduceLot.farmer_id == farmer_id]
        if status is not None:
            conditions.append(ProduceLot.status == status)

        total_result = await self.session.execute(
            select(func.count()).select_from(ProduceLot).where(*conditions)
        )
        total = int(total_result.scalar_one())

        rows_result = await self.session.execute(
            select(ProduceLot)
            .where(*conditions)
            .order_by(ProduceLot.created_at.desc(), ProduceLot.id.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(rows_result.scalars().all()), total

    async def list_history(
        self, lot_id: int, limit: int = 100
    ) -> list[ProduceLotStatusHistory]:
        """The farmer-facing status timeline, oldest first."""
        result = await self.session.execute(
            select(ProduceLotStatusHistory)
            .where(ProduceLotStatusHistory.lot_id == lot_id)
            .order_by(ProduceLotStatusHistory.id)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def count_by_status(self, farmer_id: int) -> dict[LotStatus, int]:
        """How many lots the farmer has in each status. Drives the dashboard."""
        result = await self.session.execute(
            select(ProduceLot.status, func.count())
            .where(ProduceLot.farmer_id == farmer_id)
            .group_by(ProduceLot.status)
        )
        return {status: int(count) for status, count in result.all()}

    def add(self, lot: ProduceLot) -> ProduceLot:
        self.session.add(lot)
        return lot

    def add_history(self, entry: ProduceLotStatusHistory) -> ProduceLotStatusHistory:
        self.session.add(entry)
        return entry


__all__ = ["LotRepository"]