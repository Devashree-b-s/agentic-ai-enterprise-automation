"""Comprehensive automated test suite for the Sales Management module."""

from decimal import Decimal

from fastapi.testclient import TestClient

# ============================================================================
# Customer Tests
# ============================================================================


def test_create_customer_success(client: TestClient, manager_headers: dict[str, str]):
    """Test creating a customer returns 201 and valid response fields."""
    payload = {
        "customer_code": "CUST-001",
        "name": "Acme Industrial Corp",
        "email": "procurement@acme.com",
        "phone": "+1-555-0100",
        "address": "450 Enterprise Way, Suite 10",
        "is_active": True,
    }
    response = client.post(
        "/api/v1/sales/customers", json=payload, headers=manager_headers
    )
    assert response.status_code == 201
    data = response.json()
    assert data["id"] is not None
    assert data["customer_code"] == "CUST-001"
    assert data["name"] == "Acme Industrial Corp"
    assert data["email"] == "procurement@acme.com"


def test_create_customer_duplicate_code(
    client: TestClient, manager_headers: dict[str, str]
):
    """Test creating a customer with existing code returns 409 Conflict."""
    payload = {
        "customer_code": "CUST-DUP-CODE",
        "name": "Alpha Inc",
        "email": "alpha@enterprise.com",
    }
    res1 = client.post("/api/v1/sales/customers", json=payload, headers=manager_headers)
    assert res1.status_code == 201

    payload_dup = {
        "customer_code": "CUST-DUP-CODE",
        "name": "Beta Inc",
        "email": "beta@enterprise.com",
    }
    res2 = client.post(
        "/api/v1/sales/customers", json=payload_dup, headers=manager_headers
    )
    assert res2.status_code == 409
    assert "already exists" in res2.json()["detail"]


def test_create_customer_duplicate_email(
    client: TestClient, manager_headers: dict[str, str]
):
    """Test creating a customer with existing email returns 409 Conflict."""
    res1 = client.post(
        "/api/v1/sales/customers",
        json={
            "customer_code": "CUST-EMAIL-1",
            "name": "Gamma Corp",
            "email": "shared@gamma.com",
        },
        headers=manager_headers,
    )
    assert res1.status_code == 201

    res2 = client.post(
        "/api/v1/sales/customers",
        json={
            "customer_code": "CUST-EMAIL-2",
            "name": "Delta Corp",
            "email": "shared@gamma.com",
        },
        headers=manager_headers,
    )
    assert res2.status_code == 409
    assert "already exists" in res2.json()["detail"]


def test_list_and_filter_customers(client: TestClient, manager_headers: dict[str, str]):
    """Test listing customers with active filter and pagination."""
    customers = [
        {
            "customer_code": "CUST-LST-1",
            "name": "Active One",
            "email": "act1@c.com",
            "is_active": True,
        },
        {
            "customer_code": "CUST-LST-2",
            "name": "Inactive Two",
            "email": "inact2@c.com",
            "is_active": False,
        },
    ]
    for c in customers:
        client.post("/api/v1/sales/customers", json=c, headers=manager_headers)

    # Filter active
    res_active = client.get(
        "/api/v1/sales/customers?is_active=true", headers=manager_headers
    )
    assert res_active.status_code == 200
    for cust in res_active.json():
        assert cust["is_active"] is True

    # Filter inactive
    res_inactive = client.get(
        "/api/v1/sales/customers?is_active=false", headers=manager_headers
    )
    assert res_inactive.status_code == 200
    assert any(c["customer_code"] == "CUST-LST-2" for c in res_inactive.json())


def test_get_and_update_customer(client: TestClient, manager_headers: dict[str, str]):
    """Test fetching and updating a customer record."""
    create_res = client.post(
        "/api/v1/sales/customers",
        json={
            "customer_code": "CUST-UPD-1",
            "name": "Original Name",
            "email": "original@name.com",
        },
        headers=manager_headers,
    )
    cust_id = create_res.json()["id"]

    # Update
    update_res = client.put(
        f"/api/v1/sales/customers/{cust_id}",
        json={"name": "Updated Name Corp", "phone": "+1-800-RENEW"},
        headers=manager_headers,
    )
    assert update_res.status_code == 200
    assert update_res.json()["name"] == "Updated Name Corp"
    assert update_res.json()["phone"] == "+1-800-RENEW"

    # 404 on non-existent
    not_found = client.get("/api/v1/sales/customers/999999", headers=manager_headers)
    assert not_found.status_code == 404


