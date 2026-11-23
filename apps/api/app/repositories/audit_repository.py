"""Data access for the audit log."""

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import AuditLog, UserRole


class AuditRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def record(
        self,
        *,
        action: str,
        entity_type: str,
        actor_user_id: int | None = None,
        actor_role: UserRole | None = None,
        entity_id: str | int | None = None,
        details: dict[str, Any] | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        result: str = "success",
        description: str | None = None,
    ) -> AuditLog:
        """Append an audit entry.

        The caller is responsible for committing; this keeps the audit row in
        the same transaction as the business change it describes.
        """
        entry = AuditLog(
            actor_user_id=actor_user_id,
            actor_role=actor_role,
            action=action,
            entity_type=entity_type,
            entity_id=str(entity_id) if entity_id is not None else None,
            details=details or {},
            ip_address=ip_address,
            user_agent=(user_agent or "")[:300] or None,
            result=result,
            description=description,
        )
        self.session.add(entry)
        return entry

    async def list_for_entity(
        self, entity_type: str, entity_id: str | int, limit: int = 50
    ) -> list[AuditLog]:
        result = await self.session.execute(
            select(AuditLog)
            .where(
                AuditLog.entity_type == entity_type,
                AuditLog.entity_id == str(entity_id),
            )
            .order_by(AuditLog.created_at.desc())
            .limit(min(limit, 200))
        )
        return list(result.scalars().all())