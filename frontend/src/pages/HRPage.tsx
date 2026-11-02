import React, { useEffect, useState, useMemo, useCallback } from 'react'
import {
  Users,
  Calendar,
  Search,
  Filter,
  CheckCircle,
  XCircle,
  Clock,
  RefreshCw,
  Eye,
  ShieldCheck,
  ChevronLeft,
  ChevronRight,
  UserCheck,
} from 'lucide-react'
import { useAuthStore } from '../store/auth.store'
import Card from '../components/common/Card'
import Badge from '../components/common/Badge'
import Button from '../components/common/Button'
import Modal from '../components/common/Modal'
import { SkeletonTable } from '../components/common/Skeleton'
import EmptyState from '../components/common/EmptyState'
import ConfirmModal from '../components/common/ConfirmModal'
import { hrService } from '../services/hr.service'
import { analyticsService } from '../services/analytics.service'
import type {
  Employee,
  LeaveRecord,
  LeaveSummaryReport,
} from '../types/hr.types'
import type { HRAnalytics } from '../types/enterprise.types'

export const HRPage: React.FC = () => {
  const { user } = useAuthStore()
  const canManageHR = user?.role === 'Admin' || user?.role === 'HR' || user?.role === 'Manager'

  // Tab State: 'employees' | 'leaves'
  const [activeTab, setActiveTab] = useState<'employees' | 'leaves'>('employees')

  // Employees State
  const [employees, setEmployees] = useState<Employee[]>([])
  const [hrAnalytics, setHrAnalytics] = useState<HRAnalytics | null>(null)
  const [isEmployeesLoading, setIsEmployeesLoading] = useState(canManageHR)
  const [employeeError, setEmployeeError] = useState<string | null>(null)
  const [employeeSearch, setEmployeeSearch] = useState('')
  const [departmentFilter, setDepartmentFilter] = useState('ALL')
  const [statusFilter, setStatusFilter] = useState<'ALL' | 'ACTIVE' | 'INACTIVE'>('ALL')
  const [page, setPage] = useState(1)
  const pageSize = 15

  // Leaves State
  const [leaves, setLeaves] = useState<LeaveRecord[]>([])
  const [leaveReport, setLeaveReport] = useState<LeaveSummaryReport | null>(null)
  const [isLeavesLoading, setIsLeavesLoading] = useState(true)
  const [leaveError, setLeaveError] = useState<string | null>(null)
  const [leaveStatusFilter, setLeaveStatusFilter] = useState('ALL')
  const [leavePage, setLeavePage] = useState(1)
  const leavePageSize = 15

  // Modals State
  const [selectedEmployee, setSelectedEmployee] = useState<Employee | null>(null)
  const [reviewingLeave, setReviewingLeave] = useState<LeaveRecord | null>(null)
  const [reviewAction, setReviewAction] = useState<'APPROVED' | 'REJECTED'>('APPROVED')
  const [reviewReason, setReviewReason] = useState('')
  const [isSubmittingReview, setIsSubmittingReview] = useState(false)
  const [isConfirmReviewOpen, setIsConfirmReviewOpen] = useState(false)
  const [reviewError, setReviewError] = useState<string | null>(null)
  const [actionSuccessMsg, setActionSuccessMsg] = useState<string | null>(null)

  // Load Employees (manual trigger)
  const fetchEmployees = useCallback(async () => {
    if (!canManageHR) return
    setIsEmployeesLoading(true)
    setEmployeeError(null)
    try {
      const [data, analyticsData] = await Promise.all([
        hrService.listEmployees({
          limit: 500,
          department: departmentFilter !== 'ALL' ? departmentFilter : undefined,
          is_active: statusFilter === 'ALL' ? undefined : statusFilter === 'ACTIVE',
        }),
        analyticsService.getHRAnalytics().catch(() => null),
      ])
      setEmployees(data)
      if (analyticsData) setHrAnalytics(analyticsData)
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
        'Failed to load employee directory.'
      setEmployeeError(msg)
    } finally {
      setIsEmployeesLoading(false)
    }
  }, [canManageHR, departmentFilter, statusFilter])

  // Load Leaves (manual trigger)
  const fetchLeaves = useCallback(async () => {
    setIsLeavesLoading(true)
    setLeaveError(null)
    try {
      const [leavesData, reportData, analyticsData] = await Promise.all([
        hrService.listLeaves({
          limit: 300,
          status: leaveStatusFilter !== 'ALL' ? leaveStatusFilter : undefined,
        }),
        canManageHR ? hrService.getLeavesReport().catch(() => null) : Promise.resolve(null),
        canManageHR ? analyticsService.getHRAnalytics().catch(() => null) : Promise.resolve(null),
      ])
      setLeaves(leavesData)
      if (reportData) setLeaveReport(reportData)
      if (analyticsData) setHrAnalytics(analyticsData)
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
        'Failed to load leave records.'
      setLeaveError(msg)
    } finally {
      setIsLeavesLoading(false)
    }
  }, [canManageHR, leaveStatusFilter])

  useEffect(() => {
    if (!canManageHR) {
      return
    }

    let active = true
    Promise.all([
      hrService.listEmployees({
        limit: 500,
        department: departmentFilter !== 'ALL' ? departmentFilter : undefined,
        is_active: statusFilter === 'ALL' ? undefined : statusFilter === 'ACTIVE',
      }),
      analyticsService.getHRAnalytics().catch(() => null),
    ])
      .then(([data, analyticsData]) => {
        if (!active) return
        setEmployees(data)
        if (analyticsData) setHrAnalytics(analyticsData)
      })
      .catch((err: unknown) => {
        if (active) {
          const msg =
            (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
            'Failed to load employee directory.'
          setEmployeeError(msg)
        }
      })
      .finally(() => {
        if (active) setIsEmployeesLoading(false)
      })

    return () => {
      active = false
    }
  }, [canManageHR, departmentFilter, statusFilter])

  useEffect(() => {
    let active = true
    Promise.all([
      hrService.listLeaves({
        limit: 300,
        status: leaveStatusFilter !== 'ALL' ? leaveStatusFilter : undefined,
      }),
      canManageHR ? hrService.getLeavesReport().catch(() => null) : Promise.resolve(null),
      canManageHR ? analyticsService.getHRAnalytics().catch(() => null) : Promise.resolve(null),
    ])
      .then(([leavesData, reportData, analyticsData]) => {
        if (!active) return
        setLeaves(leavesData)
        if (reportData) setLeaveReport(reportData)
        if (analyticsData) setHrAnalytics(analyticsData)
      })
      .catch((err: unknown) => {
        if (active) {
          const msg =
            (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
            'Failed to load leave records.'
          setLeaveError(msg)
        }
      })
      .finally(() => {
        if (active) setIsLeavesLoading(false)
      })

    return () => {
      active = false
    }
  }, [canManageHR, leaveStatusFilter])

  // Filtered employees by search string
  const filteredEmployees = useMemo(() => {
    if (!employeeSearch.trim()) return employees
    const query = employeeSearch.toLowerCase()
    return employees.filter(
      (emp) =>
        emp.employee_id.toLowerCase().includes(query) ||
        emp.first_name.toLowerCase().includes(query) ||
        emp.last_name.toLowerCase().includes(query) ||
        emp.email.toLowerCase().includes(query) ||
        emp.role.toLowerCase().includes(query),
    )
  }, [employees, employeeSearch])

  // Distinct departments for filter
  const departments = useMemo(() => {
    const set = new Set<string>()
    employees.forEach((e) => {
      if (e.department) set.add(e.department)
    })
    return Array.from(set).sort()
  }, [employees])

  // Pagination for Employees
  const totalEmployeePages = Math.max(1, Math.ceil(filteredEmployees.length / pageSize))
  const paginatedEmployees = useMemo(() => {
    const start = (page - 1) * pageSize
    return filteredEmployees.slice(start, start + pageSize)
  }, [filteredEmployees, page, pageSize])

  // Pagination for Leaves
  const totalLeavePages = Math.max(1, Math.ceil(leaves.length / leavePageSize))
  const paginatedLeaves = useMemo(() => {
    const start = (leavePage - 1) * leavePageSize
    return leaves.slice(start, start + leavePageSize)
  }, [leaves, leavePage, leavePageSize])

  // Handle Review Submission (opens confirmation modal)
  const handleReviewSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!reviewingLeave) return
    setIsConfirmReviewOpen(true)
  }

  // Execute review decision upon confirmation
  const executeReviewDecision = async () => {
    if (!reviewingLeave) return
    setIsSubmittingReview(true)
    setReviewError(null)

    try {
      await hrService.updateLeaveStatus(reviewingLeave.id, {
        status: reviewAction,
        reason: reviewReason.trim() ? reviewReason.trim() : undefined,
      })
      setActionSuccessMsg(
        `Leave request ${reviewingLeave.leave_code} has been successfully ${reviewAction.toLowerCase()}.`,
      )
      setIsConfirmReviewOpen(false)
      setReviewingLeave(null)
      setReviewReason('')
      // Refresh leaves & overview
      fetchLeaves()
      setTimeout(() => setActionSuccessMsg(null), 4000)
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
        'Failed to update leave status.'
      setReviewError(msg)
      setIsConfirmReviewOpen(false)
    } finally {
      setIsSubmittingReview(false)
    }
  }

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'APPROVED':
        return (
          <Badge variant="success" size="sm">
            <CheckCircle className="w-3 h-3" /> Approved
          </Badge>
        )
      case 'REJECTED':
        return (
          <Badge variant="danger" size="sm">
            <XCircle className="w-3 h-3" /> Rejected
          </Badge>
        )
      case 'PENDING':
      default:
        return (
          <Badge variant="warning" size="sm">
            <Clock className="w-3 h-3" /> Pending
          </Badge>
        )
    }
  }

  return (
    <div className="space-y-6">
      {/* Header Banner */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl md:text-2xl font-bold text-white tracking-tight m-0">
            Human Resources & Staffing Dashboard
          </h1>
          <p className="text-xs text-slate-400 mt-1 m-0">
            Enterprise workforce directory, department staffing, and leave lifecycle management
          </p>
        </div>

        <div className="flex items-center gap-2">
          <Badge variant={canManageHR ? 'success' : 'neutral'}>
            <ShieldCheck className="w-3.5 h-3.5" />
            {canManageHR ? 'HR Management Authorized' : 'Employee Self-Service'}
          </Badge>
        </div>
      </div>

      {actionSuccessMsg && (
        <div className="p-3.5 rounded-xl bg-emerald-950/40 border border-emerald-800 text-emerald-300 text-xs flex items-center justify-between">
          <span>{actionSuccessMsg}</span>
          <button
            onClick={() => setActionSuccessMsg(null)}
            className="text-emerald-400 hover:text-white"
          >
            ×
          </button>
        </div>
      )}

      {/* KPI Cards (Leave Report & Headcount) */}
      {canManageHR && leaveReport && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <Card>
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">
                Total Leave Requests
              </span>
              <Calendar className="w-4 h-4 text-indigo-400" />
            </div>
            <div className="text-2xl font-bold text-white mt-2">
              {leaveReport.total_requests}
            </div>
            <div className="text-xs text-slate-400 mt-1">
              {leaveReport.total_days_requested} total days requested
            </div>
          </Card>

          <Card>
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">
                Pending Reviews
              </span>
              <Clock className="w-4 h-4 text-amber-400" />
            </div>
            <div className="text-2xl font-bold text-amber-400 mt-2">
              {leaveReport.by_status?.PENDING || 0}
            </div>
            <div className="text-xs text-slate-400 mt-1">
              {(leaveReport.by_status?.PENDING || 0) > 0
                ? 'Requires approver decision'
                : 'All reviews up to date'}
            </div>
          </Card>

          <Card>
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">
                Approved Requests
              </span>
              <CheckCircle className="w-4 h-4 text-emerald-400" />
            </div>
            <div className="text-2xl font-bold text-emerald-400 mt-2">
              {leaveReport.by_status?.APPROVED || 0}
            </div>
            <div className="text-xs text-slate-400 mt-1">
              {leaveReport.total_days_approved} days approved
            </div>
          </Card>

          <Card>
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">
                Total Staff Roster
              </span>
              <Users className="w-4 h-4 text-cyan-400" />
            </div>
            <div className="text-2xl font-bold text-white mt-2">
              {hrAnalytics?.total_employees ?? employees.length}
            </div>
            <div className="text-xs text-slate-400 mt-1">
              Across {hrAnalytics ? Object.keys(hrAnalytics.by_department).length : departments.length} departments
              {hrAnalytics ? ` (${hrAnalytics.active_employees} active)` : ''}
            </div>
          </Card>
        </div>
      )}

      {/* Tab Navigation */}
      <div className="flex border-b border-slate-800 gap-6 text-sm">
        {canManageHR && (
          <button
            onClick={() => setActiveTab('employees')}
            className={`pb-3 font-semibold transition-colors flex items-center gap-2 ${
              activeTab === 'employees'
                ? 'text-indigo-400 border-b-2 border-indigo-500'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <Users className="w-4 h-4" />
            Employee Directory ({employees.length})
          </button>
        )}
        <button
          onClick={() => setActiveTab('leaves')}
          className={`pb-3 font-semibold transition-colors flex items-center gap-2 ${
            activeTab === 'leaves'
              ? 'text-indigo-400 border-b-2 border-indigo-500'
              : 'text-slate-400 hover:text-slate-200'
          }`}
        >
          <Calendar className="w-4 h-4" />
          Leave Requests ({leaves.length})
        </button>
      </div>

      {/* Tab 1: Employee Directory */}
      {activeTab === 'employees' && canManageHR && (
        <Card bodyClassName="!p-0">
          {/* Controls Bar */}
          <div className="p-4 border-b border-slate-800 flex flex-wrap items-center justify-between gap-3 bg-slate-900/60">
            <div className="flex flex-wrap items-center gap-3 flex-1 min-w-[280px]">
              {/* Search */}
              <div className="relative flex-1 max-w-sm">
                <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
                <input
                  type="text"
                  placeholder="Search by ID, name, email, role..."
                  value={employeeSearch}
                  onChange={(e) => {
                    setEmployeeSearch(e.target.value)
                    setPage(1)
                  }}
                  className="w-full pl-9 pr-3 py-1.5 bg-slate-950 border border-slate-800 rounded-lg text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-indigo-500"
                />
              </div>

              {/* Department Filter */}
              <div className="flex items-center gap-1.5">
                <Filter className="w-3.5 h-3.5 text-slate-400" />
                <select
                  value={departmentFilter}
                  onChange={(e) => {
                    setDepartmentFilter(e.target.value)
                    setPage(1)
                  }}
                  className="bg-slate-950 border border-slate-800 rounded-lg text-xs text-slate-200 py-1.5 px-2.5 focus:outline-none focus:border-indigo-500"
                >
                  <option value="ALL">All Departments</option>
                  {departments.map((dept) => (
                    <option key={dept} value={dept}>
                      {dept}
                    </option>
                  ))}
                </select>
              </div>

              {/* Status Filter */}
              <select
                value={statusFilter}
                onChange={(e) => {
                  setStatusFilter(e.target.value as 'ALL' | 'ACTIVE' | 'INACTIVE')
                  setPage(1)
                }}
                className="bg-slate-950 border border-slate-800 rounded-lg text-xs text-slate-200 py-1.5 px-2.5 focus:outline-none focus:border-indigo-500"
              >
                <option value="ALL">All Status</option>
                <option value="ACTIVE">Active Only</option>
                <option value="INACTIVE">Inactive Only</option>
              </select>
            </div>

            <Button
              variant="ghost"
              size="sm"
              onClick={fetchEmployees}
              disabled={isEmployeesLoading}
            >
              <RefreshCw className={`w-3.5 h-3.5 ${isEmployeesLoading ? 'animate-spin' : ''}`} />
              Refresh
            </Button>
          </div>

          {/* Table */}
          {isEmployeesLoading ? (
            <SkeletonTable rows={8} columns={7} />
          ) : employeeError ? (
            <div className="p-8 text-center text-rose-400 text-xs">
              {employeeError}
            </div>
          ) : paginatedEmployees.length === 0 ? (
            <EmptyState
              icon={<Users className="w-6 h-6 text-slate-500" />}
              title="No Employees Found"
              description="No employee records matched your active department filter, status filter, or search query."
              action={
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => {
                    setEmployeeSearch('')
                    setDepartmentFilter('ALL')
                    setStatusFilter('ALL')
                    setPage(1)
                  }}
                >
                  Reset Filters
                </Button>
              }
            />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse text-xs">
                <thead>
                  <tr className="border-b border-slate-800 text-slate-400 font-semibold uppercase tracking-wider bg-slate-950/40">
                    <th className="py-3 px-4">Code</th>
                    <th className="py-3 px-4">Name</th>
                    <th className="py-3 px-4">Email</th>
                    <th className="py-3 px-4">Department</th>
                    <th className="py-3 px-4">Role / Title</th>
                    <th className="py-3 px-4 text-center">Status</th>
                    <th className="py-3 px-4 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60">
                  {paginatedEmployees.map((emp) => (
                    <tr
                      key={emp.id}
                      className="hover:bg-slate-800/30 transition-colors"
                    >
                      <td className="py-3 px-4 font-mono font-medium text-indigo-400">
                        {emp.employee_id}
                      </td>
                      <td className="py-3 px-4 text-white font-medium">
                        {emp.first_name} {emp.last_name}
                      </td>
                      <td className="py-3 px-4 text-slate-400 font-mono">
                        {emp.email}
                      </td>
                      <td className="py-3 px-4 text-slate-300">
                        <span className="px-2 py-0.5 rounded-md bg-slate-800 text-slate-300">
                          {emp.department}
                        </span>
                      </td>
                      <td className="py-3 px-4 text-slate-300">
                        {emp.role}
                      </td>
                      <td className="py-3 px-4 text-center">
                        {emp.is_active ? (
                          <Badge variant="success" size="sm">
                            Active
                          </Badge>
                        ) : (
                          <Badge variant="neutral" size="sm">
                            Inactive
                          </Badge>
                        )}
                      </td>
                      <td className="py-3 px-4 text-right">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => setSelectedEmployee(emp)}
                          className="text-slate-300 hover:text-white"
                        >
                          <Eye className="w-3.5 h-3.5" />
                          View
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {/* Pagination */}
          <div className="p-4 border-t border-slate-800 flex items-center justify-between text-xs text-slate-400 bg-slate-950/40">
            <div>
              Showing {filteredEmployees.length > 0 ? (page - 1) * pageSize + 1 : 0} to{' '}
              {Math.min(page * pageSize, filteredEmployees.length)} of {filteredEmployees.length} employees
            </div>
            <div className="flex items-center gap-2">
              <Button
                variant="secondary"
                size="sm"
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page <= 1}
              >
                <ChevronLeft className="w-3.5 h-3.5" />
                Previous
              </Button>
              <span className="text-slate-300 px-2 font-mono">
                {page} / {totalEmployeePages}
              </span>
              <Button
                variant="secondary"
                size="sm"
                onClick={() => setPage((p) => Math.min(totalEmployeePages, p + 1))}
                disabled={page >= totalEmployeePages}
              >
                Next
                <ChevronRight className="w-3.5 h-3.5" />
              </Button>
            </div>
          </div>
        </Card>
      )}

      {/* Tab 2: Leave Requests */}
      {activeTab === 'leaves' && (
        <Card bodyClassName="!p-0">
          {/* Controls Bar */}
          <div className="p-4 border-b border-slate-800 flex flex-wrap items-center justify-between gap-3 bg-slate-900/60">
            <div className="flex items-center gap-3 flex-wrap">
              <span className="text-xs text-slate-400 font-semibold uppercase tracking-wider">
                Filter by Status:
              </span>
              <div className="flex items-center gap-1.5">
                {['ALL', 'PENDING', 'APPROVED', 'REJECTED'].map((st) => (
                  <button
                    key={st}
                    onClick={() => {
                      setLeaveStatusFilter(st)
                      setLeavePage(1)
                    }}
                    className={`px-3 py-1 rounded-lg text-xs font-medium transition-colors ${
                      leaveStatusFilter === st
                        ? 'bg-indigo-600 text-white'
                        : 'bg-slate-950 hover:bg-slate-800 text-slate-300 border border-slate-800'
                    }`}
                  >
                    {st === 'ALL' ? 'All Leaves' : st}
                  </button>
                ))}
              </div>
            </div>

            <Button
              variant="ghost"
              size="sm"
              onClick={fetchLeaves}
              disabled={isLeavesLoading}
            >
              <RefreshCw className={`w-3.5 h-3.5 ${isLeavesLoading ? 'animate-spin' : ''}`} />
              Refresh
            </Button>
          </div>

          {/* Table */}
          {isLeavesLoading ? (
            <SkeletonTable rows={8} columns={8} />
          ) : leaveError ? (
            <div className="p-8 text-center text-rose-400 text-xs">{leaveError}</div>
          ) : paginatedLeaves.length === 0 ? (
            <EmptyState
              icon={<Calendar className="w-6 h-6 text-slate-500" />}
              title="No Leave Records Found"
              description="No leave requests match the selected status filter."
              action={
                leaveStatusFilter !== 'ALL' ? (
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => {
                      setLeaveStatusFilter('ALL')
                      setLeavePage(1)
                    }}
                  >
                    View All Requests
                  </Button>
                ) : undefined
              }
            />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse text-xs">
                <thead>
                  <tr className="border-b border-slate-800 text-slate-400 font-semibold uppercase tracking-wider bg-slate-950/40">
                    <th className="py-3 px-4">Leave Code</th>
                    <th className="py-3 px-4">Employee</th>
                    <th className="py-3 px-4">Type</th>
                    <th className="py-3 px-4">Date Range</th>
                    <th className="py-3 px-4 text-center">Days</th>
                    <th className="py-3 px-4 text-center">Status</th>
                    <th className="py-3 px-4">Reason / Notes</th>
                    {canManageHR && <th className="py-3 px-4 text-right">Review Action</th>}
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60">
                  {paginatedLeaves.map((lv) => (
                    <tr key={lv.id} className="hover:bg-slate-800/30 transition-colors">
                      <td className="py-3 px-4 font-mono font-medium text-indigo-400">
                        {lv.leave_code}
                      </td>
                      <td className="py-3 px-4 font-mono text-slate-200">
                        {lv.employee_code}
                      </td>
                      <td className="py-3 px-4 text-slate-300">
                        <span className="px-2 py-0.5 rounded-md bg-slate-800 text-slate-300">
                          {lv.leave_type}
                        </span>
                      </td>
                      <td className="py-3 px-4 text-slate-300 font-mono">
                        {lv.start_date} → {lv.end_date}
                      </td>
                      <td className="py-3 px-4 text-center font-mono font-semibold text-white">
                        {lv.days_count}
                      </td>
                      <td className="py-3 px-4 text-center">
                        {getStatusBadge(lv.status)}
                      </td>
                      <td className="py-3 px-4 text-slate-400 max-w-xs truncate">
                        {lv.reason || '—'}
                      </td>
                      {canManageHR && (
                        <td className="py-3 px-4 text-right">
                          {lv.status === 'PENDING' ? (
                            <div className="flex items-center justify-end gap-1.5">
                              <Button
                                size="sm"
                                variant="primary"
                                onClick={() => {
                                  setReviewingLeave(lv)
                                  setReviewAction('APPROVED')
                                  setReviewReason('')
                                }}
                                className="!py-1 !px-2.5 text-[11px]"
                              >
                                Review
                              </Button>
                            </div>
                          ) : (
                            <span className="text-[11px] text-slate-500 italic">
                              Reviewed
                            </span>
                          )}
                        </td>
                      )}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {/* Pagination */}
          <div className="p-4 border-t border-slate-800 flex items-center justify-between text-xs text-slate-400 bg-slate-950/40">
            <div>
              Showing {leaves.length > 0 ? (leavePage - 1) * leavePageSize + 1 : 0} to{' '}
              {Math.min(leavePage * leavePageSize, leaves.length)} of {leaves.length} records
            </div>
            <div className="flex items-center gap-2">
              <Button
                variant="secondary"
                size="sm"
                onClick={() => setLeavePage((p) => Math.max(1, p - 1))}
                disabled={leavePage <= 1}
              >
                <ChevronLeft className="w-3.5 h-3.5" />
                Previous
              </Button>
              <span className="text-slate-300 px-2 font-mono">
                {leavePage} / {totalLeavePages}
              </span>
              <Button
                variant="secondary"
                size="sm"
                onClick={() => setLeavePage((p) => Math.min(totalLeavePages, p + 1))}
                disabled={leavePage >= totalLeavePages}
              >
                Next
                <ChevronRight className="w-3.5 h-3.5" />
              </Button>
            </div>
          </div>
        </Card>
      )}

      {/* Modal 1: Employee Detail View */}
      <Modal
        isOpen={selectedEmployee !== null}
        onClose={() => setSelectedEmployee(null)}
        title={`Employee Profile: ${selectedEmployee?.employee_id || ''}`}
        description="Comprehensive enterprise workforce profile"
      >
        {selectedEmployee && (
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="text-[11px] font-semibold uppercase tracking-wider text-slate-400 block mb-1">
                  Full Name
                </label>
                <div className="text-sm font-semibold text-white">
                  {selectedEmployee.first_name} {selectedEmployee.last_name}
                </div>
              </div>
              <div>
                <label className="text-[11px] font-semibold uppercase tracking-wider text-slate-400 block mb-1">
                  Employee Code
                </label>
                <div className="text-sm font-mono text-indigo-400">
                  {selectedEmployee.employee_id}
                </div>
              </div>

              <div>
                <label className="text-[11px] font-semibold uppercase tracking-wider text-slate-400 block mb-1">
                  Work Email
                </label>
                <div className="text-xs font-mono text-slate-300">
                  {selectedEmployee.email}
                </div>
              </div>
              <div>
                <label className="text-[11px] font-semibold uppercase tracking-wider text-slate-400 block mb-1">
                  Employment Status
                </label>
                <div>
                  {selectedEmployee.is_active ? (
                    <Badge variant="success" size="sm">
                      <UserCheck className="w-3 h-3" /> Active Roster
                    </Badge>
                  ) : (
                    <Badge variant="neutral" size="sm">
                      Inactive
                    </Badge>
                  )}
                </div>
              </div>

              <div>
                <label className="text-[11px] font-semibold uppercase tracking-wider text-slate-400 block mb-1">
                  Department
                </label>
                <div className="text-sm text-slate-200">
                  {selectedEmployee.department}
                </div>
              </div>
              <div>
                <label className="text-[11px] font-semibold uppercase tracking-wider text-slate-400 block mb-1">
                  Designation / Role
                </label>
                <div className="text-sm text-slate-200">
                  {selectedEmployee.role}
                </div>
              </div>

              <div>
                <label className="text-[11px] font-semibold uppercase tracking-wider text-slate-400 block mb-1">
                  Annual Compensation
                </label>
                <div className="text-sm font-mono text-emerald-400">
                  {selectedEmployee.salary !== null
                    ? `$${selectedEmployee.salary.toLocaleString('en-US', { minimumFractionDigits: 2 })}`
                    : 'Confidential / Restricted'}
                </div>
              </div>
              <div>
                <label className="text-[11px] font-semibold uppercase tracking-wider text-slate-400 block mb-1">
                  Database Surrogate ID
                </label>
                <div className="text-sm font-mono text-slate-400">
                  #{selectedEmployee.id}
                </div>
              </div>
            </div>

            <div className="pt-4 border-t border-slate-800 flex justify-end">
              <Button
                variant="secondary"
                size="sm"
                onClick={() => setSelectedEmployee(null)}
              >
                Close Profile
              </Button>
            </div>
          </div>
        )}
      </Modal>

      {/* Modal 2: Leave Review / Approval Dialog */}
      <Modal
        isOpen={reviewingLeave !== null}
        onClose={() => {
          setReviewingLeave(null)
          setReviewError(null)
        }}
        title={`Review Leave: ${reviewingLeave?.leave_code}`}
        description="Authorized approval or rejection of employee leave request"
      >
        {reviewingLeave && (
          <form onSubmit={handleReviewSubmit} className="space-y-4">
            <div className="p-3.5 rounded-xl bg-slate-950 border border-slate-800 text-xs space-y-2">
              <div className="flex justify-between">
                <span className="text-slate-400">Employee:</span>
                <span className="font-mono text-indigo-400 font-medium">
                  {reviewingLeave.employee_code}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">Type & Duration:</span>
                <span className="text-slate-200 font-medium">
                  {reviewingLeave.leave_type} — {reviewingLeave.days_count} days ({reviewingLeave.start_date} to {reviewingLeave.end_date})
                </span>
              </div>
              {reviewingLeave.reason && (
                <div className="flex flex-col gap-1 pt-1 border-t border-slate-800/80">
                  <span className="text-slate-400">Employee Reason:</span>
                  <span className="text-slate-300 italic">{reviewingLeave.reason}</span>
                </div>
              )}
            </div>

            {reviewError && (
              <div className="p-3 rounded-lg bg-rose-950/40 border border-rose-800 text-rose-300 text-xs">
                {reviewError}
              </div>
            )}

            <div>
              <label className="text-xs font-semibold text-slate-300 block mb-2">
                Review Decision
              </label>
              <div className="grid grid-cols-2 gap-3">
                <button
                  type="button"
                  onClick={() => setReviewAction('APPROVED')}
                  className={`p-3 rounded-xl border text-xs font-semibold flex items-center justify-center gap-2 transition-colors ${
                    reviewAction === 'APPROVED'
                      ? 'bg-emerald-600/20 border-emerald-500 text-emerald-300'
                      : 'bg-slate-950 border-slate-800 text-slate-400 hover:text-slate-200'
                  }`}
                >
                  <CheckCircle className="w-4 h-4 text-emerald-400" />
                  Approve Leave
                </button>
                <button
                  type="button"
                  onClick={() => setReviewAction('REJECTED')}
                  className={`p-3 rounded-xl border text-xs font-semibold flex items-center justify-center gap-2 transition-colors ${
                    reviewAction === 'REJECTED'
                      ? 'bg-rose-600/20 border-rose-500 text-rose-300'
                      : 'bg-slate-950 border-slate-800 text-slate-400 hover:text-slate-200'
                  }`}
                >
                  <XCircle className="w-4 h-4 text-rose-400" />
                  Reject Leave
                </button>
              </div>
            </div>

            <div>
              <label className="text-xs font-semibold text-slate-300 block mb-1">
                Decision Notes / Reason (Optional)
              </label>
              <textarea
                rows={3}
                placeholder="Provide approver feedback or reason for this status decision..."
                value={reviewReason}
                onChange={(e) => setReviewReason(e.target.value)}
                className="w-full p-2.5 bg-slate-950 border border-slate-800 rounded-lg text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-indigo-500"
              />
            </div>

            <div className="pt-3 border-t border-slate-800 flex items-center justify-end gap-2">
              <Button
                type="button"
                variant="secondary"
                size="sm"
                onClick={() => setReviewingLeave(null)}
                disabled={isSubmittingReview}
              >
                Cancel
              </Button>
              <Button
                type="submit"
                variant={reviewAction === 'APPROVED' ? 'primary' : 'danger'}
                size="sm"
                disabled={isSubmittingReview}
              >
                {isSubmittingReview ? 'Submitting...' : `Confirm ${reviewAction}`}
              </Button>
            </div>
          </form>
        )}
      </Modal>

      {/* Confirmation Dialog for Sensitive Leave Review Action */}
      <ConfirmModal
        isOpen={isConfirmReviewOpen}
        onClose={() => setIsConfirmReviewOpen(false)}
        onConfirm={executeReviewDecision}
        title={`Confirm Leave ${reviewAction === 'APPROVED' ? 'Approval' : 'Rejection'}`}
        message={`Are you sure you want to mark leave request ${reviewingLeave?.leave_code} as ${reviewAction}?`}
        details={
          reviewingLeave ? (
            <div className="space-y-1">
              <div><strong>Employee:</strong> {reviewingLeave.employee_code}</div>
              <div><strong>Leave Type:</strong> {reviewingLeave.leave_type} ({reviewingLeave.days_count} days)</div>
              <div><strong>Date Range:</strong> {reviewingLeave.start_date} to {reviewingLeave.end_date}</div>
              {reviewReason && <div><strong>Approver Notes:</strong> {reviewReason}</div>}
            </div>
          ) : null
        }
        confirmLabel={`Yes, Confirm ${reviewAction}`}
        variant={reviewAction === 'APPROVED' ? 'primary' : 'danger'}
        isLoading={isSubmittingReview}
      />
    </div>
  )
}

export default HRPage
