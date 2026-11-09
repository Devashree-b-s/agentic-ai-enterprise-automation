"""Database engine, sessionmaker, and session dependency."""

from collections.abc import Generator
from sqlite3 import Connection as SQLite3Connection

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings

# For SQLite, check_same_thread must be False because FastAPI handles
# requests across multiple threads in its thread pool.
connect_args = {}
if settings.DATABASE_URL.startswith("sqlite"):
    connect_args["check_same_thread"] = False

# Create the database engine
engine = create_engine(
    settings.DATABASE_URL,
    connect_args=connect_args,
    echo=False,  # Set to True when debugging raw SQL queries
)

# Enforce foreign key constraints on all SQLite connections
if settings.DATABASE_URL.startswith("sqlite"):

    @event.listens_for(engine, "connect")
    def _configure_sqlite_connection(dbapi_connection, connection_record):
        if isinstance(dbapi_connection, SQLite3Connection):
            cursor = dbapi_connection.cursor()
            # Enforce foreign key constraints
            cursor.execute("PRAGMA foreign_keys=ON")
            # Set busy timeout to 5000ms to gracefully handle concurrent operations
            cursor.execute("PRAGMA busy_timeout=5000")
            # Enable Write-Ahead Logging (WAL) mode for file-based databases to maximize read-write concurrency
            if ":memory:" not in settings.DATABASE_URL:
                cursor.execute("PRAGMA journal_mode=WAL")
            cursor.close()


# Create a configurable Session factory
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency that provides a transactional database session.

    Yields:
        Session: An active SQLAlchemy session.

    Ensures:
        The session is always closed after request processing completes,
        even if an unhandled exception occurs.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
