"""Shared pytest fixtures.

Isolation rules enforced here:

* ``ENVIRONMENT`` is forced to ``test`` **before** any application module is
  imported, so ``app.core.database`` refuses to use a real PostgreSQL DSN.
* Every test gets its OWN SQLite file under pytest's ``tmp_path``. A file (not
  ``:memory:``) is required because SQLite gives each in-memory connection a
  separate empty database, which breaks any test that opens more than one
  connection - the API test client always does.
* The file is deleted by pytest afterwards, so nothing leaks between tests and
  nothing can ever reach Supabase.

Requires ``pytest-asyncio`` in auto mode (see ``[tool.pytest.ini_options]``).
"""

import asyncio
import os

os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("DEBUG", "false")
# Dummy value only: tests never issue real tokens, but production-style
# configuration validation requires a non-empty secret.
os.environ.setdefault("SECRET_KEY", "test-only-secret-not-used-in-production")
os.environ.setdefault("POSTGRES_DSN", "")
os.environ.setdefault("SMS_PROVIDER", "mock")

import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker  # noqa: E402

from app.core.config import Settings, clear_settings_cache, get_settings  # noqa: E402
from app.core.database import (  # noqa: E402
    Base,
    dispose_engine,
    get_engine,
    init_engine,
)
from app.main import create_app  # noqa: E402
from app.models import User  # noqa: E402


def _sqlite_url(path) -> str:
    return f"sqlite+aiosqlite:///{path.as_posix()}"


def _run(coro):
    """Run a coroutine to completion from a synchronous fixture."""
    return asyncio.run(coro)


async def _create_all_tables() -> None:
    engine = get_engine()
    assert engine is not None
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)


@pytest.fixture(scope="session")
def settings() -> Settings:
    clear_settings_cache()
    return Settings(_env_file=None)


@pytest_asyncio.fixture
async def engine(tmp_path):
    """Per-test async engine with every table created."""
    test_settings = Settings(_env_file=None, TEST_DATABASE_URL=_sqlite_url(tmp_path / "unit.db"))
    test_engine = init_engine(test_settings)
    assert test_engine is not None, "Test engine failed to initialise"
    async with test_engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    try:
        yield test_engine
    finally:
        await dispose_engine()


@pytest_asyncio.fixture
async def session(engine) -> AsyncSession:
    """Per-test session inside a transaction that is always rolled back.

    ``join_transaction_mode="create_savepoint"`` matters: without it, a
    ``session.commit()`` inside a test rolls all the way back to the outer
    transaction, so code that deliberately commits part of its work (for
    example the reference importer persisting its source before a dry-run
    rollback) appears broken even though it is correct in production. With
    savepoints, an inner commit/rollback behaves exactly as it does against a
    real database while the outer transaction still isolates the test.
    """
    connection = await engine.connect()
    transaction = await connection.begin()
    factory = async_sessionmaker(
        bind=connection,
        expire_on_commit=False,
        class_=AsyncSession,
        join_transaction_mode="create_savepoint",
    )
    async with factory() as test_session:
        yield test_session
    await transaction.rollback()
    await connection.close()


@pytest_asyncio.fixture
async def make_user(session: AsyncSession):
    """Async factory creating persisted users with unique 10-digit phone numbers.

    ``phone_suffix`` must be exactly 10 digits starting with 9, e.g. "9000000001".
    """

    async def _make(phone_suffix: str, display_name: str = "Test User") -> User:
        assert len(phone_suffix) == 10 and phone_suffix[0] == "9", (
            "Test phone suffix must be 10 digits starting with 9."
        )
        user = User(phone_e164=f"+91{phone_suffix}", display_name=display_name)
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user

    return _make


@pytest.fixture()
def client(tmp_path, monkeypatch) -> TestClient:
    """TestClient backed by a fresh SQLite file for this test only.

    The engine and tables are created before the app starts, so every request in
    the test talks to a real, isolated database.
    """
    monkeypatch.setenv("TEST_DATABASE_URL", _sqlite_url(tmp_path / "api.db"))
    clear_settings_cache()

    test_settings = get_settings()
    assert init_engine(test_settings) is not None
    _run(_create_all_tables())

    app = create_app()
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        _run(dispose_engine())
        clear_settings_cache()