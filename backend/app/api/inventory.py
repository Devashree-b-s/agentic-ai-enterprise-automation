"""Inventory API router exposing endpoints for Products, Stock Operations, Alerts, and Reports."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.deps import DbSession, require_roles
from app.models.user import User, UserRole
from app.schemas.inventory import (
    CSVImportSummary,
    InventorySummaryReport,
    LowStockAlertReport,
    ProductCreate,
    ProductResponse,
    ProductUpdate,
    StockAdjustRequest,
    StockInRequest,
    StockMovementResponse,
    StockOutRequest,
)
from app.services.inventory_service import inventory_service

router = APIRouter(tags=["Inventory Management"])

# Role requirement dependencies
RequireAdmin = Annotated[User, Depends(require_roles(UserRole.ADMIN))]
RequireAdminOrManager = Annotated[
    User, Depends(require_roles(UserRole.ADMIN, UserRole.MANAGER))
]
RequireStaff = Annotated[
    User,
    Depends(
        require_roles(
            UserRole.ADMIN,
            UserRole.MANAGER,
            UserRole.HR,
            UserRole.EMPLOYEE,
        )
    ),
]


# ============================================================================
# Product Catalog Endpoints
# ============================================================================


@router.post(
    "/products",
    response_model=ProductResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create product (Admin & Manager)",
    description="Add a new product to the catalog with unique SKU validation.",
)
def create_product(
    product_in: ProductCreate,
    db: DbSession,
    current_user: RequireAdminOrManager,
) -> ProductResponse:
    """Create new product record."""
    return inventory_service.create_product(db, product_in, user_id=current_user.id)


@router.get(
    "/products",
    response_model=list[ProductResponse],
    status_code=status.HTTP_200_OK,
    summary="List products",
    description="Retrieve catalog items with search, pagination, and low-stock filtering.",
)
def list_products(
    db: DbSession,
    _: RequireStaff,
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    search: Annotated[
        str | None, Query(description="Search by SKU or product name")
    ] = None,
    is_low_stock: Annotated[
        bool | None, Query(description="Filter low-stock items")
    ] = None,
    is_active: Annotated[
        bool | None, Query(description="Filter by active status")
    ] = None,
) -> list[ProductResponse]:
    """List products with optional search and filters."""
    return inventory_service.list_products(
        db,
        skip=skip,
        limit=limit,
        search=search,
        is_low_stock=is_low_stock,
        is_active=is_active,
    )


@router.get(
    "/products/{product_id}",
    response_model=ProductResponse,
    status_code=status.HTTP_200_OK,
    summary="Get product by ID",
    description="Retrieve complete product details by database primary key ID.",
)
def get_product(
    product_id: int,
    db: DbSession,
    _: RequireStaff,
) -> ProductResponse:
    """Fetch product by ID."""
    product = inventory_service.get_product_by_id(db, product_id)
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product with ID {product_id} not found.",
        )
    return product


@router.put(
    "/products/{product_id}",
    response_model=ProductResponse,
    status_code=status.HTTP_200_OK,
    summary="Update product metadata (Admin & Manager)",
    description="Update product name, description, thresholds, or status flag.",
)
def update_product(
    product_id: int,
    product_in: ProductUpdate,
    db: DbSession,
    _: RequireAdminOrManager,
) -> ProductResponse:
    """Update product metadata."""
    product = inventory_service.get_product_by_id(db, product_id)
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product with ID {product_id} not found.",
        )
    return inventory_service.update_product(db, product, product_in)


@router.delete(
    "/products/{product_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete product (Admin only)",
    description="Delete a product if no orders or stock movements reference it.",
)
def delete_product(
    product_id: int,
    db: DbSession,
    _: RequireAdmin,
) -> None:
    """Delete product if unreferenced."""
    product = inventory_service.get_product_by_id(db, product_id)
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product with ID {product_id} not found.",
        )
    inventory_service.delete_product(db, product)


# ============================================================================
# Stock Operation Endpoints
# ============================================================================


@router.post(
    "/stock/in",
    response_model=StockMovementResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Receive stock in (Admin & Manager)",
    description="Add inventory units from deliveries with movement audit logging.",
)
def stock_in(
    req: StockInRequest,
    db: DbSession,
    current_user: RequireAdminOrManager,
) -> StockMovementResponse:
    """Receive stock into inventory."""
    return inventory_service.stock_in(db, req, user_id=current_user.id)


@router.post(
    "/stock/out",
    response_model=StockMovementResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Deduct stock out (Admin & Manager)",
    description="Deduct inventory units with concurrency-safe stock checks.",
)
def stock_out(
    req: StockOutRequest,
    db: DbSession,
    current_user: RequireAdminOrManager,
) -> StockMovementResponse:
    """Deduct stock from inventory."""
    return inventory_service.stock_out(db, req, user_id=current_user.id)


@router.post(
    "/stock/adjust",
    response_model=StockMovementResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Adjust stock level (Admin & Manager)",
    description="Reconcile physical stock count after audit/stocktake.",
)
def stock_adjust(
    req: StockAdjustRequest,
    db: DbSession,
    current_user: RequireAdminOrManager,
) -> StockMovementResponse:
    """Reconcile physical stock."""
    return inventory_service.stock_adjust(db, req, user_id=current_user.id)


@router.get(
    "/products/{product_id}/movements",
    response_model=list[StockMovementResponse],
    status_code=status.HTTP_200_OK,
    summary="Get stock movement history",
    description="Retrieve immutable audit trail of inventory movements for a product.",
)
def get_product_movements(
    product_id: int,
    db: DbSession,
    _: RequireStaff,
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> list[StockMovementResponse]:
    """Fetch product stock movement audit trail."""
    return inventory_service.list_movements_for_product(
        db, product_id, skip=skip, limit=limit
    )


# ============================================================================
# Alerts & Summary Reports
# ============================================================================


@router.get(
    "/alerts/low-stock",
    response_model=LowStockAlertReport,
    status_code=status.HTTP_200_OK,
    summary="Get low-stock alerts",
    description="Returns items where quantity_on_hand <= safety_stock with replenishment suggestions.",
)
def get_low_stock_alerts(
    db: DbSession,
    _: RequireStaff,
) -> LowStockAlertReport:
    """Retrieve low-stock alert report."""
    return inventory_service.get_low_stock_alerts(db)


@router.get(
    "/reports/summary",
    response_model=InventorySummaryReport,
    status_code=status.HTTP_200_OK,
    summary="Get inventory summary metrics (Admin & Manager)",
    description="High-level inventory health summary including on-hand, on-order, and replenishment counts.",
)
def get_inventory_summary(
    db: DbSession,
    _: RequireAdminOrManager,
) -> InventorySummaryReport:
    """Retrieve inventory summary report."""
    return inventory_service.get_inventory_summary(db)


# ============================================================================
# CSV Import Endpoint
# ============================================================================


@router.post(
    "/import/csv",
    response_model=CSVImportSummary,
    status_code=status.HTTP_200_OK,
    summary="Import inventory.csv dataset (Admin only)",
    description="Repeatable batch import of the 30 products from inventory.csv.",
)
def import_inventory_csv(
    db: DbSession,
    current_user: RequireAdmin,
    file_path: Annotated[
        str, Query(description="Relative or absolute path to inventory CSV")
    ] = "data/inventory.csv",
) -> CSVImportSummary:
    """Trigger CSV import."""
    return inventory_service.import_csv(db, file_path, user_id=current_user.id)
