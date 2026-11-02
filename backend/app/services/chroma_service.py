"""Enterprise ChromaDB vector storage, document indexing, and role-filtered semantic retrieval."""

import hashlib
import logging
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import chromadb
from chromadb.api import ClientAPI
from chromadb.utils import embedding_functions

from app.core.config import settings
from app.models.user import User, UserRole
from app.schemas.rag import (
    DocumentChunkResult,
    DocumentDeleteResponse,
    DocumentIngestResponse,
    DocumentMetadata,
)
from app.services.document_parser import (
    chunk_text,
    extract_document_text,
    validate_file_upload,
)

logger = logging.getLogger("app.services.rag")

# Role visibility hierarchy: higher roles inherit access to lower/peer documents
ROLE_ACCESS_HIERARCHY: dict[str, list[str]] = {
    UserRole.ADMIN.value: [
        UserRole.ADMIN.value,
        UserRole.MANAGER.value,
        UserRole.HR.value,
        UserRole.EMPLOYEE.value,
    ],
    UserRole.MANAGER.value: [
        UserRole.MANAGER.value,
        UserRole.EMPLOYEE.value,
    ],
    UserRole.HR.value: [
        UserRole.HR.value,
        UserRole.EMPLOYEE.value,
    ],
    UserRole.EMPLOYEE.value: [
        UserRole.EMPLOYEE.value,
    ],
}

# Cached singleton Chroma client and embedding function
_chroma_client: ClientAPI | None = None
_default_embedding_fn: Any | None = None


def get_embedding_function() -> Any:
    """Retrieve or initialize the local ONNX all-MiniLM-L6-v2 embedding function."""
    global _default_embedding_fn
    if _default_embedding_fn is None:
        logger.info("Initializing Chroma DefaultEmbeddingFunction (all-MiniLM-L6-v2 ONNX)")
        _default_embedding_fn = embedding_functions.DefaultEmbeddingFunction()
    return _default_embedding_fn


def get_chroma_client(persist_dir: str | None = None) -> ClientAPI:
    """Retrieve or initialize the persistent ChromaDB client."""
    global _chroma_client
    target_dir = persist_dir or settings.CHROMA_PERSIST_DIR
    Path(target_dir).mkdir(parents=True, exist_ok=True)

    if _chroma_client is None or persist_dir is not None:
        client = chromadb.PersistentClient(path=target_dir)
        if persist_dir is None:
            _chroma_client = client
        return client

    return _chroma_client


def get_collection(
    client: ClientAPI | None = None,
    collection_name: str | None = None,
) -> Any:
    """Get or create the Chroma collection with the standard embedding function."""
    c = client or get_chroma_client()
    name = collection_name or settings.RAG_COLLECTION_NAME
    embed_fn = get_embedding_function()
    return c.get_or_create_collection(
        name=name,
        embedding_function=embed_fn,
        metadata={"hnsw:space": "cosine"},
    )


def compute_sha256(file_bytes: bytes) -> str:
    """Compute the SHA-256 checksum for document deduplication."""
    return hashlib.sha256(file_bytes).hexdigest()


