"""Inventory business service layer implementing stock operations, alerts, and CSV import."""

import csv
from pathlib import Path

from fastapi import HTTPException, status
from sqlalchemy import func, or_, select, update
from sqlalchemy.orm import Session

from app.models.inventory import Product, StockMovement, StockMovementType
from app.models.sales import Order, OrderItem
from app.schemas.inventory import (
    CSVImportSummary,
    InventorySummaryReport,
    LowStockAlertReport,
    LowStockItem,
    ProductCreate,
    ProductUpdate,
    StockAdjustRequest,
    StockInRequest,
    StockOutRequest,
)


class InventoryService:
    """Service encapsulating product catalog management, stock operations, and analytics."""

    # ========================================================================
    # Product CRUD Methods
    # ========================================================================

    @staticmethod
    def get_product_by_id(db: Session, product_id: int) -> Product | None:
        """Fetch a product by its primary key database ID."""
        return db.get(Product, product_id)

    @staticmethod
    def get_product_by_sku(db: Session, sku: str) -> Product | None:
        """Fetch a product by its unique business SKU."""
        stmt = select(Product).where(Product.sku == sku.strip())
        return db.scalar(stmt)

    @staticmethod
    def list_products(
        db: Session,
        skip: int = 0,
        limit: int = 100,
        search: str | None = None,
        is_low_stock: bool | None = None,
        is_active: bool | None = None,
    ) -> list[Product]:
        """List products with pagination, search, and filtering."""
        stmt = select(Product)

        if search:
            search_term = f"%{search.strip()}%"
            stmt = stmt.where(
                or_(
                    Product.name.ilike(search_term),
                    Product.sku.ilike(search_term),
                )
            )

        if is_low_stock is True:
            stmt = stmt.where(Product.quantity_on_hand <= Product.safety_stock)
        elif is_low_stock is False:
            stmt = stmt.where(Product.quantity_on_hand > Product.safety_stock)

        if is_active is not None:
            stmt = stmt.where(Product.is_active == is_active)

        stmt = stmt.order_by(Product.id.asc()).offset(skip).limit(limit)
        return list(db.scalars(stmt).all())

    @staticmethod
    def create_product(
        db: Session,
        product_in: ProductCreate,
        user_id: int | None = None,
    ) -> Product:
        """Create a new product with unique SKU enforcement."""
        sku_clean = product_in.sku.strip()
        existing = InventoryService.get_product_by_sku(db, sku_clean)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Product with SKU '{sku_clean}' already exists.",
            )

        product = Product(
            sku=sku_clean,
            name=product_in.name.strip(),
            description=product_in.description,
            quantity_on_hand=product_in.quantity_on_hand,
            quantity_on_order=product_in.quantity_on_order,
            lead_time_days=product_in.lead_time_days,
            safety_stock=product_in.safety_stock,
            target_stock=product_in.target_stock,
            is_active=product_in.is_active,
        )
        db.add(product)
        db.flush()

        # If initial stock was provided, record initial stock movement
        if product_in.quantity_on_hand > 0:
            initial_movement = StockMovement(
                product_id=product.id,
                movement_type=StockMovementType.IN.value,
                quantity=product_in.quantity_on_hand,
                previous_quantity=0,
                new_quantity=product_in.quantity_on_hand,
                reason="Initial product stock creation",
                reference="CATALOG-INIT",
                created_by_user_id=user_id,
            )
            db.add(initial_movement)

        db.commit()
        db.refresh(product)
        return product

    @staticmethod
    def update_product(
        db: Session,
        product: Product,
        product_in: ProductUpdate,
    ) -> Product:
        """Update product metadata.

        Operational quantities (quantity_on_hand, quantity_on_order) are not
        modified directly here to preserve stock audit integrity.
        """
        update_data = product_in.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            if field == "name" and value is not None:
                value = value.strip()
            setattr(product, field, value)

        db.commit()
        db.refresh(product)
        return product

    @staticmethod
    def delete_product(db: Session, product: Product) -> None:
        """Safely delete product or reject if referenced by orders or stock movements.

        Adheres to RESTRICT delete behavior: historical references must not be orphaned.
        Deactivation is preferred over deletion.
        """
        # 1. Check for sales order item references
        order_item_count = (
            db.scalar(
                select(func.count(OrderItem.id)).where(
                    OrderItem.product_id == product.id
                )
            )
            or 0
        )
        if order_item_count > 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Cannot delete product '{product.sku}' referenced by {order_item_count} "
                    f"sales order item(s). Deactivate the product instead."
                ),
            )

        # 2. Check for stock movement audit references
        movement_count = (
            db.scalar(
                select(func.count(StockMovement.id)).where(
                    StockMovement.product_id == product.id
                )
            )
            or 0
        )
        if movement_count > 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Cannot delete product '{product.sku}' with {movement_count} "
                    f"recorded stock movement(s). Deactivate the product instead."
                ),
            )

        db.delete(product)
        db.commit()

    # ========================================================================
    # Stock Operations (In, Out, Adjust)
    # ========================================================================

    @staticmethod
    def stock_in(
        db: Session,
        req: StockInRequest,
        user_id: int | None = None,
    ) -> StockMovement:
        """Receive incoming stock into inventory (e.g. supplier delivery)."""
        product = db.get(Product, req.product_id)
        if not product:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Product with ID {req.product_id} not found.",
            )

        if not product.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Product '{product.sku}' is deactivated. Activate it before adding stock.",
            )

        if req.quantity <= 0:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Stock in quantity must be strictly positive (>= 1).",
            )

        prev_qty = product.quantity_on_hand
        new_qty = prev_qty + req.quantity
        product.quantity_on_hand = new_qty

        movement = StockMovement(
            product_id=product.id,
            movement_type=StockMovementType.IN.value,
            quantity=req.quantity,
            previous_quantity=prev_qty,
            new_quantity=new_qty,
            reason=req.reason or "Stock In receipt",
            reference=req.reference,
            created_by_user_id=user_id,
        )
        db.add(movement)
        db.commit()
        db.refresh(movement)
        return movement

    @staticmethod
    def stock_out(
        db: Session,
        req: StockOutRequest,
        user_id: int | None = None,
    ) -> StockMovement:
        """Deduct stock from inventory with concurrency-safe conditional update."""
        product = db.get(Product, req.product_id)
        if not product:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Product with ID {req.product_id} not found.",
            )

        if req.quantity <= 0:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Stock out quantity must be strictly positive (>= 1).",
            )

        # Concurrency-safe atomic conditional decrement:
        # Ensures that even under concurrent race conditions, stock can never drop below 0.
        stmt = (
            update(Product)
            .where(
                Product.id == req.product_id,
                Product.quantity_on_hand >= req.quantity,
            )
            .values(quantity_on_hand=Product.quantity_on_hand - req.quantity)
        )
        res = db.execute(stmt)

        if res.rowcount == 0:
            db.refresh(product)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Insufficient stock for product '{product.sku}'. "
                    f"Available on hand: {product.quantity_on_hand}, Requested: {req.quantity}."
                ),
            )

        db.refresh(product)
        prev_qty = product.quantity_on_hand + req.quantity
        new_qty = product.quantity_on_hand

        movement = StockMovement(
            product_id=product.id,
            movement_type=StockMovementType.OUT.value,
            quantity=req.quantity,
            previous_quantity=prev_qty,
            new_quantity=new_qty,
            reason=req.reason or "Stock Out deduction",
            reference=req.reference,
            created_by_user_id=user_id,
        )
        db.add(movement)
        db.commit()
        db.refresh(movement)
        return movement

    @staticmethod
    def stock_adjust(
        db: Session,
        req: StockAdjustRequest,
        user_id: int | None = None,
    ) -> StockMovement:
        """Reconcile physical stock to an exact counted count (supports both increases and decreases)."""
        product = db.get(Product, req.product_id)
        if not product:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Product with ID {req.product_id} not found.",
            )

        if req.new_quantity < 0:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Adjusted stock count cannot be negative.",
            )

        prev_qty = product.quantity_on_hand
        new_qty = req.new_quantity
        diff = abs(new_qty - prev_qty)

        if diff == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Stock count for '{product.sku}' is already {new_qty}. "
                    f"No adjustment required."
                ),
            )

        product.quantity_on_hand = new_qty

        movement = StockMovement(
            product_id=product.id,
            movement_type=StockMovementType.ADJUSTMENT.value,
            quantity=diff,
            previous_quantity=prev_qty,
            new_quantity=new_qty,
            reason=req.reason or "Physical stock count reconciliation",
            reference=req.reference,
            created_by_user_id=user_id,
        )
        db.add(movement)
        db.commit()
        db.refresh(movement)
        return movement

    @staticmethod
    def list_movements_for_product(
        db: Session,
        product_id: int,
        skip: int = 0,
        limit: int = 100,
    ) -> list[StockMovement]:
        """Fetch immutable movement audit trail for a specific product."""
        product = db.get(Product, product_id)
        if not product:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Product with ID {product_id} not found.",
            )

        stmt = (
            select(StockMovement)
            .where(StockMovement.product_id == product_id)
            .order_by(StockMovement.created_at.desc(), StockMovement.id.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(db.scalars(stmt).all())

    # ========================================================================
    # Low-Stock Alerts & Replenishment
    # ========================================================================

    @staticmethod
    def get_low_stock_alerts(db: Session) -> LowStockAlertReport:
        """Calculate low-stock alert items and required replenishment quantities.

        A product is low stock when: quantity_on_hand <= safety_stock.
        Replenishment required: max(0, target_stock - quantity_on_hand - quantity_on_order).
        """
        stmt = (
            select(Product)
            .where(
                Product.is_active.is_(True),
                Product.quantity_on_hand <= Product.safety_stock,
            )
            .order_by(Product.quantity_on_hand.asc(), Product.sku.asc())
        )
        low_stock_products = list(db.scalars(stmt).all())

        items: list[LowStockItem] = []
        for p in low_stock_products:
            replenishment_qty = max(
                0, p.target_stock - p.quantity_on_hand - p.quantity_on_order
            )
            item_status = "OUT_OF_STOCK" if p.quantity_on_hand == 0 else "LOW_STOCK"

            items.append(
                LowStockItem(
                    product_id=p.id,
                    sku=p.sku,
                    name=p.name,
                    quantity_on_hand=p.quantity_on_hand,
                    quantity_on_order=p.quantity_on_order,
                    safety_stock=p.safety_stock,
                    target_stock=p.target_stock,
                    lead_time_days=p.lead_time_days,
                    replenishment_quantity=replenishment_qty,
                    status=item_status,
                )
            )

        return LowStockAlertReport(
            total_low_stock=len(items),
            items=items,
        )

    # ========================================================================
    # Executive Summary Report
    # ========================================================================

    @staticmethod
    def get_inventory_summary(db: Session) -> InventorySummaryReport:
        """Calculate executive inventory health metrics."""
        total_products = db.scalar(select(func.count(Product.id))) or 0
        total_on_hand = (
            db.scalar(select(func.coalesce(func.sum(Product.quantity_on_hand), 0))) or 0
        )
        total_on_order = (
            db.scalar(select(func.coalesce(func.sum(Product.quantity_on_order), 0)))
            or 0
        )

        low_stock_count = (
            db.scalar(
                select(func.count(Product.id)).where(
                    Product.is_active.is_(True),
                    Product.quantity_on_hand <= Product.safety_stock,
                )
            )
            or 0
        )

        out_of_stock_count = (
            db.scalar(
                select(func.count(Product.id)).where(
                    Product.is_active.is_(True),
                    Product.quantity_on_hand == 0,
                )
            )
            or 0
        )

        # Products requiring replenishment (where target_stock > on_hand + on_order)
        replenishment_count = (
            db.scalar(
                select(func.count(Product.id)).where(
                    Product.is_active.is_(True),
                    (
                        Product.target_stock
                        - Product.quantity_on_hand
                        - Product.quantity_on_order
                    )
                    > 0,
                )
            )
            or 0
        )

        return InventorySummaryReport(
            total_products=total_products,
            total_units_on_hand=total_on_hand,
            total_units_on_order=total_on_order,
            low_stock_products_count=low_stock_count,
            out_of_stock_products_count=out_of_stock_count,
            products_requiring_replenishment_count=replenishment_count,
            monetary_valuation_available=False,
            notes=(
                "Monetary inventory valuation is unavailable because supplier unit "
                "purchase cost prices are not part of the inventory catalog."
            ),
        )

    # ========================================================================
    # CSV Import Engine (Repeatable & Safe)
    # ========================================================================

    @staticmethod
    def import_csv(
        db: Session,
        csv_filepath: str | Path,
        user_id: int | None = None,
    ) -> CSVImportSummary:
        """Import or reconcile products from inventory.csv.

        Repeatability guarantee:
        - If SKU does not exist: Creates product and records initial Stock IN movement.
        - If SKU already exists: Preserves existing operational stock levels (quantity_on_hand
          and quantity_on_order) to avoid overwriting business transactions. Updates catalog metadata.
        """
        path = Path(csv_filepath)
        if not path.is_file():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Inventory CSV file not found at '{csv_filepath}'.",
            )

        processed = 0
        created = 0
        preserved = 0
        errors: list[str] = []

        with open(path, mode="r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            required_cols = {
                "product_id",
                "product_name",
                "on_hand",
                "on_order",
                "lead_time_days",
                "safety_stock",
                "target_stock",
            }
            if not required_cols.issubset(set(reader.fieldnames or [])):
                missing = required_cols - set(reader.fieldnames or [])
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"CSV is missing required headers: {sorted(missing)}",
                )

            for line_idx, row in enumerate(reader, start=2):
                processed += 1
                try:
                    sku = str(row["product_id"]).strip()
                    name = str(row["product_name"]).strip()
                    on_hand = int(row["on_hand"])
                    on_order = int(row["on_order"])
                    lead_time = int(row["lead_time_days"])
                    safety = int(row["safety_stock"])
                    target = int(row["target_stock"])

                    if (
                        on_hand < 0
                        or on_order < 0
                        or lead_time < 0
                        or safety < 0
                        or target < 0
                    ):
                        errors.append(
                            f"Row {line_idx}: Stock and lead time values must be non-negative."
                        )
                        continue

                    existing = InventoryService.get_product_by_sku(db, sku)
                    if existing:
                        # Preserve existing operational quantities, update catalog metadata
                        existing.name = name
                        existing.lead_time_days = lead_time
                        existing.safety_stock = safety
                        existing.target_stock = target
                        preserved += 1
                    else:
                        product = Product(
                            sku=sku,
                            name=name,
                            quantity_on_hand=on_hand,
                            quantity_on_order=on_order,
                            lead_time_days=lead_time,
                            safety_stock=safety,
                            target_stock=target,
                            is_active=True,
                        )
                        db.add(product)
                        db.flush()

                        if on_hand > 0:
                            initial_mov = StockMovement(
                                product_id=product.id,
                                movement_type=StockMovementType.IN.value,
                                quantity=on_hand,
                                previous_quantity=0,
                                new_quantity=on_hand,
                                reason="Initial CSV batch import",
                                reference="CSV-INIT",
                                created_by_user_id=user_id,
                            )
                            db.add(initial_mov)
                        created += 1

                except (ValueError, KeyError) as e:
                    errors.append(f"Row {line_idx}: Invalid data format ({e}).")

        db.commit()
        return CSVImportSummary(
            total_records_processed=processed,
            new_products_created=created,
            existing_products_preserved=preserved,
            errors=errors,
        )

    # ========================================================================
    # Sales-Inventory Integration Hooks
    # ========================================================================

    @staticmethod
    def deduct_stock_for_confirmed_order(
        db: Session,
        order: Order,
        user_id: int | None = None,
    ) -> None:
        """Deduct required stock quantities upon sales order confirmation.

        Concurrency-Safe Transactional Execution:
        - Validates all products exist and are active.
        - Atomically verifies and decrements quantity_on_hand.
        - If ANY item has insufficient stock, rolls back all changes with 400 Bad Request.
        """
        if not order.items:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Order '{order.order_number}' contains no line items to confirm.",
            )

        # 1. First pass: validate product existence and active status
        for item in order.items:
            product = db.get(Product, item.product_id)
            if not product:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        f"Cannot confirm order '{order.order_number}': product with "
                        f"ID {item.product_id} ('{item.product_name}') not found in inventory."
                    ),
                )
            if not product.is_active:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        f"Cannot confirm order '{order.order_number}': product '{product.sku}' "
                        f"('{product.name}') is deactivated."
                    ),
                )

        # 2. Second pass: concurrency-safe atomic deduction
        for item in order.items:
            product = db.get(Product, item.product_id)
            assert product is not None

            # Conditional atomic decrement:
            stmt = (
                update(Product)
                .where(
                    Product.id == item.product_id,
                    Product.quantity_on_hand >= item.quantity,
                )
                .values(quantity_on_hand=Product.quantity_on_hand - item.quantity)
            )
            res = db.execute(stmt)

            if res.rowcount == 0:
                # Insufficient stock! Roll back and report exact shortage
                db.rollback()
                db.refresh(product)
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        f"Cannot confirm order '{order.order_number}': insufficient stock for "
                        f"product '{product.sku}' ('{product.name}'). "
                        f"Available: {product.quantity_on_hand}, Requested: {item.quantity}."
                    ),
                )

            # Record stock movement audit trail
            db.refresh(product)
            prev_qty = product.quantity_on_hand + item.quantity
            new_qty = product.quantity_on_hand

            movement = StockMovement(
                product_id=product.id,
                movement_type=StockMovementType.OUT.value,
                quantity=item.quantity,
                previous_quantity=prev_qty,
                new_quantity=new_qty,
                reason=f"Sales Order confirmation: {order.order_number}",
                reference=order.order_number,
                created_by_user_id=user_id,
            )
            db.add(movement)

    @staticmethod
    def restore_stock_for_cancelled_order(
        db: Session,
        order: Order,
        user_id: int | None = None,
    ) -> None:
        """Restore deducted stock when a CONFIRMED order is cancelled prior to shipping."""
        for item in order.items:
            product = db.get(Product, item.product_id)
            if not product:
                continue

            prev_qty = product.quantity_on_hand
            new_qty = prev_qty + item.quantity
            product.quantity_on_hand = new_qty

            movement = StockMovement(
                product_id=product.id,
                movement_type=StockMovementType.IN.value,
                quantity=item.quantity,
                previous_quantity=prev_qty,
                new_quantity=new_qty,
                reason=f"Sales Order cancellation restore: {order.order_number}",
                reference=order.order_number,
                created_by_user_id=user_id,
            )
            db.add(movement)


# Global singleton instance for clean imports
inventory_service = InventoryService()
