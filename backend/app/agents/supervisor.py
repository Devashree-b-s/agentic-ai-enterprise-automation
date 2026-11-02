"""LangGraph Supervisor Workflow for Enterprise Decision Support.

Implements a controlled, sequential workflow:
User Question
→ Supervisor Node (routing & tool planning)
→ Authorized Department Tool Execution (sequential)
→ Result Collection
→ Response Synthesis
→ Final Structured Answer
"""

import logging
import re
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, StateGraph
from sqlalchemy.orm import Session

from app.agents.coordinator import multi_agent_coordinator
from app.agents.llm import get_chat_model
from app.agents.prompts import SUPERVISOR_SYSTEM_PROMPT, SYNTHESIZER_SYSTEM_PROMPT
from app.agents.state import AgentState, PlannedTool, SupervisorDecision
from app.core.config import settings
from app.models.user import User
from app.schemas.agent import AgentChatResponse

logger = logging.getLogger("app.agents.supervisor")


def fallback_route_query(query: str, history: list[dict[str, str]] | None = None) -> SupervisorDecision:
    """Deterministic routing fallback with context-aware resolution from previous messages."""
    """Deterministic routing fallback used when LLM is unavailable or for test safety."""
    q = query.lower().strip()

    # Contextual pronoun & reference resolution from history if follow-up detected
    last_context = ""
    if history:
        for prev in reversed(history):
            if prev.get("role") == "user":
                last_context = prev.get("content", "").lower()
                break

    is_follow_up = any(k in q for k in ["what about", "how about", "and in", "their", "those", "them", "it", "which department"])
    if is_follow_up and last_context:
        # If previous query was about employees and current asks "what about Engineering?", blend context
        if any(e in last_context for e in ["employee", "staff", "headcount", "worker"]) and not any(k in q for k in ["leave", "revenue", "sale", "stock"]):
            q = f"{q} employee headcount"
        elif any(l in last_context for l in ["leave", "vacation"]) and not any(k in q for k in ["revenue", "sale", "stock"]):
            q = f"{q} leave requests"
        elif any(s in last_context for s in ["stock", "inventory", "product"]):
            q = f"{q} inventory stock"
        elif any(r in last_context for r in ["revenue", "sales", "order"]):
            q = f"{q} sales revenue"

    # 1. Unsupported queries
    unsupported_keywords = [
        "weather",
        "recipe",
        "cook",
        "capital of",
        "who is",
        "joke",
        "poem",
        "python code",
        "write a script",
        "movie",
        "song",
        "hack",
        "drop table",
        "select * from",
    ]
    if any(k in q for k in unsupported_keywords):
        return SupervisorDecision(
            is_supported=False,
            direct_response="I can only assist with questions related to HR, Sales, Inventory, Analytics, and Enterprise Documents.",
        )

    # Predictive Analytics Routing
    if any(k in q for k in ["forecast", "predict", "next three months", "next 3 months", "future revenue", "revenue look like"]):
        return SupervisorDecision(
            is_supported=True,
            departments=["analytics"],
            planned_tools=[
                PlannedTool(department="analytics", tool_name="get_sales_revenue_forecast")
            ],
        )

    if any(k in q for k in ["run out of stock", "shortage risk", "stockout", "out of stock risk", "prioritize for replenishment", "inventory risk"]):
        return SupervisorDecision(
            is_supported=True,
            departments=["analytics"],
            planned_tools=[
                PlannedTool(department="analytics", tool_name="get_inventory_shortage_risks")
            ],
        )

    if any(k in q for k in ["increasing demand", "decreasing demand", "demand trend", "demand prediction"]):
        return SupervisorDecision(
            is_supported=True,
            departments=["analytics"],
            planned_tools=[
                PlannedTool(department="analytics", tool_name="get_product_demand_predictions")
            ],
        )

    # Human-in-the-Loop: Check Approval Status
    req_match = re.search(r"\b(req[-_][a-z0-9_-]+)\b", q, re.IGNORECASE)
    if ("status" in q and ("approval" in q or "requisition" in q or "request" in q or req_match)) or ("check request" in q):
        code = req_match.group(1).upper() if req_match else q.strip()
        return SupervisorDecision(
            is_supported=True,
            departments=["analytics"],
            planned_tools=[
                PlannedTool(
                    department="analytics",
                    tool_name="check_approval_status",
                    arguments={"request_code": code},
                )
            ],
        )

    # Human-in-the-Loop: Prepare Purchase Requisition
    is_po_intent = any(k in q for k in ["prepare requisition", "purchase requisition", "order requisition", "create po", "buy stock", "order stock", "purchase stock"])
    if is_po_intent or (("order" in q or "purchase" in q or "buy" in q) and "sku" in q):
        sku_match = re.search(r"\b(sku[-_][a-z0-9_-]+)\b", q, re.IGNORECASE)
        sku = sku_match.group(1).upper() if sku_match else "SKU-GFT-030"
        qty_match = re.search(r"\b(\d+)\s*(?:units?|pcs?|pieces?|items?|quantity)?\b", q)
        qty = int(qty_match.group(1)) if qty_match else 10
        return SupervisorDecision(
            is_supported=True,
            departments=["inventory"],
            planned_tools=[
                PlannedTool(
                    department="inventory",
                    tool_name="prepare_purchase_requisition",
                    arguments={"sku": sku, "quantity": qty, "reason": "Replenishment requested via AI assistant"},
                )
            ],
        )

    # 2. Hybrid Document + Database Queries
    doc_keywords = [
        "policy",
        "policies",
        "handbook",
        "guideline",
        "guidelines",
        "procedure",
        "procedures",
        "manual",
        "stipend",
        "rules",
        "document",
        "documents",
        "contract",
    ]
    is_doc_focused = any(k in q for k in doc_keywords)
    is_comparison = any(
        k in q
        for k in [
            "compare",
            "versus",
            "vs",
            "against",
            "difference between",
            "aligned with",
            "in accordance with",
        ]
    )

    if is_doc_focused and (
        is_comparison
        or ("leave" in q and "pending" in q)
        or ("stock" in q and ("alert" in q or "low" in q))
    ):
        planned_hybrid: list[PlannedTool] = []
        depts_hybrid: list[str] = []

        if "leave" in q or "vacation" in q or "staff" in q:
            status_val = (
                "PENDING"
                if "pending" in q
                else ("APPROVED" if "approved" in q else None)
            )
            args_hr = {"status": status_val} if status_val else {}
            planned_hybrid.append(
                PlannedTool(
                    department="hr",
                    tool_name="query_leave_records",
                    arguments=args_hr,
                )
            )
            depts_hybrid.append("hr")
        elif "stock" in q or "inventory" in q:
            planned_hybrid.append(
                PlannedTool(
                    department="inventory",
                    tool_name="get_low_stock_alerts",
                )
            )
            depts_hybrid.append("inventory")
        elif "sales" in q or "revenue" in q:
            planned_hybrid.append(
                PlannedTool(
                    department="sales",
                    tool_name="get_recognized_revenue",
                )
            )
            depts_hybrid.append("sales")

        planned_hybrid.append(
            PlannedTool(
                department="documents",
                tool_name="search_enterprise_documents",
                arguments={"query": query},
            )
        )
        depts_hybrid.append("documents")

        return SupervisorDecision(
            is_supported=True,
            departments=depts_hybrid,
            planned_tools=planned_hybrid,
        )

    # 3. Document-only Queries
    if is_doc_focused:
        return SupervisorDecision(
            is_supported=True,
            departments=["documents"],
            planned_tools=[
                PlannedTool(
                    department="documents",
                    tool_name="search_enterprise_documents",
                    arguments={"query": query},
                )
            ],
        )

    # 4. Cross-department Analytics (e.g. executive overview across all operational domains)
    if "overview" in q or (
        "sales" in q and "inventory" in q and ("hr" in q or "employee" in q)
    ):
        return SupervisorDecision(
            is_supported=True,
            departments=["analytics"],
            planned_tools=[
                PlannedTool(
                    department="analytics", tool_name="get_executive_kpi_overview"
                )
            ],
        )

    # Multi-Department Compound Queries (e.g. products running low + monthly revenue + employees on leave)
    is_top_selling_single = ("top" in q or "best" in q) and ("selling" in q or "product" in q) and not any(k in q for k in ["running low", "on leave", "leave", "headcount", "staff"])
    has_inv = (any(k in q for k in ["stock", "inventory", "running low", "low stock"]) or ("product" in q and not is_top_selling_single)) and not is_top_selling_single
    has_sales = any(k in q for k in ["revenue", "sales", "monthly revenue", "selling"])
    has_hr = any(k in q for k in ["employee", "staff", "headcount", "on leave", "leave", "vacation"])

    if not is_top_selling_single and ((has_inv and has_sales) or (has_inv and has_hr) or (has_sales and has_hr)):
        planned_multi: list[PlannedTool] = []
        depts_multi: list[str] = []

        if has_inv:
            if "low" in q or "running low" in q or "alert" in q:
                planned_multi.append(PlannedTool(department="inventory", tool_name="get_low_stock_alerts"))
            else:
                planned_multi.append(PlannedTool(department="inventory", tool_name="get_stock_levels"))
            depts_multi.append("inventory")

        if has_sales:
            if "trend" in q or "monthly" in q:
                planned_multi.append(PlannedTool(department="sales", tool_name="get_monthly_revenue_trends"))
            else:
                planned_multi.append(PlannedTool(department="sales", tool_name="get_recognized_revenue"))
            depts_multi.append("sales")

        if has_hr:
            if "leave" in q or "on leave" in q:
                planned_multi.append(PlannedTool(department="hr", tool_name="query_leave_records", arguments={"status": "APPROVED" if "approved" in q else ("PENDING" if "pending" in q else None)}))
            else:
                planned_multi.append(PlannedTool(department="hr", tool_name="list_department_staffing"))
            depts_multi.append("hr")

        return SupervisorDecision(
            is_supported=True,
            departments=depts_multi,
            planned_tools=planned_multi,
        )
    if "demand" in q and ("stock" in q or "inventory" in q):
        return SupervisorDecision(
            is_supported=True,
            departments=["analytics"],
            planned_tools=[
                PlannedTool(
                    department="analytics", tool_name="get_product_demand_vs_stock"
                )
            ],
        )
    if ("headcount" in q or "staff" in q) and "leave" in q:
        return SupervisorDecision(
            is_supported=True,
            departments=["analytics"],
            planned_tools=[
                PlannedTool(
                    department="analytics",
                    tool_name="get_department_headcount_vs_leave_performance",
                )
            ],
        )

    # 3. HR Department
    if "leave" in q or "vacation" in q:
        if "trend" in q or "monthly" in q:
            return SupervisorDecision(
                is_supported=True,
                departments=["hr"],
                planned_tools=[
                    PlannedTool(department="hr", tool_name="get_monthly_leave_trends")
                ],
            )
        if "summary" in q or "breakdown" in q:
            return SupervisorDecision(
                is_supported=True,
                departments=["hr"],
                planned_tools=[
                    PlannedTool(
                        department="hr", tool_name="get_department_leave_summaries"
                    )
                ],
            )
        status_val = (
            "PENDING" if "pending" in q else ("APPROVED" if "approved" in q else None)
        )
        args: dict[str, Any] = {}
        if status_val:
            args["status"] = status_val

        # Extract department filter if mentioned
        known_depts = ["Engineering", "Finance", "HR", "Inventory", "Operations", "Sales", "Executive"]
        for kd in known_depts:
            if kd.lower() in q:
                args["department"] = kd
                break

        # Extract employee code if mentioned
        emp_match = re.search(r"\b(emp[-_][a-z0-9_-]+)\b", q, re.IGNORECASE)
        if emp_match:
            args["employee_code"] = emp_match.group(1).upper()

        # Extract date filters (YYYY-MM-DD)
        dates = re.findall(r"\b(\d{4}-\d{2}-\d{2})\b", q)
        if len(dates) >= 2:
            args["start_date"] = min(dates[0], dates[1])
            args["end_date"] = max(dates[0], dates[1])
        elif len(dates) == 1:
            if "after" in q or "from" in q or "start" in q:
                args["start_date"] = dates[0]
            else:
                args["end_date"] = dates[0]

        return SupervisorDecision(
            is_supported=True,
            departments=["hr"],
            planned_tools=[
                PlannedTool(
                    department="hr",
                    tool_name="query_leave_records",
                    arguments=args,
                )
            ],
        )

    if (
        "employee" in q
        or "staff" in q
        or "headcount" in q
        or "worker" in q
        or "profile" in q
    ):
        code_match = re.search(r"\b(emp[-_][a-z0-9_-]+)\b", q, re.IGNORECASE)
        if code_match:
            emp_code = code_match.group(1).upper()
            return SupervisorDecision(
                is_supported=True,
                departments=["hr"],
                planned_tools=[
                    PlannedTool(
                        department="hr",
                        tool_name="get_employee_by_code",
                        arguments={"employee_code": emp_code},
                    )
                ],
            )
        dept = None
        for d in [
            "engineering",
            "sales",
            "hr",
            "inventory",
            "marketing",
            "executive",
            "finance",
        ]:
            if d in q:
                dept = d.capitalize()
                break
        args = {"department": dept} if dept else {}
        return SupervisorDecision(
            is_supported=True,
            departments=["hr"],
            planned_tools=[
                PlannedTool(
                    department="hr",
                    tool_name="list_department_staffing",
                    arguments=args,
                )
            ],
        )

    # 4. Sales Department
    if "revenue" in q or "sales" in q or "top product" in q or "selling" in q:
        if "trend" in q or "monthly" in q:
            return SupervisorDecision(
                is_supported=True,
                departments=["sales"],
                planned_tools=[
                    PlannedTool(
                        department="sales", tool_name="get_monthly_revenue_trends"
                    )
                ],
            )
        if "top" in q or "best" in q:
            by_val = "units" if "unit" in q else "revenue"
            return SupervisorDecision(
                is_supported=True,
                departments=["sales"],
                planned_tools=[
                    PlannedTool(
                        department="sales",
                        tool_name="get_top_selling_products",
                        arguments={"by": by_val},
                    )
                ],
            )
        if "status" in q or "cancel" in q or "return" in q:
            return SupervisorDecision(
                is_supported=True,
                departments=["sales"],
                planned_tools=[
                    PlannedTool(
                        department="sales", tool_name="get_sales_status_breakdown"
                    )
                ],
            )
        return SupervisorDecision(
            is_supported=True,
            departments=["sales"],
            planned_tools=[
                PlannedTool(department="sales", tool_name="get_recognized_revenue")
            ],
        )

    # 5. Inventory Department
    if (
        "stock" in q
        or "inventory" in q
        or "product" in q
        or "replenish" in q
        or "sku" in q
    ):
        sku_match = re.search(r"\b(sku[-_][a-z0-9_-]+)\b", q, re.IGNORECASE)
        if sku_match:
            sku = sku_match.group(1).upper()
            return SupervisorDecision(
                is_supported=True,
                departments=["inventory"],
                planned_tools=[
                    PlannedTool(
                        department="inventory",
                        tool_name="get_stock_levels",
                        arguments={"sku": sku},
                    )
                ],
            )
        if "replenish" in q or "reorder" in q or "order more" in q:
            return SupervisorDecision(
                is_supported=True,
                departments=["inventory"],
                planned_tools=[
                    PlannedTool(
                        department="inventory",
                        tool_name="get_replenishment_suggestions",
                    )
                ],
            )
        if "low" in q or "alert" in q or "shortage" in q or "running low" in q:
            return SupervisorDecision(
                is_supported=True,
                departments=["inventory"],
                planned_tools=[
                    PlannedTool(
                        department="inventory", tool_name="get_low_stock_alerts"
                    )
                ],
            )
        return SupervisorDecision(
            is_supported=True,
            departments=["inventory"],
            planned_tools=[
                PlannedTool(department="inventory", tool_name="get_stock_levels")
            ],
        )

    # Unrecognized queries
    return SupervisorDecision(
        is_supported=False,
        direct_response="I can only assist with questions related to HR, Sales, Inventory, Analytics, and Enterprise Documents.",
    )


