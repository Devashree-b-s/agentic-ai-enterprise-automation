"""Pydantic schemas for Sales management: Customers, Orders, and Analytics."""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.models.sales import OrderStatus

# Standard RFC-compliant email regex pattern
EMAIL_REGEX = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"


# ============================================================================
# Customer Schemas
# ============================================================================


class CustomerBase(BaseModel):
    """Shared customer attributes."""

    customer_code: str = Field(
        ...,
        min_length=2,
        max_length=50,
        description="Unique business customer code",
        examples=["CUST-001"],
    )
    name: str = Field(
        ...,
        min_length=1,
        max_length=150,
        description="Full customer or business name",
        examples=["Acme Corporation"],
    )
    email: str = Field(
        ...,
        pattern=EMAIL_REGEX,
        max_length=255,
        description="Contact email address",
        examples=["contact@acme.com"],
    )
    phone: str | None = Field(
        default=None,
        max_length=50,
        description="Contact phone number",
        examples=["+1-555-0199"],
    )
    address: str | None = Field(
        default=None,
        max_length=255,
        description="Billing or delivery address",
        examples=["100 Industrial Parkway, Sector 4"],
    )
    is_active: bool = Field(
        default=True,
        description="Status flag indicating active client relationship",
        examples=[True],
    )


class CustomerCreate(CustomerBase):
    """Payload schema for creating a new customer."""


class CustomerUpdate(BaseModel):
    """Payload schema for updating existing customer details (all optional)."""

    name: str | None = Field(default=None, min_length=1, max_length=150)
    email: str | None = Field(default=None, pattern=EMAIL_REGEX, max_length=255)
    phone: str | None = Field(default=None, max_length=50)
    address: str | None = Field(default=None, max_length=255)
    is_active: bool | None = Field(default=None)


class CustomerResponse(CustomerBase):
    """Serialized customer record returned by API."""

    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# Order Item Schemas
# ============================================================================


class OrderItemBase(BaseModel):
    """Line-item attributes for sales orders."""

    product_id: int = Field(
        ...,
        gt=0,
        description="Product ID corresponding to the Inventory catalog",
        examples=[101],
    )
    product_name: str = Field(
        ...,
        min_length=1,
        max_length=150,
        description="Product name snapshot at the time of sale",
        examples=["Enterprise Server Rack Model X"],
    )
    quantity: int = Field(
        ...,
        gt=0,
        description="Quantity ordered (must be strictly positive, >= 1)",
        examples=[2],
    )
    unit_price: Decimal = Field(
        ...,
        ge=Decimal("0.00"),
        decimal_places=2,
        description="Unit selling price (must be non-negative, >= 0.00)",
        examples=[Decimal("1250.00")],
    )


class OrderItemCreate(OrderItemBase):
    """Line-item input for order creation."""


class OrderItemResponse(OrderItemBase):
    """Serialized order item returned by API."""

    id: int
    order_id: int
    subtotal: Decimal
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# Order Schemas
# ============================================================================


class OrderCreate(BaseModel):
    """Payload schema for creating a sales order with multiple line items."""

    customer_id: int = Field(
        ...,
        gt=0,
        description="Database ID of the purchasing customer",
        examples=[1],
    )
    order_number: str | None = Field(
        default=None,
        min_length=3,
        max_length=50,
        description="Optional custom invoice number. Auto-generated if omitted.",
        examples=["ORD-202610-001"],
    )
    notes: str | None = Field(
        default=None,
        max_length=1000,
        description="Optional delivery instructions or notes",
        examples=["Expedited shipping requested"],
    )
    items: list[OrderItemCreate] = Field(
        ...,
        min_length=1,
        description="Order must contain at least one line item",
    )


class OrderStatusUpdate(BaseModel):
    """Payload schema for updating order lifecycle status."""

    status: OrderStatus = Field(
        ...,
        description="New lifecycle status for the order",
        examples=[OrderStatus.CONFIRMED],
    )


class OrderResponse(BaseModel):
    """Serialized sales order header summary."""

    id: int
    order_number: str
    customer_id: int
    status: OrderStatus
    total_amount: Decimal
    notes: str | None = None
    created_by_user_id: int | None = None
    order_date: datetime
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class OrderDetailResponse(OrderResponse):
    """Comprehensive sales order response including customer and line items."""

    customer: CustomerResponse
    items: list[OrderItemResponse]

    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# Reports & Analytics Schemas
# ============================================================================


class SalesSummaryReport(BaseModel):
    """Executive summary report of sales performance."""

    total_orders: int
    total_revenue: Decimal
    average_order_value: Decimal
    orders_by_status: dict[str, int]


class MonthlyRevenueItem(BaseModel):
    """Monthly revenue aggregate record."""

    year: int
    month: int
    period: str
    revenue: Decimal
    order_count: int


class MonthlyRevenueReport(BaseModel):
    """Monthly revenue breakdown report."""

    total_recognized_revenue: Decimal
    months: list[MonthlyRevenueItem]
