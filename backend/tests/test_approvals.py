"""Tests for Phase 5: Human-in-the-Loop Approval Workflows and Security Safeguards."""

from app.models.inventory import Product, StockMovement
from app.models.leave import LeaveRequest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session


def test_create_purchase_requisition_proposal(client: TestClient, admin_headers: dict[str, str]):
    """Test creating a purchase requisition approval proposal."""
    payload = {
        "request_type": "PURCHASE_REQUISITION",
        "title": "Replenish 20 units of Low Stock Product",
        "description": "Stock is critically low below safety threshold",
        "assigned_role": "Manager",
        "action_payload": {
            "items": [
                {"sku": "SKU-GFT-030", "quantity": 20}
            ]
        },
    }
    res = client.post("/api/v1/approvals", json=payload, headers=admin_headers)
    assert res.status_code == 201
    data = res.json()
    assert data["request_code"].startswith("REQ-PO-")
    assert data["status"] == "PENDING"
    assert "@enterprise.com" in data["requester_email"]


def test_employee_cannot_approve_unauthorized_requests(
    client: TestClient, admin_headers: dict[str, str], employee_user_with_headers: tuple
):
    """Test that an employee cannot approve purchase requisitions or other approvals."""
    _, _, employee_headers = employee_user_with_headers

    # 1. Admin creates a proposal
    payload = {
        "request_type": "PURCHASE_REQUISITION",
        "title": "Restock Request",
        "action_payload": {"items": [{"sku": "SKU-GFT-030", "quantity": 10}]},
    }
    res = client.post("/api/v1/approvals", json=payload, headers=admin_headers)
    assert res.status_code == 201
    req_id = res.json()["id"]

    # 2. Employee attempts to approve it -> 403 Forbidden
    res_app = client.post(
        f"/api/v1/approvals/{req_id}/approve",
        json={"reason": "Self-approved by employee"},
        headers=employee_headers,
    )
    assert res_app.status_code == 403
    assert "Access forbidden" in res_app.json()["detail"] or "Self-approval" in res_app.json()["detail"]


def test_self_approval_is_blocked_by_default(
    client: TestClient, manager_headers: dict[str, str]
):
    """Test strict anti-self-approval rule: Reviewer cannot approve their own submitted request."""
    # 1. Manager submits a proposal
    payload = {
        "request_type": "PURCHASE_REQUISITION",
        "title": "Manager Personal Requisition",
        "action_payload": {"items": [{"sku": "SKU-GFT-030", "quantity": 5}]},
    }
    res_create = client.post("/api/v1/approvals", json=payload, headers=manager_headers)
    assert res_create.status_code == 201
    req_id = res_create.json()["id"]

    # 2. Same Manager attempts to approve their own request -> 403 Forbidden
    res_self = client.post(
        f"/api/v1/approvals/{req_id}/approve",
        json={"reason": "I approve my own order"},
        headers=manager_headers,
    )
    assert res_self.status_code == 403
    assert "Self-approval policy violation" in res_self.json()["detail"]


def test_unauthorized_users_cannot_access_approval_records(
    client: TestClient, admin_headers: dict[str, str], employee_user_with_headers: tuple
):
    """Test ownership privacy: Employee cannot view private proposals submitted by others."""
    _, _, employee_headers = employee_user_with_headers

    # 1. Admin creates proposal
    payload = {
        "request_type": "PURCHASE_REQUISITION",
        "title": "Confidential Executive Purchase",
        "action_payload": {"items": [{"sku": "SKU-GFT-030", "quantity": 100}]},
    }
    res_create = client.post("/api/v1/approvals", json=payload, headers=admin_headers)
    req_id = res_create.json()["id"]

    # 2. Employee attempts to view detail -> 403 Forbidden
    res_get = client.get(f"/api/v1/approvals/{req_id}", headers=employee_headers)
    assert res_get.status_code == 403


def test_pending_request_cannot_execute(client: TestClient, admin_headers: dict[str, str]):
    """Test that an unapproved PENDING request cannot be executed."""
    payload = {
        "request_type": "PURCHASE_REQUISITION",
        "title": "Premature Execution Test",
        "action_payload": {"items": [{"sku": "SKU-GFT-030", "quantity": 5}]},
    }
    res = client.post("/api/v1/approvals", json=payload, headers=admin_headers)
    req_id = res.json()["id"]

    # Attempt to execute while PENDING -> 400 Bad Request
    res_exec = client.post(f"/api/v1/approvals/{req_id}/execute", headers=admin_headers)
    assert res_exec.status_code == 400
    assert "Cannot execute a pending approval request" in res_exec.json()["detail"]


