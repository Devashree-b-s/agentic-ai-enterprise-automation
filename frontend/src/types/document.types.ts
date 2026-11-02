/**
 * Types matching the FastAPI backend RAG and Document Management schemas.
 */

export interface DocumentMetadata {
  document_id: string
  document_name: string
  file_type: string
  file_size_bytes: number
  department: string
  role_required: string
  total_chunks: number
  sha256: string
  uploaded_by: string
  uploaded_at: string
}

export interface DocumentChunkResult {
  chunk_id: string
  document_id: string
  document_name: string
  department: string
  role_required: string
  chunk_index: number
  total_chunks: number
  text: string
  similarity_score: number
}

export interface DocumentIngestResponse {
  document_id: string
  document_name: string
  file_type: string
  file_size_bytes: number
  department: string
  role_required: string
  total_chunks: number
  sha256: string
  status: string
  message: string
}

export interface DocumentSearchRequest {
  query: string
  department?: string | null
  top_k?: number
}

export interface DocumentSearchResponse {
  query: string
  total_found: number
  results: DocumentChunkResult[]
}

export interface DocumentDeleteResponse {
  document_id: string
  status: string
  deleted_chunks: number
  message: string
}

export interface RAGAnswerRequest {
  query: string
  department?: string | null
  top_k?: number
}

export interface RAGAnswerResponse {
  query: string
  answer: string
  sources: DocumentChunkResult[]
  success: boolean
  error?: string | null
}
