"""Safe SQLite schema migration script to add Product foreign key to order_items.

Adds:
    FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE RESTRICT
Preserves:
    FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE
    Existing data, indexes, types, and constraints.
"""

import logging
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def migrate_order_items_foreign_key(db_path: Path) -> bool:
    """Safely migrate order_items table in SQLite using the table rebuild pattern."""
    if not db_path.exists():
        logger.error("Database file %s does not exist.", db_path)
        return False

    # 1. Create a timestamped backup before touching the database
    backup_dir = db_path.parent / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = backup_dir / f"enterprise_pre_migration_{timestamp}.db"

    logger.info("Creating safety backup at %s ...", backup_file)
    src_conn = sqlite3.connect(str(db_path))
    dst_conn = sqlite3.connect(str(backup_file))
    with dst_conn:
        src_conn.backup(dst_conn)
    dst_conn.close()
    src_conn.close()
    logger.info("Backup created successfully (%d bytes).", backup_file.stat().st_size)

    # 2. Open connection in autocommit mode (isolation_level=None)
    # This allows running PRAGMA foreign_keys = OFF outside an active transaction.
    conn = sqlite3.connect(str(db_path), isolation_level=None)
    cursor = conn.cursor()

    try:
        # Check if products table exists
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='products';"
        )
        if not cursor.fetchone():
            logger.error("The 'products' table does not exist. Cannot add foreign key.")
            conn.close()
            return False

        # Inspect current foreign keys on order_items
        cursor.execute("PRAGMA foreign_key_list(order_items);")
        existing_fks = cursor.fetchall()
        has_product_fk = any(
            fk[2] == "products" and fk[3] == "product_id" for fk in existing_fks
        )
        if has_product_fk:
            logger.info(
                "Foreign key to products already exists on order_items.product_id. No migration needed."
            )
            conn.close()
            return True

        logger.info("Starting table-rebuild migration for order_items...")

        # Step 2a: Disable foreign keys OUTSIDE of any transaction
        cursor.execute("PRAGMA foreign_keys = OFF;")

        # Step 2b: Begin explicit transaction
        cursor.execute("BEGIN TRANSACTION;")

        # Step 2c: Create temporary replacement table with new foreign key
        cursor.execute("""
            CREATE TABLE new_order_items (
                id INTEGER NOT NULL,
                order_id INTEGER NOT NULL,
                product_id INTEGER NOT NULL,
                product_name VARCHAR(150) NOT NULL,
                quantity INTEGER NOT NULL,
                unit_price NUMERIC(10, 2) NOT NULL,
                subtotal NUMERIC(10, 2) NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
                PRIMARY KEY (id),
                FOREIGN KEY (order_id) REFERENCES orders (id) ON DELETE CASCADE,
                FOREIGN KEY (product_id) REFERENCES products (id) ON DELETE RESTRICT
            );
        """)

        # Step 2d: Copy existing data
        cursor.execute("""
            INSERT INTO new_order_items (
                id, order_id, product_id, product_name, quantity, unit_price, subtotal, created_at
            )
            SELECT id, order_id, product_id, product_name, quantity, unit_price, subtotal, created_at
            FROM order_items;
        """)

        # Step 2e: Drop old table
        cursor.execute("DROP TABLE order_items;")

        # Step 2f: Rename replacement table to target table
        cursor.execute("ALTER TABLE new_order_items RENAME TO order_items;")

        # Step 2g: Recreate indexes
        cursor.execute(
            "CREATE INDEX ix_order_items_order_id ON order_items (order_id);"
        )
        cursor.execute(
            "CREATE INDEX ix_order_items_product_id ON order_items (product_id);"
        )

        # Step 2h: Commit the transaction
        cursor.execute("COMMIT;")
        logger.info("Transaction committed successfully.")

        # Step 2i: Re-enable foreign keys OUTSIDE of transaction
        cursor.execute("PRAGMA foreign_keys = ON;")

        # Step 2j: Perform complete foreign key integrity check
        cursor.execute("PRAGMA foreign_key_check;")
        violations = cursor.fetchall()
        if violations:
            logger.error(
                "Foreign key violations detected after migration: %s", violations
            )
            conn.close()
            return False

        logger.info("PRAGMA foreign_key_check passed with 0 violations.")

        # Verify foreign keys on new table
        cursor.execute("PRAGMA foreign_key_list(order_items);")
        fks = cursor.fetchall()
        logger.info("Updated foreign_key_list(order_items):")
        for fk in fks:
            logger.info("  %s", fk)

        conn.close()
        logger.info("Migration completed successfully.")
        return True

    except Exception:
        logger.exception("Migration failed.")
        try:
            cursor.execute("ROLLBACK;")
        except sqlite3.Error:
            logger.warning("Rollback failed during error handling.")
        conn.close()
        return False


if __name__ == "__main__":
    base_dir = Path(__file__).resolve().parent.parent.parent.parent
    db_file = base_dir / "data" / "enterprise.db"
    success = migrate_order_items_foreign_key(db_file)
    sys.exit(0 if success else 1)
