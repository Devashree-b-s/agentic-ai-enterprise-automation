"""Service layer for historical sales data management and reporting."""

import csv
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.historical_sale import HistoricalSale
from app.models.inventory import Product


class HistoricalSalesService:
    """Service encapsulating historical sales analytics and dataset ingestion."""

    @staticmethod
    def import_sales_from_csv(
        db: Session,
        csv_path: Path,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        """Import historical sales transactions from CSV.

        Guarantees:
        - Completely isolated from operational live orders.
        - NEVER alters inventory stock (quantity_on_hand is not modified).
        - NEVER records operational stock movements.
        - Preserves historical status ('COMPLETED', 'SHIPPED', 'RETURNED', 'CANCELLED').
        - Idempotent: Skips existing order_id entries on repeated imports.
        """
        if not csv_path.is_file():
            raise FileNotFoundError(f"Sales CSV file not found at {csv_path}")

        with open(csv_path, mode="r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            fieldnames = [fn.strip() for fn in (reader.fieldnames or [])]
            required_fields = {
                "order_id",
                "product_id",
                "order_date",
                "quantity",
                "unit_price",
                "order_status",
            }
            missing = required_fields - set(fieldnames)
            if missing:
                raise ValueError(f"CSV missing required columns: {sorted(missing)}")

            rows = list(reader)

        total_rows = len(rows)
        created_count = 0
        preserved_count = 0
        errors: list[str] = []

        # Cache existing historical order IDs
        existing_order_ids = set(db.scalars(select(HistoricalSale.order_id)).all())

        # Map catalog SKU -> Product.id
        sku_to_product_id = {
            prod.sku: prod.id for prod in db.scalars(select(Product)).all()
        }

        # Batch insert buffer for speed with 15k+ records
        new_records: list[HistoricalSale] = []

        for idx, row in enumerate(rows, start=2):
            order_id = (row.get("order_id") or "").strip()
            sku = (row.get("product_id") or "").strip()
            order_date_str = (row.get("order_date") or "").strip()
            quantity_str = (row.get("quantity") or "").strip()
            unit_price_str = (row.get("unit_price") or "").strip()
            order_status = (row.get("order_status") or "").strip().upper()

            if not order_id or not sku:
                errors.append(f"Row {idx}: Missing order_id or product_id")
                continue

            if order_id in existing_order_ids:
                preserved_count += 1
                continue

            try:
                order_date = datetime.strptime(order_date_str, "%Y-%m-%d").date()
                quantity = int(quantity_str)
                unit_price = Decimal(unit_price_str)
            except (ValueError, TypeError) as exc:
                errors.append(f"Row {idx}: Invalid numeric or date format: {exc}")
                continue

            subtotal = Decimal(quantity) * unit_price
            product_id = sku_to_product_id.get(sku)

            record = HistoricalSale(
                order_id=order_id,
                product_id=product_id,
                sku=sku,
                order_date=order_date,
                quantity=quantity,
                unit_price=unit_price,
                subtotal=subtotal,
                order_status=order_status,
            )
            new_records.append(record)
            existing_order_ids.add(order_id)
            created_count += 1

            # Flush in chunks of 2,000 for efficiency
            if len(new_records) >= 2000:
                db.add_all(new_records)
                db.flush()
                new_records.clear()

        if new_records:
            db.add_all(new_records)
            db.flush()
            new_records.clear()

        if dry_run:
            db.rollback()
        else:
            db.commit()

        return {
            "total_rows": total_rows,
            "created": created_count,
            "preserved": preserved_count,
            "errors": errors,
            "dry_run": dry_run,
        }


historical_sales_service = HistoricalSalesService()
