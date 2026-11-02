"""Comprehensive test suite for Phase 2 Agent Tools.

Verifies:
- All 16 department and analytics tools.
- Valid and invalid inputs.
- Missing entities.
- Consistency with underlying service calculations.
- RBAC enforcement across Admin, Manager, HR, and Employee.
- Strict employee self-access boundaries.
- Attempted authorization bypasses.
- Read-only behavior.
- Database error containment and safe error messages.
"""

from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock

import pytest
from app.agents.tools import (
    check_product_availability,
    get_department_headcount_vs_leave_performance,
    get_department_leave_summaries,
    get_employee_by_code,
    get_executive_kpi_overview,
    get_low_stock_alerts,
    get_monthly_leave_trends,
    get_monthly_revenue_trends,
    get_product_demand_vs_stock,
    get_recognized_revenue,
    get_replenishment_suggestions,
    get_sales_status_breakdown,
    get_stock_levels,
    get_top_selling_products,
    list_department_staffing,
    query_leave_records,
)
from app.core.security import hash_password
from app.models.employee import Employee
from app.models.historical_sale import HistoricalSale
from app.models.inventory import Product, StockMovement
from app.models.leave import LeaveRequest, LeaveStatus, LeaveType
from app.models.user import User, UserRole
from sqlalchemy import func, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session


@pytest.fixture
def test_users(db_session: Session):
    """Fixture providing populated Admin, Manager, HR, and Employee User models."""
    # 1. Employees in DB
    emp1 = Employee(
        employee_id="EMP-T-001",
        first_name="Alice",
        last_name="Admin",
        email="alice.admin@enterprise.com",
        department="Executive",
        role="Administrator",
        salary=120000.0,
        is_active=True,
    )
    emp2 = Employee(
        employee_id="EMP-T-002",
        first_name="Bob",
        last_name="Worker",
        email="bob.worker@enterprise.com",
        department="Engineering",
        role="Developer",
        salary=85000.0,
        is_active=True,
    )
    emp3 = Employee(
        employee_id="EMP-T-003",
        first_name="Charlie",
        last_name="Staff",
        email="charlie.staff@enterprise.com",
        department="Engineering",
        role="Developer",
        salary=80000.0,
        is_active=True,
    )
    db_session.add_all([emp1, emp2, emp3])
    db_session.commit()

    # 2. Users
    admin = User(
        email="admin.tool@enterprise.com",
        hashed_password=hash_password("AdminPass123!"),
        role=UserRole.ADMIN.value,
        is_active=True,
        employee_id=emp1.id,
    )
    manager = User(
        email="manager.tool@enterprise.com",
        hashed_password=hash_password("ManagerPass123!"),
        role=UserRole.MANAGER.value,
        is_active=True,
    )
    hr = User(
        email="hr.tool@enterprise.com",
        hashed_password=hash_password("HRPass123!"),
        role=UserRole.HR.value,
        is_active=True,
    )
    employee_bob = User(
        email="bob.worker@enterprise.com",
        hashed_password=hash_password("BobPass123!"),
        role=UserRole.EMPLOYEE.value,
        is_active=True,
        employee_id=emp2.id,
    )
    db_session.add_all([admin, manager, hr, employee_bob])
    db_session.commit()

    return {
        "admin": admin,
        "manager": manager,
        "hr": hr,
        "employee_bob": employee_bob,
        "emp1": emp1,
        "emp2": emp2,
        "emp3": emp3,
    }


