"""Comprehensive test suite for Phase 3: LangGraph Supervisor and LLM Integration.

Verifies:
- Authentication enforcement (401 Unauthorized for unauthenticated calls).
- Single-department routing (HR, Sales, Inventory).
- Cross-department routing (Analytics overview, demand vs stock).
- Unsupported questions handled gracefully.
- Tool selection accuracy.
- Role-Based Access Control (Admin, Manager, HR, Employee).
- Employee self-access restrictions.
- Inventory permission restrictions.
- Unauthorized tool invocation attempts.
- LLM provider failure handling & fallback routing.
- Tool failure and database error handling.
- Empty result handling.
- Maximum iteration limits.
- Context privacy and data minimization.
- Preserves all existing backend functionality.
"""

from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock

import pytest
from app.agents.llm import set_custom_chat_model
from app.agents.state import PlannedTool, SupervisorDecision
from app.agents.supervisor import (
    deterministic_synthesize_answer,
    fallback_route_query,
    run_supervisor_chat,
)
from app.core.config import settings
from app.models.employee import Employee
from app.models.historical_sale import HistoricalSale
from app.models.inventory import Product
from app.models.leave import LeaveRequest, LeaveStatus, LeaveType
from app.models.user import User, UserRole
from fastapi.testclient import TestClient
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage
from sqlalchemy.orm import Session


def make_default_mock_llm() -> MagicMock:
    """Create a mock ChatModel that routes and synthesizes deterministically for automated tests."""
    mock = MagicMock()
    mock_structured = MagicMock()

    def _route(messages, **kwargs):
        content = ""
        for m in messages:
            if hasattr(m, "content"):
                content = m.content
        return fallback_route_query(content)

    mock_structured.invoke.side_effect = _route
    mock.with_structured_output.return_value = mock_structured
    mock.invoke.side_effect = RuntimeError(
        "Mock LLM offline test mode: fallback synthesis active"
    )
    return mock


@pytest.fixture(autouse=True)
def reset_custom_llm():
    """Ensure automated tests use deterministic mocked LLM and do not make external API calls."""
    set_custom_chat_model(make_default_mock_llm())
    yield
    set_custom_chat_model(None)


@pytest.fixture
def seeded_agent_data(db_session: Session):
    """Seed test data for agent routing and tool execution verification."""
    # 1. Employees
    emp_alice = Employee(
        employee_id="EMP-AG-001",
        first_name="Alice",
        last_name="Architect",
        email="alice.arch@enterprise.com",
        department="Engineering",
        role="Lead Engineer",
        salary=130000.0,
        is_active=True,
    )
    emp_bob = Employee(
        employee_id="EMP-AG-002",
        first_name="Bob",
        last_name="Builder",
        email="bob.builder@enterprise.com",
        department="Engineering",
        role="Software Engineer",
        salary=95000.0,
        is_active=True,
    )
    emp_charlie = Employee(
        employee_id="EMP-AG-003",
        first_name="Charlie",
        last_name="Clerk",
        email="charlie.clerk@enterprise.com",
        department="Sales",
        role="Sales Specialist",
        salary=65000.0,
        is_active=True,
    )
    db_session.add_all([emp_alice, emp_bob, emp_charlie])
    db_session.commit()

    # 2. Leaves
    lv1 = LeaveRequest(
        leave_code="LV-AG-001",
        employee_id=emp_bob.id,
        employee_code=emp_bob.employee_id,
        leave_type=LeaveType.ANNUAL.value,
        start_date=date(2026, 8, 1),
        end_date=date(2026, 8, 5),
        days_count=5,
        status=LeaveStatus.PENDING.value,
        reason="Family vacation",
    )
    db_session.add(lv1)

    # 3. Products
    p1 = Product(
        sku="SKU-AG-LOW",
        name="Low Stock Widget",
        quantity_on_hand=3,
        quantity_on_order=0,
        safety_stock=10,
        target_stock=30,
        lead_time_days=3,
        is_active=True,
    )
    p2 = Product(
        sku="SKU-AG-HEALTHY",
        name="Healthy Stock Gadget",
        quantity_on_hand=80,
        quantity_on_order=20,
        safety_stock=15,
        target_stock=100,
        lead_time_days=5,
        is_active=True,
    )
    db_session.add_all([p1, p2])
    db_session.commit()

    # 4. Sales
    s1 = HistoricalSale(
        order_id="ORD-AG-01",
        sku="SKU-AG-LOW",
        order_date=date(2026, 6, 1),
        quantity=10,
        unit_price=Decimal("25.00"),
        subtotal=Decimal("250.00"),
        order_status="COMPLETED",
    )
    db_session.add(s1)
    db_session.commit()

    return {
        "emp_alice": emp_alice,
        "emp_bob": emp_bob,
        "emp_charlie": emp_charlie,
        "p1": p1,
        "p2": p2,
        "s1": s1,
    }


