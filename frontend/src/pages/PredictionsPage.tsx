import React, { useState, useEffect } from 'react'
import {
  TrendingUp,
  TrendingDown,
  AlertTriangle,
  Package,
  RotateCcw,
  BarChart3,
  CheckCircle2,
  AlertCircle,
  HelpCircle,
  Calendar,
  Sparkles,
  ArrowRight,
  Send,
  X,
  Target,
  Calculator,
  ShieldCheck,
} from 'lucide-react'
import { predictionService } from '../services/prediction.service'
import { approvalService } from '../services/approval.service'
import apiClient from '../services/api'
import type {
  InventoryRiskItem,
  InventoryRiskResponse,
  ModelPerformanceResponse,
  ProductDemandItem,
  ProductDemandResponse,
  SalesForecastResponse,
} from '../types/prediction.types'
import Card from '../components/common/Card'
import Badge from '../components/common/Badge'
import Button from '../components/common/Button'
import LoadingSpinner from '../components/common/LoadingSpinner'

export const PredictionsPage: React.FC = () => {
  // Data state
  const [forecastData, setForecastData] = useState<SalesForecastResponse | null>(null)
  const [demandData, setDemandData] = useState<ProductDemandResponse | null>(null)
  const [riskData, setRiskData] = useState<InventoryRiskResponse | null>(null)
  const [modelPerf, setModelPerf] = useState<ModelPerformanceResponse | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [isRefreshing, setIsRefreshing] = useState(false)

  // Navigation tab state
  const [activeTab, setActiveTab] = useState<'FORECAST' | 'DEMAND' | 'RISK' | 'MODELS'>('FORECAST')
  const [demandFilter, setDemandFilter] = useState<'TOP' | 'INCREASING' | 'DECREASING'>('TOP')
  const [riskFilter, setRiskFilter] = useState<'ALL' | 'CRITICAL' | 'MODERATE' | 'HEALTHY'>('ALL')

  // Prepare Requisition Modal state
  const [prepModalOpen, setPrepModalOpen] = useState(false)
  const [selectedRiskItem, setSelectedRiskItem] = useState<InventoryRiskItem | null>(null)
  const [reqQuantity, setReqQuantity] = useState<number>(10)
  const [reqReason, setReqReason] = useState<string>('')
  const [isSubmittingReq, setIsSubmittingReq] = useState(false)
  const [reqSuccessMessage, setReqSuccessMessage] = useState<string | null>(null)
  const [reqErrorMessage, setReqErrorMessage] = useState<string | null>(null)

  const fetchData = async () => {
    try {
      setIsRefreshing(true)
      const [fData, dData, rData, mData] = await Promise.all([
        predictionService.getSalesForecast(),
        predictionService.getProductDemand(),
        predictionService.getInventoryRisk(),
        predictionService.getModelPerformance(),
      ])
      setForecastData(fData)
      setDemandData(dData)
      setRiskData(rData)
      setModelPerf(mData)
    } catch (err) {
      console.error('Failed to load predictions data:', err)
    } finally {
      setIsLoading(false)
      setIsRefreshing(false)
    }
  }

  useEffect(() => {
    let ignore = false
    Promise.all([
      predictionService.getSalesForecast(),
      predictionService.getProductDemand(),
      predictionService.getInventoryRisk(),
      predictionService.getModelPerformance(),
    ])
      .then(([fData, dData, rData, mData]) => {
        if (!ignore) {
          setForecastData(fData)
          setDemandData(dData)
          setRiskData(rData)
          setModelPerf(mData)
          setIsLoading(false)
        }
      })
      .catch((err) => {
        if (!ignore) {
          console.error('Failed to load predictions:', err)
          setIsLoading(false)
        }
      })

    return () => {
      ignore = true
    }
  }, [])

  const openRequisitionModal = (item: InventoryRiskItem) => {
    setSelectedRiskItem(item)
    setReqQuantity(item.suggested_replenishment_quantity || 15)
    setReqReason(`Automated predictive replenishment: ${item.risk_reason}`)
    setReqSuccessMessage(null)
    setReqErrorMessage(null)
    setPrepModalOpen(true)
  }

  const submitRequisition = async () => {
    if (!selectedRiskItem) return
    try {
      setIsSubmittingReq(true)
      setReqErrorMessage(null)
      const res = await approvalService.approve ? await (async () => {
        const payload = {
          request_type: 'PURCHASE_REQUISITION' as const,
          title: `Replenish ${reqQuantity} units of ${selectedRiskItem.product_name} (${selectedRiskItem.sku})`,
          description: reqReason,
          assigned_role: 'Manager',
          action_payload: {
            items: [
              {
                sku: selectedRiskItem.sku,
                name: selectedRiskItem.product_name,
                quantity: reqQuantity,
                safety_stock: selectedRiskItem.safety_stock,
                target_stock: selectedRiskItem.target_stock,
                current_on_hand: selectedRiskItem.quantity_on_hand,
              },
            ],
            total_units: reqQuantity,
            justification: reqReason,
          },
        }
        const { data } = await apiClient.post('/approvals', payload)
        return data
      })() : null

      setReqSuccessMessage(
        `Purchase requisition '${res?.request_code || 'REQ-PO'}' submitted with PENDING status! Review on Approvals Dashboard.`
      )
      // Refresh inventory risk
      const newRisk = await predictionService.getInventoryRisk()
      setRiskData(newRisk)
    } catch (err: any) {
      setReqErrorMessage(err.response?.data?.detail || 'Failed to submit requisition proposal.')
    } finally {
      setIsSubmittingReq(false)
    }
  }

  // Derived metrics
  const totalForecastedRev = (forecastData?.forecast_next_3_months || []).reduce(
    (acc, cur) => acc + cur.predicted_revenue,
    0
  )

  const topDemandProduct = demandData?.top_demanded_products?.[0]
  const criticalCount = riskData?.critical_risk_count ?? 0

  const filteredRisks = (riskData?.all_evaluated_products || []).filter((item) => {
    if (riskFilter === 'ALL') return true
    return item.shortage_risk_level === riskFilter
  })

  const demandItems = ((): ProductDemandItem[] => {
    if (!demandData) return []
    if (demandFilter === 'INCREASING') return demandData.increasing_demand_products
    if (demandFilter === 'DECREASING') return demandData.decreasing_demand_products
    return demandData.top_demanded_products
  })()

  // Find max revenue for chart scaling
  const allRevenues = [
    ...(forecastData?.historical_data || []).map((h) => h.revenue),
    ...(forecastData?.forecast_next_3_months || []).map((f) => f.predicted_revenue),
  ]
  const maxRevenue = Math.max(...allRevenues, 150000)

  if (isLoading) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] text-slate-400">
        <LoadingSpinner size="lg" className="mb-4" />
        <p className="text-sm">Initializing predictive models and time-series series...</p>
      </div>
    )
  }

  return (
    <div className="space-y-6 animate-fade-in pb-12">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-bold tracking-tight text-white m-0">
              Predictive Analytics &amp; Forecasting
            </h1>
            <Badge variant="primary" size="sm">
              Time-Series Intelligence
            </Badge>
          </div>
          <p className="text-xs text-slate-400 mt-1">
            Statistical revenue projection, product demand velocity, and inventory shortage risk analysis.
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
            Re-run Predictions
          </Button>
        </div>
      </div>

      {/* KPI Overview Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <Card className="bg-slate-900/80 border-slate-800 p-4">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-slate-400 uppercase tracking-wider">
              3-Month Projected Revenue
            </span>
            <div className="p-2 rounded-lg bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
              <TrendingUp className="w-4 h-4" />
            </div>
          </div>
          <div className="mt-2 text-2xl font-bold text-white">
            ${(totalForecastedRev / 1000).toFixed(1)}k
          </div>
          <p className="text-[11px] text-emerald-400 mt-1 flex items-center gap-1 font-medium">
            <Sparkles className="w-3 h-3" />
            {forecastData?.growth_rate_percent && forecastData.growth_rate_percent >= 0 ? '+' : ''}
            {forecastData?.growth_rate_percent}% projected growth
          </p>
        </Card>

        <Card className="bg-slate-900/80 border-slate-800 p-4">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-slate-400 uppercase tracking-wider">
              Critical Shortage Risks
            </span>
            <div className="p-2 rounded-lg bg-rose-500/10 text-rose-400 border border-rose-500/20">
              <AlertTriangle className="w-4 h-4" />
            </div>
          </div>
          <div className="mt-2 text-2xl font-bold text-white">{criticalCount}</div>
          <p className="text-[11px] text-rose-400/80 mt-1 flex items-center gap-1">
            <AlertCircle className="w-3 h-3" /> Products below safety threshold
          </p>
        </Card>

        <Card className="bg-slate-900/80 border-slate-800 p-4">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-slate-400 uppercase tracking-wider">
              Top Demand Velocity
            </span>
            <div className="p-2 rounded-lg bg-cyan-500/10 text-cyan-400 border border-cyan-500/20">
              <Package className="w-4 h-4" />
            </div>
          </div>
          <div className="mt-2 text-lg font-bold text-white truncate max-w-[180px]">
            {topDemandProduct?.product_name || 'Top SKU'}
          </div>
          <p className="text-[11px] text-cyan-400 mt-1 truncate">
            {topDemandProduct?.projected_monthly_demand} units/mo ({topDemandProduct?.sku})
          </p>
        </Card>

        <Card className="bg-slate-900/80 border-slate-800 p-4">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-slate-400 uppercase tracking-wider">
              Selected Forecast Model
            </span>
            <div className="p-2 rounded-lg bg-amber-500/10 text-amber-400 border border-amber-500/20">
              <Calculator className="w-4 h-4" />
            </div>
          </div>
          <div className="mt-2 text-sm font-bold text-white truncate max-w-[200px]">
            {forecastData?.selected_model || 'OLS Regression'}
          </div>
          <p className="text-[11px] text-amber-400/80 mt-1 flex items-center gap-1">
            <Target className="w-3 h-3" /> Minimal test RMSE on held-out split
          </p>
        </Card>
      </div>

      {/* Main Tab Navigation */}
      <div className="flex flex-wrap items-center gap-2 p-1.5 bg-slate-950/80 rounded-2xl border border-slate-800">
        {[
          { id: 'FORECAST', label: 'Sales Revenue Forecast', icon: <TrendingUp className="w-4 h-4" /> },
          { id: 'DEMAND', label: 'Product Demand Trends', icon: <Package className="w-4 h-4" /> },
          { id: 'RISK', label: 'Inventory Shortage Risks', icon: <AlertTriangle className="w-4 h-4" /> },
          { id: 'MODELS', label: 'Model Performance & Split', icon: <BarChart3 className="w-4 h-4" /> },
        ].map((t) => (
          <button
            key={t.id}
            type="button"
            onClick={() => setActiveTab(t.id as any)}
            className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-medium transition-all ${
              activeTab === t.id
                ? 'bg-indigo-600 text-white shadow-md'
                : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900'
            }`}
          >
            {t.icon}
            {t.label}
          </button>
        ))}
      </div>

      {/* TAB 1: Sales Revenue Forecast */}
      {activeTab === 'FORECAST' && forecastData && (
        <div className="space-y-6 animate-fade-in">
          {/* Visual Time-Series Chart */}
          <Card className="p-6 bg-slate-900/90 border-slate-800 space-y-6">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
              <div>
                <h3 className="text-sm font-bold text-white m-0 flex items-center gap-2">
                  <BarChart3 className="w-4 h-4 text-indigo-400" />
                  Monthly Recognized Revenue &amp; 3-Month Projection Horizon
                </h3>
                <p className="text-xs text-slate-400 mt-0.5">
                  Chronological progression comparing 6 actual historical months to 3 out-of-sample forecast months.
                </p>
              </div>

              {/* Legend */}
              <div className="flex items-center gap-4 text-[11px]">
                <div className="flex items-center gap-1.5">
                  <div className="w-3.5 h-3.5 rounded bg-cyan-500" />
                  <span className="text-slate-300">Actual Historical</span>
                </div>
                <div className="flex items-center gap-1.5">
                  <div className="w-3.5 h-3.5 rounded bg-indigo-500 border border-indigo-400 border-dashed" />
                  <span className="text-indigo-300 font-medium">3-Month Forecast</span>
                </div>
              </div>
            </div>

            {/* Visual Bar Chart */}
            <div className="h-64 flex items-end justify-between gap-2 sm:gap-4 pt-6 px-2 border-b border-slate-800">
              {/* Historical Bars */}
              {forecastData.historical_data.map((h) => {
                const heightPercent = Math.min(100, Math.round((h.revenue / maxRevenue) * 100))
                return (
                  <div key={h.month} className="flex-1 flex flex-col items-center gap-2 h-full justify-end group">
                    <span className="text-[10px] font-mono text-cyan-400 opacity-0 group-hover:opacity-100 transition-opacity">
                      ${(h.revenue / 1000).toFixed(1)}k
                    </span>
                    <div
                      style={{ height: `${heightPercent}%` }}
                      className="w-full max-w-[44px] rounded-t-lg bg-gradient-to-t from-cyan-600 to-cyan-400 transition-all duration-300 hover:brightness-110 shadow-xs"
                    />
                    <span className="text-[10px] font-mono text-slate-400">{h.month}</span>
                  </div>
                )
              })}

              {/* Forecast Bars */}
              {forecastData.forecast_next_3_months.map((f) => {
                const heightPercent = Math.min(100, Math.round((f.predicted_revenue / maxRevenue) * 100))
                return (
                  <div key={f.month} className="flex-1 flex flex-col items-center gap-2 h-full justify-end group">
                    <span className="text-[10px] font-mono text-indigo-300 opacity-0 group-hover:opacity-100 transition-opacity">
                      ${(f.predicted_revenue / 1000).toFixed(1)}k
                    </span>
                    <div
                      style={{ height: `${heightPercent}%` }}
                      className="w-full max-w-[44px] rounded-t-lg bg-gradient-to-t from-indigo-700 to-indigo-500 border-2 border-indigo-400 border-dashed transition-all duration-300 hover:brightness-125 shadow-lg shadow-indigo-500/20"
                    />
                    <span className="text-[10px] font-mono text-indigo-300 font-semibold">{f.month}*</span>
                  </div>
                )
              })}
            </div>

            {/* Forecast Projection Points Table */}
            <div className="overflow-x-auto rounded-xl border border-slate-800 bg-slate-950/70">
              <table className="w-full text-left text-xs">
                <thead className="bg-slate-900/80 text-[10px] text-slate-400 uppercase tracking-wider">
                  <tr>
                    <th className="px-4 py-3">Forecast Horizon</th>
                    <th className="px-4 py-3">Projected Revenue</th>
                    <th className="px-4 py-3">80% Confidence Lower Bound</th>
                    <th className="px-4 py-3">80% Confidence Upper Bound</th>
                    <th className="px-4 py-3 text-right">Trend Velocity</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800">
                  {forecastData.forecast_next_3_months.map((pt) => (
                    <tr key={pt.month} className="hover:bg-slate-900/50">
                      <td className="px-4 py-3 font-mono font-bold text-indigo-300 flex items-center gap-1.5">
                        <Calendar className="w-3.5 h-3.5 text-indigo-400" />
                        {pt.month}
                      </td>
                      <td className="px-4 py-3 text-sm font-bold text-white">
                        ${pt.predicted_revenue.toLocaleString('en-US', { minimumFractionDigits: 2 })}
                      </td>
                      <td className="px-4 py-3 text-slate-400 font-mono">
                        ${pt.lower_bound.toLocaleString('en-US', { minimumFractionDigits: 2 })}
                      </td>
                      <td className="px-4 py-3 text-slate-400 font-mono">
                        ${pt.upper_bound.toLocaleString('en-US', { minimumFractionDigits: 2 })}
                      </td>
                      <td className="px-4 py-3 text-right">
                        <span
                          className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-semibold ${
                            pt.trend_direction === 'UPWARD'
                              ? 'bg-emerald-950 text-emerald-400 border border-emerald-500/30'
                              : pt.trend_direction === 'DOWNWARD'
                              ? 'bg-rose-950 text-rose-400 border border-rose-500/30'
                              : 'bg-slate-800 text-slate-300'
                          }`}
                        >
                          {pt.trend_direction === 'UPWARD' ? (
                            <TrendingUp className="w-3 h-3" />
                          ) : (
                            <TrendingDown className="w-3 h-3" />
                          )}
                          {pt.trend_direction}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Methodology & Limitations Disclosure */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="p-3.5 rounded-xl bg-slate-950 border border-slate-800 space-y-1">
                <span className="text-[11px] font-semibold text-indigo-400 flex items-center gap-1.5">
                  <Calculator className="w-3.5 h-3.5" /> Modeling Methodology
                </span>
                <p className="text-[11px] text-slate-400 leading-relaxed">
                  {forecastData.methodology_notes}
                </p>
              </div>

              <div className="p-3.5 rounded-xl bg-slate-950 border border-slate-800 space-y-1">
                <span className="text-[11px] font-semibold text-amber-400 flex items-center gap-1.5">
                  <HelpCircle className="w-3.5 h-3.5" /> Limitations &amp; Seasonality Disclosure
                </span>
                <p className="text-[11px] text-slate-400 leading-relaxed">
                  {forecastData.limitations_disclosure}
                </p>
              </div>
            </div>
          </Card>
        </div>
      )}

      {/* TAB 2: Product Demand Trends */}
      {activeTab === 'DEMAND' && demandData && (
        <Card className="p-6 bg-slate-900/90 border-slate-800 space-y-5 animate-fade-in">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div>
              <h3 className="text-sm font-bold text-white m-0">Catalog SKU Demand Velocity</h3>
              <p className="text-xs text-slate-400 mt-0.5">
                Product-level consumption rate and demand velocity analysis across 30 catalog items.
              </p>
            </div>

            {/* Sub-tabs */}
            <div className="flex items-center gap-1 p-1 bg-slate-950 rounded-xl border border-slate-800">
              <button
                type="button"
                onClick={() => setDemandFilter('TOP')}
                className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                  demandFilter === 'TOP' ? 'bg-indigo-600 text-white' : 'text-slate-400 hover:text-white'
                }`}
              >
                Top Demand SKUs ({demandData.top_demanded_products.length})
              </button>
              <button
                type="button"
                onClick={() => setDemandFilter('INCREASING')}
                className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                  demandFilter === 'INCREASING'
                    ? 'bg-emerald-600 text-white'
                    : 'text-slate-400 hover:text-white'
                }`}
              >
                Accelerating ({demandData.increasing_demand_products.length})
              </button>
              <button
                type="button"
                onClick={() => setDemandFilter('DECREASING')}
                className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                  demandFilter === 'DECREASING'
                    ? 'bg-rose-600 text-white'
                    : 'text-slate-400 hover:text-white'
                }`}
              >
                Declining ({demandData.decreasing_demand_products.length})
              </button>
            </div>
          </div>

          {/* Demand Table */}
          <div className="overflow-x-auto rounded-xl border border-slate-800 bg-slate-950/70">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-900/80 text-[10px] text-slate-400 uppercase tracking-wider">
                <tr>
                  <th className="px-4 py-3">SKU</th>
                  <th className="px-4 py-3">Product Name</th>
                  <th className="px-4 py-3 text-right">Historical Units (6-Mo)</th>
                  <th className="px-4 py-3 text-right">Monthly Average</th>
                  <th className="px-4 py-3 text-right">Recent Month Demand</th>
                  <th className="px-4 py-3 text-right">Projected Monthly Need</th>
                  <th className="px-4 py-3 text-right">Demand Velocity</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800">
                {demandItems.map((item) => (
                  <tr key={item.sku} className="hover:bg-slate-900/50">
                    <td className="px-4 py-3 font-mono font-medium text-indigo-300">{item.sku}</td>
                    <td className="px-4 py-3 text-white font-medium">{item.product_name}</td>
                    <td className="px-4 py-3 text-right text-slate-300 font-mono">
                      {item.total_historical_units}
                    </td>
                    <td className="px-4 py-3 text-right text-slate-300 font-mono">
                      {item.monthly_average_units}
                    </td>
                    <td className="px-4 py-3 text-right text-slate-300 font-mono">
                      {item.recent_month_units}
                    </td>
                    <td className="px-4 py-3 text-right font-bold text-cyan-300 font-mono">
                      {item.projected_monthly_demand} units
                    </td>
                    <td className="px-4 py-3 text-right">
                      <span
                        className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-semibold ${
                          item.trend_direction === 'INCREASING'
                            ? 'bg-emerald-950/80 text-emerald-400 border border-emerald-500/30'
                            : item.trend_direction === 'DECREASING'
                            ? 'bg-rose-950/80 text-rose-400 border border-rose-500/30'
                            : 'bg-slate-800 text-slate-400'
                        }`}
                      >
                        {item.trend_direction === 'INCREASING' ? (
                          <TrendingUp className="w-3 h-3" />
                        ) : item.trend_direction === 'DECREASING' ? (
                          <TrendingDown className="w-3 h-3" />
                        ) : null}
                        {item.trend_percentage > 0 ? `+${item.trend_percentage}%` : `${item.trend_percentage}%`}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      {/* TAB 3: Inventory Shortage Risks & Approval Bridge */}
      {activeTab === 'RISK' && riskData && (
        <Card className="p-6 bg-slate-900/90 border-slate-800 space-y-5 animate-fade-in">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div>
              <h3 className="text-sm font-bold text-white m-0">Warehouse Shortage Risk &amp; Replenishment</h3>
              <p className="text-xs text-slate-400 mt-0.5">
                Evaluates physical stock vs. daily burn rate and open purchase orders to avert stockouts.
              </p>
            </div>

            {/* Filter pills */}
            <div className="flex items-center gap-1.5 p-1 bg-slate-950 rounded-xl border border-slate-800 text-xs">
              {(['ALL', 'CRITICAL', 'MODERATE', 'HEALTHY'] as const).map((lvl) => (
                <button
                  key={lvl}
                  type="button"
                  onClick={() => setRiskFilter(lvl)}
                  className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                    riskFilter === lvl
                      ? 'bg-indigo-600 text-white'
                      : 'text-slate-400 hover:text-white'
                  }`}
                >
                  {lvl.charAt(0) + lvl.slice(1).toLowerCase()}
                </button>
              ))}
            </div>
          </div>

          {/* Action Safeguard Notice */}
          <div className="p-3 rounded-xl bg-indigo-950/40 border border-indigo-500/30 flex items-center justify-between text-xs text-indigo-300">
            <div className="flex items-center gap-2">
              <ShieldCheck className="w-4 h-4 text-indigo-400 shrink-0" />
              <span>{riskData.action_notice}</span>
            </div>
            <span className="text-[11px] text-slate-400 font-mono">Phase 5 Integration Active</span>
          </div>

          {/* Shortage Risk Table */}
          <div className="overflow-x-auto rounded-xl border border-slate-800 bg-slate-950/70">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-900/80 text-[10px] text-slate-400 uppercase tracking-wider">
                <tr>
                  <th className="px-4 py-3">Risk Level</th>
                  <th className="px-4 py-3">SKU &amp; Product</th>
                  <th className="px-4 py-3 text-right">On-Hand</th>
                  <th className="px-4 py-3 text-right">On-Order</th>
                  <th className="px-4 py-3 text-right">Safety Stock</th>
                  <th className="px-4 py-3 text-right">Daily Burn</th>
                  <th className="px-4 py-3 text-right">Stock Runway</th>
                  <th className="px-4 py-3 text-right">Suggested Order</th>
                  <th className="px-4 py-3 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800">
                {filteredRisks.map((item) => (
                  <tr key={item.sku} className="hover:bg-slate-900/50">
                    {/* Risk Badge */}
                    <td className="px-4 py-3">
                      <span
                        className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-md text-[11px] font-bold ${
                          item.shortage_risk_level === 'CRITICAL'
                            ? 'bg-rose-950 text-rose-400 border border-rose-500/40'
                            : item.shortage_risk_level === 'MODERATE'
                            ? 'bg-amber-950 text-amber-400 border border-amber-500/40'
                            : 'bg-emerald-950 text-emerald-400 border border-emerald-500/40'
                        }`}
                      >
                        {item.shortage_risk_level === 'CRITICAL' && <AlertCircle className="w-3 h-3" />}
                        {item.shortage_risk_level}
                      </span>
                    </td>

                    {/* SKU & Name */}
                    <td className="px-4 py-3">
                      <div className="font-semibold text-white">{item.product_name}</div>
                      <div className="font-mono text-[10px] text-slate-500">{item.sku}</div>
                    </td>

                    {/* On-hand */}
                    <td className="px-4 py-3 text-right font-mono font-bold">
                      <span
                        className={
                          item.quantity_on_hand <= item.safety_stock ? 'text-rose-400' : 'text-slate-200'
                        }
                      >
                        {item.quantity_on_hand}
                      </span>
                    </td>

                    {/* On-order */}
                    <td className="px-4 py-3 text-right font-mono text-indigo-300">
                      {item.quantity_on_order}
                    </td>

                    {/* Safety stock */}
                    <td className="px-4 py-3 text-right font-mono text-slate-400">
                      {item.safety_stock}
                    </td>

                    {/* Daily burn */}
                    <td className="px-4 py-3 text-right font-mono text-slate-300">
                      {item.daily_burn_rate}/day
                    </td>

                    {/* Days runway */}
                    <td className="px-4 py-3 text-right font-mono font-semibold">
                      <span
                        className={
                          item.days_of_stock_remaining <= 7
                            ? 'text-rose-400'
                            : item.days_of_stock_remaining <= 21
                            ? 'text-amber-400'
                            : 'text-emerald-400'
                        }
                      >
                        {item.days_of_stock_remaining} days
                      </span>
                    </td>

                    {/* Suggested order */}
                    <td className="px-4 py-3 text-right font-mono font-bold text-cyan-300">
                      {item.suggested_replenishment_quantity > 0 ? (
                        `+${item.suggested_replenishment_quantity}`
                      ) : (
                        <span className="text-slate-500 font-normal">Sufficient</span>
                      )}
                    </td>

                    {/* Action */}
                    <td className="px-4 py-3 text-right">
                      {item.suggested_replenishment_quantity > 0 ? (
                        <Button
                          variant="primary"
                          size="sm"
                          onClick={() => openRequisitionModal(item)}
                          className="bg-indigo-600 hover:bg-indigo-500 text-white"
                          icon={<Send className="w-3 h-3" />}
                        >
                          Prepare Requisition
                        </Button>
                      ) : (
                        <span className="text-[11px] text-slate-500 italic">No action needed</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      {/* TAB 4: Model Performance & Time-Based Split */}
      {activeTab === 'MODELS' && modelPerf && (
        <Card className="p-6 bg-slate-900/90 border-slate-800 space-y-6 animate-fade-in">
          <div>
            <h3 className="text-sm font-bold text-white m-0">Forecasting Model Comparison &amp; Validation</h3>
            <p className="text-xs text-slate-400 mt-0.5">
              Time-series models were evaluated using chronological out-of-sample testing without look-ahead bias.
            </p>
          </div>

          {/* Split Info Cards */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="p-4 rounded-xl bg-slate-950 border border-slate-800">
              <span className="text-[10px] uppercase tracking-wider text-slate-500 font-semibold block">
                Chronological Training Window
              </span>
              <span className="text-sm font-bold text-cyan-300 mt-1 block">{modelPerf.train_period}</span>
              <p className="text-[11px] text-slate-400 mt-1">
                Models learned baseline parameters, linear slopes, and exponential smoothing states on early periods.
              </p>
            </div>

            <div className="p-4 rounded-xl bg-slate-950 border border-slate-800">
              <span className="text-[10px] uppercase tracking-wider text-slate-500 font-semibold block">
                Held-Out Out-of-Sample Test Window
              </span>
              <span className="text-sm font-bold text-indigo-300 mt-1 block">{modelPerf.test_period}</span>
              <p className="text-[11px] text-slate-400 mt-1">
                Evaluation metrics (MAE, RMSE, MAPE) were measured strictly on unseen true values.
              </p>
            </div>
          </div>

          {/* Model Metrics Table */}
          <div className="overflow-x-auto rounded-xl border border-slate-800 bg-slate-950/70">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-900/80 text-[10px] text-slate-400 uppercase tracking-wider">
                <tr>
                  <th className="px-4 py-3">Model Architecture</th>
                  <th className="px-4 py-3">Description</th>
                  <th className="px-4 py-3 text-right">MAE ($)</th>
                  <th className="px-4 py-3 text-right">RMSE ($)</th>
                  <th className="px-4 py-3 text-right">MAPE (%)</th>
                  <th className="px-4 py-3 text-right">Selection Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800">
                {modelPerf.models_evaluated.map((m) => (
                  <tr
                    key={m.model_name}
                    className={`hover:bg-slate-900/50 ${
                      m.is_best_model ? 'bg-indigo-950/20 border-l-2 border-indigo-500' : ''
                    }`}
                  >
                    <td className="px-4 py-3 font-semibold text-white">{m.model_name}</td>
                    <td className="px-4 py-3 text-slate-400 max-w-xs">{m.description}</td>
                    <td className="px-4 py-3 text-right font-mono text-slate-300">
                      ${m.mae.toLocaleString('en-US', { minimumFractionDigits: 2 })}
                    </td>
                    <td className="px-4 py-3 text-right font-mono font-bold text-white">
                      ${m.rmse.toLocaleString('en-US', { minimumFractionDigits: 2 })}
                    </td>
                    <td className="px-4 py-3 text-right font-mono text-slate-300">
                      {m.mape_percent}%
                    </td>
                    <td className="px-4 py-3 text-right">
                      {m.is_best_model ? (
                        <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded text-[11px] font-bold bg-indigo-950 text-indigo-300 border border-indigo-500/40">
                          <CheckCircle2 className="w-3 h-3 text-indigo-400" /> Optimal Model
                        </span>
                      ) : (
                        <span className="text-[11px] text-slate-500">Evaluated Baseline</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      {/* Requisition Proposal Modal (Phase 5 Human-in-the-Loop Integration) */}
      {prepModalOpen && selectedRiskItem && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-xs flex items-center justify-center p-4 z-50 animate-fade-in">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl w-full max-w-lg shadow-2xl overflow-hidden">
            {/* Modal Header */}
            <div className="px-6 py-4 border-b border-slate-800 flex items-center justify-between bg-slate-950/80">
              <div className="flex items-center gap-2">
                <div className="w-8 h-8 rounded-lg bg-indigo-950 border border-indigo-500/30 flex items-center justify-center text-indigo-400">
                  <Send className="w-4 h-4" />
                </div>
                <div>
                  <h3 className="text-sm font-bold text-white m-0">Prepare Purchase Requisition</h3>
                  <p className="text-[11px] text-slate-400 m-0">Human-in-the-Loop Approval Proposal</p>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setPrepModalOpen(false)}
                className="p-1 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Modal Body */}
            <div className="p-6 space-y-4 text-xs">
              {reqSuccessMessage && (
                <div className="p-3 rounded-xl bg-emerald-950/60 border border-emerald-500/40 text-emerald-300 flex items-center gap-2">
                  <CheckCircle2 className="w-4 h-4 shrink-0 text-emerald-400" />
                  <span>{reqSuccessMessage}</span>
                </div>
              )}

              {reqErrorMessage && (
                <div className="p-3 rounded-xl bg-rose-950/60 border border-rose-500/40 text-rose-300 flex items-center gap-2">
                  <AlertCircle className="w-4 h-4 shrink-0 text-rose-400" />
                  <span>{reqErrorMessage}</span>
                </div>
              )}

              <div className="p-3 rounded-xl bg-slate-950 border border-slate-800 space-y-1">
                <div className="font-semibold text-white text-sm">{selectedRiskItem.product_name}</div>
                <div className="text-[11px] font-mono text-indigo-300">{selectedRiskItem.sku}</div>
                <div className="text-[11px] text-slate-400 pt-1">
                  On Hand: <strong className="text-rose-400">{selectedRiskItem.quantity_on_hand}</strong> units |
                  Safety Stock: <strong>{selectedRiskItem.safety_stock}</strong> |
                  Target Stock: <strong>{selectedRiskItem.target_stock}</strong>
                </div>
              </div>

              <div>
                <label className="block text-[11px] font-semibold text-slate-300 mb-1">
                  Proposed Requisition Quantity (Units)
                </label>
                <input
                  type="number"
                  min="1"
                  value={reqQuantity}
                  onChange={(e) => setReqQuantity(Math.max(1, parseInt(e.target.value) || 1))}
                  className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-xs text-white focus:outline-none focus:border-indigo-500"
                />
              </div>

              <div>
                <label className="block text-[11px] font-semibold text-slate-300 mb-1">
                  Justification &amp; AI Predictive Context
                </label>
                <textarea
                  rows={3}
                  value={reqReason}
                  onChange={(e) => setReqReason(e.target.value)}
                  className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-xs text-white focus:outline-none focus:border-indigo-500"
                />
              </div>

              <div className="p-2.5 rounded-lg bg-amber-950/30 border border-amber-500/20 text-amber-300 text-[11px] flex items-center gap-2">
                <ShieldCheck className="w-4 h-4 shrink-0" />
                <span>
                  This proposal enters PENDING status for managerial authorization. No physical stock will be modified.
                </span>
              </div>
            </div>

            {/* Modal Footer */}
            <div className="px-6 py-3 border-t border-slate-800 flex items-center justify-end gap-2 bg-slate-950/80">
              <Button variant="secondary" size="sm" onClick={() => setPrepModalOpen(false)}>
                Cancel
              </Button>
              <Button
                variant="primary"
                size="sm"
                onClick={submitRequisition}
                disabled={isSubmittingReq || Boolean(reqSuccessMessage)}
                className="bg-indigo-600 hover:bg-indigo-500 text-white"
                icon={<ArrowRight className="w-3.5 h-3.5" />}
              >
                {isSubmittingReq ? 'Submitting Proposal...' : 'Submit to Approval Workflow'}
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default PredictionsPage
