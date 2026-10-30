"""Tests for database engine, session, and Employee model CRUD operations."""

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.employee import Employee


def test_insert_and_retrieve_employee(db_session: Session):
    """Test inserting a new employee record and retrieving it by primary key and employee_id."""
    emp = Employee(
        employee_id="EMP-001",
        first_name="Alice",
        last_name="Johnson",
        email="alice.johnson@enterprise.com",
        department="HR",
        role="HR Manager",
        salary=75000.0,
        is_active=True,
    )
    db_session.add(emp)
    db_session.commit()
    db_session.refresh(emp)

    # Verify primary key was generated
    assert emp.id is not None
    assert emp.id > 0
    assert emp.full_name == "Alice Johnson"
    assert emp.created_at is not None

    # Retrieve from database using select()
    stmt = select(Employee).where(Employee.employee_id == "EMP-001")
    retrieved = db_session.scalar(stmt)

    assert retrieved is not None
    assert retrieved.email == "alice.johnson@enterprise.com"
    assert retrieved.department == "HR"
    assert retrieved.salary == 75000.0


def test_unique_constraint_employee_id(db_session: Session):
    """Test that duplicate employee_id values violate unique constraint and raise IntegrityError."""
    emp1 = Employee(
        employee_id="EMP-DUPLICATE",
        first_name="Bob",
        last_name="Smith",
        email="bob@enterprise.com",
        department="Sales",
        role="Sales Executive",
        salary=60000.0,
    )
    db_session.add(emp1)
    db_session.commit()

    # Attempt to insert another employee with the exact same employee_id
    emp2 = Employee(
        employee_id="EMP-DUPLICATE",
        first_name="Charlie",
        last_name="Brown",
        email="charlie@enterprise.com",
        department="Inventory",
        role="Warehouse Specialist",
        salary=55000.0,
    )
    db_session.add(emp2)

    with pytest.raises(IntegrityError):
        db_session.commit()

    db_session.rollback()


def test_unique_constraint_email(db_session: Session):
    """Test that duplicate email addresses violate unique constraint and raise IntegrityError."""
    emp1 = Employee(
        employee_id="EMP-101",
        first_name="Dana",
        last_name="White",
        email="dana@enterprise.com",
        department="Sales",
        role="Sales Lead",
        salary=85000.0,
    )
    db_session.add(emp1)
    db_session.commit()

    # Attempt to insert another employee with the same email
    emp2 = Employee(
        employee_id="EMP-102",
        first_name="David",
        last_name="Williams",
        email="dana@enterprise.com",
        department="HR",
        role="Recruiter",
        salary=50000.0,
    )
    db_session.add(emp2)

    with pytest.raises(IntegrityError):
        db_session.commit()

    db_session.rollback()


def test_query_employees_by_department(db_session: Session):
    """Test querying and filtering employees by department."""
    employees = [
        Employee(
            employee_id="EMP-201",
            first_name="Elena",
            last_name="Rostova",
            email="elena@enterprise.com",
            department="Sales",
            role="Sales Rep",
            salary=58000.0,
        ),
        Employee(
            employee_id="EMP-202",
            first_name="Frank",
            last_name="Miller",
            email="frank@enterprise.com",
            department="Sales",
            role="Senior Sales Rep",
            salary=68000.0,
        ),
        Employee(
            employee_id="EMP-203",
            first_name="Grace",
            last_name="Hopper",
            email="grace@enterprise.com",
            department="Inventory",
            role="Inventory Manager",
            salary=82000.0,
        ),
    ]
    db_session.add_all(employees)
    db_session.commit()

    # Query all Sales employees
    stmt = select(Employee).where(Employee.department == "Sales")
    sales_team = list(db_session.scalars(stmt).all())

    assert len(sales_team) == 2
    assert {e.employee_id for e in sales_team} == {"EMP-201", "EMP-202"}


def test_update_employee_record(db_session: Session):
    """Test updating employee attributes such as salary and role."""
    emp = Employee(
        employee_id="EMP-301",
        first_name="Henry",
        last_name="Ford",
        email="henry@enterprise.com",
        department="Inventory",
        role="Junior Associate",
        salary=45000.0,
    )
    db_session.add(emp)
    db_session.commit()

    # Perform update
    emp.role = "Senior Associate"
    emp.salary = 55000.0
    db_session.commit()

    # Retrieve and verify updated values
    refreshed = db_session.scalar(select(Employee).where(Employee.employee_id == "EMP-301"))
    assert refreshed.role == "Senior Associate"
    assert refreshed.salary == 55000.0


def test_delete_employee_record(db_session: Session):
    """Test hard-deleting an employee record."""
    emp = Employee(
        employee_id="EMP-401",
        first_name="Iris",
        last_name="West",
        email="iris@enterprise.com",
        department="HR",
        role="HR Coordinator",
        salary=52000.0,
    )
    db_session.add(emp)
    db_session.commit()

    # Delete the record
    db_session.delete(emp)
    db_session.commit()

    # Verify record no longer exists
    deleted = db_session.scalar(select(Employee).where(Employee.employee_id == "EMP-401"))
    assert deleted is None
