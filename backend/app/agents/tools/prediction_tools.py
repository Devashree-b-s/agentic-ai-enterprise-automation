"""AI agent tools for Predictive Analytics, Sales Forecasting, and Inventory Risk."""

import logging
from typing import Any

from sqlalchemy.orm import Session

from app.agents.tools.base import rbac_tool
from app.models.user import User, UserRole
from app.services.prediction_service import prediction_service

logger = logging.getLogger("app.agents.tools.prediction")


@rbac_tool(UserRole.ADMIN, UserRole.MANAGER, UserRole.EMPLOYEE, tool_name="get_sales_revenue_forecast")
def get_sales_revenue_forecast(
    db: Session,
    current_user: User,
) -> dict[str, Any]:
    """Forecast sales revenue for the next 3 months using time-series modeling with baseline comparisons.

    Args:
        db: Active SQLAlchemy database session.
        current_user: Authenticated user making the query.
    """
    res = prediction_service.get_sales_forecast(db)
    return {
        "selected_forecasting_model": res.selected_model,
        "projected_growth_rate_percent": res.growth_rate_percent,
        "next_3_months_forecast": [
            {
                "month": fp.month,
                "projected_revenue": fp.predicted_revenue,
                "confidence_lower_bound": fp.lower_bound,
                "confidence_upper_bound": fp.upper_bound,
                "trend": fp.trend_direction,
            }
            for fp in res.forecast_next_3_months
        ],
        "recent_historical_trend": [
            {"month": hp.month, "revenue": hp.revenue, "units": hp.units_sold}
            for hp in res.historical_data[-3:]
        ],
        "model_performance_evaluation": [
            {"model": m.model_name, "rmse": m.rmse, "mae": m.mae, "mape": f"{m.mape_percent}%", "best": m.is_best_model}
            for m in res.model_evaluations
        ],
        "methodology": res.methodology_notes,
        "limitations": res.limitations_disclosure,
    }


@rbac_tool(UserRole.ADMIN, UserRole.MANAGER, UserRole.EMPLOYEE, tool_name="get_product_demand_predictions")
def get_product_demand_predictions(
    db: Session,
    current_user: User,
) -> dict[str, Any]:
    """Analyze product-level demand velocity, projected monthly unit demand, and increasing/decreasing trends.

    Args:
        db: Active SQLAlchemy database session.
        current_user: Authenticated user making the query.
    """
    res = prediction_service.get_product_demand(db)
    return {
        "total_catalog_products": res.total_products_analyzed,
        "top_demand_products": [
            {
                "sku": p.sku,
                "name": p.product_name,
                "projected_monthly_demand": p.projected_monthly_demand,
                "trend": p.trend_direction,
                "trend_percentage": f"{p.trend_percentage}%",
            }
            for p in res.top_demanded_products[:5]
        ],
        "products_with_increasing_demand": [
            {
                "sku": p.sku,
                "name": p.product_name,
                "projected_monthly_demand": p.projected_monthly_demand,
                "growth_percentage": f"+{p.trend_percentage}%",
            }
            for p in res.increasing_demand_products[:5]
        ],
        "products_with_decreasing_demand": [
            {
                "sku": p.sku,
                "name": p.product_name,
                "projected_monthly_demand": p.projected_monthly_demand,
                "decline_percentage": f"{p.trend_percentage}%",
            }
            for p in res.decreasing_demand_products[:5]
        ],
    }


@rbac_tool(UserRole.ADMIN, UserRole.MANAGER, UserRole.EMPLOYEE, tool_name="get_inventory_shortage_risks")
def get_inventory_shortage_risks(
    db: Session,
    current_user: User,
) -> dict[str, Any]:
    """Evaluate warehouse stock against forecasted demand velocity to identify stockout risks and replenishment suggestions.

    Args:
        db: Active SQLAlchemy database session.
        current_user: Authenticated user making the query.
    """
    res = prediction_service.get_inventory_risk(db)
    return {
        "critical_risk_count": res.critical_risk_count,
        "moderate_risk_count": res.moderate_risk_count,
        "healthy_count": res.healthy_count,
        "urgent_replenishment_priorities": [
            {
                "sku": p.sku,
                "name": p.product_name,
                "risk_level": p.shortage_risk_level,
                "on_hand": p.quantity_on_hand,
                "on_order": p.quantity_on_order,
                "safety_stock": p.safety_stock,
                "days_of_stock_remaining": p.days_of_stock_remaining,
                "suggested_replenishment_quantity": p.suggested_replenishment_quantity,
                "risk_reason": p.risk_reason,
            }
            for p in res.high_priority_replenishments[:8]
        ],
        "action_notice": res.action_notice,
    }
