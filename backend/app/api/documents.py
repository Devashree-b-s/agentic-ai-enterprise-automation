"""API endpoints for enterprise document ingestion, semantic search, RAG Q&A, and lifecycle management."""

import logging

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status

from app.core.deps import CurrentUser, require_roles
from app.models.user import UserRole
from app.schemas.rag import (
    DocumentDeleteResponse,
    DocumentIngestResponse,
    DocumentMetadata,
    DocumentSearchRequest,
    DocumentSearchResponse,
    RAGAnswerRequest,
    RAGAnswerResponse,
)
from app.services.chroma_service import (
    delete_document,
    ingest_document,
    list_documents,
    search_documents,
)
from app.services.rag_synthesizer import generate_rag_answer

logger = logging.getLogger("app.api.documents")

router = APIRouter(prefix="/documents", tags=["RAG / Enterprise Documents"])


@router.post(
    "/upload",
    response_model=DocumentIngestResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload and index an enterprise document",
    description=(
        "Upload a PDF, DOCX, or TXT enterprise document. The document is validated, "
        "parsed safely, split into overlapping chunks, embedded using a local ONNX model, "
        "and indexed into the ChromaDB vector database with strict RBAC metadata. "
        "Allowed uploaders: Admin, HR, Manager."
    ),
    dependencies=[Depends(require_roles(UserRole.ADMIN, UserRole.HR, UserRole.MANAGER))],
)
async def upload_document(
    current_user: CurrentUser,
    file: UploadFile = File(..., description="Document file to upload (PDF, DOCX, TXT)"),  # noqa: B008
    department: str = Form(default="general", description="Enterprise department scope"),
    role_required: str = Form(default="Employee", description="Minimum role required to view document"),
) -> DocumentIngestResponse:
    """Validate, parse, chunk, embed, and store document in persistent vector database."""
    # RBAC check on target role: non-admins cannot upload Admin-only documents
    if role_required == UserRole.ADMIN.value and current_user.role != UserRole.ADMIN.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators may designate documents with Admin-only access.",
        )

    try:
        file_bytes = await file.read()
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to read uploaded file payload: {exc}",
        ) from exc

    try:
        response = ingest_document(
            file_bytes=file_bytes,
            filename=file.filename or "uploaded_document.txt",
            department=department,
            role_required=role_required,
            current_user=current_user,
        )
        return response
    except ValueError as exc:
        err_msg = str(exc)
        # Distinguish scanned/empty PDF unprocessable entity from generic format errors
        if "Scanned or image-only PDF detected" in err_msg or "contains no extractable text" in err_msg:
            raise HTTPException(
                status_code=422,
                detail=err_msg,
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=err_msg,
        ) from exc
    except Exception as exc:
        logger.exception("Document ingestion error")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while indexing the document into the vector store.",
        ) from exc


@router.get(
    "",
    response_model=list[DocumentMetadata],
    status_code=status.HTTP_200_OK,
    summary="List accessible enterprise documents",
    description="Retrieve all indexed documents accessible to the authenticated user's RBAC role.",
)
def get_documents(
    current_user: CurrentUser,
) -> list[DocumentMetadata]:
    """Retrieve distinct documents indexed in ChromaDB scoped to the user's role."""
    try:
        return list_documents(user_role=current_user.role)
    except Exception as exc:
        logger.error("Error listing documents: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve enterprise documents.",
        ) from exc


@router.post(
    "/search",
    response_model=DocumentSearchResponse,
    status_code=status.HTTP_200_OK,
    summary="Semantic document search",
    description="Search indexed documents using natural language queries with strict role-based access filtering.",
)
def search_enterprise_docs(
    request: DocumentSearchRequest,
    current_user: CurrentUser,
) -> DocumentSearchResponse:
    """Execute semantic retrieval against ChromaDB filtered by caller's RBAC boundary."""
    try:
        chunks = search_documents(
            query=request.query,
            user_role=current_user.role,
            department=request.department,
            top_k=request.top_k,
        )
        return DocumentSearchResponse(
            query=request.query,
            total_found=len(chunks),
            results=chunks,
        )
    except Exception as exc:
        logger.error("Document search error: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to perform document search.",
        ) from exc


@router.post(
    "/ask",
    response_model=RAGAnswerResponse,
    status_code=status.HTTP_200_OK,
    summary="Ask enterprise documents with RAG synthesis",
    description=(
        "Retrieve relevant document excerpts and synthesize an answer using the enterprise LLM. "
        "Strict prompt boundaries prevent untrusted documents from overriding instructions."
    ),
)
def ask_enterprise_documents(
    request: RAGAnswerRequest,
    current_user: CurrentUser,
) -> RAGAnswerResponse:
    """Execute end-to-end RAG: retrieve chunks, build isolated context, synthesize answer with citations."""
    try:
        chunks = search_documents(
            query=request.query,
            user_role=current_user.role,
            department=request.department,
            top_k=request.top_k,
        )
        return generate_rag_answer(query=request.query, chunks=chunks)
    except Exception as exc:
        logger.error("RAG Q&A error: %s", exc)
        return RAGAnswerResponse(
            query=request.query,
            answer="An error occurred while generating the document answer.",
            sources=[],
            success=False,
            error=str(exc),
        )


@router.delete(
    "/{document_id}",
    response_model=DocumentDeleteResponse,
    status_code=status.HTTP_200_OK,
    summary="Delete indexed document",
    description="Remove an indexed document and all of its chunks from ChromaDB. Restricted to Admin or original uploader.",
)
def delete_enterprise_document(
    document_id: str,
    current_user: CurrentUser,
) -> DocumentDeleteResponse:
    """Delete document chunks from vector database with authorization checks."""
    try:
        return delete_document(document_id=document_id, current_user=current_user)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except PermissionError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        logger.error("Error deleting document '%s': %s", document_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete document from vector database.",
        ) from exc