@pytest.fixture
def seeded_sales_and_inventory(db_session: Session):
    """Seed sample product inventory and historical sales."""
    p1 = Product(
        sku="SKU-TOOL-001",
        name="Tool Test Frame",
        quantity_on_hand=15,
        quantity_on_order=10,
        safety_stock=20,
        target_stock=60,
        lead_time_days=5,
        is_active=True,
    )
    p2 = Product(
        sku="SKU-TOOL-002",
        name="Tool Test Clock",
        quantity_on_hand=0,
        quantity_on_order=0,
        safety_stock=10,
        target_stock=40,
        lead_time_days=10,
        is_active=True,
    )
    p3 = Product(
        sku="SKU-TOOL-003",
        name="Tool Test Tin",
        quantity_on_hand=100,
        quantity_on_order=0,
        safety_stock=15,
        target_stock=120,
        lead_time_days=7,
        is_active=True,
    )
    db_session.add_all([p1, p2, p3])
    db_session.commit()

    # Sales
    s1 = HistoricalSale(
        order_id="ORD-T-01",
        sku="SKU-TOOL-001",
        order_date=date(2026, 6, 10),
        quantity=5,
        unit_price=Decimal("20.00"),
        subtotal=Decimal("100.00"),
        order_status="COMPLETED",
    )
    s2 = HistoricalSale(
        order_id="ORD-T-02",
        sku="SKU-TOOL-001",
        order_date=date(2026, 6, 12),
        quantity=2,
        unit_price=Decimal("20.00"),
        subtotal=Decimal("40.00"),
        order_status="SHIPPED",
    )
    s3 = HistoricalSale(
        order_id="ORD-T-03",
        sku="SKU-TOOL-002",
        order_date=date(2026, 6, 15),
        quantity=1,
        unit_price=Decimal("50.00"),
        subtotal=Decimal("50.00"),
        order_status="CANCELLED",
    )
    s4 = HistoricalSale(
        order_id="ORD-T-04",
        sku="SKU-TOOL-003",
        order_date=date(2026, 6, 18),
        quantity=2,
        unit_price=Decimal("15.00"),
        subtotal=Decimal("30.00"),
        order_status="RETURNED",
    )
    db_session.add_all([s1, s2, s3, s4])
    db_session.commit()

    return {"p1": p1, "p2": p2, "p3": p3}


# ============================================================================
# HR Tools Tests
# ============================================================================


def test_get_employee_by_code_rbac_and_self_access(
    db_session: Session, test_users: dict
):
    """Test get_employee_by_code respects roles and self-access restrictions."""
    admin = test_users["admin"]
    manager = test_users["manager"]
    employee_bob = test_users["employee_bob"]

    # 1. Admin can lookup any employee, salary is exposed
    res_admin = get_employee_by_code(db_session, admin, employee_code="EMP-T-002")
    assert res_admin.success is True
    assert res_admin.authorized is True
    assert res_admin.data["first_name"] == "Bob"
    assert res_admin.data["salary"] == 85000.0

    # 2. Manager can lookup employee, salary is omitted
    res_mgr = get_employee_by_code(db_session, manager, employee_code="EMP-T-002")
    assert res_mgr.success is True
    assert res_mgr.data["first_name"] == "Bob"
    assert "salary" not in res_mgr.data

    # 3. Employee Bob can lookup himself
    res_self = get_employee_by_code(db_session, employee_bob, employee_code="EMP-T-002")
    assert res_self.success is True
    assert res_self.authorized is True
    assert res_self.data["first_name"] == "Bob"

    # 4. Employee Bob cannot lookup another employee (Charlie)
    res_other = get_employee_by_code(
        db_session, employee_bob, employee_code="EMP-T-003"
    )
    assert res_other.success is False
    assert res_other.authorized is False
    assert "access denied" in res_other.error.lower()
    assert res_other.data is None
    # Ensure error does not reveal required internal roles or implementation details
    assert "admin" not in res_other.error.lower()
    assert "manager" not in res_other.error.lower()

    # 5. Missing employee
    res_missing = get_employee_by_code(db_session, admin, employee_code="EMP-NOT-EXIST")
    assert res_missing.success is True
    assert res_missing.data["found"] is False


def test_list_department_staffing_rbac(db_session: Session, test_users: dict):
    """Test list_department_staffing access control and filtering."""
    manager = test_users["manager"]
    employee_bob = test_users["employee_bob"]

    # Manager permitted
    res_all = list_department_staffing(db_session, manager)
    assert res_all.success is True
    assert res_all.authorized is True
    assert res_all.data["total_workforce"] >= 3

    # Department filter
    res_dept = list_department_staffing(db_session, manager, department="Engineering")
    assert res_dept.success is True
    assert res_dept.data["found"] is True
    assert res_dept.data["headcount"] >= 2

    # Employee forbidden
    res_emp = list_department_staffing(db_session, employee_bob)
    assert res_emp.success is False
    assert res_emp.authorized is False
    assert "access denied" in res_emp.error.lower()
    assert res_emp.data is None
    assert "admin" not in res_emp.error.lower()


