import React, { useState, useEffect, useMemo, useCallback } from 'react'
import {
  FileText,
  Upload,
  Search,
  Trash2,
  AlertCircle,
  CheckCircle2,
  Layers,
  Sparkles,
  RefreshCw,
  FileCode,
  FileSpreadsheet,
  FolderOpen,
  Filter,
  Eye,
  Bot,
  Database,
  ArrowRight,
  Info,
} from 'lucide-react'
import { documentService } from '../services/document.service'
import type {
  DocumentChunkResult,
  DocumentMetadata,
  RAGAnswerResponse,
} from '../types/document.types'
import { useAuthStore } from '../store/auth.store'
import Card from '../components/common/Card'
import Badge from '../components/common/Badge'
import Button from '../components/common/Button'
import Modal from '../components/common/Modal'
import ConfirmModal from '../components/common/ConfirmModal'
import LoadingSpinner from '../components/common/LoadingSpinner'
import EmptyState from '../components/common/EmptyState'

export const DocumentsPage: React.FC = () => {
  const { user } = useAuthStore()
  const userRole = user?.role || 'Employee'
  const userEmail = user?.email || ''

  const canUpload = ['Admin', 'Manager', 'HR'].includes(userRole)
  const isAdmin = userRole === 'Admin'

  // Document list state
  const [documents, setDocuments] = useState<DocumentMetadata[]>([])
  const [isLoading, setIsLoading] = useState<boolean>(true)
  const [listError, setListError] = useState<string | null>(null)
  const [searchQuery, setSearchQuery] = useState<string>('')
  const [selectedDept, setSelectedDept] = useState<string>('all')

  // Upload modal state
  const [isUploadOpen, setIsUploadOpen] = useState<boolean>(false)
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [uploadDept, setUploadDept] = useState<string>('general')
  const [uploadRole, setUploadRole] = useState<string>('Employee')
  const [uploadProgress, setUploadProgress] = useState<number>(0)
  const [isUploading, setIsUploading] = useState<boolean>(false)
  const [uploadError, setUploadError] = useState<string | null>(null)
  const [uploadSuccess, setUploadSuccess] = useState<string | null>(null)

  // Delete modal state
  const [documentToDelete, setDocumentToDelete] = useState<DocumentMetadata | null>(null)
  const [isDeleting, setIsDeleting] = useState<boolean>(false)

  // Semantic Search & Q&A state
  const [semanticQuery, setSemanticQuery] = useState<string>('')
  const [topK, setTopK] = useState<number>(4)
  const [activeTab, setActiveTab] = useState<'search' | 'ask'>('ask')
  const [isSearching, setIsSearching] = useState<boolean>(false)
  const [searchResults, setSearchResults] = useState<DocumentChunkResult[]>([])
  const [ragResponse, setRagResponse] = useState<RAGAnswerResponse | null>(null)
  const [searchFeedback, setSearchFeedback] = useState<string | null>(null)

  // Chunk inspection modal state
  const [inspectDoc, setInspectDoc] = useState<DocumentMetadata | null>(null)

  // Fetch document listing
  const fetchDocuments = useCallback(async () => {
    setIsLoading(true)
    setListError(null)
    try {
      const data = await documentService.getDocuments()
      setDocuments(data)
    } catch (err: any) {
      const msg = err.response?.data?.detail || 'Failed to load enterprise documents.'
      setListError(msg)
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    let isMounted = true
    documentService
      .getDocuments()
      .then((data) => {
        if (isMounted) {
          setDocuments(data)
          setIsLoading(false)
        }
      })
      .catch((err: any) => {
        if (isMounted) {
          setListError(err.response?.data?.detail || 'Failed to load enterprise documents.')
          setIsLoading(false)
        }
      })
    return () => {
      isMounted = false
    }
  }, [])

  // Filtered documents
  const filteredDocuments = useMemo(() => {
    return documents.filter((doc) => {
      const matchSearch =
        doc.document_name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        doc.department.toLowerCase().includes(searchQuery.toLowerCase()) ||
        doc.uploaded_by.toLowerCase().includes(searchQuery.toLowerCase())
      const matchDept = selectedDept === 'all' || doc.department.toLowerCase() === selectedDept.toLowerCase()
      return matchSearch && matchDept
    })
  }, [documents, searchQuery, selectedDept])

  // Departments list for filter
  const departmentsList = useMemo(() => {
    const depts = new Set(documents.map((d) => d.department.toLowerCase()))
    return Array.from(depts).sort()
  }, [documents])

  // Total chunks count
  const totalChunks = useMemo(() => {
    return documents.reduce((sum, d) => sum + (d.total_chunks || 0), 0)
  }, [documents])

  // Handle File Selection
  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setUploadError(null)
    setUploadSuccess(null)
    if (e.target.files && e.target.files[0]) {
      const file = e.target.files[0]
      const ext = file.name.substring(file.name.lastIndexOf('.')).toLowerCase()
      if (!['.pdf', '.docx', '.txt'].includes(ext)) {
        setUploadError(`Unsupported format '${ext}'. Please upload a PDF, DOCX, or TXT file.`)
        setSelectedFile(null)
        return
      }
      if (file.size > 10 * 1024 * 1024) {
        setUploadError('File exceeds 10 MB limit.')
        setSelectedFile(null)
        return
      }
      setSelectedFile(file)
    }
  }

  // Handle Document Upload
  const handleUploadSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!selectedFile) {
      setUploadError('Please select a file to upload.')
      return
    }

    setIsUploading(true)
    setUploadError(null)
    setUploadSuccess(null)
    setUploadProgress(0)

    try {
      const res = await documentService.uploadDocument(
        selectedFile,
        uploadDept,
        uploadRole,
        (percent) => setUploadProgress(percent),
      )
      setUploadSuccess(`Indexed successfully! Generated ${res.total_chunks} vector chunks.`)
      setSelectedFile(null)
      fetchDocuments()
      setTimeout(() => {
        setIsUploadOpen(false)
        setUploadSuccess(null)
        setUploadProgress(0)
      }, 1800)
    } catch (err: any) {
      const detail = err.response?.data?.detail
      if (err.response?.status === 422) {
        setUploadError(detail || 'Scanned or image-only PDF detected. OCR is not supported.')
      } else if (err.response?.status === 400 && detail?.includes('Duplicate document')) {
        setUploadError(detail)
      } else {
        setUploadError(detail || 'Upload failed. Please check the file and try again.')
      }
    } finally {
      setIsUploading(false)
    }
  }

  // Handle Document Deletion
  const handleDeleteConfirm = async () => {
    if (!documentToDelete) return
    setIsDeleting(true)
    try {
      await documentService.deleteDocument(documentToDelete.document_id)
      setDocuments((prev) => prev.filter((d) => d.document_id !== documentToDelete.document_id))
      setDocumentToDelete(null)
    } catch (err: any) {
      const msg = err.response?.data?.detail || 'Failed to delete document.'
      alert(`Delete Error: ${msg}`)
    } finally {
      setIsDeleting(false)
    }
  }

  // Handle Semantic Search / Ask
  const handleExecuteSearch = async (e: React.FormEvent) => {
    e.preventDefault()
    const cleanQ = semanticQuery.trim()
    if (!cleanQ) return

    setIsSearching(true)
    setSearchFeedback(null)
    setSearchResults([])
    setRagResponse(null)

    try {
      if (activeTab === 'search') {
        const res = await documentService.searchDocuments({
          query: cleanQ,
          department: selectedDept === 'all' ? null : selectedDept,
          top_k: topK,
        })
        setSearchResults(res.results)
        if (res.results.length === 0) {
          setSearchFeedback('No document chunks matched your query above the relevance threshold.')
        }
      } else {
        const res = await documentService.askDocuments({
          query: cleanQ,
          department: selectedDept === 'all' ? null : selectedDept,
          top_k: topK,
        })
        setRagResponse(res)
      }
    } catch (err: any) {
      const msg = err.response?.data?.detail || 'Semantic retrieval failed.'
      setSearchFeedback(`Error: ${msg}`)
    } finally {
      setIsSearching(false)
    }
  }

  // Format bytes
  const formatBytes = (bytes: number): string => {
    if (!bytes || bytes === 0) return '0 B'
    const k = 1024
    const sizes = ['B', 'KB', 'MB']
    const i = Math.floor(Math.log(bytes) / Math.log(k))
    return `${parseFloat((bytes / Math.pow(k, i)).toFixed(1))} ${sizes[i]}`
  }

  // Format Date
  const formatDate = (isoString: string): string => {
    if (!isoString) return 'N/A'
    try {
      return new Date(isoString).toLocaleDateString('en-US', {
        month: 'short',
        day: 'numeric',
        year: 'numeric',
      })
    } catch {
      return isoString
    }
  }

  // Get file icon
  const getFileIcon = (fileType: string) => {
    const ft = fileType.toLowerCase()
    if (ft === 'pdf') return <FileText className="w-5 h-5 text-rose-400" />
    if (ft === 'docx') return <FileSpreadsheet className="w-5 h-5 text-sky-400" />
    return <FileCode className="w-5 h-5 text-slate-300" />
  }

  // Check delete permission
  const canDeleteDoc = (doc: DocumentMetadata): boolean => {
    if (isAdmin) return true
    return doc.uploaded_by === userEmail
  }

  return (
    <div className="space-y-6">
      {/* Top Header & Action Row */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold tracking-tight text-white m-0">
              Document Intelligence & RAG
            </h1>
            <Badge variant="primary" size="sm">
              ChromaDB 1.5.9
            </Badge>
          </div>
          <p className="text-sm text-slate-400 mt-1 m-0">
            Enterprise document ingestion, ONNX embedding generation, and role-governed semantic retrieval.
          </p>
        </div>

        <div className="flex items-center gap-2.5">
          <Button
            variant="ghost"
            size="sm"
            onClick={fetchDocuments}
            disabled={isLoading}
            icon={<RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />}
          >
            Refresh
          </Button>

          {canUpload && (
            <Button
              variant="primary"
              size="sm"
              onClick={() => {
                setUploadError(null)
                setUploadSuccess(null)
                setIsUploadOpen(true)
              }}
              icon={<Upload className="w-4 h-4" />}
            >
              Upload Document
            </Button>
          )}
        </div>
      </div>

      {/* KPI Overview Strip */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <Card className="p-4 bg-slate-900/60 border-slate-800">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs font-medium text-slate-400 uppercase tracking-wider m-0">
                Indexed Documents
              </p>
              <h3 className="text-2xl font-bold text-white mt-1 m-0">
                {isLoading ? '...' : documents.length}
              </h3>
            </div>
            <div className="p-2.5 rounded-xl bg-cyan-950/40 border border-cyan-800/40 text-cyan-400">
              <FolderOpen className="w-5 h-5" />
            </div>
          </div>
          <p className="text-xs text-slate-400 mt-2 m-0 flex items-center gap-1">
            <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
            <span>Accessible by role: </span>
            <span className="font-semibold text-slate-200">{userRole}</span>
          </p>
        </Card>

        <Card className="p-4 bg-slate-900/60 border-slate-800">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs font-medium text-slate-400 uppercase tracking-wider m-0">
                Vector Chunks
              </p>
              <h3 className="text-2xl font-bold text-white mt-1 m-0">
                {isLoading ? '...' : totalChunks}
              </h3>
            </div>
            <div className="p-2.5 rounded-xl bg-indigo-950/40 border border-indigo-800/40 text-indigo-400">
              <Layers className="w-5 h-5" />
            </div>
          </div>
          <p className="text-xs text-slate-400 mt-2 m-0">
            600-char recursive chunking with 100-char overlap
          </p>
        </Card>

        <Card className="p-4 bg-slate-900/60 border-slate-800">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs font-medium text-slate-400 uppercase tracking-wider m-0">
                Embedding Model
              </p>
              <h3 className="text-base font-semibold text-white mt-1 m-0 truncate">
                all-MiniLM-L6-v2
              </h3>
            </div>
            <div className="p-2.5 rounded-xl bg-purple-950/40 border border-purple-800/40 text-purple-400">
              <Sparkles className="w-5 h-5" />
            </div>
          </div>
          <p className="text-xs text-slate-400 mt-2 m-0">
            384-dim dense vectors running via local ONNX runtime
          </p>
        </Card>

        <Card className="p-4 bg-slate-900/60 border-slate-800">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs font-medium text-slate-400 uppercase tracking-wider m-0">
                Storage Engine
              </p>
              <h3 className="text-base font-semibold text-white mt-1 m-0">
                ChromaDB HNSW
              </h3>
            </div>
            <div className="p-2.5 rounded-xl bg-emerald-950/40 border border-emerald-800/40 text-emerald-400">
              <Database className="w-5 h-5" />
            </div>
          </div>
          <p className="text-xs text-slate-400 mt-2 m-0">
            Persistent cosine distance with SHA-256 deduplication
          </p>
        </Card>
      </div>

      {/* Semantic Search & Q&A Interactive Panel */}
      <Card className="p-5 bg-gradient-to-br from-slate-900 via-slate-900 to-indigo-950/30 border-slate-800">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-4">
          <div className="flex items-center gap-2.5">
            <Bot className="w-5 h-5 text-indigo-400" />
            <h2 className="text-base font-semibold text-white m-0">
              Semantic Document Explorer & RAG Synthesis
            </h2>
          </div>
          <div className="flex items-center gap-1.5 p-1 bg-slate-800/80 rounded-xl border border-slate-700/60 text-xs">
            <button
              type="button"
              onClick={() => setActiveTab('ask')}
              className={`px-3 py-1.5 rounded-lg font-medium transition-colors cursor-pointer ${
                activeTab === 'ask'
                  ? 'bg-indigo-600 text-white shadow-xs'
                  : 'text-slate-400 hover:text-white'
              }`}
            >
              Ask Documents (RAG)
            </button>
            <button
              type="button"
              onClick={() => setActiveTab('search')}
              className={`px-3 py-1.5 rounded-lg font-medium transition-colors cursor-pointer ${
                activeTab === 'search'
                  ? 'bg-indigo-600 text-white shadow-xs'
                  : 'text-slate-400 hover:text-white'
              }`}
            >
              Semantic Vector Chunks
            </button>
          </div>
        </div>

        <form onSubmit={handleExecuteSearch} className="space-y-3">
          <div className="flex flex-col md:flex-row gap-2.5">
            <div className="relative flex-1">
              <Search className="w-4 h-4 absolute left-3.5 top-3.5 text-slate-400" />
              <input
                type="text"
                placeholder={
                  activeTab === 'ask'
                    ? "Ask a business question (e.g. 'What is the annual leave quota and vacation policy?')..."
                    : "Enter search terms to find relevant chunks (e.g. 'remote access MFA requirements')..."
                }
                value={semanticQuery}
                onChange={(e) => setSemanticQuery(e.target.value)}
                className="w-full pl-10 pr-4 py-2.5 bg-slate-950/70 border border-slate-800 rounded-xl text-sm text-slate-100 placeholder-slate-500 focus:outline-hidden focus:border-indigo-500 transition-colors"
              />
            </div>
            <div className="flex items-center gap-2">
              <select
                value={topK}
                onChange={(e) => setTopK(Number(e.target.value))}
                className="px-3 py-2.5 bg-slate-950/70 border border-slate-800 rounded-xl text-xs text-slate-300 focus:outline-hidden focus:border-indigo-500"
              >
                <option value={2}>Top 2 Chunks</option>
                <option value={4}>Top 4 Chunks</option>
                <option value={8}>Top 8 Chunks</option>
              </select>

              <Button
                type="submit"
                variant="primary"
                disabled={isSearching || !semanticQuery.trim()}
                icon={isSearching ? <LoadingSpinner size="sm" /> : <ArrowRight className="w-4 h-4" />}
              >
                {isSearching ? 'Processing...' : activeTab === 'ask' ? 'Synthesize Answer' : 'Search Chunks'}
              </Button>
            </div>
          </div>
        </form>

        {/* Search Feedback Message */}
        {searchFeedback && (
          <div className="mt-3 p-3 rounded-xl bg-amber-950/30 border border-amber-800/40 text-xs text-amber-300 flex items-center gap-2">
            <Info className="w-4 h-4 shrink-0" />
            <span>{searchFeedback}</span>
          </div>
        )}

        {/* RAG Synthesis Result Box */}
        {ragResponse && activeTab === 'ask' && (
          <div className="mt-4 p-4 rounded-xl bg-slate-950/80 border border-indigo-900/40 space-y-3">
            <div className="flex items-center justify-between border-b border-slate-800/80 pb-2.5">
              <div className="flex items-center gap-2">
                <Sparkles className="w-4 h-4 text-indigo-400" />
                <span className="text-xs font-semibold text-slate-200">
                  Enterprise AI Synthesized Response
                </span>
              </div>
              <Badge variant="primary" size="sm">
                Derived strictly from {ragResponse.sources.length} document chunk(s)
              </Badge>
            </div>

            <p className="text-sm text-slate-200 leading-relaxed m-0 whitespace-pre-wrap">
              {ragResponse.answer}
            </p>

            {ragResponse.sources.length > 0 && (
              <div className="pt-2 border-t border-slate-800/60">
                <p className="text-xs font-medium text-slate-400 uppercase tracking-wider m-0 mb-2">
                  Document Provenance & Citations:
                </p>
                <div className="flex flex-wrap gap-2">
                  {ragResponse.sources.map((s, idx) => (
                    <div
                      key={s.chunk_id || idx}
                      className="px-2.5 py-1.5 rounded-lg bg-slate-900 border border-slate-800 text-xs text-slate-300 flex items-center gap-2"
                    >
                      <FileText className="w-3.5 h-3.5 text-indigo-400" />
                      <span className="font-medium text-slate-100">{s.document_name}</span>
                      <span className="text-slate-400">(Chunk {s.chunk_index + 1}/{s.total_chunks})</span>
                      <Badge variant="success" size="sm">
                        {Math.round(s.similarity_score * 100)}% match
                      </Badge>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {/* Semantic Vector Chunks Listing */}
        {searchResults.length > 0 && activeTab === 'search' && (
          <div className="mt-4 space-y-2.5">
            <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider m-0">
              Retrieved {searchResults.length} Relevant Vector Chunks:
            </p>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {searchResults.map((c) => (
                <div
                  key={c.chunk_id}
                  className="p-3.5 rounded-xl bg-slate-950/70 border border-slate-800 space-y-2"
                >
                  <div className="flex items-center justify-between text-xs">
                    <div className="flex items-center gap-1.5 font-medium text-slate-200 truncate">
                      <FileText className="w-3.5 h-3.5 text-cyan-400 shrink-0" />
                      <span className="truncate">{c.document_name}</span>
                    </div>
                    <Badge variant="primary" size="sm">
                      {Math.round(c.similarity_score * 100)}% relevance
                    </Badge>
                  </div>
                  <p className="text-xs text-slate-300 font-mono line-clamp-3 bg-slate-900/50 p-2 rounded-lg m-0">
                    "{c.text}"
                  </p>
                  <div className="flex items-center justify-between text-[11px] text-slate-400 pt-1">
                    <span>Dept: {c.department.toUpperCase()}</span>
                    <span>Role: {c.role_required}</span>
                    <span>Chunk {c.chunk_index + 1}/{c.total_chunks}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </Card>

      {/* Document Management Table Card */}
      <Card className="p-5 bg-slate-900/70 border-slate-800 space-y-4">
        {/* Table Filters & Search */}
        <div className="flex flex-col sm:flex-row items-center justify-between gap-3">
          <div className="relative w-full sm:w-72">
            <Search className="w-4 h-4 absolute left-3 top-2.5 text-slate-400" />
            <input
              type="text"
              placeholder="Filter by document name or uploader..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-9 pr-3 py-1.5 bg-slate-950 border border-slate-800 rounded-lg text-xs text-slate-200 placeholder-slate-500 focus:outline-hidden focus:border-slate-700"
            />
          </div>

          <div className="flex items-center gap-2.5 w-full sm:w-auto">
            <div className="flex items-center gap-1.5 text-xs text-slate-400">
              <Filter className="w-3.5 h-3.5" />
              <span>Dept:</span>
            </div>
            <select
              value={selectedDept}
              onChange={(e) => setSelectedDept(e.target.value)}
              className="px-2.5 py-1.5 bg-slate-950 border border-slate-800 rounded-lg text-xs text-slate-300 focus:outline-hidden focus:border-slate-700"
            >
              <option value="all">All Departments</option>
              {departmentsList.map((dept) => (
                <option key={dept} value={dept}>
                  {dept.toUpperCase()}
                </option>
              ))}
            </select>
          </div>
        </div>

        {/* Error message */}
        {listError && (
          <div className="p-3 rounded-xl bg-rose-950/40 border border-rose-800 text-xs text-rose-300 flex items-center gap-2">
            <AlertCircle className="w-4 h-4 shrink-0" />
            <span>{listError}</span>
          </div>
        )}

        {/* Document Table */}
        <div className="overflow-x-auto rounded-xl border border-slate-800">
          <table className="w-full text-left border-collapse text-xs">
            <thead>
              <tr className="bg-slate-950/90 text-slate-400 uppercase tracking-wider border-b border-slate-800">
                <th className="py-3 px-4 font-semibold">Document Name</th>
                <th className="py-3 px-3 font-semibold">Format</th>
                <th className="py-3 px-3 font-semibold">Department</th>
                <th className="py-3 px-3 font-semibold">Role Required</th>
                <th className="py-3 px-3 font-semibold">Chunks</th>
                <th className="py-3 px-3 font-semibold">Size</th>
                <th className="py-3 px-3 font-semibold">Uploaded</th>
                <th className="py-3 px-4 font-semibold text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60 bg-slate-900/40">
              {isLoading ? (
                <tr>
                  <td colSpan={8} className="py-12 text-center text-slate-400">
                    <LoadingSpinner size="md" className="mx-auto mb-2" />
                    <span>Loading indexed enterprise documents...</span>
                  </td>
                </tr>
              ) : filteredDocuments.length === 0 ? (
                <tr>
                  <td colSpan={8} className="py-10 text-center">
                    <EmptyState
                      title="No documents found"
                      description={
                        searchQuery || selectedDept !== 'all'
                          ? 'No documents match your active filter criteria.'
                          : 'No enterprise documents have been indexed yet.'
                      }
                      icon={<FileText className="w-8 h-8 text-slate-400" />}
                    />
                  </td>
                </tr>
              ) : (
                filteredDocuments.map((doc) => {
                  const canDelete = canDeleteDoc(doc)
                  return (
                    <tr
                      key={doc.document_id}
                      className="hover:bg-slate-800/40 transition-colors group"
                    >
                      <td className="py-3 px-4 font-medium text-slate-100">
                        <div className="flex items-center gap-2.5">
                          {getFileIcon(doc.file_type)}
                          <span className="font-semibold text-slate-100 truncate max-w-[220px]">
                            {doc.document_name}
                          </span>
                        </div>
                      </td>
                      <td className="py-3 px-3">
                        <span className="uppercase font-mono text-[10px] px-1.5 py-0.5 rounded-md bg-slate-800 text-slate-300">
                          {doc.file_type}
                        </span>
                      </td>
                      <td className="py-3 px-3">
                        <span className="text-slate-300 capitalize">{doc.department}</span>
                      </td>
                      <td className="py-3 px-3">
                        <Badge
                          variant={
                            doc.role_required === 'Admin'
                              ? 'danger'
                              : doc.role_required === 'Manager'
                              ? 'primary'
                              : doc.role_required === 'HR'
                              ? 'warning'
                              : 'success'
                          }
                          size="sm"
                        >
                          {doc.role_required}
                        </Badge>
                      </td>
                      <td className="py-3 px-3 font-mono text-slate-300">
                        {doc.total_chunks}
                      </td>
                      <td className="py-3 px-3 text-slate-400">
                        {formatBytes(doc.file_size_bytes)}
                      </td>
                      <td className="py-3 px-3 text-slate-400">
                        <div>{formatDate(doc.uploaded_at)}</div>
                        <div className="text-[10px] text-slate-400 truncate max-w-[120px]">
                          {doc.uploaded_by}
                        </div>
                      </td>
                      <td className="py-3 px-4 text-right">
                        <div className="flex items-center justify-end gap-1.5">
                          <button
                            type="button"
                            title="Inspect metadata"
                            onClick={() => setInspectDoc(doc)}
                            className="p-1.5 rounded-lg hover:bg-slate-800 text-slate-400 hover:text-slate-200 transition-colors cursor-pointer"
                          >
                            <Eye className="w-3.5 h-3.5" />
                          </button>
                          {canDelete && (
                            <button
                              type="button"
                              title="Delete document"
                              onClick={() => setDocumentToDelete(doc)}
                              className="p-1.5 rounded-lg hover:bg-rose-950/60 text-slate-400 hover:text-rose-400 transition-colors cursor-pointer"
                            >
                              <Trash2 className="w-3.5 h-3.5" />
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                  )
                })
              )}
            </tbody>
          </table>
        </div>
      </Card>

      {/* Upload Document Modal */}
      {canUpload && (
        <Modal
          isOpen={isUploadOpen}
        onClose={() => {
          if (!isUploading) {
            setIsUploadOpen(false)
            setUploadError(null)
            setUploadSuccess(null)
          }
        }}
        title="Upload Enterprise Document"
        maxWidth="md"
      >
        <form onSubmit={handleUploadSubmit} className="space-y-4">
          <p className="text-xs text-slate-400 m-0 leading-relaxed">
            Upload corporate handbooks, policies, or technical guidelines. Text will be parsed,
            validated, chunked, and embedded into local ChromaDB storage.
          </p>

          {/* File input */}
          <div className="p-4 border-2 border-dashed border-slate-700 hover:border-slate-600 rounded-xl bg-slate-950/40 text-center transition-colors">
            <input
              type="file"
              id="doc-file-upload"
              accept=".pdf,.docx,.txt"
              onChange={handleFileChange}
              disabled={isUploading}
              className="hidden"
            />
            <label
              htmlFor="doc-file-upload"
              className="cursor-pointer flex flex-col items-center justify-center space-y-2"
            >
              <div className="p-3 rounded-full bg-slate-800 text-indigo-400">
                <Upload className="w-6 h-6" />
              </div>
              <div className="text-xs text-slate-300">
                {selectedFile ? (
                  <span className="font-semibold text-indigo-400">{selectedFile.name}</span>
                ) : (
                  <span>Click to select PDF, DOCX, or TXT file (Max 10 MB)</span>
                )}
              </div>
              {selectedFile && (
                <span className="text-[11px] text-slate-400">
                  {formatBytes(selectedFile.size)}
                </span>
              )}
            </label>
          </div>

          {/* Metadata selectors */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-medium text-slate-300 mb-1">
                Department Scope
              </label>
              <select
                value={uploadDept}
                onChange={(e) => setUploadDept(e.target.value)}
                disabled={isUploading}
                className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-xs text-slate-200 focus:outline-hidden focus:border-indigo-500"
              >
                <option value="general">General Corporate</option>
                <option value="hr">Human Resources</option>
                <option value="sales">Sales & Revenue</option>
                <option value="inventory">Inventory & Logistics</option>
                <option value="it">Information Technology</option>
                <option value="finance">Finance & Accounting</option>
              </select>
            </div>

            <div>
              <label className="block text-xs font-medium text-slate-300 mb-1">
                Access Restriction (RBAC)
              </label>
              <select
                value={uploadRole}
                onChange={(e) => setUploadRole(e.target.value)}
                disabled={isUploading}
                className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-xs text-slate-200 focus:outline-hidden focus:border-indigo-500"
              >
                <option value="Employee">Employee (All Staff)</option>
                {['Admin', 'Manager'].includes(userRole) && (
                  <option value="Manager">Manager & Above</option>
                )}
                {['Admin', 'HR'].includes(userRole) && <option value="HR">HR Only</option>}
                {isAdmin && <option value="Admin">Admin Confidential</option>}
              </select>
            </div>
          </div>

          {/* Upload Progress Bar */}
          {isUploading && (
            <div className="space-y-1.5 pt-1">
              <div className="flex justify-between text-xs text-slate-300">
                <span>{uploadProgress < 100 ? 'Uploading document...' : 'Extracting & Indexing into ChromaDB...'}</span>
                <span>{uploadProgress}%</span>
              </div>
              <div className="w-full h-1.5 bg-slate-800 rounded-full overflow-hidden">
                <div
                  className="h-full bg-indigo-500 transition-all duration-300"
                  style={{ width: `${uploadProgress}%` }}
                />
              </div>
            </div>
          )}

          {/* Error & Success Messages */}
          {uploadError && (
            <div className="p-3 rounded-xl bg-rose-950/40 border border-rose-800 text-xs text-rose-300 flex items-start gap-2">
              <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
              <span>{uploadError}</span>
            </div>
          )}

          {uploadSuccess && (
            <div className="p-3 rounded-xl bg-emerald-950/40 border border-emerald-800 text-xs text-emerald-300 flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4 shrink-0" />
              <span>{uploadSuccess}</span>
            </div>
          )}

          <div className="flex justify-end gap-2.5 pt-2">
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={() => setIsUploadOpen(false)}
              disabled={isUploading}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              variant="primary"
              size="sm"
              disabled={isUploading || !selectedFile}
              icon={isUploading ? <LoadingSpinner size="sm" /> : <Upload className="w-4 h-4" />}
            >
              {isUploading ? 'Indexing...' : 'Index Document'}
            </Button>
          </div>
        </form>
      </Modal>
      )}

      {/* Delete Confirmation Modal */}
      {documentToDelete && (
        <ConfirmModal
          isOpen={Boolean(documentToDelete)}
          onClose={() => setDocumentToDelete(null)}
          onConfirm={handleDeleteConfirm}
          title="Delete Document"
          message={`Are you sure you want to delete '${documentToDelete.document_name}'?`}
          details={
            <div className="space-y-1 text-slate-300">
              <p className="m-0">
                This will permanently remove the document and all its{' '}
                <strong className="text-white">{documentToDelete.total_chunks} vector chunks</strong>{' '}
                from ChromaDB.
              </p>
              <p className="text-slate-400 m-0 mt-1">
                SHA-256: <code className="text-slate-300">{documentToDelete.sha256?.substring(0, 16)}...</code>
              </p>
            </div>
          }
          confirmLabel="Delete from Vector Store"
          variant="danger"
          isLoading={isDeleting}
        />
      )}

      {/* Metadata Inspector Modal */}
      {inspectDoc && (
        <Modal
          isOpen={Boolean(inspectDoc)}
          onClose={() => setInspectDoc(null)}
          title={`Document Provenance: ${inspectDoc.document_name}`}
          maxWidth="lg"
        >
          <div className="space-y-3.5 text-xs">
            <div className="grid grid-cols-2 gap-3 p-3.5 rounded-xl bg-slate-950/70 border border-slate-800">
              <div>
                <span className="text-slate-400 block">Document UUID</span>
                <span className="font-mono text-slate-200 select-all">{inspectDoc.document_id}</span>
              </div>
              <div>
                <span className="text-slate-400 block">Department Scope</span>
                <span className="font-semibold text-slate-200 capitalize">{inspectDoc.department}</span>
              </div>
              <div>
                <span className="text-slate-400 block">RBAC Restriction</span>
                <span className="font-semibold text-slate-200">{inspectDoc.role_required}</span>
              </div>
              <div>
                <span className="text-slate-400 block">Indexed Chunks</span>
                <span className="font-mono text-slate-200">{inspectDoc.total_chunks} chunks</span>
              </div>
              <div>
                <span className="text-slate-400 block">Uploaded By</span>
                <span className="text-slate-200">{inspectDoc.uploaded_by}</span>
              </div>
              <div>
                <span className="text-slate-400 block">Uploaded At</span>
                <span className="text-slate-200">{inspectDoc.uploaded_at}</span>
              </div>
            </div>

            <div>
              <span className="text-slate-400 block mb-1">Cryptographic Fingerprint (SHA-256)</span>
              <p className="font-mono text-slate-300 bg-slate-950 p-2.5 rounded-lg border border-slate-800 break-all select-all m-0">
                {inspectDoc.sha256}
              </p>
            </div>

            <div className="flex justify-end pt-2">
              <Button variant="ghost" size="sm" onClick={() => setInspectDoc(null)}>
                Close
              </Button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  )
}

export default DocumentsPage
