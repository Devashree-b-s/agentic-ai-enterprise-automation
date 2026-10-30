"""Deterministic business service layer for HR and Employee management."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.employee import Employee
from app.schemas.employee import EmployeeCreate, EmployeeUpdate


class HRService:
    """Service encapsulating all HR and Employee domain business logic."""

    @staticmethod
    def get_by_id(db: Session, employee_id: int) -> Employee | None:
        """Retrieve an employee by database primary key ID."""
        return db.get(Employee, employee_id)

    @staticmethod
    def get_by_employee_code(db: Session, employee_code: str) -> Employee | None:
        """Retrieve an employee by unique business code (e.g., 'EMP-001')."""
        stmt = select(Employee).where(Employee.employee_id == employee_code)
        return db.scalar(stmt)

    @staticmethod
    def get_by_email(db: Session, email: str) -> Employee | None:
        """Retrieve an employee by unique email address."""
        stmt = select(Employee).where(Employee.email == email)
        return db.scalar(stmt)

    @staticmethod
    def list_employees(
        db: Session,
        skip: int = 0,
        limit: int = 100,
        department: str | None = None,
        is_active: bool | None = None,
    ) -> list[Employee]:
        """List employees with optional filtering by department and status."""
        stmt = select(Employee)
        if department is not None:
            stmt = stmt.where(Employee.department == department)
        if is_active is not None:
            stmt = stmt.where(Employee.is_active == is_active)
        stmt = stmt.offset(skip).limit(limit).order_by(Employee.id.asc())
        return list(db.scalars(stmt).all())

    @staticmethod
    def create_employee(db: Session, employee_in: EmployeeCreate) -> Employee:
        """Create a new employee record after validating uniqueness constraints."""
        db_employee = Employee(
            employee_id=employee_in.employee_id,
            first_name=employee_in.first_name,
            last_name=employee_in.last_name,
            email=employee_in.email,
            department=employee_in.department,
            role=employee_in.role,
            salary=employee_in.salary,
            is_active=employee_in.is_active,
        )
        db.add(db_employee)
        db.commit()
        db.refresh(db_employee)
        return db_employee

    @staticmethod
    def update_employee(
        db: Session,
        db_employee: Employee,
        employee_in: EmployeeUpdate,
    ) -> Employee:
        """Update an existing employee record with non-null incoming fields."""
        update_data = employee_in.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_employee, field, value)

        db.commit()
        db.refresh(db_employee)
        return db_employee

    @staticmethod
    def delete_employee(db: Session, db_employee: Employee) -> None:
        """Delete an employee record from the database."""
        db.delete(db_employee)
        db.commit()


# Singleton instance of the service for convenient imports
hr_service = HRService()