def test_query_leave_records_and_employee_enforcement(
    db_session: Session, test_users: dict
):
    """Test query_leave_records enforces employee self-records."""
    manager = test_users["manager"]
    employee_bob = test_users["employee_bob"]
    emp2 = test_users["emp2"]
    emp3 = test_users["emp3"]

    # Seed leave records
    lv_bob = LeaveRequest(
        leave_code="LV-T-BOB-01",
        employee_id=emp2.id,
        employee_code=emp2.employee_id,
        leave_type=LeaveType.ANNUAL.value,
        start_date=date(2026, 7, 1),
        end_date=date(2026, 7, 3),
        days_count=3,
        status=LeaveStatus.APPROVED.value,
    )
    lv_charlie = LeaveRequest(
        leave_code="LV-T-CHARLIE-01",
        employee_id=emp3.id,
        employee_code=emp3.employee_id,
        leave_type=LeaveType.SICK.value,
        start_date=date(2026, 7, 5),
        end_date=date(2026, 7, 6),
        days_count=2,
        status=LeaveStatus.PENDING.value,
    )
    db_session.add_all([lv_bob, lv_charlie])
    db_session.commit()

    # Manager sees all
    res_mgr = query_leave_records(db_session, manager)
    assert res_mgr.success is True
    assert len(res_mgr.data) >= 2

    # Employee Bob query forces only Bob's leaves even if asking for Executive dept
    res_bob = query_leave_records(db_session, employee_bob, department="Executive")
    assert res_bob.success is True
    assert len(res_bob.data) == 1
    assert res_bob.data[0]["leave_code"] == "LV-T-BOB-01"


def test_monthly_leave_trends_and_summaries(db_session: Session, test_users: dict):
    """Test leave trends and department summaries."""
    hr = test_users["hr"]
    employee_bob = test_users["employee_bob"]

    res_trends = get_monthly_leave_trends(db_session, hr)
    assert res_trends.success is True
    assert isinstance(res_trends.data, list)

    res_summary = get_department_leave_summaries(db_session, hr)
    assert res_summary.success is True
    assert "by_status" in res_summary.data

    # Employee forbidden
    assert get_monthly_leave_trends(db_session, employee_bob).authorized is False
    assert get_department_leave_summaries(db_session, employee_bob).authorized is False


# ============================================================================
# Sales Tools Tests
# ============================================================================


def test_get_recognized_revenue_and_recognition_rules(
    db_session: Session, test_users: dict, seeded_sales_and_inventory: dict
):
    """Test get_recognized_revenue strictly recognizes COMPLETED and SHIPPED only."""
    manager = test_users["manager"]
    hr = test_users["hr"]

    # Manager access
    res = get_recognized_revenue(db_session, manager)
    assert res.success is True
    assert res.authorized is True
    # s1 (100) + s2 (40) = 140 recognized, s3 (cancelled) and s4 (returned) excluded
    assert res.data["total_recognized_revenue"] == 140.0
    assert res.data["total_units_sold"] == 7
    assert res.data["total_transactions"] == 2

    # Date filter validation
    res_filter = get_recognized_revenue(
        db_session, manager, start_date="2026-06-01", end_date="2026-06-11"
    )
    assert res_filter.success is True
    assert res_filter.data["total_recognized_revenue"] == 100.0  # s1 only

    # Bad date format handling
    res_bad = get_recognized_revenue(db_session, manager, start_date="invalid-date")
    assert res_bad.success is True
    assert "error" in res_bad.data

    # HR role forbidden
    res_hr = get_recognized_revenue(db_session, hr)
    assert res_hr.success is False
    assert res_hr.authorized is False


