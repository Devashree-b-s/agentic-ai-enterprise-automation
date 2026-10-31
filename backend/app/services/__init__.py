"""Business services package."""

from app.services.auth_service import AuthService, auth_service
from app.services.hr_service import HRService, hr_service
from app.services.sales_service import SalesService, sales_service

__all__ = [
    "AuthService",
    "HRService",
    "SalesService",
    "auth_service",
    "hr_service",
    "sales_service",
]
