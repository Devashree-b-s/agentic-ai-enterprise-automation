"""REST API router for Predictive Analytics, Sales Forecasting, and Inventory Risk."""

import logging

from fastapi import APIRouter, status

from app.core.deps import CurrentUser, DbSession
from app.schemas.prediction import (
    InventoryRiskResponse,
    ModelPerformanceResponse,
    ProductDemandResponse,
    SalesForecastResponse,
)
from app.services.prediction_service import prediction_service

logger = logging.getLogger("app.api.predictions")

router = APIRouter(prefix="/predictions", tags=["Predictive Analytics & Forecasting"])


@router.get(
    "/sales-forecast",
    response_model=SalesForecastResponse,
    status_code=status.HTTP_200_OK,
    summary="Get 3-month sales revenue forecast",
    description="Retrieve out-of-sample sales revenue forecast with baseline comparisons and time-based evaluation metrics.",
)
def get_sales_forecast(
    db: DbSession,
    current_user: CurrentUser,
) -> SalesForecastResponse:
    """Generate 3-month sales revenue forecast."""
    return prediction_service.get_sales_forecast(db=db)


@router.get(
    "/product-demand",
    response_model=ProductDemandResponse,
    status_code=status.HTTP_200_OK,
    summary="Get product demand trends",
    description="Analyze product-level demand velocity, projected monthly demand, and trend direction.",
)
def get_product_demand(
    db: DbSession,
    current_user: CurrentUser,
) -> ProductDemandResponse:
    """Retrieve product demand velocity and trends."""
    return prediction_service.get_product_demand(db=db)


@router.get(
    "/inventory-risk",
    response_model=InventoryRiskResponse,
    status_code=status.HTTP_200_OK,
    summary="Get inventory shortage risk analysis",
    description="Evaluate warehouse shortage risks combining on-hand stock, open purchase orders, safety thresholds, and daily burn rates.",
)
def get_inventory_risk(
    db: DbSession,
    current_user: CurrentUser,
) -> InventoryRiskResponse:
    """Retrieve inventory shortage risk analysis and suggested replenishments."""
    return prediction_service.get_inventory_risk(db=db)


@router.get(
    "/model-performance",
    response_model=ModelPerformanceResponse,
    status_code=status.HTTP_200_OK,
    summary="Get forecasting model performance comparison",
    description="Inspect comparative time-based evaluation results across Naive, Moving Average, OLS Regression, and Holt's Linear Trend.",
)
def get_model_performance(
    db: DbSession,
    current_user: CurrentUser,
) -> ModelPerformanceResponse:
    """Return model performance metrics and methodology."""
    return prediction_service.get_model_performance(db=db)