def test_sales_trends_and_status_breakdown(
    db_session: Session, test_users: dict, seeded_sales_and_inventory: dict
):
    """Test monthly trends, top selling products, and sales status breakdown."""
    manager = test_users["manager"]

    # Monthly trends
    res_trends = get_monthly_revenue_trends(db_session, manager)
    assert res_trends.success is True
    assert len(res_trends.data) >= 1

    # Top products by revenue
    res_top_rev = get_top_selling_products(db_session, manager, limit=5, by="revenue")
    assert res_top_rev.success is True
    assert res_top_rev.data[0]["sku"] == "SKU-TOOL-001"
    assert res_top_rev.data[0]["total_revenue"] == 140.0

    # Status breakdown (checks cancelled and returned tracking)
    res_breakdown = get_sales_status_breakdown(db_session, manager)
    assert res_breakdown.success is True
    assert res_breakdown.data["returned_revenue_lost"] == 30.0
    assert res_breakdown.data["cancelled_potential_revenue"] == 50.0


# ============================================================================
# Inventory Tools Tests
# ============================================================================


def test_get_stock_levels_and_non_monetary_valuation(
    db_session: Session, test_users: dict, seeded_sales_and_inventory: dict
):
    """Test stock level queries, RBAC matrix, and verify monetary valuation is unavailable."""
    admin = test_users["admin"]
    manager = test_users["manager"]
    hr = test_users["hr"]
    employee_bob = test_users["employee_bob"]

    # 1. Manager and Admin access
    res_sku = get_stock_levels(db_session, manager, sku="SKU-TOOL-001")
    assert res_sku.success is True
    assert res_sku.data["found"] is True
    assert res_sku.data["quantity_on_hand"] == 15
    assert res_sku.data["stock_status"] == "LOW_STOCK"  # 15 <= safety_stock (20)
    assert res_sku.data["monetary_valuation_available"] is False

    res_admin_all = get_stock_levels(db_session, admin)
    assert res_admin_all.success is True
    assert res_admin_all.data["total_stock_on_hand"] >= 115

    # Missing SKU
    res_missing = get_stock_levels(db_session, manager, sku="SKU-NOT-REAL")
    assert res_missing.success is True
    assert res_missing.data["found"] is False

    # Warehouse total
    res_all = get_stock_levels(db_session, manager)
    assert res_all.success is True
    assert res_all.data["total_stock_on_hand"] >= 115
    assert res_all.data["out_of_stock_count"] >= 1  # SKU-TOOL-002 has 0 stock
    assert res_all.data["monetary_valuation_available"] is False

    # 2. Employee permissions:
    # - Employee CAN query specific product SKU (matches GET /products/{id} RequireStaff)
    res_emp_sku = get_stock_levels(db_session, employee_bob, sku="SKU-TOOL-001")
    assert res_emp_sku.success is True
    assert res_emp_sku.authorized is True
    assert res_emp_sku.data["quantity_on_hand"] == 15

    # - Employee is DENIED warehouse summary (matches GET /reports/summary RequireAdminOrManager)
    res_emp_summary = get_stock_levels(db_session, employee_bob)
    assert res_emp_summary.success is False
    assert res_emp_summary.authorized is False
    assert "access denied" in res_emp_summary.error.lower()
    assert res_emp_summary.data is None
    assert "admin" not in res_emp_summary.error.lower()
    assert "manager" not in res_emp_summary.error.lower()

    # 3. HR permissions:
    # - HR CAN query specific product SKU
    res_hr_sku = get_stock_levels(db_session, hr, sku="SKU-TOOL-001")
    assert res_hr_sku.success is True
    assert res_hr_sku.authorized is True

    # - HR is DENIED warehouse summary
    res_hr_summary = get_stock_levels(db_session, hr)
    assert res_hr_summary.success is False
    assert res_hr_summary.authorized is False
    assert "access denied" in res_hr_summary.error.lower()
    assert res_hr_summary.data is None


