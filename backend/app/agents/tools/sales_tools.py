"""Sales department agent tools wrapping AnalyticsService and SalesService."""

from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.agents.tools.base import rbac_tool
from app.models.user import User, UserRole
from app.services.analytics_service import analytics_service


@rbac_tool(
    UserRole.ADMIN,
    UserRole.MANAGER,
    tool_name="get_recognized_revenue",
)
def get_recognized_revenue(
    db: Session,
    current_user: User,
    start_date: str | None = None,
    end_date: str | None = None,
) -> dict[str, Any]:
    """Retrieve recognized financial sales revenue from COMPLETED and SHIPPED orders.

    Optionally filters by start_date and end_date (format: YYYY-MM-DD).
    Excludes CANCELLED and RETURNED orders from recognized totals.
    """
    s_date = None
    e_date = None
    if start_date:
        try:
            s_date = datetime.strptime(start_date.strip(), "%Y-%m-%d").date()
        except ValueError:
            return {"error": "Invalid start_date format. Expected YYYY-MM-DD."}
    if end_date:
        try:
            e_date = datetime.strptime(end_date.strip(), "%Y-%m-%d").date()
        except ValueError:
            return {"error": "Invalid end_date format. Expected YYYY-MM-DD."}

    sales_data = analytics_service.get_sales_analytics(
        db, start_date=s_date, end_date=e_date
    )

    return {
        "total_recognized_revenue": float(sales_data.total_recognized_revenue),
        "total_units_sold": sales_data.total_units_sold,
        "total_transactions": sales_data.total_transactions,
        "filter_applied": {
            "start_date": str(s_date) if s_date else None,
            "end_date": str(e_date) if e_date else None,
        },
        "recognition_rule": "COMPLETED and SHIPPED transactions only (quantity * unit_price)",
    }


@rbac_tool(
    UserRole.ADMIN,
    UserRole.MANAGER,
    tool_name="get_monthly_revenue_trends",
)
def get_monthly_revenue_trends(
    db: Session,
    current_user: User,
) -> list[dict[str, Any]]:
    """Retrieve monthly sales performance trends including recognized revenue, units sold, and order volume."""
    sales_data = analytics_service.get_sales_analytics(db)
    return [
        {
            "year_month": item.year_month,
            "recognized_revenue": float(item.recognized_revenue),
            "units_sold": item.units_sold,
            "order_count": item.order_count,
        }
        for item in sales_data.monthly_revenue
    ]


@rbac_tool(
    UserRole.ADMIN,
    UserRole.MANAGER,
    tool_name="get_top_selling_products",
)
def get_top_selling_products(
    db: Session,
    current_user: User,
    limit: int = 10,
    by: str = "revenue",
) -> list[dict[str, Any]]:
    """Retrieve top-selling products ranked either by total recognized revenue ('revenue') or total units sold ('units')."""
    capped_limit = min(max(1, limit), 50)
    sales_data = analytics_service.get_sales_analytics(db)

    products = (
        sales_data.top_products_by_units
        if by.strip().lower() == "units"
        else sales_data.top_products_by_revenue
    )

    return [
        {
            "sku": p.sku,
            "product_name": p.product_name,
            "units_sold": p.units_sold,
            "total_revenue": float(p.total_revenue),
        }
        for p in products[:capped_limit]
    ]


@rbac_tool(
    UserRole.ADMIN,
    UserRole.MANAGER,
    tool_name="get_sales_status_breakdown",
)
def get_sales_status_breakdown(
    db: Session,
    current_user: User,
) -> dict[str, Any]:
    """Retrieve complete status breakdown of all sales orders, including revenue lost to cancellations and returns."""
    sales_data = analytics_service.get_sales_analytics(db)
    return {
        "revenue_by_status": {
            k: float(v) for k, v in sales_data.revenue_by_status.items()
        },
        "returned_orders_count": sales_data.returned_orders_count,
        "returned_revenue_lost": float(sales_data.returned_revenue_lost),
        "cancelled_orders_count": sales_data.cancelled_orders_count,
        "cancelled_potential_revenue": float(sales_data.cancelled_potential_revenue),
    }
