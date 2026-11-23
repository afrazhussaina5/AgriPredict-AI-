"""Tests for ORM model constraints, defaults and privacy defaults."""

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditLog, FarmerProfile, OtpVerification, User, UserRoleAssignment


async def test_user_defaults_are_safe(session: AsyncSession, make_user) -> None:
    user = await make_user("9000000001")
    assert user.status.value == "active"
    assert user.preferred_locale.value == "en"
    assert user.phone_verified_at is None


async def test_duplicate_phone_is_rejected(session: AsyncSession, make_user) -> None:
    await make_user("9000000002")
    session.add(User(phone_e164="+919000000002"))
    with pytest.raises(IntegrityError):
        await session.flush()
    await session.rollback()


async def test_invalid_phone_shape_is_rejected(session: AsyncSession) -> None:
    session.add(User(phone_e164="12345"))
    with pytest.raises(IntegrityError):
        await session.flush()
    await session.rollback()


async def test_farmer_profile_privacy_defaults_are_private(session: AsyncSession,
                                                             make_user) -> None:
    user = await make_user("9000000003")
    profile = FarmerProfile(user_id=user.id, full_name="Test Farmer")
    session.add(profile)
    await session.commit()

    assert profile.show_exact_location_to_buyers is False
    assert profile.contact_phone_visible is False
    assert profile.status.value == "draft"


async def test_role_assignment_is_unique_per_role(session: AsyncSession, make_user) -> None:
    user = await make_user("9000000004")
    session.add(UserRoleAssignment(user_id=user.id, role="farmer"))
    await session.commit()
    session.add(UserRoleAssignment(user_id=user.id, role="farmer"))
    with pytest.raises(IntegrityError):
        await session.flush()
    await session.rollback()


async def test_repository_refuses_admin_grant(session: AsyncSession, make_user) -> None:
    """Admin must never be self-assignable through the ordinary data layer."""
    from app.models import UserRole
    from app.repositories import UserRepository

    user = await make_user("9000000005")
    repository = UserRepository(session)
    # Both the enum member and a raw string must be refused.
    with pytest.raises(PermissionError):
        await repository.add_role(user.id, UserRole.ADMIN)
    with pytest.raises(PermissionError):
        await repository.add_role(user.id, "admin")


async def test_repository_allows_normal_roles(session: AsyncSession, make_user) -> None:
    from app.models import UserRole
    from app.repositories import UserRepository

    user = await make_user("9000000008")
    await UserRepository(session).add_role(user.id, UserRole.FARMER)
    await session.commit()

    roles = await UserRepository(session).list_roles(user.id)
    assert roles == {UserRole.FARMER}
    assert await UserRepository(session).has_role(user.id, UserRole.FARMER) is True
    assert await UserRepository(session).has_role(user.id, UserRole.ADMIN) is False


async def test_otp_row_stores_hash_not_code(session: AsyncSession, make_user) -> None:
    from datetime import UTC, datetime, timedelta

    user = await make_user("9000000006")
    otp = OtpVerification(
        user_id=user.id,
        phone_e164=user.phone_e164,
        code_hash="0" * 64,
        salt="s" * 32,
        expires_at=datetime.now(UTC) + timedelta(minutes=5),
        cooldown_until=datetime.now(UTC) + timedelta(seconds=30),
    )
    session.add(otp)
    await session.commit()
    assert otp.code_hash != "123456"
    assert otp.status.value == "pending"


async def test_audit_log_round_trips_json_details(session: AsyncSession, make_user) -> None:
    from app.repositories import AuditRepository

    user = await make_user("9000000007")
    repo = AuditRepository(session)
    entry = await repo.record(
        action="user.created",
        entity_type="user",
        entity_id=user.id,
        actor_user_id=user.id,
        details={"role": "farmer"},
    )
    await session.commit()
    await session.refresh(entry)

    stored = await session.execute(select(AuditLog).where(AuditLog.id == entry.id))
    assert stored.scalar_one().details == {"role": "farmer"}