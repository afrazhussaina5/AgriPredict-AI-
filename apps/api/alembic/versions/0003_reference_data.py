"""Reference data tables (states, districts, localities, mandis, commodities)

Revision ID: 0003_reference
Revises: 0002_verification_audit
Create Date: 2026-10-03

Every table records source_id so imported data is always traceable, and status
defaults to 'imported' - nothing becomes 'verified' automatically.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003_reference"
down_revision: str | None = "0002_verification_audit"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

verification_status = sa.Enum(
    "imported", "verified", "disputed", "retired",
    name="verification_status", native_enum=False,
)
locality_kind = sa.Enum("city", "town", "village", name="locality_kind", native_enum=False)
unit_dimension = sa.Enum(
    "mass", "volume", "count", "bag", name="unit_dimension", native_enum=False
)

def _timestamp_column(name: str) -> sa.Column:
    return sa.Column(
        name, sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    )


TIMESTAMP_COLUMNS = (
    _timestamp_column("created_at"),
    _timestamp_column("updated_at"),
)

STATUS_COLUMNS = (
    sa.Column("status", verification_status, nullable=False, server_default="imported"),
    sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
)



def upgrade() -> None:
    op.create_table(
        "reference_sources",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source_key", sa.String(length=60), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("url", sa.String(length=500), nullable=True),
        sa.Column("publisher", sa.String(length=200), nullable=True),
        sa.Column("is_official", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("license_notes", sa.String(length=500), nullable=True),
        sa.Column("status", verification_status, nullable=False, server_default="imported"),
        sa.Column("last_imported_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.String(length=500), nullable=True),
        *TIMESTAMP_COLUMNS,
        sa.UniqueConstraint("source_key", name="uq_reference_sources_key"),
        sa.CheckConstraint("length(trim(source_key)) > 0", name="ck_reference_sources_key"),
    )

    op.create_table(
        "reference_states",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(length=8), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("name_hi", sa.String(length=200), nullable=True),
        sa.Column("name_te", sa.String(length=200), nullable=True),
        sa.Column("source_id", sa.Integer(), nullable=False),
        *STATUS_COLUMNS,
        *TIMESTAMP_COLUMNS,
        sa.ForeignKeyConstraint(["source_id"], ["reference_sources.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("code", name="uq_reference_states_code"),
    )
    op.create_index("ix_reference_states_status", "reference_states", ["status"])

    op.create_table(
        "reference_districts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("state_id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=16), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("name_hi", sa.String(length=200), nullable=True),
        sa.Column("name_te", sa.String(length=200), nullable=True),
        sa.Column("source_id", sa.Integer(), nullable=False),
        *STATUS_COLUMNS,
        *TIMESTAMP_COLUMNS,
        sa.ForeignKeyConstraint(["state_id"], ["reference_states.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_id"], ["reference_sources.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("state_id", "code", name="uq_reference_districts_state_code"),
    )
    op.create_index(
        "ix_reference_districts_state", "reference_districts", ["state_id", "is_active"]
    )

    op.create_table(
        "reference_localities",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("district_id", sa.Integer(), nullable=False),
        sa.Column("kind", locality_kind, nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("name_hi", sa.String(length=200), nullable=True),
        sa.Column("name_te", sa.String(length=200), nullable=True),
        sa.Column("latitude", sa.Numeric(precision=9, scale=6), nullable=True),
        sa.Column("longitude", sa.Numeric(precision=9, scale=6), nullable=True),
        sa.Column("source_id", sa.Integer(), nullable=False),
        *STATUS_COLUMNS,
        *TIMESTAMP_COLUMNS,
        sa.ForeignKeyConstraint(["district_id"], ["reference_districts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_id"], ["reference_sources.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("district_id", "kind", "name", name="uq_reference_localities_name"),
    )
    op.create_index(
        "ix_reference_localities_district", "reference_localities", ["district_id", "is_active"]
    )

    op.create_table(
        "reference_mandis",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("district_id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("name_hi", sa.String(length=200), nullable=True),
        sa.Column("name_te", sa.String(length=200), nullable=True),
        sa.Column("has_storage", sa.Boolean(), nullable=True),
        sa.Column("source_id", sa.Integer(), nullable=False),
        *STATUS_COLUMNS,
        *TIMESTAMP_COLUMNS,
        sa.ForeignKeyConstraint(["district_id"], ["reference_districts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_id"], ["reference_sources.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("code", name="uq_reference_mandis_code"),
    )
    op.create_index(
        "ix_reference_mandis_district", "reference_mandis", ["district_id", "is_active"]
    )

    op.create_table(
        "reference_commodities",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("name_hi", sa.String(length=200), nullable=True),
        sa.Column("name_te", sa.String(length=200), nullable=True),
        sa.Column("category", sa.String(length=80), nullable=True),
        sa.Column("source_id", sa.Integer(), nullable=False),
        *STATUS_COLUMNS,
        *TIMESTAMP_COLUMNS,
        sa.ForeignKeyConstraint(["source_id"], ["reference_sources.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("code", name="uq_reference_commodities_code"),
    )
    op.create_index("ix_reference_commodities_status", "reference_commodities", ["status"])

    op.create_table(
        "reference_commodity_varieties",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("commodity_id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("name_hi", sa.String(length=200), nullable=True),
        sa.Column("name_te", sa.String(length=200), nullable=True),
        sa.Column("source_id", sa.Integer(), nullable=False),
        *STATUS_COLUMNS,
        *TIMESTAMP_COLUMNS,
        sa.ForeignKeyConstraint(["commodity_id"], ["reference_commodities.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_id"], ["reference_sources.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint(
            "commodity_id", "code", name="uq_reference_varieties_commodity_code"
        ),
    )
    op.create_index(
        "ix_reference_varieties_commodity",
        "reference_commodity_varieties",
        ["commodity_id", "is_active"],
    )

    op.create_table(
        "reference_commodity_grades",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("commodity_id", sa.Integer(), nullable=True),
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("name_hi", sa.String(length=200), nullable=True),
        sa.Column("name_te", sa.String(length=200), nullable=True),
        sa.Column("source_id", sa.Integer(), nullable=False),
        *STATUS_COLUMNS,
        *TIMESTAMP_COLUMNS,
        sa.ForeignKeyConstraint(["commodity_id"], ["reference_commodities.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_id"], ["reference_sources.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("commodity_id", "code", name="uq_reference_grades_commodity_code"),
    )
    op.create_index(
        "ix_reference_grades_commodity",
        "reference_commodity_grades",
        ["commodity_id", "is_active"],
    )

    op.create_table(
        "reference_units",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(length=24), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("name_hi", sa.String(length=80), nullable=True),
        sa.Column("name_te", sa.String(length=80), nullable=True),
        sa.Column("dimension", unit_dimension, nullable=False),
        # Kilograms represented by one of this unit. Null for non-mass units.
        sa.Column("to_base_kg", sa.Numeric(precision=12, scale=4), nullable=True),
        sa.Column("source_id", sa.Integer(), nullable=False),
        *STATUS_COLUMNS,
        *TIMESTAMP_COLUMNS,
        sa.ForeignKeyConstraint(["source_id"], ["reference_sources.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("code", name="uq_reference_units_code"),
        sa.CheckConstraint(
            "dimension <> 'mass' OR to_base_kg IS NOT NULL",
            name="ck_reference_units_mass_requires_conversion",
        ),
    )

    op.create_table(
        "reference_import_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source_id", sa.Integer(), nullable=False),
        sa.Column("entity_type", sa.String(length=40), nullable=False),
        sa.Column("filename", sa.String(length=300), nullable=True),
        sa.Column("row_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("inserted_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("updated_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("skipped_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("rejected_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("rejection_summary", sa.String(length=1000), nullable=True),
        sa.Column("dry_run", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("performed_by_user_id", sa.Integer(), nullable=True),
        sa.Column("imported_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["source_id"], ["reference_sources.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["performed_by_user_id"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index(
        "ix_reference_import_logs_source", "reference_import_logs", ["source_id", "imported_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_reference_import_logs_source", table_name="reference_import_logs")
    op.drop_table("reference_import_logs")
    op.drop_table("reference_units")
    op.drop_index("ix_reference_grades_commodity", table_name="reference_commodity_grades")
    op.drop_table("reference_commodity_grades")
    op.drop_index("ix_reference_varieties_commodity", table_name="reference_commodity_varieties")
    op.drop_table("reference_commodity_varieties")
    op.drop_index("ix_reference_commodities_status", table_name="reference_commodities")
    op.drop_table("reference_commodities")
    op.drop_index("ix_reference_mandis_district", table_name="reference_mandis")
    op.drop_table("reference_mandis")
    op.drop_index("ix_reference_localities_district", table_name="reference_localities")
    op.drop_table("reference_localities")
    op.drop_index("ix_reference_districts_state", table_name="reference_districts")
    op.drop_table("reference_districts")
    op.drop_index("ix_reference_states_status", table_name="reference_states")
    op.drop_table("reference_states")
    op.drop_table("reference_sources")