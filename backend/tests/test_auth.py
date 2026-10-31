"""Comprehensive unit and integration tests for Authentication, RBAC, and Security."""

from datetime import timedelta

import pytest
from app.core.bootstrap import bootstrap_first_admin, build_parser
from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)
from app.models.employee import Employee
from app.models.user import User, UserRole
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

# ============================================================================
# Unit Tests: Password Hashing & Security Utilities
# ============================================================================


def test_password_hashing_and_verification():
    """Verify that Argon2id generates valid hashes and correctly matches plaintext."""
    raw_pass = "MySecretP@ssw0rd!"
    hashed = hash_password(raw_pass)

    assert hashed != raw_pass
    assert hashed.startswith("$argon2id$")

    assert verify_password(raw_pass, hashed) is True
    assert verify_password("WrongPassword!", hashed) is False
    assert verify_password("", hashed) is False


def test_jwt_token_creation_and_expiration():
    """Verify JWT token encoding, decoding, and expiration validation."""
    data = {"sub": "123", "role": "Admin"}

    # 1. Valid token
    valid_token = create_access_token(data, expires_delta=timedelta(minutes=5))
    payload = decode_access_token(valid_token)
    assert payload["sub"] == "123"
    assert payload["role"] == "Admin"

    # 2. Expired token (delta in the past)
    expired_token = create_access_token(data, expires_delta=timedelta(minutes=-10))
    with pytest.raises(Exception) as exc_info:
        decode_access_token(expired_token)
    assert "expired" in str(exc_info.value.detail).lower()


# ============================================================================
# Integration Tests: Auth Endpoints (/register, /login, /me)
# ============================================================================


def test_user_registration_success(client: TestClient):
    """Test registering a new user returns 201 and excludes password from response."""
    payload = {
        "email": "new.member@enterprise.com",
        "password": "SecurePassword123!",
    }
    response = client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["id"] is not None
    assert data["email"] == "new.member@enterprise.com"
    assert data["role"] == "Employee"
    assert data["is_active"] is True
    assert "password" not in data
    assert "hashed_password" not in data


def test_user_registration_duplicate_email(client: TestClient):
    """Test registering with an existing email returns 409 Conflict."""
    payload = {
        "email": "duplicate.user@enterprise.com",
        "password": "SecurePassword123!",
    }
    res1 = client.post("/api/v1/auth/register", json=payload)
    assert res1.status_code == 201

    res2 = client.post("/api/v1/auth/register", json=payload)
    assert res2.status_code == 409
    assert "already exists" in res2.json()["detail"]


def test_user_registration_linked_to_employee(
    client: TestClient, hr_headers: dict[str, str]
):
    """Test registering a user linked to an existing employee record."""
    emp_res = client.post(
        "/api/v1/hr/employees/",
        json={
            "employee_id": "EMP-LINK-01",
            "first_name": "Linda",
            "last_name": "Danvers",
            "email": "linda@enterprise.com",
            "department": "HR",
            "role": "Recruiter",
            "salary": 62000.0,
        },
        headers=hr_headers,
    )
    assert emp_res.status_code == 201
    emp_id = emp_res.json()["id"]

    reg_res = client.post(
        "/api/v1/auth/register",
        json={
            "email": "linda.user@enterprise.com",
            "password": "SecurePassword123!",
            "employee_code": "EMP-LINK-01",
        },
    )
    assert reg_res.status_code == 201
    assert reg_res.json()["employee_id"] == emp_id

    # Trying to link the same employee again returns 409
    dup_link = client.post(
        "/api/v1/auth/register",
        json={
            "email": "another@enterprise.com",
            "password": "SecurePassword123!",
            "employee_code": "EMP-LINK-01",
        },
    )
    assert dup_link.status_code == 409
    assert "already has a registered user account" in dup_link.json()["detail"]


def test_user_registration_invalid_employee_code(client: TestClient):
    """Test registering with non-existent employee_code returns 404."""
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": "ghost@enterprise.com",
            "password": "SecurePassword123!",
            "employee_code": "DOES-NOT-EXIST",
        },
    )
    assert response.status_code == 404
    assert "does not exist" in response.json()["detail"]


