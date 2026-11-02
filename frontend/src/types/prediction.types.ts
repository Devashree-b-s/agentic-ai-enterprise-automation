export interface HistoricalPoint {
  month: string
  revenue: number
  units_sold: number
  order_count: number
}

export interface ForecastPoint {
  month: string
  predicted_revenue: number
  lower_bound: number
  upper_bound: number
  trend_direction: 'UPWARD' | 'DOWNWARD' | 'FLAT'
}

export interface ModelMetric {
  model_name: string
  description: string
  mae: number
  rmse: number
  mape_percent: number
  is_best_model: boolean
}

export interface SalesForecastResponse {
  historical_data: HistoricalPoint[]
  forecast_next_3_months: ForecastPoint[]
  selected_model: string
  growth_rate_percent: number
  model_evaluations: ModelMetric[]
  methodology_notes: string
  limitations_disclosure: string
}

export interface ProductDemandItem {
  sku: string
  product_name: string
  total_historical_units: number
  monthly_average_units: number
  recent_month_units: number
  projected_monthly_demand: number
  trend_direction: 'INCREASING' | 'DECREASING' | 'STABLE'
  trend_percentage: number
}

export interface ProductDemandResponse {
  total_products_analyzed: number
  top_demanded_products: ProductDemandItem[]
  increasing_demand_products: ProductDemandItem[]
  decreasing_demand_products: ProductDemandItem[]
}

export interface InventoryRiskItem {
  sku: string
  product_name: string
  quantity_on_hand: number
  quantity_on_order: number
  effective_stock: number
  safety_stock: number
  target_stock: number
  projected_monthly_demand: number
  daily_burn_rate: number
  days_of_stock_remaining: number
  shortage_risk_level: 'CRITICAL' | 'MODERATE' | 'HEALTHY'
  risk_reason: string
  suggested_replenishment_quantity: number
}

export interface InventoryRiskResponse {
  critical_risk_count: number
  moderate_risk_count: number
  healthy_count: number
  total_products_evaluated: number
  high_priority_replenishments: InventoryRiskItem[]
  all_evaluated_products: InventoryRiskItem[]
  action_notice: string
}

export interface ModelPerformanceResponse {
  train_period: string
  test_period: string
  models_evaluated: ModelMetric[]
  best_performing_model: string
  methodology: string
  evaluation_criteria: string
}
