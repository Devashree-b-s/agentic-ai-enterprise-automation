"""AI agent tools for Human-in-the-Loop proposal preparation and status tracking."""

import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.tools.base import rbac_tool
from app.models.approval import ApprovalRequest, ApprovalRequestType, ApprovalStatus
from app.models.employee import Employee
from app.models.inventory import Product
from app.models.user import User, UserRole
from app.schemas.approval import ApprovalCreateRequest
from app.services.approval_service import approval_service

logger = logging.getLogger("app.agents.tools.approval")


@rbac_tool(UserRole.ADMIN, UserRole.MANAGER, UserRole.EMPLOYEE, tool_name="prepare_purchase_requisition")
def prepare_purchase_requisition(
    db: Session,
    current_user: User,
    sku: str,
    quantity: int,
    reason: str | None = None,
) -> dict[str, Any]:
    """Prepare a purchase requisition proposal for low-stock product replenishment requiring human authorization.

    Args:
        db: Active SQLAlchemy database session.
        current_user: Authenticated user creating the proposal.
        sku: Product SKU code to replenish (e.g. 'SKU-GFT-030').
        quantity: Units to order (must be positive integer).
        reason: Optional justification or business context.
    """
    clean_sku = sku.strip().upper()
    qty = int(quantity)

    if qty <= 0:
        raise ValueError("Requisition quantity must be a positive integer greater than zero.")

    # Validate catalog product
    prod = db.scalar(select(Product).where(Product.sku == clean_sku))
    if not prod:
        raise ValueError(f"Product with SKU '{clean_sku}' does not exist in inventory catalog.")

    if not prod.is_active:
        raise ValueError(f"Product '{prod.name}' ({clean_sku}) is marked inactive.")

    title = f"Replenish {qty} units of {prod.name} ({clean_sku})"
    ai_reason = (
        reason or (
            f"Automated AI requisition prepared to restore stock from current {prod.quantity_on_hand} units "
            f"towards safety target of {prod.target_stock} units."
        )
    )

    action_payload = {
        "items": [
            {
                "product_id": prod.id,
                "sku": prod.sku,
                "name": prod.name,
                "quantity": qty,
                "current_on_hand": prod.quantity_on_hand,
                "safety_stock": prod.safety_stock,
                "target_stock": prod.target_stock,
            }
        ],
        "total_units": qty,
        "justification": ai_reason,
    }

    create_payload = ApprovalCreateRequest(
        request_type=ApprovalRequestType.PURCHASE_REQUISITION,
        title=title,
        description=ai_reason,
        assigned_role="Manager",
        action_payload=action_payload,
    )

    approval_req = approval_service.create_request(
        db=db,
        current_user=current_user,
        payload=create_payload,
    )

    return {
        "approval_required": True,
        "status": ApprovalStatus.PENDING.value,
        "request_code": approval_req.request_code,
        "request_id": approval_req.id,
        "title": approval_req.title,
        "sku": prod.sku,
        "product_name": prod.name,
        "quantity_requested": qty,
        "assigned_role": "Manager",
        "human_authorization_notice": (
            f"Purchase requisition '{approval_req.request_code}' has been submitted for human authorization. "
            f"An authorized Manager or Admin must review and approve it on the Approval Dashboard before "
            f"any supplier order or warehouse stock changes can execute."
        ),
        "why_approval_is_needed": (
            "Enterprise financial and supply controls require managerial authorization for inventory purchase "
            "commitments to prevent unauthorized purchasing."
        ),
    }


