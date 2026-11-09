"""End-to-end integration tests verifying demo roles authentication, RBAC boundaries, and protected routes."""

from app.core.seed_demo_users import DEFAULT_DEMO_PASSWORD, seed_demo_users
from app.models.user import UserRole
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session


def setup_demo_db(db_session: Session):
    """Seed demo accounts into the test database."""
    seed_demo_users(db_session)


def test_demo_admin_login_and_rbac(client: TestClient, db_session: Session):
    """Test Admin demo login, JWT generation, /auth/me profile, and Admin-only RBAC access."""
    setup_demo_db(db_session)

    # 1. Authenticate with seeded Admin credentials
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@enterprise.com", "password": DEFAULT_DEMO_PASSWORD},
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["email"] == "admin@enterprise.com"
    assert data["user"]["role"] == UserRole.ADMIN.value
    token = data["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Access protected /auth/me endpoint
    me_res = client.get("/api/v1/auth/me", headers=headers)
    assert me_res.status_code == status.HTTP_200_OK
    assert me_res.json()["email"] == "admin@enterprise.com"
    assert me_res.json()["role"] == UserRole.ADMIN.value

    # 3. Admin has permission to provision users via admin-only endpoint
    create_res = client.post(
        "/api/v1/auth/users",
        json={
            "email": "test.provisioned@enterprise.com",
            "password": "SecurePassword123!",
            "role": "Manager",
        },
        headers=headers,
    )
    assert create_res.status_code == status.HTTP_201_CREATED
    assert create_res.json()["email"] == "test.provisioned@enterprise.com"


def test_demo_manager_login_and_rbac(client: TestClient, db_session: Session):
    """Test Manager demo login, access to management endpoints, and forbidden access to Admin-only routes."""
    setup_demo_db(db_session)

    # 1. Login as Manager
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "manager@enterprise.com", "password": DEFAULT_DEMO_PASSWORD},
    )
    assert response.status_code == status.HTTP_200_OK
    token = response.json()["access_token"]
    assert response.json()["user"]["role"] == UserRole.MANAGER.value
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Verify /auth/me
    me_res = client.get("/api/v1/auth/me", headers=headers)
    assert me_res.status_code == status.HTTP_200_OK
    assert me_res.json()["role"] == UserRole.MANAGER.value

    # 3. Manager is forbidden from Admin-only endpoints (e.g., provisioning privileged users)
    admin_only_res = client.post(
        "/api/v1/auth/users",
        json={
            "email": "illegal@enterprise.com",
            "password": "SecurePassword123!",
            "role": "Admin",
        },
        headers=headers,
    )
    assert admin_only_res.status_code == status.HTTP_403_FORBIDDEN


def test_demo_hr_login_and_rbac(client: TestClient, db_session: Session):
    """Test HR demo login, HR access, and forbidden access to Admin-only endpoints."""
    setup_demo_db(db_session)

    response = client.post(
        "/api/v1/auth/login",
        json={"email": "hr@enterprise.com", "password": DEFAULT_DEMO_PASSWORD},
    )
    assert response.status_code == status.HTTP_200_OK
    token = response.json()["access_token"]
    assert response.json()["user"]["role"] == UserRole.HR.value
    headers = {"Authorization": f"Bearer {token}"}

    # HR can access /api/v1/hr/employees
    hr_res = client.get("/api/v1/hr/employees", headers=headers)
    assert hr_res.status_code == status.HTTP_200_OK

    # HR cannot create users via /api/v1/auth/users
    admin_res = client.post(
        "/api/v1/auth/users",
        json={
            "email": "denied@enterprise.com",
            "password": "SecurePassword123!",
            "role": "HR",
        },
        headers=headers,
    )
    assert admin_res.status_code == status.HTTP_403_FORBIDDEN


def test_demo_employee_login(client: TestClient, db_session: Session):
    """Test Employee demo login and role verification."""
    setup_demo_db(db_session)

    response = client.post(
        "/api/v1/auth/login",
        json={"email": "employee@enterprise.com", "password": DEFAULT_DEMO_PASSWORD},
    )
    assert response.status_code == status.HTTP_200_OK
    token = response.json()["access_token"]
    assert response.json()["user"]["role"] == UserRole.EMPLOYEE.value
    headers = {"Authorization": f"Bearer {token}"}

    # Profile shows Employee role
    me_res = client.get("/api/v1/auth/me", headers=headers)
    assert me_res.status_code == status.HTTP_200_OK
    assert me_res.json()["role"] == UserRole.EMPLOYEE.value


def test_freelancer2_demo_login(client: TestClient, db_session: Session):
    """Test that freelancer2@test.com authenticates cleanly and case-insensitively."""
    setup_demo_db(db_session)

    # Standard lowercase login
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "freelancer2@test.com", "password": DEFAULT_DEMO_PASSWORD},
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["user"]["email"] == "freelancer2@test.com"
    assert response.json()["user"]["role"] == UserRole.EMPLOYEE.value

    # Mixed-case email login
    res_case = client.post(
        "/api/v1/auth/login",
        json={"email": "FreeLancer2@Test.com", "password": DEFAULT_DEMO_PASSWORD},
    )
    assert res_case.status_code == status.HTTP_200_OK
    assert res_case.json()["user"]["email"] == "freelancer2@test.com"


def test_login_invalid_password(client: TestClient, db_session: Session):
    """Verify that an incorrect password fails with 401 Unauthorized."""
    setup_demo_db(db_session)

    response = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@enterprise.com", "password": "WrongPassword123!"},
    )
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.json()["detail"] == "Invalid email or password."


def test_login_nonexistent_email(client: TestClient, db_session: Session):
    """Verify that a non-existent email fails with 401 Unauthorized."""
    setup_demo_db(db_session)

    response = client.post(
        "/api/v1/auth/login",
        json={"email": "nonexistent.user@enterprise.com", "password": DEFAULT_DEMO_PASSWORD},
    )
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.json()["detail"] == "Invalid email or password."


def test_login_invalid_email_format(client: TestClient, db_session: Session):
    """Verify that malformed email format triggers validation error (422)."""
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "not-an-email", "password": DEFAULT_DEMO_PASSWORD},
    )
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


def test_protected_routes_without_auth(client: TestClient):
    """Verify unauthenticated requests to protected endpoints return 401."""
    res_me = client.get("/api/v1/auth/me")
    assert res_me.status_code == status.HTTP_401_UNAUTHORIZED

    res_fake_token = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer not.a.valid.jwt.token"},
    )
    assert res_fake_token.status_code == status.HTTP_401_UNAUTHORIZED

