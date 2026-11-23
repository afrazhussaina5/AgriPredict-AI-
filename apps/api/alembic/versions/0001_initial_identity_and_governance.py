"""Initial identity and governance tables

Revision ID: 0001_initial
Revises:
Create Date: 2026-10-03

Creates users, user_roles, farmer_profiles and buyer_profiles.
OTP and audit tables follow in revision 0002.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

locale_code = sa.Enum("en", "hi", "te", name="locale_code", native_enum=False)
profile_status = sa.Enum(
    "draft", "pending_review", "verified", "rejected",
    name="profile_status", native_enum=False,
)
user_status = sa.Enum(
    "active", "suspended", "deactivated", name="user_status", native_enum=False
)
user_role = sa.Enum(
    "farmer", "buyer", "transport_provider", "storage_provider", "admin",
    name="user_role", native_enum=False,
)


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("phone_e164", sa.String(length=13), nullable=False),
        sa.Column("phone_verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", user_status, nullable=False, server_default="active"),
        sa.Column("preferred_locale", locale_code, nullable=False, server_default="en"),
        sa.Column("display_name", sa.String(length=120), nullable=True),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("suspended_reason", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.UniqueConstraint("phone_e164", name="uq_users_phone_e164"),
        sa.CheckConstraint("length(phone_e164) = 13", name="ck_users_phone_e164_length"),
        sa.CheckConstraint("phone_e164 LIKE '+91%'", name="ck_users_phone_e164_country"),
    )
    op.create_index("ix_users_status", "users", ["status"])

    op.create_table(
        "user_roles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("role", user_role, nullable=False),
        sa.Column("granted_by_id", sa.Integer(), nullable=True),
        sa.Column("granted_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["granted_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("user_id", "role", name="uq_user_roles_user_role"),
    )
    op.create_index("ix_user_roles_role", "user_roles", ["role"])

    op.create_table(
        "farmer_profiles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("full_name", sa.String(length=150), nullable=False),
        sa.Column("organisation_name", sa.String(length=150), nullable=True),
        sa.Column("preferred_language", locale_code, nullable=False, server_default="en"),
        sa.Column("state_id", sa.Integer(), nullable=True),
        sa.Column("district_id", sa.Integer(), nullable=True),
        sa.Column("village_or_town", sa.String(length=150), nullable=True),
        sa.Column("latitude", sa.Float(), nullable=True),
        sa.Column("longitude", sa.Float(), nullable=True),
        sa.Column("bank_account_last4", sa.String(length=4), nullable=True),
        sa.Column("show_exact_location_to_buyers", sa.Boolean(), nullable=False,
                  server_default=sa.false()),
        sa.Column("contact_phone_visible", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("completion_percent", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", profile_status, nullable=False, server_default="draft"),
        sa.Column("bio", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("user_id", name="uq_farmer_profiles_user"),
        sa.CheckConstraint("completion_percent BETWEEN 0 AND 100",
                           name="ck_farmer_profiles_completion"),
    )
    op.create_index("ix_farmer_profiles_status", "farmer_profiles", ["status"])

    op.create_table(
        "buyer_profiles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("business_name", sa.String(length=200), nullable=False),
        sa.Column("contact_person_name", sa.String(length=150), nullable=True),
        sa.Column("business_type", sa.String(length=80), nullable=True),
        sa.Column("gst_number", sa.String(length=20), nullable=True),
        sa.Column("preferred_language", locale_code, nullable=False, server_default="en"),
        sa.Column("state_id", sa.Integer(), nullable=True),
        sa.Column("district_id", sa.Integer(), nullable=True),
        sa.Column("address_line", sa.String(length=300), nullable=True),
        sa.Column("contact_phone_visible", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("completion_percent", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", profile_status, nullable=False, server_default="draft"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("user_id", name="uq_buyer_profiles_user"),
    )
    op.create_index("ix_buyer_profiles_status", "buyer_profiles", ["status"])


def downgrade() -> None:
    op.drop_index("ix_buyer_profiles_status", table_name="buyer_profiles")
    op.drop_table("buyer_profiles")
    op.drop_index("ix_farmer_profiles_status", table_name="farmer_profiles")
    op.drop_table("farmer_profiles")
    op.drop_index("ix_user_roles_role", table_name="user_roles")
    op.drop_table("user_roles")
    op.drop_index("ix_users_status", table_name="users")
    op.drop_table("users")