def supervisor_node(state: AgentState) -> dict[str, Any]:
    """Supervisor node: analyzes user query and determines execution plan."""
    new_iteration = state.iteration_count + 1
    if new_iteration > settings.AGENT_MAX_ITERATIONS:
        return {
            "is_supported": False,
            "final_answer": "Request reached the maximum supervisor iteration limit.",
            "error": "Iteration limit exceeded.",
            "iteration_count": new_iteration,
        }

    try:
        model = get_chat_model(temperature=0.0)
        structured_model = model.with_structured_output(SupervisorDecision)
        # Construct contextual messages with conversation history window
        supervisor_messages = [SystemMessage(content=SUPERVISOR_SYSTEM_PROMPT)]
        history_window = state.history[-settings.CONVERSATION_HISTORY_LIMIT:] if state.history else []
        for h in history_window:
            role_val = h.get("role", "").lower()
            content_val = h.get("content", "")
            if role_val == "user":
                supervisor_messages.append(HumanMessage(content=f"[Previous User Query]: {content_val}"))
            elif role_val == "assistant":
                # Truncate assistant history in supervisor router to keep context lean
                short_content = content_val[:300] + ("..." if len(content_val) > 300 else "")
                supervisor_messages.append(SystemMessage(content=f"[Previous Assistant Answer Summary]: {short_content}"))
        supervisor_messages.append(HumanMessage(content=f"[Current User Question]: {state.query}"))

        decision = structured_model.invoke(supervisor_messages)
        if not isinstance(decision, SupervisorDecision):
            decision = fallback_route_query(state.query, history=state.history)
    except Exception as exc:
        logger.info(
            "Using fallback supervisor routing (LLM call skipped/failed: %s)",
            exc,
        )
        decision = fallback_route_query(state.query, history=state.history)

    if not decision.is_supported:
        return {
            "is_supported": False,
            "final_answer": decision.direct_response
            or "I can only assist with questions related to HR, Sales, Inventory, and Analytics.",
            "iteration_count": new_iteration,
        }

    return {
        "is_supported": True,
        "departments_needed": [d.lower() for d in decision.departments],
        "planned_tools": [pt.model_dump() for pt in decision.planned_tools],
        "iteration_count": new_iteration,
    }


