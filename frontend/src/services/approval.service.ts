import apiClient from './api'
import type {
  ApprovalDetail,
  ApprovalMetrics,
  ApprovalRequest,
} from '../types/approval.types'

export interface ApprovalCreatePayload {
  request_type: 'PURCHASE_REQUISITION' | 'LEAVE_REQUEST'
  title: string
  description?: string
  assigned_role?: string
  action_payload: Record<string, any>
}

export const approvalService = {
  async list(status?: string, type?: string, myRequests?: boolean): Promise<ApprovalRequest[]> {
    const params: Record<string, any> = {}
    if (status && status !== 'ALL') params.status = status
    if (type && type !== 'ALL') params.type = type
    if (myRequests) params.my_requests = true

    const response = await apiClient.get<ApprovalRequest[]>('/approvals', { params })
    return response.data
  },

  async getMetrics(): Promise<ApprovalMetrics> {
    const response = await apiClient.get<ApprovalMetrics>('/approvals/metrics')
    return response.data
  },

  async getDetail(id: number): Promise<ApprovalDetail> {
    const response = await apiClient.get<ApprovalDetail>(`/approvals/${id}`)
    return response.data
  },

  async create(payload: ApprovalCreatePayload): Promise<ApprovalRequest> {
    const response = await apiClient.post<ApprovalRequest>('/approvals', payload)
    return response.data
  },

  async approve(id: number, reason?: string): Promise<ApprovalRequest> {
    const response = await apiClient.post<ApprovalRequest>(`/approvals/${id}/approve`, { reason })
    return response.data
  },

  async reject(id: number, reason: string): Promise<ApprovalRequest> {
    const response = await apiClient.post<ApprovalRequest>(`/approvals/${id}/reject`, { reason })
    return response.data
  },

  async cancel(id: number, reason?: string): Promise<ApprovalRequest> {
    const response = await apiClient.post<ApprovalRequest>(`/approvals/${id}/cancel`, { reason })
    return response.data
  },

  async execute(id: number): Promise<any> {
    const response = await apiClient.post<any>(`/approvals/${id}/execute`)
    return response.data
  },
}

export default approvalService
