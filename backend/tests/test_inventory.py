"""Comprehensive automated test suite for the Inventory Management module and Sales integration."""

from pathlib import Path

from fastapi.testclient import TestClient

# ============================================================================
# Product Catalog Tests
# ============================================================================


def test_create_product_success(client: TestClient, manager_headers: dict[str, str]):
    """Test creating a new product returns 201, creates catalog entry, and initial movement."""
    payload = {
        "sku": "SKU-UNIT-001",
        "name": "Precision Titanium Bolt",
        "description": "High tensile aerospace grade bolt",
        "quantity_on_hand": 100,
        "quantity_on_order": 50,
        "lead_time_days": 14,
        "safety_stock": 20,
        "target_stock": 200,
        "is_active": True,
    }
    response = client.post(
        "/api/v1/inventory/products", json=payload, headers=manager_headers
    )
    assert response.status_code == 201
    data = response.json()

    assert data["id"] is not None
    assert data["sku"] == "SKU-UNIT-001"
    assert data["name"] == "Precision Titanium Bolt"
    assert data["quantity_on_hand"] == 100
    assert data["quantity_on_order"] == 50
    assert data["safety_stock"] == 20
    assert data["target_stock"] == 200
    assert data["is_active"] is True

    # Verify initial stock movement was automatically recorded
    mov_res = client.get(
        f"/api/v1/inventory/products/{data['id']}/movements", headers=manager_headers
    )
    assert mov_res.status_code == 200
    movements = mov_res.json()
    assert len(movements) == 1
    assert movements[0]["movement_type"] == "IN"
    assert movements[0]["quantity"] == 100
    assert movements[0]["previous_quantity"] == 0
    assert movements[0]["new_quantity"] == 100


def test_create_product_duplicate_sku_rejected(
    client: TestClient, manager_headers: dict[str, str]
):
    """Test that creating a product with an existing SKU returns 409 Conflict."""
    payload = {
        "sku": "SKU-DUP-TEST",
        "name": "Initial Product",
        "quantity_on_hand": 10,
    }
    res1 = client.post(
        "/api/v1/inventory/products", json=payload, headers=manager_headers
    )
    assert res1.status_code == 201

    # Attempt second insertion with same SKU
    res2 = client.post(
        "/api/v1/inventory/products", json=payload, headers=manager_headers
    )
    assert res2.status_code == 409
    assert "already exists" in res2.json()["detail"]


def test_create_product_negative_quantities_rejected(
    client: TestClient, manager_headers: dict[str, str]
):
    """Test validation errors for negative stock thresholds."""
    payload = {
        "sku": "SKU-NEG-TEST",
        "name": "Negative Tester",
        "quantity_on_hand": -10,
    }
    res = client.post(
        "/api/v1/inventory/products", json=payload, headers=manager_headers
    )
    assert res.status_code == 422


def test_list_and_search_products(client: TestClient, manager_headers: dict[str, str]):
    """Test product listing with text search and low-stock filter."""
    # List all products
    res_all = client.get("/api/v1/inventory/products", headers=manager_headers)
    assert res_all.status_code == 200
    all_prods = res_all.json()
    assert len(all_prods) >= 30  # 30 from inventory.csv + seeded test products

    # Search by SKU
    res_search_sku = client.get(
        "/api/v1/inventory/products?search=SKU-GFT-001", headers=manager_headers
    )
    assert res_search_sku.status_code == 200
    sku_matches = res_search_sku.json()
    assert len(sku_matches) == 1
    assert sku_matches[0]["sku"] == "SKU-GFT-001"

    # Search by Product Name
    res_search_name = client.get(
        "/api/v1/inventory/products?search=Ceramic", headers=manager_headers
    )
    assert res_search_name.status_code == 200
    name_matches = res_search_name.json()
    assert len(name_matches) >= 1
    assert any("Ceramic" in p["name"] for p in name_matches)

    # Filter by low-stock
    res_low = client.get(
        "/api/v1/inventory/products?is_low_stock=true", headers=manager_headers
    )
    assert res_low.status_code == 200
    low_prods = res_low.json()
    for p in low_prods:
        assert p["quantity_on_hand"] <= p["safety_stock"]


