"""API router endpoints for HR and Employee management."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.employee import (
    EmployeeCreate,
    EmployeeResponse,
    EmployeeUpdate,
)
from app.services.hr_service import hr_service

router = APIRouter(prefix="/employees", tags=["HR - Employees"])

# Database session dependency type annotation
DbSession = Annotated[Session, Depends(get_db)]


@router.post(
    "/",
    response_model=EmployeeResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new employee",
    description="Register a new employee with unique business ID and email.",
)
def create_employee(
    employee_in: EmployeeCreate,
    db: DbSession,
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
    summary="List all employees",
    description="Retrieve a paginated list of employees with optional department filtering.",
)
def list_employees(
    db: DbSession,
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
    description="Retrieve a single employee by their database primary key ID.",
)
def get_employee(
    employee_id: int,
    db: DbSession,
) -> EmployeeResponse:
    """Fetch employee details by database ID or raise 404."""
    employee = hr_service.get_by_id(db, employee_id)
    if not employee:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Employee with ID {employee_id} not found.",
        )
    return employee


@router.put(
    "/{employee_id}",
    response_model=EmployeeResponse,
    status_code=status.HTTP_200_OK,
    summary="Update an employee",
    description="Update employee attributes such as role, salary, department, or active status.",
)
def update_employee(
    employee_id: int,
    employee_in: EmployeeUpdate,
    db: DbSession,
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
    summary="Delete an employee",
    description="Permanently delete an employee record from the database.",
)
def delete_employee(
    employee_id: int,
    db: DbSession,
) -> None:
    """Delete employee by database ID or raise 404."""
    employee = hr_service.get_by_id(db, employee_id)
    if not employee:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Employee with ID {employee_id} not found.",
        )
    hr_service.delete_employee(db, employee)
