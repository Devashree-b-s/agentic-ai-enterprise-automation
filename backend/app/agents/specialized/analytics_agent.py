from typing import ClassVar

"""Specialized Analytics Agent for cross-department synthesis and correlations."""

from app.agents.specialized.base import BaseSpecializedAgent


class AnalyticsAgent(BaseSpecializedAgent):
    """Specialized agent responsible for Cross-Functional Business Intelligence and Analytics.

    Capabilities:
    - High-level executive KPI synthesis across workforce, revenue, and inventory units.
    - Correlating product sales velocity demand against stock on hand and days of supply.
    - Correlating department staffing headcount with approved leave days taken.
    """

    name = "analytics"
    display_name = "Cross-Department Analytics Specialist Agent"
    allowed_tools: ClassVar[list[str]] = [
        "get_sales_revenue_forecast",
        "get_product_demand_predictions",
        "get_inventory_shortage_risks",
        "check_approval_status",
        "get_executive_kpi_overview",
        "get_product_demand_vs_stock",
        "get_department_headcount_vs_leave_performance",
    ]


analytics_agent = AnalyticsAgent()
