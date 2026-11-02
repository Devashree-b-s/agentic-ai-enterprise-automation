"""Service layer for Human-in-the-Loop approval workflows."""

import json
import logging
from datetime import date, datetime
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.approval import (
    ApprovalAudit,
    ApprovalRequest,
    ApprovalRequestType,
    ApprovalStatus,
)
from app.models.employee import Employee
from app.models.inventory import Product
from app.models.leave import LeaveRequest, LeaveStatus
from app.models.user import User, UserRole
from app.schemas.approval import (
    ApprovalAuditResponse,
    ApprovalCreateRequest,
    ApprovalDetailResponse,
    ApprovalResponse,
    ApprovalSummaryMetrics,
)

logger = logging.getLogger("app.services.approval")


class ApprovalService:
    """Manages the lifecycle of Human-in-the-Loop approvals and verified execution."""

    @staticmethod
    def _generate_code(db: Session, request_type: ApprovalRequestType) -> str:
        """Generate human-readable unique code (e.g. REQ-PO-20261102-0001)."""
        prefix = "PO" if request_type == ApprovalRequestType.PURCHASE_REQUISITION else "LV"
        date_str = datetime.now().strftime("%Y%m%d")
        
        # Count existing today
        stmt = select(func.count(ApprovalRequest.id)).where(
            ApprovalRequest.request_code.like(f"REQ-{prefix}-{date_str}-%")
        )
        count = db.scalar(stmt) or 0
        return f"REQ-{prefix}-{date_str}-{count + 1:04d}"

    def create_request(
        self,
        db: Session,
        current_user: User,
        payload: ApprovalCreateRequest,
    ) -> ApprovalRequest:
        """Submit a new business action proposal entering PENDING approval state."""
        # 1. Idempotency safeguard
        if payload.idempotency_token:
            existing = db.scalar(
                select(ApprovalRequest).where(
                    ApprovalRequest.idempotency_token == payload.idempotency_token
                )
            )
            if existing:
                logger.info(
                    "Idempotent request detected for token=%s; returning existing code=%s",
                    payload.idempotency_token,
                    existing.request_code,
                )
                return existing

        # 2. Domain-specific action payload validation
        action_data = payload.action_payload
        if payload.request_type == ApprovalRequestType.PURCHASE_REQUISITION:
            items = action_data.get("items", [])
            if not items:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Purchase requisition action payload must include at least one item.",
                )
            # Validate products
            for item in items:
                sku = item.get("sku")
                qty = item.get("quantity")
                if not sku or not isinstance(qty, int) or qty <= 0:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Invalid purchase order item: SKU={sku}, quantity={qty}. Quantity must be positive integer.",
                    )
                prod = db.scalar(select(Product).where(Product.sku == sku))
                if not prod or not prod.is_active:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"Product with SKU '{sku}' not found or inactive in catalog.",
                    )
            assigned_role = payload.assigned_role or "Manager"

        elif payload.request_type == ApprovalRequestType.LEAVE_REQUEST:
            emp_code = action_data.get("employee_code")
            start_str = action_data.get("start_date")
            end_str = action_data.get("end_date")
            days_count = action_data.get("days_count")
            leave_type = action_data.get("leave_type")

            if not emp_code or not start_str or not end_str or not days_count or not leave_type:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Leave request payload requires employee_code, start_date, end_date, days_count, and leave_type.",
                )

            # Validate employee
            emp = db.scalar(select(Employee).where(Employee.employee_id == emp_code))
            if not emp or not emp.is_active:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Employee '{emp_code}' not found or inactive.",
                )

            # Self-scope check for Employee role
            if current_user.role == UserRole.EMPLOYEE.value and current_user.employee_id != emp.id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Employees are only authorized to submit leave requests for themselves.",
                )

            assigned_role = payload.assigned_role or "HR"
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported request type: {payload.request_type}",
            )

        # 3. Create persistent ApprovalRequest
        req_code = self._generate_code(db, payload.request_type)
        approval_req = ApprovalRequest(
            request_code=req_code,
            request_type=payload.request_type.value,
            title=payload.title.strip(),
            description=payload.description.strip() if payload.description else None,
            requester_id=current_user.id,
            assigned_role=assigned_role,
            status=ApprovalStatus.PENDING.value,
            action_payload=json.dumps(action_data),
            idempotency_token=payload.idempotency_token,
        )
        db.add(approval_req)
        db.commit()
        db.refresh(approval_req)

        # 4. Audit Log entry
        audit = ApprovalAudit(
            approval_request_id=approval_req.id,
            actor_id=current_user.id,
            actor_email=current_user.email,
            actor_role=current_user.role,
            action="CREATED",
            from_status=None,
            to_status=ApprovalStatus.PENDING.value,
            comment=payload.description or "Submitted proposal for human authorization",
        )
        db.add(audit)
        db.commit()

        logger.info(
            "Created ApprovalRequest code=%s type=%s by user_id=%s",
            approval_req.request_code,
            approval_req.request_type,
            current_user.id,
        )
        return approval_req

    def list_requests(
        self,
        db: Session,
        current_user: User,
        status_filter: str | None = None,
        type_filter: str | None = None,
        my_requests_only: bool = False,
    ) -> list[ApprovalResponse]:
        """List approval requests filtered by status, type, and RBAC ownership."""
        stmt = (
            select(ApprovalRequest, User.email.label("requester_email"))
            .join(User, ApprovalRequest.requester_id == User.id)
            .order_by(ApprovalRequest.created_at.desc())
        )

        # RBAC and ownership filtering:
        # - Employees can only see their own requests
        # - Managers can see their own + Manager-assigned + Purchase Requisitions
        # - HR can see their own + HR-assigned + Leave Requests
        # - Admins can see everything
        if current_user.role == UserRole.EMPLOYEE.value or my_requests_only:
            stmt = stmt.where(ApprovalRequest.requester_id == current_user.id)
        elif current_user.role == UserRole.HR.value:
            stmt = stmt.where(
                (ApprovalRequest.requester_id == current_user.id)
                | (ApprovalRequest.request_type == ApprovalRequestType.LEAVE_REQUEST.value)
                | (ApprovalRequest.assigned_role == "HR")
            )
        elif current_user.role == UserRole.MANAGER.value:
            stmt = stmt.where(
                (ApprovalRequest.requester_id == current_user.id)
                | (ApprovalRequest.assigned_role.in_(["Manager", "HR"]))
                | (ApprovalRequest.request_type.in_([ApprovalRequestType.PURCHASE_REQUISITION.value, ApprovalRequestType.LEAVE_REQUEST.value]))
            )

        if status_filter:
            stmt = stmt.where(ApprovalRequest.status == status_filter.upper())
        if type_filter:
            stmt = stmt.where(ApprovalRequest.request_type == type_filter.upper())

        rows = db.execute(stmt).all()
        results: list[ApprovalResponse] = []

        for req, req_email in rows:
            rev_email = None
            if req.reviewed_by_id:
                rev_user = db.get(User, req.reviewed_by_id)
                if rev_user:
                    rev_email = rev_user.email

            results.append(
                ApprovalResponse(
                    id=req.id,
                    request_code=req.request_code,
                    request_type=req.request_type,
                    title=req.title,
                    description=req.description,
                    requester_id=req.requester_id,
                    requester_email=req_email,
                    assigned_role=req.assigned_role,
                    reviewed_by_id=req.reviewed_by_id,
                    reviewed_by_email=rev_email,
                    status=req.status,
                    action_payload=req.get_payload(),
                    execution_result=req.get_execution_result(),
                    rejection_reason=req.rejection_reason,
                    review_notes=req.review_notes,
                    created_at=req.created_at,
                    reviewed_at=req.reviewed_at,
                    executed_at=req.executed_at,
                )
            )
        return results

    def get_request_detail(
        self,
        db: Session,
        request_id: int,
        current_user: User,
    ) -> ApprovalDetailResponse:
        """Retrieve full details of an approval request with audit trail."""
        req = db.get(ApprovalRequest, request_id)
        if not req:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Approval request {request_id} not found.",
            )

        # Access check: Employee can only view their own
        if current_user.role == UserRole.EMPLOYEE.value and req.requester_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: You do not have permission to view this approval request.",
            )

        requester = db.get(User, req.requester_id)
        requester_email = requester.email if requester else None

        rev_email = None
        if req.reviewed_by_id:
            reviewer = db.get(User, req.reviewed_by_id)
            if reviewer:
                rev_email = reviewer.email

        audits = (
            db.scalars(
                select(ApprovalAudit)
                .where(ApprovalAudit.approval_request_id == req.id)
                .order_by(ApprovalAudit.id.asc())
            ).all()
        )

        audit_responses = [
            ApprovalAuditResponse(
                id=a.id,
                approval_request_id=a.approval_request_id,
                actor_id=a.actor_id,
                actor_email=a.actor_email,
                actor_role=a.actor_role,
                action=a.action,
                from_status=a.from_status,
                to_status=a.to_status,
                comment=a.comment,
                created_at=a.created_at,
            )
            for a in audits
        ]

        return ApprovalDetailResponse(
            id=req.id,
            request_code=req.request_code,
            request_type=req.request_type,
            title=req.title,
            description=req.description,
            requester_id=req.requester_id,
            requester_email=requester_email,
            assigned_role=req.assigned_role,
            reviewed_by_id=req.reviewed_by_id,
            reviewed_by_email=rev_email,
            status=req.status,
            action_payload=req.get_payload(),
            execution_result=req.get_execution_result(),
            rejection_reason=req.rejection_reason,
            review_notes=req.review_notes,
            created_at=req.created_at,
            reviewed_at=req.reviewed_at,
            executed_at=req.executed_at,
            audit_records=audit_responses,
        )

    def _verify_review_permission(self, req: ApprovalRequest, current_user: User) -> None:
        """Strict server-side Python authorization check for reviewers."""
        # 1. Anti-Self-Approval Enforcement
        if req.requester_id == current_user.id:
            logger.warning(
                "Self-approval blocked: user_id=%s attempted to approve own request_code=%s",
                current_user.id,
                req.request_code,
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Self-approval policy violation: Users are not permitted to approve or reject their own requests.",
            )

        # 2. RBAC Role Boundaries
        role = current_user.role
        if role == UserRole.ADMIN.value:
            return  # Admin can review any request

        if req.request_type == ApprovalRequestType.PURCHASE_REQUISITION.value:
            if role != UserRole.MANAGER.value:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access forbidden: Purchase requisitions require Admin or Manager authorization.",
                )
        elif (
            req.request_type == ApprovalRequestType.LEAVE_REQUEST.value
            and role not in (UserRole.HR.value, UserRole.MANAGER.value)
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access forbidden: Leave requests require Admin, HR, or Manager authorization.",
            )

    def approve_request(
        self,
        db: Session,
        request_id: int,
        current_user: User,
        reason: str | None = None,
    ) -> ApprovalRequest:
        """Approve a pending approval request."""
        req = db.get(ApprovalRequest, request_id)
        if not req:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Approval request {request_id} not found.",
            )

        if req.status != ApprovalStatus.PENDING.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot approve request currently in terminal state '{req.status}'.",
            )

        self._verify_review_permission(req, current_user)

        old_status = req.status
        req.status = ApprovalStatus.APPROVED.value
        req.reviewed_by_id = current_user.id
        req.reviewed_at = func.now()
        req.review_notes = reason.strip() if reason else None

        db.commit()
        db.refresh(req)

        # Log audit record
        audit = ApprovalAudit(
            approval_request_id=req.id,
            actor_id=current_user.id,
            actor_email=current_user.email,
            actor_role=current_user.role,
            action="APPROVED",
            from_status=old_status,
            to_status=ApprovalStatus.APPROVED.value,
            comment=reason or "Approved by authorized reviewer",
        )
        db.add(audit)
        db.commit()

        logger.info("Approved request_code=%s by reviewer_id=%s", req.request_code, current_user.id)
        return req

    def reject_request(
        self,
        db: Session,
        request_id: int,
        current_user: User,
        reason: str | None = None,
    ) -> ApprovalRequest:
        """Reject a pending approval request with reason."""
        req = db.get(ApprovalRequest, request_id)
        if not req:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Approval request {request_id} not found.",
            )

        if req.status != ApprovalStatus.PENDING.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot reject request currently in terminal state '{req.status}'.",
            )

        self._verify_review_permission(req, current_user)

        clean_reason = (reason or "Request rejected by reviewer").strip()
        old_status = req.status
        req.status = ApprovalStatus.REJECTED.value
        req.reviewed_by_id = current_user.id
        req.reviewed_at = func.now()
        req.rejection_reason = clean_reason
        req.review_notes = clean_reason

        db.commit()
        db.refresh(req)

        audit = ApprovalAudit(
            approval_request_id=req.id,
            actor_id=current_user.id,
            actor_email=current_user.email,
            actor_role=current_user.role,
            action="REJECTED",
            from_status=old_status,
            to_status=ApprovalStatus.REJECTED.value,
            comment=clean_reason,
        )
        db.add(audit)
        db.commit()

        logger.info("Rejected request_code=%s by reviewer_id=%s", req.request_code, current_user.id)
        return req

    def cancel_request(
        self,
        db: Session,
        request_id: int,
        current_user: User,
        reason: str | None = None,
    ) -> ApprovalRequest:
        """Cancel a pending request (requester or Admin only)."""
        req = db.get(ApprovalRequest, request_id)
        if not req:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Approval request {request_id} not found.",
            )

        if req.status != ApprovalStatus.PENDING.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot cancel request currently in state '{req.status}'.",
            )

        if req.requester_id != current_user.id and current_user.role != UserRole.ADMIN.value:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only the proposal requester or an Administrator can cancel a pending request.",
            )

        old_status = req.status
        req.status = ApprovalStatus.CANCELLED.value
        clean_comment = (reason or "Cancelled by requester").strip()
        req.review_notes = clean_comment

        db.commit()
        db.refresh(req)

        audit = ApprovalAudit(
            approval_request_id=req.id,
            actor_id=current_user.id,
            actor_email=current_user.email,
            actor_role=current_user.role,
            action="CANCELLED",
            from_status=old_status,
            to_status=ApprovalStatus.CANCELLED.value,
            comment=clean_comment,
        )
        db.add(audit)
        db.commit()

        return req

    def execute_approved_action(
        self,
        db: Session,
        request_id: int,
        current_user: User,
    ) -> dict[str, Any]:
        """Execute the approved action with duplicate execution prevention and idempotency."""
        req = db.get(ApprovalRequest, request_id)
        if not req:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Approval request {request_id} not found.",
            )

        # Enforce execution pre-conditions
        if req.status == ApprovalStatus.PENDING.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot execute a pending approval request. Human authorization is required first.",
            )
        if req.status == ApprovalStatus.REJECTED.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot execute a rejected approval request.",
            )
        if req.status == ApprovalStatus.CANCELLED.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot execute a cancelled approval request.",
            )
        if req.status == ApprovalStatus.EXECUTED.value:
            logger.warning("Duplicate execution attempt blocked for request_code=%s", req.request_code)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Approval request '{req.request_code}' has already been executed. Duplicate execution prevented.",
            )

        if req.status != ApprovalStatus.APPROVED.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot execute request in state '{req.status}'. Must be APPROVED.",
            )

        # RBAC: Only Admin, Manager, or HR can trigger execution
        if current_user.role not in (UserRole.ADMIN.value, UserRole.MANAGER.value, UserRole.HR.value):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: You do not have permission to execute approved actions.",
            )

        payload = req.get_payload()
        execution_outcome: dict[str, Any] = {}

        try:
            # 1. Purchase Requisition Execution (Simulated PO)
            if req.request_type == ApprovalRequestType.PURCHASE_REQUISITION.value:
                items = payload.get("items", [])
                po_number = f"PO-SIM-{req.request_code}"
                updated_products = []
                total_ordered_units = 0

                for item in items:
                    sku = item.get("sku")
                    qty = int(item.get("quantity", 0))
                    prod = db.scalar(select(Product).where(Product.sku == sku))
                    if prod:
                        prev_on_order = prod.quantity_on_order
                        # Increment committed purchase quantity on order
                        prod.quantity_on_order += qty
                        total_ordered_units += qty

                        # Note: Physical stock (quantity_on_hand) is NOT modified here,
                        # and NO StockMovement(movement_type=IN) is created, because
                        # goods are on order with the supplier and have not yet been
                        # delivered/received at the warehouse dock.
                        updated_products.append({
                            "sku": prod.sku,
                            "name": prod.name,
                            "units_ordered": qty,
                            "previous_quantity_on_order": prev_on_order,
                            "new_quantity_on_order": prod.quantity_on_order,
                            "quantity_on_hand_unchanged": prod.quantity_on_hand,
                        })

                execution_outcome = {
                    "simulated_po_number": po_number,
                    "products_updated": updated_products,
                    "total_units_ordered": total_ordered_units,
                    "execution_timestamp": datetime.now().isoformat(),
                    "status": "CONFIRMED_ON_ORDER",
                    "quantity_on_order_updated": True,
                    "quantity_on_hand_updated": False,
                    "physical_movement_recorded": False,
                    "notes": (
                        f"Simulated purchase order {po_number} placed with supplier. "
                        f"Product quantity_on_order incremented by {total_ordered_units} units. "
                        f"Physical warehouse stock (quantity_on_hand) remains unchanged; physical receipt "
                        f"movement will only be recorded when warehouse stock-in delivery occurs."
                    ),
                }

            # 2. Leave Request Execution (Official HR Leave Request Created)
            elif req.request_type == ApprovalRequestType.LEAVE_REQUEST.value:
                emp_code = payload.get("employee_code")
                emp = db.scalar(select(Employee).where(Employee.employee_id == emp_code))
                if not emp:
                    raise ValueError(f"Employee {emp_code} not found during execution.")

                # Generate unique leave code
                leave_code = f"LV-{datetime.now().strftime('%Y%m%d')}-{emp.employee_id}-{int(datetime.now().timestamp()) % 10000:04d}"
                start_date = date.fromisoformat(payload["start_date"])
                end_date = date.fromisoformat(payload["end_date"])

                leave_record = LeaveRequest(
                    leave_code=leave_code,
                    employee_id=emp.id,
                    employee_code=emp.employee_id,
                    leave_type=payload["leave_type"],
                    start_date=start_date,
                    end_date=end_date,
                    days_count=int(payload["days_count"]),
                    status=LeaveStatus.APPROVED.value,  # Enters HR system pre-approved by workflow
                    reason=f"Approved via workflow {req.request_code}: {payload.get('reason', '')}".strip(),
                )
                db.add(leave_record)
                db.flush()

                execution_outcome = {
                    "official_leave_code": leave_code,
                    "employee_code": emp.employee_id,
                    "employee_name": f"{emp.first_name} {emp.last_name}",
                    "status": "APPROVED",
                    "days_count": leave_record.days_count,
                    "start_date": payload["start_date"],
                    "end_date": payload["end_date"],
                    "notes": "Official HR leave record created in APPROVED status.",
                }

            # Commit business changes and update approval request
            req.status = ApprovalStatus.EXECUTED.value
            req.executed_at = func.now()
            req.execution_result = json.dumps(execution_outcome)

            audit = ApprovalAudit(
                approval_request_id=req.id,
                actor_id=current_user.id,
                actor_email=current_user.email,
                actor_role=current_user.role,
                action="EXECUTED",
                from_status=ApprovalStatus.APPROVED.value,
                to_status=ApprovalStatus.EXECUTED.value,
                comment=f"Action executed successfully: {execution_outcome.get('simulated_po_number') or execution_outcome.get('official_leave_code')}",
            )
            db.add(audit)
            db.commit()
            db.refresh(req)

            logger.info("Successfully executed approved action for request_code=%s", req.request_code)
            return execution_outcome

        except Exception as exc:
            db.rollback()
            logger.exception("Failed executing approved action for request_code=%s", req.request_code)
            req.status = ApprovalStatus.FAILED.value
            req.execution_result = json.dumps({"error": str(exc)})
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Execution of approved action failed: {exc}",
            ) from exc

    def get_summary_metrics(self, db: Session, current_user: User) -> ApprovalSummaryMetrics:
        """Calculate counts for the approval dashboard header."""
        stmt = select(ApprovalRequest.status, func.count(ApprovalRequest.id)).group_by(ApprovalRequest.status)
        if current_user.role == UserRole.EMPLOYEE.value:
            stmt = stmt.where(ApprovalRequest.requester_id == current_user.id)
        
        counts = dict(db.execute(stmt).all())
        total = sum(counts.values())

        return ApprovalSummaryMetrics(
            pending_count=counts.get(ApprovalStatus.PENDING.value, 0),
            approved_count=counts.get(ApprovalStatus.APPROVED.value, 0),
            executed_count=counts.get(ApprovalStatus.EXECUTED.value, 0),
            rejected_count=counts.get(ApprovalStatus.REJECTED.value, 0),
            cancelled_count=counts.get(ApprovalStatus.CANCELLED.value, 0),
            total_count=total,
        )


approval_service = ApprovalService()
