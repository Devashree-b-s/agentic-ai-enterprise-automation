"""CLI utility for importing products from DataCo Supply Chain dataset into the inventory database.

Usage:
    python backend/app/core/import_dataco_inventory.py [--csv-path data/dataco_supply_chain/DataCoSupplyChainDataset.csv] [--dry-run]
"""

import argparse
import csv
import logging
import sys
from pathlib import Path

# Ensure backend root is on sys.path
backend_dir = Path(__file__).resolve().parent.parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.db.session import SessionLocal
from app.models.inventory import Product, StockMovement, StockMovementType

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def import_dataco_products(
    csv_path: Path,
    dry_run: bool = False,
) -> dict[str, int]:
    """Parse DataCo supply chain dataset and insert distinct products into the Product table."""
    if not csv_path.is_file():
        raise FileNotFoundError(f"DataCo CSV not found at {csv_path}")

    db = SessionLocal()
    created_count = 0
    skipped_count = 0

    try:
        # Extract unique products from the DataCo CSV
        products_map: dict[str, dict] = {}
        with open(csv_path, "r", encoding="latin-1") as f:
            reader = csv.DictReader(f)
            for row in reader:
                p_id = row.get("Product Card Id", "").strip()
                name = row.get("Product Name", "").strip()
                if not p_id or not name or p_id in products_map:
                    continue

                category = row.get("Category Name", "General").strip()
                try:
                    price = float(row.get("Product Price", 50.0))
                except (ValueError, TypeError):
                    price = 50.0

                try:
                    lead_time = int(row.get("Days for shipping (real)", 4))
                except (ValueError, TypeError):
                    lead_time = 4
                lead_time = max(1, lead_time)

                sku = f"SKU-DCO-{int(p_id):04d}"
                products_map[p_id] = {
                    "sku": sku,
                    "name": name,
                    "description": f"Category: {category} | Unit Price: ${price:.2f}",
                    "lead_time_days": lead_time,
                    "quantity_on_hand": 100,  # Baseline warehouse initial stock
                    "quantity_on_order": 0,
                    "safety_stock": 20,
                    "target_stock": 150,
                }

        logger.info("Found %d unique products in DataCo dataset.", len(products_map))

        if dry_run:
            logger.info("Dry-run mode: no changes committed to the database.")
            return {"total_extracted": len(products_map), "created": 0, "skipped": 0}

        for p_data in products_map.values():
            existing = db.query(Product).filter_by(sku=p_data["sku"]).first()
            if existing:
                skipped_count += 1
                continue

            product = Product(
                sku=p_data["sku"],
                name=p_data["name"],
                description=p_data["description"],
                quantity_on_hand=p_data["quantity_on_hand"],
                quantity_on_order=p_data["quantity_on_order"],
                lead_time_days=p_data["lead_time_days"],
                safety_stock=p_data["safety_stock"],
                target_stock=p_data["target_stock"],
                is_active=True,
            )
            db.add(product)
            db.flush()

            # Record initial stock receipt movement
            movement = StockMovement(
                product_id=product.id,
                movement_type=StockMovementType.IN.value,
                quantity=product.quantity_on_hand,
                previous_quantity=0,
                new_quantity=product.quantity_on_hand,
                reason="Initial import from DataCo Supply Chain dataset",
                reference="IMPORT-DATACO",
            )
            db.add(movement)
            created_count += 1

        db.commit()
        logger.info(
            "DataCo product import committed: %d created, %d skipped.",
            created_count,
            skipped_count,
        )
        return {
            "total_extracted": len(products_map),
            "created": created_count,
            "skipped": skipped_count,
        }

    except Exception:
        db.rollback()
        logger.exception("Error importing DataCo products")
        raise
    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(description="Import DataCo products into Inventory")
    parser.add_argument(
        "--csv-path",
        type=str,
        default=str(backend_dir.parent / "data" / "dataco_supply_chain" / "DataCoSupplyChainDataset.csv"),
        help="Path to DataCoSupplyChainDataset.csv",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate import without committing changes",
    )
    args = parser.parse_args()

    summary = import_dataco_products(Path(args.csv_path), dry_run=args.dry_run)
    print("\n" + "=" * 50)
    print("        DATACO PRODUCT IMPORT SUMMARY            ")
    print("=" * 50)
    print(f"  Total Extracted:   {summary['total_extracted']}")
    print(f"  Products Created:  {summary['created']}")
    print(f"  Products Skipped:  {summary['skipped']}")
    print("=" * 50)


if __name__ == "__main__":
    main()
