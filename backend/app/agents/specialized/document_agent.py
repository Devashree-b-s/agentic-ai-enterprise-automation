from typing import ClassVar

"""Specialized Document Intelligence Agent for RAG, corporate policies, and handbooks."""

from app.agents.specialized.base import BaseSpecializedAgent


class DocumentIntelligenceAgent(BaseSpecializedAgent):
    """Specialized agent responsible for Unstructured Document Intelligence and Corporate Policies.

    Capabilities:
    - Semantic vector search across uploaded enterprise documents (PDF, DOCX, TXT) via ChromaDB.
    - Retrieval of HR policies, annual leave rules, handbook guidelines, and operating procedures.
    - Strict citation extraction with document names, chunk indexes, and excerpts.
    - Prompt injection defenses and similarity threshold validation.
    """

    name = "documents"
    display_name = "Document Intelligence & Policy Specialist Agent"
    allowed_tools: ClassVar[list[str]] = [
        "search_enterprise_documents",
    ]


document_agent = DocumentIntelligenceAgent()
