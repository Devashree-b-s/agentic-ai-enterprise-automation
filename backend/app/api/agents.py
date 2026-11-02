"""API router exposing the Agentic AI Supervisor and decision-support chat endpoints."""

import logging

from fastapi import APIRouter, status

from app.agents.supervisor import run_supervisor_chat
from app.core.config import settings
from app.core.deps import CurrentUser, DbSession
from app.schemas.agent import AgentChatRequest, AgentChatResponse
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

    # 3. Execute Supervisor workflow with context
    response = run_supervisor_chat(
        query=request.message,
        db=db,
        current_user=current_user,
        history=history_turns,
    )

    # 4. Attach conversation_id to response
    response.conversation_id = conv.id

    # 5. Persist user message and assistant answer atomically
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
    except Exception as exc:
        logger.error("Failed to persist conversation messages for conv_id=%s: %s", conv.id, exc)

    return response
