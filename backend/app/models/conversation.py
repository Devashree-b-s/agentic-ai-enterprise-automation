"""Conversation and Message database models for persistent AI memory."""

import json
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.user import User


class Conversation(Base):
    """Persistent chat conversation session owned by an authenticated user."""

    __tablename__ = "conversations"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(
        String(255), default="New Conversation", nullable=False
    )
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )

    user: Mapped["User"] = relationship("User", back_populates="conversations")
    messages: Mapped[list["ConversationMessage"]] = relationship(
        "ConversationMessage",
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="ConversationMessage.id.asc()",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<Conversation(id={self.id}, user_id={self.user_id}, title='{self.title}')>"


class ConversationMessage(Base):
    """Individual message record within a conversation (user query or assistant response)."""

    __tablename__ = "conversation_messages"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    conversation_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("conversations.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    role: Mapped[str] = mapped_column(
        String(20), nullable=False
    )  # 'user' | 'assistant'
    content: Mapped[str] = mapped_column(Text, nullable=False)

    # Tool execution and attribution metadata
    departments_used: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )  # JSON list
    tools_used: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON list
    source_attribution: Mapped[str | None] = mapped_column(String(50), nullable=True)
    citations: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )  # JSON list of dicts

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        nullable=False,
    )

    conversation: Mapped["Conversation"] = relationship(
        "Conversation", back_populates="messages"
    )

    def get_departments(self) -> list[str]:
        if not self.departments_used:
            return []
        try:
            return json.loads(self.departments_used)
        except (json.JSONDecodeError, TypeError):
            return []

    def get_tools(self) -> list[str]:
        if not self.tools_used:
            return []
        try:
            return json.loads(self.tools_used)
        except (json.JSONDecodeError, TypeError):
            return []

    def get_citations(self) -> list[dict[str, Any]]:
        if not self.citations:
            return []
        try:
            return json.loads(self.citations)
        except (json.JSONDecodeError, TypeError):
            return []

    def __repr__(self) -> str:
        return f"<ConversationMessage(id={self.id}, conv_id={self.conversation_id}, role='{self.role}')>"
