"""Tests for Phase 1 database separation and migration foundations."""

import sqlite3
from pathlib import Path

import app.models
import app.models.historical_provenance
import pytest
from alembic import command
from alembic.config import Config
from app.core.backup_database import (
    create_database_backup,
    restore_database_backup,
)
from app.core.config import BACKEND_DIR, PROJECT_ROOT, Settings, settings
from app.core.migration_baseline import (
    BASELINE_REVISION,
    stamp_existing_database,
    validate_existing_schema,
)
from app.db.base import Base
from app.db.historical import (
    HistoricalDatabaseUnavailable,
    create_historical_readonly_engine,
    historical_database_path,
    historical_database_status,
)
from app.db.historical_base import HistoricalBase
from app.main import app
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect
from sqlalchemy.engine import make_url
from sqlalchemy.exc import OperationalError


def _sqlite_url(path: Path) -> str:
    return f"sqlite:///{path.as_posix()}"


def _alembic_config(ini_path: Path, database_url: str) -> Config:
    config = Config(str(ini_path))
    config.set_main_option("sqlalchemy.url", database_url)
    return config


def test_relative_database_urls_are_anchored_to_project_root():
    configured = Settings(
        _env_file=None,
        DATABASE_URL="sqlite:///./data/enterprise.db",
        HISTORICAL_DATABASE_URL="sqlite:///./data/historical.db",
        SECRET_KEY="phase1-test-key-that-is-not-for-production",
    )
    assert make_url(configured.DATABASE_URL).database == str(
        PROJECT_ROOT / "data" / "enterprise.db"
    ).replace("\\", "/")
    assert make_url(configured.HISTORICAL_DATABASE_URL).database == str(
        PROJECT_ROOT / "data" / "historical.db"
    ).replace("\\", "/")


def test_absent_historical_database_is_reported_without_creation(tmp_path, monkeypatch):
    missing_path = tmp_path / "not-created.db"
    monkeypatch.setattr(
        settings,
        "HISTORICAL_DATABASE_URL",
        _sqlite_url(missing_path),
    )

    assert historical_database_path() == missing_path
    assert historical_database_status() == {
        "available": False,
        "message": (
            "Historical data is unavailable because the historical database "
            "has not been initialized."
        ),
    }
    with pytest.raises(
        HistoricalDatabaseUnavailable, match="Historical data is unavailable"
    ):
        create_historical_readonly_engine()
    assert not missing_path.exists()


def test_historical_readonly_engine_rejects_writes(tmp_path, monkeypatch):
    historical_path = tmp_path / "history.db"
    with sqlite3.connect(historical_path) as connection:
        connection.execute("CREATE TABLE sample (id INTEGER PRIMARY KEY, value TEXT)")
        connection.execute("INSERT INTO sample (value) VALUES ('fixture')")

    monkeypatch.setattr(
        settings,
        "HISTORICAL_DATABASE_URL",
        _sqlite_url(historical_path),
    )
    engine = create_historical_readonly_engine()
    try:
        with engine.connect() as connection:
            assert connection.exec_driver_sql("PRAGMA query_only").scalar_one() == 1
            assert (
                connection.exec_driver_sql("SELECT value FROM sample").scalar_one()
                == "fixture"
            )
            with pytest.raises(OperationalError):
                connection.exec_driver_sql(
                    "INSERT INTO sample (value) VALUES ('blocked')"
                )
    finally:
        engine.dispose()

    with sqlite3.connect(
        f"file:{historical_path.as_posix()}?mode=ro", uri=True
    ) as connection:
        assert connection.execute("SELECT COUNT(*) FROM sample").fetchone()[0] == 1


