import apiClient from './api'
import type {
  Employee,
  EmployeeFilterParams,
  LeaveFilterParams,
  LeaveRecord,
  LeaveStatusUpdatePayload,
  LeaveSummaryReport,
} from '../types/hr.types'

export const hrService = {
  async listEmployees(params?: EmployeeFilterParams): Promise<Employee[]> {
    const response = await apiClient.get<Employee[]>('/hr/employees/', { params })
    return response.data
  },

  async getEmployee(id: number): Promise<Employee> {
    const response = await apiClient.get<Employee>(`/hr/employees/${id}`)
    return response.data
  },

  async listLeaves(params?: LeaveFilterParams): Promise<LeaveRecord[]> {
    const response = await apiClient.get<LeaveRecord[]>('/hr/leaves', { params })
    return response.data
  },

  async updateLeaveStatus(
    leaveId: number,
    payload: LeaveStatusUpdatePayload,
  ): Promise<LeaveRecord> {
    const response = await apiClient.patch<LeaveRecord>(
      `/hr/leaves/${leaveId}/status`,
      payload,
    )
    return response.data
  },

  async getLeavesReport(): Promise<LeaveSummaryReport> {
    const response = await apiClient.get<LeaveSummaryReport>('/hr/reports/leaves')
    return response.data
  },
}
