# AgriPredict AI - Database Core
"""
Database connection, session management, and base model.
"""

import os
from contextlib import contextmanager
from typing import Generator, Optional

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker, Session
from sqlalchemy.pool import NullPool

# Load environment variables
from dotenv import load_dotenv

_current_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.abspath(os.path.join(_current_dir, "..", ".."))
_dotenv_path = os.path.join(_project_root, ".env")

if os.path.exists(_dotenv_path):
    load_dotenv(dotenv_path=_dotenv_path)
else:
    load_dotenv()


class Base(DeclarativeBase):
    """Base class for all ORM models."""
    pass


def get_database_url() -> str:
    """Get database URL from environment with validation."""
    url = os.getenv("DATABASE_URL", "").strip()
    if not url:
        # Default to SQLite for development if PostgreSQL not configured
        sqlite_path = os.path.join(_project_root, "backend", "data", "agripredict.db")
        os.makedirs(os.path.dirname(sqlite_path), exist_ok=True)
        url = f"sqlite:///{sqlite_path}"
    return url


def create_database_engine() -> Engine:
    """Create SQLAlchemy engine with appropriate configuration."""
    url = get_database_url()
    
    if url.startswith("sqlite"):
        # SQLite configuration
        engine = create_engine(
            url,
            connect_args={"check_same_thread": False},
            poolclass=NullPool,
            echo=os.getenv("ENVIRONMENT") == "development",
        )
        
        # Enable foreign keys for SQLite
        @event.listens_for(engine, "connect")
        def set_sqlite_pragma(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()
    else:
        # PostgreSQL configuration
        engine = create_engine(
            url,
            pool_pre_ping=True,
            pool_size=5,
            max_overflow=10,
            echo=os.getenv("ENVIRONMENT") == "development",
        )
    
    return engine


# Global engine and session factory
_engine: Optional[Engine] = None
_session_factory: Optional[sessionmaker] = None


def get_engine() -> Engine:
    """Get or create the global database engine."""
    global _engine
    if _engine is None:
        _engine = create_database_engine()
    return _engine


def get_session_factory() -> sessionmaker:
    """Get or create the global session factory."""
    global _session_factory
    if _session_factory is None:
        _session_factory = sessionmaker(
            bind=get_engine(),
            autocommit=False,
            autoflush=False,
            expire_on_commit=False,
            class_=Session,
        )
    return _session_factory


@contextmanager
def get_db_session() -> Generator[Session, None, None]:
    """Context manager for database sessions with automatic commit/rollback."""
    session = get_session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency that yields a real SQLAlchemy session."""
    session = get_session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def init_database() -> None:
    """Initialize database by creating all tables."""
    engine = get_engine()
    Base.metadata.create_all(bind=engine)


def drop_database() -> None:
    """Drop all tables (use with caution)."""
    engine = get_engine()
    Base.metadata.drop_all(bind=engine)


def check_database_connection() -> bool:
    """Verify database connectivity."""
    try:
        engine = get_engine()
        with engine.connect() as conn:
            conn.execute("SELECT 1")
        return True
    except Exception:
        return False