def test_inventory_alerts_and_replenishment(
    db_session: Session, test_users: dict, seeded_sales_and_inventory: dict
):
    """Test low-stock alerts, replenishment calculations, availability checks, and RBAC."""
    admin = test_users["admin"]
    manager = test_users["manager"]
    hr = test_users["hr"]
    employee_bob = test_users["employee_bob"]

    # 1. Low stock alerts permitted for all staff (RequireStaff in API)
    # Manager
    res_alerts = get_low_stock_alerts(db_session, manager)
    assert res_alerts.success is True
    skus_in_alerts = [a["sku"] for a in res_alerts.data]
    assert "SKU-TOOL-001" in skus_in_alerts
    assert "SKU-TOOL-002" in skus_in_alerts

    # Employee CAN read low stock alerts
    res_alerts_emp = get_low_stock_alerts(db_session, employee_bob)
    assert res_alerts_emp.success is True
    assert res_alerts_emp.authorized is True
    assert len(res_alerts_emp.data) >= 1

    # HR CAN read low stock alerts
    res_alerts_hr = get_low_stock_alerts(db_session, hr)
    assert res_alerts_hr.success is True
    assert res_alerts_hr.authorized is True

    # 2. Check product availability permitted for all staff (RequireStaff in API)
    # Manager
    res_avail = check_product_availability(
        db_session, manager, sku="SKU-TOOL-001", required_quantity=10
    )
    assert res_avail.success is True
    assert res_avail.data["is_available"] is True
    assert res_avail.data["shortfall"] == 0

    # Employee CAN check availability
    res_avail_emp = check_product_availability(
        db_session, employee_bob, sku="SKU-TOOL-001", required_quantity=5
    )
    assert res_avail_emp.success is True
    assert res_avail_emp.authorized is True
    assert res_avail_emp.data["is_available"] is True

    # Shortfall check
    res_short = check_product_availability(
        db_session, manager, sku="SKU-TOOL-001", required_quantity=20
    )
    assert res_short.success is True
    assert res_short.data["is_available"] is False
    assert res_short.data["shortfall"] == 5

    # Invalid quantity (<= 0)
    res_invalid_qty = check_product_availability(
        db_session, manager, sku="SKU-TOOL-001", required_quantity=0
    )
    assert res_invalid_qty.success is True
    assert "error" in res_invalid_qty.data

    # 3. Replenishment suggestions restricted to Manager & Admin (RequireExecutive)
    # Admin and Manager permitted
    res_rep_admin = get_replenishment_suggestions(db_session, admin)
    assert res_rep_admin.success is True
    assert res_rep_admin.authorized is True

    res_rep = get_replenishment_suggestions(db_session, manager)
    assert res_rep.success is True
    assert res_rep.authorized is True
    # SKU-TOOL-001: target=60, on_hand=15, on_order=10 => suggested = 60 - 25 = 35
    sku1_rep = next(r for r in res_rep.data if r["sku"] == "SKU-TOOL-001")
    assert sku1_rep["suggested_replenishment"] == 35

    # Employee is DENIED replenishment suggestions
    res_rep_emp = get_replenishment_suggestions(db_session, employee_bob)
    assert res_rep_emp.success is False
    assert res_rep_emp.authorized is False
    assert "access denied" in res_rep_emp.error.lower()
    assert res_rep_emp.data is None
    assert "admin" not in res_rep_emp.error.lower()
    assert "manager" not in res_rep_emp.error.lower()

    # HR is DENIED replenishment suggestions
    res_rep_hr = get_replenishment_suggestions(db_session, hr)
    assert res_rep_hr.success is False
    assert res_rep_hr.authorized is False
    assert "access denied" in res_rep_hr.error.lower()
    assert res_rep_hr.data is None


# ============================================================================
# Cross-Department Analytics Tools Tests
# ============================================================================


def test_analytics_tools_rbac_and_correlations(
    db_session: Session, test_users: dict, seeded_sales_and_inventory: dict
):
    """Test cross-department analytics tools and authorization."""
    manager = test_users["manager"]
    hr = test_users["hr"]
    employee_bob = test_users["employee_bob"]

    # 1. Executive KPI overview
    res_overview = get_executive_kpi_overview(db_session, manager)
    assert res_overview.success is True
    assert res_overview.data["total_recognized_revenue"] == 140.0
    assert res_overview.data["total_products"] >= 3

    # 2. Product demand vs stock
    res_demand = get_product_demand_vs_stock(db_session, manager, limit=10)
    assert res_demand.success is True
    assert len(res_demand.data) >= 1
    assert "days_of_supply_estimate" in res_demand.data[0]

    # 3. Department headcount vs leave performance
    res_dept = get_department_headcount_vs_leave_performance(db_session, manager)
    assert res_dept.success is True
    assert len(res_dept.data) >= 1

    # RBAC: HR and Employee are blocked
    assert get_executive_kpi_overview(db_session, hr).authorized is False
    assert get_executive_kpi_overview(db_session, employee_bob).authorized is False
    assert get_product_demand_vs_stock(db_session, employee_bob).authorized is False
    assert (
        get_department_headcount_vs_leave_performance(
            db_session, employee_bob
        ).authorized
        is False
    )


