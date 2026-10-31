"""Application configuration settings using Pydantic Settings."""

import warnings
from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Base directory paths
APP_DIR = Path(__file__).resolve().parent.parent
BACKEND_DIR = APP_DIR.parent
PROJECT_ROOT = BACKEND_DIR.parent
DATA_DIR = PROJECT_ROOT / "data"

# Ensure data directory exists
DATA_DIR.mkdir(parents=True, exist_ok=True)
DEFAULT_DB_FILE = DATA_DIR / "enterprise.db"

INSECURE_DEV_SECRET = "insecure-dev-secret-key-change-in-production-32bytes"


class Settings(BaseSettings):
    """Centralized application settings loaded from environment or defaults."""

    PROJECT_NAME: str = "Agentic AI Integrated Enterprise and Decision Support System"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    API_V1_STR: str = "/api/v1"

    # Database configuration: defaults to SQLite inside the /data directory
    DATABASE_URL: str = f"sqlite:///{DEFAULT_DB_FILE.as_posix()}"

    # Secret key for JWT tokens
    SECRET_KEY: str = INSECURE_DEV_SECRET
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # Optional initial administrator bootstrap credentials
    FIRST_SUPERUSER_EMAIL: str | None = None
    FIRST_SUPERUSER_PASSWORD: str | None = None

    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @model_validator(mode="after")
    def validate_production_security(self) -> "Settings":
        """Ensure cryptographically safe secrets in production environments."""
        if self.ENVIRONMENT.lower() == "production":
            if self.SECRET_KEY == INSECURE_DEV_SECRET:
                raise ValueError(
                    "CRITICAL SECURITY ERROR: You must provide a secure SECRET_KEY in production! "
                    "Cannot use the default development secret key."
                )
            if len(self.SECRET_KEY) < 32:
                raise ValueError(
                    f"CRITICAL SECURITY ERROR: SECRET_KEY must be at least 32 characters long. "
                    f"Provided length: {len(self.SECRET_KEY)}"
                )
        elif self.SECRET_KEY == INSECURE_DEV_SECRET:
            warnings.warn(
                "Running with default development SECRET_KEY. "
                "Ensure a custom SECRET_KEY is set in your .env before deploying to production.",
                stacklevel=2,
            )
        return self


# Global settings singleton
settings = Settings()
