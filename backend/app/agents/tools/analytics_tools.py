"""Cross-department analytics agent tools wrapping AnalyticsService."""

from typing import Any

from sqlalchemy.orm import Session

from app.agents.tools.base import rbac_tool
from app.models.user import User, UserRole
from app.services.analytics_service import analytics_service


@rbac_tool(
    UserRole.ADMIN,
    UserRole.MANAGER,
    tool_name="get_executive_kpi_overview",
)
def get_executive_kpi_overview(
    db: Session,
    current_user: User,
) -> dict[str, Any]:
    """Retrieve executive cross-department snapshot synthesizing workforce, sales revenue, and inventory health."""
    overview = analytics_service.get_overview(db)
    return {
        "total_employees": overview.total_employees,
        "active_employees": overview.active_employees,
        "total_products": overview.total_products,
        "total_inventory_units": overview.total_inventory_units,
        "total_recognized_revenue": float(overview.total_recognized_revenue),
        "total_orders_completed": overview.total_orders_completed,
        "pending_leave_requests": overview.pending_leave_requests,
    }


@rbac_tool(
    UserRole.ADMIN,
    UserRole.MANAGER,
    tool_name="get_product_demand_vs_stock",
)
def get_product_demand_vs_stock(
    db: Session,
    current_user: User,
    limit: int = 30,
) -> list[dict[str, Any]]:
    """Retrieve correlated table of historical sales demand vs. current physical stock levels per product."""
    capped_limit = min(max(1, limit), 50)
    perf_list = analytics_service.get_product_performance(db, limit=capped_limit)
    return [
        {
            "sku": item.sku,
            "name": item.name,
            "units_sold": item.units_sold,
            "total_revenue": float(item.total_revenue),
            "quantity_on_hand": item.quantity_on_hand,
            "safety_stock": item.safety_stock,
            "stock_status": item.stock_status,
            "days_of_supply_estimate": item.days_of_supply_estimate,
        }
        for item in perf_list
    ]


@rbac_tool(
    UserRole.ADMIN,
    UserRole.MANAGER,
    tool_name="get_department_headcount_vs_leave_performance",
)
def get_department_headcount_vs_leave_performance(
    db: Session,
    current_user: User,
) -> list[dict[str, Any]]:
    """Retrieve department-level correlation between employee headcount and approved leave days taken."""
    dept_perf = analytics_service.get_department_performance(db)
    return [
        {
            "department": item.department,
            "employee_count": item.employee_count,
            "active_employee_count": item.active_employee_count,
            "leave_requests_count": item.leave_requests_count,
            "total_leave_days": item.total_leave_days,
            "average_leave_days_per_employee": item.average_leave_days_per_employee,
        }
        for item in dept_perf
    ]
