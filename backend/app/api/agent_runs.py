"""Authenticated, owner-scoped APIs for persistent agent runs."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from app.core.deps import CurrentUser, DbSession
from app.models.agent_run import AgentRunStatus
from app.schemas.agent_run import AgentRunListResponse, AgentRunResponse
from app.services.agent_run_service import agent_run_service

router = APIRouter(prefix="/agent-runs", tags=["Agent Runs"])


@router.get(
    "",
    response_model=AgentRunListResponse,
    summary="List agent runs for the authenticated user",
)
def list_agent_runs(
    db: DbSession,
    current_user: CurrentUser,
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    run_status: Annotated[AgentRunStatus | None, Query(alias="status")] = None,
) -> AgentRunListResponse:
    runs, total = agent_run_service.list_for_user(
        db,
        user_id=current_user.id,
        skip=skip,
        limit=limit,
        status_filter=run_status,
    )
    return AgentRunListResponse(items=runs, total=total, skip=skip, limit=limit)


@router.get(
    "/{run_id}",
    response_model=AgentRunResponse,
    summary="Get an agent run owned by the authenticated user",
)
def get_agent_run(
    run_id: UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> AgentRunResponse:
    run = agent_run_service.get_for_user(
        db, run_id=str(run_id), user_id=current_user.id
    )
    if run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent run not found.",
        )
    return AgentRunResponse.model_validate(run)
