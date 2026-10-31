"""Automated test suite for employee leave management and reports."""

from datetime import date, timedelta
from pathlib import Path

from app.models.employee import Employee
from app.models.leave import LeaveRequest
from app.models.user import User
from app.services.leave_service import leave_service
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session


def test_create_leave_request_success(
    client: TestClient,
    employee_user_with_headers: tuple[User, Employee, dict[str, str]],
):
    """Test that an employee can file a valid leave request for themselves."""
    _, emp, headers = employee_user_with_headers

    today = date.today()
    payload = {
        "employee_id": emp.id,
        "leave_type": "ANNUAL",
        "start_date": str(today + timedelta(days=5)),
        "end_date": str(today + timedelta(days=9)),
        "reason": "Family vacation",
    }
    response = client.post("/api/v1/hr/leaves", json=payload, headers=headers)
    assert response.status_code == 201
    data = response.json()
    assert data["employee_id"] == emp.id
    assert data["employee_code"] == emp.employee_id
    assert data["leave_type"] == "ANNUAL"
    assert data["status"] == "PENDING"
    assert data["days_count"] == 5
    assert data["leave_code"].startswith("LV-")


def test_create_leave_request_date_validation(
    client: TestClient,
    employee_user_with_headers: tuple[User, Employee, dict[str, str]],
):
    """Test that end_date earlier than start_date is rejected with 422/400."""
    _, emp, headers = employee_user_with_headers

    today = date.today()
    payload = {
        "employee_id": emp.id,
        "leave_type": "SICK",
        "start_date": str(today + timedelta(days=10)),
        "end_date": str(today + timedelta(days=5)),
        "reason": "Invalid dates",
    }
    response = client.post("/api/v1/hr/leaves", json=payload, headers=headers)
    assert response.status_code in (400, 422)


def test_employee_cannot_create_leave_for_another_employee(
    client: TestClient,
    db_session: Session,
    employee_user_with_headers: tuple[User, Employee, dict[str, str]],
):
    """Test that regular employees cannot submit leave requests for someone else."""
    _, _, headers = employee_user_with_headers

    # Create another employee
    other_emp = Employee(
        employee_id="EMP-OTHER-001",
        first_name="Bob",
        last_name="Other",
        email="bob.other@enterprise.com",
        department="Engineering",
        role="Developer",
        is_active=True,
    )
    db_session.add(other_emp)
    db_session.commit()
    db_session.refresh(other_emp)

    today = date.today()
    payload = {
        "employee_id": other_emp.id,
        "leave_type": "ANNUAL",
        "start_date": str(today + timedelta(days=1)),
        "end_date": str(today + timedelta(days=3)),
    }
    response = client.post("/api/v1/hr/leaves", json=payload, headers=headers)
    assert response.status_code == 403


def test_list_and_filter_leaves_as_manager(
    client: TestClient,
    db_session: Session,
    manager_headers: dict[str, str],
):
    """Test that managers can list leave requests with department and status filters."""
    emp1 = Employee(
        employee_id="EMP-LV-001",
        first_name="Carol",
        last_name="Danvers",
        email="carol@enterprise.com",
        department="Operations",
        role="Operator",
        is_active=True,
    )
    emp2 = Employee(
        employee_id="EMP-LV-002",
        first_name="Diana",
        last_name="Prince",
        email="diana@enterprise.com",
        department="Finance",
        role="Accountant",
        is_active=True,
    )
    db_session.add_all([emp1, emp2])
    db_session.commit()

    today = date.today()
    lv1 = LeaveRequest(
        leave_code="LV-TEST-001",
        employee_id=emp1.id,
        employee_code=emp1.employee_id,
        leave_type="ANNUAL",
        start_date=today,
        end_date=today + timedelta(days=2),
        days_count=3,
        status="PENDING",
    )
    lv2 = LeaveRequest(
        leave_code="LV-TEST-002",
        employee_id=emp2.id,
        employee_code=emp2.employee_id,
        leave_type="SICK",
        start_date=today,
        end_date=today + timedelta(days=1),
        days_count=2,
        status="APPROVED",
    )
    db_session.add_all([lv1, lv2])
    db_session.commit()

    # Filter by department Operations
    res_dept = client.get(
        "/api/v1/hr/leaves",
        params={"department": "Operations"},
        headers=manager_headers,
    )
    assert res_dept.status_code == 200
    items = res_dept.json()
    assert len(items) == 1
    assert items[0]["leave_code"] == "LV-TEST-001"

    # Filter by status APPROVED
    res_status = client.get(
        "/api/v1/hr/leaves",
        params={"status": "APPROVED"},
        headers=manager_headers,
    )
    assert res_status.status_code == 200
    items_approved = res_status.json()
    assert any(item["leave_code"] == "LV-TEST-002" for item in items_approved)


