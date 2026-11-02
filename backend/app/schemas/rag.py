"""Pydantic schemas for RAG document ingestion, metadata, and semantic retrieval."""


from pydantic import BaseModel, Field


class DocumentChunkResult(BaseModel):
    """A single retrieved document chunk with similarity scoring and provenance metadata."""

    chunk_id: str = Field(..., description="Unique chunk identifier in vector database")
    document_id: str = Field(..., description="Unique ID of the parent document")
    document_name: str = Field(..., description="Original filename of the source document")
    department: str = Field(..., description="Enterprise department associated with the document")
    role_required: str = Field(..., description="Minimum RBAC role required to access this chunk")
    chunk_index: int = Field(..., description="Zero-based index of this chunk within the document")
    total_chunks: int = Field(..., description="Total number of chunks in the parent document")
    text: str = Field(..., description="Extracted text content of this chunk")
    similarity_score: float = Field(..., description="Cosine similarity score (0.0 to 1.0)")


class DocumentIngestResponse(BaseModel):
    """Response returned upon successful document parsing, chunking, and embedding."""

    document_id: str = Field(..., description="Assigned unique document UUID")
    document_name: str = Field(..., description="Sanitized filename of the uploaded document")
    file_type: str = Field(..., description="Document format (pdf, docx, txt)")
    file_size_bytes: int = Field(..., description="Size of the raw document file in bytes")
    department: str = Field(..., description="Target department scope")
    role_required: str = Field(..., description="RBAC role assigned to the document")
    total_chunks: int = Field(..., description="Number of vector chunks generated and indexed")
    sha256: str = Field(..., description="Cryptographic SHA-256 hash of the document content")
    status: str = Field(default="indexed", description="Ingestion status ('indexed', 'duplicate')")
    message: str = Field(..., description="Human-readable status message")


class DocumentMetadata(BaseModel):
    """Descriptive metadata for an indexed enterprise document."""

    document_id: str = Field(..., description="Unique document UUID")
    document_name: str = Field(..., description="Original filename")
    file_type: str = Field(..., description="File extension / type")
    file_size_bytes: int = Field(default=0, description="Size in bytes")
    department: str = Field(..., description="Department scope")
    role_required: str = Field(..., description="Required RBAC role")
    total_chunks: int = Field(..., description="Total chunks indexed")
    sha256: str = Field(..., description="SHA-256 fingerprint")
    uploaded_by: str = Field(..., description="Email of user who uploaded document")
    uploaded_at: str = Field(..., description="ISO 8601 upload timestamp")


class DocumentSearchRequest(BaseModel):
    """Request payload for semantic document search."""

    query: str = Field(..., min_length=2, max_length=500, description="Natural language search query")
    department: str | None = Field(default=None, description="Optional department filter")
    top_k: int = Field(default=4, ge=1, le=20, description="Maximum number of chunks to retrieve")


class DocumentSearchResponse(BaseModel):
    """Response envelope for semantic document retrieval."""

    query: str = Field(..., description="The queried text")
    total_found: int = Field(..., description="Number of chunks matching threshold")
    results: list[DocumentChunkResult] = Field(default_factory=list, description="Retrieved chunks")


class DocumentDeleteResponse(BaseModel):
    """Response envelope for document removal from vector store."""

    document_id: str = Field(..., description="UUID of deleted document")
    status: str = Field(default="deleted", description="Operation status")
    deleted_chunks: int = Field(..., description="Number of vector chunks removed")
    message: str = Field(..., description="Outcome summary")


class RAGAnswerRequest(BaseModel):
    """Request to answer a question using RAG document retrieval + LLM synthesis."""

    query: str = Field(..., min_length=2, max_length=1000, description="Question to answer")
    department: str | None = Field(default=None, description="Optional department filter")
    top_k: int = Field(default=4, ge=1, le=10, description="Maximum chunks to use as context")


class RAGAnswerResponse(BaseModel):
    """Synthesized response with source citations."""

    query: str = Field(..., description="Original question")
    answer: str = Field(..., description="Synthesized response strictly derived from retrieved documents")
    sources: list[DocumentChunkResult] = Field(default_factory=list, description="Retrieved source chunks")
    success: bool = Field(default=True, description="Whether answer generation succeeded")
    error: str | None = Field(default=None, description="Safe error message if retrieval failed")
