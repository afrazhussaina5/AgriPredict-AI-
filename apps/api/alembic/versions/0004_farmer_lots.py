"""Produce lots and lot status history (Phase 6)

Revision ID: 0004_farmer_lots
Revises: 0003_reference
Create Date: 2026-10-03

Adds the farmer's own produce lots: the unit of sale that offers (Phase 8),
transport (Phase 9), storage (Phase 10) and net realization (Phase 13) all hang
off. Every privacy-relevant column defaults to the hidden setting, and money is
Numeric rather than float so rupees keep their paise.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004_farmer_lots"
down_revision: str | None = "0003_reference"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

lot_status = sa.Enum(
    "draft", "published", "paused", "closed", "archived",
    name="lot_status", native_enum=False,
)


def upgrade() -> None:
    # The farmer's usual market. Nullable: many farmers never visit a mandi.
    op.add_column(
        "farmer_profiles",
        sa.Column("mandi_id", sa.Integer(), nullable=True),
    )

    op.create_table(
        "produce_lots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("farmer_id", sa.Integer(), nullable=False),
        sa.Column("commodity_id", sa.Integer(), nullable=False),
        sa.Column("variety_id", sa.Integer(), nullable=True),
        sa.Column("grade_id", sa.Integer(), nullable=True),
        sa.Column("quantity", sa.Numeric(precision=12, scale=3), nullable=False),
        sa.Column("unit_id", sa.Integer(), nullable=False),
        sa.Column("pickup_district_id", sa.Integer(), nullable=True),
        sa.Column("pickup_mandi_id", sa.Integer(), nullable=True),
        sa.Column("pickup_area_label", sa.String(length=150), nullable=True),
        sa.Column("ready_date", sa.Date(), nullable=False),
        sa.Column("expected_price_per_unit", sa.Numeric(precision=12, scale=2),
                  nullable=True),
        sa.Column("min_expected_price_per_unit", sa.Numeric(precision=12, scale=2),
                  nullable=True),
        # Privacy defaults: hidden unless the farmer explicitly opts in.
        sa.Column("show_expected_price", sa.Boolean(), nullable=False,
                  server_default=sa.false()),
        sa.Column("show_pickup_area", sa.Boolean(), nullable=False,
                  server_default=sa.false()),
        sa.Column("show_notes", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("status", lot_status, nullable=False, server_default="draft"),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_reason", sa.String(length=300), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["farmer_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["commodity_id"], ["reference_commodities.id"],
                                ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["variety_id"], ["reference_commodity_varieties.id"],
                                ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["grade_id"], ["reference_commodity_grades.id"],
                                ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["unit_id"], ["reference_units.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["pickup_district_id"], ["reference_districts.id"],
                                ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["pickup_mandi_id"], ["reference_mandis.id"],
                                ondelete="RESTRICT"),
        sa.CheckConstraint("quantity > 0", name="ck_produce_lots_quantity_positive"),
        sa.CheckConstraint(
            "expected_price_per_unit IS NULL OR expected_price_per_unit >= 0",
            name="ck_produce_lots_price_not_negative",
        ),
        sa.CheckConstraint(
            "min_expected_price_per_unit IS NULL OR expected_price_per_unit IS NULL "
            "OR min_expected_price_per_unit <= expected_price_per_unit",
            name="ck_produce_lots_price_range_ordered",
        ),
        sa.CheckConstraint(
            "(pickup_mandi_id IS NULL OR pickup_district_id IS NOT NULL)",
            name="ck_produce_lots_mandi_requires_district",
        ),
    )
    op.create_index("ix_produce_lots_farmer", "produce_lots",
                    ["farmer_id", "status", "created_at"])
    op.create_index("ix_produce_lots_public", "produce_lots", ["status", "ready_date"])
    op.create_index("ix_produce_lots_commodity", "produce_lots",
                    ["commodity_id", "status"])

    op.create_table(
        "produce_lot_status_history",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("lot_id", sa.Integer(), nullable=False),
        # Null only for the first entry, when the lot is created.
        sa.Column("from_status", lot_status, nullable=True),
        sa.Column("to_status", lot_status, nullable=False),
        sa.Column("changed_by_user_id", sa.Integer(), nullable=True),
        sa.Column("note", sa.String(length=300), nullable=True),
        sa.Column("changed_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["lot_id"], ["produce_lots.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["changed_by_user_id"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_produce_lot_history_lot", "produce_lot_status_history",
                    ["lot_id", "id"])


def downgrade() -> None:
    op.drop_index("ix_produce_lot_history_lot", table_name="produce_lot_status_history")
    op.drop_table("produce_lot_status_history")
    op.drop_index("ix_produce_lots_commodity", table_name="produce_lots")
    op.drop_index("ix_produce_lots_public", table_name="produce_lots")
    op.drop_index("ix_produce_lots_farmer", table_name="produce_lots")
    op.drop_table("produce_lots")
    op.drop_column("farmer_profiles", "mandi_id")