def test_rejected_request_cannot_execute(
    client: TestClient, admin_headers: dict[str, str], manager_headers: dict[str, str]
):
    """Test that a rejected request cannot be executed."""
    # 1. Admin creates proposal
    payload = {
        "request_type": "PURCHASE_REQUISITION",
        "title": "Rejection Test",
        "action_payload": {"items": [{"sku": "SKU-GFT-030", "quantity": 15}]},
    }
    res = client.post("/api/v1/approvals", json=payload, headers=admin_headers)
    req_id = res.json()["id"]

    # 2. Manager rejects it
    res_rej = client.post(
        f"/api/v1/approvals/{req_id}/reject",
        json={"reason": "Budget exhausted for this quarter"},
        headers=manager_headers,
    )
    assert res_rej.status_code == 200
    assert res_rej.json()["status"] == "REJECTED"

    # 3. Attempt execution on REJECTED -> 400 Bad Request
    res_exec = client.post(f"/api/v1/approvals/{req_id}/execute", headers=admin_headers)
    assert res_exec.status_code == 400
    assert "Cannot execute a rejected approval request" in res_exec.json()["detail"]


def test_approved_request_executes_only_once_and_simulates_po(
    client: TestClient, admin_headers: dict[str, str], manager_headers: dict[str, str], db_session: Session
):
    """Test purchase requisition lifecycle: updates on_order, preserves on_hand, prevents false physical receipt."""
    prod = db_session.scalar(select(Product).where(Product.sku == "SKU-GFT-030"))
    assert prod is not None
    initial_on_order = prod.quantity_on_order
    initial_on_hand = prod.quantity_on_hand

    # 1. Admin creates purchase requisition
    payload = {
        "request_type": "PURCHASE_REQUISITION",
        "title": "Simulated PO Lifecycle Requisition",
        "action_payload": {"items": [{"sku": "SKU-GFT-030", "quantity": 12}]},
    }
    res = client.post("/api/v1/approvals", json=payload, headers=admin_headers)
    req_id = res.json()["id"]

    # 2. Manager approves it
    res_app = client.post(
        f"/api/v1/approvals/{req_id}/approve",
        json={"reason": "Approved for replenishment"},
        headers=manager_headers,
    )
    assert res_app.status_code == 200
    assert res_app.json()["status"] == "APPROVED"

    # 3. Execute approved simulated PO
    res_exec = client.post(f"/api/v1/approvals/{req_id}/execute", headers=manager_headers)
    assert res_exec.status_code == 200
    exec_data = res_exec.json()
    assert exec_data["status"] == "CONFIRMED_ON_ORDER"
    assert "PO-SIM-" in exec_data["simulated_po_number"]
    assert exec_data["quantity_on_order_updated"] is True
    assert exec_data["quantity_on_hand_updated"] is False
    assert exec_data["physical_movement_recorded"] is False

    # 4. Verify database state:
    # - quantity_on_order is incremented by 12
    # - quantity_on_hand REMAINS COMPLETELY UNCHANGED
    # - NO physical StockMovement is created before delivery!
    db_session.expire_all()
    updated_prod = db_session.scalar(select(Product).where(Product.sku == "SKU-GFT-030"))
    assert updated_prod.quantity_on_order == initial_on_order + 12
    assert updated_prod.quantity_on_hand == initial_on_hand

    movement = db_session.scalar(
        select(StockMovement).where(StockMovement.reference == exec_data["simulated_po_number"])
    )
    assert movement is None, "Purchase order placement must NOT record a physical StockMovement!"

    # 5. Duplicate execution attempt -> 400 Bad Request
    res_dup = client.post(f"/api/v1/approvals/{req_id}/execute", headers=manager_headers)
    assert res_dup.status_code == 400
    assert "already been executed" in res_dup.json()["detail"]

    # 6. Verify subsequent actual delivery receipt (via separate stock_in) DOES update on_hand and creates StockMovement
    receipt_res = client.post(
        "/api/v1/inventory/stock/in",
        json={
            "product_id": updated_prod.id,
            "quantity": 12,
            "reason": "Physical delivery received from supplier",
            "reference": exec_data["simulated_po_number"],
        },
        headers=manager_headers,
    )
    assert receipt_res.status_code == 201
    movement_data = receipt_res.json()
    assert movement_data["movement_type"] == "IN"
    assert movement_data["quantity"] == 12

    db_session.expire_all()
    delivered_prod = db_session.scalar(select(Product).where(Product.sku == "SKU-GFT-030"))
    assert delivered_prod.quantity_on_hand == initial_on_hand + 12
    assert delivered_prod.quantity_on_order == initial_on_order


