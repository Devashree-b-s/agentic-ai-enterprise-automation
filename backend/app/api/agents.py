"""API router exposing the Agentic AI Supervisor and decision-support chat endpoints."""

import logging

from fastapi import APIRouter, HTTPException, status

from app.agents.supervisor import run_supervisor_chat
from app.core.config import settings
from app.core.deps import CurrentUser, DbSession
from app.schemas.agent import AgentChatRequest, AgentChatResponse
from app.services.agent_run_service import (
    AgentRunPersistenceError,
    agent_run_service,
)
from app.services.conversation_service import conversation_service

logger = logging.getLogger("app.api.agents")

router = APIRouter(prefix="/agents", tags=["Agentic AI"])


@router.post(
    "/chat",
    response_model=AgentChatResponse,
    status_code=status.HTTP_200_OK,
    summary="Chat with Enterprise Supervisor Agent",
    description=(
        "Send a natural-language business question to the Agentic AI system. "
        "The Supervisor identifies the relevant departments, executes authorized read-only tools, "
        "and synthesizes an answer based strictly on verified business data. "
        "User identity, RBAC boundaries, and persistent conversation memory are strictly enforced."
    ),
)
def chat_with_supervisor(
    request: AgentChatRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> AgentChatResponse:
    """Execute LangGraph supervisor workflow for authenticated user question with persistent memory."""
    # 1. Resolve or create conversation with ownership validation
    if request.conversation_id:
        conv = conversation_service.get_conversation_or_404(
            db=db,
            conversation_id=request.conversation_id,
            user_id=current_user.id,
        )
    else:
        # Auto-create conversation with title derived from user question
        title = request.message.strip()
        if len(title) > 40:
            title = title[:37] + "..."
        conv = conversation_service.create_conversation(
            db=db,
            user_id=current_user.id,
            title=title,
        )

    # 2. Retrieve recent message history for contextual memory window
    history_turns = conversation_service.get_recent_history(
        db=db,
        conversation_id=conv.id,
        limit=settings.CONVERSATION_HISTORY_LIMIT,
    )

    logger.info(
        "Agent chat request: user_id=%s role=%s conv_id=%s history_turns=%s query_len=%s",
        current_user.id,
        current_user.role,
        conv.id,
        len(history_turns),
        len(request.message),
    )

    # 3. Persist tracking before execution; do not execute if tracking is unavailable.
    try:
        run = agent_run_service.create_running(
            db,
            user_id=current_user.id,
            conversation_id=conv.id,
        )
    except AgentRunPersistenceError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Agent run tracking is temporarily unavailable.",
        ) from None

    # 4. Execute the supervisor and persist only bounded execution metadata.
    try:
        response = run_supervisor_chat(
            query=request.message,
            db=db,
            current_user=current_user,
            history=history_turns,
        )
    except Exception:  # noqa: BLE001 - contain workflow failures without exposing details
        response = AgentChatResponse(
            answer="An error occurred while processing your request. Please try again later.",
            success=False,
            error="Internal agent execution error.",
        )

    try:
        if response.success:
            agent_run_service.mark_completed(db, run, response)
        else:
            agent_run_service.mark_failed(db, run, "Agent execution failed.")
    except AgentRunPersistenceError:
        if response.success:
            try:
                agent_run_service.mark_failed(
                    db, run, "Execution result could not be recorded."
                )
            except AgentRunPersistenceError:
                logger.error(
                    "Agent run tracking could not record terminal status for run_id=%s",
                    run.id,
                )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Agent run tracking is temporarily unavailable.",
        ) from None

    # 5. Attach conversation_id to response
    response.conversation_id = conv.id

    # 6. Persist user message and assistant answer atomically
    try:
        conversation_service.add_message(
            db=db,
            conversation_id=conv.id,
            role="user",
            content=request.message,
        )
        conversation_service.add_message(
            db=db,
            conversation_id=conv.id,
            role="assistant",
            content=response.answer,
            departments_used=response.departments_used,
            tools_used=response.tools_used,
            source_attribution=response.source_attribution,
            citations=response.citations,
        )
    except Exception:  # noqa: BLE001 - preserve the established chat response on persistence errors
        logger.error("Failed to persist conversation messages for conv_id=%s", conv.id)

    return response
