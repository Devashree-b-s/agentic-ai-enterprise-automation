import React, { useEffect, useState, useMemo, useCallback } from 'react'
import {
  TrendingUp,
  DollarSign,
  Package,
  ShoppingBag,
  RotateCcw,
  Ban,
  RefreshCw,
  Eye,
  ChevronLeft,
  ChevronRight,
  ShieldAlert,
} from 'lucide-react'
import { useAuthStore } from '../store/auth.store'
import Card from '../components/common/Card'
import Badge from '../components/common/Badge'
import Button from '../components/common/Button'
import Modal from '../components/common/Modal'
import { SimpleBarChart } from '../components/common/SimpleBarChart'
import { Skeleton, SkeletonCard } from '../components/common/Skeleton'
import EmptyState from '../components/common/EmptyState'
import { salesService } from '../services/sales.service'
import type {
  OrderDetail,
  ProductSalesItem,
  SalesAnalytics,
} from '../types/sales.types'

export const SalesPage: React.FC = () => {
  const { user } = useAuthStore()
  const isAuthorized = user?.role === 'Admin' || user?.role === 'Manager'

  const [analytics, setAnalytics] = useState<SalesAnalytics | null>(null)
  const [orders, setOrders] = useState<OrderDetail[]>([])
  const [isLoading, setIsLoading] = useState(isAuthorized)
  const [error, setError] = useState<string | null>(null)

  // Order Detail Modal State
  const [selectedOrder, setSelectedOrder] = useState<OrderDetail | null>(null)

  // Orders Pagination & Filter
  const [orderStatusFilter, setOrderStatusFilter] = useState('ALL')
  const [orderPage, setOrderPage] = useState(1)
  const orderPageSize = 10

  const fetchData = useCallback(async () => {
    if (!isAuthorized) return
    setIsLoading(true)
    setError(null)

    try {
      const [analyticsData, ordersData] = await Promise.all([
        salesService.getSalesAnalytics(),
        salesService.listOrders({ limit: 100 }),
      ])
      setAnalytics(analyticsData)
      setOrders(ordersData)
    } catch (err: unknown) {
      const msg =
        (err as { response?: { status?: number; data?: { detail?: string } } })?.response?.status === 403
          ? 'Access forbidden: Sales performance data is restricted to Executive and Sales Management.'
          : (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
            'Failed to load sales analytics data.'
      setError(msg)
    } finally {
      setIsLoading(false)
    }
  }, [isAuthorized])

  useEffect(() => {
    if (!isAuthorized) {
      return
    }

    let active = true
    Promise.all([
      salesService.getSalesAnalytics(),
      salesService.listOrders({ limit: 100 }),
    ])
      .then(([analyticsData, ordersData]) => {
        if (!active) return
        setAnalytics(analyticsData)
        setOrders(ordersData)
      })
      .catch((err: unknown) => {
        if (!active) return
        const msg =
          (err as { response?: { status?: number; data?: { detail?: string } } })?.response?.status === 403
            ? 'Access forbidden: Sales performance data is restricted to Executive and Sales Management.'
            : (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
              'Failed to load sales analytics data.'
        setError(msg)
      })
      .finally(() => {
        if (active) setIsLoading(false)
      })

    return () => {
      active = false
    }
  }, [isAuthorized])

  // Filter orders
  const filteredOrders = useMemo(() => {
    if (orderStatusFilter === 'ALL') return orders
    return orders.filter((o) => o.status === orderStatusFilter)
  }, [orders, orderStatusFilter])

  // Orders pagination
  const totalOrderPages = Math.max(1, Math.ceil(filteredOrders.length / orderPageSize))
  const paginatedOrders = useMemo(() => {
    const start = (orderPage - 1) * orderPageSize
    return filteredOrders.slice(start, start + orderPageSize)
  }, [filteredOrders, orderPage, orderPageSize])

  // Chart data: Monthly Revenue Trends
  const monthlyRevenueChartData = useMemo(() => {
    if (!analytics || !analytics.monthly_revenue) return []
    return analytics.monthly_revenue.map((item) => ({
      label: item.year_month,
      value: Number(item.recognized_revenue),
      formattedValue: `$${Number(item.recognized_revenue).toLocaleString('en-US', {
        minimumFractionDigits: 0,
        maximumFractionDigits: 0,
      })} (${item.units_sold} units)`,
      color: 'bg-emerald-500',
    }))
  }, [analytics])

  const getOrderStatusBadge = (status: string) => {
    switch (status) {
      case 'COMPLETED':
      case 'DELIVERED':
        return (
          <Badge variant="success" size="sm">
            {status}
          </Badge>
        )
      case 'SHIPPED':
      case 'CONFIRMED':
      case 'PROCESSING':
        return (
          <Badge variant="primary" size="sm">
            {status}
          </Badge>
        )
      case 'CANCELLED':
        return (
          <Badge variant="danger" size="sm">
            {status}
          </Badge>
        )
      case 'RETURNED':
        return (
          <Badge variant="warning" size="sm">
            {status}
          </Badge>
        )
      default:
        return (
          <Badge variant="neutral" size="sm">
            {status}
          </Badge>
        )
    }
  }

  if (!isAuthorized) {
    return (
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-xl font-bold text-white m-0">Sales Analytics</h1>
            <p className="text-xs text-slate-400 mt-1 m-0">
              Recognized revenue and order management
            </p>
          </div>
          <Badge variant="danger">
            <ShieldAlert className="w-3.5 h-3.5" />
            Restricted ({user?.role})
          </Badge>
        </div>

        <div className="p-8 rounded-2xl bg-slate-900 border border-slate-800 text-center max-w-lg mx-auto">
          <ShieldAlert className="w-12 h-12 text-rose-400 mx-auto mb-3" />
          <h2 className="text-base font-semibold text-white m-0">
            Permission Required
          </h2>
          <p className="text-xs text-slate-400 mt-2 mb-0 leading-relaxed">
            Sales analytics, revenue recognition figures, and sales orders are accessible
            exclusively to users with the <strong className="text-indigo-400">Admin</strong> or{' '}
            <strong className="text-indigo-400">Manager</strong> role.
          </p>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl md:text-2xl font-bold text-white tracking-tight m-0">
            Sales & Revenue Analytics Dashboard
          </h1>
          <p className="text-xs text-slate-400 mt-1 m-0">
            Strict recognized revenue accounting, monthly sales trends, and order fulfillment
          </p>
        </div>

        <div className="flex items-center gap-2">
          <Badge variant="success">
            <DollarSign className="w-3.5 h-3.5" />
            Live Database Data
          </Badge>
          <Button
            variant="ghost"
            size="sm"
            onClick={fetchData}
            disabled={isLoading}
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isLoading ? 'animate-spin' : ''}`} />
            Refresh
          </Button>
        </div>
      </div>

      {isLoading ? (
        <div className="space-y-6">
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {Array.from({ length: 4 }).map((_, i) => (
              <SkeletonCard key={i} />
            ))}
          </div>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div className="p-6 rounded-xl border border-slate-800 bg-slate-900/60 space-y-4">
              <Skeleton className="h-5 w-48" />
              <Skeleton className="h-4 w-64" />
              <Skeleton className="h-48 w-full mt-4" />
            </div>
            <div className="p-6 rounded-xl border border-slate-800 bg-slate-900/60 space-y-4">
              <Skeleton className="h-5 w-48" />
              <Skeleton className="h-4 w-64" />
              <Skeleton className="h-48 w-full mt-4" />
            </div>
          </div>
        </div>
      ) : error ? (
        <div className="p-4 rounded-xl bg-rose-950/30 border border-rose-800 text-rose-200 text-sm flex items-center justify-between">
          <span>{error}</span>
          <Button size="sm" variant="secondary" onClick={fetchData}>
            Retry
          </Button>
        </div>
      ) : analytics ? (
        <>
          {/* KPI Cards Grid */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {/* Total Recognized Revenue */}
            <Card>
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">
                  Recognized Revenue
                </span>
                <div className="p-2 rounded-lg bg-emerald-500/10 text-emerald-400">
                  <TrendingUp className="w-4 h-4" />
                </div>
              </div>
              <div className="text-2xl font-bold text-white mt-2">
                ${Number(analytics.total_recognized_revenue).toLocaleString('en-US', {
                  minimumFractionDigits: 2,
                  maximumFractionDigits: 2,
                })}
              </div>
              <div className="text-xs text-slate-400 mt-1">
                From COMPLETED & SHIPPED orders
              </div>
            </Card>

            {/* Total Units Sold */}
            <Card>
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">
                  Units Sold
                </span>
                <div className="p-2 rounded-lg bg-indigo-500/10 text-indigo-400">
                  <Package className="w-4 h-4" />
                </div>
              </div>
              <div className="text-2xl font-bold text-white mt-2">
                {analytics.total_units_sold.toLocaleString()}
              </div>
              <div className="text-xs text-slate-400 mt-1">
                Across {analytics.total_transactions} orders
              </div>
            </Card>

            {/* Cancelled Orders Lost Potential */}
            <Card>
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">
                  Cancelled Orders
                </span>
                <div className="p-2 rounded-lg bg-rose-500/10 text-rose-400">
                  <Ban className="w-4 h-4" />
                </div>
              </div>
              <div className="text-2xl font-bold text-rose-400 mt-2">
                {analytics.cancelled_orders_count}
              </div>
              <div className="text-xs text-slate-400 mt-1">
                ${Number(analytics.cancelled_potential_revenue).toLocaleString('en-US', {
                  minimumFractionDigits: 2,
                })}{' '}
                unrealized
              </div>
            </Card>

            {/* Returned Orders Lost Revenue */}
            <Card>
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">
                  Returned Orders
                </span>
                <div className="p-2 rounded-lg bg-amber-500/10 text-amber-400">
                  <RotateCcw className="w-4 h-4" />
                </div>
              </div>
              <div className="text-2xl font-bold text-amber-400 mt-2">
                {analytics.returned_orders_count}
              </div>
              <div className="text-xs text-slate-400 mt-1">
                ${Number(analytics.returned_revenue_lost).toLocaleString('en-US', {
                  minimumFractionDigits: 2,
                })}{' '}
                refunded
              </div>
            </Card>
          </div>

          {/* Monthly Trends & Top Selling Products */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Monthly Trends Chart */}
            <Card
              title="Monthly Revenue Trends"
              subtitle="Recognized gross revenue grouped by calendar month"
            >
              {monthlyRevenueChartData.length === 0 ? (
                <div className="h-56 flex items-center justify-center text-xs text-slate-500">
                  No monthly sales trend records available.
                </div>
              ) : (
                <SimpleBarChart
                  data={monthlyRevenueChartData}
                  valuePrefix="$"
                />
              )}
            </Card>

            {/* Top Products by Revenue */}
            <Card
              title="Top-Selling Products by Revenue"
              subtitle="Ranked catalog items by gross revenue contribution"
            >
              <div className="space-y-3">
                {analytics.top_products_by_revenue.slice(0, 5).map((prod: ProductSalesItem, idx: number) => (
                  <div
                    key={prod.sku}
                    className="flex items-center justify-between p-2.5 rounded-xl bg-slate-950/60 border border-slate-800/80 hover:border-slate-700 transition-colors"
                  >
                    <div className="flex items-center gap-3">
                      <div className="w-6 h-6 rounded-md bg-indigo-500/20 text-indigo-400 font-mono text-xs font-bold flex items-center justify-center">
                        #{idx + 1}
                      </div>
                      <div>
                        <div className="text-xs font-semibold text-white">
                          {prod.product_name}
                        </div>
                        <div className="text-[11px] font-mono text-slate-400">
                          {prod.sku} • {prod.units_sold.toLocaleString()} units sold
                        </div>
                      </div>
                    </div>
                    <div className="text-right">
                      <div className="text-xs font-bold font-mono text-emerald-400">
                        ${Number(prod.total_revenue).toLocaleString('en-US', {
                          minimumFractionDigits: 2,
                          maximumFractionDigits: 2,
                        })}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </Card>
          </div>

          {/* Order Status Breakdown Summary */}
          <Card
            title="Order Status Breakdown"
            subtitle="Financial metrics categorized by order fulfillment status"
          >
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              {Object.entries(analytics.revenue_by_status).map(([status, rev]) => (
                <div
                  key={status}
                  className="p-3 rounded-xl bg-slate-950 border border-slate-800 text-xs"
                >
                  <div className="flex items-center justify-between mb-1">
                    <span className="font-semibold text-slate-300">{status}</span>
                    {getOrderStatusBadge(status)}
                  </div>
                  <div className="text-base font-bold font-mono text-white mt-1">
                    ${Number(rev).toLocaleString('en-US', { minimumFractionDigits: 2 })}
                  </div>
                </div>
              ))}
            </div>
          </Card>

          {/* Recent Sales Orders Table */}
          <Card bodyClassName="!p-0">
            <div className="p-4 border-b border-slate-800 flex flex-wrap items-center justify-between gap-3 bg-slate-900/60">
              <div className="flex items-center gap-3">
                <ShoppingBag className="w-4 h-4 text-indigo-400" />
                <h3 className="text-sm font-semibold text-white m-0">
                  Sales Orders Roster ({filteredOrders.length})
                </h3>
              </div>

              {/* Status Filter */}
              <select
                value={orderStatusFilter}
                onChange={(e) => {
                  setOrderStatusFilter(e.target.value)
                  setOrderPage(1)
                }}
                className="bg-slate-950 border border-slate-800 rounded-lg text-xs text-slate-200 py-1.5 px-2.5 focus:outline-none focus:border-indigo-500"
              >
                <option value="ALL">All Statuses</option>
                <option value="COMPLETED">COMPLETED</option>
                <option value="SHIPPED">SHIPPED</option>
                <option value="PROCESSING">PROCESSING</option>
                <option value="CONFIRMED">CONFIRMED</option>
                <option value="PENDING">PENDING</option>
                <option value="CANCELLED">CANCELLED</option>
                <option value="RETURNED">RETURNED</option>
              </select>
            </div>

            {paginatedOrders.length === 0 ? (
              <EmptyState
                icon={<ShoppingBag className="w-6 h-6 text-slate-500" />}
                title="No Orders Found"
                description="No sales orders match the selected status filter."
                action={
                  orderStatusFilter !== 'ALL' ? (
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => {
                        setOrderStatusFilter('ALL')
                        setOrderPage(1)
                      }}
                    >
                      View All Orders
                    </Button>
                  ) : undefined
                }
              />
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left border-collapse text-xs">
                  <thead>
                    <tr className="border-b border-slate-800 text-slate-400 font-semibold uppercase tracking-wider bg-slate-950/40">
                      <th className="py-3 px-4">Order #</th>
                      <th className="py-3 px-4">Customer</th>
                      <th className="py-3 px-4">Date</th>
                      <th className="py-3 px-4 text-center">Status</th>
                      <th className="py-3 px-4 text-center">Items</th>
                      <th className="py-3 px-4 text-right">Total Amount</th>
                      <th className="py-3 px-4 text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800/60">
                    {paginatedOrders.map((ord) => (
                      <tr
                        key={ord.id}
                        className="hover:bg-slate-800/30 transition-colors"
                      >
                        <td className="py-3 px-4 font-mono font-medium text-indigo-400">
                          {ord.order_number}
                        </td>
                        <td className="py-3 px-4">
                          <div className="text-white font-medium">
                            {ord.customer?.name || `Customer #${ord.customer_id}`}
                          </div>
                          <div className="text-[11px] font-mono text-slate-400">
                            {ord.customer?.customer_code}
                          </div>
                        </td>
                        <td className="py-3 px-4 text-slate-300 font-mono">
                          {ord.order_date ? ord.order_date.split('T')[0] : '—'}
                        </td>
                        <td className="py-3 px-4 text-center">
                          {getOrderStatusBadge(ord.status)}
                        </td>
                        <td className="py-3 px-4 text-center text-slate-300 font-mono">
                          {ord.items?.length || 0}
                        </td>
                        <td className="py-3 px-4 text-right font-mono font-bold text-white">
                          ${Number(ord.total_amount).toLocaleString('en-US', {
                            minimumFractionDigits: 2,
                            maximumFractionDigits: 2,
                          })}
                        </td>
                        <td className="py-3 px-4 text-right">
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => setSelectedOrder(ord)}
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
                Showing {filteredOrders.length > 0 ? (orderPage - 1) * orderPageSize + 1 : 0} to{' '}
                {Math.min(orderPage * orderPageSize, filteredOrders.length)} of {filteredOrders.length} orders
              </div>
              <div className="flex items-center gap-2">
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => setOrderPage((p) => Math.max(1, p - 1))}
                  disabled={orderPage <= 1}
                >
                  <ChevronLeft className="w-3.5 h-3.5" />
                  Previous
                </Button>
                <span className="text-slate-300 px-2 font-mono">
                  {orderPage} / {totalOrderPages}
                </span>
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => setOrderPage((p) => Math.min(totalOrderPages, p + 1))}
                  disabled={orderPage >= totalOrderPages}
                >
                  Next
                  <ChevronRight className="w-3.5 h-3.5" />
                </Button>
              </div>
            </div>
          </Card>
        </>
      ) : null}

      {/* Order Details Modal */}
      <Modal
        isOpen={selectedOrder !== null}
        onClose={() => setSelectedOrder(null)}
        title={`Order Details: ${selectedOrder?.order_number || ''}`}
        description="Comprehensive line items and purchaser summary"
        maxWidth="xl"
      >
        {selectedOrder && (
          <div className="space-y-4">
            {/* Header info */}
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 p-3.5 rounded-xl bg-slate-950 border border-slate-800 text-xs">
              <div>
                <span className="text-slate-400 block mb-0.5">Customer Name:</span>
                <span className="font-semibold text-white">
                  {selectedOrder.customer?.name}
                </span>
              </div>
              <div>
                <span className="text-slate-400 block mb-0.5">Customer Email:</span>
                <span className="font-mono text-slate-300">
                  {selectedOrder.customer?.email}
                </span>
              </div>
              <div>
                <span className="text-slate-400 block mb-0.5">Order Status:</span>
                <div>{getOrderStatusBadge(selectedOrder.status)}</div>
              </div>
              <div>
                <span className="text-slate-400 block mb-0.5">Order Date:</span>
                <span className="font-mono text-slate-300">
                  {selectedOrder.order_date ? selectedOrder.order_date.split('T')[0] : '—'}
                </span>
              </div>
              <div>
                <span className="text-slate-400 block mb-0.5">Total Amount:</span>
                <span className="font-mono font-bold text-emerald-400 text-sm">
                  ${Number(selectedOrder.total_amount).toLocaleString('en-US', {
                    minimumFractionDigits: 2,
                  })}
                </span>
              </div>
              <div>
                <span className="text-slate-400 block mb-0.5">Client Code:</span>
                <span className="font-mono text-indigo-400">
                  {selectedOrder.customer?.customer_code}
                </span>
              </div>
            </div>

            {/* Line items table */}
            <div>
              <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-400 mb-2">
                Purchased Line Items ({selectedOrder.items?.length || 0})
              </h4>
              <div className="border border-slate-800 rounded-xl overflow-hidden">
                <table className="w-full text-left border-collapse text-xs">
                  <thead>
                    <tr className="border-b border-slate-800 bg-slate-950 text-slate-400 uppercase tracking-wider">
                      <th className="py-2.5 px-3">Product Name</th>
                      <th className="py-2.5 px-3 text-center">Quantity</th>
                      <th className="py-2.5 px-3 text-right">Unit Price</th>
                      <th className="py-2.5 px-3 text-right">Subtotal</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800/60 bg-slate-900/40">
                    {selectedOrder.items?.map((item) => (
                      <tr key={item.id}>
                        <td className="py-2.5 px-3 text-white font-medium">
                          {item.product_name}
                        </td>
                        <td className="py-2.5 px-3 text-center font-mono text-slate-300">
                          {item.quantity}
                        </td>
                        <td className="py-2.5 px-3 text-right font-mono text-slate-300">
                          ${Number(item.unit_price).toFixed(2)}
                        </td>
                        <td className="py-2.5 px-3 text-right font-mono font-semibold text-emerald-400">
                          ${Number(item.subtotal).toFixed(2)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            {selectedOrder.notes && (
              <div className="p-3 rounded-lg bg-slate-950 border border-slate-800 text-xs text-slate-300">
                <strong className="text-slate-400">Order Notes: </strong>
                {selectedOrder.notes}
              </div>
            )}

            <div className="pt-2 flex justify-end">
              <Button
                variant="secondary"
                size="sm"
                onClick={() => setSelectedOrder(null)}
              >
                Close
              </Button>
            </div>
          </div>
        )}
      </Modal>
    </div>
  )
}

export default SalesPage