# ============================================================================
# Security Tests: Anti-Privilege Escalation on Public Registration
# ============================================================================


def test_public_registration_cannot_create_admin(client: TestClient):
    """Security Test: Attempting to register as Admin is ignored and forces Employee role."""
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": "hacker.admin@enterprise.com",
            "password": "ExploitPassword123!",
            "role": "Admin",  # Client attempts privilege escalation
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["role"] == "Employee"  # Strictly enforced as Employee
    assert data["role"] != "Admin"


def test_public_registration_cannot_create_hr(client: TestClient):
    """Security Test: Attempting to register as HR is ignored and forces Employee role."""
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": "fake.hr@enterprise.com",
            "password": "ExploitPassword123!",
            "role": "HR",
        },
    )
    assert response.status_code == 201
    assert response.json()["role"] == "Employee"


def test_public_registration_cannot_create_manager(client: TestClient):
    """Security Test: Attempting to register as Manager is ignored and forces Employee role."""
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": "fake.manager@enterprise.com",
            "password": "ExploitPassword123!",
            "role": "Manager",
        },
    )
    assert response.status_code == 201
    assert response.json()["role"] == "Employee"


# ============================================================================
# Security Tests: Admin Privileged User Creation (/users)
# ============================================================================


def test_admin_can_create_privileged_accounts(
    client: TestClient, admin_headers: dict[str, str]
):
    """Security Test: Only Admin can create accounts with Admin, HR, and Manager roles."""
    # 1. Admin creates an HR user
    res_hr = client.post(
        "/api/v1/auth/users",
        json={
            "email": "new.hr.staff@enterprise.com",
            "password": "OfficialPass123!",
            "role": "HR",
        },
        headers=admin_headers,
    )
    assert res_hr.status_code == 201
    assert res_hr.json()["role"] == "HR"

    # 2. Admin creates a Manager user
    res_mgr = client.post(
        "/api/v1/auth/users",
        json={
            "email": "new.sales.mgr@enterprise.com",
            "password": "OfficialPass123!",
            "role": "Manager",
        },
        headers=admin_headers,
    )
    assert res_mgr.status_code == 201
    assert res_mgr.json()["role"] == "Manager"

    # 3. Admin creates another Admin
    res_admin = client.post(
        "/api/v1/auth/users",
        json={
            "email": "secondary.admin@enterprise.com",
            "password": "OfficialPass123!",
            "role": "Admin",
        },
        headers=admin_headers,
    )
    assert res_admin.status_code == 201
    assert res_admin.json()["role"] == "Admin"


def test_employee_cannot_create_privileged_accounts(
    client: TestClient,
    employee_user_with_headers: tuple[User, Employee, dict[str, str]],
):
    """Security Test: Employee role is forbidden from accessing /users endpoint."""
    _, _, emp_headers = employee_user_with_headers
    response = client.post(
        "/api/v1/auth/users",
        json={
            "email": "illegal.account@enterprise.com",
            "password": "IllegalPass123!",
            "role": "Admin",
        },
        headers=emp_headers,
    )
    assert response.status_code == 403
    assert "Access forbidden" in response.json()["detail"]


def test_hr_user_cannot_create_privileged_accounts(
    client: TestClient, hr_headers: dict[str, str]
):
    """Security Test: HR role is forbidden from creating users on /users endpoint."""
    response = client.post(
        "/api/v1/auth/users",
        json={
            "email": "hr.attempt@enterprise.com",
            "password": "SomePassword123!",
            "role": "Manager",
        },
        headers=hr_headers,
    )
    assert response.status_code == 403
    assert "Access forbidden" in response.json()["detail"]


def test_unauthenticated_cannot_create_users(client: TestClient):
    """Security Test: Unauthenticated calls to /users return 401 Unauthorized."""
    response = client.post(
        "/api/v1/auth/users",
        json={
            "email": "anon@enterprise.com",
            "password": "SomePassword123!",
            "role": "HR",
        },
    )
    assert response.status_code == 401


# ============================================================================
# Security Tests: First Admin Bootstrap Mechanism
# ============================================================================


