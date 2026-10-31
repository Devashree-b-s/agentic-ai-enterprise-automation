"""Automated test suite for cross-department analytics, data integration, and reporting."""

from datetime import date
from decimal import Decimal
from pathlib import Path

from app.models.employee import Employee
from app.models.historical_sale import HistoricalSale
from app.models.inventory import Product
from app.models.leave import LeaveRequest
from app.models.user import User
from app.services.historical_sales_service import historical_sales_service
from app.services.hr_service import hr_service
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session


def test_analytics_overview_calculation(
    client: TestClient,
    db_session: Session,
    manager_headers: dict[str, str],
):
    """Test that /api/v1/analytics/overview synthesizes accurate cross-department metrics."""
    # Seed known records
    emp = Employee(
        employee_id="EMP-ANL-001",
        first_name="Analytics",
        last_name="User",
        email="analytics.user@enterprise.com",
        department="Operations",
        role="Manager",
        is_active=True,
    )
    db_session.add(emp)
    db_session.commit()

    # Add historical recognized sale
    sale = HistoricalSale(
        order_id="ORD-HIST-001",
        sku="SKU-TEST-101",
        order_date=date(2026, 6, 15),
        quantity=2,
        unit_price=Decimal("50.00"),
        subtotal=Decimal("100.00"),
        order_status="COMPLETED",
    )
    # Add historical cancelled sale (must be excluded from recognized revenue)
    cancelled_sale = HistoricalSale(
        order_id="ORD-HIST-002",
        sku="SKU-TEST-101",
        order_date=date(2026, 6, 16),
        quantity=1,
        unit_price=Decimal("50.00"),
        subtotal=Decimal("50.00"),
        order_status="CANCELLED",
    )
    db_session.add_all([sale, cancelled_sale])
    db_session.commit()

    response = client.get("/api/v1/analytics/overview", headers=manager_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["total_employees"] >= 1
    assert data["active_employees"] >= 1
    assert data["total_products"] >= 1
    assert Decimal(str(data["total_recognized_revenue"])) >= Decimal("100.00")


def test_sales_analytics_status_filtering_and_recognition(
    client: TestClient,
    db_session: Session,
    manager_headers: dict[str, str],
):
    """Test that sales analytics strictly counts COMPLETED and SHIPPED as recognized revenue,

    and accurately accounts for CANCELLED and RETURNED transactions without double counting.
    """
    s1 = HistoricalSale(
        order_id="ORD-REV-001",
        sku="SKU-TEST-101",
        order_date=date(2026, 5, 10),
        quantity=2,
        unit_price=Decimal("100.00"),
        subtotal=Decimal("200.00"),
        order_status="COMPLETED",
    )
    s2 = HistoricalSale(
        order_id="ORD-REV-002",
        sku="SKU-TEST-101",
        order_date=date(2026, 5, 11),
        quantity=1,
        unit_price=Decimal("150.00"),
        subtotal=Decimal("150.00"),
        order_status="SHIPPED",
    )
    s3 = HistoricalSale(
        order_id="ORD-REV-003",
        sku="SKU-TEST-101",
        order_date=date(2026, 5, 12),
        quantity=1,
        unit_price=Decimal("50.00"),
        subtotal=Decimal("50.00"),
        order_status="RETURNED",
    )
    s4 = HistoricalSale(
        order_id="ORD-REV-004",
        sku="SKU-TEST-101",
        order_date=date(2026, 5, 13),
        quantity=3,
        unit_price=Decimal("20.00"),
        subtotal=Decimal("60.00"),
        order_status="CANCELLED",
    )
    db_session.add_all([s1, s2, s3, s4])
    db_session.commit()

    response = client.get("/api/v1/analytics/sales", headers=manager_headers)
    assert response.status_code == 200
    data = response.json()

    # Recognized revenue must include s1 (200) + s2 (150) = 350, excluding s3 (50) and s4 (60)
    assert Decimal(str(data["total_recognized_revenue"])) >= Decimal("350.00")
    assert data["returned_orders_count"] >= 1
    assert Decimal(str(data["returned_revenue_lost"])) >= Decimal("50.00")
    assert data["cancelled_orders_count"] >= 1
    assert Decimal(str(data["cancelled_potential_revenue"])) >= Decimal("60.00")


def test_inventory_analytics_and_replenishment(
    client: TestClient,
    db_session: Session,
    manager_headers: dict[str, str],
):
    """Test inventory analytics and replenishment urgency ranking."""
    response = client.get("/api/v1/analytics/inventory", headers=manager_headers)
    assert response.status_code == 200
    inv_data = response.json()
    assert inv_data["total_stock_on_hand"] >= 0
    assert inv_data["monetary_valuation_available"] is False
    assert "unavailable" in inv_data["valuation_note"].lower()

    # Test replenishment recommendations
    rep_res = client.get("/api/v1/analytics/replenishment", headers=manager_headers)
    assert rep_res.status_code == 200
    items = rep_res.json()
    assert isinstance(items, list)
    for item in items:
        assert "urgency" in item
        assert item["urgency"] in ("CRITICAL", "WARNING", "NORMAL")
        assert "suggested_replenishment" in item


def test_department_performance_analytics(
    client: TestClient,
    db_session: Session,
    manager_headers: dict[str, str],
):
    """Test department performance correlating staffing and leave utilization."""
    emp = Employee(
        employee_id="EMP-DEPT-001",
        first_name="Dept",
        last_name="Worker",
        email="dept.worker@enterprise.com",
        department="Engineering",
        role="Engineer",
        is_active=True,
    )
    db_session.add(emp)
    db_session.commit()

    lv = LeaveRequest(
        leave_code="LV-DEPT-001",
        employee_id=emp.id,
        employee_code=emp.employee_id,
        leave_type="ANNUAL",
        start_date=date(2026, 7, 1),
        end_date=date(2026, 7, 5),
        days_count=5,
        status="APPROVED",
    )
    db_session.add(lv)
    db_session.commit()

    response = client.get(
        "/api/v1/analytics/department-performance", headers=manager_headers
    )
    assert response.status_code == 200
    depts = response.json()
    eng_dept = next((d for d in depts if d["department"] == "Engineering"), None)
    assert eng_dept is not None
    assert eng_dept["employee_count"] >= 1
    assert eng_dept["total_leave_days"] >= 5


def test_product_performance_analytics(
    client: TestClient,
    db_session: Session,
    manager_headers: dict[str, str],
):
    """Test product performance combining sales volume and stock status."""
    response = client.get(
        "/api/v1/analytics/product-performance", headers=manager_headers
    )
    assert response.status_code == 200
    products = response.json()
    assert isinstance(products, list)
    if products:
        p = products[0]
        assert "stock_status" in p
        assert p["stock_status"] in ("HEALTHY", "LOW_STOCK", "OUT_OF_STOCK")


def test_cross_department_executive_report(
    client: TestClient,
    manager_headers: dict[str, str],
):
    """Test unified cross-department executive report endpoint."""
    response = client.get("/api/v1/analytics/cross-department", headers=manager_headers)
    assert response.status_code == 200
    data = response.json()
    assert "overview" in data
    assert "top_critical_products" in data
    assert "department_headcounts" in data
    assert "department_leaves" in data


def test_analytics_rbac_permissions(
    client: TestClient,
    employee_user_with_headers: tuple[User, Employee, dict[str, str]],
    manager_headers: dict[str, str],
):
    """Test RBAC on analytics: Unauthenticated (401), Employee (403), Manager (200)."""
    _, _, emp_headers = employee_user_with_headers

    # 1. Unauthenticated requests are rejected (401)
    assert client.get("/api/v1/analytics/overview").status_code == 401
    assert client.get("/api/v1/analytics/sales").status_code == 401

    # 2. Regular employee cannot access executive analytics (403)
    assert (
        client.get("/api/v1/analytics/overview", headers=emp_headers).status_code == 403
    )
    assert client.get("/api/v1/analytics/sales", headers=emp_headers).status_code == 403
    assert (
        client.get("/api/v1/analytics/inventory", headers=emp_headers).status_code
        == 403
    )

    # 3. Manager can access (200)
    assert (
        client.get("/api/v1/analytics/overview", headers=manager_headers).status_code
        == 200
    )
    assert (
        client.get("/api/v1/analytics/sales", headers=manager_headers).status_code
        == 200
    )


def test_historical_sales_import_does_not_alter_inventory_stock(
    db_session: Session,
    tmp_path: Path,
):
    """Test that importing historical sales never decrements or alters operational inventory stock."""
    prod = Product(
        sku="SKU-ISOLATION-01",
        name="Isolation Product",
        quantity_on_hand=100,
        safety_stock=10,
        target_stock=150,
        is_active=True,
    )
    db_session.add(prod)
    db_session.commit()
    db_session.refresh(prod)

    initial_stock = prod.quantity_on_hand

    # Create historical sales CSV with 50 units sold
    sales_csv = tmp_path / "test_sales_iso.csv"
    sales_csv.write_text(
        "order_id,product_id,order_date,quantity,unit_price,order_status\n"
        "ORD-ISO-001,SKU-ISOLATION-01,2026-06-01,30,25.00,COMPLETED\n"
        "ORD-ISO-002,SKU-ISOLATION-01,2026-06-02,20,25.00,SHIPPED\n",
        encoding="utf-8",
    )

    summary = historical_sales_service.import_sales_from_csv(db_session, sales_csv)
    assert summary["created"] == 2

    # Verify inventory stock was NOT touched
    db_session.refresh(prod)
    assert prod.quantity_on_hand == initial_stock == 100


def test_employee_import_preserves_manually_created_employees(
    db_session: Session,
    tmp_path: Path,
):
    """Test that employee import preserves existing manual records like EMP-INIT-001."""
    manual_emp = Employee(
        employee_id="EMP-INIT-001",
        first_name="Manual",
        last_name="Admin",
        email="manual.admin@enterprise.com",
        department="HR",
        role="Admin",
        salary=99999.0,
        is_active=True,
    )
    db_session.add(manual_emp)
    db_session.commit()

    # CSV containing EMP-INIT-001 with different details
    csv_file = tmp_path / "test_employees_overlap.csv"
    csv_file.write_text(
        "employee_id,full_name,department,role,is_active\n"
        "EMP-INIT-001,Different Name,Different Dept,employee,1\n"
        "EMP-NEW-999,New Person,Sales,employee,1\n",
        encoding="utf-8",
    )

    summary = hr_service.import_employees_from_csv(db_session, csv_file)
    assert summary["created"] == 1
    assert summary["preserved"] == 1

    # Verify manual employee salary and email were preserved intact
    db_session.refresh(manual_emp)
    assert manual_emp.first_name == "Manual"
    assert manual_emp.salary == 99999.0
    assert manual_emp.email == "manual.admin@enterprise.com"


def test_employee_import_dry_run_and_placeholder_email(
    db_session: Session,
    tmp_path: Path,
):
    """Test that employee import dry-run does not write to DB, and emails are non-deliverable placeholders."""
    csv_file = tmp_path / "test_emp_dry.csv"
    csv_file.write_text(
        "employee_id,full_name,department,role,is_active\n"
        "EMP-DRY-001,Dry Run Person,Engineering,Developer,1\n"
        "EMP-DRY-002,Manager Person,Sales,Manager,1\n",
        encoding="utf-8",
    )

    # 1. Dry run
    dry_res = hr_service.import_employees_from_csv(db_session, csv_file, dry_run=True)
    assert dry_res["dry_run"] is True
    assert dry_res["created"] == 2
    assert (
        db_session.scalar(
            select(func.count(Employee.id)).where(
                Employee.employee_id.like("EMP-DRY-%")
            )
        )
        == 0
    )

    # 2. Actual import
    real_res = hr_service.import_employees_from_csv(db_session, csv_file, dry_run=False)
    assert real_res["created"] == 2

    emp1 = db_session.scalar(
        select(Employee).where(Employee.employee_id == "EMP-DRY-001")
    )
    assert emp1 is not None
    assert emp1.salary is None
    assert emp1.email == "emp-dry-001@internal.invalid"

    # Verify no User accounts were created (strict RBAC separation)
    users_count = db_session.scalar(
        select(func.count(User.id)).where(User.email.like("%@internal.invalid"))
    )
    assert users_count == 0


def test_historical_sales_import_dry_run_and_repeatable(
    db_session: Session,
    tmp_path: Path,
):
    """Test that historical sales import supports dry-run and repeatable idempotent execution."""
    sales_csv = tmp_path / "test_hist_sales_dry.csv"
    sales_csv.write_text(
        "order_id,product_id,order_date,quantity,unit_price,order_status\n"
        "ORD-DRY-001,SKU-DRY-1,2026-07-01,5,10.00,COMPLETED\n"
        "ORD-DRY-002,SKU-DRY-2,2026-07-02,3,15.00,COMPLETED\n",
        encoding="utf-8",
    )

    # 1. Dry run
    dry_res = historical_sales_service.import_sales_from_csv(
        db_session, sales_csv, dry_run=True
    )
    assert dry_res["dry_run"] is True
    assert dry_res["created"] == 2
    assert (
        db_session.scalar(
            select(func.count(HistoricalSale.id)).where(
                HistoricalSale.order_id.like("ORD-DRY-%")
            )
        )
        == 0
    )

    # 2. Actual run
    real_res = historical_sales_service.import_sales_from_csv(
        db_session, sales_csv, dry_run=False
    )
    assert real_res["created"] == 2
    assert (
        db_session.scalar(
            select(func.count(HistoricalSale.id)).where(
                HistoricalSale.order_id.like("ORD-DRY-%")
            )
        )
        == 2
    )

    # 3. Repeat run - idempotent duplicate prevention
    repeat_res = historical_sales_service.import_sales_from_csv(
        db_session, sales_csv, dry_run=False
    )
    assert repeat_res["created"] == 0
    assert repeat_res["preserved"] == 2
    assert (
        db_session.scalar(
            select(func.count(HistoricalSale.id)).where(
                HistoricalSale.order_id.like("ORD-DRY-%")
            )
        )
        == 2
    )


def test_analytics_leave_trends_endpoint(
    client: TestClient,
    db_session: Session,
    manager_headers: dict[str, str],
    hr_headers: dict[str, str],
    employee_user_with_headers: tuple[User, Employee, dict[str, str]],
):
    """Test /api/v1/analytics/leave-trends permissions and response structure."""
    _, _, emp_headers = employee_user_with_headers

    # HR role allowed
    res_hr = client.get("/api/v1/analytics/leave-trends", headers=hr_headers)
    assert res_hr.status_code == 200
    assert isinstance(res_hr.json(), list)

    # Manager role allowed
    res_mgr = client.get("/api/v1/analytics/leave-trends", headers=manager_headers)
    assert res_mgr.status_code == 200

    # Employee role forbidden
    res_emp = client.get("/api/v1/analytics/leave-trends", headers=emp_headers)
    assert res_emp.status_code == 403


def test_analytics_replenishment_endpoint(
    client: TestClient,
    db_session: Session,
    manager_headers: dict[str, str],
):
    """Test /api/v1/analytics/replenishment suggestions endpoint."""
    prod = Product(
        sku="SKU-REP-01",
        name="Replenishment Test Product",
        quantity_on_hand=5,
        quantity_on_order=0,
        safety_stock=10,
        target_stock=50,
        is_active=True,
    )
    db_session.add(prod)
    db_session.commit()

    response = client.get("/api/v1/analytics/replenishment", headers=manager_headers)
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    matching = [p for p in data if p["sku"] == "SKU-REP-01"]
    assert len(matching) == 1
    assert matching[0]["urgency"] == "CRITICAL"
    assert matching[0]["suggested_replenishment"] == 45  # 50 - 5
