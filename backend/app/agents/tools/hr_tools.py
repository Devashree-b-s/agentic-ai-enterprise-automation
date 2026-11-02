import logging
from typing import Any

from sqlalchemy.orm import Session

from app.agents.tools.base import rbac_tool
from app.models.user import User, UserRole
from app.services.analytics_service import analytics_service
from app.services.hr_service import hr_service
from app.services.leave_service import leave_service

logger = logging.getLogger("app.agents.tools.hr")

class LeaveQueryResult(list):
    """List of leave records that preserves list interface while attaching total_count metadata."""

    def __init__(
        self,
        records: list[dict[str, Any]],
        total_count: int,
        filters: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(records)
        self.total_count = total_count
        self.filters = filters or {}


@rbac_tool(
    UserRole.ADMIN,
    UserRole.HR,
    UserRole.MANAGER,
    allow_employee_self=True,
    tool_name="get_employee_by_code",
)
def get_employee_by_code(
    db: Session,
    current_user: User,
    employee_code: str,
) -> dict[str, Any]:
    """Retrieve employee details by their employee business code (e.g. 'EMP-0001').

    Employees may only view their own linked profile. Admin, HR, and Manager
    can view any employee profile.
    """
    cleaned_code = employee_code.strip()

    # Strict server-side employee self-access restriction:
    # Check authorization BEFORE querying any external employee data
    if current_user.role == UserRole.EMPLOYEE.value:
        if not current_user.employee_id:
            logger.warning(
                "Employee profile access denied: user_id=%s has no linked employee profile",
                current_user.id,
            )
            raise PermissionError(
                "Access denied: Employee user is not linked to an employee profile."
            )

        own_emp = current_user.employee or hr_service.get_employee(
            db, current_user.employee_id
        )
        if not own_emp or own_emp.employee_id != cleaned_code:
            logger.warning(
                "Employee unauthorized profile access attempt: user_id=%s tried to access employee_code=%s",
                current_user.id,
                cleaned_code,
            )
            raise PermissionError(
                "Access denied: You do not have permission to view this employee profile."
            )
        employee = own_emp
    else:
        employee = hr_service.get_by_employee_code(db, cleaned_code)
        if not employee:
            return {
                "found": False,
                "message": f"Employee code '{cleaned_code}' was not found.",
            }

    # Sanitize and format data
    data: dict[str, Any] = {
        "found": True,
        "employee_id": employee.employee_id,
        "first_name": employee.first_name,
        "last_name": employee.last_name,
        "department": employee.department,
        "role": employee.role,
        "is_active": employee.is_active,
    }

    # Only expose salary if caller is Admin or HR
    if current_user.role in (UserRole.ADMIN.value, UserRole.HR.value):
        data["salary"] = employee.salary

    return data


@rbac_tool(
    UserRole.ADMIN,
    UserRole.HR,
    UserRole.MANAGER,
    tool_name="list_department_staffing",
)
def list_department_staffing(
    db: Session,
    current_user: User,
    department: str | None = None,
) -> dict[str, Any]:
    """Retrieve department-level employee headcount and active staffing counts."""
    hr_data = analytics_service.get_hr_analytics(db)
    dept_counts = hr_data.by_department

    if department:
        target = department.strip()
        matched = {k: v for k, v in dept_counts.items() if k.lower() == target.lower()}
        if not matched:
            return {
                "department": department,
                "found": False,
                "headcount": 0,
                "available_departments": list(dept_counts.keys()),
            }
        dept_name = next(iter(matched))
        return {
            "department": dept_name,
            "found": True,
            "headcount": matched[dept_name],
        }

    return {
        "total_departments": len(dept_counts),
        "department_headcounts": dept_counts,
        "total_workforce": hr_data.total_employees,
        "active_workforce": hr_data.active_employees,
    }


@rbac_tool(
    UserRole.ADMIN,
    UserRole.HR,
    UserRole.MANAGER,
    allow_employee_self=True,
    tool_name="query_leave_records",
)
def query_leave_records(
    db: Session,
    current_user: User,
    department: str | None = None,
    status: str | None = None,
    leave_type: str | None = None,
    employee_code: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    limit: int = 50,
) -> LeaveQueryResult:
    """Query employee leave records with filtering by department, status, leave type, employee, or date range.

    Returns a list of matching records with total_matching_count metadata.
    Employees are strictly restricted to querying their own linked leave records.
    """
    from datetime import datetime

    from sqlalchemy import func, select

    from app.models.employee import Employee
    from app.models.leave import LeaveRequest

    capped_limit = min(max(1, limit), 100)

    # Parse date arguments if provided
    parsed_start = None
    if start_date:
        try:
            parsed_start = datetime.strptime(start_date.strip(), "%Y-%m-%d").date()
        except ValueError:
            parsed_start = None

    parsed_end = None
    if end_date:
        try:
            parsed_end = datetime.strptime(end_date.strip(), "%Y-%m-%d").date()
        except ValueError:
            parsed_end = None

    # Server-side enforcement of employee self-access
    emp_internal_id = None
    clean_emp_code = employee_code.strip() if employee_code else None
    clean_dept = department.strip() if department else None
    clean_status = status.strip().upper() if status else None
    clean_type = leave_type.strip().upper() if leave_type else None

    filters: dict[str, Any] = {}
    if clean_status:
        filters["status"] = clean_status
    if clean_dept:
        filters["department"] = clean_dept
    if clean_type:
        filters["leave_type"] = clean_type
    if clean_emp_code:
        filters["employee_code"] = clean_emp_code
    if start_date:
        filters["start_date"] = start_date
    if end_date:
        filters["end_date"] = end_date

    if current_user.role == UserRole.EMPLOYEE.value:
        if not current_user.employee_id:
            return LeaveQueryResult([], total_count=0, filters=filters)
        emp_internal_id = current_user.employee_id
        clean_dept = None  # Prevent querying other departments
    elif clean_emp_code:
        emp = hr_service.get_by_employee_code(db, clean_emp_code)
        if not emp:
            return LeaveQueryResult([], total_count=0, filters=filters)
        emp_internal_id = emp.id

    # Compute total matching count in database
    count_stmt = select(func.count(LeaveRequest.id)).join(
        Employee, LeaveRequest.employee_id == Employee.id
    )
    if emp_internal_id is not None:
        count_stmt = count_stmt.where(LeaveRequest.employee_id == emp_internal_id)
    if clean_dept is not None:
        count_stmt = count_stmt.where(Employee.department == clean_dept)
    if clean_status is not None:
        count_stmt = count_stmt.where(LeaveRequest.status == clean_status)
    if clean_type is not None:
        count_stmt = count_stmt.where(LeaveRequest.leave_type == clean_type)
    if parsed_start is not None:
        count_stmt = count_stmt.where(LeaveRequest.start_date >= parsed_start)
    if parsed_end is not None:
        count_stmt = count_stmt.where(LeaveRequest.end_date <= parsed_end)

    total_matching = db.scalar(count_stmt) or 0

    leaves = leave_service.list_leaves(
        db=db,
        employee_id=emp_internal_id,
        department=clean_dept,
        status_filter=clean_status,
        leave_type=clean_type,
        start_date=parsed_start,
        end_date=parsed_end,
        skip=0,
        limit=capped_limit,
    )

    records = [
        {
            "leave_id": lv.id,
            "leave_code": lv.leave_code,
            "employee_id": lv.employee_id,
            "employee_code": lv.employee_code,
            "leave_type": lv.leave_type,
            "start_date": str(lv.start_date),
            "end_date": str(lv.end_date),
            "days_count": lv.days_count,
            "status": lv.status,
            "reason": lv.reason,
        }
        for lv in leaves
    ]

    return LeaveQueryResult(records, total_count=total_matching, filters=filters)


@rbac_tool(
    UserRole.ADMIN,
    UserRole.HR,
    UserRole.MANAGER,
    tool_name="get_monthly_leave_trends",
)
def get_monthly_leave_trends(
    db: Session,
    current_user: User,
) -> list[dict[str, Any]]:
    """Retrieve monthly workforce leave request counts, approval counts, and total days taken."""
    hr_data = analytics_service.get_hr_analytics(db)
    return [
        {
            "year_month": item.year_month,
            "total_requests": item.total_requests,
            "approved_requests": item.approved_requests,
            "total_days": item.total_days,
        }
        for item in hr_data.monthly_leave_trends
    ]


@rbac_tool(
    UserRole.ADMIN,
    UserRole.HR,
    UserRole.MANAGER,
    tool_name="get_department_leave_summaries",
)
def get_department_leave_summaries(
    db: Session,
    current_user: User,
) -> dict[str, Any]:
    """Retrieve summarized breakdown of leave requests by status, leave type, and department."""
    summary = leave_service.get_leave_summary(db)
    return {
        "total_requests": summary.total_requests,
        "by_status": summary.by_status,
        "by_leave_type": summary.by_type,
        "by_department": summary.by_department,
        "total_days_requested": summary.total_days_requested,
        "total_days_approved": summary.total_days_approved,
    }