def should_execute_tools(state: AgentState) -> str:
    """Conditional edge router: proceed to tool execution or directly to synthesis."""
    if not state.is_supported:
        return "synthesize"
    if state.planned_tools:
        return "execute"
    return "synthesize"


def execute_department_tools_node(
    state: AgentState, db: Session, current_user: User
) -> dict[str, Any]:
    """Execute planned tools via Multi-Agent Coordinator with concurrent execution and domain isolation."""
    coord_res = multi_agent_coordinator.coordinate_execution(
        planned_tools_raw=state.planned_tools,
        current_user=current_user,
        main_db=db,
    )

    tools_used = list(state.tools_used) + coord_res.get("tools_used", [])
    tool_results = list(state.tool_results) + coord_res.get("tool_results", [])
    completed_depts = list(state.completed_departments)
    for d in coord_res.get("completed_departments", []):
        if d not in completed_depts:
            completed_depts.append(d)

    return {
        "agents_involved": coord_res.get("agents_involved", []),
        "agent_executions": coord_res.get("agent_executions", {}),
        "tools_used": tools_used,
        "tool_results": tool_results,
        "completed_departments": completed_depts,
    }


def deterministic_synthesize_answer(query: str, results: list[dict[str, Any]]) -> str:
    """Format safe deterministic natural language response from collected tool results."""
    if not results:
        return "No information could be retrieved for this query."

    parts: list[str] = []

    for r in results:
        tool_name = r.get("tool_name", "")
        success = r.get("success", False)
        authorized = r.get("authorized", True)
        data = r.get("data")
        error = r.get("error")

        if not authorized:
            parts.append(
                "Access denied: You do not have permission to access this information."
            )
            continue

        if not success or error:
            parts.append(error or f"Failed to retrieve data from {tool_name}.")
            continue

        if data is None:
            parts.append("No records found.")
            continue

        # Format by tool type
        if tool_name == "list_department_staffing":
            if isinstance(data, dict) and "department" in data:
                dept_name = data.get("department")
                count = data.get("headcount", 0)
                if data.get("found") is True:
                    parts.append(f"There are {count} employees in the {dept_name} department.")
                else:
                    parts.append(f"There are currently 0 active employees recorded in the {dept_name} department.")
            elif isinstance(data, dict):
                parts.append(
                    f"Total enterprise workforce: {data.get('total_workforce', 0)} employees "
                    f"({data.get('active_workforce', 0)} active) across {data.get('total_departments', 0)} departments."
                )

        elif tool_name == "get_sales_revenue_forecast":
            model = data.get("selected_forecasting_model", "Predictive Model")
            growth = data.get("projected_growth_rate_percent", 0.0)
            forecasts = data.get("next_3_months_forecast", [])
            f_lines = [f"{f['month']}: ${f['projected_revenue']:,.2f} ({f['trend']})" for f in forecasts]
            parts.append(
                f"Sales Revenue Forecast ({model}, {growth:+.1f}% projected growth):\n" + "\n".join(f_lines)
            )

        elif tool_name == "get_product_demand_predictions":
            top = data.get("top_demand_products", [])
            top_str = ", ".join([f"{p['name']} ({p['projected_monthly_demand']} units/mo)" for p in top[:3]])
            inc = data.get("products_with_increasing_demand", [])
            inc_str = ", ".join([f"{p['name']} ({p['growth_percentage']})" for p in inc[:2]])
            parts.append(
                f"Product Demand Analysis: Top demand products: {top_str}. Accelerating growth: {inc_str}."
            )

        elif tool_name == "get_inventory_shortage_risks":
            crit_count = data.get("critical_risk_count", 0)
            priorities = data.get("urgent_replenishment_priorities", [])
            p_lines = [f"{p['name']} ({p['sku']}): {p['on_hand']} on hand, {p['days_of_stock_remaining']} days stock ({p['risk_level']})" for p in priorities[:3]]
            parts.append(
                f"Inventory Shortage Risk: {crit_count} product(s) at critical risk below safety stock.\nPriorities:\n" + "\n".join(p_lines)
            )

        elif tool_name == "get_recognized_revenue":
            rev = data.get("total_recognized_revenue", 0.0)
            units = data.get("total_units_sold", 0)
            txs = data.get("total_transactions", 0)
            parts.append(
                f"Total recognized revenue is ${rev:,.2f} across {txs} completed/shipped transactions ({units} units sold)."
            )

        elif tool_name == "get_low_stock_alerts":
            if isinstance(data, list) and data:
                items = [
                    f"{item['name']} ({item['sku']}): {item['quantity_on_hand']} on hand (safety stock: {item['safety_stock']})"
                    for item in data[:5]
                ]
                parts.append(
                    f"There are {len(data)} products currently running low on stock:\n- "
                    + "\n- ".join(items)
                )
            else:
                parts.append(
                    "All products are currently operating at healthy stock levels."
                )

        elif tool_name == "query_leave_records":
            total = (
                data.get("total_matching_count")
                if isinstance(data, dict)
                else getattr(data, "total_count", len(data) if isinstance(data, list) else 0)
            )
            filters = (
                data.get("filters", {})
                if isinstance(data, dict)
                else getattr(data, "filters", {})
            )
            status_desc = filters.get("status") or "all"
            dept_desc = f" in {filters.get('department')}" if filters.get("department") else ""
            emp_desc = f" for employee {filters.get('employee_code')}" if filters.get("employee_code") else ""
            date_desc = ""
            if filters.get("start_date") and filters.get("end_date"):
                date_desc = f" between {filters.get('start_date')} and {filters.get('end_date')}"
            elif filters.get("start_date"):
                date_desc = f" from {filters.get('start_date')}"
            elif filters.get("end_date"):
                date_desc = f" up to {filters.get('end_date')}"

            parts.append(
                f"There are currently {total} {status_desc.lower()} leave request(s){dept_desc}{emp_desc}{date_desc}."
            )

        elif tool_name == "get_stock_levels":
            if isinstance(data, dict) and data.get("found") is True:
                parts.append(
                    f"Product {data.get('name')} ({data.get('sku')}): {data.get('quantity_on_hand')} units on hand, "
                    f"{data.get('quantity_on_order')} units on order (Status: {data.get('stock_status')})."
                )
            elif isinstance(data, dict) and "total_stock_on_hand" in data:
                parts.append(
                    f"Warehouse total: {data.get('total_stock_on_hand')} units across {data.get('total_products')} products. "
                    f"Low stock items: {data.get('low_stock_count')}."
                )
            else:
                parts.append("Product not found.")

        elif tool_name == "get_executive_kpi_overview":
            parts.append(
                f"Enterprise KPI Overview:\n"
                f"- Workforce: {data.get('total_employees', 0)} total employees ({data.get('active_employees', 0)} active)\n"
                f"- Revenue: ${data.get('total_recognized_revenue', 0.0):,.2f} recognized across {data.get('total_orders_completed', 0)} completed orders\n"
                f"- Inventory: {data.get('total_inventory_units', 0)} units on hand across {data.get('total_products', 0)} products\n"
                f"- Pending Leaves: {data.get('pending_leave_requests', 0)} request(s)"
            )

        elif tool_name == "get_product_demand_vs_stock":
            if isinstance(data, list) and data:
                top_items = [
                    f"{i['name']} ({i['sku']}): {i['units_sold']} sold, {i['quantity_on_hand']} on hand (supply: {i.get('days_of_supply_estimate', 'N/A')})"
                    for i in data[:3]
                ]
                parts.append(
                    "Product demand vs inventory:\n- " + "\n- ".join(top_items)
                )
            else:
                parts.append("Product performance data is currently unavailable.")

        elif tool_name == "get_employee_by_code":
            if data.get("found") is True:
                parts.append(
                    f"Employee {data.get('first_name')} {data.get('last_name')} ({data.get('employee_id')}): "
                    f"Department: {data.get('department')}, Role: {data.get('role')}."
                )
            else:
                parts.append(data.get("message", "Employee not found."))

        elif tool_name == "search_enterprise_documents":
            chunks = data.get("chunks", []) if isinstance(data, dict) else []
            sources = data.get("sources", []) if isinstance(data, dict) else []
            if chunks:
                snips = [
                    f"[{c.get('document_name', 'Doc')}]: {c.get('text', '')[:200]}..."
                    for c in chunks[:3]
                ]
                src_str = ", ".join(sources) if sources else "enterprise documents"
                parts.append(
                    "Enterprise document findings:\n- "
                    + "\n- ".join(snips)
                    + f"\n(Sources: {src_str})"
                )
            else:
                parts.append("No matching information was found in enterprise documents.")

        else:
            parts.append(str(data))

    has_docs = any(
        r.get("tool_name") == "search_enterprise_documents" for r in results
    )
    has_db = any(
        r.get("tool_name") != "search_enterprise_documents" for r in results
    )

    base_answer = "\n\n".join(parts)
    if has_docs and has_db:
        return f"{base_answer}\n\nSource Attribution: Both Enterprise Documents & Operational Database"
    if has_docs:
        return f"{base_answer}\n\nSource Attribution: Enterprise Documents"
    if has_db:
        return f"{base_answer}\n\nSource Attribution: Operational Database"
    return base_answer


