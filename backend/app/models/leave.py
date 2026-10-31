"""Leave request database models for the HR domain."""

from datetime import date, datetime
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.employee import Employee


class LeaveType(str, Enum):
    """Standard categorized leave types recognized by enterprise HR."""

    ANNUAL = "ANNUAL"
    SICK = "SICK"
    UNPAID = "UNPAID"
    BEREAVEMENT = "BEREAVEMENT"


class LeaveStatus(str, Enum):
    """Lifecycle states for employee leave requests."""

    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class LeaveRequest(Base):
    """SQLAlchemy model representing an employee leave request."""

    __tablename__ = "leave_requests"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    leave_code: Mapped[str] = mapped_column(
        String(50), unique=True, index=True, nullable=False
    )
    employee_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("employees.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    employee_code: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    leave_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    start_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    end_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    days_count: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20),
        default=LeaveStatus.PENDING.value,
        nullable=False,
        index=True,
    )
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
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

    # Relationship to Employee
    employee: Mapped["Employee"] = relationship(
        "Employee",
        back_populates="leaves",
    )

    def __repr__(self) -> str:
        return (
            f"<LeaveRequest(id={self.id}, leave_code='{self.leave_code}', "
            f"emp='{self.employee_code}', type='{self.leave_type}', status='{self.status}')>"
        )
