"""Pydantic schemas for Predictive Analytics and Business Forecasting."""


from pydantic import BaseModel, Field


class HistoricalPoint(BaseModel):
    """Historical time-series observation."""

    month: str = Field(description="Year-Month string (YYYY-MM)")
    revenue: float = Field(description="Actual recognized sales revenue")
    units_sold: int = Field(description="Actual units sold")
    order_count: int = Field(description="Total completed orders")


class ForecastPoint(BaseModel):
    """Out-of-sample forecast point."""

    month: str = Field(description="Forecast Year-Month string (YYYY-MM)")
    predicted_revenue: float = Field(description="Projected revenue")
    lower_bound: float = Field(description="Conservative lower bound (80% confidence)")
    upper_bound: float = Field(description="Optimistic upper bound (80% confidence)")
    trend_direction: str = Field(description="'UPWARD', 'DOWNWARD', or 'FLAT'")


class ModelMetric(BaseModel):
    """Time-based evaluation metrics for a specific forecasting model."""

    model_name: str
    description: str
    mae: float = Field(description="Mean Absolute Error on test period")
    rmse: float = Field(description="Root Mean Squared Error on test period")
    mape_percent: float = Field(description="Mean Absolute Percentage Error on test period")
    is_best_model: bool = Field(default=False)


class SalesForecastResponse(BaseModel):
    """Complete revenue forecast response with baseline comparisons and evaluation."""

    historical_data: list[HistoricalPoint]
    forecast_next_3_months: list[ForecastPoint]
    selected_model: str
    growth_rate_percent: float
    model_evaluations: list[ModelMetric]
    methodology_notes: str
    limitations_disclosure: str


class ProductDemandItem(BaseModel):
    """Demand prediction and trend direction for an individual catalog SKU."""

    sku: str
    product_name: str
    total_historical_units: int
    monthly_average_units: float
    recent_month_units: int
    projected_monthly_demand: float
    trend_direction: str = Field(description="'INCREASING', 'DECREASING', or 'STABLE'")
    trend_percentage: float = Field(description="Percentage change over recent historical periods")


class ProductDemandResponse(BaseModel):
    """Summary of product demand predictions across catalog."""

    total_products_analyzed: int
    top_demanded_products: list[ProductDemandItem]
    increasing_demand_products: list[ProductDemandItem]
    decreasing_demand_products: list[ProductDemandItem]


class InventoryRiskItem(BaseModel):
    """Inventory shortage risk assessment for an individual product."""

    sku: str
    product_name: str
    quantity_on_hand: int
    quantity_on_order: int
    effective_stock: int
    safety_stock: int
    target_stock: int
    projected_monthly_demand: float
    daily_burn_rate: float
    days_of_stock_remaining: float
    shortage_risk_level: str = Field(description="'CRITICAL', 'MODERATE', or 'HEALTHY'")
    risk_reason: str
    suggested_replenishment_quantity: int


class InventoryRiskResponse(BaseModel):
    """Summary of warehouse shortage risks and replenishment priorities."""

    critical_risk_count: int
    moderate_risk_count: int
    healthy_count: int
    total_products_evaluated: int
    high_priority_replenishments: list[InventoryRiskItem]
    all_evaluated_products: list[InventoryRiskItem]
    action_notice: str


class ModelPerformanceResponse(BaseModel):
    """Detailed model performance and time-based train/test split results."""

    train_period: str
    test_period: str
    models_evaluated: list[ModelMetric]
    best_performing_model: str
    methodology: str
    evaluation_criteria: str