def test_bootstrap_first_admin_success(db_session: Session):
    """Test bootstrapping initial admin when no admin exists in the database."""
    # Ensure no admin exists
    existing = db_session.scalars(
        select(User).where(User.role == UserRole.ADMIN.value)
    ).all()
    for u in existing:
        db_session.delete(u)
    db_session.commit()

    admin = bootstrap_first_admin(
        db_session,
        email="initial.bootstrap@enterprise.com",
        password="BootstrapPassword123!",
    )
    assert admin.id is not None
    assert admin.email == "initial.bootstrap@enterprise.com"
    assert admin.role == "Admin"
    assert verify_password("BootstrapPassword123!", admin.hashed_password) is True


def test_bootstrap_first_admin_aborts_if_admin_already_exists(
    db_session: Session, admin_headers: dict[str, str]
):
    """Security Test: Bootstrap aborts if an Administrator already exists."""
    # admin_headers fixture already created an Admin in db_session
    with pytest.raises(RuntimeError) as exc_info:
        bootstrap_first_admin(
            db_session,
            email="second.admin@enterprise.com",
            password="SecondAdminPass123!",
        )
    assert "already exists" in str(exc_info.value).lower()


def test_bootstrap_cli_parser_omits_password_flag():
    """Security Test: CLI parser must never expose a --password flag to prevent shell history leak."""
    parser = build_parser()
    flag_options = [opt for action in parser._actions for opt in action.option_strings]
    assert "--password" not in flag_options
    assert "-p" not in flag_options
    assert "--email" in flag_options


def test_bootstrap_first_admin_short_password_rejected(db_session: Session):
    """Security Test: Passwords shorter than 8 characters must be rejected."""
    # Ensure no admin exists
    existing = db_session.scalars(
        select(User).where(User.role == UserRole.ADMIN.value)
    ).all()
    for u in existing:
        db_session.delete(u)
    db_session.commit()

    with pytest.raises(ValueError) as exc_info:
        bootstrap_first_admin(
            db_session,
            email="short.pass@enterprise.com",
            password="short",  # < 8 chars
        )
    assert "at least 8 characters" in str(exc_info.value)


# ============================================================================
# Authentication & Login Tests
# ============================================================================


def test_user_login_success(client: TestClient):
    """Test authenticating with valid credentials returns 200 and JWT access token."""
    client.post(
        "/api/v1/auth/register",
        json={
            "email": "login.test@enterprise.com",
            "password": "LoginPassword123!",
        },
    )

    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": "login.test@enterprise.com",
            "password": "LoginPassword123!",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["email"] == "login.test@enterprise.com"
    assert data["user"]["role"] == "Employee"


def test_user_login_invalid_password(client: TestClient):
    """Test authenticating with incorrect password returns 401 Unauthorized."""
    client.post(
        "/api/v1/auth/register",
        json={
            "email": "wrong.pass@enterprise.com",
            "password": "CorrectPassword123!",
        },
    )

    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": "wrong.pass@enterprise.com",
            "password": "BadPassword999!",
        },
    )
    assert response.status_code == 401
    assert "Invalid email or password" in response.json()["detail"]


def test_user_login_nonexistent_email(client: TestClient):
    """Test authenticating with un-registered email returns 401 Unauthorized."""
    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": "nobody@enterprise.com",
            "password": "AnyPassword123!",
        },
    )
    assert response.status_code == 401
    assert "Invalid email or password" in response.json()["detail"]


def test_user_login_deactivated_account(client: TestClient, db_session: Session):
    """Test authenticating with a deactivated account returns 403 Forbidden."""
    user = User(
        email="inactive@enterprise.com",
        hashed_password=hash_password("InactivePass123!"),
        role=UserRole.EMPLOYEE.value,
        is_active=False,
    )
    db_session.add(user)
    db_session.commit()

    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": "inactive@enterprise.com",
            "password": "InactivePass123!",
        },
    )
    assert response.status_code == 403
    assert "deactivated" in response.json()["detail"].lower()


