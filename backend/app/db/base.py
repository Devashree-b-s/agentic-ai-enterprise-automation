"""Declarative Base class for all SQLAlchemy ORM models."""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base class for all database models.

    All database tables will inherit from this Base class so SQLAlchemy
    can track table schemas, columns, and relationships in Base.metadata.
    """