def test_get_and_update_product(client: TestClient, manager_headers: dict[str, str]):
    """Test retrieving and updating product catalog details."""
    create_res = client.post(
        "/api/v1/inventory/products",
        json={"sku": "SKU-UPDATE-ME", "name": "Old Name", "safety_stock": 10},
        headers=manager_headers,
    )
    prod_id = create_res.json()["id"]

    # 1. Get by ID
    get_res = client.get(
        f"/api/v1/inventory/products/{prod_id}", headers=manager_headers
    )
    assert get_res.status_code == 200
    assert get_res.json()["name"] == "Old Name"

    # 2. Update metadata
    update_res = client.put(
        f"/api/v1/inventory/products/{prod_id}",
        json={
            "name": "New Modern Name",
            "safety_stock": 25,
            "description": "Updated description",
        },
        headers=manager_headers,
    )
    assert update_res.status_code == 200
    updated_data = update_res.json()
    assert updated_data["name"] == "New Modern Name"
    assert updated_data["safety_stock"] == 25
    assert updated_data["description"] == "Updated description"

    # 3. Non-existent product ID
    assert (
        client.get(
            "/api/v1/inventory/products/99999", headers=manager_headers
        ).status_code
        == 404
    )
    assert (
        client.put(
            "/api/v1/inventory/products/99999",
            json={"name": "X"},
            headers=manager_headers,
        ).status_code
        == 404
    )


def test_delete_product_safe_and_restricted(
    client: TestClient, manager_headers: dict[str, str], admin_headers: dict[str, str]
):
    """Test that unreferenced products can be deleted, but products with audit trails are protected."""
    # 1. Product with initial stock 0 (no initial StockMovement)
    zero_stock_prod = client.post(
        "/api/v1/inventory/products",
        json={"sku": "SKU-EMPTY-001", "name": "Zero Stock", "quantity_on_hand": 0},
        headers=manager_headers,
    ).json()
    del_res = client.delete(
        f"/api/v1/inventory/products/{zero_stock_prod['id']}", headers=admin_headers
    )
    assert del_res.status_code == 204

    # 2. Product with initial stock > 0 has an immutable StockMovement -> deletion must be rejected!
    stocked_prod = client.post(
        "/api/v1/inventory/products",
        json={
            "sku": "SKU-HAS-AUDIT",
            "name": "Has Audit Record",
            "quantity_on_hand": 50,
        },
        headers=manager_headers,
    ).json()
    blocked_del = client.delete(
        f"/api/v1/inventory/products/{stocked_prod['id']}", headers=admin_headers
    )
    assert blocked_del.status_code == 400
    assert "Deactivate the product instead" in blocked_del.json()["detail"]


# ============================================================================
# Stock Operation Tests (In, Out, Adjust)
# ============================================================================


def test_stock_in_operation(client: TestClient, manager_headers: dict[str, str]):
    """Test receiving inventory via stock-in endpoint."""
    prod = client.post(
        "/api/v1/inventory/products",
        json={"sku": "SKU-STOCKIN-01", "name": "Stock In Test", "quantity_on_hand": 10},
        headers=manager_headers,
    ).json()
    prod_id = prod["id"]

    # Stock In +40
    res = client.post(
        "/api/v1/inventory/stock/in",
        json={
            "product_id": prod_id,
            "quantity": 40,
            "reason": "Shipment from Supplier ABC",
            "reference": "PO-9901",
        },
        headers=manager_headers,
    )
    assert res.status_code == 201
    movement = res.json()
    assert movement["movement_type"] == "IN"
    assert movement["quantity"] == 40
    assert movement["previous_quantity"] == 10
    assert movement["new_quantity"] == 50
    assert movement["reference"] == "PO-9901"

    # Verify product on hand updated
    updated_prod = client.get(
        f"/api/v1/inventory/products/{prod_id}", headers=manager_headers
    ).json()
    assert updated_prod["quantity_on_hand"] == 50


