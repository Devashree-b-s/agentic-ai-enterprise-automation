from typing import Any

from pydantic import BaseModel, Field


class AgentChatRequest(BaseModel):
    """User query request for the Agentic AI system."""

    message: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="Natural-language business question across HR, Sales, Inventory, or Analytics.",
        examples=["How many employees are in the Engineering department?"],
    )
    conversation_id: int | None = Field(
        default=None,
        description="Optional ID of an existing conversation to continue. If omitted, a new conversation is created.",
    )


class AgentChatResponse(BaseModel):
    """Structured response returned by the Agentic AI supervisor workflow."""

    answer: str = Field(
        ...,
        description="Synthesized, factual natural-language answer based strictly on tool results.",
    )
    departments_used: list[str] = Field(
        default_factory=list,
        description="List of enterprise departments queried (e.g. 'hr', 'sales', 'inventory', 'analytics').",
    )
    agents_involved: list[str] = Field(
        default_factory=list,
        description="List of specialized agents that coordinated to produce the response.",
    )
    tools_used: list[str] = Field(
        default_factory=list,
        description="Names of the specific backend tools invoked to answer the query.",
    )
    success: bool = Field(
        default=True,
        description="Whether the supervisor workflow completed successfully.",
    )
    error: str | None = Field(
        default=None,
        description="Safe, non-leaking error description if query execution failed or was rejected.",
    )
    source_attribution: str | None = Field(
        default=None,
        description="Origin of answer data: 'database', 'documents', or 'hybrid'.",
    )
    citations: list[dict[str, Any]] = Field(
        default_factory=list,
        description="List of document citations with document_name, chunk_index, and excerpt.",
    )
    conversation_id: int | None = Field(
        default=None,
        description="Database ID of the conversation where this exchange is stored.",
    )
