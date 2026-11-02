from typing import ClassVar

"""Specialized Sales Agent for revenue, orders, and sales performance."""

from app.agents.specialized.base import BaseSpecializedAgent


class SalesAgent(BaseSpecializedAgent):
    """Specialized agent responsible for all Sales, Revenue, and Commercial inquiries.

    Capabilities:
    - Gross and recognized revenue calculations from completed and shipped orders.
    - Monthly sales revenue trends and transaction volumes.
    - Top-selling products ranked by recognized revenue or physical units sold.
    - Order lifecycle breakdown, lost revenue from returns, and cancelled potential revenue.
    """

    name = "sales"
    display_name = "Sales & Revenue Specialist Agent"
    allowed_tools: ClassVar[list[str]] = [
        "get_recognized_revenue",
        "get_monthly_revenue_trends",
        "get_top_selling_products",
        "get_sales_status_breakdown",
    ]


sales_agent = SalesAgent()