def test_stock_out_success_and_insufficient_stock_rejection(
    client: TestClient, manager_headers: dict[str, str]
):
    """Test deducting inventory and rejecting overselling."""
    prod = client.post(
        "/api/v1/inventory/products",
        json={
            "sku": "SKU-STOCKOUT-01",
            "name": "Stock Out Test",
            "quantity_on_hand": 30,
        },
        headers=manager_headers,
    ).json()
    prod_id = prod["id"]

    # 1. Valid deduction: 30 - 10 = 20
    res_valid = client.post(
        "/api/v1/inventory/stock/out",
        json={"product_id": prod_id, "quantity": 10, "reason": "Internal R&D use"},
        headers=manager_headers,
    )
    assert res_valid.status_code == 201
    mov = res_valid.json()
    assert mov["movement_type"] == "OUT"
    assert mov["quantity"] == 10
    assert mov["previous_quantity"] == 30
    assert mov["new_quantity"] == 20

    # 2. Overselling deduction: Available 20, Request 25 -> must fail with 400
    res_oversell = client.post(
        "/api/v1/inventory/stock/out",
        json={"product_id": prod_id, "quantity": 25},
        headers=manager_headers,
    )
    assert res_oversell.status_code == 400
    assert "Insufficient stock" in res_oversell.json()["detail"]

    # Verify quantity remained 20
    check_prod = client.get(
        f"/api/v1/inventory/products/{prod_id}", headers=manager_headers
    ).json()
    assert check_prod["quantity_on_hand"] == 20


def test_stock_adjust_both_directions(
    client: TestClient, manager_headers: dict[str, str]
):
    """Test physical stock reconciliation counts (increasing, decreasing, and duplicate rejection)."""
    prod = client.post(
        "/api/v1/inventory/products",
        json={
            "sku": "SKU-ADJUST-01",
            "name": "Stocktake Product",
            "quantity_on_hand": 50,
        },
        headers=manager_headers,
    ).json()
    prod_id = prod["id"]

    # 1. Upward adjustment: 50 -> 75 (diff: 25)
    res_up = client.post(
        "/api/v1/inventory/stock/adjust",
        json={
            "product_id": prod_id,
            "new_quantity": 75,
            "reason": "Found unrecorded carton",
        },
        headers=manager_headers,
    )
    assert res_up.status_code == 201
    mov_up = res_up.json()
    assert mov_up["movement_type"] == "ADJUSTMENT"
    assert mov_up["quantity"] == 25
    assert mov_up["previous_quantity"] == 50
    assert mov_up["new_quantity"] == 75

    # 2. Downward adjustment: 75 -> 40 (diff: 35)
    res_down = client.post(
        "/api/v1/inventory/stock/adjust",
        json={
            "product_id": prod_id,
            "new_quantity": 40,
            "reason": "Shrinkage write-off",
        },
        headers=manager_headers,
    )
    assert res_down.status_code == 201
    mov_down = res_down.json()
    assert mov_down["movement_type"] == "ADJUSTMENT"
    assert mov_down["quantity"] == 35
    assert mov_down["previous_quantity"] == 75
    assert mov_down["new_quantity"] == 40

    # 3. Redundant adjustment: 40 -> 40 (rejected with 400)
    res_same = client.post(
        "/api/v1/inventory/stock/adjust",
        json={"product_id": prod_id, "new_quantity": 40},
        headers=manager_headers,
    )
    assert res_same.status_code == 400
    assert "already 40" in res_same.json()["detail"]

    # 4. Negative adjustment count rejected (422)
    res_neg = client.post(
        "/api/v1/inventory/stock/adjust",
        json={"product_id": prod_id, "new_quantity": -5},
        headers=manager_headers,
    )
    assert res_neg.status_code == 422


# ============================================================================
# Low-Stock Alerts & Inventory Summary Reports
# ============================================================================


def test_low_stock_alerts_and_replenishment_quantities(
    client: TestClient, manager_headers: dict[str, str]
):
    """Test low stock alert identification and replenishment quantity calculation."""
    # Create product 1: On hand 5 <= safety 10 -> Low stock! Target: 100, on_order: 20
    # Replenishment = max(0, 100 - 5 - 20) = 75
    p1 = client.post(
        "/api/v1/inventory/products",
        json={
            "sku": "SKU-ALERT-LOW",
            "name": "Low Stock Widget",
            "quantity_on_hand": 5,
            "quantity_on_order": 20,
            "safety_stock": 10,
            "target_stock": 100,
        },
        headers=manager_headers,
    ).json()

    # Create product 2: On hand 0 <= safety 15 -> OUT OF STOCK! Target: 50, on_order: 0
    # Replenishment = max(0, 50 - 0 - 0) = 50
    p2 = client.post(
        "/api/v1/inventory/products",
        json={
            "sku": "SKU-ALERT-OUT",
            "name": "Out of Stock Gadget",
            "quantity_on_hand": 0,
            "quantity_on_order": 0,
            "safety_stock": 15,
            "target_stock": 50,
        },
        headers=manager_headers,
    ).json()

    res = client.get("/api/v1/inventory/alerts/low-stock", headers=manager_headers)
    assert res.status_code == 200
    report = res.json()

    assert report["total_low_stock"] >= 2
    item1 = next(i for i in report["items"] if i["product_id"] == p1["id"])
    assert item1["status"] == "LOW_STOCK"
    assert item1["replenishment_quantity"] == 75

    item2 = next(i for i in report["items"] if i["product_id"] == p2["id"])
    assert item2["status"] == "OUT_OF_STOCK"
    assert item2["replenishment_quantity"] == 50


