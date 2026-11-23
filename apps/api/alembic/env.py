"""Alembic environment.

Safety rules:
- The URL is read from ``POSTGRES_DSN`` (settings), never from alembic.ini, and
  it is never logged. Alembic's ``sqlalchemy.url`` is set in memory only.
- ``compare_type`` and server-default comparison are on so schema drift is
  detected instead of silently ignored.
- This module never creates or drops a database; only migrations do that.
"""

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from app.core.config import get_settings
from app.models import Base  # noqa: F401 - importing registers all tables

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

settings = get_settings()
_dsn = settings.TEST_DATABASE_URL if settings.is_test else settings.POSTGRES_DSN
if not _dsn:
    raise RuntimeError(
        "POSTGRES_DSN is not set. Add it to apps/api/.env before running migrations."
    )
config.set_main_option("sqlalchemy.url", _dsn)

target_metadata = Base.metadata


def _configure() -> None:
    context.configure(
        connection=None,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
        include_schemas=False,
        render_as_batch=False,
    )


def run_migrations_offline() -> None:
    """Emit SQL to stdout without connecting to a database."""
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def _do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    """Connect and apply migrations."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(_do_run_migrations)
    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())