def test_delete_customer_without_orders(
    client: TestClient, manager_headers: dict[str, str]
):
    """Test deleting a customer without orders returns 204."""
    create_res = client.post(
        "/api/v1/sales/customers",
        json={
            "customer_code": "CUST-DEL-1",
            "name": "Delete Me",
            "email": "del@me.com",
        },
        headers=manager_headers,
    )
    cust_id = create_res.json()["id"]

    del_res = client.delete(
        f"/api/v1/sales/customers/{cust_id}", headers=manager_headers
    )
    assert del_res.status_code == 204

    # Verify deleted
    get_res = client.get(f"/api/v1/sales/customers/{cust_id}", headers=manager_headers)
    assert get_res.status_code == 404


# ============================================================================
# Order Creation & Calculation Tests
# ============================================================================


def test_create_order_deterministic_calculation(
    client: TestClient, manager_headers: dict[str, str]
):
    """Test order creation computes item subtotals and order total deterministically."""
    # Create customer first
    cust_res = client.post(
        "/api/v1/sales/customers",
        json={
            "customer_code": "CUST-ORD-CALC",
            "name": "Global Logistics",
            "email": "orders@globallogistics.com",
        },
        headers=manager_headers,
    )
    cust_id = cust_res.json()["id"]

    # Place order with 2 items
    # Item 1: 3 units @ $150.25 = $450.75
    # Item 2: 2 units @ $25.50 = $51.00
    # Expected total = $501.75
    order_payload = {
        "customer_id": cust_id,
        "notes": "Urgent enterprise delivery",
        "items": [
            {
                "product_id": 101,
                "product_name": "Heavy Duty Router",
                "quantity": 3,
                "unit_price": 150.25,
            },
            {
                "product_id": 102,
                "product_name": "Patch Cable Pack",
                "quantity": 2,
                "unit_price": 25.50,
            },
        ],
    }
    response = client.post(
        "/api/v1/sales/orders", json=order_payload, headers=manager_headers
    )
    assert response.status_code == 201
    data = response.json()

    assert data["id"] is not None
    assert data["order_number"].startswith("ORD-")
    assert data["status"] == "PENDING"
    assert Decimal(str(data["total_amount"])) == Decimal("501.75")
    assert len(data["items"]) == 2

    # Verify line item calculations
    item1 = next(i for i in data["items"] if i["product_id"] == 101)
    assert Decimal(str(item1["subtotal"])) == Decimal("450.75")

    item2 = next(i for i in data["items"] if i["product_id"] == 102)
    assert Decimal(str(item2["subtotal"])) == Decimal("51.00")

    # Verify eager-loaded customer
    assert data["customer"]["id"] == cust_id
    assert data["customer"]["name"] == "Global Logistics"


def test_create_order_validation_errors(
    client: TestClient, manager_headers: dict[str, str]
):
    """Test order creation rejects non-existent customer, negative quantities, and empty items."""
    # 1. Non-existent customer
    res_bad_cust = client.post(
        "/api/v1/sales/orders",
        json={
            "customer_id": 999999,
            "items": [
                {
                    "product_id": 1,
                    "product_name": "X",
                    "quantity": 1,
                    "unit_price": 10.0,
                }
            ],
        },
        headers=manager_headers,
    )
    assert res_bad_cust.status_code == 404

    # 2. Empty items list
    res_empty = client.post(
        "/api/v1/sales/orders",
        json={
            "customer_id": 1,
            "items": [],
        },
        headers=manager_headers,
    )
    assert res_empty.status_code == 422

    # 3. Negative quantity
    res_neg_qty = client.post(
        "/api/v1/sales/orders",
        json={
            "customer_id": 1,
            "items": [
                {
                    "product_id": 1,
                    "product_name": "X",
                    "quantity": -2,
                    "unit_price": 10.0,
                }
            ],
        },
        headers=manager_headers,
    )
    assert res_neg_qty.status_code == 422

    # 4. Negative unit price
    res_neg_price = client.post(
        "/api/v1/sales/orders",
        json={
            "customer_id": 1,
            "items": [
                {
                    "product_id": 1,
                    "product_name": "X",
                    "quantity": 1,
                    "unit_price": -50.0,
                }
            ],
        },
        headers=manager_headers,
    )
    assert res_neg_price.status_code == 422


