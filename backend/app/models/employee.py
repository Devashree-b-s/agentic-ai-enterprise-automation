"""Employee database model for the HR domain."""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Employee(Base):
    """SQLAlchemy model representing an enterprise employee in the HR domain.

    Attributes:
        id: Primary key surrogate identifier.
        employee_id: Business identifier (e.g. 'EMP-001'), unique across the enterprise.
        first_name: Given name of the employee.
        last_name: Family / surname of the employee.
        email: Work email address, unique across the enterprise.
        department: Assigned department (e.g., 'HR', 'Sales', 'Inventory').
        role: Job designation (e.g., 'Sales Manager', 'Inventory Clerk').
        salary: Annual compensation amount (used for deterministic financial analytics).
        is_active: Employment status flag (active vs terminated).
        created_at: Database timestamp when the record was inserted.
        updated_at: Database timestamp when the record was last modified.
    """

    __tablename__ = "employees"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    employee_id: Mapped[str] = mapped_column(
        String(50), unique=True, index=True, nullable=False
    )
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(
        String(255), unique=True, index=True, nullable=False
    )
    department: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    role: Mapped[str] = mapped_column(String(100), nullable=False)
    salary: Mapped[float] = mapped_column(Float, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    @property
    def full_name(self) -> str:
        """Convenience property returning the employee's full name."""
        return f"{self.first_name} {self.last_name}"

    def __repr__(self) -> str:
        return (
            f"<Employee(id={self.id}, employee_id='{self.employee_id}', "
            f"name='{self.full_name}', department='{self.department}')>"
        )
