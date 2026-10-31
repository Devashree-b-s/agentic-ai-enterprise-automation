"""Authentication and user management business service."""

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import create_access_token, hash_password, verify_password
from app.models.employee import Employee
from app.models.user import User, UserRole
from app.schemas.user import UserCreateByAdmin, UserLogin, UserRegister


class AuthService:
    """Service handling user registration, admin creation, authentication, and token generation."""

    @staticmethod
    def get_by_id(db: Session, user_id: int) -> User | None:
        """Fetch a user by database primary key ID."""
        return db.get(User, user_id)

    @staticmethod
    def get_by_email(db: Session, email: str) -> User | None:
        """Fetch a user by unique email address."""
        stmt = select(User).where(User.email == email)
        return db.scalar(stmt)

    @staticmethod
    def _resolve_employee_link(db: Session, employee_code: str | None) -> int | None:
        """Helper to validate employee code and ensure it is not already linked to another user."""
        if not employee_code:
            return None

        stmt = select(Employee).where(Employee.employee_id == employee_code)
        employee = db.scalar(stmt)
        if not employee:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Employee code '{employee_code}' does not exist.",
            )

        stmt_user = select(User).where(User.employee_id == employee.id)
        if db.scalar(stmt_user):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Employee '{employee_code}' already has a registered user account.",
            )

        return employee.id

    @staticmethod
    def register_user(db: Session, user_in: UserRegister) -> User:
        """Register a new user account through public self-registration.

        SECURITY ENFORCEMENT:
        Public users are ALWAYS assigned the 'Employee' role.
        Clients cannot self-promote to Admin, HR, or Manager.
        """
        if AuthService.get_by_email(db, user_in.email):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"User with email '{user_in.email}' already exists.",
            )

        linked_employee_id = AuthService._resolve_employee_link(
            db, user_in.employee_code
        )
        hashed = hash_password(user_in.password)

        user = User(
            email=user_in.email,
            hashed_password=hashed,
            role=UserRole.EMPLOYEE.value,  # Strictly enforce Employee role
            is_active=True,
            employee_id=linked_employee_id,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    @staticmethod
    def create_user_by_admin(
        db: Session,
        user_in: UserCreateByAdmin,
    ) -> User:
        """Create a user account with explicit role assignment (Admin only)."""
        if AuthService.get_by_email(db, user_in.email):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"User with email '{user_in.email}' already exists.",
            )

        linked_employee_id = AuthService._resolve_employee_link(
            db, user_in.employee_code
        )
        hashed = hash_password(user_in.password)

        user = User(
            email=user_in.email,
            hashed_password=hashed,
            role=user_in.role.value,  # Admin assigns specific role
            is_active=True,
            employee_id=linked_employee_id,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    @staticmethod
    def authenticate_user(db: Session, login_data: UserLogin) -> User:
        """Verify user credentials and return authenticated user."""
        user = AuthService.get_by_email(db, login_data.email)
        if not user or not verify_password(login_data.password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User account is deactivated. Contact an administrator.",
            )

        return user

    @staticmethod
    def generate_token_for_user(user: User) -> str:
        """Generate a signed JWT token containing user identity and role claims."""
        claims = {
            "sub": str(user.id),
            "email": user.email,
            "role": user.role,
            "employee_id": user.employee_id,
        }
        return create_access_token(claims)


# Global singleton instance for clean imports
auth_service = AuthService()
