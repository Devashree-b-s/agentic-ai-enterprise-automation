"""API router endpoints for HR, Employee management, and Leave management with RBAC."""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.deps import CurrentUser, DbSession, require_roles
from app.models.user import User, UserRole
from app.schemas.employee import (
    EmployeeCreate,
    EmployeeResponse,
    EmployeeUpdate,
)
from app.schemas.leave import (
    LeaveCreate,
    LeaveResponse,
    LeaveStatusUpdate,
    LeaveSummaryReport,
)
from app.services.hr_service import hr_service
from app.services.leave_service import leave_service

# Top-level HR router mounted under /api/v1/hr
router = APIRouter()

# Sub-routers
employees_router = APIRouter(prefix="/employees", tags=["HR - Employees"])
leaves_router = APIRouter(prefix="/leaves", tags=["HR - Leaves"])
reports_router = APIRouter(prefix="/reports", tags=["HR - Reports"])

# Role requirement dependencies
RequireAdminOrHR = Annotated[User, Depends(require_roles(UserRole.ADMIN, UserRole.HR))]
RequireStaffOrManager = Annotated[
    User, Depends(require_roles(UserRole.ADMIN, UserRole.HR, UserRole.MANAGER))
]


# ============================================================================
# Employee Endpoints
# ============================================================================


@employees_router.post(
    "/",
    response_model=EmployeeResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new employee (Admin & HR only)",
    description="Register a new employee. Restricted to Admin and HR roles.",
)
def create_employee(
    employee_in: EmployeeCreate,
    db: DbSession,
    _: RequireAdminOrHR,
) -> EmployeeResponse:
    """Create a new employee with validation and duplicate prevention."""
    if hr_service.get_by_employee_code(db, employee_in.employee_id):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Employee with ID '{employee_in.employee_id}' already exists.",
        )

    if hr_service.get_by_email(db, employee_in.email):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Employee with email '{employee_in.email}' already exists.",
        )

    return hr_service.create_employee(db, employee_in)


@employees_router.get(
    "/",
    response_model=list[EmployeeResponse],
    status_code=status.HTTP_200_OK,
    summary="List all employees (Admin, HR, Manager only)",
    description="Retrieve a paginated list of employees. Restricted to Admin, HR, and Manager.",
)
def list_employees(
    db: DbSession,
    _: RequireStaffOrManager,
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(
        100, ge=1, le=500, description="Max number of records to return"
    ),
    department: str | None = Query(None, description="Filter by department"),
    is_active: bool | None = Query(None, description="Filter by active status"),
) -> list[EmployeeResponse]:
    """Retrieve employees with pagination and filters."""
    return hr_service.list_employees(
        db,
        skip=skip,
        limit=limit,
        department=department,
        is_active=is_active,
    )


@employees_router.get(
    "/{employee_id}",
    response_model=EmployeeResponse,
    status_code=status.HTTP_200_OK,
    summary="Get employee by ID",
    description=(
        "Retrieve employee profile. Admin, HR, and Manager can access any profile. "
        "Employee role users can only access their own linked profile."
    ),
)
def get_employee(
    employee_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> EmployeeResponse:
    """Fetch employee details by database ID with employee self-access restriction."""
    employee = hr_service.get_by_id(db, employee_id)
    if not employee:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Employee with ID {employee_id} not found.",
        )

    if (
        current_user.role == UserRole.EMPLOYEE.value
        and current_user.employee_id != employee.id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden: You can only view your own employee profile.",
        )

    return employee


@employees_router.put(
    "/{employee_id}",
    response_model=EmployeeResponse,
    status_code=status.HTTP_200_OK,
    summary="Update an employee (Admin & HR only)",
    description="Update employee attributes. Restricted to Admin and HR roles.",
)
def update_employee(
    employee_id: int,
    employee_in: EmployeeUpdate,
    db: DbSession,
    _: RequireAdminOrHR,
) -> EmployeeResponse:
    """Update employee fields with duplicate email validation."""
    employee = hr_service.get_by_id(db, employee_id)
    if not employee:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Employee with ID {employee_id} not found.",
        )

    if employee_in.email is not None and employee_in.email != employee.email:
        existing = hr_service.get_by_email(db, employee_in.email)
        if existing and existing.id != employee_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Employee with email '{employee_in.email}' already exists.",
            )

    return hr_service.update_employee(db, employee, employee_in)


