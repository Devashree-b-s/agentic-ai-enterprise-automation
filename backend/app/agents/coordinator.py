"""Multi-Agent Coordination Engine for concurrent delegation and failure containment."""

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from sqlalchemy.orm import Session

from app.agents.specialized import (
    SPECIALIZED_AGENTS,
    AgentExecutionResult,
    BaseSpecializedAgent,
)
from app.agents.state import PlannedTool
from app.core.config import settings
from app.db.session import SessionLocal
from app.models.user import User

logger = logging.getLogger("app.agents.coordinator")


class MultiAgentCoordinator:
    """Orchestrates delegation of planned business tools to domain-specialized agents.

    Guarantees:
    - Independent department agents execute concurrently in parallel worker threads where safe.
    - Thread-safe SQLAlchemy database session management for SQLite.
    - Bounded failure containment: failure in one agent does not abort remaining agents.
    - Telemetry tracking of agents involved, tools executed, and partial results.
    - Duplicate tool execution prevention.
    """

    def __init__(self, agents: dict[str, BaseSpecializedAgent] | None = None) -> None:
        self.agents = agents or SPECIALIZED_AGENTS

    def resolve_agent_for_tool(self, tool_name: str, suggested_dept: str | None = None) -> BaseSpecializedAgent | None:
        """Find the specialized agent that owns the given tool."""
        # 1. Try suggested department first
        if suggested_dept:
            dept_key = suggested_dept.lower().strip()
            agent = self.agents.get(dept_key)
            if agent and agent.can_handle(tool_name):
                return agent

        # 2. Search across all registered specialized agents
        for agent in self.agents.values():
            if agent.can_handle(tool_name):
                return agent

        return None

    def _execute_agent_worker(
        self,
        agent: BaseSpecializedAgent,
        tasks: list[PlannedTool],
        user_id: int | None,
        user_role: str,
        user_employee_id: int | None,
        user_email: str,
    ) -> AgentExecutionResult:
        """Worker thread entrypoint: creates a fresh, thread-local database session."""
        db: Session = SessionLocal()
        try:
            thread_user = None
            if user_id:
                try:
                    thread_user = db.get(User, user_id)
                except Exception:
                    thread_user = None

            if not thread_user:
                thread_user = User(
                    id=user_id,
                    email=user_email,
                    role=user_role,
                    employee_id=user_employee_id,
                    is_active=True,
                )

            return agent.execute_tasks(tasks=tasks, db=db, current_user=thread_user)
        except Exception:
            logger.exception("Worker thread exception executing agent '%s'", agent.name)
            return AgentExecutionResult(
                agent_name=agent.name,
                display_name=agent.display_name,
                success=False,
                authorized=True,
                error=f"Agent '{agent.display_name}' encountered an internal execution failure.",
            )
        finally:
            try:
                db.close()
            except Exception as exc:
                logger.debug("Failed closing thread db session: %s", exc)

    def coordinate_execution(
        self,
        planned_tools_raw: list[dict[str, Any]],
        current_user: User,
        main_db: Session,
    ) -> dict[str, Any]:
        """Group planned tasks by specialized agent and execute concurrently."""
        # 1. Parse and deduplicate planned tools
        seen_keys: set[str] = set()
        deduped_tasks: list[PlannedTool] = []

        for pt_dict in planned_tools_raw:
            pt = PlannedTool(
                department=pt_dict.get("department", "unknown"),
                tool_name=pt_dict.get("tool_name", ""),
                arguments=pt_dict.get("arguments", {}),
            )
            # Create deduplication signature based on tool_name and sorted arguments
            arg_items = tuple(sorted(pt.arguments.items(), key=lambda x: x[0]))
            key = f"{pt.tool_name}:{arg_items}"
            if key not in seen_keys:
                seen_keys.add(key)
                deduped_tasks.append(pt)

        # 2. Group tasks by specialized agent
        agent_batches: dict[str, list[PlannedTool]] = {}
        unassigned_tasks: list[PlannedTool] = []

        for task in deduped_tasks:
            agent = self.resolve_agent_for_tool(task.tool_name, task.department)
            if agent:
                agent_batches.setdefault(agent.name, []).append(task)
            else:
                unassigned_tasks.append(task)

        if unassigned_tasks:
            logger.warning(
                "Unassigned tools with no specialized agent: %s",
                [t.tool_name for t in unassigned_tasks],
            )

        agents_involved = sorted(agent_batches.keys())
        agent_results: list[AgentExecutionResult] = []

        # Extract user properties safely before threading
        try:
            u_id = getattr(current_user, "id", None)
            u_role = getattr(current_user, "role", "Employee")
            u_emp_id = getattr(current_user, "employee_id", None)
            u_email = getattr(current_user, "email", "user@enterprise.com")
        except AttributeError:
            u_id = None
            u_role = "Employee"
            u_emp_id = None
            u_email = "user@enterprise.com"

        # 3. Execution strategy:
        # If single agent: run synchronously on main_db to eliminate thread overhead.
        # If multiple agents: run concurrently using ThreadPoolExecutor with thread-local sessions.
        if len(agents_involved) <= 1:
            for agent_name, tasks in agent_batches.items():
                agent = self.agents[agent_name]
                res = agent.execute_tasks(tasks=tasks, db=main_db, current_user=current_user)
                agent_results.append(res)
        else:
            logger.info(
                "Executing multi-agent coordination concurrently for agents: %s",
                agents_involved,
            )
            max_workers = min(len(agents_involved), 5)
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                future_to_agent = {
                    executor.submit(
                        self._execute_agent_worker,
                        self.agents[agent_name],
                        tasks,
                        u_id,
                        u_role,
                        u_emp_id,
                        u_email,
                    ): agent_name
                    for agent_name, tasks in agent_batches.items()
                }

                for future in as_completed(future_to_agent):
                    agent_name = future_to_agent[future]
                    try:
                        res = future.result(timeout=settings.AGENT_TIMEOUT_SECONDS)
                        agent_results.append(res)
                    except Exception as exc:
                        logger.error("Agent '%s' worker execution failed: %s", agent_name, exc)
                        agent = self.agents.get(agent_name)
                        agent_results.append(
                            AgentExecutionResult(
                                agent_name=agent_name,
                                display_name=agent.display_name if agent else agent_name,
                                success=False,
                                authorized=True,
                                error=f"Specialized agent '{agent_name}' failed to complete.",
                            )
                        )

        # 4. Aggregate results, telemetry, and status
        all_tools_used: list[str] = []
        all_tool_results: list[dict[str, Any]] = []
        completed_departments: list[str] = []
        agent_executions: dict[str, Any] = {}

        for ar in agent_results:
            if ar.agent_name not in completed_departments:
                completed_departments.append(ar.agent_name)
            all_tools_used.extend(ar.tools_executed)
            all_tool_results.extend(ar.results)
            agent_executions[ar.agent_name] = {
                "display_name": ar.display_name,
                "success": ar.success,
                "authorized": ar.authorized,
                "tools_executed": ar.tools_executed,
                "error": ar.error,
                "execution_time_ms": ar.execution_time_ms,
            }

        return {
            "agents_involved": agents_involved,
            "agent_executions": agent_executions,
            "tools_used": all_tools_used,
            "tool_results": all_tool_results,
            "completed_departments": completed_departments,
        }


multi_agent_coordinator = MultiAgentCoordinator()
