import React, { useEffect, useState, useCallback, useMemo } from 'react'
import { Link } from 'react-router-dom'
import {
  Users,
  TrendingUp,
  Package,
  AlertTriangle,
  Bot,
  ArrowRight,
  ShieldCheck,
  RefreshCw,
  Clock,
  Calendar,
  Activity,
  Layers,
  Briefcase,
  CheckSquare,
  FileText,
} from 'lucide-react'
import { useAuthStore } from '../store/auth.store'
import Card from '../components/common/Card'
import Badge from '../components/common/Badge'
import Button from '../components/common/Button'
import { SimpleBarChart } from '../components/common/SimpleBarChart'
import { Skeleton, SkeletonCard } from '../components/common/Skeleton'
import EmptyState from '../components/common/EmptyState'
import { analyticsService } from '../services/analytics.service'
import { inventoryService } from '../services/inventory.service'
import { hrService } from '../services/hr.service'
import type {
  DepartmentPerformance,
  ExecutiveOverview,
  HRAnalytics,
} from '../types/enterprise.types'
import type { Employee, LeaveRecord } from '../types/hr.types'

export const OverviewPage: React.FC = () => {
  const { user } = useAuthStore()
  const userRole = user?.role || 'Employee'

  const isAdmin = userRole === 'Admin'
  const isManager = userRole === 'Manager'
  const isExecutive = isAdmin || isManager
  const isHR = userRole === 'HR'
  const isEmployee = userRole === 'Employee'

  const [overview, setOverview] = useState<ExecutiveOverview | null>(null)
  const [deptPerformance, setDeptPerformance] = useState<DepartmentPerformance[]>([])
  const [hrAnalytics, setHrAnalytics] = useState<HRAnalytics | null>(null)
  const [employeeProfile, setEmployeeProfile] = useState<Employee | null>(null)
  const [myLeaves, setMyLeaves] = useState<LeaveRecord[]>([])
  const [lowStockCount, setLowStockCount] = useState<number | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [isRefreshing, setIsRefreshing] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const loadData = useCallback(async (refresh = false) => {
    if (refresh) setIsRefreshing(true)
    else setIsLoading(true)
    setError(null)

    try {
      if (isExecutive) {
        const [overviewData, deptData, alertsData] = await Promise.all([
          analyticsService.getOverview().catch(() => null),
          analyticsService.getDepartmentPerformance().catch(() => []),
          inventoryService.getLowStockAlerts().catch(() => null),
        ])
        if (overviewData) setOverview(overviewData)
        if (deptData) setDeptPerformance(deptData)
        if (alertsData) setLowStockCount(alertsData.total_low_stock)
      } else if (isHR) {
        const [hrData, alertsData] = await Promise.all([
          analyticsService.getHRAnalytics().catch(() => null),
          inventoryService.getLowStockAlerts().catch(() => null),
        ])
        if (hrData) setHrAnalytics(hrData)
        if (alertsData) setLowStockCount(alertsData.total_low_stock)
      } else if (isEmployee) {
        const leavesData = await hrService.listLeaves(
          user?.employee_id ? { employee_id: user.employee_id } : undefined
        ).catch(() => [])
        setMyLeaves(leavesData || [])
        if (user?.employee_id) {
          const profile = await hrService.getEmployee(user.employee_id).catch(() => null)
          setEmployeeProfile(profile)
        }
      }
    } catch (err: unknown) {
      const errorMsg =
        (err as { response?: { status?: number } })?.response?.status === 403
          ? 'Access restricted: You do not have permissions to view this domain.'
          : 'Failed to fetch enterprise intelligence. Please verify system connection.'
      setError(errorMsg)
    } finally {
      setIsLoading(false)
      setIsRefreshing(false)
    }
  }, [isExecutive, isHR, isEmployee, user])

  useEffect(() => {
    loadData()
  }, [loadData])

  const chartData = deptPerformance.map((dept) => ({
    label: dept.department,
    value: dept.employee_count,
    color: '#6366F1',
  }))

  const greeting = useMemo(() => {
    const hour = new Date().getHours()
    if (hour < 12) return 'Good Morning'
    if (hour < 17) return 'Good Afternoon'
    return 'Good Evening'
  }, [])

  const currentDate = useMemo(() => {
    return new Intl.DateTimeFormat('en-US', {
      weekday: 'long',
      month: 'short',
      day: 'numeric',
      year: 'numeric',
    }).format(new Date())
  }, [])

  return (
    <div className="space-y-8 animate-in fade-in duration-300">
      {/* Header Banner */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-6 border-b border-slate-800/80">
        <div>
          <div className="flex items-center gap-3 mb-1.5">
            <h1 className="text-2xl font-bold text-white tracking-tight">
              {greeting}, {user?.email?.split('@')[0] || 'User'}
            </h1>
            <Badge
              variant={
                userRole === 'Admin'
                  ? 'danger'
                  : userRole === 'Manager'
                  ? 'primary'
                  : userRole === 'HR'
                  ? 'warning'
                  : 'success'
              }
              size="sm"
            >
              {userRole}
            </Badge>
          </div>
          <p className="text-sm text-slate-400 flex items-center gap-2">
            <Calendar className="w-4 h-4 text-slate-500" />
            {currentDate}
            <span className="text-slate-600">|</span>
            <span className="flex items-center gap-1.5 text-emerald-400 font-medium">
              <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
              Autonomous Enterprise System Active
            </span>
          </p>
        </div>

        <div className="flex items-center gap-3">
          <Button
            variant="secondary"
            size="sm"
            onClick={() => loadData(true)}
            disabled={isRefreshing || isLoading}
            className="flex items-center gap-2 text-slate-300"
          >
            <RefreshCw className={`w-4 h-4 ${isRefreshing ? 'animate-spin text-indigo-400' : ''}`} />
            Refresh
          </Button>

          <Link to="/chat">
            <Button
              variant="primary"
              size="sm"
              className="flex items-center gap-2 shadow-lg shadow-indigo-500/20"
            >
              <Bot className="w-4 h-4" />
              Launch AI Assistant
            </Button>
          </Link>
        </div>
      </div>

      {/* Error Alert */}
      {error && (
        <div className="p-4 bg-rose-500/10 border border-rose-500/20 rounded-xl flex items-center justify-between text-rose-300 text-sm">
          <div className="flex items-center gap-3">
            <AlertTriangle className="w-5 h-5 text-rose-400 shrink-0" />
            <span>{error}</span>
          </div>
          <Button variant="secondary" size="sm" onClick={() => loadData()}>
            Retry
          </Button>
        </div>
      )}

      {/* Loading Skeletons */}
      {isLoading ? (
        <div className="space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
            <SkeletonCard />
            <SkeletonCard />
            <SkeletonCard />
            <SkeletonCard />
          </div>
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <div className="lg:col-span-2">
              <Skeleton className="h-80 w-full rounded-xl" />
            </div>
            <div>
              <Skeleton className="h-80 w-full rounded-xl" />
            </div>
          </div>
        </div>
      ) : (
        <>
          {/* Executive & Manager Dashboard */}
          {isExecutive && overview && (
            <>
              {/* 4 Metric Cards */}
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
                <Card className="p-5 border-slate-800/80 bg-slate-900/60 backdrop-blur-sm">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-xs font-semibold uppercase tracking-wider text-slate-400">
                        Total Workforce
                      </p>
                      <h3 className="text-3xl font-extrabold text-white mt-2 tracking-tight">
                        {overview.total_employees.toLocaleString()}
                      </h3>
                      <p className="text-xs text-emerald-400 mt-2 flex items-center gap-1 font-medium">
                        <TrendingUp className="w-3.5 h-3.5" /> {overview.active_employees} Active Staff
                      </p>
                    </div>
                    <div className="p-3.5 bg-indigo-500/10 rounded-xl text-indigo-400 border border-indigo-500/20">
                      <Users className="w-6 h-6" />
                    </div>
                  </div>
                </Card>

                <Card className="p-5 border-slate-800/80 bg-slate-900/60 backdrop-blur-sm">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-xs font-semibold uppercase tracking-wider text-slate-400">
                        Recognized Revenue
                      </p>
                      <h3 className="text-3xl font-extrabold text-white mt-2 tracking-tight">
                        ${Math.round(overview.total_recognized_revenue || 0).toLocaleString()}
                      </h3>
                      <p className="text-xs text-emerald-400 mt-2 flex items-center gap-1 font-medium">
                        <TrendingUp className="w-3.5 h-3.5" /> {overview.total_orders_completed} Completed Orders
                      </p>
                    </div>
                    <div className="p-3.5 bg-emerald-500/10 rounded-xl text-emerald-400 border border-emerald-500/20">
                      <TrendingUp className="w-6 h-6" />
                    </div>
                  </div>
                </Card>

                <Card className="p-5 border-slate-800/80 bg-slate-900/60 backdrop-blur-sm">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-xs font-semibold uppercase tracking-wider text-slate-400">
                        Inventory Stock
                      </p>
                      <h3 className="text-3xl font-extrabold text-white mt-2 tracking-tight">
                        {overview.total_inventory_units.toLocaleString()} units
                      </h3>
                      <p className="text-xs text-amber-400 mt-2 flex items-center gap-1 font-medium">
                        {(lowStockCount ?? 0) > 0 ? (
                          <>
                            <AlertTriangle className="w-3.5 h-3.5" /> {lowStockCount} Items below threshold
                          </>
                        ) : (
                          <>
                            <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" /> Optimal Stock Levels
                          </>
                        )}
                      </p>
                    </div>
                    <div className="p-3.5 bg-amber-500/10 rounded-xl text-amber-400 border border-amber-500/20">
                      <Package className="w-6 h-6" />
                    </div>
                  </div>
                </Card>

                <Card className="p-5 border-slate-800/80 bg-slate-900/60 backdrop-blur-sm">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-xs font-semibold uppercase tracking-wider text-slate-400">
                        Pending Approvals
                      </p>
                      <h3 className="text-3xl font-extrabold text-white mt-2 tracking-tight">
                        {overview.pending_leave_requests.toLocaleString()}
                      </h3>
                      <p className="text-xs text-indigo-400 mt-2 flex items-center gap-1 font-medium">
                        <Clock className="w-3.5 h-3.5" /> Requires Management Review
                      </p>
                    </div>
                    <div className="p-3.5 bg-purple-500/10 rounded-xl text-purple-400 border border-purple-500/20">
                      <CheckSquare className="w-6 h-6" />
                    </div>
                  </div>
                </Card>
              </div>

              {/* Chart & Quick Launch Grid */}
              <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                {/* Department Performance Chart */}
                <div className="lg:col-span-2">
                  <Card className="p-6 border-slate-800/80 bg-slate-900/60 h-full flex flex-col justify-between">
                    <div className="flex items-center justify-between mb-6">
                      <div>
                        <h2 className="text-lg font-bold text-white">Department Staffing Distribution</h2>
                        <p className="text-xs text-slate-400 mt-1">
                          Active workforce headcount breakdown across operational domains
                        </p>
                      </div>
                      <Badge variant="primary" size="sm">
                        Live Sync
                      </Badge>
                    </div>

                    {chartData.length > 0 ? (
                      <div className="h-64 flex items-center justify-center">
                        <SimpleBarChart data={chartData} />
                      </div>
                    ) : (
                      <EmptyState
                        title="No Performance Data"
                        description="Department metrics will show up as teams log performance indicators."
                        icon={<Activity className="w-8 h-8 text-slate-500" />}
                      />
                    )}

                    <div className="mt-4 pt-4 border-t border-slate-800/80 flex items-center justify-between text-xs text-slate-400">
                      <span>Top Domain: Engineering & Operations</span>
                      <Link
                        to="/sales"
                        className="text-indigo-400 hover:text-indigo-300 font-medium flex items-center gap-1"
                      >
                        Deep dive into metrics <ArrowRight className="w-3.5 h-3.5" />
                      </Link>
                    </div>
                  </Card>
                </div>

                {/* Quick Launch & Actions */}
                <div>
                  <Card className="p-6 border-slate-800/80 bg-slate-900/60 h-full flex flex-col justify-between">
                    <div>
                      <h2 className="text-lg font-bold text-white mb-1">Command Center</h2>
                      <p className="text-xs text-slate-400 mb-5">
                        Quick actions and automated decision modules
                      </p>

                      <div className="space-y-3">
                        <Link
                          to="/chat"
                          className="group flex items-center justify-between p-3.5 rounded-xl bg-slate-800/50 hover:bg-indigo-600/15 border border-slate-800 hover:border-indigo-500/30 transition-all"
                        >
                          <div className="flex items-center gap-3">
                            <div className="p-2 rounded-lg bg-indigo-500/10 text-indigo-400 group-hover:bg-indigo-500/20">
                              <Bot className="w-4 h-4" />
                            </div>
                            <div>
                              <div className="text-sm font-semibold text-slate-200 group-hover:text-white">
                                AI Decision Agent
                              </div>
                              <div className="text-xs text-slate-400">
                                Query enterprise state & plans
                              </div>
                            </div>
                          </div>
                          <ArrowRight className="w-4 h-4 text-slate-500 group-hover:text-indigo-400 group-hover:translate-x-0.5 transition-transform" />
                        </Link>

                        <Link
                          to="/approvals"
                          className="group flex items-center justify-between p-3.5 rounded-xl bg-slate-800/50 hover:bg-amber-600/15 border border-slate-800 hover:border-amber-500/30 transition-all"
                        >
                          <div className="flex items-center gap-3">
                            <div className="p-2 rounded-lg bg-amber-500/10 text-amber-400 group-hover:bg-amber-500/20">
                              <CheckSquare className="w-4 h-4" />
                            </div>
                            <div>
                              <div className="text-sm font-semibold text-slate-200 group-hover:text-white">
                                Approvals Engine
                              </div>
                              <div className="text-xs text-slate-400">
                                Human-in-the-loop decisions
                              </div>
                            </div>
                          </div>
                          <ArrowRight className="w-4 h-4 text-slate-500 group-hover:text-amber-400 group-hover:translate-x-0.5 transition-transform" />
                        </Link>

                        <Link
                          to="/documents"
                          className="group flex items-center justify-between p-3.5 rounded-xl bg-slate-800/50 hover:bg-cyan-600/15 border border-slate-800 hover:border-cyan-500/30 transition-all"
                        >
                          <div className="flex items-center gap-3">
                            <div className="p-2 rounded-lg bg-cyan-500/10 text-cyan-400 group-hover:bg-cyan-500/20">
                              <FileText className="w-4 h-4" />
                            </div>
                            <div>
                              <div className="text-sm font-semibold text-slate-200 group-hover:text-white">
                                Document Intelligence
                              </div>
                              <div className="text-xs text-slate-400">
                                Vector RAG & policy corpus
                              </div>
                            </div>
                          </div>
                          <ArrowRight className="w-4 h-4 text-slate-500 group-hover:text-cyan-400 group-hover:translate-x-0.5 transition-transform" />
                        </Link>

                        <Link
                          to="/inventory"
                          className="group flex items-center justify-between p-3.5 rounded-xl bg-slate-800/50 hover:bg-emerald-600/15 border border-slate-800 hover:border-emerald-500/30 transition-all"
                        >
                          <div className="flex items-center gap-3">
                            <div className="p-2 rounded-lg bg-emerald-500/10 text-emerald-400 group-hover:bg-emerald-500/20">
                              <Package className="w-4 h-4" />
                            </div>
                            <div>
                              <div className="text-sm font-semibold text-slate-200 group-hover:text-white">
                                Stock Management
                              </div>
                              <div className="text-xs text-slate-400">
                                Warehouse replenishments
                              </div>
                            </div>
                          </div>
                          <ArrowRight className="w-4 h-4 text-slate-500 group-hover:text-emerald-400 group-hover:translate-x-0.5 transition-transform" />
                        </Link>
                      </div>
                    </div>

                    <div className="mt-4 pt-4 border-t border-slate-800/80 text-xs text-slate-400 flex items-center gap-2">
                      <ShieldCheck className="w-4 h-4 text-emerald-400 shrink-0" />
                      <span>All autonomous actions logged for audit</span>
                    </div>
                  </Card>
                </div>
              </div>

              {/* System Architecture & Status Card (Admin Only) */}
              {isAdmin && (
                <Card className="p-6 border-slate-800/80 bg-slate-900/60">
                <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                  <div className="flex items-center gap-4">
                    <div className="w-12 h-12 rounded-2xl bg-indigo-600/20 border border-indigo-500/30 flex items-center justify-center text-indigo-400 shrink-0">
                      <Layers className="w-6 h-6" />
                    </div>
                    <div>
                      <h3 className="text-base font-bold text-white">
                        Agentic Decision Intelligence Core
                      </h3>
                      <p className="text-xs text-slate-400 mt-0.5">
                        Powered by LangGraph multi-agent architecture with ChromaDB vector search and SQL analytics.
                      </p>
                    </div>
                  </div>

                  <div className="flex flex-wrap items-center gap-3">
                    <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                      <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
                      FastAPI Backend Active
                    </span>
                    <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
                      <span className="w-1.5 h-1.5 rounded-full bg-indigo-400" />
                      Vector Store Connected
                    </span>
                    <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium bg-purple-500/10 text-purple-400 border border-purple-500/20">
                      <span className="w-1.5 h-1.5 rounded-full bg-purple-400" />
                      SQLite Database Live
                    </span>
                  </div>
                </div>
              </Card>
              )}
            </>
          )}

          {/* HR View */}
          {isHR && (
            <div className="space-y-6">
              <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                <Card className="p-6 border-slate-800/80 bg-slate-900/60">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-xs font-semibold uppercase tracking-wider text-slate-400">
                        Total Headcount
                      </p>
                      <h3 className="text-3xl font-extrabold text-white mt-2">
                        {hrAnalytics?.total_employees || 0}
                      </h3>
                      <p className="text-xs text-emerald-400 mt-2">
                        {hrAnalytics?.active_employees || 0} Active Staff Members
                      </p>
                    </div>
                    <div className="p-3.5 bg-indigo-500/10 text-indigo-400 rounded-xl border border-indigo-500/20">
                      <Users className="w-6 h-6" />
                    </div>
                  </div>
                </Card>

                <Card className="p-6 border-slate-800/80 bg-slate-900/60">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-xs font-semibold uppercase tracking-wider text-slate-400">
                        Pending Leave Reviews
                      </p>
                      <h3 className="text-3xl font-extrabold text-white mt-2">
                        {hrAnalytics?.pending_leave_requests || 0}
                      </h3>
                      <p className="text-xs text-amber-400 mt-2 flex items-center gap-1 font-medium">
                        <Clock className="w-3.5 h-3.5" /> Awaiting HR Action
                      </p>
                    </div>
                    <div className="p-3.5 bg-amber-500/10 text-amber-400 rounded-xl border border-amber-500/20">
                      <CheckSquare className="w-6 h-6" />
                    </div>
                  </div>
                </Card>

                <Card className="p-6 border-slate-800/80 bg-slate-900/60">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-xs font-semibold uppercase tracking-wider text-slate-400">
                        Supply & Stock Alerts
                      </p>
                      <h3 className="text-3xl font-extrabold text-white mt-2">
                        {lowStockCount !== null ? lowStockCount : 0}
                      </h3>
                      <p className="text-xs text-slate-400 mt-2">Items Below Safety Stock</p>
                    </div>
                    <div className="p-3.5 bg-purple-500/10 text-purple-400 rounded-xl border border-purple-500/20">
                      <Package className="w-6 h-6" />
                    </div>
                  </div>
                </Card>
              </div>

              <div className="flex flex-wrap gap-4">
                <Link to="/hr">
                  <Button variant="primary" className="flex items-center gap-2">
                    <Users className="w-4 h-4" /> Open Staff Directory
                  </Button>
                </Link>
                <Link to="/approvals">
                  <Button variant="secondary" className="flex items-center gap-2">
                    <CheckSquare className="w-4 h-4" /> Review Leave Requests
                  </Button>
                </Link>
                <Link to="/documents">
                  <Button variant="secondary" className="flex items-center gap-2">
                    <FileText className="w-4 h-4" /> HR Policy Documents
                  </Button>
                </Link>
              </div>
            </div>
          )}

          {/* Employee Self-Service View */}
          {isEmployee && (
            <div className="space-y-6">
              <Card className="p-6 border-slate-800/80 bg-slate-900/60">
                <div className="flex items-start justify-between flex-wrap gap-4">
                  <div className="flex items-center gap-4">
                    <div className="w-14 h-14 rounded-2xl bg-indigo-600/20 border border-indigo-500/30 flex items-center justify-center text-xl font-bold text-indigo-400">
                      {user?.email?.charAt(0).toUpperCase()}
                    </div>
                    <div>
                      <h2 className="text-xl font-bold text-white">
                        {employeeProfile ? `${employeeProfile.first_name} ${employeeProfile.last_name}` : user?.email}
                      </h2>
                      <div className="flex items-center flex-wrap gap-x-3 gap-y-1 mt-1 text-sm text-slate-400">
                        <span className="flex items-center gap-1.5">
                          <Briefcase className="w-4 h-4 text-slate-500" />
                          <span className="text-slate-400">Designation:</span>
                          <span className="font-medium text-slate-200 capitalize">
                            {employeeProfile?.role || 'Staff Member'}
                          </span>
                        </span>
                        <span className="text-slate-600">|</span>
                        <span className="flex items-center gap-1.5">
                          <span className="text-slate-400">Department:</span>
                          <span className="font-medium text-indigo-400">
                            {employeeProfile?.department || 'General'}
                          </span>
                        </span>
                        <span className="text-slate-600">|</span>
                        <span className="flex items-center gap-1.5 text-xs text-slate-500">
                          <span>Emp ID:</span>
                          <span className="font-mono text-slate-300">
                            {employeeProfile?.employee_id || (user?.employee_id ? `EMP-${user.employee_id}` : 'N/A')}
                          </span>
                        </span>
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center gap-3">
                    <Link to="/approvals">
                      <Button variant="primary" size="sm" className="flex items-center gap-2">
                        <CheckSquare className="w-4 h-4" /> Submit Request
                      </Button>
                    </Link>
                    <Link to="/chat">
                      <Button variant="secondary" size="sm" className="flex items-center gap-2">
                        <Bot className="w-4 h-4" /> Ask AI Assistant
                      </Button>
                    </Link>
                    <Link to="/documents">
                      <Button variant="secondary" size="sm" className="flex items-center gap-2">
                        <FileText className="w-4 h-4" /> Permitted Docs
                      </Button>
                    </Link>
                  </div>
                </div>
              </Card>

              {/* Leave records */}
              <Card className="p-6 border-slate-800/80 bg-slate-900/60">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-base font-bold text-white">Recent Leave Applications</h3>
                  <Link to="/approvals" className="text-xs text-indigo-400 hover:text-indigo-300 font-medium">
                    View All
                  </Link>
                </div>

                {myLeaves.length > 0 ? (
                  <div className="overflow-x-auto">
                    <table className="w-full text-left text-sm text-slate-300">
                      <thead className="text-xs uppercase bg-slate-800/40 text-slate-400">
                        <tr>
                          <th className="px-4 py-3">Leave Type</th>
                          <th className="px-4 py-3">Duration</th>
                          <th className="px-4 py-3">Dates</th>
                          <th className="px-4 py-3">Status</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-800/60">
                        {myLeaves.slice(0, 5).map((l) => (
                          <tr key={l.id} className="hover:bg-slate-800/30">
                            <td className="px-4 py-3 font-medium text-white">{l.leave_type}</td>
                            <td className="px-4 py-3">{l.days_count} days</td>
                            <td className="px-4 py-3 text-xs text-slate-400">
                              {l.start_date} to {l.end_date}
                            </td>
                            <td className="px-4 py-3">
                              <Badge
                                variant={
                                  l.status === 'APPROVED'
                                    ? 'success'
                                    : l.status === 'REJECTED'
                                    ? 'danger'
                                    : 'warning'
                                }
                                size="sm"
                              >
                                {l.status}
                              </Badge>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <div className="text-center py-8 text-slate-400 text-sm">
                    <Calendar className="w-8 h-8 text-slate-600 mx-auto mb-2" />
                    No recent leave applications found.
                  </div>
                )}
              </Card>
            </div>
          )}
        </>
      )}
    </div>
  )
}

export default OverviewPage
