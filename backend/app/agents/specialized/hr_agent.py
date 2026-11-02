from typing import ClassVar

"""Specialized HR Agent for workforce, staffing, and leave management."""

from app.agents.specialized.base import BaseSpecializedAgent


class HRAgent(BaseSpecializedAgent):
    """Specialized agent responsible for all Human Resources inquiries.

    Capabilities:
    - Active workforce headcounts and department staffing distribution.
    - Employee profile lookup with self-access restrictions and salary confidentiality.
    - Leave request tracking, status querying, date filtering, and annual trends.
    - Department-level leave utilization summaries.
    """

    name = "hr"
    display_name = "HR & Workforce Specialist Agent"
    allowed_tools: ClassVar[list[str]] = [
        "prepare_leave_request",
        "get_employee_by_code",
        "list_department_staffing",
        "query_leave_records",
        "get_monthly_leave_trends",
        "get_department_leave_summaries",
    ]


hr_agent = HRAgent()
