"""Inventory domain models: Product and StockMovement."""

from datetime import datetime
from enum import Enum

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class StockMovementType(str, Enum):
    """Categorization of stock movements."""

    IN = "IN"
    OUT = "OUT"
    ADJUSTMENT = "ADJUSTMENT"


class Product(Base):
    """Product catalog item in the Inventory domain.

    Attributes:
        id: Primary key surrogate identifier.
        sku: Unique business Stock Keeping Unit (e.g. 'SKU-GFT-001').
        name: Product catalog name.
        description: Optional product details.
        quantity_on_hand: Units currently available in warehouse stock (must be >= 0).
        quantity_on_order: Units on open purchase order from suppliers (must be >= 0).
        lead_time_days: Supplier delivery lead time in days (must be >= 0).
        safety_stock: Buffer stock threshold triggering replenishment (must be >= 0).
        target_stock: Target optimal stock level for replenishment (must be >= 0).
        is_active: Active product status flag.
        created_at: Timestamp when product was created.
        updated_at: Timestamp when product was last modified.
        movements: History of stock movements associated with this product.
    """

    __tablename__ = "products"
    __table_args__ = (
        CheckConstraint("quantity_on_hand >= 0", name="chk_product_quantity_on_hand"),
        CheckConstraint("quantity_on_order >= 0", name="chk_product_quantity_on_order"),
        CheckConstraint("lead_time_days >= 0", name="chk_product_lead_time_days"),
        CheckConstraint("safety_stock >= 0", name="chk_product_safety_stock"),
        CheckConstraint("target_stock >= 0", name="chk_product_target_stock"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    sku: Mapped[str] = mapped_column(
        String(50), unique=True, index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(150), index=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    quantity_on_hand: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    quantity_on_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    lead_time_days: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    safety_stock: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    target_stock: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    movements: Mapped[list["StockMovement"]] = relationship(
        "StockMovement",
        back_populates="product",
    )

    def __repr__(self) -> str:
        return f"<Product(id={self.id}, sku='{self.sku}', name='{self.name}', on_hand={self.quantity_on_hand})>"


class StockMovement(Base):
    """Immutable audit record of inventory movements.

    Records every addition, deduction, or reconciliation adjustment to ensure
    full traceability and auditability.

    Attributes:
        id: Primary key identifier.
        product_id: Foreign key to Product (RESTRICT prevents accidental deletion).
        movement_type: Direction/type of movement (IN, OUT, ADJUSTMENT).
        quantity: Magnitude of unit change (must be > 0).
        previous_quantity: Stock level immediately before this movement (>= 0).
        new_quantity: Stock level immediately after this movement (>= 0).
        reason: Optional human-readable explanation.
        reference: Business reference (e.g. Sales Order number, PO number).
        created_by_user_id: Foreign key to the user account that initiated the change.
        created_at: Timestamp when movement occurred.
    """

    __tablename__ = "stock_movements"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="chk_stock_movement_quantity"),
        CheckConstraint("previous_quantity >= 0", name="chk_stock_movement_prev_qty"),
        CheckConstraint("new_quantity >= 0", name="chk_stock_movement_new_qty"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    product_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("products.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    movement_type: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    previous_quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    new_quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    reference: Mapped[str | None] = mapped_column(
        String(100), nullable=True, index=True
    )
    created_by_user_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        nullable=False,
        index=True,
    )

    product: Mapped["Product"] = relationship("Product", back_populates="movements")

    def __repr__(self) -> str:
        return (
            f"<StockMovement(id={self.id}, product_id={self.product_id}, "
            f"type='{self.movement_type}', qty={self.quantity}, "
            f"prev={self.previous_quantity}, new={self.new_quantity})>"
        )
