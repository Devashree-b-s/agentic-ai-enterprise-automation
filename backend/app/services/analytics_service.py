"""Deterministic cross-department analytics service for HR, Sales, and Inventory."""

from datetime import date, datetime
from decimal import Decimal
from typing import ClassVar

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.models.employee import Employee
from app.models.historical_sale import HistoricalSale
from app.models.inventory import Product
from app.models.leave import LeaveRequest, LeaveStatus
from app.models.sales import Order, OrderItem, OrderStatus
from app.schemas.analytics import (
    CrossDepartmentReport,
    DepartmentPerformance,
    HRAnalytics,
    InventoryAnalytics,
    MonthlyLeaveTrendItem,
    MonthlySalesTrendItem,
    OverviewAnalytics,
    ProductPerformance,
    ProductSalesItem,
    ReplenishmentAnalyticsItem,
    SalesAnalytics,
    StockProductItem,
)


class AnalyticsService:
    """Service providing aggregated business intelligence and decision-support analytics."""

    # Revenue-contributing statuses
    RECOGNIZED_HISTORICAL_STATUSES: ClassVar[set[str]] = {"COMPLETED", "SHIPPED"}
    RECOGNIZED_OPERATIONAL_STATUSES: ClassVar[set[str]] = {
        OrderStatus.CONFIRMED.value,
        OrderStatus.SHIPPED.value,
        OrderStatus.DELIVERED.value,
    }

    @classmethod
    def get_overview(cls, db: Session) -> OverviewAnalytics:
        """High-level executive overview across all three operational domains."""
        # HR metrics
        total_emp = db.scalar(select(func.count(Employee.id))) or 0
        active_emp = (
            db.scalar(
                select(func.count(Employee.id)).where(Employee.is_active.is_(True))
            )
            or 0
        )
        pending_leaves = (
            db.scalar(
                select(func.count(LeaveRequest.id)).where(
                    LeaveRequest.status == LeaveStatus.PENDING.value
                )
            )
            or 0
        )

        # Inventory metrics
        total_prod = db.scalar(select(func.count(Product.id))) or 0
        total_units = db.scalar(select(func.sum(Product.quantity_on_hand))) or 0

        # Sales metrics (Historical recognized + Operational recognized)
        hist_rev = db.scalar(
            select(func.sum(HistoricalSale.subtotal)).where(
                HistoricalSale.order_status.in_(cls.RECOGNIZED_HISTORICAL_STATUSES)
            )
        ) or Decimal("0.00")
        hist_orders_count = (
            db.scalar(
                select(func.count(HistoricalSale.id)).where(
                    HistoricalSale.order_status.in_(cls.RECOGNIZED_HISTORICAL_STATUSES)
                )
            )
            or 0
        )

        op_rev = db.scalar(
            select(func.sum(Order.total_amount)).where(
                Order.status.in_(cls.RECOGNIZED_OPERATIONAL_STATUSES)
            )
        ) or Decimal("0.00")
        op_orders_count = (
            db.scalar(
                select(func.count(Order.id)).where(
                    Order.status.in_(cls.RECOGNIZED_OPERATIONAL_STATUSES)
                )
            )
            or 0
        )

        total_rev = Decimal(str(hist_rev)) + Decimal(str(op_rev))
        total_orders = hist_orders_count + op_orders_count

        return OverviewAnalytics(
            total_employees=total_emp,
            active_employees=active_emp,
            total_products=total_prod,
            total_inventory_units=int(total_units),
            total_recognized_revenue=total_rev,
            total_orders_completed=total_orders,
            pending_leave_requests=pending_leaves,
        )

    @staticmethod
    def get_hr_analytics(db: Session) -> HRAnalytics:
        """Workforce staffing, department allocations, and leave trends."""
        total_emp = db.scalar(select(func.count(Employee.id))) or 0
        active_emp = (
            db.scalar(
                select(func.count(Employee.id)).where(Employee.is_active.is_(True))
            )
            or 0
        )
        inactive_emp = total_emp - active_emp

        # Department distribution
        dept_rows = db.execute(
            select(Employee.department, func.count(Employee.id)).group_by(
                Employee.department
            )
        ).all()
        by_dept = {r[0]: r[1] for r in dept_rows}

        # Role distribution
        role_rows = db.execute(
            select(Employee.role, func.count(Employee.id)).group_by(Employee.role)
        ).all()
        by_role = {r[0]: r[1] for r in role_rows}

        # Leaves by status
        leave_status_rows = db.execute(
            select(LeaveRequest.status, func.count(LeaveRequest.id)).group_by(
                LeaveRequest.status
            )
        ).all()
        by_status = {r[0]: r[1] for r in leave_status_rows}
        pending_leaves = by_status.get("PENDING", 0)

        # Leaves by department
        leave_dept_rows = db.execute(
            select(Employee.department, func.count(LeaveRequest.id))
            .join(LeaveRequest, Employee.id == LeaveRequest.employee_id)
            .group_by(Employee.department)
        ).all()
        by_leave_dept = {r[0]: r[1] for r in leave_dept_rows}

        # Monthly leave trends
        monthly_rows = db.execute(
            select(
                func.strftime("%Y-%m", LeaveRequest.start_date).label("ym"),
                func.count(LeaveRequest.id).label("total_req"),
                func.sum(
                    case(
                        (LeaveRequest.status == LeaveStatus.APPROVED.value, 1), else_=0
                    )
                ).label("approved_req"),
                func.sum(LeaveRequest.days_count).label("days_sum"),
            )
            .group_by("ym")
            .order_by("ym")
        ).all()

        monthly_trends = [
            MonthlyLeaveTrendItem(
                year_month=r[0],
                total_requests=r[1],
                approved_requests=r[2] or 0,
                total_days=r[3] or 0,
            )
            for r in monthly_rows
            if r[0] is not None
        ]

        return HRAnalytics(
            total_employees=total_emp,
            active_employees=active_emp,
            inactive_employees=inactive_emp,
            by_department=by_dept,
            by_role=by_role,
            leave_requests_by_status=by_status,
            pending_leave_requests=pending_leaves,
            leave_requests_by_department=by_leave_dept,
            monthly_leave_trends=monthly_trends,
        )

    @classmethod
    def get_sales_analytics(
        cls,
        db: Session,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> SalesAnalytics:
        """Sales performance analytics covering recognized revenue, trends, top products, and returns."""
        # 1. Historical Sales aggregation
        hist_stmt = select(HistoricalSale)
        if start_date:
            hist_stmt = hist_stmt.where(HistoricalSale.order_date >= start_date)
        if end_date:
            hist_stmt = hist_stmt.where(HistoricalSale.order_date <= end_date)

        # Revenue by status in historical
        status_query = select(
            HistoricalSale.order_status,
            func.sum(HistoricalSale.subtotal),
            func.count(HistoricalSale.id),
            func.sum(HistoricalSale.quantity),
        )
        if start_date:
            status_query = status_query.where(HistoricalSale.order_date >= start_date)
        if end_date:
            status_query = status_query.where(HistoricalSale.order_date <= end_date)
        hist_status_rows = db.execute(
            status_query.group_by(HistoricalSale.order_status)
        ).all()

        revenue_by_status: dict[str, Decimal] = {}
        for row in hist_status_rows:
            st = row[0]
            val = Decimal(str(row[1] or "0.00"))
            revenue_by_status[st] = val

        recognized_rev = Decimal("0.00")
        total_units = 0
        total_tx = 0

        for st in cls.RECOGNIZED_HISTORICAL_STATUSES:
            for row in hist_status_rows:
                if row[0] == st:
                    recognized_rev += Decimal(str(row[1] or "0.00"))
                    total_tx += row[2] or 0
                    total_units += row[3] or 0

        # Also add operational recognized sales
        op_query = select(
            Order.status,
            func.sum(Order.total_amount),
            func.count(Order.id),
        )
        if start_date:
            op_query = op_query.where(func.date(Order.created_at) >= start_date)
        if end_date:
            op_query = op_query.where(func.date(Order.created_at) <= end_date)
        op_order_rows = db.execute(op_query.group_by(Order.status)).all()

        for op_row in op_order_rows:
            st = op_row[0]
            val = Decimal(str(op_row[1] or "0.00"))
            revenue_by_status[f"OPERATIONAL_{st}"] = val
            if st in cls.RECOGNIZED_OPERATIONAL_STATUSES:
                recognized_rev += val
                total_tx += op_row[2] or 0

        # Operational units sold
        op_units_query = (
            select(func.sum(OrderItem.quantity))
            .join(Order, OrderItem.order_id == Order.id)
            .where(Order.status.in_(cls.RECOGNIZED_OPERATIONAL_STATUSES))
        )
        if start_date:
            op_units_query = op_units_query.where(
                func.date(Order.created_at) >= start_date
            )
        if end_date:
            op_units_query = op_units_query.where(
                func.date(Order.created_at) <= end_date
            )
        op_units = db.scalar(op_units_query) or 0
        total_units += int(op_units)

        # Monthly recognized revenue trends
        monthly_hist_rows = db.execute(
            select(
                func.strftime("%Y-%m", HistoricalSale.order_date).label("ym"),
                func.sum(HistoricalSale.subtotal),
                func.sum(HistoricalSale.quantity),
                func.count(HistoricalSale.id),
            )
            .where(HistoricalSale.order_status.in_(cls.RECOGNIZED_HISTORICAL_STATUSES))
            .group_by("ym")
            .order_by("ym")
        ).all()

        monthly_sales = [
            MonthlySalesTrendItem(
                year_month=r[0],
                recognized_revenue=Decimal(str(r[1] or "0.00")),
                units_sold=r[2] or 0,
                order_count=r[3] or 0,
            )
            for r in monthly_hist_rows
            if r[0] is not None
        ]

        # Top products by revenue
        top_rev_rows = db.execute(
            select(
                HistoricalSale.sku,
                func.coalesce(Product.name, HistoricalSale.sku).label("prod_name"),
                func.sum(HistoricalSale.quantity).label("units"),
                func.sum(HistoricalSale.subtotal).label("rev"),
            )
            .outerjoin(Product, HistoricalSale.product_id == Product.id)
            .where(HistoricalSale.order_status.in_(cls.RECOGNIZED_HISTORICAL_STATUSES))
            .group_by(HistoricalSale.sku, "prod_name")
            .order_by(func.sum(HistoricalSale.subtotal).desc())
            .limit(10)
        ).all()

        top_by_revenue = [
            ProductSalesItem(
                sku=r[0],
                product_name=r[1],
                units_sold=r[2],
                total_revenue=Decimal(str(r[3])),
            )
            for r in top_rev_rows
        ]

        # Top products by units
        top_unit_rows = db.execute(
            select(
                HistoricalSale.sku,
                func.coalesce(Product.name, HistoricalSale.sku).label("prod_name"),
                func.sum(HistoricalSale.quantity).label("units"),
                func.sum(HistoricalSale.subtotal).label("rev"),
            )
            .outerjoin(Product, HistoricalSale.product_id == Product.id)
            .where(HistoricalSale.order_status.in_(cls.RECOGNIZED_HISTORICAL_STATUSES))
            .group_by(HistoricalSale.sku, "prod_name")
            .order_by(func.sum(HistoricalSale.quantity).desc())
            .limit(10)
        ).all()

        top_by_units = [
            ProductSalesItem(
                sku=r[0],
                product_name=r[1],
                units_sold=r[2],
                total_revenue=Decimal(str(r[3])),
            )
            for r in top_unit_rows
        ]

        # Returned & Cancelled analytics
        ret_count = (
            db.scalar(
                select(func.count(HistoricalSale.id)).where(
                    HistoricalSale.order_status == "RETURNED"
                )
            )
            or 0
        )
        ret_val = db.scalar(
            select(func.sum(HistoricalSale.subtotal)).where(
                HistoricalSale.order_status == "RETURNED"
            )
        ) or Decimal("0.00")

        canc_count = (
            db.scalar(
                select(func.count(HistoricalSale.id)).where(
                    HistoricalSale.order_status == "CANCELLED"
                )
            )
            or 0
        )
        canc_val = db.scalar(
            select(func.sum(HistoricalSale.subtotal)).where(
                HistoricalSale.order_status == "CANCELLED"
            )
        ) or Decimal("0.00")

        return SalesAnalytics(
            total_recognized_revenue=recognized_rev,
            total_units_sold=total_units,
            total_transactions=total_tx,
            revenue_by_status=revenue_by_status,
            monthly_revenue=monthly_sales,
            top_products_by_revenue=top_by_revenue,
            top_products_by_units=top_by_units,
            returned_orders_count=ret_count,
            returned_revenue_lost=Decimal(str(ret_val)),
            cancelled_orders_count=canc_count,
            cancelled_potential_revenue=Decimal(str(canc_val)),
        )

    @staticmethod
    def get_inventory_analytics(db: Session) -> InventoryAnalytics:
        """Warehouse stock volume, low stock alerts, and replenishment requirements."""
        total_prod = db.scalar(select(func.count(Product.id))) or 0
        total_on_hand = db.scalar(select(func.sum(Product.quantity_on_hand))) or 0
        total_on_order = db.scalar(select(func.sum(Product.quantity_on_order))) or 0

        low_stock = (
            db.scalar(
                select(func.count(Product.id)).where(
                    Product.quantity_on_hand <= Product.safety_stock
                )
            )
            or 0
        )
        out_of_stock = (
            db.scalar(
                select(func.count(Product.id)).where(Product.quantity_on_hand == 0)
            )
            or 0
        )

        replenish_count = (
            db.scalar(
                select(func.count(Product.id)).where(
                    (Product.quantity_on_hand + Product.quantity_on_order)
                    < Product.target_stock
                )
            )
            or 0
        )

        highest_stock_rows = db.execute(
            select(
                Product.sku,
                Product.name,
                Product.quantity_on_hand,
                Product.safety_stock,
                Product.target_stock,
            )
            .order_by(Product.quantity_on_hand.desc())
            .limit(10)
        ).all()

        highest_products = [
            StockProductItem(
                sku=r[0],
                name=r[1],
                quantity_on_hand=r[2],
                safety_stock=r[3],
                target_stock=r[4],
            )
            for r in highest_stock_rows
        ]

        return InventoryAnalytics(
            total_products=total_prod,
            total_stock_on_hand=int(total_on_hand),
            total_stock_on_order=int(total_on_order),
            low_stock_count=low_stock,
            out_of_stock_count=out_of_stock,
            highest_stock_products=highest_products,
            replenishment_needed_count=replenish_count,
            monetary_valuation_available=False,
            valuation_note=(
                "Monetary inventory valuation is unavailable because supplier unit purchase "
                "costs are not included in the catalog dataset."
            ),
        )

    @classmethod
    def get_product_performance(
        cls, db: Session, limit: int = 30
    ) -> list[ProductPerformance]:
        """Cross-department sales demand vs inventory availability per product."""
        # Query total units sold & revenue per SKU from historical recognized sales
        sales_subq = (
            select(
                HistoricalSale.sku,
                func.sum(HistoricalSale.quantity).label("total_units"),
                func.sum(HistoricalSale.subtotal).label("total_rev"),
                func.min(HistoricalSale.order_date).label("first_date"),
                func.max(HistoricalSale.order_date).label("last_date"),
            )
            .where(HistoricalSale.order_status.in_(cls.RECOGNIZED_HISTORICAL_STATUSES))
            .group_by(HistoricalSale.sku)
            .subquery()
        )

        query = (
            select(
                Product.sku,
                Product.name,
                func.coalesce(sales_subq.c.total_units, 0).label("units_sold"),
                func.coalesce(sales_subq.c.total_rev, Decimal("0.00")).label("revenue"),
                Product.quantity_on_hand,
                Product.safety_stock,
                sales_subq.c.first_date,
                sales_subq.c.last_date,
            )
            .outerjoin(sales_subq, Product.sku == sales_subq.c.sku)
            .order_by(sales_subq.c.total_units.desc().nullslast())
            .limit(limit)
        )

        rows = db.execute(query).all()
        results: list[ProductPerformance] = []

        for r in rows:
            sku, name, units, rev, on_hand, safety, first_d, last_d = r
            if on_hand == 0:
                stock_status = "OUT_OF_STOCK"
            elif on_hand <= safety:
                stock_status = "LOW_STOCK"
            else:
                stock_status = "HEALTHY"

            # Days of supply estimate (daily velocity over date range)
            days_supply: float | None = None
            if units > 0 and first_d and last_d:
                span_days = max(1, (last_d - first_d).days)
                daily_rate = units / span_days
                if daily_rate > 0:
                    days_supply = round(on_hand / daily_rate, 1)

            results.append(
                ProductPerformance(
                    sku=sku,
                    name=name,
                    units_sold=units,
                    total_revenue=Decimal(str(rev)),
                    quantity_on_hand=on_hand,
                    safety_stock=safety,
                    stock_status=stock_status,
                    days_of_supply_estimate=days_supply,
                )
            )

        return results

    @staticmethod
    def get_department_performance(db: Session) -> list[DepartmentPerformance]:
        """Correlate department headcount with employee leave days taken."""
        emp_subq = (
            select(
                Employee.department,
                func.count(Employee.id).label("headcount"),
                func.sum(case((Employee.is_active.is_(True), 1), else_=0)).label(
                    "active_count"
                ),
            )
            .group_by(Employee.department)
            .subquery()
        )

        leave_subq = (
            select(
                Employee.department,
                func.count(LeaveRequest.id).label("leave_requests"),
                func.sum(LeaveRequest.days_count).label("total_days"),
            )
            .join(LeaveRequest, Employee.id == LeaveRequest.employee_id)
            .where(LeaveRequest.status == LeaveStatus.APPROVED.value)
            .group_by(Employee.department)
            .subquery()
        )

        query = (
            select(
                emp_subq.c.department,
                emp_subq.c.headcount,
                emp_subq.c.active_count,
                func.coalesce(leave_subq.c.leave_requests, 0).label("requests"),
                func.coalesce(leave_subq.c.total_days, 0).label("days"),
            )
            .outerjoin(leave_subq, emp_subq.c.department == leave_subq.c.department)
            .order_by(emp_subq.c.headcount.desc())
        )

        rows = db.execute(query).all()
        results: list[DepartmentPerformance] = []

        for r in rows:
            dept, headcount, active_cnt, req_cnt, days = r
            avg_days = round(days / headcount, 1) if headcount > 0 else 0.0
            results.append(
                DepartmentPerformance(
                    department=dept,
                    employee_count=headcount,
                    active_employee_count=active_cnt or 0,
                    leave_requests_count=req_cnt,
                    total_leave_days=days,
                    average_leave_days_per_employee=avg_days,
                )
            )

        return results

    @classmethod
    def get_replenishment_suggestions(
        cls, db: Session
    ) -> list[ReplenishmentAnalyticsItem]:
        """Replenishment analytics combining historical sales volume and inventory target levels."""
        sales_subq = (
            select(
                HistoricalSale.sku,
                func.sum(HistoricalSale.quantity).label("units_sold"),
            )
            .where(HistoricalSale.order_status.in_(cls.RECOGNIZED_HISTORICAL_STATUSES))
            .group_by(HistoricalSale.sku)
            .subquery()
        )

        query = (
            select(
                Product.sku,
                Product.name,
                Product.quantity_on_hand,
                Product.quantity_on_order,
                Product.safety_stock,
                Product.target_stock,
                func.coalesce(sales_subq.c.units_sold, 0).label("units_sold"),
            )
            .outerjoin(sales_subq, Product.sku == sales_subq.c.sku)
            .order_by(Product.quantity_on_hand.asc())
        )

        rows = db.execute(query).all()
        results: list[ReplenishmentAnalyticsItem] = []

        for r in rows:
            sku, name, on_hand, on_order, safety, target, units = r
            suggested = max(0, target - (on_hand + on_order))
            if on_hand <= safety:
                urgency = "CRITICAL"
            elif (on_hand + on_order) < target:
                urgency = "WARNING"
            else:
                urgency = "NORMAL"

            results.append(
                ReplenishmentAnalyticsItem(
                    sku=sku,
                    name=name,
                    quantity_on_hand=on_hand,
                    quantity_on_order=on_order,
                    safety_stock=safety,
                    target_stock=target,
                    units_sold=units,
                    suggested_replenishment=suggested,
                    urgency=urgency,
                )
            )

        return results

    @classmethod
    def get_cross_department_report(cls, db: Session) -> CrossDepartmentReport:
        """Combined executive decision-support report."""
        overview = cls.get_overview(db)
        replenishment = cls.get_replenishment_suggestions(db)
        critical_items = [
            item for item in replenishment if item.urgency in ("CRITICAL", "WARNING")
        ][:10]

        dept_perf = cls.get_department_performance(db)
        dept_heads = {d.department: d.employee_count for d in dept_perf}
        dept_leaves = {d.department: d.total_leave_days for d in dept_perf}

        return CrossDepartmentReport(
            generated_at=datetime.now().isoformat(),
            overview=overview,
            top_critical_products=critical_items,
            department_headcounts=dept_heads,
            department_leaves=dept_leaves,
        )


analytics_service = AnalyticsService()