def test_online_backup_verifies_integrity_and_row_counts(tmp_path):
    source = tmp_path / "source.db"
    with sqlite3.connect(source) as connection:
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("CREATE TABLE fixture (id INTEGER PRIMARY KEY, value TEXT)")
        connection.executemany(
            "INSERT INTO fixture (value) VALUES (?)",
            [("one",), ("two",)],
        )

    backup = create_database_backup(_sqlite_url(source), tmp_path / "backups")

    assert Path(backup["path"]).is_file()
    assert backup["integrity_check"] == "ok"
    assert backup["table_count"] == 1
    assert backup["row_count_total"] == 2
    assert len(backup["sha256"]) == 64
    assert not Path(f"{backup['path']}-wal").exists()
    assert not Path(f"{backup['path']}-shm").exists()

    restored_path = tmp_path / "restored.db"
    restored = restore_database_backup(Path(backup["path"]), restored_path)
    assert restored["integrity_check"] == "ok"
    assert restored["row_count_total"] == 2
    with pytest.raises(FileExistsError):
        restore_database_backup(Path(backup["path"]), restored_path)

    with sqlite3.connect(source.as_uri() + "?mode=ro", uri=True) as connection:
        assert connection.execute("SELECT COUNT(*) FROM fixture").fetchone()[0] == 2


def test_operational_migrations_upgrade_downgrade_and_reupgrade(tmp_path):
    database_url = _sqlite_url(tmp_path / "fresh-operational.db")
    config = _alembic_config(BACKEND_DIR / "alembic.ini", database_url)

    command.upgrade(config, "head")
    engine = create_engine(database_url)
    try:
        inspector = inspect(engine)
        assert set(Base.metadata.tables).issubset(set(inspector.get_table_names()))
        assert inspector.has_table("alembic_version")
        assert validate_existing_schema(database_url) == []
        assert inspector.get_foreign_keys("data_provenance_batches") == []
        with engine.connect() as connection:
            assert (
                connection.exec_driver_sql(
                    "SELECT version_num FROM alembic_version"
                ).scalar_one()
                == "c42b67d91e20"
            )

        command.downgrade(config, "base")
        assert not set(Base.metadata.tables).intersection(
            inspect(engine).get_table_names()
        )
        command.upgrade(config, "head")
        assert set(Base.metadata.tables).issubset(
            set(inspect(engine).get_table_names())
        )
    finally:
        engine.dispose()


def test_existing_baseline_is_validated_before_stamping_safe_fixture(tmp_path):
    database_url = _sqlite_url(tmp_path / "legacy-copy.db")
    config = _alembic_config(BACKEND_DIR / "alembic.ini", database_url)
    command.upgrade(config, BASELINE_REVISION)

    with sqlite3.connect(tmp_path / "legacy-copy.db") as connection:
        connection.execute("DROP TABLE alembic_version")

    assert validate_existing_schema(database_url) == []
    stamp_existing_database(database_url)

    with sqlite3.connect(tmp_path / "legacy-copy.db") as connection:
        assert (
            connection.execute("SELECT version_num FROM alembic_version").fetchone()[0]
            == BASELINE_REVISION
        )


def test_historical_migrations_are_independent(tmp_path):
    database_url = _sqlite_url(tmp_path / "fresh-historical.db")
    config = _alembic_config(BACKEND_DIR / "alembic_historical.ini", database_url)

    command.upgrade(config, "head")
    engine = create_engine(database_url)
    try:
        tables = set(inspect(engine).get_table_names())
        assert "data_provenance_batches" in tables
        assert "historical_alembic_version" in tables
        assert "alembic_version" not in tables
        assert inspect(engine).get_foreign_keys("data_provenance_batches") == []
        assert set(HistoricalBase.metadata.tables) == {"data_provenance_batches"}
    finally:
        engine.dispose()


def test_startup_does_not_create_absent_historical_database(tmp_path, monkeypatch):
    missing_path = tmp_path / "startup-history.db"
    monkeypatch.setattr(
        settings,
        "HISTORICAL_DATABASE_URL",
        _sqlite_url(missing_path),
    )

    with TestClient(app) as client:
        assert client.get("/health").status_code == 200
    assert not missing_path.exists()
