"""CLI and standalone utility for importing the 30-product inventory.csv dataset."""

import argparse
import sys
from pathlib import Path

# Ensure backend root is on sys.path
backend_dir = Path(__file__).resolve().parent.parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.db.session import SessionLocal
from app.services.inventory_service import inventory_service


def run_import(csv_path: str = "data/inventory.csv") -> int:
    """Execute repeatable inventory CSV import and display formatted summary.

    Returns:
        0 on success, 1 on failure.
    """
    resolved_path = Path(csv_path)
    if not resolved_path.is_absolute():
        # Look relative to project root
        project_root = backend_dir.parent
        resolved_path = project_root / csv_path

    if not resolved_path.is_file():
        print(
            f"Error: Inventory CSV file not found at '{resolved_path}'.",
            file=sys.stderr,
        )
        return 1

    db = SessionLocal()
    try:
        print(f"Starting inventory import from: {resolved_path}")
        summary = inventory_service.import_csv(db, resolved_path)

        print("\n==================================================")
        print("           INVENTORY IMPORT SUMMARY               ")
        print("==================================================")
        print(f"  Total Rows Processed:       {summary.total_records_processed}")
        print(f"  New Products Created:       {summary.new_products_created}")
        print(f"  Existing Products Preserved: {summary.existing_products_preserved}")
        print(f"  Errors Encountered:         {len(summary.errors)}")

        if summary.errors:
            print("\nErrors detail:")
            for err in summary.errors:
                print(f"  - {err}", file=sys.stderr)

        print("==================================================\n")
        return 0
    finally:
        db.close()


def main():
    """CLI entrypoint."""
    parser = argparse.ArgumentParser(
        description="Repeatably import products from inventory.csv into the enterprise database."
    )
    parser.add_argument(
        "--csv-path",
        default="data/inventory.csv",
        help="Path to inventory.csv (default: data/inventory.csv)",
    )
    args = parser.parse_args()
    sys.exit(run_import(args.csv_path))


if __name__ == "__main__":
    main()
