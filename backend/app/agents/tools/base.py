import functools
import logging
import time
from collections.abc import Callable
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.user import User, UserRole

logger = logging.getLogger("app.agents.tools")


class ToolResult(BaseModel):
    """Standardized, safe result envelope returned by all agent tools."""

    success: bool = Field(description="Whether tool execution completed successfully")
    data: Any = Field(
        default=None, description="Serialized result payload from underlying service"
    )
    error: str | None = Field(
        default=None, description="Safe, non-leaking error message if failed"
    )
    authorized: bool = Field(
        default=True, description="Whether caller has RBAC permission for tool"
    )
    execution_time_ms: float = Field(
        default=0.0, description="Execution duration in milliseconds"
    )
    tool_name: str = Field(default="", description="Name of the executed tool")


def rbac_tool(
    *allowed_roles: UserRole,
    allow_employee_self: bool = False,
    tool_name: str | None = None,
) -> Callable:
    """Decorator to enforce backend RBAC permissions on agent tool functions.

    Ensures that authorization is strictly verified in Python code before
    calling any underlying service methods. Never relies on LLMs for access decisions.

    Args:
        *allowed_roles: User roles permitted to execute this tool.
        allow_employee_self: If True, allows Employee role users, but inner tool
                             enforces self-record filtering.
        tool_name: Optional explicit name for tool telemetry and result envelope.
    """
    allowed_values = {role.value for role in allowed_roles}

    def decorator(func: Callable) -> Callable:
        name = tool_name or func.__name__

        @functools.wraps(func)
        def wrapper(
            db: Session, current_user: User, *args: Any, **kwargs: Any
        ) -> ToolResult:
            start_time = time.perf_counter()

            # 1. RBAC authorization check in backend Python
            user_role = current_user.role
            is_permitted = user_role in allowed_values
            if (
                not is_permitted
                and allow_employee_self
                and user_role == UserRole.EMPLOYEE.value
            ):
                is_permitted = True

            if not is_permitted:
                elapsed = round((time.perf_counter() - start_time) * 1000, 2)
                logger.warning(
                    "Tool access denied: user_id=%s role=%s attempted to access tool=%s (requires=%s)",
                    getattr(current_user, "id", None),
                    user_role,
                    name,
                    sorted(allowed_values),
                )
                return ToolResult(
                    success=False,
                    data=None,
                    error="Access denied: You do not have permission to access this resource or perform this action.",
                    authorized=False,
                    execution_time_ms=elapsed,
                    tool_name=name,
                )

            # 2. Safe execution boundary with error containment
            try:
                res = func(db, current_user, *args, **kwargs)
                elapsed = round((time.perf_counter() - start_time) * 1000, 2)
                return ToolResult(
                    success=True,
                    data=res,
                    error=None,
                    authorized=True,
                    execution_time_ms=elapsed,
                    tool_name=name,
                )
            except PermissionError as exc:
                elapsed = round((time.perf_counter() - start_time) * 1000, 2)
                logger.warning(
                    "Fine-grained tool access denied: user_id=%s role=%s tool=%s diagnostic=%s",
                    getattr(current_user, "id", None),
                    getattr(current_user, "role", None),
                    name,
                    exc,
                )
                return ToolResult(
                    success=False,
                    data=None,
                    error="Access denied: You do not have permission to access this resource or perform this action.",
                    authorized=False,
                    execution_time_ms=elapsed,
                    tool_name=name,
                )
            except SQLAlchemyError:
                elapsed = round((time.perf_counter() - start_time) * 1000, 2)
                return ToolResult(
                    success=False,
                    data=None,
                    error="Database query encountered an error while processing the request.",
                    authorized=True,
                    execution_time_ms=elapsed,
                    tool_name=name,
                )
            except Exception as exc:
                elapsed = round((time.perf_counter() - start_time) * 1000, 2)
                # Return clean message without leaking server paths or raw tracebacks
                return ToolResult(
                    success=False,
                    data=None,
                    error=f"Execution error in '{name}': {exc!s}",
                    authorized=True,
                    execution_time_ms=elapsed,
                    tool_name=name,
                )

        # Store metadata for tool introspection
        wrapper.__tool_name__ = name  # type: ignore[attr-defined]
        wrapper.__allowed_roles__ = allowed_values  # type: ignore[attr-defined]
        wrapper.__allow_employee_self__ = allow_employee_self  # type: ignore[attr-defined]
        return wrapper

    return decorator
