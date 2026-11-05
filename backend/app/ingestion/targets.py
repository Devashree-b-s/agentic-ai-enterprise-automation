"""Explicit database target helpers for ingestion callers."""

from pathlib import Path
from sqlite3 import Connection as SQLite3Connection

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine, make_url

from app.core.config import settings
from app.db.historical import historical_database_path


def create_historical_writer_engine() -> Engine:
    """Create an explicit writer engine without enabling it during application startup."""
    historical_path = historical_database_path().resolve()
    operational_url = make_url(settings.DATABASE_URL)
    if (
        operational_url.drivername.startswith("sqlite")
        and operational_url.database
        and operational_url.database != ":memory:"
        and historical_path == Path(operational_url.database).resolve()
    ):
        raise ValueError("Historical and operational database paths must be distinct.")

    engine = create_engine(
        settings.HISTORICAL_DATABASE_URL,
        connect_args={"check_same_thread": False},
        pool_pre_ping=True,
    )

    @event.listens_for(engine, "connect")
    def _configure_historical_writer(
        dbapi_connection: SQLite3Connection, connection_record: object
    ) -> None:
        del connection_record
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.close()

    return engine