@rbac_tool(UserRole.ADMIN, UserRole.HR, UserRole.MANAGER, UserRole.EMPLOYEE, tool_name="prepare_leave_request")
def prepare_leave_request(
    db: Session,
    current_user: User,
    start_date: str,
    end_date: str,
    days_count: int,
    leave_type: str = "ANNUAL",
    reason: str | None = None,
) -> dict[str, Any]:
    """Prepare an employee leave request proposal requiring human HR or Manager authorization.

    Args:
        db: Active SQLAlchemy database session.
        current_user: Authenticated employee requesting leave.
        start_date: Starting leave date (YYYY-MM-DD).
        end_date: Ending leave date (YYYY-MM-DD).
        days_count: Working days requested.
        leave_type: Leave category (ANNUAL, SICK, UNPAID, BEREAVEMENT).
        reason: Purpose or explanation for leave.
    """
    days = int(days_count)
    if days <= 0:
        raise ValueError("Leave days count must be a positive integer.")

    # Resolve linked employee
    emp = None
    if current_user.employee_id:
        emp = db.get(Employee, current_user.employee_id)
    if not emp:
        # Fallback to match by email
        emp = db.scalar(select(Employee).where(Employee.email == current_user.email))
    if not emp:
        raise ValueError("Authenticated user is not linked to an active employee HR profile.")

    title = f"{leave_type.capitalize()} Leave ({days} days) - {emp.first_name} {emp.last_name}"
    description = reason or f"Employee leave requested from {start_date} to {end_date}."

    action_payload = {
        "employee_id": emp.id,
        "employee_code": emp.employee_id,
        "employee_name": f"{emp.first_name} {emp.last_name}",
        "leave_type": leave_type.upper(),
        "start_date": start_date.strip(),
        "end_date": end_date.strip(),
        "days_count": days,
        "reason": description,
    }

    create_payload = ApprovalCreateRequest(
        request_type=ApprovalRequestType.LEAVE_REQUEST,
        title=title,
        description=description,
        assigned_role="HR",
        action_payload=action_payload,
    )

    approval_req = approval_service.create_request(
        db=db,
        current_user=current_user,
        payload=create_payload,
    )

    return {
        "approval_required": True,
        "status": ApprovalStatus.PENDING.value,
        "request_code": approval_req.request_code,
        "request_id": approval_req.id,
        "title": approval_req.title,
        "employee_code": emp.employee_id,
        "employee_name": f"{emp.first_name} {emp.last_name}",
        "days_count": days,
        "start_date": start_date,
        "end_date": end_date,
        "assigned_role": "HR",
        "human_authorization_notice": (
            f"Leave request proposal '{approval_req.request_code}' has been submitted for human authorization. "
            f"An HR Specialist or Manager must approve it before official HR leave records are updated."
        ),
    }


@rbac_tool(UserRole.ADMIN, UserRole.MANAGER, UserRole.HR, UserRole.EMPLOYEE, tool_name="check_approval_status")
def check_approval_status(
    db: Session,
    current_user: User,
    request_code: str,
) -> dict[str, Any]:
    """Check the live review and execution status of an approval request by its code.

    Args:
        db: Active SQLAlchemy database session.
        current_user: Authenticated user checking status.
        request_code: Human-readable request code (e.g. 'REQ-PO-20261102-0001').
    """
    code_clean = request_code.strip()
    req = db.scalar(select(ApprovalRequest).where(ApprovalRequest.request_code == code_clean))
    if not req and code_clean.isdigit():
        req = db.get(ApprovalRequest, int(code_clean))

    if not req:
        return {
            "found": False,
            "message": f"Approval request with code '{code_clean}' was not found in the system.",
        }

    # Employee privacy check
    if current_user.role == UserRole.EMPLOYEE.value and req.requester_id != current_user.id:
        return {
            "found": True,
            "authorized": False,
            "message": "Access denied: You do not have permission to inspect this approval request.",
        }

    reviewer_email = None
    if req.reviewed_by_id:
        rev = db.get(User, req.reviewed_by_id)
        if rev:
            reviewer_email = rev.email

    return {
        "found": True,
        "request_code": req.request_code,
        "request_type": req.request_type,
        "title": req.title,
        "status": req.status,
        "assigned_role": req.assigned_role,
        "reviewed_by": reviewer_email,
        "reviewed_at": req.reviewed_at.isoformat() if req.reviewed_at else None,
        "review_notes": req.review_notes,
        "rejection_reason": req.rejection_reason,
        "executed_at": req.executed_at.isoformat() if req.executed_at else None,
        "execution_result": req.get_execution_result(),
    }