def test_read_current_user_me(client: TestClient, hr_headers: dict[str, str]):
    """Test GET /api/v1/auth/me returns the profile of the current bearer token holder."""
    response = client.get("/api/v1/auth/me", headers=hr_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "hr.fixture@enterprise.com"
    assert data["role"] == "HR"


def test_read_current_user_without_token(client: TestClient):
    """Test GET /api/v1/auth/me without headers returns 401 Unauthorized."""
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 401
    assert "credentials were not provided" in response.json()["detail"].lower()


# ============================================================================
# RBAC Tests: Role Restrictions & Self-Access Only on HR API
# ============================================================================


def test_unauthenticated_access_to_hr_api_rejected(client: TestClient):
    """Test that accessing protected HR endpoints without token returns 401 Unauthorized."""
    res_list = client.get("/api/v1/hr/employees/")
    assert res_list.status_code == 401

    res_post = client.post("/api/v1/hr/employees/", json={})
    assert res_post.status_code == 401


def test_manager_cannot_create_or_delete_employee(
    client: TestClient,
    manager_headers: dict[str, str],
):
    """Test that Manager role cannot create or delete employees (403 Forbidden)."""
    create_res = client.post(
        "/api/v1/hr/employees/",
        json={
            "employee_id": "EMP-MGR-TRY",
            "first_name": "Test",
            "last_name": "User",
            "email": "test@enterprise.com",
            "department": "Sales",
            "role": "Sales",
            "salary": 50000.0,
        },
        headers=manager_headers,
    )
    assert create_res.status_code == 403
    assert "Access forbidden" in create_res.json()["detail"]

    delete_res = client.delete("/api/v1/hr/employees/1", headers=manager_headers)
    assert delete_res.status_code == 403
    assert "Access forbidden" in delete_res.json()["detail"]


def test_manager_can_view_employee_list(
    client: TestClient,
    manager_headers: dict[str, str],
    hr_headers: dict[str, str],
):
    """Test that Manager role is authorized to view the employee directory."""
    client.post(
        "/api/v1/hr/employees/",
        json={
            "employee_id": "EMP-MGR-VIEW",
            "first_name": "Peter",
            "last_name": "Parker",
            "email": "peter@enterprise.com",
            "department": "Engineering",
            "role": "Photographer",
            "salary": 45000.0,
        },
        headers=hr_headers,
    )

    list_res = client.get("/api/v1/hr/employees/", headers=manager_headers)
    assert list_res.status_code == 200
    assert len(list_res.json()) >= 1


def test_employee_cannot_view_employee_list(
    client: TestClient,
    employee_user_with_headers: tuple[User, Employee, dict[str, str]],
):
    """Test that Employee role is forbidden from viewing the full directory list."""
    _, _, emp_headers = employee_user_with_headers
    list_res = client.get("/api/v1/hr/employees/", headers=emp_headers)
    assert list_res.status_code == 403
    assert "Access forbidden" in list_res.json()["detail"]


def test_employee_can_view_own_profile_only(
    client: TestClient,
    employee_user_with_headers: tuple[User, Employee, dict[str, str]],
    hr_headers: dict[str, str],
):
    """Test that an Employee user can view their own profile, but is forbidden from viewing others."""
    _, emp_record, emp_headers = employee_user_with_headers

    own_res = client.get(f"/api/v1/hr/employees/{emp_record.id}", headers=emp_headers)
    assert own_res.status_code == 200
    assert own_res.json()["employee_id"] == emp_record.employee_id

    other_res = client.post(
        "/api/v1/hr/employees/",
        json={
            "employee_id": "EMP-OTHER-99",
            "first_name": "Bruce",
            "last_name": "Wayne",
            "email": "bruce@enterprise.com",
            "department": "Executive",
            "role": "CEO",
            "salary": 250000.0,
        },
        headers=hr_headers,
    )
    assert other_res.status_code == 201
    other_emp_id = other_res.json()["id"]

    other_access_res = client.get(
        f"/api/v1/hr/employees/{other_emp_id}",
        headers=emp_headers,
    )
    assert other_access_res.status_code == 403
    assert (
        "You can only view your own employee profile"
        in other_access_res.json()["detail"]
    )
