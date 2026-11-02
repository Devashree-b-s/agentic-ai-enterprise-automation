import logging
from typing import Any

from sqlalchemy.orm import Session

from app.agents.tools.base import rbac_tool
from app.models.user import User, UserRole
from app.services.analytics_service import analytics_service
from app.services.inventory_service import inventory_service

logger = logging.getLogger("app.agents.tools.inventory")


@rbac_tool(
    UserRole.ADMIN,
    UserRole.MANAGER,
    UserRole.HR,
    UserRole.EMPLOYEE,
    tool_name="get_stock_levels",
)
def get_stock_levels(
    db: Session,
    current_user: User,
    sku: str | None = None,
) -> dict[str, Any]:
    """Retrieve current stock quantities for a specific product SKU or warehouse totals.

    - Querying a specific product by SKU is permitted to all authenticated staff (Employee, HR, Manager, Admin).
    - Querying the aggregate warehouse summary requires Manager or Admin privileges.
    - Returns physical unit counts only. Monetary valuation is unavailable.
    """
    if sku:
        prod = inventory_service.get_product_by_sku(db, sku.strip())
        if not prod:
            return {
                "found": False,
                "sku": sku,
                "message": f"Product with SKU '{sku}' not found.",
            }

        stock_status = "HEALTHY"
        if prod.quantity_on_hand == 0:
            stock_status = "OUT_OF_STOCK"
        elif prod.quantity_on_hand <= prod.safety_stock:
            stock_status = "LOW_STOCK"

        return {
            "found": True,
            "sku": prod.sku,
            "name": prod.name,
            "quantity_on_hand": prod.quantity_on_hand,
            "quantity_on_order": prod.quantity_on_order,
            "safety_stock": prod.safety_stock,
            "target_stock": prod.target_stock,
            "lead_time_days": prod.lead_time_days,
            "stock_status": stock_status,
            "monetary_valuation_available": False,
        }

    # Aggregate warehouse summary requires Executive / Manager privileges
    if current_user.role not in (UserRole.ADMIN.value, UserRole.MANAGER.value):
        logger.warning(
            "Unauthorized warehouse inventory summary attempt: user_id=%s role=%s",
            getattr(current_user, "id", None),
            current_user.role,
        )
        raise PermissionError(
            "Warehouse inventory summary requires Admin or Manager privileges."
        )

    inv_analytics = analytics_service.get_inventory_analytics(db)
    return {
        "total_products": inv_analytics.total_products,
        "total_stock_on_hand": inv_analytics.total_stock_on_hand,
        "total_stock_on_order": inv_analytics.total_stock_on_order,
        "low_stock_count": inv_analytics.low_stock_count,
        "out_of_stock_count": inv_analytics.out_of_stock_count,
        "replenishment_needed_count": inv_analytics.replenishment_needed_count,
        "monetary_valuation_available": False,
        "highest_stock_items": [
            {
                "sku": item.sku,
                "name": item.name,
                "quantity_on_hand": item.quantity_on_hand,
                "safety_stock": item.safety_stock,
                "target_stock": item.target_stock,
            }
            for item in inv_analytics.highest_stock_products[:10]
        ],
    }


@rbac_tool(
    UserRole.ADMIN,
    UserRole.MANAGER,
    UserRole.HR,
    UserRole.EMPLOYEE,
    tool_name="get_low_stock_alerts",
)
def get_low_stock_alerts(
    db: Session,
    current_user: User,
) -> list[dict[str, Any]]:
    """Retrieve all products currently at or below their safety stock threshold.

    Consistent with the existing API route /api/v1/inventory/alerts/low-stock (RequireStaff),
    all authenticated staff (Employee, HR, Manager, Admin) are authorized to view low stock alerts.
    """
    report = inventory_service.get_low_stock_alerts(db)
    return [
        {
            "product_id": a.product_id,
            "sku": a.sku,
            "name": a.name,
            "quantity_on_hand": a.quantity_on_hand,
            "quantity_on_order": a.quantity_on_order,
            "safety_stock": a.safety_stock,
            "target_stock": a.target_stock,
            "stock_status": a.status,
            "stockout": a.status == "OUT_OF_STOCK",
            "recommended_replenishment": a.replenishment_quantity,
        }
        for a in report.items
    ]


@rbac_tool(
    UserRole.ADMIN,
    UserRole.MANAGER,
    tool_name="get_replenishment_suggestions",
)
def get_replenishment_suggestions(
    db: Session,
    current_user: User,
    urgency_filter: str | None = None,
) -> list[dict[str, Any]]:
    """Retrieve prescriptive replenishment suggestions calculated as: target_stock - (on_hand + on_order).

    Restricted to Manager and Admin in accordance with existing API rules (/analytics/replenishment).
    Optionally filter by urgency ('CRITICAL', 'WARNING', 'NORMAL').
    """
    suggestions = analytics_service.get_replenishment_suggestions(db)
    if urgency_filter:
        target_urgency = urgency_filter.strip().upper()
        suggestions = [s for s in suggestions if s.urgency.upper() == target_urgency]

    return [
        {
            "sku": s.sku,
            "name": s.name,
            "quantity_on_hand": s.quantity_on_hand,
            "quantity_on_order": s.quantity_on_order,
            "safety_stock": s.safety_stock,
            "target_stock": s.target_stock,
            "units_sold": s.units_sold,
            "suggested_replenishment": s.suggested_replenishment,
            "urgency": s.urgency,
        }
        for s in suggestions
    ]


@rbac_tool(
    UserRole.ADMIN,
    UserRole.MANAGER,
    UserRole.HR,
    UserRole.EMPLOYEE,
    tool_name="check_product_availability",
)
def check_product_availability(
    db: Session,
    current_user: User,
    sku: str,
    required_quantity: int,
) -> dict[str, Any]:
    """Check whether sufficient stock is currently on hand to satisfy a specific order quantity.

    Consistent with /api/v1/inventory/products/{product_id} (RequireStaff), all staff may check stock availability.
    """
    if required_quantity <= 0:
        return {"error": "required_quantity must be greater than zero."}

    prod = inventory_service.get_product_by_sku(db, sku.strip())
    if not prod:
        return {
            "found": False,
            "sku": sku,
            "message": f"Product with SKU '{sku}' not found.",
        }

    available_units = prod.quantity_on_hand
    is_sufficient = available_units >= required_quantity
    shortfall = max(0, required_quantity - available_units)

    return {
        "found": True,
        "sku": prod.sku,
        "name": prod.name,
        "requested_units": required_quantity,
        "available_units": available_units,
        "is_available": is_sufficient,
        "shortfall": shortfall,
        "quantity_on_order": prod.quantity_on_order,
        "lead_time_days": prod.lead_time_days,
    }
