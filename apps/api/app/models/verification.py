"""Verification records and audit trail (Phase 3).

Security decisions baked into the schema:
- ``code_hash`` stores a salted SHA-256/HMAC digest, never the OTP itself.
- ``request_ip`` is stored truncated and is never returned by any endpoint.
- Audit payloads are JSON with a size cap so a request body cannot bloat the
  table, and they are written inside the same transaction as the change.
"""

from datetime import datetime
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from ..core.database import Base
from .base import (
    OtpPurpose,
    OtpStatus,
    TimestampMixin,
    UserRole,
    sa_enum,
    utcnow,
)


class OtpVerification(Base, TimestampMixin):
    """A single OTP challenge. The plaintext code is never stored."""

    __tablename__ = "otp_verifications"
    __table_args__ = (
        UniqueConstraint("user_id", "purpose", name="uq_otp_user_purpose_active"),
        Index("ix_otp_user_status", "user_id", "status"),
        Index("ix_otp_expires_at", "expires_at"),
        CheckConstraint("attempt_count >= 0", name="ck_otp_attempt_count"),
        CheckConstraint("attempt_count <= 10", name="ck_otp_attempt_count_max"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    phone_e164: Mapped[str] = mapped_column(String(13), nullable=False)
    purpose: Mapped[OtpPurpose] = mapped_column(
        sa_enum(OtpPurpose, "otp_purpose"), nullable=False, default=OtpPurpose.LOGIN
    )
    # HMAC-SHA256 of the code with SECRET_KEY. Irreversible without the secret.
    code_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    salt: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[OtpStatus] = mapped_column(
        sa_enum(OtpStatus, "otp_status"), nullable=False, default=OtpStatus.PENDING
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    # Blocks resends; enforced again in the service layer in Phase 4.
    cooldown_until: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    # Sliding one-hour request window. The unique constraint above allows only
    # one row per (user, purpose), so counting rows would collapse every resend
    # into a single request and make the rate limit useless. These two columns
    # record how many codes were actually issued in the current window.
    window_started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
    window_request_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    consumed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # Provider metadata only - never the message body or the code.
    provider_name: Mapped[str | None] = mapped_column(String(40), nullable=True)
    provider_message_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    request_ip: Mapped[str | None] = mapped_column(String(45), nullable=True)


class AuditLog(Base):
    """Append-only record of privileged or state-changing actions.

    Written by the service layer in the same transaction as the business change
    so the trail cannot drift from reality. Rows are never updated or deleted by
    application code.
    """

    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("ix_audit_actor_created", "actor_user_id", "created_at"),
        Index("ix_audit_action_created", "action", "created_at"),
        Index("ix_audit_entity", "entity_type", "entity_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    actor_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    actor_role: Mapped[UserRole | None] = mapped_column(
        sa_enum(UserRole, "user_role"), nullable=True
    )
    action: Mapped[str] = mapped_column(String(80), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(60), nullable=False)
    entity_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # JSONB on PostgreSQL; plain JSON elsewhere so tests can run on SQLite.
    details: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), nullable=False, default=dict
    )
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(300), nullable=True)
    result: Mapped[str] = mapped_column(String(20), nullable=False, default="success")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)