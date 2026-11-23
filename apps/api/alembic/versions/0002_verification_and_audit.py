"""OTP verification and audit log tables

Revision ID: 0002_verification_audit
Revises: 0001_initial
Create Date: 2026-10-03

The OTP table stores only a salted hash of the code - never the code itself.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002_verification_audit"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

otp_purpose = sa.Enum("login", "phone_change", "sensitive_action",
                      name="otp_purpose", native_enum=False)
otp_status = sa.Enum("pending", "verified", "expired", "failed",
                     name="otp_status", native_enum=False)
user_role = sa.Enum(
    "farmer", "buyer", "transport_provider", "storage_provider", "admin",
    name="user_role", native_enum=False,
)


def upgrade() -> None:
    op.create_table(
        "otp_verifications",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("phone_e164", sa.String(length=13), nullable=False),
        sa.Column("purpose", otp_purpose, nullable=False, server_default="login"),
        sa.Column("code_hash", sa.String(length=64), nullable=False),
        sa.Column("salt", sa.String(length=32), nullable=False),
        sa.Column("status", otp_status, nullable=False, server_default="pending"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("cooldown_until", sa.DateTime(timezone=True), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="5"),
        # Sliding one-hour request window used for rate limiting.
        sa.Column("window_started_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.Column("window_request_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("provider_name", sa.String(length=40), nullable=True),
        sa.Column("provider_message_id", sa.String(length=120), nullable=True),
        sa.Column("request_ip", sa.String(length=45), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("user_id", "purpose", name="uq_otp_user_purpose_active"),
        sa.CheckConstraint("attempt_count >= 0", name="ck_otp_attempt_count"),
        sa.CheckConstraint("attempt_count <= 10", name="ck_otp_attempt_count_max"),
    )
    op.create_index("ix_otp_user_status", "otp_verifications", ["user_id", "status"])
    op.create_index("ix_otp_expires_at", "otp_verifications", ["expires_at"])

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("actor_user_id", sa.Integer(), nullable=True),
        sa.Column("actor_role", user_role, nullable=True),
        sa.Column("action", sa.String(length=80), nullable=False),
        sa.Column("entity_type", sa.String(length=60), nullable=False),
        sa.Column("entity_id", sa.String(length=64), nullable=True),
        # JSONB on PostgreSQL; JSON elsewhere keeps the type portable.
        # The DEFAULT must stay portable too: a literal `'{}'` is coerced to
        # jsonb by PostgreSQL and is valid JSON for SQLite. An explicit
        # `'{}'::jsonb` cast is PostgreSQL-only syntax and makes this migration
        # fail outright on SQLite, so it is deliberately not used.
        sa.Column("details",
                  sa.JSON().with_variant(postgresql.JSONB, "postgresql"),
                  nullable=False, server_default=sa.text("'{}'")),
        sa.Column("ip_address", sa.String(length=45), nullable=True),
        sa.Column("user_agent", sa.String(length=300), nullable=True),
        sa.Column("result", sa.String(length=20), nullable=False, server_default="success"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.Column("description", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_audit_actor_created", "audit_logs", ["actor_user_id", "created_at"])
    op.create_index("ix_audit_action_created", "audit_logs", ["action", "created_at"])
    op.create_index("ix_audit_entity", "audit_logs", ["entity_type", "entity_id"])


def downgrade() -> None:
    op.drop_index("ix_audit_entity", table_name="audit_logs")
    op.drop_index("ix_audit_action_created", table_name="audit_logs")
    op.drop_index("ix_audit_actor_created", table_name="audit_logs")
    op.drop_table("audit_logs")
    op.drop_index("ix_otp_expires_at", table_name="otp_verifications")
    op.drop_index("ix_otp_user_status", table_name="otp_verifications")
    op.drop_table("otp_verifications")