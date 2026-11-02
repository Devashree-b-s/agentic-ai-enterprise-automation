"""Pydantic schemas for Conversation and Message management."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class MessageResponse(BaseModel):
    """Schema for returning an individual message in a conversation."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    conversation_id: int
    role: str = Field(..., description="'user' or 'assistant'")
    content: str
    departments_used: list[str] = Field(default_factory=list)
    tools_used: list[str] = Field(default_factory=list)
    source_attribution: str | None = None
    citations: list[dict[str, Any]] = Field(default_factory=list)
    created_at: datetime


class ConversationCreate(BaseModel):
    """Schema for creating a new conversation."""

    title: str | None = Field(
        default=None,
        max_length=255,
        description="Optional title for the conversation. If omitted, defaults to 'New Conversation'.",
    )


class ConversationUpdate(BaseModel):
    """Schema for renaming or updating a conversation title."""

    title: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="New title for the conversation.",
    )


class ConversationResponse(BaseModel):
    """Summary schema for listing conversations."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    user_id: int
    message_count: int = 0
    created_at: datetime
    updated_at: datetime


class ConversationDetailResponse(ConversationResponse):
    """Detailed conversation response including the list of messages."""

    messages: list[MessageResponse] = Field(default_factory=list)
