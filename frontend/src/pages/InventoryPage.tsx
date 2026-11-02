import React, { useEffect, useState, useMemo } from 'react'
import {
  Package,
  AlertTriangle,
  RefreshCw,
  Search,
  ArrowDownCircle,
  ArrowUpCircle,
  SlidersHorizontal,
  History,
  ShieldCheck,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  TrendingUp,
} from 'lucide-react'
import { useAuthStore } from '../store/auth.store'
import Card from '../components/common/Card'
import Badge from '../components/common/Badge'
import Button from '../components/common/Button'
import LoadingSpinner from '../components/common/LoadingSpinner'
import Modal from '../components/common/Modal'
import { SkeletonTable } from '../components/common/Skeleton'
import EmptyState from '../components/common/EmptyState'
import ConfirmModal from '../components/common/ConfirmModal'
import { inventoryService } from '../services/inventory.service'
import type {
  LowStockItem,
  Product,
  ReplenishmentItem,
  StockMovement,
} from '../types/inventory.types'

export const InventoryPage: React.FC = () => {
  const { user } = useAuthStore()
  const isPrivileged = user?.role === 'Admin' || user?.role === 'Manager'

  // Tabs: 'catalog' | 'alerts' | 'replenishment'
  const [activeTab, setActiveTab] = useState<'catalog' | 'alerts' | 'replenishment'>('catalog')

  // Products State
  const [products, setProducts] = useState<Product[]>([])
  const [isProductsLoading, setIsProductsLoading] = useState(true)
  const [productError, setProductError] = useState<string | null>(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [filterLowStockOnly, setFilterLowStockOnly] = useState(false)
  const [catalogPage, setCatalogPage] = useState(1)
  const catalogPageSize = 12

  // Low-Stock Alerts State
  const [alerts, setAlerts] = useState<LowStockItem[]>([])
  const [isAlertsLoading, setIsAlertsLoading] = useState(false)

  // Replenishment Suggestions State (Admin & Manager)
  const [replenishment, setReplenishment] = useState<ReplenishmentItem[]>([])
  const [isReplenishmentLoading, setIsReplenishmentLoading] = useState(false)

  // Modal 1: Stock Movement Audit History
  const [viewingMovementsProduct, setViewingMovementsProduct] = useState<Product | null>(null)
  const [movements, setMovements] = useState<StockMovement[]>([])
  const [isMovementsLoading, setIsMovementsLoading] = useState(false)

  // Modal 2: Stock Operation Modal (Admin & Manager)
  const [operatingProduct, setOperatingProduct] = useState<Product | null>(null)
  const [operationType, setOperationType] = useState<'IN' | 'OUT' | 'ADJUST'>('IN')
  const [operationQty, setOperationQty] = useState<number>(10)
  const [operationReason, setOperationReason] = useState('')
  const [operationReference, setOperationReference] = useState('')
  const [isSubmittingOperation, setIsSubmittingOperation] = useState(false)
  const [isConfirmStockOpen, setIsConfirmStockOpen] = useState(false)
  const [operationError, setOperationError] = useState<string | null>(null)
  const [operationSuccessMsg, setOperationSuccessMsg] = useState<string | null>(null)

  // Manual refresh all inventory datasets
  const refreshAllData = async () => {
    setIsProductsLoading(true)
    setIsAlertsLoading(true)
    if (isPrivileged) setIsReplenishmentLoading(true)
    try {
      const [prodData, alertsReport, replData] = await Promise.all([
        inventoryService.listProducts({
          limit: 200,
          search: searchQuery.trim() || undefined,
          is_low_stock: filterLowStockOnly ? true : undefined,
        }),
        inventoryService.getLowStockAlerts(),
        isPrivileged ? inventoryService.getReplenishmentSuggestions().catch(() => null) : Promise.resolve(null),
      ])
      setProducts(prodData)
      setAlerts(alertsReport.items || [])
      if (replData) setReplenishment(replData)
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
        'Failed to refresh inventory.'
      setProductError(msg)
    } finally {
      setIsProductsLoading(false)
      setIsAlertsLoading(false)
      setIsReplenishmentLoading(false)
    }
  }

  useEffect(() => {
    let active = true

    inventoryService
      .listProducts({
        limit: 200,
        search: searchQuery.trim() ? searchQuery.trim() : undefined,
        is_low_stock: filterLowStockOnly ? true : undefined,
      })
      .then((data) => {
        if (active) setProducts(data)
      })
      .catch((err: unknown) => {
        if (active) {
          const msg =
            (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
            'Failed to load inventory products.'
          setProductError(msg)
        }
      })
      .finally(() => {
        if (active) setIsProductsLoading(false)
      })

    inventoryService
      .getLowStockAlerts()
      .then((report) => {
        if (active) setAlerts(report.items || [])
      })
      .catch((err) => console.error(err))
      .finally(() => {
        if (active) setIsAlertsLoading(false)
      })

    if (isPrivileged) {
      inventoryService
        .getReplenishmentSuggestions()
        .then((data) => {
          if (active) setReplenishment(data || [])
        })
        .catch((err) => console.error(err))
        .finally(() => {
          if (active) setIsReplenishmentLoading(false)
        })
    }

    return () => {
      active = false
    }
  }, [filterLowStockOnly, isPrivileged, searchQuery])

  // Search filter (client-side responsiveness + trigger fetch on enter/click)
  const filteredProducts = useMemo(() => {
    if (!searchQuery.trim()) return products
    const q = searchQuery.toLowerCase()
    return products.filter(
      (p) => p.sku.toLowerCase().includes(q) || p.name.toLowerCase().includes(q),
    )
  }, [products, searchQuery])

  // Pagination for catalog
  const totalCatalogPages = Math.max(1, Math.ceil(filteredProducts.length / catalogPageSize))
  const paginatedProducts = useMemo(() => {
    const start = (catalogPage - 1) * catalogPageSize
    return filteredProducts.slice(start, start + catalogPageSize)
  }, [filteredProducts, catalogPage, catalogPageSize])

  // Load movements for selected product
  const handleOpenMovements = async (product: Product) => {
    setViewingMovementsProduct(product)
    setIsMovementsLoading(true)
    try {
      const data = await inventoryService.getProductMovements(product.id)
      setMovements(data)
    } catch (err) {
      console.error('Failed to load movements', err)
      setMovements([])
    } finally {
      setIsMovementsLoading(false)
    }
  }

  // Handle stock operation submit (opens confirmation modal)
  const handleStockOperationSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!operatingProduct) return
    setIsConfirmStockOpen(true)
  }

  // Execute confirmed stock operation
  const executeStockOperation = async () => {
    if (!operatingProduct) return
    setIsSubmittingOperation(true)
    setOperationError(null)

    try {
      if (operationType === 'IN') {
        await inventoryService.stockIn({
          product_id: operatingProduct.id,
          quantity: Number(operationQty),
          reason: operationReason.trim() || undefined,
          reference: operationReference.trim() || undefined,
        })
      } else if (operationType === 'OUT') {
        await inventoryService.stockOut({
          product_id: operatingProduct.id,
          quantity: Number(operationQty),
          reason: operationReason.trim() || undefined,
          reference: operationReference.trim() || undefined,
        })
      } else {
        await inventoryService.stockAdjust({
          product_id: operatingProduct.id,
          new_quantity: Number(operationQty),
          reason: operationReason.trim() || undefined,
          reference: operationReference.trim() || undefined,
        })
      }

      setOperationSuccessMsg(
        `Successfully applied ${operationType} operation to ${operatingProduct.sku}.`,
      )
      setIsConfirmStockOpen(false)
      setOperatingProduct(null)
      setOperationReason('')
      setOperationReference('')
      // Refresh all datasets
      refreshAllData()
      setTimeout(() => setOperationSuccessMsg(null), 4000)
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
        'Stock operation failed. Verify quantities and permissions.'
      setOperationError(msg)
      setIsConfirmStockOpen(false)
    } finally {
      setIsSubmittingOperation(false)
    }
  }

  const getProductAvailabilityBadge = (product: Product) => {
    if (product.quantity_on_hand === 0) {
      return (
        <Badge variant="danger" size="sm">
          OUT OF STOCK
        </Badge>
      )
    }
    if (product.quantity_on_hand <= product.safety_stock) {
      return (
        <Badge variant="warning" size="sm">
          LOW STOCK ({product.quantity_on_hand} &le; {product.safety_stock})
        </Badge>
      )
    }
    return (
      <Badge variant="success" size="sm">
        HEALTHY ({product.quantity_on_hand})
      </Badge>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl md:text-2xl font-bold text-white tracking-tight m-0">
            Inventory & Warehouse Management
          </h1>
          <p className="text-xs text-slate-400 mt-1 m-0">
            Physical stock monitoring, low-stock threshold alerts, and prescriptive replenishment
          </p>
        </div>

        <div className="flex items-center gap-2">
          <Badge variant={isPrivileged ? 'primary' : 'success'}>
            <ShieldCheck className="w-3.5 h-3.5" />
            {isPrivileged ? 'Authorized Stock Operations' : 'Catalog Viewer (All Staff)'}
          </Badge>
          <Button
            variant="ghost"
            size="sm"
            onClick={refreshAllData}
            disabled={isProductsLoading}
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isProductsLoading ? 'animate-spin' : ''}`} />
            Refresh
          </Button>
        </div>
      </div>

      {operationSuccessMsg && (
        <div className="p-3.5 rounded-xl bg-emerald-950/40 border border-emerald-800 text-emerald-300 text-xs flex items-center justify-between">
          <div className="flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4 text-emerald-400" />
            <span>{operationSuccessMsg}</span>
          </div>
          <button
            onClick={() => setOperationSuccessMsg(null)}
            className="text-emerald-400 hover:text-white"
          >
            ×
          </button>
        </div>
      )}

      {/* KPI Overview Strip */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <Card>
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">
              Total Catalog SKUs
            </span>
            <Package className="w-4 h-4 text-cyan-400" />
          </div>
          <div className="text-2xl font-bold text-white mt-2">
            {products.length}
          </div>
          <div className="text-xs text-slate-400 mt-1">
            Active tracking items
          </div>
        </Card>

        <Card>
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">
              Low-Stock Alerts
            </span>
            <AlertTriangle className="w-4 h-4 text-amber-400" />
          </div>
          <div className="text-2xl font-bold text-amber-400 mt-2">
            {alerts.length}
          </div>
          <div className="text-xs text-slate-400 mt-1">
            {alerts.length > 0 ? 'Requires stock replenishment' : 'All SKUs above safety stock'}
          </div>
        </Card>

        <Card>
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">
              Total Units On Hand
            </span>
            <TrendingUp className="w-4 h-4 text-emerald-400" />
          </div>
          <div className="text-2xl font-bold text-white mt-2">
            {products.reduce((acc, p) => acc + (p.quantity_on_hand || 0), 0).toLocaleString()}
          </div>
          <div className="text-xs text-slate-400 mt-1">
            Units available in warehouse
          </div>
        </Card>

        <Card>
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">
              Units On Order
            </span>
            <Package className="w-4 h-4 text-indigo-400" />
          </div>
          <div className="text-2xl font-bold text-indigo-400 mt-2">
            {products.reduce((acc, p) => acc + (p.quantity_on_order || 0), 0).toLocaleString()}
          </div>
          <div className="text-xs text-slate-400 mt-1">
            Open purchase orders
          </div>
        </Card>
      </div>

      {/* Tabs Navigation */}
      <div className="flex border-b border-slate-800 gap-6 text-sm">
        <button
          onClick={() => setActiveTab('catalog')}
          className={`pb-3 font-semibold transition-colors flex items-center gap-2 ${
            activeTab === 'catalog'
              ? 'text-indigo-400 border-b-2 border-indigo-500'
              : 'text-slate-400 hover:text-slate-200'
          }`}
        >
          <Package className="w-4 h-4" />
          Product Catalog ({products.length})
        </button>

        <button
          onClick={() => setActiveTab('alerts')}
          className={`pb-3 font-semibold transition-colors flex items-center gap-2 ${
            activeTab === 'alerts'
              ? 'text-indigo-400 border-b-2 border-indigo-500'
              : 'text-slate-400 hover:text-slate-200'
          }`}
        >
          <AlertTriangle className="w-4 h-4" />
          Low-Stock Alerts ({alerts.length})
        </button>

        {isPrivileged && (
          <button
            onClick={() => setActiveTab('replenishment')}
            className={`pb-3 font-semibold transition-colors flex items-center gap-2 ${
              activeTab === 'replenishment'
                ? 'text-indigo-400 border-b-2 border-indigo-500'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <RefreshCw className="w-4 h-4" />
            Replenishment Engine ({replenishment.length})
          </button>
        )}
      </div>

      {/* Tab 1: Product Catalog */}
      {activeTab === 'catalog' && (
        <Card bodyClassName="!p-0">
          {/* Controls Bar */}
          <div className="p-4 border-b border-slate-800 flex flex-wrap items-center justify-between gap-3 bg-slate-900/60">
            <div className="flex flex-wrap items-center gap-3 flex-1 min-w-[280px]">
              {/* Search */}
              <div className="relative flex-1 max-w-sm">
                <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
                <input
                  type="text"
                  placeholder="Search by SKU or Product Name..."
                  value={searchQuery}
                  onChange={(e) => {
                    setSearchQuery(e.target.value)
                    setCatalogPage(1)
                  }}
                  className="w-full pl-9 pr-3 py-1.5 bg-slate-950 border border-slate-800 rounded-lg text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-indigo-500"
                />
              </div>

              {/* Low stock filter toggle */}
              <label className="flex items-center gap-2 text-xs text-slate-300 cursor-pointer select-none">
                <input
                  type="checkbox"
                  checked={filterLowStockOnly}
                  onChange={(e) => {
                    setFilterLowStockOnly(e.target.checked)
                    setCatalogPage(1)
                  }}
                  className="rounded bg-slate-950 border-slate-800 text-indigo-600 focus:ring-0 focus:ring-offset-0"
                />
                Show Low-Stock Only
              </label>
            </div>
          </div>

          {/* Table */}
          {isProductsLoading ? (
            <SkeletonTable rows={8} columns={7} />
          ) : productError ? (
            <div className="p-8 text-center text-rose-400 text-xs">
              {productError}
            </div>
          ) : paginatedProducts.length === 0 ? (
            <EmptyState
              icon={<Package className="w-6 h-6 text-slate-500" />}
              title="No Products Found"
              description="No inventory items matched your active search query or low-stock filter."
              action={
                (searchQuery || filterLowStockOnly) ? (
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => {
                      setSearchQuery('')
                      setFilterLowStockOnly(false)
                      setCatalogPage(1)
                    }}
                  >
                    Reset Inventory Filters
                  </Button>
                ) : undefined
              }
            />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse text-xs">
                <thead>
                  <tr className="border-b border-slate-800 text-slate-400 font-semibold uppercase tracking-wider bg-slate-950/40">
                    <th className="py-3 px-4">SKU</th>
                    <th className="py-3 px-4">Product Name</th>
                    <th className="py-3 px-4 text-right">Stock On Hand</th>
                    <th className="py-3 px-4 text-right">Stock On Order</th>
                    <th className="py-3 px-4 text-right">Safety Stock</th>
                    <th className="py-3 px-4 text-center">Availability</th>
                    <th className="py-3 px-4 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60">
                  {paginatedProducts.map((p) => (
                    <tr
                      key={p.id}
                      className="hover:bg-slate-800/30 transition-colors"
                    >
                      <td className="py-3 px-4 font-mono font-medium text-indigo-400">
                        {p.sku}
                      </td>
                      <td className="py-3 px-4">
                        <div className="text-white font-medium">{p.name}</div>
                        {p.description && (
                          <div className="text-[11px] text-slate-400 max-w-xs truncate">
                            {p.description}
                          </div>
                        )}
                      </td>
                      <td className="py-3 px-4 text-right font-mono font-semibold text-white">
                        {p.quantity_on_hand.toLocaleString()}
                      </td>
                      <td className="py-3 px-4 text-right font-mono text-slate-300">
                        {p.quantity_on_order.toLocaleString()}
                      </td>
                      <td className="py-3 px-4 text-right font-mono text-slate-400">
                        {p.safety_stock}
                      </td>
                      <td className="py-3 px-4 text-center">
                        {getProductAvailabilityBadge(p)}
                      </td>
                      <td className="py-3 px-4 text-right">
                        <div className="flex items-center justify-end gap-1.5">
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => handleOpenMovements(p)}
                            className="text-slate-300 hover:text-white !py-1 !px-2 text-[11px]"
                            title="View stock movement history"
                          >
                            <History className="w-3.5 h-3.5" />
                            History
                          </Button>
                          {isPrivileged && (
                            <Button
                              variant="secondary"
                              size="sm"
                              onClick={() => {
                                setOperatingProduct(p)
                                setOperationType('IN')
                                setOperationQty(10)
                                setOperationReason('')
                                setOperationReference('')
                                setOperationError(null)
                              }}
                              className="!py-1 !px-2.5 text-[11px]"
                            >
                              <SlidersHorizontal className="w-3 h-3" />
                              Stock Op
                            </Button>
                          )}
                        </div>
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
              Showing {filteredProducts.length > 0 ? (catalogPage - 1) * catalogPageSize + 1 : 0} to{' '}
              {Math.min(catalogPage * catalogPageSize, filteredProducts.length)} of {filteredProducts.length} products
            </div>
            <div className="flex items-center gap-2">
              <Button
                variant="secondary"
                size="sm"
                onClick={() => setCatalogPage((cp) => Math.max(1, cp - 1))}
                disabled={catalogPage <= 1}
              >
                <ChevronLeft className="w-3.5 h-3.5" />
                Previous
              </Button>
              <span className="text-slate-300 px-2 font-mono">
                {catalogPage} / {totalCatalogPages}
              </span>
              <Button
                variant="secondary"
                size="sm"
                onClick={() => setCatalogPage((cp) => Math.min(totalCatalogPages, cp + 1))}
                disabled={catalogPage >= totalCatalogPages}
              >
                Next
                <ChevronRight className="w-3.5 h-3.5" />
              </Button>
            </div>
          </div>
        </Card>
      )}

      {/* Tab 2: Low-Stock Alerts */}
      {activeTab === 'alerts' && (
        <Card bodyClassName="!p-0">
          <div className="p-4 border-b border-slate-800 flex items-center justify-between bg-slate-900/60">
            <div>
              <h3 className="text-sm font-semibold text-white m-0">
                Low-Stock Threshold Breaches ({alerts.length})
              </h3>
              <p className="text-xs text-slate-400 mt-0.5 m-0">
                Items where warehouse stock on hand is at or below defined safety stock bounds
              </p>
            </div>
          </div>

          {isAlertsLoading ? (
            <div className="p-16 flex justify-center">
              <LoadingSpinner size="lg" label="Evaluating safety stock thresholds..." />
            </div>
          ) : alerts.length === 0 ? (
            <div className="p-12 text-center text-emerald-400 text-xs">
              All inventory items are currently above their safety stock levels.
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse text-xs">
                <thead>
                  <tr className="border-b border-slate-800 text-slate-400 font-semibold uppercase tracking-wider bg-slate-950/40">
                    <th className="py-3 px-4">SKU</th>
                    <th className="py-3 px-4">Product Name</th>
                    <th className="py-3 px-4 text-right">On Hand</th>
                    <th className="py-3 px-4 text-right">On Order</th>
                    <th className="py-3 px-4 text-right">Safety Stock</th>
                    <th className="py-3 px-4 text-right">Target Stock</th>
                    <th className="py-3 px-4 text-right">Needed Qty</th>
                    <th className="py-3 px-4 text-center">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60">
                  {alerts.map((item) => (
                    <tr key={item.sku} className="hover:bg-slate-800/30 transition-colors">
                      <td className="py-3 px-4 font-mono font-medium text-amber-400">
                        {item.sku}
                      </td>
                      <td className="py-3 px-4 text-white font-medium">
                        {item.name}
                      </td>
                      <td className="py-3 px-4 text-right font-mono font-bold text-rose-400">
                        {item.quantity_on_hand}
                      </td>
                      <td className="py-3 px-4 text-right font-mono text-slate-300">
                        {item.quantity_on_order}
                      </td>
                      <td className="py-3 px-4 text-right font-mono text-slate-400">
                        {item.safety_stock}
                      </td>
                      <td className="py-3 px-4 text-right font-mono text-slate-400">
                        {item.target_stock}
                      </td>
                      <td className="py-3 px-4 text-right font-mono font-bold text-emerald-400">
                        +{item.replenishment_quantity}
                      </td>
                      <td className="py-3 px-4 text-center">
                        <Badge
                          variant={item.status === 'OUT_OF_STOCK' ? 'danger' : 'warning'}
                          size="sm"
                        >
                          {item.status}
                        </Badge>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      )}

      {/* Tab 3: Prescriptive Replenishment (Privileged) */}
      {activeTab === 'replenishment' && isPrivileged && (
        <Card bodyClassName="!p-0">
          <div className="p-4 border-b border-slate-800 flex items-center justify-between bg-slate-900/60">
            <div>
              <h3 className="text-sm font-semibold text-white m-0">
                Prescriptive Replenishment Suggestions ({replenishment.length})
              </h3>
              <p className="text-xs text-slate-400 mt-0.5 m-0">
                Actionable reorder quantities synthesized from sales velocity and safety buffer targets
              </p>
            </div>
          </div>

          {isReplenishmentLoading ? (
            <div className="p-16 flex justify-center">
              <LoadingSpinner size="lg" label="Computing demand velocity and suggested replenishment..." />
            </div>
          ) : replenishment.length === 0 ? (
            <div className="p-12 text-center text-slate-400 text-xs">
              No replenishment items flagged at this time.
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse text-xs">
                <thead>
                  <tr className="border-b border-slate-800 text-slate-400 font-semibold uppercase tracking-wider bg-slate-950/40">
                    <th className="py-3 px-4">SKU</th>
                    <th className="py-3 px-4">Product Name</th>
                    <th className="py-3 px-4 text-right">On Hand</th>
                    <th className="py-3 px-4 text-right">On Order</th>
                    <th className="py-3 px-4 text-right">Units Sold</th>
                    <th className="py-3 px-4 text-right">Target Stock</th>
                    <th className="py-3 px-4 text-right">Suggested Order</th>
                    <th className="py-3 px-4 text-center">Urgency</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60">
                  {replenishment.map((item) => (
                    <tr key={item.sku} className="hover:bg-slate-800/30 transition-colors">
                      <td className="py-3 px-4 font-mono font-medium text-indigo-400">
                        {item.sku}
                      </td>
                      <td className="py-3 px-4 text-white font-medium">
                        {item.name}
                      </td>
                      <td className="py-3 px-4 text-right font-mono text-slate-200">
                        {item.quantity_on_hand}
                      </td>
                      <td className="py-3 px-4 text-right font-mono text-slate-300">
                        {item.quantity_on_order}
                      </td>
                      <td className="py-3 px-4 text-right font-mono text-slate-400">
                        {item.units_sold}
                      </td>
                      <td className="py-3 px-4 text-right font-mono text-slate-400">
                        {item.target_stock}
                      </td>
                      <td className="py-3 px-4 text-right font-mono font-bold text-emerald-400">
                        +{item.suggested_replenishment} units
                      </td>
                      <td className="py-3 px-4 text-center">
                        <Badge
                          variant={
                            item.urgency === 'CRITICAL'
                              ? 'danger'
                              : item.urgency === 'WARNING'
                              ? 'warning'
                              : 'neutral'
                          }
                          size="sm"
                        >
                          {item.urgency}
                        </Badge>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      )}

      {/* Modal 1: Stock Movement Audit Trail */}
      <Modal
        isOpen={viewingMovementsProduct !== null}
        onClose={() => setViewingMovementsProduct(null)}
        title={`Stock Movements: ${viewingMovementsProduct?.name || ''} (${viewingMovementsProduct?.sku || ''})`}
        description="Immutable audit trail of inventory balance modifications"
        maxWidth="xl"
      >
        <div className="space-y-4">
          {isMovementsLoading ? (
            <div className="p-8 flex justify-center">
              <LoadingSpinner size="md" label="Loading movement audit trail..." />
            </div>
          ) : movements.length === 0 ? (
            <div className="p-8 text-center text-slate-400 text-xs">
              No historical stock movements recorded for this item.
            </div>
          ) : (
            <div className="border border-slate-800 rounded-xl overflow-hidden max-h-96 overflow-y-auto">
              <table className="w-full text-left border-collapse text-xs">
                <thead>
                  <tr className="border-b border-slate-800 bg-slate-950 text-slate-400 uppercase tracking-wider sticky top-0">
                    <th className="py-2.5 px-3">Type</th>
                    <th className="py-2.5 px-3 text-center">Quantity</th>
                    <th className="py-2.5 px-3 text-center">Stock Transition</th>
                    <th className="py-2.5 px-3">Reference / Reason</th>
                    <th className="py-2.5 px-3">Date</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60 bg-slate-900/40">
                  {movements.map((m) => (
                    <tr key={m.id} className="hover:bg-slate-800/20">
                      <td className="py-2.5 px-3">
                        <Badge
                          variant={
                            m.movement_type === 'IN'
                              ? 'success'
                              : m.movement_type === 'OUT'
                              ? 'danger'
                              : 'primary'
                          }
                          size="sm"
                        >
                          {m.movement_type}
                        </Badge>
                      </td>
                      <td className="py-2.5 px-3 text-center font-mono font-semibold text-white">
                        {m.movement_type === 'OUT' ? `-${m.quantity}` : `+${m.quantity}`}
                      </td>
                      <td className="py-2.5 px-3 text-center font-mono text-slate-400">
                        {m.previous_quantity} &rarr; <span className="text-white font-bold">{m.new_quantity}</span>
                      </td>
                      <td className="py-2.5 px-3 text-slate-300">
                        <div>{m.reference || '—'}</div>
                        {m.reason && (
                          <div className="text-[11px] text-slate-400 italic">{m.reason}</div>
                        )}
                      </td>
                      <td className="py-2.5 px-3 font-mono text-slate-400">
                        {m.created_at ? m.created_at.split('T')[0] : '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          <div className="flex justify-end pt-2">
            <Button
              variant="secondary"
              size="sm"
              onClick={() => setViewingMovementsProduct(null)}
            >
              Close History
            </Button>
          </div>
        </div>
      </Modal>

      {/* Modal 2: Stock Operations (Stock In / Stock Out / Adjust) */}
      <Modal
        isOpen={operatingProduct !== null}
        onClose={() => setOperatingProduct(null)}
        title={`Stock Operation: ${operatingProduct?.sku}`}
        description={`Current on-hand: ${operatingProduct?.quantity_on_hand} units`}
      >
        {operatingProduct && (
          <form onSubmit={handleStockOperationSubmit} className="space-y-4">
            {operationError && (
              <div className="p-3 rounded-lg bg-rose-950/40 border border-rose-800 text-rose-300 text-xs">
                {operationError}
              </div>
            )}

            {/* Operation Type Switcher */}
            <div>
              <label className="text-xs font-semibold text-slate-300 block mb-2">
                Operation Action
              </label>
              <div className="grid grid-cols-3 gap-2">
                <button
                  type="button"
                  onClick={() => setOperationType('IN')}
                  className={`p-2.5 rounded-xl border text-xs font-semibold flex items-center justify-center gap-1.5 transition-colors ${
                    operationType === 'IN'
                      ? 'bg-emerald-600/20 border-emerald-500 text-emerald-300'
                      : 'bg-slate-950 border-slate-800 text-slate-400 hover:text-slate-200'
                  }`}
                >
                  <ArrowDownCircle className="w-3.5 h-3.5" />
                  Stock In
                </button>
                <button
                  type="button"
                  onClick={() => setOperationType('OUT')}
                  className={`p-2.5 rounded-xl border text-xs font-semibold flex items-center justify-center gap-1.5 transition-colors ${
                    operationType === 'OUT'
                      ? 'bg-rose-600/20 border-rose-500 text-rose-300'
                      : 'bg-slate-950 border-slate-800 text-slate-400 hover:text-slate-200'
                  }`}
                >
                  <ArrowUpCircle className="w-3.5 h-3.5" />
                  Stock Out
                </button>
                <button
                  type="button"
                  onClick={() => setOperationType('ADJUST')}
                  className={`p-2.5 rounded-xl border text-xs font-semibold flex items-center justify-center gap-1.5 transition-colors ${
                    operationType === 'ADJUST'
                      ? 'bg-indigo-600/20 border-indigo-500 text-indigo-300'
                      : 'bg-slate-950 border-slate-800 text-slate-400 hover:text-slate-200'
                  }`}
                >
                  <SlidersHorizontal className="w-3.5 h-3.5" />
                  Adjust Count
                </button>
              </div>
            </div>

            {/* Quantity */}
            <div>
              <label className="text-xs font-semibold text-slate-300 block mb-1">
                {operationType === 'ADJUST' ? 'Exact Counted Quantity' : 'Units Quantity'}
              </label>
              <input
                type="number"
                min={operationType === 'ADJUST' ? 0 : 1}
                value={operationQty}
                onChange={(e) => setOperationQty(Math.max(0, parseInt(e.target.value) || 0))}
                required
                className="w-full p-2.5 bg-slate-950 border border-slate-800 rounded-lg text-xs text-white font-mono focus:outline-none focus:border-indigo-500"
              />
              <span className="text-[11px] text-slate-400 mt-1 block">
                {operationType === 'IN' && `Adds units to existing on-hand stock`}
                {operationType === 'OUT' && `Deducts units from warehouse (max ${operatingProduct.quantity_on_hand})`}
                {operationType === 'ADJUST' && `Replaces stock balance after physical stocktake`}
              </span>
            </div>

            {/* Reference */}
            <div>
              <label className="text-xs font-semibold text-slate-300 block mb-1">
                Reference Code (Optional)
              </label>
              <input
                type="text"
                placeholder="e.g. PO-9842, Audit-Sheet-2026, Dispatch-04"
                value={operationReference}
                onChange={(e) => setOperationReference(e.target.value)}
                className="w-full p-2.5 bg-slate-950 border border-slate-800 rounded-lg text-xs text-slate-200 focus:outline-none focus:border-indigo-500"
              />
            </div>

            {/* Reason */}
            <div>
              <label className="text-xs font-semibold text-slate-300 block mb-1">
                Reason / Justification (Optional)
              </label>
              <input
                type="text"
                placeholder="e.g. Supplier delivery, Annual stock reconciliation, Damaged return"
                value={operationReason}
                onChange={(e) => setOperationReason(e.target.value)}
                className="w-full p-2.5 bg-slate-950 border border-slate-800 rounded-lg text-xs text-slate-200 focus:outline-none focus:border-indigo-500"
              />
            </div>

            <div className="pt-3 border-t border-slate-800 flex items-center justify-end gap-2">
              <Button
                type="button"
                variant="secondary"
                size="sm"
                onClick={() => setOperatingProduct(null)}
                disabled={isSubmittingOperation}
              >
                Cancel
              </Button>
              <Button
                type="submit"
                variant="primary"
                size="sm"
                disabled={isSubmittingOperation}
              >
                {isSubmittingOperation ? 'Processing...' : `Confirm ${operationType}`}
              </Button>
            </div>
          </form>
        )}
      </Modal>

      {/* Confirmation Dialog for Sensitive Stock Operations */}
      <ConfirmModal
        isOpen={isConfirmStockOpen}
        onClose={() => setIsConfirmStockOpen(false)}
        onConfirm={executeStockOperation}
        title={`Confirm Stock ${operationType === 'IN' ? 'Receipt' : operationType === 'OUT' ? 'Dispatch' : 'Adjustment'}`}
        message={`Are you sure you want to execute a physical stock ${operationType} operation for ${operatingProduct?.name}?`}
        details={
          operatingProduct ? (
            <div className="space-y-1">
              <div><strong>Product SKU:</strong> {operatingProduct.sku}</div>
              <div><strong>Operation Type:</strong> {operationType === 'IN' ? 'Stock In (+)' : operationType === 'OUT' ? 'Stock Out (-)' : 'Physical Inventory Reconciliation (=)'}</div>
              <div><strong>Units:</strong> {operationQty}</div>
              <div><strong>Current Stock:</strong> {operatingProduct.quantity_on_hand} units</div>
              <div><strong>Projected Result:</strong> {
                operationType === 'IN'
                  ? operatingProduct.quantity_on_hand + Number(operationQty)
                  : operationType === 'OUT'
                    ? operatingProduct.quantity_on_hand - Number(operationQty)
                    : Number(operationQty)
              } units on hand</div>
              {operationReference && <div><strong>Reference:</strong> {operationReference}</div>}
              {operationReason && <div><strong>Reason:</strong> {operationReason}</div>}
            </div>
          ) : null
        }
        confirmLabel={`Yes, Execute Stock ${operationType}`}
        variant={operationType === 'OUT' ? 'warning' : 'primary'}
        isLoading={isSubmittingOperation}
      />
    </div>
  )
}

export default InventoryPage
