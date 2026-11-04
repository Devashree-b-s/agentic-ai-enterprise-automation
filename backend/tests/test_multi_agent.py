"""Tests for Phase 4: Advanced Multi-Agent Coordination and Domain Specialization."""

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.agents.coordinator import multi_agent_coordinator
from app.agents.llm import set_custom_chat_model
from app.agents.specialized import SPECIALIZED_AGENTS
from app.agents.supervisor import fallback_route_query
from app.core.security import hash_password
from app.models.user import User, UserRole


@pytest.fixture
def deterministic_supervisor_llm():
    """Inject deterministic routing and force the deterministic answer synthesizer."""
    model = MagicMock()
    structured_model = MagicMock()

    def route(messages, **kwargs):
        query = messages[-1].content
        prefix = "[Current User Question]: "
        query = query.removeprefix(prefix)
        return fallback_route_query(query)

    structured_model.invoke.side_effect = route
    model.with_structured_output.return_value = structured_model
    model.invoke.side_effect = RuntimeError("Deterministic test synthesis")
    set_custom_chat_model(model)
    try:
        yield
    finally:
        set_custom_chat_model(None)


def test_specialized_agents_registry():
    """Verify that all 5 specialized enterprise agents are registered with scoped tools."""
    expected_agents = {"hr", "sales", "inventory", "documents", "analytics"}
    assert set(SPECIALIZED_AGENTS.keys()) == expected_agents

    hr = SPECIALIZED_AGENTS["hr"]
    assert hr.name == "hr"
    assert "list_department_staffing" in hr.allowed_tools
    assert "get_employee_by_code" in hr.allowed_tools

    sales = SPECIALIZED_AGENTS["sales"]
    assert sales.name == "sales"
    assert "get_recognized_revenue" in sales.allowed_tools

    inv = SPECIALIZED_AGENTS["inventory"]
    assert inv.name == "inventory"
    assert "get_low_stock_alerts" in inv.allowed_tools

    doc = SPECIALIZED_AGENTS["documents"]
    assert doc.name == "documents"
    assert "search_enterprise_documents" in doc.allowed_tools

    analytics = SPECIALIZED_AGENTS["analytics"]
    assert analytics.name == "analytics"
    assert "get_executive_kpi_overview" in analytics.allowed_tools


def test_single_specialized_agent_delegation(client: TestClient, admin_headers: dict[str, str]):
    """Test queries targeting a single specialized agent."""
    # 1. HR Agent query
    res_hr = client.post(
        "/api/v1/agents/chat",
        json={"message": "How many active employees are there?"},
        headers=admin_headers,
    )
    assert res_hr.status_code == 200
    data_hr = res_hr.json()
    assert "hr" in data_hr["departments_used"] or "hr" in data_hr.get("agents_involved", [])
    assert "list_department_staffing" in data_hr["tools_used"]

    # 2. Sales Agent query
    res_sales = client.post(
        "/api/v1/agents/chat",
        json={"message": "What is our total recognized revenue?"},
        headers=admin_headers,
    )
    assert res_sales.status_code == 200
    data_sales = res_sales.json()
    assert "sales" in data_sales["departments_used"] or "sales" in data_sales.get("agents_involved", [])
    assert "get_recognized_revenue" in data_sales["tools_used"]

    # 3. Inventory Agent query
    res_inv = client.post(
        "/api/v1/agents/chat",
        json={"message": "Which products are currently low in stock?"},
        headers=admin_headers,
    )
    assert res_inv.status_code == 200
    data_inv = res_inv.json()
    assert "inventory" in data_inv["departments_used"] or "inventory" in data_inv.get("agents_involved", [])
    assert "get_low_stock_alerts" in data_inv["tools_used"]


def test_multi_agent_coordination_and_decomposition(
    client: TestClient,
    admin_headers: dict[str, str],
    deterministic_supervisor_llm,
):
    """Test cross-department compound query coordinating Inventory, Sales, and HR agents."""
    query = "Which products are running low, what is our monthly revenue, and how many employees are on leave?"
    res = client.post(
        "/api/v1/agents/chat",
        json={"message": query},
        headers=admin_headers,
    )
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True

    # Verify multiple agents were coordinated
    agents_involved = data.get("agents_involved", [])
    depts_used = data.get("departments_used", [])
    combined = set(agents_involved) | set(depts_used)

    assert "inventory" in combined
    assert "sales" in combined
    assert "hr" in combined
    assert len(data["tools_used"]) >= 3


