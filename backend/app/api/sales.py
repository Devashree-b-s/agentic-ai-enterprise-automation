"""Sales API router exposing endpoints for Customers, Orders, and Revenue Reports."""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.deps import DbSession, require_roles
from app.models.sales import OrderStatus
from app.models.user import User, UserRole
from app.schemas.sales import (
    CustomerCreate,
    CustomerResponse,
    CustomerUpdate,
    MonthlyRevenueReport,
    OrderCreate,
    OrderDetailResponse,
    OrderStatusUpdate,
    SalesSummaryReport,
)
from app.services.sales_service import sales_service

router = APIRouter(tags=["Sales Management"])

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
# Customer Endpoints
# ============================================================================


@router.post(
    "/customers",
    response_model=CustomerResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create customer (Admin & Manager)",
    description="Register a new customer with a unique customer code and email.",
)
def create_customer(
    customer_in: CustomerCreate,
    db: DbSession,
    _: RequireAdminOrManager,
) -> CustomerResponse:
    """Create a new customer record."""
    return sales_service.create_customer(db, customer_in)


@router.get(
    "/customers",
    response_model=list[CustomerResponse],
    status_code=status.HTTP_200_OK,
    summary="List customers",
    description="Retrieve a paginated list of customers with optional active filter.",
)
def list_customers(
    db: DbSession,
    _: RequireStaff,
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    is_active: Annotated[bool | None, Query()] = None,
) -> list[CustomerResponse]:
    """List customers with pagination and filtering."""
    return sales_service.list_customers(db, skip=skip, limit=limit, is_active=is_active)


@router.get(
    "/customers/{customer_id}",
    response_model=CustomerResponse,
    status_code=status.HTTP_200_OK,
    summary="Get customer by ID",
    description="Fetch full customer profile by database ID.",
)
def get_customer(
    customer_id: int,
    db: DbSession,
    _: RequireStaff,
) -> CustomerResponse:
    """Fetch customer details by primary key ID."""
    customer = sales_service.get_customer_by_id(db, customer_id)
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Customer with ID {customer_id} not found.",
        )
    return customer


@router.put(
    "/customers/{customer_id}",
    response_model=CustomerResponse,
    status_code=status.HTTP_200_OK,
    summary="Update customer (Admin & Manager)",
    description="Update customer contact details.",
)
def update_customer(
    customer_id: int,
    customer_in: CustomerUpdate,
    db: DbSession,
    _: RequireAdminOrManager,
) -> CustomerResponse:
    """Update existing customer details."""
    customer = sales_service.get_customer_by_id(db, customer_id)
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Customer with ID {customer_id} not found.",
        )
    return sales_service.update_customer(db, customer, customer_in)


@router.delete(
    "/customers/{customer_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete customer (Admin & Manager)",
    description="Delete a customer if no associated orders exist.",
)
def delete_customer(
    customer_id: int,
    db: DbSession,
    _: RequireAdminOrManager,
) -> None:
    """Delete customer record."""
    customer = sales_service.get_customer_by_id(db, customer_id)
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Customer with ID {customer_id} not found.",
        )
    sales_service.delete_customer(db, customer)


# ============================================================================
# Order Endpoints
# ============================================================================


@router.post(
    "/orders",
    response_model=OrderDetailResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create sales order",
    description="Place a new sales order with multiple line items. Computes totals automatically.",
)
def create_order(
    order_in: OrderCreate,
    db: DbSession,
    current_user: RequireStaff,
) -> OrderDetailResponse:
    """Create a new sales order with line items."""
    return sales_service.create_order(db, order_in, user_id=current_user.id)  # type: ignore


@router.get(
    "/orders",
    response_model=list[OrderDetailResponse],
    status_code=status.HTTP_200_OK,
    summary="List sales orders",
    description="Retrieve sales orders with status and date filtering and pagination.",
)
def list_orders(
    db: DbSession,
    _: RequireStaff,
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    customer_id: Annotated[int | None, Query()] = None,
    order_status: Annotated[OrderStatus | None, Query(alias="status")] = None,
    start_date: Annotated[datetime | None, Query()] = None,
    end_date: Annotated[datetime | None, Query()] = None,
) -> list[OrderDetailResponse]:
    """List orders with filtering."""
    return sales_service.list_orders(
        db,
        skip=skip,
        limit=limit,
        customer_id=customer_id,
        order_status=order_status,
        start_date=start_date,
        end_date=end_date,
    )  # type: ignore


@router.get(
    "/orders/{order_id}",
    response_model=OrderDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Get order details",
    description="Retrieve comprehensive order details including customer and line items.",
)
def get_order(
    order_id: int,
    db: DbSession,
    _: RequireStaff,
) -> OrderDetailResponse:
    """Fetch order by primary key ID."""
    order = sales_service.get_order_by_id(db, order_id)
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Order with ID {order_id} not found.",
        )
    return order  # type: ignore


@router.patch(
    "/orders/{order_id}/status",
    response_model=OrderDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Update order status (Admin & Manager)",
    description="Progress or cancel an order using the defined state machine transitions.",
)
def update_order_status(
    order_id: int,
    status_in: OrderStatusUpdate,
    db: DbSession,
    current_user: RequireAdminOrManager,
) -> OrderDetailResponse:
    """Update order status with state-machine transition validation."""
    order = sales_service.get_order_by_id(db, order_id)
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Order with ID {order_id} not found.",
        )
    return sales_service.update_order_status(
        db, order, status_in.status, user_id=current_user.id
    )  # type: ignore


@router.delete(
    "/orders/{order_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete order (Admin only)",
    description="Permanently delete a sales order record.",
)
def delete_order(
    order_id: int,
    db: DbSession,
    _: RequireAdmin,
) -> None:
    """Delete an order."""
    order = sales_service.get_order_by_id(db, order_id)
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Order with ID {order_id} not found.",
        )
    sales_service.delete_order(db, order)


# ============================================================================
# Analytics & Reports Endpoints
# ============================================================================


@router.get(
    "/reports/summary",
    response_model=SalesSummaryReport,
    status_code=status.HTTP_200_OK,
    summary="Get sales summary metrics (Admin & Manager)",
    description="Returns high-level sales metrics including recognized revenue and status counts.",
)
def get_sales_summary(
    db: DbSession,
    _: RequireAdminOrManager,
) -> SalesSummaryReport:
    """Retrieve executive sales summary report."""
    return sales_service.get_sales_summary(db)


@router.get(
    "/reports/monthly",
    response_model=MonthlyRevenueReport,
    status_code=status.HTTP_200_OK,
    summary="Get monthly revenue breakdown (Admin & Manager)",
    description="Returns aggregated recognized revenue grouped by calendar month.",
)
def get_monthly_revenue(
    db: DbSession,
    _: RequireAdminOrManager,
) -> MonthlyRevenueReport:
    """Retrieve monthly revenue aggregate report."""
    return sales_service.get_monthly_revenue_report(db)
