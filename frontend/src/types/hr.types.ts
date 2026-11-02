export interface Employee {
  id: number
  employee_id: string
  first_name: string
  last_name: string
  email: string
  department: string
  role: string
  salary: number | null
  is_active: boolean
  created_at: string
  updated_at: string
}

export type LeaveType = 'ANNUAL' | 'SICK' | 'UNPAID' | 'CASUAL' | 'MATERNITY' | 'PATERNITY' | string
export type LeaveStatus = 'PENDING' | 'APPROVED' | 'REJECTED'

export interface LeaveRecord {
  id: number
  leave_code: string
  employee_id: number
  employee_code: string
  leave_type: LeaveType
  start_date: string
  end_date: string
  days_count: number
  status: LeaveStatus
  reason: string | null
  created_at: string
  updated_at: string
}

export interface LeaveSummaryReport {
  total_requests: number
  by_status: Record<string, number>
  by_type: Record<string, number>
  by_department: Record<string, number>
  total_days_requested: number
  total_days_approved: number
}

export interface LeaveStatusUpdatePayload {
  status: 'APPROVED' | 'REJECTED'
  reason?: string
}

export interface EmployeeFilterParams {
  skip?: number
  limit?: number
  department?: string
  is_active?: boolean
}

export interface LeaveFilterParams {
  skip?: number
  limit?: number
  employee_id?: number
  department?: string
  status?: string
  leave_type?: string
  start_date?: string
  end_date?: string
}
