"""Secure management bootstrap utility to initialize the first Administrator account."""

import argparse
import getpass
import sys
from pathlib import Path

# Ensure backend root is on sys.path when executed as standalone script
backend_dir = Path(__file__).resolve().parent.parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import hash_password
from app.db.base import Base
from app.db.session import SessionLocal, engine
from app.models.user import User, UserRole


def bootstrap_first_admin(
    db: Session,
    email: str | None = None,
    password: str | None = None,
) -> User:
    """Safely initialize the initial system Administrator.

    SECURITY CONTROLS:
    1. Single-Bootstrap Lockout: Checks if ANY user with Admin privileges exists.
       If an Admin exists, immediately aborts to prevent backdoor accounts.
    2. Secure Input: Accepts password strictly via environment configuration,
       protected interactive prompt (getpass), or programmatic call.
       CLI arguments for passwords are intentionally forbidden to prevent
       process list and shell history leaks.
    3. Hashing: Uses Argon2id before database storage.
    4. Confidentiality: Passwords are never printed or logged.

    Raises:
        RuntimeError: If an Admin account already exists or email is taken.
        ValueError: If email or password is missing or shorter than 8 characters.
    """
    # 1. Enforce single-bootstrap guard: check for existing Admin
    stmt = select(User).where(User.role == UserRole.ADMIN.value)
    existing_admin = db.scalar(stmt)
    if existing_admin:
        raise RuntimeError(
            "Bootstrap aborted: An Administrator account already exists in this database. "
            "Additional accounts must be created by an authenticated Admin via the API."
        )

    # 2. Resolve credentials from parameters or environment
    target_email = email or settings.FIRST_SUPERUSER_EMAIL
    target_password = password or settings.FIRST_SUPERUSER_PASSWORD

    if not target_email or not target_password:
        raise ValueError(
            "Bootstrap credentials missing. Provide an email and password via "
            "secure interactive prompt or environment variables "
            "(FIRST_SUPERUSER_EMAIL, FIRST_SUPERUSER_PASSWORD)."
        )

    if len(target_password) < 8:
        raise ValueError("Admin password must be at least 8 characters long.")

    # 3. Check if target email is already taken by another role
    stmt_email = select(User).where(User.email == target_email)
    if db.scalar(stmt_email):
        raise RuntimeError(
            f"Bootstrap aborted: User with email '{target_email}' already exists."
        )

    # 4. Create and persist initial Admin
    hashed = hash_password(target_password)
    admin_user = User(
        email=target_email,
        hashed_password=hashed,
        role=UserRole.ADMIN.value,
        is_active=True,
    )
    db.add(admin_user)
    db.commit()
    db.refresh(admin_user)
    return admin_user


def build_parser() -> argparse.ArgumentParser:
    """Construct CLI argument parser without exposing password arguments."""
    parser = argparse.ArgumentParser(
        description=(
            "Securely bootstrap the initial Administrator for the Enterprise System. "
            "Passwords must be entered interactively via getpass or loaded from "
            "FIRST_SUPERUSER_PASSWORD."
        )
    )
    parser.add_argument(
        "--email",
        type=str,
        default=None,
        help="Administrator email address (falls back to FIRST_SUPERUSER_EMAIL or prompt)",
    )
    return parser


def main() -> None:
    """CLI entry point for: python -m app.core.bootstrap"""
    parser = build_parser()
    args = parser.parse_args()

    # 1. Resolve email
    admin_email = args.email or settings.FIRST_SUPERUSER_EMAIL
    if not admin_email:
        if sys.stdin.isatty():
            admin_email = input("Enter Administrator email address: ").strip()
        else:
            print(
                "ERROR: Administrator email must be provided via --email, "
                "FIRST_SUPERUSER_EMAIL, or interactive terminal.",
                file=sys.stderr,
            )
            sys.exit(1)

    # 2. Resolve password: read from environment or prompt securely with getpass
    admin_password = settings.FIRST_SUPERUSER_PASSWORD
    if not admin_password:
        if sys.stdin.isatty():
            admin_password = getpass.getpass(
                "Enter Administrator password (minimum 8 characters): "
            )
            confirm = getpass.getpass("Confirm Administrator password: ")
            if admin_password != confirm:
                print(
                    "ERROR: Passwords do not match. Bootstrap aborted.",
                    file=sys.stderr,
                )
                sys.exit(1)
        else:
            print(
                "ERROR: Administrator password must be provided via "
                "FIRST_SUPERUSER_PASSWORD environment variable or interactive terminal.",
                file=sys.stderr,
            )
            sys.exit(1)

    # 3. Ensure tables exist
    Base.metadata.create_all(bind=engine)

    # 4. Execute bootstrap
    db = SessionLocal()
    try:
        admin = bootstrap_first_admin(db, email=admin_email, password=admin_password)
        print(
            f"SUCCESS: Initial Administrator account created successfully: {admin.email}"
        )
    except (RuntimeError, ValueError) as err:
        print(f"ERROR: {err}", file=sys.stderr)
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
