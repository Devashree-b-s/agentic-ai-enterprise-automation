"""API router for Human-in-the-Loop approval workflows and audit trails."""

import logging
from typing import Any

from fastapi import APIRouter, Query, status

from app.core.deps import CurrentUser, DbSession
from app.schemas.approval import (
    ApprovalAuditResponse,
    ApprovalCreateRequest,
    ApprovalDetailResponse,
    ApprovalResponse,
    ApprovalReviewRequest,
    ApprovalSummaryMetrics,
)
from app.services.approval_service import approval_service

logger = logging.getLogger("app.api.approvals")

router = APIRouter(prefix="/approvals", tags=["Human-in-the-Loop Approvals"])


@router.post(
    "",
    response_model=ApprovalResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit approval proposal",
    description="Submit a new business action proposal (e.g. Purchase Requisition or Leave Request) for human authorization.",
)
def create_approval_request(
    payload: ApprovalCreateRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> ApprovalResponse:
    """Create approval request entering PENDING state."""
    req = approval_service.create_request(db=db, current_user=current_user, payload=payload)
    return ApprovalResponse(
        id=req.id,
        request_code=req.request_code,
        request_type=req.request_type,
        title=req.title,
        description=req.description,
        requester_id=req.requester_id,
        requester_email=current_user.email,
        assigned_role=req.assigned_role,
        reviewed_by_id=req.reviewed_by_id,
        status=req.status,
        action_payload=req.get_payload(),
        execution_result=req.get_execution_result(),
        rejection_reason=req.rejection_reason,
        review_notes=req.review_notes,
        created_at=req.created_at,
        reviewed_at=req.reviewed_at,
        executed_at=req.executed_at,
    )


@router.get(
    "",
    response_model=list[ApprovalResponse],
    status_code=status.HTTP_200_OK,
    summary="List approval requests",
    description="List approval requests with filtering by status, request type, and RBAC ownership.",
)
def list_approvals(
    db: DbSession,
    current_user: CurrentUser,
    status_filter: str | None = Query(None, alias="status", description="Filter by status (PENDING, APPROVED, etc.)"),
    type_filter: str | None = Query(None, alias="type", description="Filter by type (PURCHASE_REQUISITION, LEAVE_REQUEST)"),
    my_requests: bool = Query(False, description="Filter strictly to requests submitted by the caller"),
) -> list[ApprovalResponse]:
    """Retrieve list of approval requests."""
    return approval_service.list_requests(
        db=db,
        current_user=current_user,
        status_filter=status_filter,
        type_filter=type_filter,
        my_requests_only=my_requests,
    )


@router.get(
    "/metrics",
    response_model=ApprovalSummaryMetrics,
    status_code=status.HTTP_200_OK,
    summary="Get approval KPI metrics",
    description="Retrieve count breakdown of approvals across lifecycle states for dashboard badges.",
)
def get_approval_metrics(
    db: DbSession,
    current_user: CurrentUser,
) -> ApprovalSummaryMetrics:
    """Return dashboard summary metrics."""
    return approval_service.get_summary_metrics(db=db, current_user=current_user)


@router.get(
    "/pending",
    response_model=list[ApprovalResponse],
    status_code=status.HTTP_200_OK,
    summary="List pending approval queue",
    description="Shortcut endpoint to retrieve items awaiting human authorization.",
)
def list_pending_approvals(
    db: DbSession,
    current_user: CurrentUser,
) -> list[ApprovalResponse]:
    """Return pending approval requests."""
    return approval_service.list_requests(
        db=db,
        current_user=current_user,
        status_filter="PENDING",
    )


@router.get(
    "/{request_id}",
    response_model=ApprovalDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Get approval request details",
    description="Retrieve detailed approval proposal with chronological audit trail.",
)
def get_approval_detail(
    request_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> ApprovalDetailResponse:
    """Retrieve full request details with audit history."""
    return approval_service.get_request_detail(
        db=db,
        request_id=request_id,
        current_user=current_user,
    )


@router.post(
    "/{request_id}/approve",
    response_model=ApprovalResponse,
    status_code=status.HTTP_200_OK,
    summary="Approve request",
    description="Authorize a pending proposal with optional reviewer commentary. Enforces anti-self-approval.",
)
def approve_request(
    request_id: int,
    payload: ApprovalReviewRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> ApprovalResponse:
    """Approve a pending approval request."""
    req = approval_service.approve_request(
        db=db,
        request_id=request_id,
        current_user=current_user,
        reason=payload.reason,
    )
    return ApprovalResponse(
        id=req.id,
        request_code=req.request_code,
        request_type=req.request_type,
        title=req.title,
        description=req.description,
        requester_id=req.requester_id,
        requester_email=req.requester.email if req.requester else None,
        assigned_role=req.assigned_role,
        reviewed_by_id=req.reviewed_by_id,
        reviewed_by_email=current_user.email,
        status=req.status,
        action_payload=req.get_payload(),
        execution_result=req.get_execution_result(),
        rejection_reason=req.rejection_reason,
        review_notes=req.review_notes,
        created_at=req.created_at,
        reviewed_at=req.reviewed_at,
        executed_at=req.executed_at,
    )


@router.post(
    "/{request_id}/reject",
    response_model=ApprovalResponse,
    status_code=status.HTTP_200_OK,
    summary="Reject request",
    description="Reject a pending proposal with justification reason. Enforces anti-self-approval.",
)
def reject_request(
    request_id: int,
    payload: ApprovalReviewRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> ApprovalResponse:
    """Reject a pending approval request."""
    req = approval_service.reject_request(
        db=db,
        request_id=request_id,
        current_user=current_user,
        reason=payload.reason,
    )
    return ApprovalResponse(
        id=req.id,
        request_code=req.request_code,
        request_type=req.request_type,
        title=req.title,
        description=req.description,
        requester_id=req.requester_id,
        requester_email=req.requester.email if req.requester else None,
        assigned_role=req.assigned_role,
        reviewed_by_id=req.reviewed_by_id,
        reviewed_by_email=current_user.email,
        status=req.status,
        action_payload=req.get_payload(),
        execution_result=req.get_execution_result(),
        rejection_reason=req.rejection_reason,
        review_notes=req.review_notes,
        created_at=req.created_at,
        reviewed_at=req.reviewed_at,
        executed_at=req.executed_at,
    )


@router.post(
    "/{request_id}/cancel",
    response_model=ApprovalResponse,
    status_code=status.HTTP_200_OK,
    summary="Cancel proposal",
    description="Cancel a pending proposal submitted by the caller or an Administrator.",
)
def cancel_request(
    request_id: int,
    payload: ApprovalReviewRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> ApprovalResponse:
    """Cancel a pending approval request."""
    req = approval_service.cancel_request(
        db=db,
        request_id=request_id,
        current_user=current_user,
        reason=payload.reason,
    )
    return ApprovalResponse(
        id=req.id,
        request_code=req.request_code,
        request_type=req.request_type,
        title=req.title,
        description=req.description,
        requester_id=req.requester_id,
        requester_email=req.requester.email if req.requester else None,
        assigned_role=req.assigned_role,
        reviewed_by_id=req.reviewed_by_id,
        status=req.status,
        action_payload=req.get_payload(),
        execution_result=req.get_execution_result(),
        rejection_reason=req.rejection_reason,
        review_notes=req.review_notes,
        created_at=req.created_at,
        reviewed_at=req.reviewed_at,
        executed_at=req.executed_at,
    )


@router.post(
    "/{request_id}/execute",
    response_model=dict[str, Any],
    status_code=status.HTTP_200_OK,
    summary="Execute approved action",
    description="Execute an approved action (e.g. simulated PO stock on order or official leave record).",
)
def execute_approved_action(
    request_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> dict[str, Any]:
    """Execute verified business action with idempotency protection."""
    return approval_service.execute_approved_action(
        db=db,
        request_id=request_id,
        current_user=current_user,
    )


@router.get(
    "/{request_id}/history",
    response_model=list[ApprovalAuditResponse],
    status_code=status.HTTP_200_OK,
    summary="Get approval audit history",
    description="Retrieve chronological audit history for an approval request.",
)
def get_approval_history(
    request_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> list[ApprovalAuditResponse]:
    """Return audit history records."""
    detail = approval_service.get_request_detail(
        db=db,
        request_id=request_id,
        current_user=current_user,
    )
    return detail.audit_records
