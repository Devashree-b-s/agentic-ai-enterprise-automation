"""Deterministic service layer for employee leave management and reporting."""

import csv
from datetime import date, datetime
from pathlib import Path
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.employee import Employee
from app.models.leave import LeaveRequest, LeaveStatus
from app.schemas.leave import LeaveCreate, LeaveStatusUpdate, LeaveSummaryReport


class LeaveService:
    """Service encapsulating all Leave Request business operations and analytics."""

    @staticmethod
    def get_by_id(db: Session, leave_id: int) -> LeaveRequest | None:
        """Retrieve leave request by primary key ID."""
        return db.get(LeaveRequest, leave_id)

    @staticmethod
    def get_by_code(db: Session, leave_code: str) -> LeaveRequest | None:
        """Retrieve leave request by unique business code (e.g. 'LV-00001')."""
        stmt = select(LeaveRequest).where(LeaveRequest.leave_code == leave_code)
        return db.scalar(stmt)

    @staticmethod
    def list_leaves(
        db: Session,
        employee_id: int | None = None,
        department: str | None = None,
        status_filter: str | None = None,
        leave_type: str | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[LeaveRequest]:
        """Query leave requests with comprehensive multi-criteria filtering."""
        stmt = select(LeaveRequest).join(
            Employee, LeaveRequest.employee_id == Employee.id
        )

        if employee_id is not None:
            stmt = stmt.where(LeaveRequest.employee_id == employee_id)
        if department is not None:
            stmt = stmt.where(Employee.department == department)
        if status_filter is not None:
            stmt = stmt.where(LeaveRequest.status == status_filter.upper())
        if leave_type is not None:
            stmt = stmt.where(LeaveRequest.leave_type == leave_type.upper())
        if start_date is not None:
            stmt = stmt.where(LeaveRequest.start_date >= start_date)
        if end_date is not None:
            stmt = stmt.where(LeaveRequest.end_date <= end_date)

        stmt = stmt.order_by(LeaveRequest.id.asc()).offset(skip).limit(limit)
        return list(db.scalars(stmt).all())

    @staticmethod
    def create_leave_request(db: Session, leave_in: LeaveCreate) -> LeaveRequest:
        """Create a new leave request for an employee with date and existence validation."""
        emp = db.get(Employee, leave_in.employee_id)
        if not emp:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Employee with ID {leave_in.employee_id} not found.",
            )

        if leave_in.end_date < leave_in.start_date:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Leave end_date cannot be earlier than start_date.",
            )

        days_count = (
            leave_in.days_count or (leave_in.end_date - leave_in.start_date).days + 1
        )
        if days_count < 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Leave duration must be at least 1 day.",
            )

        # Generate unique leave code
        count = db.scalar(select(func.count(LeaveRequest.id))) or 0
        leave_code = f"LV-REQ-{count + 1:05d}"

        leave = LeaveRequest(
            leave_code=leave_code,
            employee_id=emp.id,
            employee_code=emp.employee_id,
            leave_type=leave_in.leave_type.value,
            start_date=leave_in.start_date,
            end_date=leave_in.end_date,
            days_count=days_count,
            status=LeaveStatus.PENDING.value,
            reason=leave_in.reason,
        )
        db.add(leave)
        db.commit()
        db.refresh(leave)
        return leave

    @staticmethod
    def update_leave_status(
        db: Session,
        leave: LeaveRequest,
        status_in: LeaveStatusUpdate,
    ) -> LeaveRequest:
        """Update leave status (approve or reject) with state validation."""
        if leave.status != LeaveStatus.PENDING.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot change status of leave request already in terminal state '{leave.status}'.",
            )

        leave.status = status_in.status.value
        if status_in.reason:
            leave.reason = f"{leave.reason or ''} [Review: {status_in.reason}]".strip()

        db.commit()
        db.refresh(leave)
        return leave

    @staticmethod
    def get_leave_summary(db: Session) -> LeaveSummaryReport:
        """Compute aggregate leave metrics across statuses, types, and departments."""
        total_requests = db.scalar(select(func.count(LeaveRequest.id))) or 0

        # Group by status
        status_rows = db.execute(
            select(LeaveRequest.status, func.count(LeaveRequest.id)).group_by(
                LeaveRequest.status
            )
        ).all()
        by_status = {row[0]: row[1] for row in status_rows}

        # Group by leave type
        type_rows = db.execute(
            select(LeaveRequest.leave_type, func.count(LeaveRequest.id)).group_by(
                LeaveRequest.leave_type
            )
        ).all()
        by_type = {row[0]: row[1] for row in type_rows}

        # Group by department
        dept_rows = db.execute(
            select(Employee.department, func.count(LeaveRequest.id))
            .join(LeaveRequest, Employee.id == LeaveRequest.employee_id)
            .group_by(Employee.department)
        ).all()
        by_department = {row[0]: row[1] for row in dept_rows}

        # Days sums
        total_days_requested = db.scalar(select(func.sum(LeaveRequest.days_count))) or 0
        total_days_approved = (
            db.scalar(
                select(func.sum(LeaveRequest.days_count)).where(
                    LeaveRequest.status == LeaveStatus.APPROVED.value
                )
            )
            or 0
        )

        return LeaveSummaryReport(
            total_requests=total_requests,
            by_status=by_status,
            by_type=by_type,
            by_department=by_department,
            total_days_requested=int(total_days_requested),
            total_days_approved=int(total_days_approved),
        )

    @staticmethod
    def import_leaves_from_csv(
        db: Session,
        csv_path: Path,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        """Import leave records from CSV in an idempotent, non-destructive manner.

        Rules:
        - Validates CSV headers ('leave_id', 'employee_id', 'leave_type', 'start_date', 'end_date', 'days_count', 'status').
        - Resolves employee_id to Employee primary key.
        - Validates date order and leave type / status.
        - Preserves existing leave records (matching on leave_code).
        - If dry_run is True, rolls back without committing.
        """
        if not csv_path.is_file():
            raise FileNotFoundError(f"Leave records CSV not found at {csv_path}")

        with open(csv_path, mode="r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            fieldnames = [fn.strip() for fn in (reader.fieldnames or [])]
            required_fields = {
                "leave_id",
                "employee_id",
                "leave_type",
                "start_date",
                "end_date",
                "days_count",
                "status",
            }
            missing = required_fields - set(fieldnames)
            if missing:
                raise ValueError(f"CSV missing required columns: {sorted(missing)}")

            rows = list(reader)

        total_rows = len(rows)
        created_count = 0
        preserved_count = 0
        errors: list[str] = []

        # Cache existing leave codes
        existing_leave_codes = set(db.scalars(select(LeaveRequest.leave_code)).all())

        # Map employee_id business code -> Employee.id
        emp_map = {
            emp.employee_id: emp.id for emp in db.scalars(select(Employee)).all()
        }

        for idx, row in enumerate(rows, start=2):
            leave_code = (row.get("leave_id") or "").strip()
            emp_code = (row.get("employee_id") or "").strip()
            leave_type = (row.get("leave_type") or "").strip().upper()
            start_date_str = (row.get("start_date") or "").strip()
            end_date_str = (row.get("end_date") or "").strip()
            days_count_str = (row.get("days_count") or "").strip()
            status_val = (row.get("status") or "").strip().upper()

            if not leave_code or not emp_code:
                errors.append(f"Row {idx}: Missing leave_id or employee_id")
                continue

            if leave_code in existing_leave_codes:
                preserved_count += 1
                continue

            emp_internal_id = emp_map.get(emp_code)
            if not emp_internal_id:
                errors.append(
                    f"Row {idx}: Employee code '{emp_code}' not found in database."
                )
                continue

            try:
                start_date_val = datetime.strptime(start_date_str, "%Y-%m-%d").date()
                end_date_val = datetime.strptime(end_date_str, "%Y-%m-%d").date()
            except ValueError:
                errors.append(f"Row {idx}: Invalid date format (expected YYYY-MM-DD)")
                continue

            if end_date_val < start_date_val:
                errors.append(f"Row {idx}: end_date earlier than start_date")
                continue

            try:
                days_count = int(days_count_str)
            except ValueError:
                days_count = (end_date_val - start_date_val).days + 1

            # Validate or normalize status
            if status_val not in ("PENDING", "APPROVED", "REJECTED"):
                status_val = "PENDING"

            new_leave = LeaveRequest(
                leave_code=leave_code,
                employee_id=emp_internal_id,
                employee_code=emp_code,
                leave_type=leave_type,
                start_date=start_date_val,
                end_date=end_date_val,
                days_count=days_count,
                status=status_val,
                reason=None,
            )
            db.add(new_leave)
            existing_leave_codes.add(leave_code)
            created_count += 1

        if dry_run:
            db.rollback()
        else:
            db.commit()

        return {
            "total_rows": total_rows,
            "created": created_count,
            "preserved": preserved_count,
            "errors": errors,
            "dry_run": dry_run,
        }


leave_service = LeaveService()
