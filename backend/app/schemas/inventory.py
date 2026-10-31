"""Pydantic schemas for Inventory management: Products, Stock Movements, Alerts, and Reports."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.inventory import StockMovementType

# ============================================================================
# Product Schemas
# ============================================================================


class ProductBase(BaseModel):
    """Shared product attributes."""

    sku: str = Field(
        ...,
        min_length=2,
        max_length=50,
        description="Unique business SKU identifier",
        examples=["SKU-GFT-001"],
    )
    name: str = Field(
        ...,
        min_length=1,
        max_length=150,
        description="Product name in catalog",
        examples=["Ceramic Photo Frame"],
    )
    description: str | None = Field(
        default=None,
        max_length=1000,
        description="Optional detailed product description",
        examples=["Hand-painted ceramic picture frame suitable for 4x6 photos"],
    )
    quantity_on_hand: int = Field(
        default=0,
        ge=0,
        description="Units currently available in warehouse stock",
        examples=[93],
    )
    quantity_on_order: int = Field(
        default=0,
        ge=0,
        description="Units on open purchase order from suppliers",
        examples=[175],
    )
    lead_time_days: int = Field(
        default=0,
        ge=0,
        description="Expected supplier delivery lead time in days",
        examples=[17],
    )
    safety_stock: int = Field(
        default=0,
        ge=0,
        description="Buffer threshold triggering replenishment",
        examples=[16],
    )
    target_stock: int = Field(
        default=0,
        ge=0,
        description="Optimal target stock level",
        examples=[169],
    )
    is_active: bool = Field(
        default=True,
        description="Status flag indicating active catalog item",
        examples=[True],
    )


class ProductCreate(ProductBase):
    """Payload schema for creating a new product."""


class ProductUpdate(BaseModel):
    """Payload schema for updating product metadata.

    Note: quantity_on_hand and quantity_on_order are managed exclusively via
    audited stock movements and purchase orders, not direct update mutations.
    """

    name: str | None = Field(default=None, min_length=1, max_length=150)
    description: str | None = Field(default=None, max_length=1000)
    lead_time_days: int | None = Field(default=None, ge=0)
    safety_stock: int | None = Field(default=None, ge=0)
    target_stock: int | None = Field(default=None, ge=0)
    is_active: bool | None = Field(default=None)


class ProductResponse(ProductBase):
    """Serialized product record returned by API."""

    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# Stock Operation Schemas
# ============================================================================


class StockInRequest(BaseModel):
    """Payload for adding inventory stock (e.g. supplier deliveries)."""

    product_id: int = Field(..., gt=0, description="Product database ID")
    quantity: int = Field(
        ..., gt=0, description="Quantity received into inventory (strictly > 0)"
    )
    reason: str | None = Field(
        default=None,
        max_length=255,
        description="Reason for receipt (e.g. 'Supplier Shipment')",
    )
    reference: str | None = Field(
        default=None,
        max_length=100,
        description="Supplier invoice or PO reference",
    )


class StockOutRequest(BaseModel):
    """Payload for deducting inventory stock (e.g. manual dispatch or shrinkage)."""

    product_id: int = Field(..., gt=0, description="Product database ID")
    quantity: int = Field(
        ..., gt=0, description="Quantity deducted from inventory (strictly > 0)"
    )
    reason: str | None = Field(
        default=None,
        max_length=255,
        description="Reason for deduction (e.g. 'Damaged Goods', 'Sample')",
    )
    reference: str | None = Field(
        default=None,
        max_length=100,
        description="Issue reference or dispatch slip",
    )


class StockAdjustRequest(BaseModel):
    """Payload for physical inventory reconciliation count."""

    product_id: int = Field(..., gt=0, description="Product database ID")
    new_quantity: int = Field(
        ...,
        ge=0,
        description="Exact counted physical stock level on hand (must be >= 0)",
    )
    reason: str | None = Field(
        default=None,
        max_length=255,
        description="Reason for reconciliation (e.g. 'Annual Stocktake')",
    )
    reference: str | None = Field(
        default=None,
        max_length=100,
        description="Stocktake sheet or audit count reference",
    )


class StockMovementResponse(BaseModel):
    """Serialized immutable stock movement audit record."""

    id: int
    product_id: int
    movement_type: StockMovementType
    quantity: int
    previous_quantity: int
    new_quantity: int
    reason: str | None = None
    reference: str | None = None
    created_by_user_id: int | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# Alerts & Summary Reports
# ============================================================================


class LowStockItem(BaseModel):
    """Product item requiring replenishment."""

    product_id: int
    sku: str
    name: str
    quantity_on_hand: int
    quantity_on_order: int
    safety_stock: int
    target_stock: int
    lead_time_days: int
    replenishment_quantity: int = Field(
        description="Units needed to reach target stock: max(0, target - on_hand - on_order)"
    )
    status: str = Field(description="'OUT_OF_STOCK' or 'LOW_STOCK'")


class LowStockAlertReport(BaseModel):
    """Consolidated low-stock alert report."""

    total_low_stock: int
    items: list[LowStockItem]


class InventorySummaryReport(BaseModel):
    """High-level executive inventory metrics."""

    total_products: int
    total_units_on_hand: int
    total_units_on_order: int
    low_stock_products_count: int
    out_of_stock_products_count: int
    products_requiring_replenishment_count: int
    monetary_valuation_available: bool = False
    notes: str = (
        "Monetary valuation is unavailable because supplier unit cost prices "
        "are not included in the catalog dataset."
    )


class CSVImportSummary(BaseModel):
    """Summary of batch inventory CSV import."""

    total_records_processed: int
    new_products_created: int
    existing_products_preserved: int
    errors: list[str] = Field(default_factory=list)
