from app.agents.tools.approval_tools import (
    check_approval_status,
    prepare_leave_request,
    prepare_purchase_requisition,
)
from app.agents.tools.prediction_tools import (
    get_inventory_shortage_risks,
    get_product_demand_predictions,
    get_sales_revenue_forecast,
)

"""Agent tool registry and exports."""

from app.agents.tools.analytics_tools import (
    get_department_headcount_vs_leave_performance,
    get_executive_kpi_overview,
    get_product_demand_vs_stock,
)
from app.agents.tools.base import ToolResult, rbac_tool
from app.agents.tools.hr_tools import (
    get_department_leave_summaries,
    get_employee_by_code,
    get_monthly_leave_trends,
    list_department_staffing,
    query_leave_records,
)
from app.agents.tools.inventory_tools import (
    check_product_availability,
    get_low_stock_alerts,
    get_replenishment_suggestions,
    get_stock_levels,
)
from app.agents.tools.rag_tools import search_enterprise_documents
from app.agents.tools.sales_tools import (
    get_monthly_revenue_trends,
    get_recognized_revenue,
    get_sales_status_breakdown,
    get_top_selling_products,
)

ALL_TOOLS = {
    # HR
    "get_employee_by_code": get_employee_by_code,
    "list_department_staffing": list_department_staffing,
    "query_leave_records": query_leave_records,
    "get_monthly_leave_trends": get_monthly_leave_trends,
    "get_department_leave_summaries": get_department_leave_summaries,
    # Sales
    "get_recognized_revenue": get_recognized_revenue,
    "get_monthly_revenue_trends": get_monthly_revenue_trends,
    "get_top_selling_products": get_top_selling_products,
    "get_sales_status_breakdown": get_sales_status_breakdown,
    # Inventory
    "get_stock_levels": get_stock_levels,
    "get_low_stock_alerts": get_low_stock_alerts,
    "get_replenishment_suggestions": get_replenishment_suggestions,
    "check_product_availability": check_product_availability,
    # Analytics
    "get_executive_kpi_overview": get_executive_kpi_overview,
    "get_product_demand_vs_stock": get_product_demand_vs_stock,
    "get_department_headcount_vs_leave_performance": get_department_headcount_vs_leave_performance,
    # Documents / RAG
    "search_enterprise_documents": search_enterprise_documents,
    # Predictive Analytics
    "get_sales_revenue_forecast": get_sales_revenue_forecast,
    "get_product_demand_predictions": get_product_demand_predictions,
    "get_inventory_shortage_risks": get_inventory_shortage_risks,
    # Human-in-the-Loop Approvals
    "prepare_purchase_requisition": prepare_purchase_requisition,
    "prepare_leave_request": prepare_leave_request,
    "check_approval_status": check_approval_status,
}

DEPARTMENT_TOOLS = {
    "hr": [
        "prepare_leave_request",
        "get_employee_by_code",
        "list_department_staffing",
        "query_leave_records",
        "get_monthly_leave_trends",
        "get_department_leave_summaries",
    ],
    "sales": [
        "get_recognized_revenue",
        "get_monthly_revenue_trends",
        "get_top_selling_products",
        "get_sales_status_breakdown",
    ],
    "inventory": [
        "prepare_purchase_requisition",
        "get_stock_levels",
        "get_low_stock_alerts",
        "get_replenishment_suggestions",
        "check_product_availability",
    ],
    "analytics": [
        "get_sales_revenue_forecast",
        "get_product_demand_predictions",
        "get_inventory_shortage_risks",
        "check_approval_status",
        "get_executive_kpi_overview",
        "get_product_demand_vs_stock",
        "get_department_headcount_vs_leave_performance",
    ],
    "documents": [
        "search_enterprise_documents",
    ],
}

__all__ = [
    "ALL_TOOLS",
    "DEPARTMENT_TOOLS",
    "ToolResult",
    "check_product_availability",
    "get_department_headcount_vs_leave_performance",
    "get_department_leave_summaries",
    "get_employee_by_code",
    "get_executive_kpi_overview",
    "get_low_stock_alerts",
    "get_monthly_leave_trends",
    "get_monthly_revenue_trends",
    "get_product_demand_vs_stock",
    "get_recognized_revenue",
    "get_replenishment_suggestions",
    "get_sales_status_breakdown",
    "get_stock_levels",
    "get_top_selling_products",
    "list_department_staffing",
    "query_leave_records",
    "rbac_tool",
    "search_enterprise_documents",
]