def test_leave_approval_workflow(
    client: TestClient,
    admin_headers: dict[str, str],
    hr_headers: dict[str, str],
    employee_user_with_headers: tuple,
    db_session: Session,
):
    """Test full leave request approval lifecycle: submit -> HR approves -> execute creates official leave."""
    payload = {
        "request_type": "LEAVE_REQUEST",
        "title": "Annual Leave Application",
        "action_payload": {
            "employee_code": "EMP-FIXTURE-001",
            "leave_type": "ANNUAL",
            "start_date": "2026-11-20",
            "end_date": "2026-11-25",
            "days_count": 5,
            "reason": "Family vacation",
        },
    }
    # 1. Admin submits proposal
    res_create = client.post("/api/v1/approvals", json=payload, headers=admin_headers)
    assert res_create.status_code == 201
    req_id = res_create.json()["id"]

    # 2. HR approves proposal
    res_app = client.post(
        f"/api/v1/approvals/{req_id}/approve",
        json={"reason": "Leave quota verified and authorized"},
        headers=hr_headers,
    )
    assert res_app.status_code == 200
    assert res_app.json()["status"] == "APPROVED"

    # 3. Execute approved leave
    res_exec = client.post(f"/api/v1/approvals/{req_id}/execute", headers=hr_headers)
    assert res_exec.status_code == 200
    exec_data = res_exec.json()
    assert exec_data["status"] == "APPROVED"
    assert "official_leave_code" in exec_data

    # 4. Verify official LeaveRequest created in HR database
    leave_rec = db_session.scalar(
        select(LeaveRequest).where(LeaveRequest.leave_code == exec_data["official_leave_code"])
    )
    assert leave_rec is not None
    assert leave_rec.days_count == 5
    assert leave_rec.status == "APPROVED"


def test_approval_history_and_audit_trail(
    client: TestClient, admin_headers: dict[str, str], manager_headers: dict[str, str]
):
    """Test that full audit trail of transitions is preserved chronologically."""
    # 1. Create
    payload = {
        "request_type": "PURCHASE_REQUISITION",
        "title": "Audit Trail Inspection Request",
        "action_payload": {"items": [{"sku": "SKU-GFT-030", "quantity": 8}]},
    }
    res = client.post("/api/v1/approvals", json=payload, headers=admin_headers)
    req_id = res.json()["id"]

    # 2. Approve
    client.post(
        f"/api/v1/approvals/{req_id}/approve",
        json={"reason": "Audit checkpoint approved"},
        headers=manager_headers,
    )

    # 3. Execute
    client.post(f"/api/v1/approvals/{req_id}/execute", headers=manager_headers)

    # 4. Fetch history
    res_hist = client.get(f"/api/v1/approvals/{req_id}/history", headers=admin_headers)
    assert res_hist.status_code == 200
    history = res_hist.json()
    assert len(history) >= 3
    actions = [h["action"] for h in history]
    assert actions == ["CREATED", "APPROVED", "EXECUTED"]


def test_ai_agent_prepare_requisition_and_status_check(
    client: TestClient, admin_headers: dict[str, str]
):
    """Test AI assistant tools: prepare_purchase_requisition and check_approval_status."""
    # 1. Ask AI to prepare a purchase requisition
    chat_res = client.post(
        "/api/v1/agents/chat",
        json={"message": "Prepare a purchase requisition for 15 units of SKU-GFT-030"},
        headers=admin_headers,
    )
    assert chat_res.status_code == 200
    ans = chat_res.json()["answer"]
    assert "REQ-PO-" in ans or "purchase requisition" in ans.lower()

    # 2. Query status via chat
    status_res = client.post(
        "/api/v1/agents/chat",
        json={"message": "Check approval status of the requisition"},
        headers=admin_headers,
    )
    assert status_res.status_code == 200
    assert "check_approval_status" in status_res.json()["tools_used"] or "status" in status_res.json()["answer"].lower()
