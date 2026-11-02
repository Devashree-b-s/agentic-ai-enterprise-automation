"""API router for managing user conversations and persistent chat history."""

import logging

from fastapi import APIRouter, status

from app.core.deps import CurrentUser, DbSession
from app.schemas.conversation import (
    ConversationCreate,
    ConversationDetailResponse,
    ConversationResponse,
    ConversationUpdate,
)
from app.services.conversation_service import conversation_service

logger = logging.getLogger("app.api.conversations")

router = APIRouter(prefix="/conversations", tags=["Conversations"])


@router.get(
    "",
    response_model=list[ConversationResponse],
    status_code=status.HTTP_200_OK,
    summary="List current user conversations",
    description="Retrieve all conversation sessions owned by the authenticated user, ordered by latest activity.",
)
def list_user_conversations(
    db: DbSession,
    current_user: CurrentUser,
) -> list[ConversationResponse]:
    """List conversations owned by current user."""
    return conversation_service.list_conversations(db=db, user_id=current_user.id)


@router.post(
    "",
    response_model=ConversationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new conversation",
    description="Initialize a new conversation session for the authenticated user.",
)
def create_conversation(
    payload: ConversationCreate,
    db: DbSession,
    current_user: CurrentUser,
) -> ConversationResponse:
    """Create a new conversation session."""
    conv = conversation_service.create_conversation(
        db=db, user_id=current_user.id, title=payload.title
    )
    return ConversationResponse(
        id=conv.id,
        title=conv.title,
        user_id=conv.user_id,
        message_count=0,
        created_at=conv.created_at,
        updated_at=conv.updated_at,
    )


@router.get(
    "/{conversation_id}",
    response_model=ConversationDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Get conversation detail with message history",
    description="Retrieve full message history for a conversation owned by the authenticated user.",
)
def get_conversation_detail(
    conversation_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> ConversationDetailResponse:
    """Fetch conversation details and messages with strict ownership verification."""
    return conversation_service.get_conversation_detail(
        db=db, conversation_id=conversation_id, user_id=current_user.id
    )


@router.patch(
    "/{conversation_id}",
    response_model=ConversationResponse,
    status_code=status.HTTP_200_OK,
    summary="Rename conversation title",
    description="Update the title of an existing conversation owned by the authenticated user.",
)
def update_conversation(
    conversation_id: int,
    payload: ConversationUpdate,
    db: DbSession,
    current_user: CurrentUser,
) -> ConversationResponse:
    """Update conversation title."""
    return conversation_service.update_conversation_title(
        db=db,
        conversation_id=conversation_id,
        user_id=current_user.id,
        title=payload.title,
    )


@router.delete(
    "/{conversation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete conversation",
    description="Permanently delete a conversation session and all its messages.",
)
def delete_conversation(
    conversation_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> None:
    """Delete conversation with strict ownership check."""
    conversation_service.delete_conversation(
        db=db, conversation_id=conversation_id, user_id=current_user.id
    )
