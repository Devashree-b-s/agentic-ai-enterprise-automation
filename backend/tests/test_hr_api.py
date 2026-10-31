"""Integration tests for the Employee HR REST API endpoints with RBAC."""

from fastapi.testclient import TestClient


def test_create_employee_success(client: TestClient, hr_headers: dict[str, str]):
    """Test creating a new employee returns 201 and correctly serialized response."""
    payload = {
        "employee_id": "EMP-001",
        "first_name": "Alice",
        "last_name": "Johnson",
        "email": "alice.johnson@enterprise.com",
        "department": "HR",
        "role": "HR Manager",
        "salary": 75000.0,
        "is_active": True,
    }
    response = client.post("/api/v1/hr/employees/", json=payload, headers=hr_headers)
    assert response.status_code == 201
    data = response.json()
    assert data["id"] is not None
    assert data["employee_id"] == "EMP-001"
    assert data["first_name"] == "Alice"
    assert data["email"] == "alice.johnson@enterprise.com"
    assert data["salary"] == 75000.0
    assert "created_at" in data
    assert "updated_at" in data


def test_create_employee_duplicate_code(client: TestClient, hr_headers: dict[str, str]):
    """Test creating an employee with a duplicate employee_id returns 409 Conflict."""
    payload = {
        "employee_id": "EMP-002",
        "first_name": "Bob",
        "last_name": "Smith",
        "email": "bob.smith@enterprise.com",
        "department": "Sales",
        "role": "Sales Rep",
        "salary": 60000.0,
    }
    res1 = client.post("/api/v1/hr/employees/", json=payload, headers=hr_headers)
    assert res1.status_code == 201

    duplicate_payload = {
        "employee_id": "EMP-002",  # Duplicate code
        "first_name": "Bobby",
        "last_name": "Tables",
        "email": "bobby.tables@enterprise.com",
        "department": "IT",
        "role": "DBA",
        "salary": 70000.0,
    }
    res2 = client.post(
        "/api/v1/hr/employees/", json=duplicate_payload, headers=hr_headers
    )
    assert res2.status_code == 409
    assert "already exists" in res2.json()["detail"]


def test_create_employee_duplicate_email(
    client: TestClient, hr_headers: dict[str, str]
):
    """Test creating an employee with a duplicate email returns 409 Conflict."""
    payload1 = {
        "employee_id": "EMP-003",
        "first_name": "Charlie",
        "last_name": "Brown",
        "email": "shared.email@enterprise.com",
        "department": "Sales",
        "role": "Associate",
        "salary": 50000.0,
    }
    res1 = client.post("/api/v1/hr/employees/", json=payload1, headers=hr_headers)
    assert res1.status_code == 201

    payload2 = {
        "employee_id": "EMP-004",
        "first_name": "Charlotte",
        "last_name": "Green",
        "email": "shared.email@enterprise.com",  # Duplicate email
        "department": "Inventory",
        "role": "Clerk",
        "salary": 48000.0,
    }
    res2 = client.post("/api/v1/hr/employees/", json=payload2, headers=hr_headers)
    assert res2.status_code == 409
    assert "already exists" in res2.json()["detail"]


def test_create_employee_invalid_email(client: TestClient, hr_headers: dict[str, str]):
    """Test that submitting an invalid email address triggers Pydantic 422 error."""
    payload = {
        "employee_id": "EMP-005",
        "first_name": "David",
        "last_name": "Miller",
        "email": "invalid-email-address",
        "department": "Engineering",
        "role": "Developer",
        "salary": 80000.0,
    }
    response = client.post("/api/v1/hr/employees/", json=payload, headers=hr_headers)
    assert response.status_code == 422


def test_create_employee_negative_salary(
    client: TestClient, hr_headers: dict[str, str]
):
    """Test that submitting a negative salary triggers Pydantic 422 error."""
    payload = {
        "employee_id": "EMP-006",
        "first_name": "Eva",
        "last_name": "Green",
        "email": "eva@enterprise.com",
        "department": "Sales",
        "role": "Executive",
        "salary": -1000.0,
    }
    response = client.post("/api/v1/hr/employees/", json=payload, headers=hr_headers)
    assert response.status_code == 422


