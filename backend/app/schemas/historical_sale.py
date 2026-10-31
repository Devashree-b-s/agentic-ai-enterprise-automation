"""Pydantic schemas for historical sales data reporting."""

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class HistoricalSaleResponse(BaseModel):
    """Schema representing an individual historical sale transaction record."""

    id: int = Field(description="Internal surrogate primary key")
    order_id: str = Field(description="Historical order identifier (e.g., 'ORD-00001')")
    product_id: int | None = Field(
        default=None, description="Catalog product ID if resolved"
    )
    sku: str = Field(description="Product SKU identifier")
    order_date: date = Field(description="Date transaction occurred")
    quantity: int = Field(description="Number of units purchased")
    unit_price: Decimal = Field(description="Price per unit in USD")
    subtotal: Decimal = Field(
        description="Total line item revenue (quantity * unit_price)"
    )
    order_status: str = Field(
        description="Historical status (COMPLETED, SHIPPED, RETURNED, CANCELLED)"
    )
    created_at: datetime = Field(description="Timestamp record was imported")

    model_config = ConfigDict(from_attributes=True)
