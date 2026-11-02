import React, { useState, useEffect, useCallback } from 'react'
import {
  CheckSquare,
  Clock,
  CheckCircle2,
  XCircle,
  Play,
  RotateCcw,
  Package,
  Calendar,
  AlertTriangle,
  History,
  FileCheck,
  User as UserIcon,
  Copy,
  Check,
  Search,
  Eye,
  X,
  Shield,
  Layers,
} from 'lucide-react'
import { approvalService } from '../services/approval.service'
import type {
  ApprovalDetail,
  ApprovalMetrics,
  ApprovalRequest,
  ApprovalStatus,
} from '../types/approval.types'
import { useAuthStore } from '../store/auth.store'
import Card from '../components/common/Card'
import Badge from '../components/common/Badge'
import Button from '../components/common/Button'
import LoadingSpinner from '../components/common/LoadingSpinner'

export const ApprovalsPage: React.FC = () => {
  const { user } = useAuthStore()

  // State
  const [requests, setRequests] = useState<ApprovalRequest[]>([])
  const [metrics, setMetrics] = useState<ApprovalMetrics | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [isRefreshing, setIsRefreshing] = useState(false)
  const [selectedStatus, setSelectedStatus] = useState<string>('PENDING')
  const [selectedType, setSelectedType] = useState<string>('ALL')
  const [myRequestsOnly, setMyRequestsOnly] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')

  // Detail Modal
  const [detailModalOpen, setDetailModalOpen] = useState(false)
  const [selectedRequest, setSelectedRequest] = useState<ApprovalDetail | null>(null)
  const [isLoadingDetail, setIsLoadingDetail] = useState(false)
  const [reviewReason, setReviewReason] = useState('')
  const [actionError, setActionError] = useState<string | null>(null)
  const [isSubmittingAction, setIsSubmittingAction] = useState(false)
  const [copiedCode, setCopiedCode] = useState<string | null>(null)

  const fetchData = useCallback(async () => {
    try {
      const [listData, metricsData] = await Promise.all([
        approvalService.list(selectedStatus, selectedType, myRequestsOnly),
        approvalService.getMetrics(),
      ])
      setRequests(listData)
      setMetrics(metricsData)
    } catch (err) {
      console.error('Failed to fetch approval data:', err)
    } finally {
      setIsLoading(false)
      setIsRefreshing(false)
    }
  }, [selectedStatus, selectedType, myRequestsOnly])

  useEffect(() => {
    let ignore = false
    Promise.all([
      approvalService.list(selectedStatus, selectedType, myRequestsOnly),
      approvalService.getMetrics(),
    ])
      .then(([listData, metricsData]) => {
        if (!ignore) {
          setRequests(listData)
          setMetrics(metricsData)
        }
      })
      .catch((err) => {
        if (!ignore) console.error('Failed to fetch approval data:', err)
      })
      .finally(() => {
        if (!ignore) setIsLoading(false)
      })

    return () => {
      ignore = true
    }
  }, [selectedStatus, selectedType, myRequestsOnly])

  const openDetail = async (reqId: number) => {
    try {
      setIsLoadingDetail(true)
      setActionError(null)
      setReviewReason('')
      setDetailModalOpen(true)
      const detail = await approvalService.getDetail(reqId)
      setSelectedRequest(detail)
    } catch (err: any) {
      console.error('Failed to load detail:', err)
      setActionError(err.response?.data?.detail || 'Failed to load details')
    } finally {
      setIsLoadingDetail(false)
    }
  }

  const handleApprove = async (id: number) => {
    try {
      setIsSubmittingAction(true)
      setActionError(null)
      await approvalService.approve(id, reviewReason || undefined)
      await fetchData()
      if (selectedRequest && selectedRequest.id === id) {
        const updated = await approvalService.getDetail(id)
        setSelectedRequest(updated)
      }
    } catch (err: any) {
      setActionError(err.response?.data?.detail || 'Failed to approve request')
    } finally {
      setIsSubmittingAction(false)
    }
  }

  const handleReject = async (id: number) => {
    if (!reviewReason.trim()) {
      setActionError('Please provide a rejection reason.')
      return
    }
    try {
      setIsSubmittingAction(true)
      setActionError(null)
      await approvalService.reject(id, reviewReason.trim())
      await fetchData()
      if (selectedRequest && selectedRequest.id === id) {
        const updated = await approvalService.getDetail(id)
        setSelectedRequest(updated)
      }
    } catch (err: any) {
      setActionError(err.response?.data?.detail || 'Failed to reject request')
    } finally {
      setIsSubmittingAction(false)
    }
  }

  const handleCancel = async (id: number) => {
    if (!window.confirm('Are you sure you want to cancel this request?')) return
    try {
      setIsSubmittingAction(true)
      setActionError(null)
      await approvalService.cancel(id, reviewReason || undefined)
      await fetchData()
      if (selectedRequest && selectedRequest.id === id) {
        const updated = await approvalService.getDetail(id)
        setSelectedRequest(updated)
      }
    } catch (err: any) {
      setActionError(err.response?.data?.detail || 'Failed to cancel request')
    } finally {
      setIsSubmittingAction(false)
    }
  }

  const handleExecute = async (id: number) => {
    try {
      setIsSubmittingAction(true)
      setActionError(null)
      await approvalService.execute(id)
      await fetchData()
      if (selectedRequest && selectedRequest.id === id) {
        const updated = await approvalService.getDetail(id)
        setSelectedRequest(updated)
      }
    } catch (err: any) {
      setActionError(err.response?.data?.detail || 'Execution failed')
    } finally {
      setIsSubmittingAction(false)
    }
  }

  const copyCode = (code: string) => {
    navigator.clipboard.writeText(code)
    setCopiedCode(code)
    setTimeout(() => setCopiedCode(null), 2000)
  }

  const getStatusBadge = (status: ApprovalStatus) => {
    switch (status) {
      case 'PENDING':
        return <Badge variant="warning">PENDING</Badge>
      case 'APPROVED':
        return <Badge variant="success">APPROVED</Badge>
      case 'EXECUTED':
        return <Badge variant="primary">EXECUTED</Badge>
      case 'REJECTED':
        return <Badge variant="danger">REJECTED</Badge>
      case 'CANCELLED':
        return <Badge variant="neutral">CANCELLED</Badge>
      default:
        return <Badge variant="neutral">{status}</Badge>
    }
  }

  const getTypeBadge = (type: string) => {
    if (type === 'PURCHASE_REQUISITION') {
      return (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-medium bg-cyan-950/70 border border-cyan-500/40 text-cyan-300">
          <Package className="w-3 h-3" /> Purchase Requisition
        </span>
      )
    }
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-medium bg-purple-950/70 border border-purple-500/40 text-purple-300">
        <Calendar className="w-3 h-3" /> Leave Request
      </span>
    )
  }

  // Filtered list by search query
  const filteredRequests = requests.filter((r) => {
    if (!searchQuery.trim()) return true
    const q = searchQuery.toLowerCase()
    return (
      r.request_code.toLowerCase().includes(q) ||
      r.title.toLowerCase().includes(q) ||
      (r.description && r.description.toLowerCase().includes(q)) ||
      (r.requester_email && r.requester_email.toLowerCase().includes(q))
    )
  })

  const userRole = user?.role || 'Employee'
  const isApproverRole = ['Admin', 'Manager', 'HR'].includes(userRole)

  return (
    <div className="space-y-6 animate-fade-in pb-12">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-bold tracking-tight text-white m-0">
              Human-in-the-Loop Approvals
            </h1>
            <Badge variant="warning" size="sm">
              Controlled Execution
            </Badge>
          </div>
          <p className="text-xs text-slate-400 mt-1">
            Authorize proposed purchase requisitions and leave requests with immutable audit trails.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <Button
            variant="secondary"
            size="sm"
            onClick={fetchData}
            disabled={isRefreshing}
            icon={<RotateCcw className={`w-3.5 h-3.5 ${isRefreshing ? 'animate-spin' : ''}`} />}
          >
            Refresh
          </Button>
        </div>
      </div>

      {/* KPI Summary Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <Card className="bg-slate-900/80 border-slate-800 p-4">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-slate-400 uppercase tracking-wider">
              Pending Reviews
            </span>
            <div className="p-2 rounded-lg bg-amber-500/10 text-amber-400 border border-amber-500/20">
              <Clock className="w-4 h-4" />
            </div>
          </div>
          <div className="mt-2 text-2xl font-bold text-white">
            {metrics?.pending_count ?? 0}
          </div>
          <p className="text-[11px] text-amber-400/80 mt-1 flex items-center gap-1">
            <AlertTriangle className="w-3 h-3" /> Awaiting managerial authorization
          </p>
        </Card>

        <Card className="bg-slate-900/80 border-slate-800 p-4">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-slate-400 uppercase tracking-wider">
              Approved (Pending Exec)
            </span>
            <div className="p-2 rounded-lg bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
              <CheckCircle2 className="w-4 h-4" />
            </div>
          </div>
          <div className="mt-2 text-2xl font-bold text-white">
            {metrics?.approved_count ?? 0}
          </div>
          <p className="text-[11px] text-emerald-400/80 mt-1 flex items-center gap-1">
            <FileCheck className="w-3 h-3" /> Ready for system execution
          </p>
        </Card>

        <Card className="bg-slate-900/80 border-slate-800 p-4">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-slate-400 uppercase tracking-wider">
              Executed Actions
            </span>
            <div className="p-2 rounded-lg bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
              <Play className="w-4 h-4" />
            </div>
          </div>
          <div className="mt-2 text-2xl font-bold text-white">
            {metrics?.executed_count ?? 0}
          </div>
          <p className="text-[11px] text-indigo-400/80 mt-1 flex items-center gap-1">
            <Layers className="w-3 h-3" /> Stock on order &amp; leaves applied
          </p>
        </Card>

        <Card className="bg-slate-900/80 border-slate-800 p-4">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-slate-400 uppercase tracking-wider">
              Rejected / Cancelled
            </span>
            <div className="p-2 rounded-lg bg-rose-500/10 text-rose-400 border border-rose-500/20">
              <XCircle className="w-4 h-4" />
            </div>
          </div>
          <div className="mt-2 text-2xl font-bold text-white">
            {(metrics?.rejected_count ?? 0) + (metrics?.cancelled_count ?? 0)}
          </div>
          <p className="text-[11px] text-slate-400 mt-1">
            {metrics?.rejected_count ?? 0} rejected · {metrics?.cancelled_count ?? 0} cancelled
          </p>
        </Card>
      </div>

      {/* Filter Tabs & Search Controls */}
      <Card className="p-4 bg-slate-900/90 border-slate-800">
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
          {/* Status Tabs */}
          <div className="flex flex-wrap items-center gap-1.5 p-1 bg-slate-950 rounded-xl border border-slate-800">
            {['PENDING', 'APPROVED', 'EXECUTED', 'REJECTED', 'ALL'].map((st) => (
              <button
                key={st}
                type="button"
                onClick={() => setSelectedStatus(st)}
                className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                  selectedStatus === st
                    ? 'bg-indigo-600 text-white shadow-sm'
                    : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900'
                }`}
              >
                {st === 'ALL' ? 'All Requests' : st.charAt(0) + st.slice(1).toLowerCase()}
              </button>
            ))}
          </div>

          {/* Right Filters */}
          <div className="flex flex-wrap items-center gap-3">
            {/* Search */}
            <div className="relative min-w-[200px]">
              <Search className="w-3.5 h-3.5 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
              <input
                type="text"
                placeholder="Search code or title..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full pl-9 pr-3 py-1.5 bg-slate-950 border border-slate-800 rounded-lg text-xs text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500"
              />
            </div>

            {/* Type Filter */}
            <select
              value={selectedType}
              onChange={(e) => setSelectedType(e.target.value)}
              className="px-3 py-1.5 bg-slate-950 border border-slate-800 rounded-lg text-xs text-slate-300 focus:outline-none focus:border-indigo-500"
            >
              <option value="ALL">All Types</option>
              <option value="PURCHASE_REQUISITION">Purchase Requisitions</option>
              <option value="LEAVE_REQUEST">Leave Requests</option>
            </select>

            {/* My Submissions Only Toggle */}
            <label className="flex items-center gap-2 text-xs text-slate-400 cursor-pointer">
              <input
                type="checkbox"
                checked={myRequestsOnly}
                onChange={(e) => setMyRequestsOnly(e.target.checked)}
                className="rounded bg-slate-950 border-slate-800 text-indigo-600 focus:ring-0"
              />
              <span>My Submissions</span>
            </label>
          </div>
        </div>
      </Card>

      {/* Main Approval Requests List */}
      <Card className="p-0 bg-slate-900/90 border-slate-800 overflow-hidden shadow-xl">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-950/80 border-b border-slate-800 text-slate-400 uppercase tracking-wider text-[10px]">
              <tr>
                <th className="px-4 py-3">Request Code</th>
                <th className="px-4 py-3">Type</th>
                <th className="px-4 py-3">Proposal Title</th>
                <th className="px-4 py-3">Requester</th>
                <th className="px-4 py-3">Assigned Role</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/80">
              {isLoading ? (
                <tr>
                  <td colSpan={7} className="text-center py-12 text-slate-500">
                    <LoadingSpinner size="md" className="mx-auto mb-2" />
                    Loading approval workflows...
                  </td>
                </tr>
              ) : filteredRequests.length === 0 ? (
                <tr>
                  <td colSpan={7} className="text-center py-12 text-slate-500">
                    <CheckSquare className="w-8 h-8 text-slate-600 mx-auto mb-2" />
                    No approval requests found matching your filter criteria.
                  </td>
                </tr>
              ) : (
                filteredRequests.map((req) => {
                  const isRequester = user?.id === req.requester_id
                  const canReview = isApproverRole && !isRequester && req.status === 'PENDING'

                  return (
                    <tr
                      key={req.id}
                      className="hover:bg-slate-800/40 transition-colors group cursor-pointer"
                      onClick={() => openDetail(req.id)}
                    >
                      {/* Code */}
                      <td className="px-4 py-3 font-mono font-medium text-indigo-300">
                        <div className="flex items-center gap-1.5">
                          <span>{req.request_code}</span>
                          <button
                            type="button"
                            onClick={(e) => {
                              e.stopPropagation()
                              copyCode(req.request_code)
                            }}
                            className="p-1 text-slate-500 hover:text-white transition-colors"
                            title="Copy Code"
                          >
                            {copiedCode === req.request_code ? (
                              <Check className="w-3 h-3 text-emerald-400" />
                            ) : (
                              <Copy className="w-3 h-3" />
                            )}
                          </button>
                        </div>
                      </td>

                      {/* Type */}
                      <td className="px-4 py-3">{getTypeBadge(req.request_type)}</td>

                      {/* Title */}
                      <td className="px-4 py-3 max-w-xs">
                        <div className="font-semibold text-white truncate">{req.title}</div>
                        {req.description && (
                          <div className="text-[11px] text-slate-400 truncate mt-0.5">
                            {req.description}
                          </div>
                        )}
                      </td>

                      {/* Requester */}
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-1.5">
                          <UserIcon className="w-3.5 h-3.5 text-slate-500" />
                          <span className="text-slate-300">{req.requester_email || 'User'}</span>
                        </div>
                        {isRequester && (
                          <span className="text-[10px] text-indigo-400 font-medium">
                            (Your proposal)
                          </span>
                        )}
                      </td>

                      {/* Assigned Role */}
                      <td className="px-4 py-3">
                        <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-slate-950 border border-slate-800 text-slate-300">
                          {req.assigned_role}
                        </span>
                      </td>

                      {/* Status */}
                      <td className="px-4 py-3">{getStatusBadge(req.status)}</td>

                      {/* Actions */}
                      <td className="px-4 py-3 text-right" onClick={(e) => e.stopPropagation()}>
                        <div className="flex items-center justify-end gap-1.5">
                          <Button
                            variant="secondary"
                            size="sm"
                            onClick={() => openDetail(req.id)}
                            icon={<Eye className="w-3 h-3" />}
                          >
                            Details
                          </Button>

                          {/* Review quick actions */}
                          {canReview && (
                            <>
                              <Button
                                variant="primary"
                                size="sm"
                                onClick={() => handleApprove(req.id)}
                                disabled={isSubmittingAction}
                                className="bg-emerald-600 hover:bg-emerald-500 text-white"
                                icon={<Check className="w-3 h-3" />}
                              >
                                Approve
                              </Button>
                              <Button
                                variant="danger"
                                size="sm"
                                onClick={() => {
                                  openDetail(req.id)
                                }}
                                disabled={isSubmittingAction}
                                icon={<X className="w-3 h-3" />}
                              >
                                Reject
                              </Button>
                            </>
                          )}

                          {/* Execute action if APPROVED */}
                          {req.status === 'APPROVED' && isApproverRole && (
                            <Button
                              variant="primary"
                              size="sm"
                              onClick={() => handleExecute(req.id)}
                              disabled={isSubmittingAction}
                              icon={<Play className="w-3 h-3" />}
                            >
                              Execute
                            </Button>
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

      {/* Request Detail & Review Modal */}
      {detailModalOpen && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-xs flex items-center justify-center p-4 z-50 animate-fade-in">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl w-full max-w-2xl max-h-[90vh] flex flex-col shadow-2xl overflow-hidden">
            {/* Modal Header */}
            <div className="px-6 py-4 border-b border-slate-800 flex items-center justify-between bg-slate-950/80">
              <div className="flex items-center gap-2.5">
                <div className="w-8 h-8 rounded-lg bg-indigo-950 border border-indigo-500/30 flex items-center justify-center text-indigo-400">
                  <CheckSquare className="w-4 h-4" />
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-xs text-indigo-300 font-semibold">
                      {selectedRequest?.request_code}
                    </span>
                    {selectedRequest && getStatusBadge(selectedRequest.status)}
                  </div>
                  <h2 className="text-sm font-bold text-white truncate max-w-md mt-0.5">
                    {selectedRequest?.title}
                  </h2>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setDetailModalOpen(false)}
                className="p-1 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Modal Body */}
            <div className="p-6 overflow-y-auto space-y-5 text-xs">
              {isLoadingDetail ? (
                <div className="py-12 text-center text-slate-500">
                  <LoadingSpinner size="md" className="mx-auto mb-2" />
                  Loading details...
                </div>
              ) : selectedRequest ? (
                <>
                  {/* Action Error Alert */}
                  {actionError && (
                    <div className="p-3 rounded-xl bg-rose-950/60 border border-rose-500/40 text-rose-300 flex items-center gap-2">
                      <AlertTriangle className="w-4 h-4 shrink-0 text-rose-400" />
                      <span>{actionError}</span>
                    </div>
                  )}

                  {/* Summary Metadata */}
                  <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 p-3 rounded-xl bg-slate-950/60 border border-slate-800">
                    <div>
                      <span className="text-[10px] text-slate-500 uppercase tracking-wider block">
                        Requester
                      </span>
                      <span className="text-slate-300 font-medium truncate block">
                        {selectedRequest.requester_email || 'User'}
                      </span>
                    </div>
                    <div>
                      <span className="text-[10px] text-slate-500 uppercase tracking-wider block">
                        Target Role
                      </span>
                      <span className="text-slate-300 font-medium">
                        {selectedRequest.assigned_role}
                      </span>
                    </div>
                    <div>
                      <span className="text-[10px] text-slate-500 uppercase tracking-wider block">
                        Submitted On
                      </span>
                      <span className="text-slate-300 font-medium">
                        {new Intl.DateTimeFormat('en-US', {
                          month: 'short',
                          day: 'numeric',
                          hour: 'numeric',
                          minute: '2-digit',
                        }).format(new Date(selectedRequest.created_at))}
                      </span>
                    </div>
                  </div>

                  {/* Proposed Action Snapshot */}
                  <div>
                    <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-400 mb-2 flex items-center gap-1.5">
                      <Package className="w-3.5 h-3.5 text-cyan-400" />
                      Immutable Action Snapshot
                    </h3>

                    {selectedRequest.request_type === 'PURCHASE_REQUISITION' ? (
                      <div className="rounded-xl border border-slate-800 overflow-hidden bg-slate-950/70">
                        <table className="w-full text-left text-xs">
                          <thead className="bg-slate-900/80 text-[10px] text-slate-400 uppercase">
                            <tr>
                              <th className="px-3 py-2">Product SKU</th>
                              <th className="px-3 py-2">Product Name</th>
                              <th className="px-3 py-2 text-right">Units Requested</th>
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-slate-800">
                            {(selectedRequest.action_payload.items || []).map((item: any, i: number) => (
                              <tr key={i}>
                                <td className="px-3 py-2 font-mono text-indigo-300">{item.sku}</td>
                                <td className="px-3 py-2 text-white">{item.name || 'Catalog Item'}</td>
                                <td className="px-3 py-2 text-right font-bold text-cyan-300">
                                  {item.quantity} units
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    ) : (
                      <div className="p-3 rounded-xl border border-slate-800 bg-slate-950/70 space-y-2">
                        <div className="grid grid-cols-2 gap-2">
                          <div>
                            <span className="text-slate-500 text-[10px] block">Employee:</span>
                            <span className="text-white font-medium">
                              {selectedRequest.action_payload.employee_name} ({selectedRequest.action_payload.employee_code})
                            </span>
                          </div>
                          <div>
                            <span className="text-slate-500 text-[10px] block">Category:</span>
                            <span className="text-white font-medium">
                              {selectedRequest.action_payload.leave_type} Leave ({selectedRequest.action_payload.days_count} days)
                            </span>
                          </div>
                          <div>
                            <span className="text-slate-500 text-[10px] block">Period:</span>
                            <span className="text-white font-medium">
                              {selectedRequest.action_payload.start_date} to {selectedRequest.action_payload.end_date}
                            </span>
                          </div>
                          <div>
                            <span className="text-slate-500 text-[10px] block">Reason:</span>
                            <span className="text-slate-300 italic">
                              &quot;{selectedRequest.action_payload.reason || 'None provided'}&quot;
                            </span>
                          </div>
                        </div>
                      </div>
                    )}
                  </div>

                  {/* Execution Outcome (if EXECUTED) */}
                  {selectedRequest.execution_result && (
                    <div className="p-3.5 rounded-xl bg-indigo-950/40 border border-indigo-500/30 text-indigo-200">
                      <div className="font-semibold text-xs text-indigo-300 flex items-center gap-1.5 mb-1.5">
                        <CheckCircle2 className="w-3.5 h-3.5 text-indigo-400" />
                        Execution Record Output
                      </div>
                      <pre className="font-mono text-[11px] bg-slate-950/80 p-2.5 rounded-lg border border-indigo-900/40 overflow-x-auto text-slate-300">
                        {JSON.stringify(selectedRequest.execution_result, null, 2)}
                      </pre>
                    </div>
                  )}

                  {/* Audit Trail Timeline */}
                  <div>
                    <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-400 mb-2 flex items-center gap-1.5">
                      <History className="w-3.5 h-3.5 text-amber-400" />
                      Chronological Audit Trail
                    </h3>
                    <div className="space-y-2 pl-2 border-l-2 border-slate-800">
                      {selectedRequest.audit_records.map((a) => (
                        <div key={a.id} className="relative pl-4 text-xs">
                          <div className="absolute -left-[21px] top-1 w-2.5 h-2.5 rounded-full bg-slate-800 border-2 border-indigo-500" />
                          <div className="flex items-center gap-2">
                            <span className="font-semibold text-white">{a.action}</span>
                            <span className="text-[10px] text-slate-500">
                              by {a.actor_email} ({a.actor_role})
                            </span>
                            <span className="text-[10px] text-slate-500 ml-auto">
                              {new Intl.DateTimeFormat('en-US', {
                                month: 'short',
                                day: 'numeric',
                                hour: 'numeric',
                                minute: '2-digit',
                              }).format(new Date(a.created_at))}
                            </span>
                          </div>
                          {a.comment && (
                            <div className="text-[11px] text-slate-400 italic mt-0.5">
                              &quot;{a.comment}&quot;
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* Review Actions Panel */}
                  {selectedRequest.status === 'PENDING' && (
                    <div className="p-4 rounded-xl bg-slate-950 border border-slate-800 space-y-3">
                      <h4 className="text-xs font-semibold text-white flex items-center gap-1.5">
                        <Shield className="w-3.5 h-3.5 text-indigo-400" />
                        Reviewer Action Control
                      </h4>

                      {/* Anti-self-approval warning */}
                      {user?.id === selectedRequest.requester_id ? (
                        <div className="p-2.5 rounded-lg bg-amber-950/40 border border-amber-500/30 text-amber-300 text-[11px] flex items-center justify-between">
                          <span>
                            You submitted this proposal. A separate authorized reviewer must evaluate it.
                          </span>
                          <Button
                            variant="danger"
                            size="sm"
                            onClick={() => handleCancel(selectedRequest.id)}
                            disabled={isSubmittingAction}
                          >
                            Cancel Request
                          </Button>
                        </div>
                      ) : !isApproverRole ? (
                        <div className="text-[11px] text-slate-400 italic">
                          Your current role ({userRole}) does not have review permissions for this proposal.
                        </div>
                      ) : (
                        <div className="space-y-3">
                          <input
                            type="text"
                            placeholder="Review notes or rejection reason (required for reject)..."
                            value={reviewReason}
                            onChange={(e) => setReviewReason(e.target.value)}
                            className="w-full px-3 py-2 bg-slate-900 border border-slate-800 rounded-lg text-xs text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500"
                          />
                          <div className="flex items-center justify-end gap-2">
                            <Button
                              variant="danger"
                              size="sm"
                              onClick={() => handleReject(selectedRequest.id)}
                              disabled={isSubmittingAction || !reviewReason.trim()}
                              icon={<X className="w-3.5 h-3.5" />}
                            >
                              Reject Proposal
                            </Button>
                            <Button
                              variant="primary"
                              size="sm"
                              onClick={() => handleApprove(selectedRequest.id)}
                              disabled={isSubmittingAction}
                              className="bg-emerald-600 hover:bg-emerald-500 text-white"
                              icon={<Check className="w-3.5 h-3.5" />}
                            >
                              Authorize &amp; Approve
                            </Button>
                          </div>
                        </div>
                      )}
                    </div>
                  )}

                  {/* Execution trigger if APPROVED */}
                  {selectedRequest.status === 'APPROVED' && isApproverRole && (
                    <div className="p-4 rounded-xl bg-emerald-950/20 border border-emerald-500/30 flex items-center justify-between">
                      <div>
                        <div className="font-semibold text-xs text-emerald-300">
                          Proposal is Approved
                        </div>
                        <div className="text-[11px] text-slate-400 mt-0.5">
                          Click to execute business changes (simulated PO placement or official leave registration).
                        </div>
                      </div>
                      <Button
                        variant="primary"
                        size="sm"
                        onClick={() => handleExecute(selectedRequest.id)}
                        disabled={isSubmittingAction}
                        icon={<Play className="w-3.5 h-3.5" />}
                      >
                        Execute Action
                      </Button>
                    </div>
                  )}
                </>
              ) : null}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default ApprovalsPage
