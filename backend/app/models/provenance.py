"""Operational database import provenance registry."""

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class DataProvenanceBatch(Base):
    """Tracks source files and transformations without storing imported rows."""

    __tablename__ = "data_provenance_batches"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    batch_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    source_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    source_file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    source_file_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    source_row_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    imported_row_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rejected_row_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    imported_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    source_mappings_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    transformation_metadata_json: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