def sanitize_data_for_llm(data: Any) -> Any:
    """Recursively sanitize data before passing to external LLMs.

    Strips employee emails, contact details, salaries, medical leave reasons,
    database primary keys, and internal system IDs to protect privacy and minimize context.
    """
    sensitive_keys = {
        "email",
        "salary",
        "reason",
        "hashed_password",
        "password",
        "leave_id",
        "phone",
        "address",
    }
    if isinstance(data, dict):
        sanitized = {}
        for k, v in data.items():
            if k.lower() in sensitive_keys:
                continue
            # If key is "employee_id" and value is an integer (database PK), omit it
            if k.lower() == "employee_id" and isinstance(v, int):
                continue
            sanitized[k] = sanitize_data_for_llm(v)
        return sanitized
    if hasattr(data, "total_count"):
        return {
            "total_matching_count": data.total_count,
            "returned_count": len(data),
            "filters": sanitize_data_for_llm(getattr(data, "filters", {})),
            "sample_records": [sanitize_data_for_llm(item) for item in data[:10]],
        }
    if isinstance(data, list):
        return [sanitize_data_for_llm(item) for item in data]
    return data


def synthesizer_node(state: AgentState) -> dict[str, Any]:
    """Synthesizer node: formats final natural-language response based strictly on tool results."""
    if state.final_answer and not state.is_supported:
        return {"final_answer": state.final_answer}

    if not state.tool_results:
        return {
            "final_answer": state.final_answer
            or "No tool results were produced to answer this question."
        }

    try:
        model = get_chat_model(temperature=0.0)
        # Minimize context: strip any internal sensitive identifiers and tag explicit statuses
        safe_context = []
        for r in state.tool_results:
            is_auth = r.get("authorized", True)
            is_succ = r.get("success", False)
            if not is_auth:
                status_str = "ACCESS_DENIED"
            elif is_succ:
                status_str = "SUCCESS"
            else:
                status_str = "EXECUTION_FAILED"

            safe_context.append(
                {
                    "tool_name": r.get("tool_name"),
                    "department": r.get("department"),
                    "status": status_str,
                    "authorized": is_auth,
                    "success": is_succ,
                    "data": sanitize_data_for_llm(r.get("data"))
                    if is_auth and is_succ
                    else None,
                    "error": r.get("error") if not is_auth or not is_succ else None,
                }
            )

        history_str = ""
        if state.history:
            history_lines = []
            for h in state.history[-settings.CONVERSATION_HISTORY_LIMIT:]:
                role_label = "User" if h.get("role") == "user" else "Assistant"
                history_lines.append(f"{role_label}: {h.get('content', '')}")
            history_str = "\n".join(history_lines)

        history_section = f"Conversation History (for resolving follow-up context and pronouns):\n{history_str}\n\n" if history_str else ""
        prompt_text = (
            f"{history_section}Current User Question: {state.query}\n\nTool Execution Results:\n{safe_context}"
        )
        response = model.invoke(
            [
                SystemMessage(content=SYNTHESIZER_SYSTEM_PROMPT),
                HumanMessage(content=prompt_text),
            ]
        )
        answer = response.content if hasattr(response, "content") else str(response)
        return {"final_answer": str(answer).strip()}
    except Exception as exc:
        logger.info("Using deterministic synthesis (LLM call skipped/failed: %s)", exc)
        answer = deterministic_synthesize_answer(state.query, state.tool_results)
        return {"final_answer": answer}


