"""Tests for Phase 6: Predictive Analytics, Business Forecasting, and Inventory Shortage Risks."""

from datetime import date
from decimal import Decimal

import pytest
from app.models.historical_sale import HistoricalSale
from app.models.inventory import Product
from app.services.prediction_service import prediction_service
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session


@pytest.fixture(autouse=True)
def seeded_sales_data(db_session: Session):
    """Seed 6 months of historical sales data and catalog products for testing."""
    # Ensure test products exist
    products_to_seed = [
        ("SKU-GFT-030", "Rustic Bunting", 3, 0, 5, 15),
        ("SKU-GFT-001", "Ceramic Photo Frame", 93, 175, 16, 169),
        ("SKU-GFT-006", "Vintage Tea Set", 44, 0, 30, 169),
        ("SKU-GFT-017", "Wooden Mug", 16, 0, 5, 32),
        ("SKU-GFT-023", "Luxury Cushion", 120, 50, 20, 200),
    ]
    for sku, name, on_hand, on_order, safety, target in products_to_seed:
        p = db_session.scalar(select(Product).where(Product.sku == sku))
        if not p:
            p = Product(
                sku=sku,
                name=name,
                quantity_on_hand=on_hand,
                quantity_on_order=on_order,
                safety_stock=safety,
                target_stock=target,
                is_active=True,
            )
            db_session.add(p)
    db_session.commit()

    # Seed 6 months of historical sales (May to October 2026)
    sales = []
    monthly_data = [
        ("2026-05-15", "104171.00", 5345),
        ("2026-06-15", "116439.84", 6009),
        ("2026-07-15", "117200.26", 6041),
        ("2026-08-15", "125264.30", 6385),
        ("2026-09-15", "112335.10", 5728),
        ("2026-10-15", "119355.80", 6063),
    ]
    for i, (dt_str, rev_str, qty) in enumerate(monthly_data, 1):
        d = date.fromisoformat(dt_str)
        # Add primary volume row
        sales.append(
            HistoricalSale(
                order_id=f"ORD-HIST-M{i:02d}-01",
                sku="SKU-GFT-030",
                order_date=d,
                quantity=40 if i != 6 else 4,
                unit_price=Decimal("10.00"),
                subtotal=Decimal("400.00"),
                order_status="COMPLETED",
            )
        )
        sales.append(
            HistoricalSale(
                order_id=f"ORD-HIST-M{i:02d}-02",
                sku="SKU-GFT-023",
                order_date=d,
                quantity=450 + i * 10,
                unit_price=Decimal("20.00"),
                subtotal=Decimal(rev_str) - Decimal("400.00"),
                order_status="SHIPPED",
            )
        )
    db_session.add_all(sales)
    db_session.commit()


def test_sales_forecast_engine_and_time_split(db_session: Session):
    """Test out-of-sample time-based evaluation, model comparison, and 3-month forecast generation."""
    res = prediction_service.get_sales_forecast(db_session)

    # 1. Historical data integrity
    assert len(res.historical_data) >= 6
    months = [h.month for h in res.historical_data]
    assert months[:6] == ["2026-05", "2026-06", "2026-07", "2026-08", "2026-09", "2026-10"]

    # 2. 3-Month Out-of-sample forecast
    assert len(res.forecast_next_3_months) == 3
    f_months = [f.month for f in res.forecast_next_3_months]
    assert f_months == ["2026-11", "2026-12", "2027-01"]

    for fp in res.forecast_next_3_months:
        assert fp.predicted_revenue > 0
        assert fp.lower_bound <= fp.predicted_revenue <= fp.upper_bound
        assert fp.trend_direction in ["UPWARD", "DOWNWARD", "FLAT"]

    # 3. Time-based model evaluation comparison
    assert len(res.model_evaluations) >= 4
    model_names = [m.model_name for m in res.model_evaluations]
    assert any("Naive" in name for name in model_names)
    assert any("Moving Average" in name for name in model_names)
    assert any("Linear Trend" in name for name in model_names)
    assert any("Holt" in name for name in model_names)

    best_count = sum(1 for m in res.model_evaluations if m.is_best_model)
    assert best_count == 1

    # Verify metrics are non-negative and non-fabricated
    for m in res.model_evaluations:
        assert m.mae > 0
        assert m.rmse > 0
        assert m.mape_percent > 0

    assert res.selected_model != ""
    assert "limitations" in res.limitations_disclosure.lower() or "seasonality" in res.limitations_disclosure.lower()


