"""RAG document retrieval tools for LangGraph supervisor integration."""

import logging
from typing import Any

from sqlalchemy.orm import Session

from app.agents.tools.base import rbac_tool
from app.models.user import User, UserRole
from app.services.chroma_service import search_documents

logger = logging.getLogger("app.agents.tools.rag")


@rbac_tool(
    UserRole.ADMIN,
    UserRole.HR,
    UserRole.MANAGER,
    UserRole.EMPLOYEE,
    tool_name="search_enterprise_documents",
)
def search_enterprise_documents(
    db: Session,
    current_user: User,
    query: str,
    department: str | None = None,
    top_k: int = 4,
) -> dict[str, Any]:
    """Retrieve relevant excerpts from uploaded enterprise documents using semantic search.

    Available to all authenticated roles. The underlying retrieval service strictly
    enforces document-level RBAC filters so callers can never access documents beyond
    their role authorization boundary.

    Args:
        db: Active database session (unused by vector store but preserved for standard signature).
        current_user: Authenticated user executing the retrieval.
        query: Natural language question or search phrase.
        department: Optional department scope ('hr', 'sales', 'inventory', 'general').
        top_k: Maximum number of relevant document chunks to return (default: 4).
    """
    clean_query = query.strip()
    if not clean_query:
        return {
            "query": query,
            "total_found": 0,
            "chunks": [],
            "message": "Empty search query provided.",
        }

    chunks = search_documents(
        query=clean_query,
        user_role=current_user.role,
        department=department,
        top_k=top_k,
    )

    serialized_chunks = [
        {
            "chunk_id": c.chunk_id,
            "document_id": c.document_id,
            "document_name": c.document_name,
            "department": c.department,
            "role_required": c.role_required,
            "chunk_index": c.chunk_index,
            "total_chunks": c.total_chunks,
            "text": c.text,
            "similarity_score": c.similarity_score,
        }
        for c in chunks
    ]

    return {
        "query": clean_query,
        "total_found": len(serialized_chunks),
        "chunks": serialized_chunks,
        "sources": sorted({c.document_name for c in chunks}),
    }
