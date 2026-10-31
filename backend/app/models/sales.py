"""Sales domain models: Customer, Order, OrderItem, and OrderStatus."""

from datetime import datetime
from decimal import Decimal
from enum import Enum

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class OrderStatus(str, Enum):
    """Lifecycle statuses for sales orders."""

    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    SHIPPED = "SHIPPED"
    DELIVERED = "DELIVERED"
    CANCELLED = "CANCELLED"


class Customer(Base):
    """Customer entity model representing clients in the Sales domain.

    Attributes:
        id: Primary key identifier.
        customer_code: Unique business identifier (e.g. 'CUST-001').
        name: Full customer/company name.
        email: Contact email address (unique).
        phone: Contact telephone number.
        address: Physical or billing address.
        is_active: Status flag indicating whether customer is active.
        created_at: Timestamp when record was created.
        updated_at: Timestamp when record was last updated.
        orders: Relationship to customer's sales orders.
    """

    __tablename__ = "customers"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    customer_code: Mapped[str] = mapped_column(
        String(50), unique=True, index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    email: Mapped[str] = mapped_column(
        String(255), unique=True, index=True, nullable=False
    )
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    address: Mapped[str | None] = mapped_column(String(255), nullable=True)
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

    orders: Mapped[list["Order"]] = relationship(
        "Order",
        back_populates="customer",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return (
            f"<Customer(id={self.id}, code='{self.customer_code}', name='{self.name}')>"
        )


class Order(Base):
    """Sales Order model tracking sales transactions and lifecycle.

    Attributes:
        id: Primary key identifier.
        order_number: Unique business invoice/order number (e.g. 'ORD-202610-001').
        customer_id: Foreign key to Customer.
        status: Current order lifecycle status (OrderStatus).
        total_amount: Total monetary value computed deterministically from items.
        notes: Optional order notes or instructions.
        created_by_user_id: Foreign key to the User who entered the order.
        order_date: Date and time of order placement.
        created_at: Record creation timestamp.
        updated_at: Record update timestamp.
        customer: Linked Customer model.
        items: List of line items in this order.
    """

    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    order_number: Mapped[str] = mapped_column(
        String(50), unique=True, index=True, nullable=False
    )
    customer_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("customers.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        String(50),
        default=OrderStatus.PENDING.value,
        nullable=False,
        index=True,
    )
    total_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), default=Decimal("0.00"), nullable=False
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by_user_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    order_date: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        nullable=False,
        index=True,
    )
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

    customer: Mapped["Customer"] = relationship("Customer", back_populates="orders")
    items: Mapped[list["OrderItem"]] = relationship(
        "OrderItem",
        back_populates="order",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return (
            f"<Order(id={self.id}, number='{self.order_number}', "
            f"status='{self.status}', total={self.total_amount})>"
        )


class OrderItem(Base):
    """Line item in a sales order.

    Designed for clean integration with the upcoming Inventory module via product_id.

    Attributes:
        id: Primary key identifier.
        order_id: Foreign key to parent Order.
        product_id: Identifier representing the product in Inventory.
        product_name: Snapshot of product name at the time of order.
        quantity: Units ordered (must be > 0).
        unit_price: Price per unit at time of sale (must be >= 0).
        subtotal: Computed line-item value (quantity * unit_price).
        created_at: Record creation timestamp.
        order: Linked parent Order model.
    """

    __tablename__ = "order_items"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("orders.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    product_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("products.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    product_name: Mapped[str] = mapped_column(String(150), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    subtotal: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        nullable=False,
    )

    order: Mapped["Order"] = relationship("Order", back_populates="items")

    def __repr__(self) -> str:
        return (
            f"<OrderItem(id={self.id}, order_id={self.order_id}, "
            f"product='{self.product_name}', qty={self.quantity}, subtotal={self.subtotal})>"
        )
