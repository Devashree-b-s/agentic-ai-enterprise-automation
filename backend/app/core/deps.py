"""Reusable authentication and RBAC dependency injectors for FastAPI."""

from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.db.session import get_db
from app.models.user import User, UserRole

# HTTP Bearer scheme (extracts token from `Authorization: Bearer <token>`)
bearer_scheme = HTTPBearer(auto_error=False)

# Standard type aliases for dependency injection
DbSession = Annotated[Session, Depends(get_db)]
BearerCredentials = Annotated[
    HTTPAuthorizationCredentials | None, Depends(bearer_scheme)
]


def get_current_user(
    db: DbSession,
    credentials: BearerCredentials,
) -> User:
    """Validate JWT access token and return the currently authenticated user.

    Raises:
        HTTPException 401: If token is missing, invalid, or expired.
        HTTPException 403: If user account is deactivated.
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication credentials were not provided.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials
    payload = decode_access_token(token)

    sub = payload.get("sub")
    if not sub:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token payload is missing subject identifier.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        user_id = int(sub)
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid user identifier format in token.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None

    user = db.get(User, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User associated with this token no longer exists.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account has been deactivated.",
        )

    return user


# Type annotation for injecting current user into route handlers
CurrentUser = Annotated[User, Depends(get_current_user)]


def require_roles(*allowed_roles: UserRole):
    """Enforce Role-Based Access Control (RBAC) on route handlers.

    Usage:
        @router.post("/", dependencies=[Depends(require_roles(UserRole.ADMIN, UserRole.HR))])
    """
    allowed_values = {role.value for role in allowed_roles}

    def role_verifier(current_user: CurrentUser) -> User:
        if current_user.role not in allowed_values:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"Access forbidden: requires one of the following roles: "
                    f"{sorted(allowed_values)}."
                ),
            )
        return current_user

    return role_verifier
