"""Pydantic schemas for Leave Request validation and serialization."""

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.leave import LeaveStatus, LeaveType


class LeaveBase(BaseModel):
    """Base fields for leave requests."""

    leave_type: LeaveType = Field(
        ...,
        description="Type of leave requested",
        examples=[LeaveType.ANNUAL],
    )
    start_date: date = Field(
        ...,
        description="First day of leave (inclusive)",
        examples=["2026-06-01"],
    )
    end_date: date = Field(
        ...,
        description="Last day of leave (inclusive)",
        examples=["2026-06-05"],
    )
    days_count: int | None = Field(
        default=None,
        ge=1,
        description="Total business or calendar days for this leave",
        examples=[5],
    )
    reason: str | None = Field(
        default=None,
        max_length=500,
        description="Optional justification or notes for the leave request",
        examples=["Family vacation"],
    )

    @model_validator(mode="after")
    def validate_dates_and_days(self) -> "LeaveBase":
        """Validate date ordering and compute days_count if not provided."""
        if self.end_date < self.start_date:
            raise ValueError("end_date cannot be earlier than start_date")
        if self.days_count is None:
            # Default to calendar days difference + 1
            self.days_count = (self.end_date - self.start_date).days + 1
        return self


class LeaveCreate(LeaveBase):
    """Payload schema for submitting a new leave request."""

    employee_id: int = Field(
        ...,
        description="Primary key ID of the employee requesting leave",
        examples=[1],
    )


class LeaveStatusUpdate(BaseModel):
    """Payload schema for an approver/manager reviewing a leave request."""

    status: LeaveStatus = Field(
        ...,
        description="New lifecycle status (must be APPROVED or REJECTED)",
        examples=[LeaveStatus.APPROVED],
    )
    reason: str | None = Field(
        default=None,
        max_length=500,
        description="Optional feedback or rejection reason",
        examples=["Approved by manager."],
    )

    @model_validator(mode="after")
    def validate_status_transition(self) -> "LeaveStatusUpdate":
        if self.status not in (LeaveStatus.APPROVED, LeaveStatus.REJECTED):
            raise ValueError("Leave status update must be either APPROVED or REJECTED.")
        return self


class LeaveResponse(BaseModel):
    """Response schema for a single leave request."""

    id: int = Field(description="Primary key surrogate ID in the database")
    leave_code: str = Field(
        description="Enterprise unique identifier (e.g. 'LV-00001')"
    )
    employee_id: int = Field(description="Foreign key ID of the associated employee")
    employee_code: str = Field(
        description="Business employee identifier (e.g. 'EMP-0155')"
    )
    leave_type: str = Field(description="Category of leave")
    start_date: date = Field(description="Start date (inclusive)")
    end_date: date = Field(description="End date (inclusive)")
    days_count: int = Field(description="Total days duration")
    status: str = Field(description="Current status (PENDING, APPROVED, REJECTED)")
    reason: str | None = Field(default=None, description="Request or review notes")
    created_at: datetime = Field(description="Timestamp when request was filed")
    updated_at: datetime = Field(description="Timestamp when record was last updated")

    model_config = ConfigDict(from_attributes=True)


class LeaveSummaryReport(BaseModel):
    """High-level summary report for leave requests across the enterprise."""

    total_requests: int
    by_status: dict[str, int]
    by_type: dict[str, int]
    by_department: dict[str, int]
    total_days_requested: int
    total_days_approved: int
