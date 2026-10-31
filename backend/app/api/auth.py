"""Authentication API endpoints for registration, login, admin user creation, and profiles."""

from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.core.deps import CurrentUser, DbSession, require_roles
from app.models.user import User, UserRole
from app.schemas.user import (
    TokenResponse,
    UserCreateByAdmin,
    UserLogin,
    UserRegister,
    UserResponse,
)
from app.services.auth_service import auth_service

router = APIRouter(prefix="/auth", tags=["Authentication"])

RequireAdmin = Annotated[User, Depends(require_roles(UserRole.ADMIN))]


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Public user registration (Employee role only)",
    description=(
        "Public self-registration endpoint. All registered users are strictly assigned "
        "the Employee role. Privileged role selection is disallowed."
    ),
)
def register(
    user_in: UserRegister,
    db: DbSession,
) -> UserResponse:
    """Register a new employee user account."""
    return auth_service.register_user(db, user_in)


@router.post(
    "/users",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create privileged user account (Admin only)",
    description=(
        "Administrator-only endpoint to provision user accounts with specific roles "
        "(Admin, HR, Manager, or Employee)."
    ),
)
def create_privileged_user(
    user_in: UserCreateByAdmin,
    db: DbSession,
    _: RequireAdmin,
) -> UserResponse:
    """Admin-exclusive user provisioning with role assignment."""
    return auth_service.create_user_by_admin(db, user_in)


@router.post(
    "/login",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Authenticate user and obtain JWT token",
    description="Validate credentials and issue a signed JWT access token.",
)
def login(
    login_data: UserLogin,
    db: DbSession,
) -> TokenResponse:
    """Authenticate with email and password to receive a bearer token."""
    user = auth_service.authenticate_user(db, login_data)
    access_token = auth_service.generate_token_for_user(user)
    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        user=UserResponse.model_validate(user),
    )


@router.get(
    "/me",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Get current user profile",
    description="Retrieve the profile of the currently authenticated user from their JWT token.",
)
def read_current_user(
    current_user: CurrentUser,
) -> UserResponse:
    """Return profile details of the authenticated caller."""
    return current_user
