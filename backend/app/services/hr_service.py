"""Deterministic business service layer for HR and Employee management."""

import csv
from pathlib import Path
from typing import Any

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

    @staticmethod
    def import_employees_from_csv(
        db: Session,
        csv_path: Path,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        """Import employee records from CSV in an idempotent, non-destructive manner.

        Rules:
        - Validates CSV headers ('employee_id', 'full_name', 'department', 'role', 'is_active').
        - Splits 'full_name' into first_name and last_name.
        - Generates clean, deterministic non-deliverable placeholder email:
          f"{employee_id.lower()}@internal.invalid".
        - Leaves salary as None (does not fabricate fictional salary estimates).
        - Preserves existing records (matching on employee_id) without overwriting them.
        - Separates organizational job roles from application RBAC roles.
        - If dry_run is True, rolls back all changes without committing.
        """
        if not csv_path.is_file():
            raise FileNotFoundError(f"Employee CSV file not found at {csv_path}")

        with open(csv_path, mode="r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            fieldnames = [fn.strip() for fn in (reader.fieldnames or [])]
            required_fields = {
                "employee_id",
                "full_name",
                "department",
                "role",
                "is_active",
            }
            missing = required_fields - set(fieldnames)
            if missing:
                raise ValueError(f"CSV missing required columns: {sorted(missing)}")

            rows = list(reader)

        total_rows = len(rows)
        created_count = 0
        preserved_count = 0
        errors: list[str] = []

        # Cache existing employee IDs in database for fast lookup
        existing_emp_ids = set(db.scalars(select(Employee.employee_id)).all())

        for idx, row in enumerate(rows, start=2):
            emp_id = (row.get("employee_id") or "").strip()
            full_name = (row.get("full_name") or "").strip()
            department = (row.get("department") or "").strip()
            role = (row.get("role") or "").strip()
            is_active_raw = (row.get("is_active") or "").strip()

            if not emp_id or not full_name:
                errors.append(f"Row {idx}: Missing employee_id or full_name")
                continue

            if emp_id in existing_emp_ids:
                preserved_count += 1
                continue

            # Split full_name
            name_parts = full_name.split()
            first_name = name_parts[0] if name_parts else "Unknown"
            last_name = (
                " ".join(name_parts[1:]) if len(name_parts) > 1 else name_parts[0]
            )

            # Mark clearly with deterministic non-deliverable placeholder
            placeholder_email = f"{emp_id.lower()}@internal.invalid"
            is_active = is_active_raw not in ("0", "false", "False")

            new_emp = Employee(
                employee_id=emp_id,
                first_name=first_name,
                last_name=last_name,
                email=placeholder_email,
                department=department or "General",
                role=role or "Employee",
                salary=None,  # Nullable, no fabricated salary
                is_active=is_active,
            )
            db.add(new_emp)
            existing_emp_ids.add(emp_id)
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


# Singleton instance of the service for convenient imports
hr_service = HRService()
