import apiClient from './api'
import type {
  InventorySummaryReport,
  LowStockAlertReport,
  Product,
  ProductFilterParams,
  ReplenishmentItem,
  StockAdjustPayload,
  StockInPayload,
  StockMovement,
  StockOutPayload,
} from '../types/inventory.types'

export const inventoryService = {
  async listProducts(params?: ProductFilterParams): Promise<Product[]> {
    const response = await apiClient.get<Product[]>('/inventory/products', { params })
    return response.data
  },

  async getProduct(id: number): Promise<Product> {
    const response = await apiClient.get<Product>(`/inventory/products/${id}`)
    return response.data
  },

  async getLowStockAlerts(): Promise<LowStockAlertReport> {
    const response = await apiClient.get<LowStockAlertReport>('/inventory/alerts/low-stock')
    return response.data
  },

  async getReplenishmentSuggestions(): Promise<ReplenishmentItem[]> {
    const response = await apiClient.get<ReplenishmentItem[]>('/analytics/replenishment')
    return response.data
  },

  async getProductMovements(productId: number): Promise<StockMovement[]> {
    const response = await apiClient.get<StockMovement[]>(
      `/inventory/products/${productId}/movements`,
    )
    return response.data
  },

  async stockIn(payload: StockInPayload): Promise<StockMovement> {
    const response = await apiClient.post<StockMovement>('/inventory/stock/in', payload)
    return response.data
  },

  async stockOut(payload: StockOutPayload): Promise<StockMovement> {
    const response = await apiClient.post<StockMovement>('/inventory/stock/out', payload)
    return response.data
  },

  async stockAdjust(payload: StockAdjustPayload): Promise<StockMovement> {
    const response = await apiClient.post<StockMovement>(
      '/inventory/stock/adjust',
      payload,
    )
    return response.data
  },

  async getInventorySummary(): Promise<InventorySummaryReport> {
    const response = await apiClient.get<InventorySummaryReport>(
      '/inventory/reports/summary',
    )
    return response.data
  },
}