def test_product_demand_predictions_and_trends(db_session: Session):
    """Test product-level demand velocity, projected demand, and increasing/decreasing trends."""
    res = prediction_service.get_product_demand(db_session)

    assert res.total_products_analyzed >= 2
    assert len(res.top_demanded_products) > 0

    # Top demand products should be sorted by volume
    top_units = [p.total_historical_units for p in res.top_demanded_products]
    assert top_units == sorted(top_units, reverse=True)

    # Verify items have trend classification
    for item in res.top_demanded_products:
        assert item.trend_direction in ["INCREASING", "DECREASING", "STABLE"]
        assert item.projected_monthly_demand > 0


def test_inventory_shortage_risk_evaluation(db_session: Session):
    """Test inventory shortage risk calculation combining stock, on-order, demand, and safety stock."""
    res = prediction_service.get_inventory_risk(db_session)

    assert res.total_products_evaluated >= 2
    assert res.critical_risk_count >= 1

    # SKU-GFT-030 (Rustic Bunting) has 3 units on hand with safety stock 5 -> MUST be flagged CRITICAL
    rustic = next((p for p in res.all_evaluated_products if p.sku == "SKU-GFT-030"), None)
    assert rustic is not None
    assert rustic.shortage_risk_level == "CRITICAL"
    assert rustic.suggested_replenishment_quantity > 0
    assert rustic.days_of_stock_remaining > 0

    # Verify action notice states Human-in-the-Loop approval is required
    assert "human-in-the-loop" in res.action_notice.lower() or "approval" in res.action_notice.lower()


def test_predictions_api_endpoints_authenticated(
    client: TestClient, admin_headers: dict[str, str]
):
    """Test all prediction API endpoints with valid authentication."""
    # 1. Sales forecast
    res_forecast = client.get("/api/v1/predictions/sales-forecast", headers=admin_headers)
    assert res_forecast.status_code == 200
    data_f = res_forecast.json()
    assert len(data_f["forecast_next_3_months"]) == 3

    # 2. Product demand
    res_demand = client.get("/api/v1/predictions/product-demand", headers=admin_headers)
    assert res_demand.status_code == 200
    data_d = res_demand.json()
    assert data_d["total_products_analyzed"] >= 2

    # 3. Inventory risk
    res_risk = client.get("/api/v1/predictions/inventory-risk", headers=admin_headers)
    assert res_risk.status_code == 200
    data_r = res_risk.json()
    assert data_r["critical_risk_count"] >= 1

    # 4. Model performance
    res_perf = client.get("/api/v1/predictions/model-performance", headers=admin_headers)
    assert res_perf.status_code == 200
    data_p = res_perf.json()
    assert len(data_p["models_evaluated"]) >= 4


def test_predictions_api_unauthenticated_rejected(client: TestClient):
    """Test that predictive endpoints reject unauthenticated access with 401."""
    res = client.get("/api/v1/predictions/sales-forecast")
    assert res.status_code == 401


def test_analytics_agent_predictive_chat_queries(
    client: TestClient, admin_headers: dict[str, str]
):
    """Test AI Decision Assistant answering predictive analytics and risk questions."""
    # 1. Revenue forecast query
    res_forecast = client.post(
        "/api/v1/agents/chat",
        json={"message": "What will our revenue look like over the next three months?"},
        headers=admin_headers,
    )
    assert res_forecast.status_code == 200
    data_f = res_forecast.json()
    assert "get_sales_revenue_forecast" in data_f["tools_used"]
    assert "forecast" in data_f["answer"].lower() or "revenue" in data_f["answer"].lower()

    # 2. Inventory shortage risk query
    res_risk = client.post(
        "/api/v1/agents/chat",
        json={"message": "Which products may run out of stock and what should we prioritize for replenishment?"},
        headers=admin_headers,
    )
    assert res_risk.status_code == 200
    data_r = res_risk.json()
    assert "get_inventory_shortage_risks" in data_r["tools_used"]
    assert "stock" in data_r["answer"].lower() or "rustic" in data_r["answer"].lower() or "risk" in data_r["answer"].lower()
