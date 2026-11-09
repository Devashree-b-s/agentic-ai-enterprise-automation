"""Seed script to ensure all demo role accounts and testing accounts exist with verified credentials."""

import logging
import sys
from pathlib import Path

# Ensure backend root is on sys.path
backend_dir = Path(__file__).resolve().parent.parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_password, verify_password
from app.db.base import Base
from app.db.session import SessionLocal, engine
from app.models.employee import Employee
from app.models.user import User, UserRole

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

DEFAULT_DEMO_PASSWORD = "Admin@123"

DEMO_ACCOUNTS = [
    {
        "email": "admin@enterprise.com",
        "role": UserRole.ADMIN.value,
        "employee_code": "EMP-0001",
        "description": "System Administrator",
    },
    {
        "email": "manager@enterprise.com",
        "role": UserRole.MANAGER.value,
        "employee_code": "EMP-0004",
        "description": "Sales & Inventory Manager",
    },
    {
        "email": "hr@enterprise.com",
        "role": UserRole.HR.value,
        "employee_code": "EMP-0005",
        "description": "HR & Staffing Manager",
    },
    {
        "email": "employee@enterprise.com",
        "role": UserRole.EMPLOYEE.value,
        "employee_code": "EMP-0002",
        "description": "General Staff / Employee",
    },
    {
        "email": "freelancer2@test.com",
        "role": UserRole.EMPLOYEE.value,
        "employee_code": "EMP-0003",
        "description": "External Freelancer / Staff",
    },
    # Secondary .local aliases matching VIVA and demo documentation
    {
        "email": "admin@enterprise.local",
        "role": UserRole.ADMIN.value,
        "employee_code": "EMP-0006",
        "description": "Admin (.local domain alias)",
    },
    {
        "email": "manager@enterprise.local",
        "role": UserRole.MANAGER.value,
        "employee_code": "EMP-0007",
        "description": "Manager (.local domain alias)",
    },
    {
        "email": "hr@enterprise.local",
        "role": UserRole.HR.value,
        "employee_code": "EMP-0008",
        "description": "HR (.local domain alias)",
    },
    {
        "email": "employee@enterprise.local",
        "role": UserRole.EMPLOYEE.value,
        "employee_code": "EMP-0009",
        "description": "Employee (.local domain alias)",
    },
]


def seed_demo_users(db: Session, password: str = DEFAULT_DEMO_PASSWORD) -> dict[str, int]:
    """Ensure all required demo users exist and have valid credentials.

    Args:
        db: SQLAlchemy session.
        password: Plaintext password for seeded demo users (defaults to 'Admin@123').

    Returns:
        Dict summarizing created, updated, and total users.
    """
    created_count = 0
    updated_count = 0

    hashed_pw = hash_password(password)

    for item in DEMO_ACCOUNTS:
        email = item["email"]
        role = item["role"]
        emp_code = item["employee_code"]

        # Resolve employee database ID if code exists
        emp_id = None
        if emp_code:
            stmt_emp = select(Employee).where(Employee.employee_id == emp_code)
            emp = db.scalar(stmt_emp)
            if emp:
                emp_id = emp.id

        stmt = select(User).where(User.email == email)
        user = db.scalar(stmt)

        if not user:
            new_user = User(
                email=email,
                hashed_password=hashed_pw,
                role=role,
                is_active=True,
                employee_id=emp_id,
            )
            db.add(new_user)
            created_count += 1
            logger.info("Created demo user: %s (Role: %s)", email, role)
        else:
            changes = False
            if not user.is_active:
                user.is_active = True
                changes = True
            if user.role != role:
                user.role = role
                changes = True
            if not verify_password(password, user.hashed_password):
                user.hashed_password = hashed_pw
                changes = True
            if emp_id and user.employee_id != emp_id:
                # Check if another user already holds this employee_id
                conflict = db.scalar(
                    select(User).where(User.employee_id == emp_id, User.id != user.id)
                )
                if not conflict:
                    user.employee_id = emp_id
                    changes = True
            if changes:
                updated_count += 1
                logger.info("Updated demo user: %s (Role: %s)", email, role)

    db.commit()
    return {
        "created": created_count,
        "updated": updated_count,
        "total": len(DEMO_ACCOUNTS),
    }


def main() -> None:
    """CLI execution entrypoint."""
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        result = seed_demo_users(db)
        print("\n" + "=" * 50)
        print("          DEMO USERS SEED SUMMARY           ")
        print("=" * 50)
        print(f"  New Users Created:   {result['created']}")
        print(f"  Users Updated:       {result['updated']}")
        print(f"  Total Demo Accounts: {result['total']}")
        print(f"  Standard Password:   {DEFAULT_DEMO_PASSWORD}")
        print("=" * 50)
        for acc in DEMO_ACCOUNTS:
            print(f"  • {acc['label'] if 'label' in acc else acc['description']}: {acc['email']} [{acc['role']}]")
        print("=" * 50 + "\n")
    finally:
        db.close()


if __name__ == "__main__":
    main()

