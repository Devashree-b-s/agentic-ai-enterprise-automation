"""API routers package."""

from app.api.analytics import router as analytics_router
from app.api.auth import router as auth_router
from app.api.hr import router as hr_router
from app.api.inventory import router as inventory_router
from app.api.sales import router as sales_router

__all__ = [
    "analytics_router",
    "auth_router",
    "hr_router",
    "inventory_router",
    "sales_router",
]