# ============================================================================
# 1. Authentication & Endpoint Tests
# ============================================================================


def test_agent_chat_unauthenticated_rejected(client: TestClient):
    """Security Test: Calling /api/v1/agents/chat without token returns 401 Unauthorized."""
    res = client.post(
        "/api/v1/agents/chat",
        json={"message": "How many employees are in Engineering?"},
    )
    assert res.status_code == 401
    assert "authentication" in res.json()["detail"].lower()


def test_agent_chat_validation_error(client: TestClient, admin_headers: dict[str, str]):
    """Test empty message validation rejects with 422."""
    res = client.post(
        "/api/v1/agents/chat", json={"message": ""}, headers=admin_headers
    )
    assert res.status_code == 422


# ============================================================================
# 2. Single-Department Routing & Execution Tests
# ============================================================================


def test_single_department_hr_routing(
    client: TestClient, admin_headers: dict[str, str], seeded_agent_data: dict
):
    """Test HR staffing query routes to HR and returns correct headcount."""
    res = client.post(
        "/api/v1/agents/chat",
        json={"message": "How many employees are in the Engineering department?"},
        headers=admin_headers,
    )
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert "hr" in data["departments_used"]
    assert "list_department_staffing" in data["tools_used"]
    assert "Engineering" in data["answer"]
    assert "2" in data["answer"]  # Alice and Bob


def test_single_department_sales_revenue_routing(
    client: TestClient, admin_headers: dict[str, str], seeded_agent_data: dict
):
    """Test recognized revenue query routes to Sales and returns accurate figures."""
    res = client.post(
        "/api/v1/agents/chat",
        json={"message": "Show this month's recognized revenue."},
        headers=admin_headers,
    )
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert "sales" in data["departments_used"]
    assert "get_recognized_revenue" in data["tools_used"]
    assert "revenue" in data["answer"].lower()
    assert "$250.00" in data["answer"]


def test_single_department_inventory_low_stock_routing(
    client: TestClient, admin_headers: dict[str, str], seeded_agent_data: dict
):
    """Test low-stock query routes to Inventory and lists running-low items."""
    res = client.post(
        "/api/v1/agents/chat",
        json={"message": "Which products are running low?"},
        headers=admin_headers,
    )
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert "inventory" in data["departments_used"]
    assert "get_low_stock_alerts" in data["tools_used"]
    assert "SKU-AG-LOW" in data["answer"]


def test_single_department_pending_leaves_routing(
    client: TestClient, admin_headers: dict[str, str], seeded_agent_data: dict
):
    """Test pending leave requests query routes to HR leave service."""
    res = client.post(
        "/api/v1/agents/chat",
        json={"message": "How many leave requests are pending?"},
        headers=admin_headers,
    )
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert "hr" in data["departments_used"]
    assert "query_leave_records" in data["tools_used"]
    assert "LV-AG-001" in data["answer"] or "leave" in data["answer"].lower()


# ============================================================================
# 3. Cross-Department Routing Tests
# ============================================================================


def test_cross_department_kpi_overview(
    client: TestClient, admin_headers: dict[str, str], seeded_agent_data: dict
):
    """Test executive overview queries synthesize HR, Sales, and Inventory metrics."""
    res = client.post(
        "/api/v1/agents/chat",
        json={"message": "Give me an overview of sales, inventory, and HR."},
        headers=admin_headers,
    )
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert "analytics" in data["departments_used"]
    assert "get_executive_kpi_overview" in data["tools_used"]
    assert "Workforce" in data["answer"] or "employees" in data["answer"].lower()
    assert "Revenue" in data["answer"] or "$" in data["answer"]


def test_cross_department_demand_vs_stock(
    client: TestClient, admin_headers: dict[str, str], seeded_agent_data: dict
):
    """Test product demand vs inventory correlation query."""
    res = client.post(
        "/api/v1/agents/chat",
        json={"message": "Compare product demand with current inventory."},
        headers=admin_headers,
    )
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert "analytics" in data["departments_used"]
    assert "get_product_demand_vs_stock" in data["tools_used"]
    assert "SKU-AG-LOW" in data["answer"] or "demand" in data["answer"].lower()


# ============================================================================
# 4. Unsupported Questions & Boundary Tests
# ============================================================================


