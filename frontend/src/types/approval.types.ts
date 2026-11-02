export type ApprovalRequestType = 'PURCHASE_REQUISITION' | 'LEAVE_REQUEST'

export type ApprovalStatus =
  | 'PENDING'
  | 'APPROVED'
  | 'REJECTED'
  | 'EXECUTED'
  | 'FAILED'
  | 'CANCELLED'

export interface ApprovalAudit {
  id: number
  approval_request_id: number
  actor_id: number | null
  actor_email: string
  actor_role: string
  action: string
  from_status: string | null
  to_status: string
  comment: string | null
  created_at: string
}

export interface ApprovalRequest {
  id: number
  request_code: string
  request_type: ApprovalRequestType
  title: string
  description: string | null
  requester_id: number
  requester_email: string | null
  assigned_role: string
  reviewed_by_id: number | null
  reviewed_by_email: string | null
  status: ApprovalStatus
  action_payload: Record<string, any>
  execution_result: Record<string, any> | null
  rejection_reason: string | null
  review_notes: string | null
  created_at: string
  reviewed_at: string | null
  executed_at: string | null
}

export interface ApprovalDetail extends ApprovalRequest {
  audit_records: ApprovalAudit[]
}

export interface ApprovalMetrics {
  pending_count: number
  approved_count: number
  executed_count: number
  rejected_count: number
  cancelled_count: number
  total_count: number
}
