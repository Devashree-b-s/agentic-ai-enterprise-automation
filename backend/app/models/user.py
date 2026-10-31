"""User database model and RBAC roles."""

from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.employee import Employee


class UserRole(str, Enum):
    """Role-based access control roles."""

    ADMIN = "Admin"
    HR = "HR"
    MANAGER = "Manager"
    EMPLOYEE = "Employee"


class User(Base):
    """User account model for authentication and access control.

    Attributes:
        id: Primary key identifier.
        email: Work email used as the unique login credential.
        hashed_password: Securely hashed password using Argon2id.
        role: Assigned RBAC role determining API authorization boundaries.
        is_active: Flag indicating if the user account is active.
        employee_id: Foreign key connecting this user to their HR employee record.
        employee: 1-to-1 relationship to the Employee model.
        created_at: Timestamp when account was created.
        updated_at: Timestamp when account was last updated.
    """

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(
        String(255), unique=True, index=True, nullable=False
    )
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(
        String(50), default=UserRole.EMPLOYEE.value, nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    employee_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("employees.id", ondelete="SET NULL"),
        unique=True,
        nullable=True,
    )

    employee: Mapped["Employee | None"] = relationship(
        "Employee", back_populates="user"
    )

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

    def __repr__(self) -> str:
        return f"<User(id={self.id}, email='{self.email}', role='{self.role}')>"