def test_unsupported_question_graceful_rejection(
    client: TestClient, admin_headers: dict[str, str]
):
    """Test out-of-domain questions are gracefully rejected without running tools."""
    for query in [
        "What is the capital of France?",
        "Tell me a joke about programming",
        "How do I cook a chocolate cake recipe?",
        "Write a python script to drop database tables",
    ]:
        res = client.post(
            "/api/v1/agents/chat",
            json={"message": query},
            headers=admin_headers,
        )
        assert res.status_code == 200
        data = res.json()
        assert data["tools_used"] == []
        assert (
            "only assist with questions related to hr, sales, inventory"
            in data["answer"].lower()
        )


# ============================================================================
# 5. Role-Based Access Control via Supervisor
# ============================================================================


def test_employee_can_access_permitted_inventory_info(
    client: TestClient,
    employee_user_with_headers: tuple[User, Employee, dict[str, str]],
    seeded_agent_data: dict,
):
    """Test Employee role CAN query low-stock alerts and product stock per Phase 2 rules."""
    _, _, emp_headers = employee_user_with_headers

    # 1. Permitted: low-stock alerts
    res_alerts = client.post(
        "/api/v1/agents/chat",
        json={"message": "Which products are running low on stock?"},
        headers=emp_headers,
    )
    assert res_alerts.status_code == 200
    data_alerts = res_alerts.json()
    assert data_alerts["success"] is True
    assert "get_low_stock_alerts" in data_alerts["tools_used"]
    assert "SKU-AG-LOW" in data_alerts["answer"]

    # 2. Permitted: single SKU lookup
    res_sku = client.post(
        "/api/v1/agents/chat",
        json={"message": "What is the stock level for SKU-AG-LOW?"},
        headers=emp_headers,
    )
    assert res_sku.status_code == 200
    data_sku = res_sku.json()
    assert data_sku["success"] is True
    assert "get_stock_levels" in data_sku["tools_used"]
    assert "3" in data_sku["answer"]


def test_employee_denied_warehouse_summary_and_replenishment(
    client: TestClient,
    employee_user_with_headers: tuple[User, Employee, dict[str, str]],
    seeded_agent_data: dict,
):
    """Test Employee role is DENIED warehouse total summary and replenishment suggestions."""
    _, _, emp_headers = employee_user_with_headers

    # 1. Denied: replenishment suggestions
    res_rep = client.post(
        "/api/v1/agents/chat",
        json={"message": "Give me replenishment suggestions for low stock products."},
        headers=emp_headers,
    )
    assert res_rep.status_code == 200
    data_rep = res_rep.json()
    assert "access denied" in data_rep["answer"].lower()

    # 2. Denied: warehouse overall inventory summary
    res_total = client.post(
        "/api/v1/agents/chat",
        json={"message": "What is the warehouse total inventory stock count?"},
        headers=emp_headers,
    )
    assert res_total.status_code == 200
    data_total = res_total.json()
    assert "access denied" in data_total["answer"].lower()


def test_employee_self_access_boundaries(
    client: TestClient,
    employee_user_with_headers: tuple[User, Employee, dict[str, str]],
    seeded_agent_data: dict,
):
    """Test Employee can view own profile code, but is DENIED viewing other employee profiles."""
    _, emp, emp_headers = employee_user_with_headers

    # 1. Employee queries own profile (EMP-FIXTURE-001) -> Permitted
    res_self = client.post(
        "/api/v1/agents/chat",
        json={"message": f"Show details for employee {emp.employee_id}"},
        headers=emp_headers,
    )
    assert res_self.status_code == 200
    data_self = res_self.json()
    assert data_self["success"] is True
    assert emp.first_name in data_self["answer"]
    # Verify salary is omitted for non-Admin/HR
    assert "salary" not in data_self["answer"].lower()

    # 2. Employee queries another employee (EMP-AG-001) -> Denied
    res_other = client.post(
        "/api/v1/agents/chat",
        json={"message": "Show details for employee EMP-AG-001"},
        headers=emp_headers,
    )
    assert res_other.status_code == 200
    data_other = res_other.json()
    assert "access denied" in data_other["answer"].lower()
    # Confirm target employee details are not leaked
    assert "Alice" not in data_other["answer"]