def test_list_employees_and_filtering(client: TestClient, hr_headers: dict[str, str]):
    """Test listing employees with department filtering and pagination."""
    employees = [
        {
            "employee_id": "EMP-101",
            "first_name": "Frank",
            "last_name": "Castle",
            "email": "frank@enterprise.com",
            "department": "HR",
            "role": "Recruiter",
            "salary": 55000.0,
        },
        {
            "employee_id": "EMP-102",
            "first_name": "Grace",
            "last_name": "Kelly",
            "email": "grace@enterprise.com",
            "department": "Sales",
            "role": "Lead",
            "salary": 72000.0,
        },
        {
            "employee_id": "EMP-103",
            "first_name": "Hank",
            "last_name": "Pym",
            "email": "hank@enterprise.com",
            "department": "Sales",
            "role": "Manager",
            "salary": 90000.0,
        },
    ]
    for emp in employees:
        client.post("/api/v1/hr/employees/", json=emp, headers=hr_headers)

    # List all
    res_all = client.get("/api/v1/hr/employees/", headers=hr_headers)
    assert res_all.status_code == 200
    assert len(res_all.json()) >= 3

    # Filter by department
    res_sales = client.get("/api/v1/hr/employees/?department=Sales", headers=hr_headers)
    assert res_sales.status_code == 200
    sales_data = res_sales.json()
    assert len(sales_data) == 2
    for emp in sales_data:
        assert emp["department"] == "Sales"

    # Pagination: limit 1
    res_paged = client.get("/api/v1/hr/employees/?limit=1", headers=hr_headers)
    assert res_paged.status_code == 200
    assert len(res_paged.json()) == 1


def test_get_employee_by_id(client: TestClient, hr_headers: dict[str, str]):
    """Test retrieving an employee by database primary key ID."""
    payload = {
        "employee_id": "EMP-201",
        "first_name": "Iris",
        "last_name": "West",
        "email": "iris@enterprise.com",
        "department": "Inventory",
        "role": "Lead",
        "salary": 65000.0,
    }
    create_res = client.post("/api/v1/hr/employees/", json=payload, headers=hr_headers)
    emp_id = create_res.json()["id"]

    # Success lookup
    get_res = client.get(f"/api/v1/hr/employees/{emp_id}", headers=hr_headers)
    assert get_res.status_code == 200
    assert get_res.json()["employee_id"] == "EMP-201"

    # 404 lookup
    not_found_res = client.get("/api/v1/hr/employees/999999", headers=hr_headers)
    assert not_found_res.status_code == 404
    assert "not found" in not_found_res.json()["detail"].lower()


def test_update_employee(client: TestClient, hr_headers: dict[str, str]):
    """Test updating employee attributes and handling duplicate email conflict."""
    emp1 = client.post(
        "/api/v1/hr/employees/",
        json={
            "employee_id": "EMP-301",
            "first_name": "Jack",
            "last_name": "Reacher",
            "email": "jack@enterprise.com",
            "department": "Security",
            "role": "Officer",
            "salary": 60000.0,
        },
        headers=hr_headers,
    ).json()

    res_emp2 = client.post(
        "/api/v1/hr/employees/",
        json={
            "employee_id": "EMP-302",
            "first_name": "John",
            "last_name": "Wick",
            "email": "john@enterprise.com",
            "department": "Security",
            "role": "Specialist",
            "salary": 80000.0,
        },
        headers=hr_headers,
    )
    assert res_emp2.status_code == 201

    # Update role and salary
    update_res = client.put(
        f"/api/v1/hr/employees/{emp1['id']}",
        json={
            "role": "Head of Security",
            "salary": 75000.0,
        },
        headers=hr_headers,
    )
    assert update_res.status_code == 200
    assert update_res.json()["role"] == "Head of Security"
    assert update_res.json()["salary"] == 75000.0

    # Attempt to update emp1's email to emp2's email -> 409 Conflict
    conflict_res = client.put(
        f"/api/v1/hr/employees/{emp1['id']}",
        json={
            "email": "john@enterprise.com",
        },
        headers=hr_headers,
    )
    assert conflict_res.status_code == 409
    assert "already exists" in conflict_res.json()["detail"]

    # 404 Update non-existent employee
    not_found_res = client.put(
        "/api/v1/hr/employees/999999",
        json={"role": "Manager"},
        headers=hr_headers,
    )
    assert not_found_res.status_code == 404


def test_delete_employee(client: TestClient, hr_headers: dict[str, str]):
    """Test deleting an employee returns 204 and subsequent queries return 404."""
    emp = client.post(
        "/api/v1/hr/employees/",
        json={
            "employee_id": "EMP-401",
            "first_name": "Karen",
            "last_name": "Page",
            "email": "karen@enterprise.com",
            "department": "Legal",
            "role": "Counsel",
            "salary": 95000.0,
        },
        headers=hr_headers,
    ).json()

    # Delete existing
    del_res = client.delete(f"/api/v1/hr/employees/{emp['id']}", headers=hr_headers)
    assert del_res.status_code == 204

    # Verify lookup returns 404
    get_res = client.get(f"/api/v1/hr/employees/{emp['id']}", headers=hr_headers)
    assert get_res.status_code == 404

    # Delete non-existent employee returns 404
    del_not_found = client.delete("/api/v1/hr/employees/999999", headers=hr_headers)
    assert del_not_found.status_code == 404
