"""Identity models: users, roles and role-specific profiles (Phase 3).

Privacy notes that are enforced by the schema, not just by convention:
- ``phone_e164`` is unique but never selected into API responses directly; the
  Pydantic schemas expose a masked form only.
- ``contact_phone_visible`` defaults to ``False`` so phone sharing is opt-in.
- Admin is a role like any other; assignment happens only through a privileged,
  audited service call added in Phase 15.
"""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

if TYPE_CHECKING:  # Imported for typing only; avoids a circular import at runtime.
    from .lots import ProduceLot
    from .reference import ReferenceImportLog

from ..core.database import Base
from .base import (
    LocaleCode,
    ProfileStatus,
    TimestampMixin,
    UserRole,
    UserStatus,
    sa_enum,
    utcnow,
)


class User(Base, TimestampMixin):
    """A platform account, identified by a verified phone number."""

    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("phone_e164", name="uq_users_phone_e164"),
        # '+91' + 10 national digits = 13 characters exactly.
        CheckConstraint("length(phone_e164) = 13", name="ck_users_phone_e164_length"),
        CheckConstraint(
            "phone_e164 LIKE '+91%'", name="ck_users_phone_e164_country"
        ),
        Index("ix_users_status", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # Stored as '+91' + 10 national digits (13 characters).
    # Never logged, never returned raw.
    phone_e164: Mapped[str] = mapped_column(String(13), nullable=False)
    phone_verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    status: Mapped[UserStatus] = mapped_column(
        sa_enum(UserStatus, "user_status"), nullable=False, default=UserStatus.ACTIVE
    )
    preferred_locale: Mapped[LocaleCode] = mapped_column(
        sa_enum(LocaleCode, "locale_code"), nullable=False, default=LocaleCode.EN
    )
    display_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    last_login_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # Set by an admin moderation action; never by the user themselves.
    suspended_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)

    roles: Mapped[list["UserRoleAssignment"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="selectin",
        # users -> user_roles has TWO possible FK paths (user_id and
        # granted_by_id), so the join condition must be stated explicitly.
        foreign_keys="UserRoleAssignment.user_id",
    )
    farmer_profile: Mapped["FarmerProfile | None"] = relationship(
        back_populates="user", cascade="all, delete-orphan", uselist=False
    )
    buyer_profile: Mapped["BuyerProfile | None"] = relationship(
        back_populates="user", cascade="all, delete-orphan", uselist=False
    )
    # A farmer may run several lots at once, each with its own status.
    produce_lots: Mapped[list["ProduceLot"]] = relationship(
        back_populates="farmer", cascade="all, delete-orphan"
    )
    # Import runs this user performed (admin reference imports, Phase 5).
    # No cascade: ON DELETE SET NULL keeps the log if the account is erased.
    reference_import_logs: Mapped[list["ReferenceImportLog"]] = relationship(
        back_populates="performed_by",
        foreign_keys="ReferenceImportLog.performed_by_user_id",
    )


class UserRoleAssignment(Base, TimestampMixin):
    """Join table supporting multiple roles per user."""

    __tablename__ = "user_roles"
    __table_args__ = (
        UniqueConstraint("user_id", "role", name="uq_user_roles_user_role"),
        Index("ix_user_roles_role", "role"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[UserRole] = mapped_column(sa_enum(UserRole, "user_role"), nullable=False)
    # Phase 4 uses this to mark admin grants; kept now so the audit trail is complete.
    granted_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    granted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )

    user: Mapped[User] = relationship(
        back_populates="roles",
        foreign_keys=[user_id],
    )


class FarmerProfile(Base, TimestampMixin):
    """Farmer details. An ordinary individual farmer uses this - no FPO needed."""

    __tablename__ = "farmer_profiles"
    __table_args__ = (
        UniqueConstraint("user_id", name="uq_farmer_profiles_user"),
        CheckConstraint("completion_percent BETWEEN 0 AND 100",
                        name="ck_farmer_profiles_completion"),
        Index("ix_farmer_profiles_status", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    full_name: Mapped[str] = mapped_column(String(150), nullable=False)
    # Optional organisation name: many farmers trade independently, some via an FPO.
    organisation_name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    preferred_language: Mapped[LocaleCode] = mapped_column(
        sa_enum(LocaleCode, "locale_code"), nullable=False, default=LocaleCode.EN
    )
    # Approximate administrative location chosen by the user in Phase 5.
    state_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    district_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    village_or_town: Mapped[str | None] = mapped_column(String(150), nullable=True)
    # The farmer's usual market. Optional: plenty of farmers sell through a
    # trader and never visit a mandi themselves.
    mandi_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Precise coordinates are optional, permission-based and never public (Phase 5).
    latitude: Mapped[float | None] = mapped_column(nullable=True)
    longitude: Mapped[float | None] = mapped_column(nullable=True)
    bank_account_last4: Mapped[str | None] = mapped_column(String(4), nullable=True)
    # Privacy controls - both default to the private setting.
    show_exact_location_to_buyers: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    contact_phone_visible: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    completion_percent: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    status: Mapped[ProfileStatus] = mapped_column(
        sa_enum(ProfileStatus, "profile_status"), nullable=False, default=ProfileStatus.DRAFT
    )
    bio: Mapped[str | None] = mapped_column(Text, nullable=True)

    user: Mapped[User] = relationship(back_populates="farmer_profile")


class BuyerProfile(Base, TimestampMixin):
    """Buyer or trader business details."""

    __tablename__ = "buyer_profiles"
    __table_args__ = (
        UniqueConstraint("user_id", name="uq_buyer_profiles_user"),
        Index("ix_buyer_profiles_status", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    business_name: Mapped[str] = mapped_column(String(200), nullable=False)
    contact_person_name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    business_type: Mapped[str | None] = mapped_column(String(80), nullable=True)
    gst_number: Mapped[str | None] = mapped_column(String(20), nullable=True)
    preferred_language: Mapped[LocaleCode] = mapped_column(
        sa_enum(LocaleCode, "locale_code"), nullable=False, default=LocaleCode.EN
    )
    state_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    district_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    address_line: Mapped[str | None] = mapped_column(String(300), nullable=True)
    contact_phone_visible: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    completion_percent: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    status: Mapped[ProfileStatus] = mapped_column(
        sa_enum(ProfileStatus, "profile_status"), nullable=False, default=ProfileStatus.DRAFT
    )

    user: Mapped[User] = relationship(back_populates="buyer_profile")