"""Base class and result envelope for specialized enterprise department agents."""

import logging
import time
from typing import Any, ClassVar

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.agents.state import PlannedTool
from app.agents.tools import ALL_TOOLS
from app.models.user import User

logger = logging.getLogger("app.agents.specialized")


class AgentExecutionResult(BaseModel):
    """Execution telemetry and data envelope produced by a specialized agent."""

    agent_name: str = Field(description="Unique identifier of the specialized agent (e.g. 'hr', 'sales')")
    display_name: str = Field(description="Human-readable title (e.g. 'HR Specialist Agent')")
    success: bool = Field(default=True, description="Whether all delegated tasks succeeded")
    authorized: bool = Field(default=True, description="Whether caller had RBAC permissions")
    tools_executed: list[str] = Field(default_factory=list, description="Names of tools invoked by this agent")
    results: list[dict[str, Any]] = Field(default_factory=list, description="ToolResult envelopes collected")
    error: str | None = Field(default=None, description="Error message if execution failed")
    execution_time_ms: float = Field(default=0.0, description="Execution time in milliseconds")


class BaseSpecializedAgent:
    """Base class encapsulating a department-specific AI agent with scoped tools and RBAC."""

    name: str = "base"
    display_name: str = "Base Enterprise Agent"
    allowed_tools: ClassVar[list[str]] = []

    def can_handle(self, tool_name: str) -> bool:
        """Check whether this agent owns and is authorized to execute the given tool."""
        return tool_name in self.allowed_tools

    def execute_tasks(
        self,
        tasks: list[PlannedTool],
        db: Session,
        current_user: User,
    ) -> AgentExecutionResult:
        """Execute delegated tasks within this specialized domain boundary with strict error containment."""
        start_time = time.perf_counter()
        tools_executed: list[str] = []
        collected_results: list[dict[str, Any]] = []
        overall_success = True
        overall_authorized = True
        first_error: str | None = None

        for pt in tasks:
            tool_name = pt.tool_name
            args = pt.arguments or {}

            if not self.can_handle(tool_name):
                logger.warning(
                    "Specialized agent '%s' rejected unowned tool '%s'",
                    self.name,
                    tool_name,
                )
                continue

            tool_func = ALL_TOOLS.get(tool_name)
            if not tool_func:
                logger.error("Tool '%s' not registered in ALL_TOOLS", tool_name)
                overall_success = False
                first_error = f"Tool '{tool_name}' is not registered."
                collected_results.append({
                    "tool_name": tool_name,
                    "department": self.name,
                    "success": False,
                    "authorized": True,
                    "error": first_error,
                    "data": None,
                })
                continue

            try:
                # Execute tool function wrapped with @rbac_tool
                tool_res = tool_func(db=db, current_user=current_user, **args)
                tools_executed.append(tool_name)

                res_dict = {
                    "tool_name": tool_name,
                    "department": self.name,
                    "success": tool_res.success,
                    "authorized": tool_res.authorized,
                    "error": tool_res.error,
                    "data": tool_res.data,
                    "execution_time_ms": tool_res.execution_time_ms,
                }
                collected_results.append(res_dict)

                if not tool_res.authorized:
                    overall_authorized = False
                    overall_success = False
                    if not first_error:
                        first_error = tool_res.error or "Access denied."
                elif not tool_res.success:
                    overall_success = False
                    if not first_error:
                        first_error = tool_res.error or f"Tool '{tool_name}' failed."

            except Exception:
                logger.exception("Unexpected exception executing '%s' in agent '%s'", tool_name, self.name)
                overall_success = False
                if not first_error:
                    first_error = f"Agent '{self.display_name}' encountered an error."
                collected_results.append({
                    "tool_name": tool_name,
                    "department": self.name,
                    "success": False,
                    "authorized": True,
                    "error": first_error,
                    "data": None,
                })

        elapsed = round((time.perf_counter() - start_time) * 1000, 2)
        return AgentExecutionResult(
            agent_name=self.name,
            display_name=self.display_name,
            success=overall_success,
            authorized=overall_authorized,
            tools_executed=tools_executed,
            results=collected_results,
            error=first_error,
            execution_time_ms=elapsed,
        )
