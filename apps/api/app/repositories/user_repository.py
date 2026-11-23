"""Data access for users and roles.

Repositories only ever use ORM queries (parameterised by SQLAlchemy), so user
input can never be concatenated into SQL.
"""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import User, UserRole, UserRoleAssignment


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, user_id: int) -> User | None:
        return await self.session.get(User, user_id)

    async def get_by_phone(self, phone_e164: str) -> User | None:
        result = await self.session.execute(
            select(User).where(User.phone_e164 == phone_e164)
        )
        return result.scalar_one_or_none()

    async def list_roles(self, user_id: int) -> set[UserRole]:
        result = await self.session.execute(
            select(UserRoleAssignment.role).where(UserRoleAssignment.user_id == user_id)
        )
        return set(result.scalars().all())

    async def has_role(self, user_id: int, role: UserRole) -> bool:
        result = await self.session.execute(
            select(func.count())
            .select_from(UserRoleAssignment)
            .where(
                UserRoleAssignment.user_id == user_id,
                UserRoleAssignment.role == role,
            )
        )
        return bool(result.scalar_one())

    async def add_role(
        self, user_id: int, role: UserRole, granted_by_id: int | None = None
    ) -> UserRoleAssignment:
        """Assign a role. Admin assignment is refused here as a defence in depth.

        The real guard lives in the Phase 15 admin service; this keeps the
        repository safe even if a future route forgets to check.
        """
        # Equality (not identity) on purpose: a plain string such as "admin" must be
        # caught too, otherwise a caller could bypass this guard by passing a
        # raw value instead of the enum member.
        if role == UserRole.ADMIN:
            raise PermissionError("Admin role cannot be assigned through the user repository.")
        assignment = UserRoleAssignment(user_id=user_id, role=role, granted_by_id=granted_by_id)
        self.session.add(assignment)
        return assignment

    async def count(self) -> int:
        result = await self.session.execute(select(func.count()).select_from(User))
        return int(result.scalar_one())

    async def touch_last_login(self, user: User) -> None:
        from ..models import utcnow

        user.last_login_at = utcnow()
        self.session.add(user)