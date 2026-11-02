export interface Product {
  id: number
  sku: string
  name: string
  description: string | null
  quantity_on_hand: number
  quantity_on_order: number
  lead_time_days: number
  safety_stock: number
  target_stock: number
  is_active: boolean
  created_at: string
  updated_at: string
}

export type MovementType = 'IN' | 'OUT' | 'ADJUSTMENT' | 'SALE'

export interface StockMovement {
  id: number
  product_id: number
  movement_type: MovementType
  quantity: number
  previous_quantity: number
  new_quantity: number
  reason: string | null
  reference: string | null
  created_by_user_id: number | null
  created_at: string
}

export interface LowStockItem {
  product_id: number
  sku: string
  name: string
  quantity_on_hand: number
  quantity_on_order: number
  safety_stock: number
  target_stock: number
  lead_time_days: number
  replenishment_quantity: number
  status: 'OUT_OF_STOCK' | 'LOW_STOCK' | string
}

// Alias for backwards compatibility
export type LowStockAlertItem = LowStockItem

export interface LowStockAlertReport {
  total_low_stock: number
  items: LowStockItem[]
}

export interface ReplenishmentItem {
  sku: string
  name: string
  quantity_on_hand: number
  quantity_on_order: number
  safety_stock: number
  target_stock: number
  units_sold: number
  suggested_replenishment: number
  urgency: 'CRITICAL' | 'WARNING' | 'NORMAL' | string
}

export interface InventorySummaryReport {
  total_products: number
  total_units_on_hand: number
  total_units_on_order: number
  low_stock_products_count: number
  out_of_stock_products_count: number
  products_requiring_replenishment_count: number
  monetary_valuation_available: boolean
  notes: string
}

export interface StockInPayload {
  product_id: number
  quantity: number
  reason?: string
  reference?: string
}

export interface StockOutPayload {
  product_id: number
  quantity: number
  reason?: string
  reference?: string
}

export interface StockAdjustPayload {
  product_id: number
  new_quantity: number
  reason?: string
  reference?: string
}

export interface ProductFilterParams {
  skip?: number
  limit?: number
  search?: string
  is_low_stock?: boolean
  is_active?: boolean
}