def test_multi_agent_coordinator_deduplication(db_session):
    """Test that the coordinator deduplicates identical planned tool calls."""
    admin_user = User(
        email="coord.dedup@enterprise.com",
        hashed_password=hash_password("Pass123!"),
        role=UserRole.ADMIN.value,
        is_active=True,
    )
    db_session.add(admin_user)
    db_session.commit()

    raw_planned = [
        {"department": "inventory", "tool_name": "get_low_stock_alerts", "arguments": {}},
        {"department": "inventory", "tool_name": "get_low_stock_alerts", "arguments": {}},
        {"department": "sales", "tool_name": "get_recognized_revenue", "arguments": {}},
    ]

    coord_res = multi_agent_coordinator.coordinate_execution(
        planned_tools_raw=raw_planned,
        current_user=admin_user,
        main_db=db_session,
    )

    # get_low_stock_alerts should only be executed once
    assert coord_res["tools_used"].count("get_low_stock_alerts") == 1
    assert "get_recognized_revenue" in coord_res["tools_used"]
    assert set(coord_res["agents_involved"]) == {"inventory", "sales"}


def test_agent_domain_permission_enforcement(
    client: TestClient, employee_user_with_headers: tuple
):
    """Test RBAC boundaries: Employee role executing unauthorized department tools."""
    _, _, employee_headers = employee_user_with_headers

    # Employee asking for warehouse executive summary or replenishment suggestions (Admin/Manager only)
    res = client.post(
        "/api/v1/agents/chat",
        json={"message": "Show me warehouse replenishment suggestions for all products."},
        headers=employee_headers,
    )
    assert res.status_code == 200
    data = res.json()
    # Server-side RBAC catches access denial
    assert (
        "access denied" in data["answer"].lower()
        or (data["error"] and "access denied" in data["error"].lower())
        or not data["success"]
    )


def test_agent_failure_containment_and_partial_results(db_session):
    """Test that a failure in one specialized agent does not crash other coordinating agents."""
    admin_user = User(
        email="coord.failure@enterprise.com",
        hashed_password=hash_password("Pass123!"),
        role=UserRole.ADMIN.value,
        is_active=True,
    )
    db_session.add(admin_user)
    db_session.commit()

    # Pass an unknown/faulty tool alongside a valid tool
    raw_planned = [
        {"department": "sales", "tool_name": "get_recognized_revenue", "arguments": {}},
        {"department": "inventory", "tool_name": "non_existent_exploding_tool", "arguments": {}},
    ]

    coord_res = multi_agent_coordinator.coordinate_execution(
        planned_tools_raw=raw_planned,
        current_user=admin_user,
        main_db=db_session,
    )

    # Sales succeeded
    assert "get_recognized_revenue" in coord_res["tools_used"]
    assert "sales" in coord_res["completed_departments"]
    # Telemetry captured
    assert "sales" in coord_res["agent_executions"]
    assert coord_res["agent_executions"]["sales"]["success"] is True


def test_multi_agent_with_persistent_conversation_memory(
    client: TestClient, admin_headers: dict[str, str]
):
    """Test compound multi-agent queries store full history in conversation session."""
    # 1. Create a conversation
    res_conv = client.post(
        "/api/v1/conversations",
        json={"title": "Multi-Agent Executive Briefing"},
        headers=admin_headers,
    )
    assert res_conv.status_code == 201
    conv_id = res_conv.json()["id"]

    # 2. Send multi-agent query attached to conversation
    res_chat = client.post(
        "/api/v1/agents/chat",
        json={
            "message": "Which products are running low and what is our recognized revenue?",
            "conversation_id": conv_id,
        },
        headers=admin_headers,
    )
    assert res_chat.status_code == 200
    assert res_chat.json()["conversation_id"] == conv_id

    # 3. Retrieve conversation history
    res_detail = client.get(f"/api/v1/conversations/{conv_id}", headers=admin_headers)
    assert res_detail.status_code == 200
    detail = res_detail.json()
    assert len(detail["messages"]) >= 2
    assistant_msg = detail["messages"][-1]
    assert assistant_msg["role"] == "assistant"
    assert len(assistant_msg["tools_used"]) >= 2
