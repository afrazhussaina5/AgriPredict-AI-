"""Alembic migrations must actually run.

The rest of the suite creates tables with ``Base.metadata.create_all``, which
never exercises the migration scripts. That let a PostgreSQL-only
``'{}'::jsonb`` server default ship in migration 0002 and break every local
migration run without a single test noticing.

These tests run the real ``alembic upgrade head`` / ``downgrade base`` against a
throwaway SQLite file, so a migration that cannot be applied is a failing test
rather than a surprise during setup.
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy import inspect, text

API_ROOT = Path(__file__).resolve().parent.parent


def _alembic_env(database_url: str) -> dict[str, str]:
    """Environment for an Alembic run isolated to ``database_url``."""
    env = dict(os.environ)
    env.update(
        ENVIRONMENT="test",
        TEST_DATABASE_URL=database_url,
        SECRET_KEY="test-only-secret-not-used-in-production",
        POSTGRES_DSN="",
        SMS_PROVIDER="mock",
        PYTHONIOENCODING="utf-8",
    )
    return env


def _run_alembic(args: list[str], database_url: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=API_ROOT,
        env=_alembic_env(database_url),
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=300,
        check=False,
    )


@pytest.fixture(scope="module")
def migrated_database(tmp_path_factory) -> str:
    """A SQLite file with every migration applied, plus its URL."""
    path = tmp_path_factory.mktemp("alembic") / "migrations.db"
    url = f"sqlite+aiosqlite:///{path.as_posix()}"

    result = _run_alembic(["upgrade", "head"], url)
    assert result.returncode == 0, (
        "alembic upgrade head failed.\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    return url


def test_every_migration_applies_to_a_fresh_database(migrated_database: str) -> None:
    """Phase 0-6 migrations must all apply in order on an empty database."""
    import asyncio

    from app.core.database import create_engine_for

    async def _tables() -> list[str]:
        settings_engine = create_engine_for(_settings(migrated_database))
        try:
            async with settings_engine.connect() as connection:
                return await connection.run_sync(
                    lambda sync_connection: inspect(sync_connection).get_table_names()
                )
        finally:
            await settings_engine.dispose()

    tables = set(asyncio.run(_tables()))
    expected = {
        "users", "user_roles", "farmer_profiles", "buyer_profiles",
        "otp_verifications", "audit_logs",
        "reference_sources", "reference_states", "reference_districts",
        "reference_localities", "reference_mandis", "reference_commodities",
        "reference_commodity_varieties", "reference_commodity_grades",
        "reference_units", "reference_import_logs",
        "produce_lots", "produce_lot_status_history",
        "market_prices", "market_price_cache",
    }
    missing = expected - tables
    assert not missing, f"Migrations did not create: {sorted(missing)}"


def _settings(database_url: str):
    from app.core.config import Settings

    return Settings(_env_file=None, TEST_DATABASE_URL=database_url)


def test_audit_details_default_is_valid_on_sqlite(migrated_database: str) -> None:
    """The audit ``details`` column defaults to an empty JSON object.

    Regression test for a PostgreSQL-only ``'{}'::jsonb`` default that made
    migration 0002 impossible to apply on SQLite.
    """
    import asyncio

    from sqlalchemy.ext.asyncio import create_async_engine

    async def _check() -> object:
        engine = create_async_engine(migrated_database)
        try:
            async with engine.begin() as connection:
                await connection.execute(
                    text(
                        "INSERT INTO audit_logs (actor_role, action, entity_type, "
                        "result, created_at) VALUES ('admin', 'test.action', "
                        "'test', 'success', datetime('now'))"
                    )
                )
                result = await connection.execute(
                    text("SELECT details FROM audit_logs WHERE action = 'test.action'")
                )
                return result.scalar_one()
        finally:
            await engine.dispose()

    assert asyncio.run(_check()) == "{}"


def test_migrations_can_be_fully_reverted(tmp_path) -> None:
    """``downgrade base`` must undo every migration without error."""
    path = tmp_path / "downgrade.db"
    url = f"sqlite+aiosqlite:///{path.as_posix()}"

    up = _run_alembic(["upgrade", "head"], url)
    assert up.returncode == 0, f"upgrade failed:\n{up.stderr}"

    down = _run_alembic(["downgrade", "base"], url)
    assert down.returncode == 0, f"downgrade failed:\n{down.stderr}"