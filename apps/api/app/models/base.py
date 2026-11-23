"""Shared column helpers and enumerations for AgriPredict AI models."""

from datetime import UTC, datetime
from enum import StrEnum

from sqlalchemy import DateTime, Enum as SAEnum, func
from sqlalchemy.orm import Mapped, mapped_column


class UserRole(StrEnum):
    """The five platform roles. A user may hold more than one."""

    FARMER = "farmer"
    BUYER = "buyer"
    TRANSPORT_PROVIDER = "transport_provider"
    STORAGE_PROVIDER = "storage_provider"
    ADMIN = "admin"


class LocaleCode(StrEnum):
    EN = "en"
    HI = "hi"
    TE = "te"


class UserStatus(StrEnum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    DEACTIVATED = "deactivated"


class OtpPurpose(StrEnum):
    LOGIN = "login"
    PHONE_CHANGE = "phone_change"
    SENSITIVE_ACTION = "sensitive_action"


class OtpStatus(StrEnum):
    PENDING = "pending"
    VERIFIED = "verified"
    EXPIRED = "expired"
    FAILED = "failed"


class ProfileStatus(StrEnum):
    DRAFT = "draft"
    PENDING_REVIEW = "pending_review"
    VERIFIED = "verified"
    REJECTED = "rejected"


def sa_enum(enum_cls: type[StrEnum], name: str) -> SAEnum:
    """Build a reusable named Enum column type.

    ``native_enum=False`` stores values as VARCHAR + CHECK so the schema stays
    portable and Alembic autogenerate produces simpler migrations.
    """
    return SAEnum(
        enum_cls,
        name=name,
        native_enum=False,
        validate_strings=True,
        values_callable=lambda e: [member.value for member in e],
    )


class TimestampMixin:
    """``created_at`` / ``updated_at`` maintained by the database clock."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


def utcnow() -> datetime:
    """Timezone-aware UTC now. Used where a server default is not available."""
    return datetime.now(UTC)