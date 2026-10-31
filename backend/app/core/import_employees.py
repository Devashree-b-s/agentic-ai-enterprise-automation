"""CLI utility for safe, repeatable employee CSV dataset import.

Usage:
    python backend/app/core/import_employees.py [--csv-path data/hr_employees.csv] [--dry-run]
"""

import argparse
import logging
import sys
from pathlib import Path

# Ensure backend root is on sys.path
backend_dir = Path(__file__).resolve().parent.parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.db.session import SessionLocal
from app.services.hr_service import hr_service

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def main() -> None:
    """CLI entrypoint for importing HR employees from CSV."""
    parser = argparse.ArgumentParser(
        description="Import HR employee catalog from CSV dataset."
    )
    parser.add_argument(
        "--csv-path",
        type=str,
        default=str(backend_dir.parent / "data" / "hr_employees.csv"),
        help="Path to the hr_employees.csv file",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate import and output statistics without committing changes",
    )
    args = parser.parse_args()

    csv_path = Path(args.csv_path)
    if not csv_path.is_file():
        logger.error("CSV file not found at: %s", csv_path)
        sys.exit(1)

    logger.info(
        "Starting employee import from: %s (dry-run=%s)", csv_path, args.dry_run
    )

    db = SessionLocal()
    try:
        summary = hr_service.import_employees_from_csv(
            db, csv_path, dry_run=args.dry_run
        )
        print("\n" + "=" * 50)
        print("           EMPLOYEE IMPORT SUMMARY           ")
        print("=" * 50)
        print(f"  Total Rows Processed:        {summary['total_rows']}")
        print(f"  New Employees Created:       {summary['created']}")
        print(f"  Existing Employees Preserved:{summary['preserved']}")
        print(f"  Errors Encountered:          {len(summary['errors'])}")
        print(f"  Dry Run (no changes saved):  {summary['dry_run']}")
        print("=" * 50 + "\n")

        if summary["errors"]:
            for err in summary["errors"][:10]:
                logger.warning(err)
            if len(summary["errors"]) > 10:
                logger.warning("... and %d more errors.", len(summary["errors"]) - 10)

    except Exception:
        logger.exception("Employee import failed due to an unhandled error.")
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
