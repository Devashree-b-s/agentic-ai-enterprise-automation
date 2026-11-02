import apiClient from './api'
import type {
  DocumentDeleteResponse,
  DocumentIngestResponse,
  DocumentMetadata,
  DocumentSearchRequest,
  DocumentSearchResponse,
  RAGAnswerRequest,
  RAGAnswerResponse,
} from '../types/document.types'

export const documentService = {
  /**
   * Upload and index an enterprise document (PDF, DOCX, TXT).
   * Supports upload progress tracking.
   */
  async uploadDocument(
    file: File,
    department: string,
    roleRequired: string,
    onProgress?: (percent: number) => void,
  ): Promise<DocumentIngestResponse> {
    const formData = new FormData()
    formData.append('file', file)
    formData.append('department', department)
    formData.append('role_required', roleRequired)

    const response = await apiClient.post<DocumentIngestResponse>(
      '/documents/upload',
      formData,
      {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
        onUploadProgress: (progressEvent) => {
          if (progressEvent.total && onProgress) {
            const percent = Math.round((progressEvent.loaded * 100) / progressEvent.total)
            onProgress(percent)
          }
        },
      },
    )
    return response.data
  },

  /**
   * Retrieve all documents indexed in ChromaDB visible to the user's RBAC role.
   */
  async getDocuments(): Promise<DocumentMetadata[]> {
    const response = await apiClient.get<DocumentMetadata[]>('/documents')
    return response.data
  },

  /**
   * Execute semantic search across indexed document vector chunks.
   */
  async searchDocuments(request: DocumentSearchRequest): Promise<DocumentSearchResponse> {
    const response = await apiClient.post<DocumentSearchResponse>('/documents/search', request)
    return response.data
  },

  /**
   * Run end-to-end RAG question answering against indexed documents.
   */
  async askDocuments(request: RAGAnswerRequest): Promise<RAGAnswerResponse> {
    const response = await apiClient.post<RAGAnswerResponse>('/documents/ask', request)
    return response.data
  },

  /**
   * Delete an indexed document and all of its chunks from vector storage.
   */
  async deleteDocument(documentId: string): Promise<DocumentDeleteResponse> {
    const response = await apiClient.delete<DocumentDeleteResponse>(`/documents/${documentId}`)
    return response.data
  },
}

export default documentService