def test_inventory_summary_report(client: TestClient, manager_headers: dict[str, str]):
    """Test high-level inventory metrics and non-availability of monetary valuation."""
    res = client.get("/api/v1/inventory/reports/summary", headers=manager_headers)
    assert res.status_code == 200
    summary = res.json()

    assert summary["total_products"] >= 30
    assert summary["total_units_on_hand"] > 0
    assert summary["total_units_on_order"] > 0
    assert summary["monetary_valuation_available"] is False
    assert "cost prices are not" in summary["notes"]


# ============================================================================
# Repeatable CSV Import Tests
# ============================================================================


def test_csv_import_repeatable_and_preserves_stock(
    client: TestClient, admin_headers: dict[str, str], manager_headers: dict[str, str]
):
    """Test that CSV import creates all 30 products and does not overwrite modified operational stock."""
    # 1. Trigger CSV import
    res1 = client.post("/api/v1/inventory/import/csv", headers=admin_headers)
    assert res1.status_code == 200
    summary1 = res1.json()
    assert summary1["total_records_processed"] == 30
    assert len(summary1["errors"]) == 0

    # 2. Modify stock for SKU-GFT-001 (initially 93) by deducting 13 units
    prod = client.get(
        "/api/v1/inventory/products?search=SKU-GFT-001", headers=manager_headers
    ).json()[0]
    client.post(
        "/api/v1/inventory/stock/out",
        json={
            "product_id": prod["id"],
            "quantity": 13,
            "reason": "Operational sale test",
        },
        headers=manager_headers,
    )
    # New on hand should be 93 - 13 = 80
    modified_prod = client.get(
        f"/api/v1/inventory/products/{prod['id']}", headers=manager_headers
    ).json()
    assert modified_prod["quantity_on_hand"] == 80

    # 3. Run CSV import again: Operational stock 80 MUST NOT be overwritten back to 93!
    res2 = client.post("/api/v1/inventory/import/csv", headers=admin_headers)
    assert res2.status_code == 200
    summary2 = res2.json()
    assert summary2["new_products_created"] == 0
    assert summary2["existing_products_preserved"] == 30

    check_prod = client.get(
        f"/api/v1/inventory/products/{prod['id']}", headers=manager_headers
    ).json()
    assert check_prod["quantity_on_hand"] == 80  # Preserved operational stock!


# ============================================================================
# Sales & Inventory Transactional Integration Tests
# ============================================================================


