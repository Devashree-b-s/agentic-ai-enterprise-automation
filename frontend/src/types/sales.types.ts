export interface MonthlySalesTrendItem {
  year_month: string
  recognized_revenue: number
  units_sold: number
  order_count: number
}

export interface ProductSalesItem {
  sku: string
  product_name: string
  units_sold: number
  total_revenue: number
}

// Alias for backwards compatibility
export type TopSellingProductItem = ProductSalesItem

export interface SalesAnalytics {
  total_recognized_revenue: number
  total_units_sold: number
  total_transactions: number
  revenue_by_status: Record<string, number>
  monthly_revenue: MonthlySalesTrendItem[]
  top_products_by_revenue: ProductSalesItem[]
  top_products_by_units: ProductSalesItem[]
  returned_orders_count: number
  returned_revenue_lost: number
  cancelled_orders_count: number
  cancelled_potential_revenue: number
}

export interface OrderItem {
  id: number
  order_id: number
  product_id: number
  product_name: string
  quantity: number
  unit_price: number
  subtotal: number
  created_at: string
}

export interface Customer {
  id: number
  customer_code: string
  name: string
  email: string
  phone: string | null
  address?: string | null
  is_active: boolean
  created_at: string
  updated_at: string
}

export type OrderStatus =
  | 'PENDING'
  | 'CONFIRMED'
  | 'PROCESSING'
  | 'SHIPPED'
  | 'COMPLETED'
  | 'CANCELLED'
  | 'RETURNED'

export interface OrderDetail {
  id: number
  order_number: string
  customer_id: number
  status: OrderStatus
  total_amount: number
  notes: string | null
  created_by_user_id: number | null
  order_date: string
  created_at: string
  updated_at: string
  customer: Customer
  items: OrderItem[]
}

export interface SalesSummaryReport {
  total_orders: number
  total_revenue: number
  average_order_value: number
  orders_by_status: Record<string, number>
}
