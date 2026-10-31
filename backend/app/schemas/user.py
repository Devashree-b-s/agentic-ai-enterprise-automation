"""Pydantic schemas for user registration, admin user creation, login, and tokens."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.user import UserRole

# Standard RFC-compliant email regex pattern
EMAIL_REGEX = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"


class UserBase(BaseModel):
    """Base user properties shared across schemas."""

    email: str = Field(
        ...,
        pattern=EMAIL_REGEX,
        max_length=255,
        description="Official enterprise email address used for login",
        examples=["employee@enterprise.com"],
    )
    is_active: bool = Field(
        default=True,
        description="Flag indicating active account status",
        examples=[True],
    )


class UserRegister(BaseModel):
    """Schema for public user self-registration.

    SECURITY NOTICE:
    Role selection is strictly excluded from public registration.
    All self-registered users are automatically assigned the Employee role.
    Any attempt to pass a 'role' parameter in the JSON payload is safely ignored.
    """

    email: str = Field(
        ...,
        pattern=EMAIL_REGEX,
        max_length=255,
        examples=["new.employee@enterprise.com"],
    )
    password: str = Field(
        ...,
        min_length=8,
        max_length=128,
        description="Password (minimum 8 characters)",
        examples=["SecurePass123!"],
    )
    employee_code: str | None = Field(
        default=None,
        description="Optional employee business identifier to link this user account",
        examples=["EMP-001"],
    )

    model_config = ConfigDict(extra="ignore")


class UserCreateByAdmin(BaseModel):
    """Schema for privileged user account creation by authenticated Administrators."""

    email: str = Field(
        ...,
        pattern=EMAIL_REGEX,
        max_length=255,
        examples=["new.manager@enterprise.com"],
    )
    password: str = Field(
        ...,
        min_length=8,
        max_length=128,
        description="Initial password (minimum 8 characters)",
        examples=["SecurePass123!"],
    )
    role: UserRole = Field(
        ...,
        description="Assigned RBAC role (Admin, HR, Manager, or Employee)",
        examples=[UserRole.MANAGER],
    )
    employee_code: str | None = Field(
        default=None,
        description="Optional employee business identifier to link this user account",
        examples=["EMP-002"],
    )


# Alias UserCreate to UserRegister for backward-compatibility where needed
UserCreate = UserRegister


class UserLogin(BaseModel):
    """Schema for user authentication requests."""

    email: str = Field(
        ...,
        pattern=EMAIL_REGEX,
        max_length=255,
        examples=["admin@enterprise.com"],
    )
    password: str = Field(
        ...,
        min_length=1,
        max_length=128,
        examples=["SecurePass123!"],
    )


class UserResponse(BaseModel):
    """Schema for public user profile responses."""

    id: int
    email: str
    role: UserRole
    is_active: bool
    employee_id: int | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TokenResponse(BaseModel):
    """Schema for returning JWT access tokens upon successful authentication."""

    access_token: str
    token_type: str = "bearer"
    user: UserResponse