def create_supervisor_graph(db: Session, current_user: User):
    """Build and compile the LangGraph workflow scoped to the request's db and user context."""
    workflow = StateGraph(AgentState)

    workflow.add_node("supervisor", supervisor_node)
    workflow.add_node(
        "execute_department_tools",
        lambda state: execute_department_tools_node(
            state, db=db, current_user=current_user
        ),
    )
    workflow.add_node("synthesizer", synthesizer_node)

    workflow.set_entry_point("supervisor")

    workflow.add_conditional_edges(
        "supervisor",
        should_execute_tools,
        {
            "execute": "execute_department_tools",
            "synthesize": "synthesizer",
        },
    )
    workflow.add_edge("execute_department_tools", "synthesizer")
    workflow.add_edge("synthesizer", END)

    return workflow.compile()


def run_supervisor_chat(
    query: str,
    db: Session,
    current_user: User,
    history: list[dict[str, str]] | None = None,
) -> AgentChatResponse:
    """Execute the supervisor workflow for an authenticated user query and return AgentChatResponse."""
    initial_state = AgentState(
        query=query.strip(),
        user_id=current_user.id,
        user_role=current_user.role,
        employee_id=current_user.employee_id,
        history=history or [],
    )

    try:
        app_graph = create_supervisor_graph(db=db, current_user=current_user)
        result_state = app_graph.invoke(initial_state)

        # Convert dict or model to dict if needed
        final_dict = (
            result_state.model_dump()
            if hasattr(result_state, "model_dump")
            else dict(result_state)
        )

        tool_results = final_dict.get("tool_results", [])
        has_denied = any(not r.get("authorized", True) for r in tool_results)
        all_denied_or_failed = bool(tool_results) and all(
            (not r.get("authorized", True) or not r.get("success", False))
            for r in tool_results
        )
        is_supported = final_dict.get("is_supported", True)

        overall_success = (
            is_supported and not all_denied_or_failed and not final_dict.get("error")
        )

        safe_error = final_dict.get("error")
        if not safe_error:
            if has_denied and all_denied_or_failed:
                safe_error = "Access denied: You do not have permission to access the requested resource."
            elif has_denied:
                safe_error = "Partial access: One or more requested operations were restricted by permissions."
            elif all_denied_or_failed:
                safe_error = "One or more requested operations could not be completed."

        tools_used = final_dict.get("tools_used", [])
        has_docs = "search_enterprise_documents" in tools_used
        has_db = any(t != "search_enterprise_documents" for t in tools_used)

        source_attribution: str | None = None
        if has_docs and has_db:
            source_attribution = "hybrid"
        elif has_docs:
            source_attribution = "documents"
        elif has_db:
            source_attribution = "database"

        citations: list[dict[str, Any]] = []
        for r in tool_results:
            if r.get("tool_name") == "search_enterprise_documents" and isinstance(
                r.get("data"), dict
            ):
                for c in r["data"].get("chunks", []):
                    citations.append(
                        {
                            "document_name": c.get("document_name"),
                            "chunk_index": c.get("chunk_index"),
                            "total_chunks": c.get("total_chunks"),
                            "department": c.get("department"),
                            "similarity_score": c.get("similarity_score"),
                            "excerpt": (c.get("text") or "")[:250],
                        }
                    )

        agents_involved = final_dict.get("agents_involved", [])
        if not agents_involved:
            agents_involved = final_dict.get("completed_departments", [])

        return AgentChatResponse(
            answer=final_dict.get("final_answer", "No answer could be generated."),
            departments_used=final_dict.get("completed_departments", []),
            agents_involved=agents_involved,
            tools_used=tools_used,
            success=overall_success,
            error=safe_error,
            source_attribution=source_attribution,
            citations=citations,
        )
    except Exception as exc:
        logger.error("Supervisor workflow execution error: %s", exc)
        return AgentChatResponse(
            answer="An error occurred while processing your request. Please try again later.",
            departments_used=[],
            tools_used=[],
            success=False,
            error="Internal agent execution error.",
        )