def ingest_document(
    file_bytes: bytes,
    filename: str,
    department: str,
    role_required: str,
    current_user: User,
    client: ClientAPI | None = None,
    collection_name: str | None = None,
) -> DocumentIngestResponse:
    """Process, chunk, embed, and index an enterprise document into ChromaDB.

    Enforces validation, duplicate detection, and source metadata provenance.
    """
    # 1. Validate file format and size
    safe_filename, file_type = validate_file_upload(
        filename=filename,
        file_bytes=file_bytes,
        max_size_bytes=settings.RAG_MAX_UPLOAD_SIZE_BYTES,
    )

    # 2. Normalize metadata fields
    norm_department = department.strip().lower()
    norm_role = role_required.strip()
    valid_roles = {r.value for r in UserRole}
    if norm_role not in valid_roles:
        norm_role = UserRole.EMPLOYEE.value

    # 3. Compute cryptographic fingerprint
    sha256_hash = compute_sha256(file_bytes)

    # 4. Check for duplicate ingestion in vector database
    coll = get_collection(client=client, collection_name=collection_name)
    existing = coll.get(where={"sha256": sha256_hash}, limit=1)
    if existing and existing.get("ids"):
        existing_meta = existing["metadatas"][0] if existing.get("metadatas") else {}
        raise ValueError(
            f"Duplicate document detected: '{safe_filename}' has already been indexed as "
            f"'{existing_meta.get('document_name', 'unknown')}' (ID: {existing_meta.get('document_id')})."
        )

    # 5. Extract text safely
    extracted_text = extract_document_text(file_bytes, file_type)

    # 6. Chunk text into overlapping segments
    chunks = chunk_text(
        text=extracted_text,
        chunk_size=settings.RAG_CHUNK_SIZE,
        chunk_overlap=settings.RAG_CHUNK_OVERLAP,
    )
    if not chunks:
        raise ValueError("Document contains no valid chunks after processing.")

    # 7. Generate unique IDs and provenance metadata
    doc_id = str(uuid.uuid4())
    upload_timestamp = datetime.now(UTC).isoformat()
    uploader_email = getattr(current_user, "email", "system@enterprise.internal")

    chunk_ids: list[str] = []
    chunk_metadatas: list[dict[str, Any]] = []

    for idx, chunk_content in enumerate(chunks):
        c_id = f"{doc_id}_chunk_{idx}"
        chunk_ids.append(c_id)
        chunk_metadatas.append(
            {
                "document_id": doc_id,
                "document_name": safe_filename,
                "department": norm_department,
                "role_required": norm_role,
                "chunk_index": idx,
                "total_chunks": len(chunks),
                "sha256": sha256_hash,
                "file_type": file_type,
                "file_size_bytes": len(file_bytes),
                "uploaded_by": uploader_email,
                "uploaded_at": upload_timestamp,
            }
        )

    # 8. Index into Chroma collection
    coll.add(
        ids=chunk_ids,
        documents=chunks,
        metadatas=chunk_metadatas,
    )

    logger.info(
        "Successfully indexed document '%s' (id=%s, department=%s, role=%s, chunks=%s)",
        safe_filename,
        doc_id,
        norm_department,
        norm_role,
        len(chunks),
    )

    return DocumentIngestResponse(
        document_id=doc_id,
        document_name=safe_filename,
        file_type=file_type,
        file_size_bytes=len(file_bytes),
        department=norm_department,
        role_required=norm_role,
        total_chunks=len(chunks),
        sha256=sha256_hash,
        status="indexed",
        message=f"Document '{safe_filename}' successfully processed and indexed into {len(chunks)} chunks.",
    )


def search_documents(
    query: str,
    user_role: str,
    department: str | None = None,
    top_k: int | None = None,
    score_threshold: float | None = None,
    client: ClientAPI | None = None,
    collection_name: str | None = None,
) -> list[DocumentChunkResult]:
    """Perform role-restricted semantic retrieval across indexed enterprise documents.

    Never allows unauthorized users to retrieve restricted chunks.
    """
    clean_query = query.strip()
    if not clean_query:
        return []

    coll = get_collection(client=client, collection_name=collection_name)
    total_docs = coll.count()
    if total_docs == 0:
        return []

    # 1. Determine allowed roles for this user
    allowed_roles = ROLE_ACCESS_HIERARCHY.get(user_role, [UserRole.EMPLOYEE.value])

    # 2. Build Chroma metadata where filter
    role_filter = (
        {"role_required": {"$in": allowed_roles}}
        if len(allowed_roles) > 1
        else {"role_required": allowed_roles[0]}
    )

    if department and department.strip():
        norm_dept = department.strip().lower()
        where_filter: dict[str, Any] = {
            "$and": [
                role_filter,
                {"department": norm_dept},
            ]
        }
    else:
        where_filter = role_filter

    k = min(top_k or settings.RAG_TOP_K, total_docs)
    threshold = (
        score_threshold
        if score_threshold is not None
        else settings.RAG_SIMILARITY_THRESHOLD
    )

    try:
        results = coll.query(
            query_texts=[clean_query],
            n_results=k,
            where=where_filter,
        )
    except Exception as exc:
        logger.error("ChromaDB query error with filter %s: %s", where_filter, exc)
        return []

    output_chunks: list[DocumentChunkResult] = []

    if not results or not results.get("ids") or not results["ids"][0]:
        return []

    ids = results["ids"][0]
    docs = results["documents"][0] if results.get("documents") else []
    metas = results["metadatas"][0] if results.get("metadatas") else []
    distances = results["distances"][0] if results.get("distances") else []

    for i, chunk_id in enumerate(ids):
        # In Chroma with cosine distance, distance is in [0, 2], where 0 is identical
        dist = distances[i] if i < len(distances) else 1.0
        # Cosine similarity = 1.0 - distance
        similarity = max(0.0, min(1.0, 1.0 - dist))

        if similarity < threshold:
            continue

        meta = metas[i] if i < len(metas) else {}
        doc_text = docs[i] if i < len(docs) else ""

        output_chunks.append(
            DocumentChunkResult(
                chunk_id=chunk_id,
                document_id=str(meta.get("document_id", "")),
                document_name=str(meta.get("document_name", "Unknown Document")),
                department=str(meta.get("department", "general")),
                role_required=str(meta.get("role_required", UserRole.EMPLOYEE.value)),
                chunk_index=int(meta.get("chunk_index", 0)),
                total_chunks=int(meta.get("total_chunks", 1)),
                text=doc_text,
                similarity_score=round(similarity, 4),
            )
        )

    return output_chunks


