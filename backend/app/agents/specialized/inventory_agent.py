from typing import ClassVar

"""Specialized Inventory Agent for stock levels, replenishment, and catalog items."""

from app.agents.specialized.base import BaseSpecializedAgent


class InventoryAgent(BaseSpecializedAgent):
    """Specialized agent responsible for all Warehouse, Stock, and Inventory inquiries.

    Capabilities:
    - Product stock levels on hand and on order.
    - Low-stock alerts for products at or below safety stock.
    - Prescriptive replenishment suggestions with urgency classification.
    - Product stock availability checking for incoming customer orders.
    - Non-monetary valuation enforcement (physical unit counts only).
    """

    name = "inventory"
    display_name = "Inventory & Warehouse Specialist Agent"
    allowed_tools: ClassVar[list[str]] = [
        "prepare_purchase_requisition",
        "get_stock_levels",
        "get_low_stock_alerts",
        "get_replenishment_suggestions",
        "check_product_availability",
    ]


inventory_agent = InventoryAgent()