def test_delete_customer_with_orders_blocked(
    client: TestClient, manager_headers: dict[str, str]
):
    """Test that customer cannot be deleted if sales orders are linked to them."""
    cust_res = client.post(
        "/api/v1/sales/customers",
        json={
            "customer_code": "CUST-HAS-ORDERS",
            "name": "Loyal Client",
            "email": "loyal@client.com",
        },
        headers=manager_headers,
    )
    cust_id = cust_res.json()["id"]

    # Place an order
    client.post(
        "/api/v1/sales/orders",
        json={
            "customer_id": cust_id,
            "items": [
                {
                    "product_id": 1,
                    "product_name": "Item",
                    "quantity": 1,
                    "unit_price": 100.0,
                }
            ],
        },
        headers=manager_headers,
    )

    # Attempt deletion -> must fail with 400
    del_res = client.delete(
        f"/api/v1/sales/customers/{cust_id}", headers=manager_headers
    )
    assert del_res.status_code == 400
    assert "Cannot delete customer" in del_res.json()["detail"]


# ============================================================================
# Order Status State Machine Tests
# ============================================================================


def test_order_status_valid_lifecycle(
    client: TestClient, manager_headers: dict[str, str]
):
    """Test valid order progression: PENDING -> CONFIRMED -> SHIPPED -> DELIVERED."""
    cust_res = client.post(
        "/api/v1/sales/customers",
        json={
            "customer_code": "CUST-STATUS-OK",
            "name": "Status Tester",
            "email": "status@test.com",
        },
        headers=manager_headers,
    )
    cust_id = cust_res.json()["id"]

    order_res = client.post(
        "/api/v1/sales/orders",
        json={
            "customer_id": cust_id,
            "items": [
                {
                    "product_id": 1,
                    "product_name": "Product",
                    "quantity": 1,
                    "unit_price": 100.0,
                }
            ],
        },
        headers=manager_headers,
    )
    order_id = order_res.json()["id"]
    assert order_res.json()["status"] == "PENDING"

    # PENDING -> CONFIRMED
    res_conf = client.patch(
        f"/api/v1/sales/orders/{order_id}/status",
        json={"status": "CONFIRMED"},
        headers=manager_headers,
    )
    assert res_conf.status_code == 200
    assert res_conf.json()["status"] == "CONFIRMED"

    # CONFIRMED -> SHIPPED
    res_ship = client.patch(
        f"/api/v1/sales/orders/{order_id}/status",
        json={"status": "SHIPPED"},
        headers=manager_headers,
    )
    assert res_ship.status_code == 200
    assert res_ship.json()["status"] == "SHIPPED"

    # SHIPPED -> DELIVERED
    res_del = client.patch(
        f"/api/v1/sales/orders/{order_id}/status",
        json={"status": "DELIVERED"},
        headers=manager_headers,
    )
    assert res_del.status_code == 200
    assert res_del.json()["status"] == "DELIVERED"


def test_order_status_invalid_transitions(
    client: TestClient, manager_headers: dict[str, str]
):
    """Test invalid status transitions are rejected with 400 Bad Request."""
    cust_res = client.post(
        "/api/v1/sales/customers",
        json={
            "customer_code": "CUST-STATUS-BAD",
            "name": "Bad Transitions",
            "email": "bad@status.com",
        },
        headers=manager_headers,
    )
    cust_id = cust_res.json()["id"]

    order = client.post(
        "/api/v1/sales/orders",
        json={
            "customer_id": cust_id,
            "items": [
                {
                    "product_id": 1,
                    "product_name": "Product",
                    "quantity": 1,
                    "unit_price": 100.0,
                }
            ],
        },
        headers=manager_headers,
    ).json()

    # Cancel order: PENDING -> CANCELLED
    client.patch(
        f"/api/v1/sales/orders/{order['id']}/status",
        json={"status": "CANCELLED"},
        headers=manager_headers,
    )

    # Attempt to revive CANCELLED -> CONFIRMED (must fail)
    res_invalid = client.patch(
        f"/api/v1/sales/orders/{order['id']}/status",
        json={"status": "CONFIRMED"},
        headers=manager_headers,
    )
    assert res_invalid.status_code == 400
    assert "Invalid status transition" in res_invalid.json()["detail"]


