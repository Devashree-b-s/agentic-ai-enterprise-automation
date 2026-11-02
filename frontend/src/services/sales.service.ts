import apiClient from './api'
import type { Customer, OrderDetail, SalesAnalytics } from '../types/sales.types'

export const salesService = {
  async getSalesAnalytics(): Promise<SalesAnalytics> {
    const response = await apiClient.get<SalesAnalytics>('/analytics/sales')
    return response.data
  },

  async listOrders(params?: {
    status?: string
    skip?: number
    limit?: number
  }): Promise<OrderDetail[]> {
    const response = await apiClient.get<OrderDetail[]>('/sales/orders', { params })
    return response.data
  },

  async listCustomers(params?: {
    skip?: number
    limit?: number
  }): Promise<Customer[]> {
    const response = await apiClient.get<Customer[]>('/sales/customers', { params })
    return response.data
  },
}
