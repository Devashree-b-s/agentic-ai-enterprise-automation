"""Independent declarative metadata for the historical database."""

from sqlalchemy.orm import DeclarativeBase


class HistoricalBase(DeclarativeBase):
    """Base for historical models; intentionally separate from operational metadata."""
