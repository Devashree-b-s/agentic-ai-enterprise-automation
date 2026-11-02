"""State models and routing schemas for the LangGraph Supervisor workflow."""

from typing import Any

from pydantic import BaseModel, Field


class PlannedTool(BaseModel):
    """Specification of a tool to be executed by the supervisor."""

    department: str = Field(
        ...,
        description="Department name: 'hr', 'sales', 'inventory', or 'analytics'",
    )
    tool_name: str = Field(
        ...,
        description="Exact registered name of the tool to invoke",
    )
    arguments: dict[str, Any] = Field(
        default_factory=dict,
        description="Keyword arguments for the tool",
    )


class SupervisorDecision(BaseModel):
    """Structured routing and tool planning decision emitted by the Supervisor."""

    is_supported: bool = Field(
        default=True,
        description="Whether the user query is a supported enterprise domain question.",
    )
    departments: list[str] = Field(
        default_factory=list,
        description="List of enterprise departments relevant to answering the query.",
    )
    planned_tools: list[PlannedTool] = Field(
        default_factory=list,
        description="Sequential list of tools to invoke to answer the query.",
    )
    direct_response: str | None = Field(
        default=None,
        description="Direct answer message if query is unsupported or requires no tool calls.",
    )


class AgentState(BaseModel):
    """State model passed through all nodes of the LangGraph workflow."""

    query: str = Field(..., description="User's original natural-language question")
    history: list[dict[str, str]] = Field(
        default_factory=list,
        description="Recent conversational turns (role and content) for context-aware memory",
    )
    user_id: int | None = Field(
        default=None, description="Current authenticated user database ID"
    )
    user_role: str = Field(
        default="Employee", description="Current authenticated user RBAC role"
    )
    employee_id: int | None = Field(
        default=None, description="Linked Employee primary key if any"
    )

    is_supported: bool = Field(
        default=True, description="Whether the query was recognized as supported"
    )
    departments_needed: list[str] = Field(
        default_factory=list, description="Departments requiring execution"
    )
    completed_departments: list[str] = Field(
        default_factory=list, description="Departments whose tools have finished"
    )
    agents_involved: list[str] = Field(
        default_factory=list,
        description="Names of specialized department agents delegated to",
    )
    agent_executions: dict[str, Any] = Field(
        default_factory=dict,
        description="Execution telemetry and results indexed by specialized agent",
    )

    planned_tools: list[dict[str, Any]] = Field(
        default_factory=list, description="Tools planned for execution"
    )
    tools_used: list[str] = Field(
        default_factory=list, description="Names of tools actually executed"
    )
    tool_results: list[dict[str, Any]] = Field(
        default_factory=list, description="Outputs collected from tool calls"
    )

    final_answer: str = Field(
        default="", description="Final synthesized response for the user"
    )
    error: str | None = Field(
        default=None, description="Error message if workflow failed"
    )
    iteration_count: int = Field(
        default=0, description="Supervisor iteration counter to guard against loops"
    )