# ============================================================================
# Revenue Calculations & Sales Reports Tests
# ============================================================================


def test_sales_summary_and_monthly_revenue_reports(
    client: TestClient, manager_headers: dict[str, str]
):
    """Test executive summary and monthly revenue calculations with recognized vs cancelled revenue."""
    cust = client.post(
        "/api/v1/sales/customers",
        json={
            "customer_code": "CUST-REPORTS",
            "name": "Big Enterprise Client",
            "email": "analytics@bigenterprise.com",
        },
        headers=manager_headers,
    ).json()

    # Create Order 1: $1000.0 (CONFIRMED -> Recognized)
    o1 = client.post(
        "/api/v1/sales/orders",
        json={
            "customer_id": cust["id"],
            "items": [
                {
                    "product_id": 1,
                    "product_name": "Server",
                    "quantity": 1,
                    "unit_price": 1000.0,
                }
            ],
        },
        headers=manager_headers,
    ).json()
    client.patch(
        f"/api/v1/sales/orders/{o1['id']}/status",
        json={"status": "CONFIRMED"},
        headers=manager_headers,
    )

    # Create Order 2: $500.0 (SHIPPED -> Recognized)
    o2 = client.post(
        "/api/v1/sales/orders",
        json={
            "customer_id": cust["id"],
            "items": [
                {
                    "product_id": 2,
                    "product_name": "Switch",
                    "quantity": 1,
                    "unit_price": 500.0,
                }
            ],
        },
        headers=manager_headers,
    ).json()
    res_conf2 = client.patch(
        f"/api/v1/sales/orders/{o2['id']}/status",
        json={"status": "CONFIRMED"},
        headers=manager_headers,
    )
    assert res_conf2.status_code == 200
    res_ship2 = client.patch(
        f"/api/v1/sales/orders/{o2['id']}/status",
        json={"status": "SHIPPED"},
        headers=manager_headers,
    )
    assert res_ship2.status_code == 200

    # Create Order 3: $300.0 (CANCELLED -> NOT Recognized in Revenue)
    o3 = client.post(
        "/api/v1/sales/orders",
        json={
            "customer_id": cust["id"],
            "items": [
                {
                    "product_id": 3,
                    "product_name": "Cables",
                    "quantity": 1,
                    "unit_price": 300.0,
                }
            ],
        },
        headers=manager_headers,
    ).json()
    client.patch(
        f"/api/v1/sales/orders/{o3['id']}/status",
        json={"status": "CANCELLED"},
        headers=manager_headers,
    )

    # 1. Summary Report Verification
    res_summary = client.get("/api/v1/sales/reports/summary", headers=manager_headers)
    assert res_summary.status_code == 200
    summary = res_summary.json()

    assert summary["total_orders"] >= 3
    # Recognized revenue must include $1000 + $500 = $1500, but exclude $300
    assert Decimal(str(summary["total_revenue"])) >= Decimal("1500.00")
    assert Decimal(str(summary["average_order_value"])) > Decimal("0.00")
    assert summary["orders_by_status"]["CANCELLED"] >= 1
    assert summary["orders_by_status"]["CONFIRMED"] >= 1

    # 2. Monthly Revenue Report Verification
    res_monthly = client.get("/api/v1/sales/reports/monthly", headers=manager_headers)
    assert res_monthly.status_code == 200
    monthly = res_monthly.json()

    assert Decimal(str(monthly["total_recognized_revenue"])) >= Decimal("1500.00")
    assert len(monthly["months"]) >= 1
    current_month_item = monthly["months"][0]
    assert Decimal(str(current_month_item["revenue"])) >= Decimal("1500.00")
    assert current_month_item["order_count"] >= 2


# ============================================================================
# RBAC Security Tests on Sales API
# ============================================================================


