"""Business services package."""

from app.services.auth_service import AuthService, auth_service
from app.services.hr_service import HRService, hr_service

__all__ = ["AuthService", "HRService", "auth_service", "hr_service"]