def list_documents(
    user_role: str,
    client: ClientAPI | None = None,
    collection_name: str | None = None,
) -> list[DocumentMetadata]:
    """List all indexed documents accessible to the specified user role."""
    coll = get_collection(client=client, collection_name=collection_name)
    if coll.count() == 0:
        return []

    allowed_roles = ROLE_ACCESS_HIERARCHY.get(user_role, [UserRole.EMPLOYEE.value])
    where_filter = (
        {"role_required": {"$in": allowed_roles}}
        if len(allowed_roles) > 1
        else {"role_required": allowed_roles[0]}
    )

    records = coll.get(where=where_filter)
    if not records or not records.get("metadatas"):
        return []

    # Aggregate chunk metadatas by document_id
    doc_map: dict[str, DocumentMetadata] = {}
    for meta in records["metadatas"]:
        doc_id = str(meta.get("document_id", ""))
        if not doc_id or doc_id in doc_map:
            continue

        doc_map[doc_id] = DocumentMetadata(
            document_id=doc_id,
            document_name=str(meta.get("document_name", "")),
            file_type=str(meta.get("file_type", "txt")),
            file_size_bytes=int(meta.get("file_size_bytes", 0)),
            department=str(meta.get("department", "general")),
            role_required=str(meta.get("role_required", UserRole.EMPLOYEE.value)),
            total_chunks=int(meta.get("total_chunks", 1)),
            sha256=str(meta.get("sha256", "")),
            uploaded_by=str(meta.get("uploaded_by", "")),
            uploaded_at=str(meta.get("uploaded_at", "")),
        )

    return sorted(doc_map.values(), key=lambda d: d.uploaded_at, reverse=True)


def delete_document(
    document_id: str,
    current_user: User,
    client: ClientAPI | None = None,
    collection_name: str | None = None,
) -> DocumentDeleteResponse:
    """Delete an indexed document and all its chunks from the vector database.

    Enforces that only Admin users or the original uploader can delete documents.
    """
    coll = get_collection(client=client, collection_name=collection_name)
    existing = coll.get(where={"document_id": document_id})

    if not existing or not existing.get("ids") or len(existing["ids"]) == 0:
        raise ValueError(f"Document with ID '{document_id}' not found.")

    # Check authorization: Admin can delete any doc; others only if they are the uploader
    first_meta = existing["metadatas"][0] if existing.get("metadatas") else {}
    uploader_email = first_meta.get("uploaded_by")

    is_admin = current_user.role == UserRole.ADMIN.value
    is_uploader = uploader_email and current_user.email == uploader_email

    if not (is_admin or is_uploader):
        raise PermissionError("Access denied: You do not have permission to delete this document.")

    chunk_ids = existing["ids"]
    coll.delete(ids=chunk_ids)

    logger.info(
        "Deleted document '%s' (%s chunks) by user %s",
        document_id,
        len(chunk_ids),
        current_user.email,
    )

    return DocumentDeleteResponse(
        document_id=document_id,
        status="deleted",
        deleted_chunks=len(chunk_ids),
        message=f"Successfully removed document '{first_meta.get('document_name')}' and {len(chunk_ids)} vector chunks.",
    )