def test_sales_inventory_lifecycle_stock_deduction_and_restoration(
    client: TestClient, manager_headers: dict[str, str]
):
    """Test full integration: PENDING no deduction, CONFIRMED deducts, CANCELLED restores."""
    # 1. Setup Customer & Product with 100 units
    cust = client.post(
        "/api/v1/sales/customers",
        json={
            "customer_code": "CUST-INT-01",
            "name": "Integration Client",
            "email": "int@client.com",
        },
        headers=manager_headers,
    ).json()

    prod = client.post(
        "/api/v1/inventory/products",
        json={
            "sku": "SKU-INT-PROD-01",
            "name": "Integration Widget",
            "quantity_on_hand": 100,
        },
        headers=manager_headers,
    ).json()
    prod_id = prod["id"]

    # 2. Create Order in PENDING status: 25 units
    order = client.post(
        "/api/v1/sales/orders",
        json={
            "customer_id": cust["id"],
            "items": [
                {
                    "product_id": prod_id,
                    "product_name": "Integration Widget",
                    "quantity": 25,
                    "unit_price": 50.00,
                }
            ],
        },
        headers=manager_headers,
    ).json()
    order_id = order["id"]
    assert order["status"] == "PENDING"

    # Verify PENDING status did NOT deduct stock
    prod_pending = client.get(
        f"/api/v1/inventory/products/{prod_id}", headers=manager_headers
    ).json()
    assert prod_pending["quantity_on_hand"] == 100

    # 3. Confirm Order: PENDING -> CONFIRMED
    res_conf = client.patch(
        f"/api/v1/sales/orders/{order_id}/status",
        json={"status": "CONFIRMED"},
        headers=manager_headers,
    )
    assert res_conf.status_code == 200
    assert res_conf.json()["status"] == "CONFIRMED"

    # Verify stock deducted: 100 - 25 = 75
    prod_conf = client.get(
        f"/api/v1/inventory/products/{prod_id}", headers=manager_headers
    ).json()
    assert prod_conf["quantity_on_hand"] == 75

    # Verify StockMovement OUT was logged with order number reference
    movs = client.get(
        f"/api/v1/inventory/products/{prod_id}/movements", headers=manager_headers
    ).json()
    latest_mov = movs[0]
    assert latest_mov["movement_type"] == "OUT"
    assert latest_mov["quantity"] == 25
    assert latest_mov["previous_quantity"] == 100
    assert latest_mov["new_quantity"] == 75
    assert latest_mov["reference"] == order["order_number"]

    # 4. Cancel Order: CONFIRMED -> CANCELLED
    res_cancel = client.patch(
        f"/api/v1/sales/orders/{order_id}/status",
        json={"status": "CANCELLED"},
        headers=manager_headers,
    )
    assert res_cancel.status_code == 200
    assert res_cancel.json()["status"] == "CANCELLED"

    # Verify stock restored: 75 + 25 = 100
    prod_restored = client.get(
        f"/api/v1/inventory/products/{prod_id}", headers=manager_headers
    ).json()
    assert prod_restored["quantity_on_hand"] == 100

    # Verify StockMovement IN was logged for cancellation
    movs_after_cancel = client.get(
        f"/api/v1/inventory/products/{prod_id}/movements", headers=manager_headers
    ).json()
    assert movs_after_cancel[0]["movement_type"] == "IN"
    assert movs_after_cancel[0]["quantity"] == 25
    assert movs_after_cancel[0]["new_quantity"] == 100


def test_sales_inventory_insufficient_stock_aborts_confirmation_with_rollback(
    client: TestClient, manager_headers: dict[str, str]
):
    """Test atomic multi-item rollback: if one item lacks stock, confirmation fails and NO stock is deducted."""
    cust = client.post(
        "/api/v1/sales/customers",
        json={
            "customer_code": "CUST-ROLLBACK-01",
            "name": "Rollback Client",
            "email": "rollback@client.com",
        },
        headers=manager_headers,
    ).json()

    # Product A: 50 on hand
    prod_a = client.post(
        "/api/v1/inventory/products",
        json={"sku": "SKU-ROLLBACK-A", "name": "Product A", "quantity_on_hand": 50},
        headers=manager_headers,
    ).json()

    # Product B: only 5 on hand
    prod_b = client.post(
        "/api/v1/inventory/products",
        json={"sku": "SKU-ROLLBACK-B", "name": "Product B", "quantity_on_hand": 5},
        headers=manager_headers,
    ).json()

    # Order requires 10 units of A (sufficient) and 20 units of B (INSUFFICIENT)
    order = client.post(
        "/api/v1/sales/orders",
        json={
            "customer_id": cust["id"],
            "items": [
                {
                    "product_id": prod_a["id"],
                    "product_name": "Product A",
                    "quantity": 10,
                    "unit_price": 20.00,
                },
                {
                    "product_id": prod_b["id"],
                    "product_name": "Product B",
                    "quantity": 20,
                    "unit_price": 30.00,
                },
            ],
        },
        headers=manager_headers,
    ).json()
    order_id = order["id"]

    # Attempt confirmation -> must fail with 400
    res_conf = client.patch(
        f"/api/v1/sales/orders/{order_id}/status",
        json={"status": "CONFIRMED"},
        headers=manager_headers,
    )
    assert res_conf.status_code == 400
    assert "insufficient stock" in res_conf.json()["detail"].lower()
    assert "Product B" in res_conf.json()["detail"]

    # Crucial assertion: Product A's stock was rolled back and NOT deducted!
    check_a = client.get(
        f"/api/v1/inventory/products/{prod_a['id']}", headers=manager_headers
    ).json()
    assert check_a["quantity_on_hand"] == 50

    check_b = client.get(
        f"/api/v1/inventory/products/{prod_b['id']}", headers=manager_headers
    ).json()
    assert check_b["quantity_on_hand"] == 5

    # Order remained in PENDING status
    order_check = client.get(
        f"/api/v1/sales/orders/{order_id}", headers=manager_headers
    ).json()
    assert order_check["status"] == "PENDING"


