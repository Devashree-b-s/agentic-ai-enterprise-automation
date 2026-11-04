"""add operational provenance registry

Revision ID: a20d5b9e8f41
Revises: 71a342e826c8
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "a20d5b9e8f41"
down_revision: str | None = "71a342e826c8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "data_provenance_batches",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("batch_id", sa.String(length=64), nullable=False),
        sa.Column("source_name", sa.String(length=100), nullable=False),
        sa.Column("source_file_name", sa.String(length=255), nullable=False),
        sa.Column("source_file_sha256", sa.String(length=64), nullable=False),
        sa.Column("source_row_count", sa.Integer(), nullable=True),
        sa.Column("imported_row_count", sa.Integer(), nullable=False),
        sa.Column("rejected_row_count", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("imported_at", sa.DateTime(), nullable=True),
        sa.Column("source_mappings_json", sa.Text(), nullable=True),
        sa.Column("transformation_metadata_json", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("batch_id"),
    )
    op.create_index(
        "ix_data_provenance_batches_source_name",
        "data_provenance_batches",
        ["source_name"],
        unique=False,
    )
    op.create_index(
        "ix_data_provenance_batches_status",
        "data_provenance_batches",
        ["status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_data_provenance_batches_status",
        table_name="data_provenance_batches",
    )
    op.drop_index(
        "ix_data_provenance_batches_source_name",
        table_name="data_provenance_batches",
    )
    op.drop_table("data_provenance_batches")
