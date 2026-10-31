"""API routers package."""

from app.api.auth import router as auth_router
from app.api.hr import router as hr_router

__all__ = ["auth_router", "hr_router"]