@employees_router.delete(
    "/{employee_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an employee (Admin & HR only)",
    description="Permanently delete an employee record. Restricted to Admin and HR roles.",
)
def delete_employee(
    employee_id: int,
    db: DbSession,
    _: RequireAdminOrHR,
) -> None:
    """Delete employee by database ID or raise 404."""
    employee = hr_service.get_by_id(db, employee_id)
    if not employee:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Employee with ID {employee_id} not found.",
        )
    hr_service.delete_employee(db, employee)


# ============================================================================
# Leave Management Endpoints (/api/v1/hr/leaves)
# ============================================================================


@leaves_router.post(
    "",
    response_model=LeaveResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit a new leave request",
    description="File a leave request. Employees may only submit for themselves.",
)
def create_leave(
    leave_in: LeaveCreate,
    db: DbSession,
    current_user: CurrentUser,
) -> LeaveResponse:
    """Submit a new employee leave request with self-service validation."""
    if (
        current_user.role == UserRole.EMPLOYEE.value
        and current_user.employee_id != leave_in.employee_id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Employees can only submit leave requests for their own account.",
        )
    return leave_service.create_leave_request(db, leave_in)


@leaves_router.get(
    "",
    response_model=list[LeaveResponse],
    status_code=status.HTTP_200_OK,
    summary="List leave requests with filtering",
    description="Query leave requests. Employees only see their own requests.",
)
def list_leaves(
    db: DbSession,
    current_user: CurrentUser,
    employee_id: Annotated[
        int | None, Query(description="Filter by employee ID")
    ] = None,
    department: Annotated[str | None, Query(description="Filter by department")] = None,
    status_filter: Annotated[
        str | None,
        Query(
            alias="status",
            description="Filter by status (PENDING, APPROVED, REJECTED)",
        ),
    ] = None,
    leave_type: Annotated[str | None, Query(description="Filter by leave type")] = None,
    start_date: Annotated[
        date | None, Query(description="Filter start date on or after")
    ] = None,
    end_date: Annotated[
        date | None, Query(description="Filter end date on or before")
    ] = None,
    skip: Annotated[int, Query(ge=0, description="Records to skip")] = 0,
    limit: Annotated[
        int, Query(ge=1, le=500, description="Max records to return")
    ] = 100,
) -> list[LeaveResponse]:
    """List leave requests with role-based filtering."""
    if current_user.role == UserRole.EMPLOYEE.value:
        if not current_user.employee_id:
            return []
        employee_id = current_user.employee_id
        department = None  # Enforce self-only

    return leave_service.list_leaves(
        db,
        employee_id=employee_id,
        department=department,
        status_filter=status_filter,
        leave_type=leave_type,
        start_date=start_date,
        end_date=end_date,
        skip=skip,
        limit=limit,
    )


@leaves_router.get(
    "/{leave_id}",
    response_model=LeaveResponse,
    status_code=status.HTTP_200_OK,
    summary="Get leave request details",
    description="Fetch a single leave request. Employees restricted to own requests.",
)
def get_leave(
    leave_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> LeaveResponse:
    """Retrieve single leave request by primary key."""
    leave = leave_service.get_by_id(db, leave_id)
    if not leave:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Leave request with ID {leave_id} not found.",
        )

    if (
        current_user.role == UserRole.EMPLOYEE.value
        and current_user.employee_id != leave.employee_id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden: You can only view your own leave requests.",
        )

    return leave


@leaves_router.patch(
    "/{leave_id}/status",
    response_model=LeaveResponse,
    status_code=status.HTTP_200_OK,
    summary="Approve or reject a leave request (Admin, HR, Manager only)",
    description="Transition a pending leave request to APPROVED or REJECTED.",
)
def update_leave_status(
    leave_id: int,
    status_in: LeaveStatusUpdate,
    db: DbSession,
    _: RequireStaffOrManager,
) -> LeaveResponse:
    """Update leave request review status."""
    leave = leave_service.get_by_id(db, leave_id)
    if not leave:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Leave request with ID {leave_id} not found.",
        )
    return leave_service.update_leave_status(db, leave, status_in)


# ============================================================================
# HR Reports Endpoints (/api/v1/hr/reports)
# ============================================================================


@reports_router.get(
    "/leaves",
    response_model=LeaveSummaryReport,
    status_code=status.HTTP_200_OK,
    summary="Get enterprise leave summary report (Admin, HR, Manager only)",
    description="Aggregate leave metrics across status, type, and department.",
)
def get_leaves_report(
    db: DbSession,
    _: RequireStaffOrManager,
) -> LeaveSummaryReport:
    """Compute enterprise leave summary report."""
    return leave_service.get_leave_summary(db)


# Mount sub-routers on main HR router
router.include_router(employees_router)
router.include_router(leaves_router)
router.include_router(reports_router)
