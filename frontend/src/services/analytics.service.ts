import apiClient from './api'
import type {
  DepartmentPerformance,
  ExecutiveOverview,
  HRAnalytics,
  ProductPerformance,
} from '../types/enterprise.types'

export const analyticsService = {
  async getOverview(): Promise<ExecutiveOverview> {
    const response = await apiClient.get<ExecutiveOverview>('/analytics/overview')
    return response.data
  },

  async getHRAnalytics(): Promise<HRAnalytics> {
    const response = await apiClient.get<HRAnalytics>('/analytics/hr')
    return response.data
  },

  async getDepartmentPerformance(): Promise<DepartmentPerformance[]> {
    const response = await apiClient.get<DepartmentPerformance[]>(
      '/analytics/department-performance',
    )
    return response.data
  },

  async getProductPerformance(limit: number = 30): Promise<ProductPerformance[]> {
    const response = await apiClient.get<ProductPerformance[]>(
      '/analytics/product-performance',
      { params: { limit } },
    )
    return response.data
  },
}
