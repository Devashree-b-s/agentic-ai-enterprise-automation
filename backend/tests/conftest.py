"""Pytest fixtures for test database sessions and configuration."""

import sys
from pathlib import Path
from collections.abc import Generator

# Ensure backend directory is in sys.path
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base


@pytest.fixture(scope="function")
def db_session() -> Generator[Session, None, None]:
    """Provides an isolated, in-memory SQLite database session for each test.
    
    Using StaticPool and sqlite:///:memory: ensures:
    - Tests run blazingly fast in memory.
    - Each test starts with a freshly created, clean database schema.
    - Tests are completely isolated from each other.
    - No mock data ever touches the production/development database file.
    """
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=engine,
    )

    # Create all database tables defined in Base.metadata
    Base.metadata.create_all(bind=engine)

    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        # Drop all tables after test completes
        Base.metadata.drop_all(bind=engine)