def test_rbac_sales_employee_permissions(
    client: TestClient,
    employee_user_with_headers: tuple,
    manager_headers: dict[str, str],
):
    """Test RBAC: Employee can place and view orders, but cannot delete or view revenue analytics."""
    _, _, emp_headers = employee_user_with_headers

    # Seed customer using Manager
    cust = client.post(
        "/api/v1/sales/customers",
        json={
            "customer_code": "CUST-RBAC-EMP",
            "name": "Employee Sales Client",
            "email": "emp.client@corp.com",
        },
        headers=manager_headers,
    ).json()

    # 1. Employee CAN create an order
    emp_order_res = client.post(
        "/api/v1/sales/orders",
        json={
            "customer_id": cust["id"],
            "items": [
                {
                    "product_id": 1,
                    "product_name": "Widget",
                    "quantity": 2,
                    "unit_price": 50.0,
                }
            ],
        },
        headers=emp_headers,
    )
    assert emp_order_res.status_code == 201
    order_id = emp_order_res.json()["id"]

    # 2. Employee CANNOT update order status (403 Forbidden)
    status_res = client.patch(
        f"/api/v1/sales/orders/{order_id}/status",
        json={"status": "CONFIRMED"},
        headers=emp_headers,
    )
    assert status_res.status_code == 403

    # 3. Employee CANNOT delete an order (403 Forbidden)
    del_res = client.delete(f"/api/v1/sales/orders/{order_id}", headers=emp_headers)
    assert del_res.status_code == 403

    # 4. Employee CANNOT view revenue analytics reports (403 Forbidden)
    report_res = client.get("/api/v1/sales/reports/summary", headers=emp_headers)
    assert report_res.status_code == 403

    monthly_res = client.get("/api/v1/sales/reports/monthly", headers=emp_headers)
    assert monthly_res.status_code == 403


def test_sales_api_unauthenticated_rejected(client: TestClient):
    """Test unauthenticated calls to Sales endpoints return 401 Unauthorized."""
    assert client.get("/api/v1/sales/customers").status_code == 401
    assert client.get("/api/v1/sales/orders").status_code == 401
    assert client.get("/api/v1/sales/reports/summary").status_code == 401


# ============================================================================
# Financial Precision & Strict State Machine Tests
# ============================================================================


def test_financial_precision_calculations(
    client: TestClient, manager_headers: dict[str, str]
):
    """Test exact Decimal financial precision avoiding binary floating-point inaccuracies.

    Verifies calculations with 0.10, 0.20, and 19.99, plus schema validation of decimals.
    """
    cust_res = client.post(
        "/api/v1/sales/customers",
        json={
            "customer_code": "CUST-PRECISION-TEST",
            "name": "Precision Engineering Ltd",
            "email": "precision@engineering.com",
        },
        headers=manager_headers,
    )
    assert cust_res.status_code == 201
    cust_id = cust_res.json()["id"]

    # Test 1: 0.10 + 0.20 = 0.30 (avoid IEEE 754 0.30000000000000004 bug)
    order_01_02 = client.post(
        "/api/v1/sales/orders",
        json={
            "customer_id": cust_id,
            "items": [
                {
                    "product_id": 1,
                    "product_name": "Resistor 0.10",
                    "quantity": 1,
                    "unit_price": 0.10,
                },
                {
                    "product_id": 2,
                    "product_name": "Capacitor 0.20",
                    "quantity": 1,
                    "unit_price": 0.20,
                },
            ],
        },
        headers=manager_headers,
    )
    assert order_01_02.status_code == 201
    data_01_02 = order_01_02.json()

    assert Decimal(str(data_01_02["total_amount"])) == Decimal("0.30")
    item0 = data_01_02["items"][0]
    item1 = data_01_02["items"][1]
    assert Decimal(str(item0["subtotal"])) == Decimal("0.10")
    assert Decimal(str(item1["subtotal"])) == Decimal("0.20")

    # Test 2: 3 * 19.99 = 59.97 (avoid binary 59.96999999999999 bug)
    order_1999 = client.post(
        "/api/v1/sales/orders",
        json={
            "customer_id": cust_id,
            "items": [
                {
                    "product_id": 3,
                    "product_name": "Specialty Tool",
                    "quantity": 3,
                    "unit_price": 19.99,
                }
            ],
        },
        headers=manager_headers,
    )
    assert order_1999.status_code == 201
    data_1999 = order_1999.json()

    assert Decimal(str(data_1999["total_amount"])) == Decimal("59.97")
    assert Decimal(str(data_1999["items"][0]["subtotal"])) == Decimal("59.97")

    # Test 3: String-based monetary representations ("19.99" and "0.10")
    order_str = client.post(
        "/api/v1/sales/orders",
        json={
            "customer_id": cust_id,
            "items": [
                {
                    "product_id": 4,
                    "product_name": "Widget A",
                    "quantity": 2,
                    "unit_price": "19.99",
                },
                {
                    "product_id": 5,
                    "product_name": "Widget B",
                    "quantity": 5,
                    "unit_price": "0.10",
                },
            ],
        },
        headers=manager_headers,
    )
    assert order_str.status_code == 201
    data_str = order_str.json()
    # 2 * 19.99 = 39.98; 5 * 0.10 = 0.50; 39.98 + 0.50 = 40.48
    assert Decimal(str(data_str["total_amount"])) == Decimal("40.48")

    # Test 4: Reject more than 2 decimal places (e.g. 19.999)
    res_invalid_places = client.post(
        "/api/v1/sales/orders",
        json={
            "customer_id": cust_id,
            "items": [
                {
                    "product_id": 6,
                    "product_name": "Invalid Price",
                    "quantity": 1,
                    "unit_price": 19.999,
                }
            ],
        },
        headers=manager_headers,
    )
    assert res_invalid_places.status_code == 422

    # Test 5: Reject negative unit price
    res_neg_price = client.post(
        "/api/v1/sales/orders",
        json={
            "customer_id": cust_id,
            "items": [
                {
                    "product_id": 7,
                    "product_name": "Negative Price",
                    "quantity": 1,
                    "unit_price": -0.01,
                }
            ],
        },
        headers=manager_headers,
    )
    assert res_neg_price.status_code == 422


