"""Pydantic schemas for Employee data validation and serialization."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

# Standard RFC-compliant email regex pattern
EMAIL_REGEX = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"


class EmployeeBase(BaseModel):
    """Shared attributes common across creation, update, and response schemas."""

    employee_id: str = Field(
        ...,
        min_length=2,
        max_length=50,
        description="Unique business identifier for the employee",
        examples=["EMP-001"],
    )
    first_name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Given name of the employee",
        examples=["Alice"],
    )
    last_name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Family name / surname of the employee",
        examples=["Johnson"],
    )
    email: str = Field(
        ...,
        pattern=EMAIL_REGEX,
        max_length=255,
        description="Official enterprise email address",
        examples=["alice.johnson@enterprise.com"],
    )
    department: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Assigned organizational department",
        examples=["HR"],
    )
    role: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Job title or designation",
        examples=["HR Manager"],
    )
    salary: float = Field(
        ...,
        ge=0,
        description="Annual compensation (must be non-negative)",
        examples=[75000.0],
    )
    is_active: bool = Field(
        default=True,
        description="Employment status flag",
        examples=[True],
    )


class EmployeeCreate(EmployeeBase):
    """Schema for validating employee creation payloads."""


class EmployeeUpdate(BaseModel):
    """Schema for validating employee update payloads (all fields optional)."""

    first_name: str | None = Field(default=None, min_length=1, max_length=100)
    last_name: str | None = Field(default=None, min_length=1, max_length=100)
    email: str | None = Field(default=None, pattern=EMAIL_REGEX, max_length=255)
    department: str | None = Field(default=None, min_length=1, max_length=100)
    role: str | None = Field(default=None, min_length=1, max_length=100)
    salary: float | None = Field(default=None, ge=0)
    is_active: bool | None = Field(default=None)


class EmployeeResponse(EmployeeBase):
    """Schema for serializing employee data in API responses.

    Uses `from_attributes=True` (formerly `orm_mode=True`) to read data
    directly from SQLAlchemy ORM models.
    """

    id: int = Field(description="Primary key surrogate ID in the database")
    created_at: datetime = Field(description="Timestamp when record was created")
    updated_at: datetime = Field(description="Timestamp when record was last updated")

    model_config = ConfigDict(from_attributes=True)
