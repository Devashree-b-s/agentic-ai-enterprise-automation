"""Historical sales database models for reporting and business analytics."""

from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Date, DateTime, ForeignKey, Integer, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.inventory import Product


class HistoricalSale(Base):
    """SQLAlchemy model representing an immutable historical sales transaction.

    These records represent finalized or historical sales from the enterprise dataset
    (e.g., data/sales.csv), kept strictly separate from operational live orders so that:
    - Historical sales do not trigger operational inventory deductions.
    - Historical statuses ('COMPLETED', 'RETURNED') remain intact.
    - Historical and operational sales are never double counted.
    """

    __tablename__ = "historical_sales"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    order_id: Mapped[str] = mapped_column(
        String(50), unique=True, index=True, nullable=False
    )
    product_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("products.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    sku: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    order_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    subtotal: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    order_status: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        nullable=False,
    )

    # Optional relationship to Product in inventory catalog
    product: Mapped["Product | None"] = relationship("Product")

    def __repr__(self) -> str:
        return (
            f"<HistoricalSale(id={self.id}, order_id='{self.order_id}', sku='{self.sku}', "
            f"qty={self.quantity}, subtotal={self.subtotal}, status='{self.order_status}')>"
        )
