"""Sales business service layer implementing deterministic calculations and workflows."""

import uuid
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session, selectinload

from app.models.sales import Customer, Order, OrderItem, OrderStatus
from app.schemas.sales import (
    CustomerCreate,
    CustomerUpdate,
    MonthlyRevenueItem,
    MonthlyRevenueReport,
    OrderCreate,
    SalesSummaryReport,
)

# Standard monetary precision: 2 decimal places
TWOPLACES = Decimal("0.01")

# Valid state machine transitions for order statuses
# Strict business rule: Cancellation is prevented once an order has SHIPPED or DELIVERED.
VALID_STATUS_TRANSITIONS: dict[OrderStatus, set[OrderStatus]] = {
    OrderStatus.PENDING: {OrderStatus.CONFIRMED, OrderStatus.CANCELLED},
    OrderStatus.CONFIRMED: {OrderStatus.SHIPPED, OrderStatus.CANCELLED},
    OrderStatus.SHIPPED: {
        OrderStatus.DELIVERED
    },  # Terminal progression only; no cancellation
    OrderStatus.DELIVERED: set(),  # Terminal state
    OrderStatus.CANCELLED: set(),  # Terminal state
}

# Statuses that qualify for recognized revenue
REVENUE_RECOGNIZED_STATUSES = {
    OrderStatus.CONFIRMED.value,
    OrderStatus.SHIPPED.value,
    OrderStatus.DELIVERED.value,
}