def test_sales_inventory_shipped_order_cancellation_prevented(
    client: TestClient, manager_headers: dict[str, str]
):
    """Test that after an order is SHIPPED, cancellation is blocked and stock remains deducted."""
    cust = client.post(
        "/api/v1/sales/customers",
        json={
            "customer_code": "CUST-SHIPPED-INT",
            "name": "Shipped Client",
            "email": "ship@client.com",
        },
        headers=manager_headers,
    ).json()

    prod = client.post(
        "/api/v1/inventory/products",
        json={"sku": "SKU-SHIP-INT", "name": "Shipped Product", "quantity_on_hand": 80},
        headers=manager_headers,
    ).json()

    order = client.post(
        "/api/v1/sales/orders",
        json={
            "customer_id": cust["id"],
            "items": [
                {
                    "product_id": prod["id"],
                    "product_name": "Shipped Product",
                    "quantity": 30,
                    "unit_price": 40.00,
                }
            ],
        },
        headers=manager_headers,
    ).json()
    order_id = order["id"]

    # PENDING -> CONFIRMED (80 - 30 = 50)
    client.patch(
        f"/api/v1/sales/orders/{order_id}/status",
        json={"status": "CONFIRMED"},
        headers=manager_headers,
    )

    # CONFIRMED -> SHIPPED
    client.patch(
        f"/api/v1/sales/orders/{order_id}/status",
        json={"status": "SHIPPED"},
        headers=manager_headers,
    )

    # Attempt to cancel SHIPPED order -> must fail with 400
    res_bad_cancel = client.patch(
        f"/api/v1/sales/orders/{order_id}/status",
        json={"status": "CANCELLED"},
        headers=manager_headers,
    )
    assert res_bad_cancel.status_code == 400
    assert "Invalid status transition" in res_bad_cancel.json()["detail"]

    # Stock must remain at 50
    prod_check = client.get(
        f"/api/v1/inventory/products/{prod['id']}", headers=manager_headers
    ).json()
    assert prod_check["quantity_on_hand"] == 50


# ============================================================================
# RBAC Security Tests on Inventory Endpoints
# ============================================================================


def test_inventory_rbac_permissions(
    client: TestClient,
    employee_user_with_headers: tuple,
    manager_headers: dict[str, str],
):
    """Test RBAC: Employee can view products and alerts, but cannot mutate products or stock."""
    _, _, emp_headers = employee_user_with_headers

    # 1. Employee CAN view products and low-stock alerts (200 OK)
    assert (
        client.get("/api/v1/inventory/products", headers=emp_headers).status_code == 200
    )
    assert (
        client.get(
            "/api/v1/inventory/alerts/low-stock", headers=emp_headers
        ).status_code
        == 200
    )

    # 2. Employee CANNOT create a product (403 Forbidden)
    res_create = client.post(
        "/api/v1/inventory/products",
        json={
            "sku": "SKU-EMP-FORBIDDEN",
            "name": "Illegal Widget",
            "quantity_on_hand": 10,
        },
        headers=emp_headers,
    )
    assert res_create.status_code == 403

    # 3. Employee CANNOT perform stock in, out, or adjust (403 Forbidden)
    assert (
        client.post(
            "/api/v1/inventory/stock/in",
            json={"product_id": 1, "quantity": 5},
            headers=emp_headers,
        ).status_code
        == 403
    )
    assert (
        client.post(
            "/api/v1/inventory/stock/out",
            json={"product_id": 1, "quantity": 5},
            headers=emp_headers,
        ).status_code
        == 403
    )
    assert (
        client.post(
            "/api/v1/inventory/stock/adjust",
            json={"product_id": 1, "new_quantity": 5},
            headers=emp_headers,
        ).status_code
        == 403
    )

    # 4. Employee CANNOT view executive summary report (403 Forbidden)
    assert (
        client.get("/api/v1/inventory/reports/summary", headers=emp_headers).status_code
        == 403
    )

    # 5. Manager CAN view executive summary report (200 OK)
    assert (
        client.get(
            "/api/v1/inventory/reports/summary", headers=manager_headers
        ).status_code
        == 200
    )

    # 6. Unauthenticated requests are rejected (401 Unauthorized)
    assert client.get("/api/v1/inventory/products").status_code == 401
    assert client.get("/api/v1/inventory/alerts/low-stock").status_code == 401
    assert (
        client.post(
            "/api/v1/inventory/stock/in", json={"product_id": 1, "quantity": 5}
        ).status_code
        == 401
    )


