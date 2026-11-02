"""Pydantic schemas for Human-in-the-Loop approval workflows."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models.approval import ApprovalRequestType


class ApprovalAuditResponse(BaseModel):
    """Schema for returning an individual approval audit event."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    approval_request_id: int
    actor_id: int | None = None
    actor_email: str
    actor_role: str
    action: str
    from_status: str | None = None
    to_status: str
    comment: str | None = None
    created_at: datetime


class ApprovalCreateRequest(BaseModel):
    """Schema for submitting a new approval proposal."""

    request_type: ApprovalRequestType = Field(
        ...,
        description="Workflow category: 'PURCHASE_REQUISITION' or 'LEAVE_REQUEST'",
    )
    title: str = Field(
        ...,
        min_length=3,
        max_length=255,
        description="Concise descriptive title of the proposal",
    )
    description: str | None = Field(
        default=None,
        description="Detailed justification, AI reasoning, or context",
    )
    assigned_role: str = Field(
        default="Manager",
        description="Target reviewer role (e.g. 'Manager', 'HR', 'Admin')",
    )
    action_payload: dict[str, Any] = Field(
        ...,
        description="Immutable structured parameters for the action to execute once approved",
    )
    idempotency_token: str | None = Field(
        default=None,
        max_length=100,
        description="Client-supplied deduplication token",
    )


class ApprovalReviewRequest(BaseModel):
    """Schema for approving or rejecting an approval request."""

    reason: str | None = Field(
        default=None,
        max_length=1000,
        description="Reviewer commentary, justification, or rejection reason",
    )


class ApprovalResponse(BaseModel):
    """Standard representation of an approval request."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    request_code: str
    request_type: str
    title: str
    description: str | None = None
    requester_id: int
    requester_email: str | None = None
    assigned_role: str
    reviewed_by_id: int | None = None
    reviewed_by_email: str | None = None
    status: str
    action_payload: dict[str, Any]
    execution_result: dict[str, Any] | None = None
    rejection_reason: str | None = None
    review_notes: str | None = None
    created_at: datetime
    reviewed_at: datetime | None = None
    executed_at: datetime | None = None


class ApprovalDetailResponse(ApprovalResponse):
    """Detailed view of an approval request with chronological audit history."""

    audit_records: list[ApprovalAuditResponse] = Field(default_factory=list)


class ApprovalSummaryMetrics(BaseModel):
    """Dashboard summary metrics across approval lifecycle states."""

    pending_count: int = 0
    approved_count: int = 0
    executed_count: int = 0
    rejected_count: int = 0
    cancelled_count: int = 0
    total_count: int = 0
