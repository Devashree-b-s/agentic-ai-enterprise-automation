"""Create a verified SQLite online backup of the operational database."""

import argparse
import hashlib
import os
import sqlite3
import sys
import uuid
from datetime import datetime
from pathlib import Path

from sqlalchemy.engine import make_url

from app.core.config import DATA_DIR, settings


def _quoted_identifier(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def _database_path(database_url: str) -> Path:
    url = make_url(database_url)
    if not url.drivername.startswith("sqlite") or not url.database:
        raise ValueError("Database backup currently supports SQLite files only.")
    path = Path(url.database)
    if not path.is_absolute():
        raise ValueError("DATABASE_URL must resolve to an absolute file path.")
    return path


def _inspect_database(
    source: Path,
    *,
    immutable: bool = False,
) -> tuple[str, list[str], dict[str, int]]:
    query = "mode=ro&immutable=1" if immutable else "mode=ro"
    source_connection = sqlite3.connect(
        f"{source.as_uri()}?{query}",
        uri=True,
    )
    source_connection.execute("PRAGMA query_only=ON")
    try:
        integrity = source_connection.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity != "ok":
            raise RuntimeError(f"Database integrity check failed for {source}.")
        table_names = [
            row[0]
            for row in source_connection.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
            )
        ]
        row_counts = {
            table: source_connection.execute(
                f"SELECT COUNT(*) FROM {_quoted_identifier(table)}"
            ).fetchone()[0]
            for table in table_names
        }
        return integrity, table_names, row_counts
    finally:
        source_connection.close()


def _snapshot(source: Path, destination: Path) -> tuple[list[str], dict[str, int]]:
    _, table_names, row_counts = _inspect_database(source)
    source_connection = sqlite3.connect(
        f"{source.as_uri()}?mode=ro",
        uri=True,
    )
    source_connection.execute("PRAGMA query_only=ON")
    try:
        destination_connection = sqlite3.connect(destination)
        try:
            source_connection.backup(destination_connection)
        finally:
            destination_connection.close()
    finally:
        source_connection.close()
    return table_names, row_counts


def _verify_backup(
    destination: Path,
    expected_tables: list[str],
    expected_counts: dict[str, int],
) -> tuple[str, dict[str, int]]:
    integrity, tables, counts = _inspect_database(destination, immutable=True)

    if integrity != "ok" or tables != expected_tables or counts != expected_counts:
        raise RuntimeError(
            "Backup verification failed: integrity, table list, or row counts differ."
        )

    digest = hashlib.sha256()
    with destination.open("rb") as backup_file:
        for chunk in iter(lambda: backup_file.read(1024 * 1024), b""):
            digest.update(chunk)
    return integrity, {
        "row_count_total": sum(counts.values()),
        "table_count": len(tables),
        "sha256": digest.hexdigest(),
    }


def create_database_backup(
    database_url: str = settings.DATABASE_URL,
    backup_directory: Path | None = None,
) -> dict[str, object]:
    """Create a no-overwrite online backup and verify it independently."""
    source = _database_path(database_url)
    if not source.is_file():
        raise FileNotFoundError(f"Operational database not found: {source}")

    target_directory = backup_directory or DATA_DIR / "backups"
    target_directory.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().astimezone()
    destination = target_directory / (
        f"enterprise_{timestamp.strftime('%Y%m%d_%H%M%S_%f')}_{uuid.uuid4().hex[:8]}.db"
    )
    descriptor = os.open(
        destination,
        os.O_CREAT | os.O_EXCL | os.O_WRONLY,
        0o600,
    )
    os.close(descriptor)

    try:
        tables, counts = _snapshot(source, destination)
        integrity, verification = _verify_backup(destination, tables, counts)
    except (OSError, RuntimeError, sqlite3.Error):
        destination.unlink(missing_ok=True)
        raise

    return {
        "path": destination,
        "created_at": timestamp.isoformat(),
        "size_bytes": destination.stat().st_size,
        "integrity_check": integrity,
        **verification,
    }


def restore_database_backup(
    backup_path: Path,
    destination_path: Path,
) -> dict[str, object]:
    """Restore a verified backup to a new file without overwriting existing data."""
    backup = backup_path.resolve()
    destination = destination_path.resolve()
    if not backup.is_file():
        raise FileNotFoundError(f"Backup file not found: {backup}")
    if backup == destination:
        raise ValueError("Restore destination must differ from the backup file.")

    _, tables, counts = _inspect_database(backup)
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(
        destination,
        os.O_CREAT | os.O_EXCL | os.O_WRONLY,
        0o600,
    )
    os.close(descriptor)

    try:
        _snapshot(backup, destination)
        integrity, verification = _verify_backup(destination, tables, counts)
    except (OSError, RuntimeError, sqlite3.Error):
        destination.unlink(missing_ok=True)
        raise

    return {
        "path": destination,
        "size_bytes": destination.stat().st_size,
        "integrity_check": integrity,
        **verification,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Create a verified backup or restore it to a new SQLite file."
    )
    parser.add_argument("--restore-from", type=Path)
    parser.add_argument("--restore-to", type=Path)
    args = parser.parse_args()
    try:
        if args.restore_from or args.restore_to:
            if not args.restore_from or not args.restore_to:
                parser.error("--restore-from and --restore-to must be used together.")
            result = restore_database_backup(args.restore_from, args.restore_to)
        else:
            result = create_database_backup()
    except (OSError, RuntimeError, ValueError, sqlite3.Error) as exc:
        print(f"Backup failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc

    print(f"Backup: {result['path']}")
    if "created_at" in result:
        print(f"Created: {result['created_at']}")
    print(f"Size: {result['size_bytes']} bytes")
    print(f"Integrity: {result['integrity_check']}")
    print(f"Tables: {result['table_count']}")
    print(f"Rows: {result['row_count_total']}")
    print(f"SHA-256: {result['sha256']}")


if __name__ == "__main__":
    main()
