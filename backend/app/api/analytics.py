"""API endpoints for cross-department business intelligence and analytics."""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from app.core.deps import DbSession, require_roles
from app.models.user import User, UserRole
from app.schemas.analytics import (
    CrossDepartmentReport,
    DepartmentPerformance,
    HRAnalytics,
    InventoryAnalytics,
    MonthlyLeaveTrendItem,
    OverviewAnalytics,
    ProductPerformance,
    ReplenishmentAnalyticsItem,
    SalesAnalytics,
)
from app.services.analytics_service import analytics_service

router = APIRouter(tags=["Cross-Department Analytics"])

# Permissions
RequireExecutive = Annotated[
    User, Depends(require_roles(UserRole.ADMIN, UserRole.MANAGER))
]
RequireHRorExecutive = Annotated[
    User, Depends(require_roles(UserRole.ADMIN, UserRole.MANAGER, UserRole.HR))
]


@router.get(
    "/overview",
    response_model=OverviewAnalytics,
    status_code=status.HTTP_200_OK,
    summary="Get executive KPI overview (Admin & Manager only)",
    description="High-level dashboard metrics synthesizing HR, Sales, and Inventory operational health.",
)
def get_overview(
    db: DbSession,
    _: RequireExecutive,
) -> OverviewAnalytics:
    """Retrieve executive overview metrics."""
    return analytics_service.get_overview(db)


@router.get(
    "/hr",
    response_model=HRAnalytics,
    status_code=status.HTTP_200_OK,
    summary="Get HR workforce analytics (Admin, Manager, HR only)",
    description="Workforce headcount, active/inactive ratios, department distributions, and leave trends.",
)
def get_hr_analytics(
    db: DbSession,
    _: RequireHRorExecutive,
) -> HRAnalytics:
    """Retrieve HR and workforce metrics."""
    return analytics_service.get_hr_analytics(db)


@router.get(
    "/sales",
    response_model=SalesAnalytics,
    status_code=status.HTTP_200_OK,
    summary="Get sales performance analytics (Admin & Manager only)",
    description="Recognized revenue, units sold, monthly trends, top products, and cancellations/returns.",
)
def get_sales_analytics(
    db: DbSession,
    _: RequireExecutive,
    start_date: Annotated[
        date | None, Query(description="Start date filter (YYYY-MM-DD)")
    ] = None,
    end_date: Annotated[
        date | None, Query(description="End date filter (YYYY-MM-DD)")
    ] = None,
) -> SalesAnalytics:
    """Retrieve comprehensive sales analytics."""
    return analytics_service.get_sales_analytics(
        db, start_date=start_date, end_date=end_date
    )


@router.get(
    "/inventory",
    response_model=InventoryAnalytics,
    status_code=status.HTTP_200_OK,
    summary="Get inventory condition analytics (Admin & Manager only)",
    description="Stock on hand, on order, low-stock breaches, and replenishment requirements.",
)
def get_inventory_analytics(
    db: DbSession,
    _: RequireExecutive,
) -> InventoryAnalytics:
    """Retrieve warehouse inventory analytics."""
    return analytics_service.get_inventory_analytics(db)


@router.get(
    "/department-performance",
    response_model=list[DepartmentPerformance],
    status_code=status.HTTP_200_OK,
    summary="Get department-level staffing and leave performance (Admin & Manager only)",
    description="Correlates department headcount with employee leave days taken.",
)
def get_department_performance(
    db: DbSession,
    _: RequireExecutive,
) -> list[DepartmentPerformance]:
    """Retrieve department staffing and leave utilization."""
    return analytics_service.get_department_performance(db)


@router.get(
    "/product-performance",
    response_model=list[ProductPerformance],
    status_code=status.HTTP_200_OK,
    summary="Get product demand vs. inventory availability (Admin & Manager only)",
    description="Combines historical sales velocity with physical stock levels and days of supply remaining.",
)
def get_product_performance(
    db: DbSession,
    _: RequireExecutive,
    limit: Annotated[
        int, Query(ge=1, le=100, description="Max products to return")
    ] = 30,
) -> list[ProductPerformance]:
    """Retrieve product sales performance and inventory coverage."""
    return analytics_service.get_product_performance(db, limit=limit)


@router.get(
    "/leave-trends",
    response_model=list[MonthlyLeaveTrendItem],
    status_code=status.HTTP_200_OK,
    summary="Get monthly employee leave trends (Admin, Manager, HR only)",
    description="Monthly aggregated leave request volume and days duration.",
)
def get_leave_trends(
    db: DbSession,
    _: RequireHRorExecutive,
) -> list[MonthlyLeaveTrendItem]:
    """Retrieve monthly workforce leave trends."""
    hr_data = analytics_service.get_hr_analytics(db)
    return hr_data.monthly_leave_trends


@router.get(
    "/replenishment",
    response_model=list[ReplenishmentAnalyticsItem],
    status_code=status.HTTP_200_OK,
    summary="Get prescriptive replenishment suggestions (Admin & Manager only)",
    description="Actionable replenishment recommendations based on sales demand and safety stock.",
)
def get_replenishment(
    db: DbSession,
    _: RequireExecutive,
) -> list[ReplenishmentAnalyticsItem]:
    """Retrieve stock replenishment recommendations."""
    return analytics_service.get_replenishment_suggestions(db)


@router.get(
    "/cross-department",
    response_model=CrossDepartmentReport,
    status_code=status.HTTP_200_OK,
    summary="Get unified cross-department executive report (Admin & Manager only)",
    description="Comprehensive decision-support report linking HR, Sales, and Inventory.",
)
def get_cross_department_report(
    db: DbSession,
    _: RequireExecutive,
) -> CrossDepartmentReport:
    """Retrieve combined cross-department executive report."""
    return analytics_service.get_cross_department_report(db)
