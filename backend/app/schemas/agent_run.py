"""API schemas for retrieving persistent agent execution records."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.agent_run import AgentRunStatus


class AgentRunResponse(BaseModel):
    """Safe representation of an agent execution record."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: int | None
    agent_type: str
    status: AgentRunStatus
    conversation_id: int | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    error_summary: str | None
    result_metadata: dict[str, Any] | None


class AgentRunListResponse(BaseModel):
    """Paginated agent run list."""

    items: list[AgentRunResponse]
    total: int
    skip: int = Field(ge=0)
    limit: int = Field(ge=1)