def test_concurrent_order_confirmations_prevent_overselling(tmp_path: Path):
    """Test that concurrent confirmation requests on insufficient combined stock prevent overselling.

    Uses a file-backed SQLite database with timeout to simulate separate connections,
    demonstrating that conditional atomic database updates prevent race conditions and partial stock movements.
    """
    import concurrent.futures

    from app.core.security import create_access_token, hash_password
    from app.db.base import Base
    from app.db.session import get_db
    from app.main import app
    from app.models.user import User, UserRole
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    test_db = tmp_path / "test_concur.db"
    file_engine = create_engine(
        f"sqlite:///{test_db}",
        connect_args={"check_same_thread": False, "timeout": 20},
    )
    FileSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=file_engine)
    Base.metadata.create_all(bind=file_engine)

    def file_override_get_db():
        db = FileSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = file_override_get_db

    try:
        # Create manager user
        with FileSessionLocal() as db:
            mgr = User(
                email="concur_mgr@enterprise.com",
                hashed_password=hash_password("MgrSecure123!"),
                role=UserRole.MANAGER.value,
                is_active=True,
            )
            db.add(mgr)
            db.commit()
            db.refresh(mgr)
            token = create_access_token({"sub": str(mgr.id), "role": mgr.role})
            headers = {"Authorization": f"Bearer {token}"}

        c1 = TestClient(app)
        c2 = TestClient(app)

        # 1. Create customer
        cust = c1.post(
            "/api/v1/sales/customers",
            json={
                "customer_code": "CUST-CONCUR",
                "name": "Concur Client",
                "email": "concur@client.com",
            },
            headers=headers,
        ).json()

        # 2. Create product with initial stock = 15
        prod = c1.post(
            "/api/v1/inventory/products",
            json={
                "sku": "SKU-CONCUR-RACE",
                "name": "Race Product",
                "quantity_on_hand": 15,
            },
            headers=headers,
        ).json()
        prod_id = prod["id"]

        # 3. Create two pending orders, each demanding 10 units (total 20 > 15 available)
        o1 = c1.post(
            "/api/v1/sales/orders",
            json={
                "customer_id": cust["id"],
                "items": [
                    {
                        "product_id": prod_id,
                        "product_name": "Race Product",
                        "quantity": 10,
                        "unit_price": 50.0,
                    }
                ],
            },
            headers=headers,
        ).json()

        o2 = c1.post(
            "/api/v1/sales/orders",
            json={
                "customer_id": cust["id"],
                "items": [
                    {
                        "product_id": prod_id,
                        "product_name": "Race Product",
                        "quantity": 10,
                        "unit_price": 50.0,
                    }
                ],
            },
            headers=headers,
        ).json()

        def confirm(client_inst: TestClient, order_id: int):
            return client_inst.patch(
                f"/api/v1/sales/orders/{order_id}/status",
                json={"status": "CONFIRMED"},
                headers=headers,
            )

        # 4. Attempt simultaneous confirmation
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            f1 = executor.submit(confirm, c1, o1["id"])
            f2 = executor.submit(confirm, c2, o2["id"])
            res1 = f1.result()
            res2 = f2.result()

        status_codes = sorted([res1.status_code, res2.status_code])
        # Exactly one order succeeds (200) and the other is rejected (400)
        assert status_codes == [200, 400]

        # 5. Check product inventory - stock must be exactly 5, NEVER negative
        prod_check = c1.get(
            f"/api/v1/inventory/products/{prod_id}", headers=headers
        ).json()
        assert prod_check["quantity_on_hand"] == 5

        # 6. Verify movement audit trail: initial CATALOG-INIT (15) + exactly 1 OUT movement (10)
        movs = c1.get(
            f"/api/v1/inventory/products/{prod_id}/movements", headers=headers
        ).json()
        out_movs = [m for m in movs if m["movement_type"] == "OUT"]
        assert len(out_movs) == 1
        assert out_movs[0]["quantity"] == 10
        assert out_movs[0]["previous_quantity"] == 15
        assert out_movs[0]["new_quantity"] == 5

    finally:
        app.dependency_overrides.clear()
        file_engine.dispose()
