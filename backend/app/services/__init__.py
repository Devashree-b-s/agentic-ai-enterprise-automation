"""Business services package."""

from app.services.analytics_service import AnalyticsService, analytics_service
from app.services.auth_service import AuthService, auth_service
from app.services.historical_sales_service import (
    HistoricalSalesService,
    historical_sales_service,
)
from app.services.hr_service import HRService, hr_service
from app.services.inventory_service import InventoryService, inventory_service
from app.services.leave_service import LeaveService, leave_service
from app.services.sales_service import SalesService, sales_service

__all__ = [
    "AnalyticsService",
    "AuthService",
    "HRService",
    "HistoricalSalesService",
    "InventoryService",
    "LeaveService",
    "SalesService",
    "analytics_service",
    "auth_service",
    "historical_sales_service",
    "hr_service",
    "inventory_service",
    "leave_service",
    "sales_service",
]