def test_order_status_cannot_cancel_after_shipped_or_delivered(
    client: TestClient, manager_headers: dict[str, str]
):
    """Test order state machine prevents cancellation once SHIPPED or DELIVERED, and keeps terminal states."""
    cust_res = client.post(
        "/api/v1/sales/customers",
        json={
            "customer_code": "CUST-TERMINAL-STATE",
            "name": "State Machine Co",
            "email": "lifecycle@statemachine.com",
        },
        headers=manager_headers,
    )
    cust_id = cust_res.json()["id"]

    order = client.post(
        "/api/v1/sales/orders",
        json={
            "customer_id": cust_id,
            "items": [
                {
                    "product_id": 1,
                    "product_name": "Hardware Server",
                    "quantity": 1,
                    "unit_price": 2000.00,
                }
            ],
        },
        headers=manager_headers,
    ).json()
    order_id = order["id"]

    # 1. Advance PENDING -> CONFIRMED
    res_conf = client.patch(
        f"/api/v1/sales/orders/{order_id}/status",
        json={"status": "CONFIRMED"},
        headers=manager_headers,
    )
    assert res_conf.status_code == 200

    # 2. Advance CONFIRMED -> SHIPPED
    res_ship = client.patch(
        f"/api/v1/sales/orders/{order_id}/status",
        json={"status": "SHIPPED"},
        headers=manager_headers,
    )
    assert res_ship.status_code == 200
    assert res_ship.json()["status"] == "SHIPPED"

    # 3. Attempt SHIPPED -> CANCELLED (Strictly forbidden!)
    res_cancel_shipped = client.patch(
        f"/api/v1/sales/orders/{order_id}/status",
        json={"status": "CANCELLED"},
        headers=manager_headers,
    )
    assert res_cancel_shipped.status_code == 400
    assert (
        "Invalid status transition from 'SHIPPED' to 'CANCELLED'"
        in res_cancel_shipped.json()["detail"]
    )
    assert "Allowed transitions: ['DELIVERED']" in res_cancel_shipped.json()["detail"]

    # 4. Advance SHIPPED -> DELIVERED
    res_del = client.patch(
        f"/api/v1/sales/orders/{order_id}/status",
        json={"status": "DELIVERED"},
        headers=manager_headers,
    )
    assert res_del.status_code == 200
    assert res_del.json()["status"] == "DELIVERED"

    # 5. Attempt DELIVERED -> CANCELLED (Terminal state, strictly forbidden!)
    res_cancel_del = client.patch(
        f"/api/v1/sales/orders/{order_id}/status",
        json={"status": "CANCELLED"},
        headers=manager_headers,
    )
    assert res_cancel_del.status_code == 400
    assert "Invalid status transition" in res_cancel_del.json()["detail"]

    # 6. Attempt DELIVERED -> SHIPPED / CONFIRMED (Terminal state, cannot regress)
    res_regress = client.patch(
        f"/api/v1/sales/orders/{order_id}/status",
        json={"status": "SHIPPED"},
        headers=manager_headers,
    )
    assert res_regress.status_code == 400
