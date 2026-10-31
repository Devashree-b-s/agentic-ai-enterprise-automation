"""Safe SQLite schema migration script for Milestone 6.

Changes:
1. Alters employees table to make salary nullable (via SQLite table-rebuild pattern).
2. Preserves all existing employee data, unique indexes, timestamps, and relationships.
3. Creates new tables (leave_requests, historical_sales) via Base.metadata.create_all.
4. Verifies foreign key integrity.
"""

import logging
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

# Ensure backend root is on sys.path
backend_dir = Path(__file__).resolve().parent.parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.db.base import Base
from app.db.session import engine

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def migrate_milestone6(db_path: Path) -> bool:
    """Migrate SQLite schema for Milestone 6 safely without data loss."""
    if not db_path.exists():
        logger.error("Database file %s does not exist.", db_path)
        return False

    # 1. Create a timestamped backup before touching the database
    backup_dir = db_path.parent / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = backup_dir / f"enterprise_m6_pre_migration_{timestamp}.db"

    logger.info("Creating safety backup at %s ...", backup_file)
    src_conn = sqlite3.connect(str(db_path))
    dst_conn = sqlite3.connect(str(backup_file))
    with dst_conn:
        src_conn.backup(dst_conn)
    dst_conn.close()
    src_conn.close()
    logger.info(
        "Safety backup created successfully (%d bytes).", backup_file.stat().st_size
    )

    # 2. Check current nullability of employees.salary
    conn = sqlite3.connect(str(db_path), isolation_level=None)
    cursor = conn.cursor()

    try:
        cursor.execute("PRAGMA table_info(employees);")
        columns = cursor.fetchall()
        salary_col = next((col for col in columns if col[1] == "salary"), None)

        # In PRAGMA table_info, col[3] == 1 means NOT NULL, col[3] == 0 means NULLABLE
        if salary_col and salary_col[3] == 1:
            logger.info(
                "employees.salary is currently NOT NULL. Rebuilding table to allow NULL..."
            )

            # 2a. PRAGMA foreign_keys = OFF outside of transaction
            cursor.execute("PRAGMA foreign_keys = OFF;")
            cursor.execute("BEGIN TRANSACTION;")

            # 2b. Create new employees table with salary nullable
            cursor.execute("""
                CREATE TABLE new_employees (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    employee_id VARCHAR(50) NOT NULL,
                    first_name VARCHAR(100) NOT NULL,
                    last_name VARCHAR(100) NOT NULL,
                    email VARCHAR(255) NOT NULL,
                    department VARCHAR(100) NOT NULL,
                    role VARCHAR(100) NOT NULL,
                    salary FLOAT,
                    is_active BOOLEAN NOT NULL DEFAULT 1,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL
                );
            """)

            # 2c. Copy existing data
            cursor.execute("""
                INSERT INTO new_employees (
                    id, employee_id, first_name, last_name, email, department, role, salary, is_active, created_at, updated_at
                )
                SELECT id, employee_id, first_name, last_name, email, department, role, salary, is_active, created_at, updated_at
                FROM employees;
            """)

            # 2d. Drop old table
            cursor.execute("DROP TABLE employees;")

            # 2e. Rename replacement table
            cursor.execute("ALTER TABLE new_employees RENAME TO employees;")

            # 2f. Recreate indexes
            cursor.execute(
                "CREATE UNIQUE INDEX ix_employees_email ON employees (email);"
            )
            cursor.execute(
                "CREATE UNIQUE INDEX ix_employees_employee_id ON employees (employee_id);"
            )
            cursor.execute(
                "CREATE INDEX ix_employees_department ON employees (department);"
            )

            cursor.execute("COMMIT;")
            cursor.execute("PRAGMA foreign_keys = ON;")
            logger.info("employees table successfully rebuilt with nullable salary.")
        else:
            logger.info("employees.salary is already nullable. Skipping table rebuild.")

        # 3. Check foreign key check
        cursor.execute("PRAGMA foreign_key_check;")
        violations = cursor.fetchall()
        if violations:
            logger.error("Foreign key violations detected: %s", violations)
            conn.close()
            return False

        conn.close()

        # 4. Create newly added tables (leave_requests, historical_sales)
        logger.info(
            "Creating new tables (leave_requests, historical_sales) if not present..."
        )
        Base.metadata.create_all(bind=engine)
        logger.info("Schema migration completed successfully.")
        return True

    except Exception:
        logger.exception("Migration failed due to unexpected error.")
        try:
            cursor.execute("ROLLBACK;")
        except sqlite3.Error:
            pass
        conn.close()
        return False


if __name__ == "__main__":
    db_file = backend_dir.parent / "data" / "enterprise.db"
    success = migrate_milestone6(db_file)
    sys.exit(0 if success else 1)
