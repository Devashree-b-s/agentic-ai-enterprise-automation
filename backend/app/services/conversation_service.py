"""Service layer for conversation and persistent message management."""

import json
import logging
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.conversation import Conversation, ConversationMessage
from app.schemas.conversation import (
    ConversationDetailResponse,
    ConversationResponse,
    MessageResponse,
)

logger = logging.getLogger("app.services.conversation")


class ConversationService:
    """Encapsulates all persistent conversation CRUD operations and history retrieval."""

    @staticmethod
    def list_conversations(db: Session, user_id: int) -> list[ConversationResponse]:
        """List all conversations owned by the specified user, ordered by latest activity."""
        # Query conversations with message counts in a single efficient query
        stmt = (
            select(
                Conversation,
                func.count(ConversationMessage.id).label("msg_count"),
            )
            .outerjoin(ConversationMessage, Conversation.id == ConversationMessage.conversation_id)
            .where(Conversation.user_id == user_id)
            .group_by(Conversation.id)
            .order_by(Conversation.updated_at.desc())
        )
        rows = db.execute(stmt).all()

        results: list[ConversationResponse] = []
        for conv, count in rows:
            results.append(
                ConversationResponse(
                    id=conv.id,
                    title=conv.title,
                    user_id=conv.user_id,
                    message_count=count,
                    created_at=conv.created_at,
                    updated_at=conv.updated_at,
                )
            )
        return results

    @staticmethod
    def create_conversation(
        db: Session, user_id: int, title: str | None = None
    ) -> Conversation:
        """Create a new conversation session owned by user_id."""
        clean_title = (title or "New Conversation").strip()
        if not clean_title:
            clean_title = "New Conversation"

        conv = Conversation(
            user_id=user_id,
            title=clean_title[:255],
        )
        db.add(conv)
        db.commit()
        db.refresh(conv)
        logger.info("Created conversation id=%s for user_id=%s", conv.id, user_id)
        return conv

    @staticmethod
    def get_conversation_or_404(
        db: Session, conversation_id: int, user_id: int
    ) -> Conversation:
        """Retrieve conversation by ID enforcing strict user ownership.

        Raises 404 if conversation does not exist.
        Raises 403 Forbidden if conversation belongs to another user.
        """
        conv = db.get(Conversation, conversation_id)
        if not conv:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Conversation {conversation_id} not found.",
            )

        if conv.user_id != user_id:
            logger.warning(
                "Unauthorized conversation access attempt: user_id=%s tried to access conv_id=%s owned by user_id=%s",
                user_id,
                conversation_id,
                conv.user_id,
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: You do not have permission to view or modify this conversation.",
            )

        return conv

    @classmethod
    def get_conversation_detail(
        cls, db: Session, conversation_id: int, user_id: int
    ) -> ConversationDetailResponse:
        """Fetch conversation details with full message history."""
        conv = cls.get_conversation_or_404(db, conversation_id, user_id)

        messages = (
            db.scalars(
                select(ConversationMessage)
                .where(ConversationMessage.conversation_id == conversation_id)
                .order_by(ConversationMessage.id.asc())
            ).all()
        )

        msg_responses = [
            MessageResponse(
                id=m.id,
                conversation_id=m.conversation_id,
                role=m.role,
                content=m.content,
                departments_used=m.get_departments(),
                tools_used=m.get_tools(),
                source_attribution=m.source_attribution,
                citations=m.get_citations(),
                created_at=m.created_at,
            )
            for m in messages
        ]

        return ConversationDetailResponse(
            id=conv.id,
            title=conv.title,
            user_id=conv.user_id,
            message_count=len(messages),
            created_at=conv.created_at,
            updated_at=conv.updated_at,
            messages=msg_responses,
        )

    @classmethod
    def update_conversation_title(
        cls, db: Session, conversation_id: int, user_id: int, title: str
    ) -> ConversationResponse:
        """Rename an existing conversation."""
        conv = cls.get_conversation_or_404(db, conversation_id, user_id)
        clean_title = title.strip()
        if not clean_title:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Conversation title cannot be empty.",
            )

        conv.title = clean_title[:255]
        db.commit()
        db.refresh(conv)

        count = (
            db.scalar(
                select(func.count(ConversationMessage.id)).where(
                    ConversationMessage.conversation_id == conv.id
                )
            )
            or 0
        )

        return ConversationResponse(
            id=conv.id,
            title=conv.title,
            user_id=conv.user_id,
            message_count=count,
            created_at=conv.created_at,
            updated_at=conv.updated_at,
        )

    @classmethod
    def delete_conversation(
        cls, db: Session, conversation_id: int, user_id: int
    ) -> None:
        """Delete an entire conversation and all its messages."""
        conv = cls.get_conversation_or_404(db, conversation_id, user_id)
        db.delete(conv)
        db.commit()
        logger.info("Deleted conversation id=%s for user_id=%s", conversation_id, user_id)

    @staticmethod
    def add_message(
        db: Session,
        conversation_id: int,
        role: str,
        content: str,
        departments_used: list[str] | None = None,
        tools_used: list[str] | None = None,
        source_attribution: str | None = None,
        citations: list[dict[str, Any]] | None = None,
    ) -> ConversationMessage:
        """Append a message to the conversation and touch the conversation's updated_at."""
        msg = ConversationMessage(
            conversation_id=conversation_id,
            role=role.strip().lower(),
            content=content,
            departments_used=json.dumps(departments_used) if departments_used else None,
            tools_used=json.dumps(tools_used) if tools_used else None,
            source_attribution=source_attribution,
            citations=json.dumps(citations) if citations else None,
        )
        db.add(msg)

        # Update conversation updated_at
        conv = db.get(Conversation, conversation_id)
        if conv:
            conv.updated_at = func.now()

        db.commit()
        db.refresh(msg)
        return msg

    @staticmethod
    def get_recent_history(
        db: Session, conversation_id: int, limit: int = 10
    ) -> list[dict[str, str]]:
        """Retrieve recent chronological turns for LLM conversation window."""
        # Get the last N messages
        recent_msgs = (
            db.scalars(
                select(ConversationMessage)
                .where(ConversationMessage.conversation_id == conversation_id)
                .order_by(ConversationMessage.id.desc())
                .limit(limit)
            ).all()
        )
        # Reverse to chronological order (oldest first)
        ordered = list(reversed(recent_msgs))
        return [{"role": m.role, "content": m.content} for m in ordered]


conversation_service = ConversationService()
