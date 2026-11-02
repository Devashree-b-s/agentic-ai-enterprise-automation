import apiClient from './api'
import type {
  InventoryRiskResponse,
  ModelPerformanceResponse,
  ProductDemandResponse,
  SalesForecastResponse,
} from '../types/prediction.types'

export const predictionService = {
  async getSalesForecast(): Promise<SalesForecastResponse> {
    const response = await apiClient.get<SalesForecastResponse>('/predictions/sales-forecast')
    return response.data
  },

  async getProductDemand(): Promise<ProductDemandResponse> {
    const response = await apiClient.get<ProductDemandResponse>('/predictions/product-demand')
    return response.data
  },

  async getInventoryRisk(): Promise<InventoryRiskResponse> {
    const response = await apiClient.get<InventoryRiskResponse>('/predictions/inventory-risk')
    return response.data
  },

  async getModelPerformance(): Promise<ModelPerformanceResponse> {
    const response = await apiClient.get<ModelPerformanceResponse>('/predictions/model-performance')
    return response.data
  },
}
