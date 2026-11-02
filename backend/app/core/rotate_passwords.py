"""Secure management utility for rotating user passwords with Argon2id hashing.

SECURITY CONTROLS:
1. Strict confidentiality: Passwords and raw hashes are NEVER logged or printed.
2. Input security: Passwords must be supplied via interactive hidden prompt (getpass)
   or designated environment variable. CLI argument flags for plaintext passwords
   are intentionally disallowed to prevent shell history and process table exposure.
3. Argon2id hashing: All passwords are cryptographic hashed before persistence.
4. Validation: Enforces minimum 8 characters and maximum 128 characters.
"""

import argparse
import getpass
import os
import sys
from pathlib import Path

# Ensure backend root is on sys.path
backend_dir = Path(__file__).resolve().parent.parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.user import User


def rotate_user_password(db: Session, email: str, new_password: str) -> bool:
    """Safely update a user's password using Argon2id hashing.

    Args:
        db: Active database session.
        email: User email address.
        new_password: New plaintext password.

    Returns:
        True on success.

    Raises:
        ValueError: If password length is invalid or user not found.
    """
    if len(new_password) < 8:
        raise ValueError("Password must be at least 8 characters long.")
    if len(new_password) > 128:
        raise ValueError("Password cannot exceed 128 characters.")

    stmt = select(User).where(User.email == email)
    user = db.scalar(stmt)
    if not user:
        raise ValueError(f"User with email '{email}' not found.")

    user.hashed_password = hash_password(new_password)
    db.commit()
    db.refresh(user)
    return True


def build_parser() -> argparse.ArgumentParser:
    """Construct CLI argument parser for secure password rotation."""
    parser = argparse.ArgumentParser(
        description="Securely rotate an enterprise user password using Argon2id."
    )
    parser.add_argument(
        "--email",
        type=str,
        required=True,
        help="Email address of the target account",
    )
    parser.add_argument(
        "--env-var",
        type=str,
        default=None,
        help="Optional environment variable name containing the new password",
    )
    return parser


def main() -> None:
    """CLI entry point: python -m app.core.rotate_passwords --email user@enterprise.com"""
    parser = build_parser()
    args = parser.parse_args()

    email = args.email.strip()

    if args.env_var:
        new_password = os.getenv(args.env_var)
        if not new_password:
            print(
                f"ERROR: Environment variable '{args.env_var}' is empty or not set.",
                file=sys.stderr,
            )
            sys.exit(1)
    else:
        if not sys.stdin.isatty():
            print(
                "ERROR: Interactive prompt unavailable. Use --env-var in automated environments.",
                file=sys.stderr,
            )
            sys.exit(1)
        new_password = getpass.getpass(f"Enter new password for '{email}': ")
        confirm_password = getpass.getpass("Confirm new password: ")
        if new_password != confirm_password:
            print("ERROR: Passwords do not match.", file=sys.stderr)
            sys.exit(1)

    db: Session = SessionLocal()
    try:
        rotate_user_password(db, email, new_password)
        print(f"SUCCESS: Password for account '{email}' was rotated successfully using Argon2id.")
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
