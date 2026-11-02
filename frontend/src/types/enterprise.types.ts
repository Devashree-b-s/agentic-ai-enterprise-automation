export interface OverviewAnalytics {
  total_employees: number
  active_employees: number
  total_products: number
  total_inventory_units: number
  total_recognized_revenue: number
  total_orders_completed: number
  pending_leave_requests: number
}

// Alias for backwards compatibility if needed
export type ExecutiveOverview = OverviewAnalytics

export interface DepartmentPerformance {
  department: string
  employee_count: number
  active_employee_count: number
  leave_requests_count: number
  total_leave_days: number
  average_leave_days_per_employee: number
}

export interface ProductPerformance {
  sku: string
  name: string
  units_sold: number
  total_revenue: number
  quantity_on_hand: number
  safety_stock: number
  stock_status: string
  days_of_supply_estimate: number | null
}

export interface StockProductItem {
  sku: string
  name: string
  quantity_on_hand: number
  safety_stock: number
  target_stock: number
}

export interface InventoryAnalytics {
  total_products: number
  total_stock_on_hand: number
  total_stock_on_order: number
  low_stock_count: number
  out_of_stock_count: number
  highest_stock_products: StockProductItem[]
  replenishment_needed_count: number
  monetary_valuation_available: boolean
  valuation_note: string
}

export interface MonthlyLeaveTrendItem {
  year_month: string
  total_requests: number
  approved_requests: number
  total_days: number
}

export interface HRAnalytics {
  total_employees: number
  active_employees: number
  inactive_employees: number
  by_department: Record<string, number>
  by_role: Record<string, number>
  leave_requests_by_status: Record<string, number>
  pending_leave_requests: number
  leave_requests_by_department: Record<string, number>
  monthly_leave_trends?: MonthlyLeaveTrendItem[]
}

