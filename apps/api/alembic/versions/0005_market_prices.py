"""Market prices and extract cache (Phase 6)

Revision ID: 0005_market_prices
Revises: 0004_farmer_lots
Create Date: 2026-10-05

The public mandi price board. Two rules are enforced by the schema rather
than by convention:

* The unique key spans commodity+grade+mandi+district+state+date+unit, so a
  re-import of the same business day is an upsert - never a duplicate row.
* ``modal_price`` is Numeric and may be NULL, never negative: NULL means "the
  source shipped no modal price", which the UI renders as blank rather than 0.

The cache row stores the last successful *extract* so ``/market/freshness``
answers without scanning ``market_prices``.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005_market_prices"
down_revision: str | None = "0004_farmer_lots"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "market_prices",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("commodity_id", sa.Integer(), nullable=False),
        # Nullable: the source row may carry no grade, rendered "not graded".
        sa.Column("grade_id", sa.Integer(), nullable=True),
        sa.Column("mandi_id", sa.Integer(), nullable=False),
        sa.Column("district_id", sa.Integer(), nullable=False),
        sa.Column("state_id", sa.Integer(), nullable=False),
        sa.Column("unit_id", sa.Integer(), nullable=False),
        sa.Column("market_date", sa.Date(), nullable=False),
        sa.Column("modal_price", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("arrivals", sa.Integer(), nullable=True),
        sa.Column("source_id", sa.Integer(), nullable=False),
        sa.Column(
            "imported_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("cache_key", sa.String(length=80), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["commodity_id"], ["reference_commodities.id"],
                                ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["grade_id"], ["reference_commodity_grades.id"],
                                ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["mandi_id"], ["reference_mandis.id"],
                                ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["district_id"], ["reference_districts.id"],
                                ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["state_id"], ["reference_states.id"],
                                ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["unit_id"], ["reference_units.id"],
                                ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["source_id"], ["reference_sources.id"],
                                ondelete="RESTRICT"),
        # Re-importing the same business day upserts, never duplicates.
        sa.UniqueConstraint(
            "commodity_id", "grade_id", "mandi_id", "district_id", "state_id",
            "market_date", "unit_id", name="uq_market_prices_key",
        ),
        sa.CheckConstraint(
            "modal_price IS NULL OR modal_price >= 0",
            name="ck_market_prices_non_negative",
        ),
    )
    op.create_index("ix_market_prices_state", "market_prices",
                    ["state_id", "market_date"])
    op.create_index("ix_market_prices_mandi", "market_prices",
                    ["mandi_id", "market_date"])
    op.create_index("ix_market_prices_date", "market_prices", ["market_date"])

    op.create_table(
        "market_price_cache",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("key", sa.String(length=80), nullable=False),
        # JSON document as text so SQLite (tests) and PostgreSQL read the
        # same bytes; the freshness endpoint parses it directly.
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.UniqueConstraint("key", name="uq_market_price_cache_key"),
    )


def downgrade() -> None:
    op.drop_table("market_price_cache")
    op.drop_index("ix_market_prices_date", table_name="market_prices")
    op.drop_index("ix_market_prices_mandi", table_name="market_prices")
    op.drop_index("ix_market_prices_state", table_name="market_prices")
    op.drop_table("market_prices")