class SalesService:
    """Service encapsulating customer CRUD, sales order workflows, and revenue analytics."""

    # ========================================================================
    # Customer Methods
    # ========================================================================

    @staticmethod
    def get_customer_by_id(db: Session, customer_id: int) -> Customer | None:
        """Fetch customer by database primary key ID."""
        return db.get(Customer, customer_id)

    @staticmethod
    def get_customer_by_code(db: Session, code: str) -> Customer | None:
        """Fetch customer by unique business customer code."""
        stmt = select(Customer).where(Customer.customer_code == code)
        return db.scalar(stmt)

    @staticmethod
    def get_customer_by_email(db: Session, email: str) -> Customer | None:
        """Fetch customer by unique email address."""
        stmt = select(Customer).where(Customer.email == email)
        return db.scalar(stmt)

    @staticmethod
    def list_customers(
        db: Session,
        skip: int = 0,
        limit: int = 100,
        is_active: bool | None = None,
    ) -> list[Customer]:
        """List customers with optional active status filter and pagination."""
        stmt = select(Customer)
        if is_active is not None:
            stmt = stmt.where(Customer.is_active == is_active)
        stmt = stmt.offset(skip).limit(limit).order_by(Customer.id.asc())
        return list(db.scalars(stmt).all())

    @staticmethod
    def create_customer(db: Session, customer_in: CustomerCreate) -> Customer:
        """Create a new customer after verifying uniqueness constraints."""
        if SalesService.get_customer_by_code(db, customer_in.customer_code):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Customer with code '{customer_in.customer_code}' already exists.",
            )

        if SalesService.get_customer_by_email(db, customer_in.email):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Customer with email '{customer_in.email}' already exists.",
            )

        customer = Customer(
            customer_code=customer_in.customer_code,
            name=customer_in.name,
            email=customer_in.email,
            phone=customer_in.phone,
            address=customer_in.address,
            is_active=customer_in.is_active,
        )
        db.add(customer)
        db.commit()
        db.refresh(customer)
        return customer

    @staticmethod
    def update_customer(
        db: Session, customer: Customer, customer_in: CustomerUpdate
    ) -> Customer:
        """Update an existing customer's contact details."""
        if customer_in.email is not None and customer_in.email != customer.email:
            existing = SalesService.get_customer_by_email(db, customer_in.email)
            if existing and existing.id != customer.id:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Customer with email '{customer_in.email}' already exists.",
                )

        update_data = customer_in.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(customer, field, value)

        db.commit()
        db.refresh(customer)
        return customer

    @staticmethod
    def delete_customer(db: Session, customer: Customer) -> None:
        """Delete customer if no dependent sales orders exist, otherwise prevent data loss."""
        # Check if customer has associated orders
        stmt = select(func.count(Order.id)).where(Order.customer_id == customer.id)
        order_count = db.scalar(stmt) or 0
        if order_count > 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Cannot delete customer '{customer.customer_code}' with {order_count} "
                    f"existing order(s). Deactivate the customer instead."
                ),
            )

        db.delete(customer)
        db.commit()

    # ========================================================================
    # Order Methods
    # ========================================================================

    @staticmethod
    def get_order_by_id(db: Session, order_id: int) -> Order | None:
        """Fetch an order with eager-loaded items and customer."""
        stmt = (
            select(Order)
            .where(Order.id == order_id)
            .options(selectinload(Order.items), selectinload(Order.customer))
        )
        return db.scalar(stmt)

    @staticmethod
    def get_order_by_number(db: Session, order_number: str) -> Order | None:
        """Fetch an order by unique invoice/order number."""
        stmt = (
            select(Order)
            .where(Order.order_number == order_number)
            .options(selectinload(Order.items), selectinload(Order.customer))
        )
        return db.scalar(stmt)

    @staticmethod
    def list_orders(
        db: Session,
        skip: int = 0,
        limit: int = 100,
        customer_id: int | None = None,
        order_status: OrderStatus | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> list[Order]:
        """List sales orders with filtering and pagination."""
        stmt = select(Order).options(
            selectinload(Order.items), selectinload(Order.customer)
        )

        if customer_id is not None:
            stmt = stmt.where(Order.customer_id == customer_id)
        if order_status is not None:
            stmt = stmt.where(Order.status == order_status.value)
        if start_date is not None:
            stmt = stmt.where(Order.order_date >= start_date)
        if end_date is not None:
            stmt = stmt.where(Order.order_date <= end_date)

        stmt = stmt.offset(skip).limit(limit).order_by(desc(Order.order_date))
        return list(db.scalars(stmt).all())

    @staticmethod
    def create_order(
        db: Session,
        order_in: OrderCreate,
        user_id: int | None = None,
    ) -> Order:
        """Create a sales order with line items and deterministic financial calculation."""
        # 1. Validate customer existence and active status
        customer = SalesService.get_customer_by_id(db, order_in.customer_id)
        if not customer:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Customer with ID {order_in.customer_id} does not exist.",
            )
        if not customer.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Customer '{customer.name}' is inactive and cannot place orders.",
            )

        # 2. Resolve or generate unique order number
        if order_in.order_number:
            if SalesService.get_order_by_number(db, order_in.order_number):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Order with number '{order_in.order_number}' already exists.",
                )
            assigned_order_number = order_in.order_number
        else:
            date_prefix = datetime.now().strftime("%Y%m%d")
            unique_suffix = uuid.uuid4().hex[:6].upper()
            assigned_order_number = f"ORD-{date_prefix}-{unique_suffix}"

        # 3. Calculate line item subtotals and overall order total deterministically
        calculated_items: list[OrderItem] = []
        total_order_amount = Decimal("0.00")

        for item_in in order_in.items:
            if item_in.quantity <= 0:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Item quantity must be strictly positive (>= 1).",
                )
            if item_in.unit_price < Decimal("0.00"):
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Item unit price cannot be negative.",
                )

            unit_price_dec = (
                item_in.unit_price
                if isinstance(item_in.unit_price, Decimal)
                else Decimal(str(item_in.unit_price))
            ).quantize(TWOPLACES, rounding=ROUND_HALF_UP)
            qty_dec = Decimal(str(item_in.quantity))
            subtotal = (qty_dec * unit_price_dec).quantize(
                TWOPLACES, rounding=ROUND_HALF_UP
            )
            total_order_amount += subtotal

            calculated_items.append(
                OrderItem(
                    product_id=item_in.product_id,
                    product_name=item_in.product_name,
                    quantity=item_in.quantity,
                    unit_price=unit_price_dec,
                    subtotal=subtotal,
                )
            )

        total_order_amount = total_order_amount.quantize(
            TWOPLACES, rounding=ROUND_HALF_UP
        )

        # 4. Create and persist Order with cascaded items
        order = Order(
            order_number=assigned_order_number,
            customer_id=customer.id,
            status=OrderStatus.PENDING.value,
            total_amount=total_order_amount,
            notes=order_in.notes,
            created_by_user_id=user_id,
            items=calculated_items,
        )

        db.add(order)
        db.commit()
        db.refresh(order)

        # Load relationships for response serialization
        return SalesService.get_order_by_id(db, order.id)  # type: ignore

    @staticmethod
    def update_order_status(
        db: Session,
        order: Order,
        new_status: OrderStatus,
    ) -> Order:
        """Enforce strict lifecycle transitions when modifying order status."""
        current_status = OrderStatus(order.status)

        if current_status == new_status:
            return order

        allowed_next_statuses = VALID_STATUS_TRANSITIONS.get(current_status, set())
        if new_status not in allowed_next_statuses:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Invalid status transition from '{current_status.value}' to '{new_status.value}'. "
                    f"Allowed transitions: {[s.value for s in allowed_next_statuses]}."
                ),
            )

        order.status = new_status.value
        db.commit()
        db.refresh(order)
        return SalesService.get_order_by_id(db, order.id)  # type: ignore

    @staticmethod
    def delete_order(db: Session, order: Order) -> None:
        """Delete an order (Admin only)."""
        db.delete(order)
        db.commit()

    # ========================================================================
    # Analytics & Reports
    # ========================================================================

    @staticmethod
    def get_sales_summary(db: Session) -> SalesSummaryReport:
        """Calculate high-level executive sales performance metrics."""
        # 1. Total order count
        total_orders = db.scalar(select(func.count(Order.id))) or 0

        # 2. Total recognized revenue (CONFIRMED, SHIPPED, DELIVERED)
        stmt_revenue = select(func.sum(Order.total_amount)).where(
            Order.status.in_(REVENUE_RECOGNIZED_STATUSES)
        )
        raw_revenue = db.scalar(stmt_revenue)
        total_revenue = (
            (
                raw_revenue
                if isinstance(raw_revenue, Decimal)
                else Decimal(str(raw_revenue))
            ).quantize(TWOPLACES, rounding=ROUND_HALF_UP)
            if raw_revenue is not None
            else Decimal("0.00")
        )

        # 3. Count recognized orders to compute average order value
        stmt_rec_count = select(func.count(Order.id)).where(
            Order.status.in_(REVENUE_RECOGNIZED_STATUSES)
        )
        recognized_count = db.scalar(stmt_rec_count) or 0

        average_order_value = (
            (total_revenue / Decimal(str(recognized_count))).quantize(
                TWOPLACES, rounding=ROUND_HALF_UP
            )
            if recognized_count > 0
            else Decimal("0.00")
        )

        # 4. Breakdown of orders by status
        status_counts: dict[str, int] = {s.value: 0 for s in OrderStatus}
        stmt_breakdown = select(Order.status, func.count(Order.id)).group_by(
            Order.status
        )
        for st, count in db.execute(stmt_breakdown).all():
            status_counts[st] = count

        return SalesSummaryReport(
            total_orders=total_orders,
            total_revenue=total_revenue,
            average_order_value=average_order_value,
            orders_by_status=status_counts,
        )

    @staticmethod
    def get_monthly_revenue_report(db: Session) -> MonthlyRevenueReport:
        """Aggregate recognized revenue by year and month using exact Decimal arithmetic."""
        # Fetch all revenue-recognized orders
        stmt = (
            select(Order)
            .where(Order.status.in_(REVENUE_RECOGNIZED_STATUSES))
            .order_by(Order.order_date.asc())
        )
        orders = list(db.scalars(stmt).all())

        monthly_buckets: dict[str, dict[str, Any]] = {}
        total_recognized_revenue = Decimal("0.00")

        for order in orders:
            order_dt = order.order_date
            period_key = order_dt.strftime("%Y-%m")
            if period_key not in monthly_buckets:
                monthly_buckets[period_key] = {
                    "year": order_dt.year,
                    "month": order_dt.month,
                    "period": period_key,
                    "revenue": Decimal("0.00"),
                    "order_count": 0,
                }

            order_amount = (
                order.total_amount
                if isinstance(order.total_amount, Decimal)
                else Decimal(str(order.total_amount))
            )
            monthly_buckets[period_key]["revenue"] += order_amount
            monthly_buckets[period_key]["order_count"] += 1
            total_recognized_revenue += order_amount

        items = [
            MonthlyRevenueItem(
                year=int(b["year"]),
                month=int(b["month"]),
                period=str(b["period"]),
                revenue=b["revenue"].quantize(TWOPLACES, rounding=ROUND_HALF_UP),
                order_count=int(b["order_count"]),
            )
            for b in sorted(monthly_buckets.values(), key=lambda x: str(x["period"]))
        ]

        return MonthlyRevenueReport(
            total_recognized_revenue=total_recognized_revenue.quantize(
                TWOPLACES, rounding=ROUND_HALF_UP
            ),
            months=items,
        )


# Global singleton instance for clean imports
sales_service = SalesService()
