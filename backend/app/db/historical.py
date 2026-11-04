"""Read-only access helpers for the separate historical SQLite database."""

from collections.abc import Generator
from pathlib import Path
from sqlite3 import Connection as SQLite3Connection

from sqlalchemy import create_engine, event
from sqlalchemy.engine import URL, Engine, make_url
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings

HISTORICAL_UNAVAILABLE_MESSAGE = (
    "Historical data is unavailable because the historical database has not been "
    "initialized."
)


class HistoricalDatabaseUnavailable(RuntimeError):
    """Raised when a historical read is requested before its database exists."""


def historical_database_path() -> Path:
    """Return the configured absolute file path without opening the database."""
    url = make_url(settings.HISTORICAL_DATABASE_URL)
    if not url.drivername.startswith("sqlite") or not url.database:
        raise ValueError(
            "HISTORICAL_DATABASE_URL must identify a SQLite database file."
        )
    path = Path(url.database)
    if not path.is_absolute():
        raise ValueError("HISTORICAL_DATABASE_URL must resolve to an absolute path.")
    return path


def historical_database_status() -> dict[str, str | bool]:
    """Report historical availability without connecting to or creating the file."""
    available = historical_database_path().is_file()
    return {
        "available": available,
        "message": "" if available else HISTORICAL_UNAVAILABLE_MESSAGE,
    }


def create_historical_readonly_engine() -> Engine:
    """Create a lazy SQLite engine that cannot create or write historical data."""
    path = historical_database_path()
    if not path.is_file():
        raise HistoricalDatabaseUnavailable(HISTORICAL_UNAVAILABLE_MESSAGE)

    url = URL.create(
        "sqlite+pysqlite",
        database=f"file:{path.as_posix()}",
        query={"mode": "ro", "uri": "true"},
    )
    engine = create_engine(
        url,
        connect_args={"check_same_thread": False},
    )

    @event.listens_for(engine, "connect")
    def _protect_historical_connection(
        dbapi_connection: SQLite3Connection, connection_record: object
    ) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA query_only=ON")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.close()

    return engine


def get_historical_db() -> Generator[Session, None, None]:
    """Yield a short-lived session with SQLite read-only and query-only protection."""
    engine = create_historical_readonly_engine()
    session_factory = sessionmaker(autoflush=False, autocommit=False, bind=engine)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()
