"""Async SQLAlchemy engine, session factory and FastAPI dependency.

Rules enforced here:
- The URL is never logged. Only :func:`app.core.config.describe_database_target`
  output (host/port/database) is safe to print.
- ``ENVIRONMENT=test`` forces an isolated in-memory SQLite database so tests can
  never touch Supabase.
- Sessions are read-only by default unless the caller explicitly asks for a
  write, and a read-only session always rolls back.
"""

from collections.abc import AsyncIterator

from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from .config import Settings, get_settings
from .logging import get_logger

logger = get_logger(__name__)


class Base(DeclarativeBase):
    """Declarative base for every AgriPredict AI ORM model."""


_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def resolve_engine_url(settings: Settings) -> str | None:
    """Return the async SQLAlchemy URL to use, or ``None`` when unconfigured.

    In test mode a non-SQLite ``TEST_DATABASE_URL`` is ignored on purpose: a
    stray value in a developer's local ``.env`` must never be able to point the
    test suite at a real database.
    """
    if settings.is_test:
        candidate = settings.TEST_DATABASE_URL
        if candidate.startswith("sqlite"):
            return candidate
        logger.warning("TEST_DATABASE_URL is not SQLite; falling back to in-memory SQLite.")
        return "sqlite+aiosqlite:///:memory:"
    return settings.POSTGRES_DSN or None


def create_engine_for(settings: Settings) -> AsyncEngine:
    """Build a new engine. Used by the app and by tests."""
    url = resolve_engine_url(settings)
    if url is None:
        raise RuntimeError("No database URL configured (POSTGRES_DSN is empty).")

    kwargs: dict[str, object] = {"echo": settings.DB_ECHO, "future": True}
    if not url.startswith("sqlite"):
        kwargs.update(
            pool_size=settings.DB_POOL_SIZE,
            max_overflow=settings.DB_MAX_OVERFLOW,
            pool_timeout=settings.DB_POOL_TIMEOUT_SECONDS,
            pool_pre_ping=True,
        )
    engine = create_async_engine(url, **kwargs)

    if url.startswith("sqlite"):
        # SQLite ships with foreign-key enforcement OFF, which silently
        # disables every ON DELETE CASCADE / SET NULL in the schema. Turning it
        # on per connection makes local development and the test suite actually
        # enforce the referential rules the models declare. PostgreSQL always
        # enforces them, so this only closes the SQLite/Postgres gap.
        @event.listens_for(engine.sync_engine, "connect")
        def _enable_sqlite_foreign_keys(dbapi_connection, _record) -> None:
            cursor = dbapi_connection.cursor()
            try:
                cursor.execute("PRAGMA foreign_keys=ON")
            finally:
                cursor.close()

    return engine


def get_engine() -> AsyncEngine | None:
    """Return the process-wide engine, or ``None`` if the DB is not configured."""
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession] | None:
    return _session_factory


def init_engine(settings: Settings | None = None) -> AsyncEngine | None:
    """Create the engine/session factory once per process. Idempotent."""
    global _engine, _session_factory
    if _engine is not None:
        return _engine

    resolved = settings or get_settings()
    url = resolve_engine_url(resolved)
    if url is None:
        logger.warning("Database not configured; running without a database.")
        return None

    _engine = create_engine_for(resolved)
    _session_factory = async_sessionmaker(_engine, expire_on_commit=False, class_=AsyncSession)
    # Only the safe description is logged - never the DSN.
    from .config import describe_database_target

    logger.info("Database engine ready: %s", describe_database_target(resolved))
    return _engine


async def dispose_engine() -> None:
    """Close pooled connections on shutdown."""
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
    _engine = None
    _session_factory = None


async def get_db() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency yielding a session.

    The session is rolled back on exit unless the route commits explicitly, so a
    failed request can never leave a half-written transaction behind.
    """
    factory = _session_factory
    if factory is None:
        raise RuntimeError("Database is not initialised. Call init_engine() first.")

    session = factory()
    try:
        yield session
        await session.rollback()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()


async def check_connection() -> tuple[bool, str | None]:
    """Probe the database with ``SELECT 1``. Never raises, never leaks the URL."""
    engine = get_engine()
    if engine is None:
        return False, "Database is not configured."

    from sqlalchemy import text

    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
    except Exception as exc:
        # exc may embed the DSN, so report only the exception class name.
        return False, f"Connection failed ({type(exc).__name__})."
    return True, None