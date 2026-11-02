"""Approval domain models: ApprovalRequest and ApprovalAudit for Human-in-the-Loop workflows."""

import json
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.user import User


class ApprovalRequestType(str, Enum):
    """Categorization of approval requests."""

    PURCHASE_REQUISITION = "PURCHASE_REQUISITION"
    LEAVE_REQUEST = "LEAVE_REQUEST"


class ApprovalStatus(str, Enum):
    """Lifecycle states of an approval request."""

    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXECUTED = "EXECUTED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class ApprovalRequest(Base):
    """Immutable Human-in-the-Loop approval request proposal.

    Attributes:
        id: Primary key surrogate identifier.
        request_code: Unique human-readable identifier (e.g. 'REQ-PO-20261102-0001').
        request_type: Business workflow type (PURCHASE_REQUISITION or LEAVE_REQUEST).
        title: Descriptive summary title.
        description: Justification, AI reasoning, or contextual details.
        requester_id: User account that initiated the proposal.
        assigned_role: Reviewer role permitted to review this request (e.g. 'Manager', 'HR', 'Admin').
        reviewed_by_id: User account that approved or rejected the request.
        status: Current lifecycle state.
        action_payload: Immutable JSON serialized snapshot of proposed action.
        execution_result: Immutable JSON serialized outcome of execution.
        rejection_reason: Explanation if rejected.
        review_notes: Additional reviewer comments.
        idempotency_token: Unique deduplication token.
        created_at: Submission timestamp.
        reviewed_at: Review decision timestamp.
        executed_at: Action execution timestamp.
    """

    __tablename__ = "approval_requests"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    request_code: Mapped[str] = mapped_column(
        String(50), unique=True, index=True, nullable=False
    )
    request_type: Mapped[str] = mapped_column(
        String(50), index=True, nullable=False
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    requester_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    assigned_role: Mapped[str] = mapped_column(
        String(50), nullable=False, default="Manager"
    )
    reviewed_by_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    status: Mapped[str] = mapped_column(
        String(20),
        default=ApprovalStatus.PENDING.value,
        nullable=False,
        index=True,
    )

    action_payload: Mapped[str] = mapped_column(Text, nullable=False)
    execution_result: Mapped[str | None] = mapped_column(Text, nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    review_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    idempotency_token: Mapped[str | None] = mapped_column(
        String(100), unique=True, nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        nullable=False,
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    executed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Relationships
    requester: Mapped["User"] = relationship(
        "User", foreign_keys=[requester_id], back_populates="requested_approvals"
    )
    reviewed_by: Mapped["User | None"] = relationship(
        "User", foreign_keys=[reviewed_by_id], back_populates="reviewed_approvals"
    )
    audit_records: Mapped[list["ApprovalAudit"]] = relationship(
        "ApprovalAudit",
        back_populates="request",
        cascade="all, delete-orphan",
        order_by="ApprovalAudit.id.asc()",
    )

    def get_payload(self) -> dict[str, Any]:
        """Deserialize immutable action payload safely."""
        try:
            return json.loads(self.action_payload)
        except (json.JSONDecodeError, TypeError):
            return {}

    def get_execution_result(self) -> dict[str, Any] | None:
        """Deserialize execution result safely."""
        if not self.execution_result:
            return None
        try:
            return json.loads(self.execution_result)
        except (json.JSONDecodeError, TypeError):
            return None

    def __repr__(self) -> str:
        return (
            f"<ApprovalRequest(code='{self.request_code}', type='{self.request_type}', "
            f"status='{self.status}')>"
        )


class ApprovalAudit(Base):
    """Immutable audit trail of actions taken on an ApprovalRequest."""

    __tablename__ = "approval_audits"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    approval_request_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("approval_requests.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    actor_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    actor_email: Mapped[str] = mapped_column(String(255), nullable=False)
    actor_role: Mapped[str] = mapped_column(String(50), nullable=False)
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    from_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    to_status: Mapped[str] = mapped_column(String(20), nullable=False)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        nullable=False,
    )

    request: Mapped["ApprovalRequest"] = relationship(
        "ApprovalRequest", back_populates="audit_records"
    )

    def __repr__(self) -> str:
        return (
            f"<ApprovalAudit(id={self.id}, request_id={self.approval_request_id}, "
            f"action='{self.action}', to_status='{self.to_status}')>"
        )
