"""Pydantic schemas for cross-department business intelligence and analytics."""

from decimal import Decimal

from pydantic import BaseModel, Field


class OverviewAnalytics(BaseModel):
    """Executive cross-department KPI snapshot."""

    total_employees: int = Field(description="Total headcount registered in the system")
    active_employees: int = Field(description="Active headcount eligible for work")
    total_products: int = Field(description="Total catalog items tracked in inventory")
    total_inventory_units: int = Field(
        description="Total physical units currently on hand"
    )
    total_recognized_revenue: Decimal = Field(
        description="Gross recognized revenue from COMPLETED and SHIPPED orders"
    )
    total_orders_completed: int = Field(
        description="Count of successfully fulfilled orders"
    )
    pending_leave_requests: int = Field(
        description="Count of leave requests awaiting approval"
    )


class MonthlyLeaveTrendItem(BaseModel):
    """Monthly leave request count and duration aggregated by month."""

    year_month: str = Field(description="Calendar month in YYYY-MM format")
    total_requests: int = Field(description="Number of leave requests in this month")
    approved_requests: int = Field(description="Approved leave requests in this month")
    total_days: int = Field(description="Cumulative days taken across all leaves")


class HRAnalytics(BaseModel):
    """Detailed analytics for workforce staffing, roles, and absenteeism."""

    total_employees: int
    active_employees: int
    inactive_employees: int
    by_department: dict[str, int]
    by_role: dict[str, int]
    leave_requests_by_status: dict[str, int]
    pending_leave_requests: int
    leave_requests_by_department: dict[str, int]
    monthly_leave_trends: list[MonthlyLeaveTrendItem]


class MonthlySalesTrendItem(BaseModel):
    """Monthly revenue and volume figures."""

    year_month: str
    recognized_revenue: Decimal
    units_sold: int
    order_count: int


class ProductSalesItem(BaseModel):
    """Product-level sales contribution."""

    sku: str
    product_name: str
    units_sold: int
    total_revenue: Decimal


class SalesAnalytics(BaseModel):
    """Comprehensive sales performance analytics."""

    total_recognized_revenue: Decimal = Field(
        description="Total recognized revenue from COMPLETED and SHIPPED sales"
    )
    total_units_sold: int
    total_transactions: int
    revenue_by_status: dict[str, Decimal]
    monthly_revenue: list[MonthlySalesTrendItem]
    top_products_by_revenue: list[ProductSalesItem]
    top_products_by_units: list[ProductSalesItem]
    returned_orders_count: int
    returned_revenue_lost: Decimal
    cancelled_orders_count: int
    cancelled_potential_revenue: Decimal


class StockProductItem(BaseModel):
    """Product stock level summary item."""

    sku: str
    name: str
    quantity_on_hand: int
    safety_stock: int
    target_stock: int


class InventoryAnalytics(BaseModel):
    """Inventory warehouse and stock condition analytics."""

    total_products: int
    total_stock_on_hand: int
    total_stock_on_order: int
    low_stock_count: int = Field(
        description="Products with quantity_on_hand <= safety_stock"
    )
    out_of_stock_count: int = Field(description="Products with quantity_on_hand == 0")
    highest_stock_products: list[StockProductItem]
    replenishment_needed_count: int
    monetary_valuation_available: bool = Field(
        default=False,
        description="Always False as inventory dataset lacks cost/purchase price data",
    )
    valuation_note: str = Field(
        default=(
            "Monetary inventory valuation is unavailable because supplier unit purchase "
            "costs are not included in the catalog dataset."
        ),
        description="Notice regarding absence of monetary inventory valuation",
    )


class DepartmentPerformance(BaseModel):
    """Department staffing and operational leave metrics."""

    department: str
    employee_count: int
    active_employee_count: int
    leave_requests_count: int
    total_leave_days: int
    average_leave_days_per_employee: float


class ProductPerformance(BaseModel):
    """Combined sales demand vs. current inventory stock."""

    sku: str
    name: str
    units_sold: int
    total_revenue: Decimal
    quantity_on_hand: int
    safety_stock: int
    stock_status: str = Field(description="'HEALTHY', 'LOW_STOCK', or 'OUT_OF_STOCK'")
    days_of_supply_estimate: float | None = Field(
        default=None,
        description="Estimated days of supply based on average daily sales velocity",
    )


class ReplenishmentAnalyticsItem(BaseModel):
    """Prescriptive replenishment suggestion based on sales demand and lead times."""

    sku: str
    name: str
    quantity_on_hand: int
    quantity_on_order: int
    safety_stock: int
    target_stock: int
    units_sold: int
    suggested_replenishment: int
    urgency: str = Field(description="'CRITICAL', 'WARNING', or 'NORMAL'")


class CrossDepartmentReport(BaseModel):
    """Combined executive analytics report across HR, Sales, and Inventory."""

    generated_at: str
    overview: OverviewAnalytics
    top_critical_products: list[ReplenishmentAnalyticsItem]
    department_headcounts: dict[str, int]
    department_leaves: dict[str, int]
