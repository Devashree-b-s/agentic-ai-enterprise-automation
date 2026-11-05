"""add ingestion batch tracking fields

Revision ID: c42b67d91e20
Revises: a20d5b9e8f41
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c42b67d91e20"
down_revision: str | None = "a20d5b9e8f41"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("data_provenance_batches") as batch_op:
        batch_op.add_column(sa.Column("dataset_identifier", sa.String(100)))
        batch_op.add_column(sa.Column("source_declaration", sa.Text()))
        batch_op.add_column(sa.Column("target_database", sa.String(32)))
        batch_op.add_column(
            sa.Column("rows_read", sa.Integer(), nullable=False, server_default="0")
        )
        batch_op.add_column(
            sa.Column(
                "rows_accepted", sa.Integer(), nullable=False, server_default="0"
            )
        )
        batch_op.add_column(sa.Column("validation_summary_json", sa.Text()))

    op.execute(
        "UPDATE data_provenance_batches "
        "SET dataset_identifier = source_name, "
        "rows_read = COALESCE(source_row_count, 0), "
        "rows_accepted = imported_row_count "
        "WHERE dataset_identifier IS NULL"
    )
    op.create_index(
        "uq_operational_provenance_dataset_checksum_target",
        "data_provenance_batches",
        ["dataset_identifier", "source_file_sha256", "target_database"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(
        "uq_operational_provenance_dataset_checksum_target",
        table_name="data_provenance_batches",
    )
    with op.batch_alter_table("data_provenance_batches") as batch_op:
        batch_op.drop_column("validation_summary_json")
        batch_op.drop_column("rows_accepted")
        batch_op.drop_column("rows_read")
        batch_op.drop_column("target_database")
        batch_op.drop_column("source_declaration")
        batch_op.drop_column("dataset_identifier")
