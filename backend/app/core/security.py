"""Cryptographic security utilities for password hashing and JWT management."""

from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from fastapi import HTTPException, status

from app.core.config import settings

# Initialize Argon2id password hasher with secure defaults
ph = PasswordHasher()


def hash_password(password: str) -> str:
    """Hash a plaintext password using the Argon2id algorithm."""
    return ph.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against an Argon2id hash.

    Returns:
        True if the password matches, False otherwise.
    """
    try:
        return ph.verify(hashed_password, plain_password)
    except (VerifyMismatchError, InvalidHashError):
        return False


def create_access_token(
    data: dict[str, Any],
    expires_delta: timedelta | None = None,
) -> str:
    """Generate a signed JWT access token.

    Args:
        data: Claims dictionary to encode (e.g., {'sub': str(user.id), 'role': user.role}).
        expires_delta: Optional custom token expiration duration.

    Returns:
        Encoded and signed JWT string.
    """
    to_encode = data.copy()
    now = datetime.now(UTC)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({"exp": expire, "iat": now})
    return jwt.encode(
        to_encode,
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )


def decode_access_token(token: str) -> dict[str, Any]:
    """Decode and validate a JWT access token signature and expiration.

    Args:
        token: Encoded JWT string.

    Returns:
        Decoded claims payload dictionary.

    Raises:
        HTTPException 401 if expired or invalid.
    """
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
        )
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired. Please log in again.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None
