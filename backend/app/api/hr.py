"""API router endpoints for HR and Employee management with RBAC protection."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.deps import CurrentUser, DbSession, require_roles
from app.models.user import User, UserRole
from app.schemas.employee import (
    EmployeeCreate,
    EmployeeResponse,
    EmployeeUpdate,
)
from app.services.hr_service import hr_service

router = APIRouter(prefix="/employees", tags=["HR - Employees"])

# Role requirement dependencies
RequireAdminOrHR = Annotated[User, Depends(require_roles(UserRole.ADMIN, UserRole.HR))]
RequireStaffOrManager = Annotated[
    User, Depends(require_roles(UserRole.ADMIN, UserRole.HR, UserRole.MANAGER))
]


@router.post(
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
    # Check duplicate business employee_id
    if hr_service.get_by_employee_code(db, employee_in.employee_id):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Employee with ID '{employee_in.employee_id}' already exists.",
        )

    # Check duplicate email
    if hr_service.get_by_email(db, employee_in.email):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Employee with email '{employee_in.email}' already exists.",
        )

    return hr_service.create_employee(db, employee_in)


@router.get(
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


@router.get(
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

    # If the user has an Employee role, restrict access to their own profile
    if (
        current_user.role == UserRole.EMPLOYEE.value
        and current_user.employee_id != employee.id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden: You can only view your own employee profile.",
        )

    return employee


@router.put(
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

    # If updating email, ensure no OTHER employee has this email
    if employee_in.email is not None and employee_in.email != employee.email:
        existing = hr_service.get_by_email(db, employee_in.email)
        if existing and existing.id != employee_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Employee with email '{employee_in.email}' already exists.",
            )

    return hr_service.update_employee(db, employee, employee_in)


@router.delete(
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