def test_approve_and_reject_leave_request(
    client: TestClient,
    db_session: Session,
    manager_headers: dict[str, str],
    employee_user_with_headers: tuple[User, Employee, dict[str, str]],
):
    """Test approving a pending leave request, verifying terminal state protection."""
    _, emp, emp_headers = employee_user_with_headers

    today = date.today()
    leave = LeaveRequest(
        leave_code="LV-APPROVAL-001",
        employee_id=emp.id,
        employee_code=emp.employee_id,
        leave_type="ANNUAL",
        start_date=today,
        end_date=today + timedelta(days=2),
        days_count=3,
        status="PENDING",
    )
    db_session.add(leave)
    db_session.commit()
    db_session.refresh(leave)

    # 1. Employee cannot approve their own leave request
    res_emp = client.patch(
        f"/api/v1/hr/leaves/{leave.id}/status",
        json={"status": "APPROVED", "reason": "Self-approval attempt"},
        headers=emp_headers,
    )
    assert res_emp.status_code == 403

    # 2. Manager approves leave request
    res_mgr = client.patch(
        f"/api/v1/hr/leaves/{leave.id}/status",
        json={"status": "APPROVED", "reason": "Approved by manager"},
        headers=manager_headers,
    )
    assert res_mgr.status_code == 200
    assert res_mgr.json()["status"] == "APPROVED"

    # 3. Terminal state: cannot reject an already approved leave
    res_terminal = client.patch(
        f"/api/v1/hr/leaves/{leave.id}/status",
        json={"status": "REJECTED"},
        headers=manager_headers,
    )
    assert res_terminal.status_code == 400


def test_get_leaves_report(
    client: TestClient,
    db_session: Session,
    manager_headers: dict[str, str],
):
    """Test leave aggregate summary report."""
    emp = Employee(
        employee_id="EMP-RPT-001",
        first_name="Report",
        last_name="Test",
        email="report.test@enterprise.com",
        department="HR",
        role="Generalist",
        is_active=True,
    )
    db_session.add(emp)
    db_session.commit()

    today = date.today()
    lv1 = LeaveRequest(
        leave_code="LV-RPT-001",
        employee_id=emp.id,
        employee_code=emp.employee_id,
        leave_type="ANNUAL",
        start_date=today,
        end_date=today + timedelta(days=3),
        days_count=4,
        status="APPROVED",
    )
    lv2 = LeaveRequest(
        leave_code="LV-RPT-002",
        employee_id=emp.id,
        employee_code=emp.employee_id,
        leave_type="SICK",
        start_date=today + timedelta(days=10),
        end_date=today + timedelta(days=11),
        days_count=2,
        status="PENDING",
    )
    db_session.add_all([lv1, lv2])
    db_session.commit()

    response = client.get("/api/v1/hr/reports/leaves", headers=manager_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["total_requests"] >= 2
    assert data["by_status"]["APPROVED"] >= 1
    assert data["by_status"]["PENDING"] >= 1
    assert data["total_days_approved"] >= 4


def test_leave_import_idempotency_and_dry_run(db_session: Session, tmp_path: Path):
    """Test that leave CSV import is safe, idempotent, and supports dry-run."""
    emp = Employee(
        employee_id="EMP-CSV-001",
        first_name="Import",
        last_name="Test",
        email="import.test@enterprise.com",
        department="Sales",
        role="Rep",
        is_active=True,
    )
    db_session.add(emp)
    db_session.commit()

    # Create test CSV
    csv_file = tmp_path / "test_leaves.csv"
    csv_file.write_text(
        "leave_id,employee_id,leave_type,start_date,end_date,days_count,status\n"
        "LV-TEST-1001,EMP-CSV-001,ANNUAL,2026-06-01,2026-06-03,3,APPROVED\n"
        "LV-TEST-1002,EMP-CSV-001,SICK,2026-07-01,2026-07-02,2,PENDING\n",
        encoding="utf-8",
    )

    # 1. Dry run
    dry_res = leave_service.import_leaves_from_csv(db_session, csv_file, dry_run=True)
    assert dry_res["created"] == 2
    assert dry_res["dry_run"] is True
    # Confirm nothing was committed
    assert leave_service.get_by_code(db_session, "LV-TEST-1001") is None

    # 2. Actual import
    real_res = leave_service.import_leaves_from_csv(db_session, csv_file, dry_run=False)
    assert real_res["created"] == 2
    assert leave_service.get_by_code(db_session, "LV-TEST-1001") is not None

    # 3. Repeat import - must preserve and not duplicate
    repeat_res = leave_service.import_leaves_from_csv(
        db_session, csv_file, dry_run=False
    )
    assert repeat_res["created"] == 0
    assert repeat_res["preserved"] == 2
