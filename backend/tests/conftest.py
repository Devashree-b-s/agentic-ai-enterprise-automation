"""Pytest fixtures for test database sessions and configuration."""

import sys
from collections.abc import Generator
from pathlib import Path

# Ensure backend directory is in sys.path
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

import pytest
from app.core.security import create_access_token, hash_password
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.employee import Employee
from app.models.user import User, UserRole
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool


@pytest.fixture(scope="function")
def db_session() -> Generator[Session, None, None]:
    """Provides an isolated, in-memory SQLite database session for each test.

    Using StaticPool and sqlite:///:memory: ensures:
    - Tests run blazingly fast in memory.
    - Each test starts with a freshly created, clean database schema.
    - Tests are completely isolated from each other.
    - No mock data ever touches the development database file.
    """
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=engine,
    )

    # Create all database tables defined in Base.metadata
    Base.metadata.create_all(bind=engine)

    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(db_session: Session) -> Generator[TestClient, None, None]:
    """Provides a TestClient wired to the isolated in-memory test database session.

    Overrides the FastAPI `get_db` dependency so all API requests during testing
    operate against the in-memory SQLite database.
    """

    def _override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture(scope="function")
def admin_headers(db_session: Session) -> dict[str, str]:
    """Provides Authorization headers for an Admin user."""
    admin = User(
        email="admin.fixture@enterprise.com",
        hashed_password=hash_password("AdminSecure123!"),
        role=UserRole.ADMIN.value,
        is_active=True,
    )
    db_session.add(admin)
    db_session.commit()
    db_session.refresh(admin)

    token = create_access_token({"sub": str(admin.id), "role": admin.role})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="function")
def hr_headers(db_session: Session) -> dict[str, str]:
    """Provides Authorization headers for an HR user."""
    hr_user = User(
        email="hr.fixture@enterprise.com",
        hashed_password=hash_password("HRSecure123!"),
        role=UserRole.HR.value,
        is_active=True,
    )
    db_session.add(hr_user)
    db_session.commit()
    db_session.refresh(hr_user)

    token = create_access_token({"sub": str(hr_user.id), "role": hr_user.role})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="function")
def manager_headers(db_session: Session) -> dict[str, str]:
    """Provides Authorization headers for a Manager user."""
    manager = User(
        email="manager.fixture@enterprise.com",
        hashed_password=hash_password("ManagerSecure123!"),
        role=UserRole.MANAGER.value,
        is_active=True,
    )
    db_session.add(manager)
    db_session.commit()
    db_session.refresh(manager)

    token = create_access_token({"sub": str(manager.id), "role": manager.role})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="function")
def employee_user_with_headers(
    db_session: Session,
) -> tuple[User, Employee, dict[str, str]]:
    """Provides a linked Employee model, User model, and Authorization headers."""
    emp = Employee(
        employee_id="EMP-FIXTURE-001",
        first_name="Evan",
        last_name="Employee",
        email="evan.employee@enterprise.com",
        department="Sales",
        role="Sales Representative",
        salary=60000.0,
        is_active=True,
    )
    db_session.add(emp)
    db_session.commit()
    db_session.refresh(emp)

    emp_user = User(
        email="evan.employee@enterprise.com",
        hashed_password=hash_password("EmployeeSecure123!"),
        role=UserRole.EMPLOYEE.value,
        is_active=True,
        employee_id=emp.id,
    )
    db_session.add(emp_user)
    db_session.commit()
    db_session.refresh(emp_user)

    token = create_access_token(
        {
            "sub": str(emp_user.id),
            "role": emp_user.role,
            "employee_id": emp.id,
        }
    )
    headers = {"Authorization": f"Bearer {token}"}
    return emp_user, emp, headers