# ============================================================================
# Tool Safety & Error Handling Tests
# ============================================================================


def test_tool_database_failure_handling(test_users: dict):
    """Test tool intercepts database exceptions without crashing or leaking raw traces."""
    manager = test_users["manager"]

    # Create a mock session that raises SQLAlchemy OperationalError on execute
    mock_db = MagicMock(spec=Session)
    mock_db.execute.side_effect = OperationalError(
        "connection refused", {}, Exception()
    )
    mock_db.scalar.side_effect = OperationalError("connection refused", {}, Exception())

    res = get_stock_levels(mock_db, manager, sku="SKU-TOOL-001")
    assert res.success is False
    assert res.authorized is True
    assert "database query encountered an error" in res.error.lower()
    assert res.execution_time_ms >= 0.0


def test_tools_are_strictly_read_only(
    db_session: Session, test_users: dict, seeded_sales_and_inventory: dict
):
    """Verify that calling tools never mutates products, stock movements, leaves, sales, or employee records."""
    manager = test_users["manager"]
    employee_bob = test_users["employee_bob"]
    prod = seeded_sales_and_inventory["p1"]
    initial_stock = prod.quantity_on_hand

    # Baseline counts
    baseline_prod_count = db_session.scalar(select(func.count(Product.id)))
    baseline_movement_count = db_session.scalar(select(func.count(StockMovement.id)))
    baseline_leave_count = db_session.scalar(select(func.count(LeaveRequest.id)))
    baseline_sales_count = db_session.scalar(select(func.count(HistoricalSale.id)))
    baseline_employee_count = db_session.scalar(select(func.count(Employee.id)))

    # Invoke multiple tools across all four departments
    get_stock_levels(db_session, manager, sku=prod.sku)
    get_stock_levels(db_session, employee_bob, sku=prod.sku)
    get_stock_levels(db_session, manager)
    check_product_availability(db_session, manager, sku=prod.sku, required_quantity=100)
    check_product_availability(
        db_session, employee_bob, sku=prod.sku, required_quantity=5
    )
    get_replenishment_suggestions(db_session, manager)
    get_low_stock_alerts(db_session, manager)
    get_low_stock_alerts(db_session, employee_bob)
    get_recognized_revenue(db_session, manager)
    get_monthly_revenue_trends(db_session, manager)
    get_top_selling_products(db_session, manager)
    get_sales_status_breakdown(db_session, manager)
    get_employee_by_code(db_session, manager, employee_code="EMP-T-002")
    get_employee_by_code(db_session, employee_bob, employee_code="EMP-T-002")
    list_department_staffing(db_session, manager)
    query_leave_records(db_session, manager)
    query_leave_records(db_session, employee_bob)
    get_monthly_leave_trends(db_session, manager)
    get_department_leave_summaries(db_session, manager)
    get_executive_kpi_overview(db_session, manager)
    get_product_demand_vs_stock(db_session, manager)
    get_department_headcount_vs_leave_performance(db_session, manager)

    db_session.refresh(prod)
    assert prod.quantity_on_hand == initial_stock

    # Zero mutation assertion
    assert db_session.scalar(select(func.count(Product.id))) == baseline_prod_count
    assert (
        db_session.scalar(select(func.count(StockMovement.id)))
        == baseline_movement_count
    )
    assert (
        db_session.scalar(select(func.count(LeaveRequest.id))) == baseline_leave_count
    )
    assert (
        db_session.scalar(select(func.count(HistoricalSale.id))) == baseline_sales_count
    )
    assert db_session.scalar(select(func.count(Employee.id))) == baseline_employee_count