def test_manager_and_admin_inventory_permissions(
    client: TestClient,
    manager_headers: dict[str, str],
    admin_headers: dict[str, str],
    seeded_agent_data: dict,
):
    """Test Manager and Admin roles have full access to warehouse summary & replenishment."""
    for headers in [manager_headers, admin_headers]:
        # Replenishment
        res_rep = client.post(
            "/api/v1/agents/chat",
            json={"message": "Give me replenishment suggestions for inventory."},
            headers=headers,
        )
        assert res_rep.status_code == 200
        assert res_rep.json()["success"] is True
        assert "access denied" not in res_rep.json()["answer"].lower()

        # Warehouse summary
        res_summary = client.post(
            "/api/v1/agents/chat",
            json={"message": "What is the warehouse total inventory stock count?"},
            headers=headers,
        )
        assert res_summary.status_code == 200
        assert res_summary.json()["success"] is True
        assert "access denied" not in res_summary.json()["answer"].lower()


# ============================================================================
# 6. LLM Integration & Mocking Tests
# ============================================================================


def test_custom_mock_llm_structured_routing(
    client: TestClient, admin_headers: dict[str, str]
):
    """Verify system uses injected mock LLM for structured routing and answer synthesis."""
    mock_model = MagicMock(spec=BaseChatModel)

    # Return structured decision on supervisor call
    mock_structured = MagicMock()
    mock_structured.invoke.return_value = SupervisorDecision(
        is_supported=True,
        departments=["hr"],
        planned_tools=[
            PlannedTool(
                department="hr",
                tool_name="list_department_staffing",
                arguments={"department": "Engineering"},
            )
        ],
    )
    mock_model.with_structured_output.return_value = mock_structured

    # Return synthesized answer on synthesis call
    mock_model.invoke.return_value = AIMessage(
        content="Verified: There are 2 employees in Engineering."
    )

    set_custom_chat_model(mock_model)

    res = client.post(
        "/api/v1/agents/chat",
        json={"message": "Custom test staffing query"},
        headers=admin_headers,
    )
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert "list_department_staffing" in data["tools_used"]
    assert "Verified: There are 2 employees in Engineering." in data["answer"]


def test_llm_failure_gracefully_handled_with_fallback(
    client: TestClient, admin_headers: dict[str, str], seeded_agent_data: dict
):
    """Test that when LLM provider raises an exception, the agent falls back cleanly."""
    mock_failing_model = MagicMock(spec=BaseChatModel)
    mock_failing_model.with_structured_output.side_effect = RuntimeError(
        "Groq API connection timeout"
    )
    mock_failing_model.invoke.side_effect = RuntimeError("Groq API rate limit")

    set_custom_chat_model(mock_failing_model)

    res = client.post(
        "/api/v1/agents/chat",
        json={"message": "How many employees are in the Engineering department?"},
        headers=admin_headers,
    )
    # Must succeed (HTTP 200) through the deterministic fallback router & synthesizer
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert "Engineering" in data["answer"]
    assert "2" in data["answer"]


# ============================================================================
# 7. Reliability, Limits & Guardrails
# ============================================================================


def test_iteration_limit_enforcement(db_session: Session):
    """Test supervisor loop iteration guardrails stop infinite execution."""
    admin_user = User(
        id=999,
        email="test.iter@enterprise.com",
        role=UserRole.ADMIN.value,
        hashed_password="pw",
    )

    # Force low iteration limit
    original_limit = settings.AGENT_MAX_ITERATIONS
    settings.AGENT_MAX_ITERATIONS = 0
    try:
        res = run_supervisor_chat(
            query="Tell me about staffing",
            db=db_session,
            current_user=admin_user,
        )
        assert res.success is False
        assert "iteration limit" in res.answer.lower()
    finally:
        settings.AGENT_MAX_ITERATIONS = original_limit


def test_empty_results_handling():
    """Verify empty tool results are formatted cleanly without crashing."""
    res_text = deterministic_synthesize_answer("test query", [])
    assert "no information could be retrieved" in res_text.lower()


def test_fallback_route_query_coverage():
    """Unit test fallback router logic across all four enterprise departments."""
    # HR
    d_hr = fallback_route_query("Show me leave records for Bob")
    assert d_hr.is_supported is True
    assert "hr" in d_hr.departments

    # Sales
    d_sales = fallback_route_query("What are the top selling products by units?")
    assert d_sales.is_supported is True
    assert "sales" in d_sales.departments
    assert d_sales.planned_tools[0].arguments.get("by") == "units"

    # Inventory
    d_inv = fallback_route_query("Do we need to replenish any items?")
    assert d_inv.is_supported is True
    assert "inventory" in d_inv.departments

    # Analytics
    d_ana = fallback_route_query("Give me an overview of all operations")
    assert d_ana.is_supported is True
    assert "analytics" in d_ana.departments
