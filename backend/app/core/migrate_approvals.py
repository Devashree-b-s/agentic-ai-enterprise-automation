"""Database migration script for Phase 5: Human-in-the-Loop Approval Workflows.

Creates:
- `approval_requests` table
- `approval_audits` table

Features:
- Verified timestamped safety backup in data/backups/
- Foreign key integrity verification via PRAGMA foreign_key_check
"""

import logging
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

backend_dir = Path(__file__).resolve().parent.parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.db.base import Base
from app.db.session import engine

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def migrate_approvals(db_path: Path) -> bool:
    """Migrate SQLite schema for approval workflows safely without data loss."""
    if not db_path.exists():
        logger.error("Database file %s does not exist.", db_path)
        return False

    # 1. Create a verified timestamped backup before touching the database
    backup_dir = db_path.parent / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = backup_dir / f"enterprise_pre_approvals_migration_{timestamp}.db"

    logger.info("Creating safety backup at %s ...", backup_file)
    src_conn = sqlite3.connect(str(db_path))
    dst_conn = sqlite3.connect(str(backup_file))
    with dst_conn:
        src_conn.backup(dst_conn)
    dst_conn.close()
    src_conn.close()
    logger.info("Safety backup created successfully (%d bytes).", backup_file.stat().st_size)

    # 2. Create tables
    try:
        logger.info("Creating approval_requests and approval_audits tables...")
        Base.metadata.create_all(bind=engine)

        # 3. Verify Foreign Keys and Tables
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        cursor.execute("PRAGMA foreign_keys = ON;")
        cursor.execute("PRAGMA foreign_key_check;")
        violations = cursor.fetchall()
        if violations:
            logger.error("Foreign key violations detected: %s", violations)
            conn.close()
            return False

        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name IN ('approval_requests', 'approval_audits');"
        )
        tables = [row[0] for row in cursor.fetchall()]
        logger.info("Verified tables present: %s", tables)
        conn.close()

        if len(tables) == 2:
            logger.info("Approval workflows schema migration completed successfully.")
            return True
        else:
            logger.error("Expected 2 tables, found %d: %s", len(tables), tables)
            return False
    except Exception:
        logger.exception("Migration failed due to an unexpected error.")
        return False


if __name__ == "__main__":
    db_file = backend_dir.parent / "data" / "enterprise.db"
    success = migrate_approvals(db_file)
    sys.exit(0 if success else 1)
