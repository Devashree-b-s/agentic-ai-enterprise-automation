"""Alembic environment for the operational enterprise database."""

from logging.config import fileConfig

from sqlalchemy import Float, Numeric, engine_from_config, pool

import app.models  # noqa: F401
from alembic import context
from app.core.config import settings
from app.db.base import Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _database_url() -> str:
    x_args = context.get_x_argument(as_dictionary=True)
    return (
        x_args.get("db_url")
        or config.get_main_option("sqlalchemy.url")
        or settings.DATABASE_URL
    )


def _include_object(object_, name, type_, reflected, compare_to):
    x_args = context.get_x_argument(as_dictionary=True)
    if (
        x_args.get("baseline") == "1"
        and type_ == "table"
        and name == "data_provenance_batches"
    ):
        return False
    return not (
        type_ == "column"
        and name == "id"
        and object_.table.name == "employees"
    )


def _compare_type(
    context_, inspected_column, metadata_column, inspected_type, metadata_type
):
    key = (metadata_column.table.name, metadata_column.name)
    if (
        key == ("orders", "total_amount")
        and isinstance(inspected_type, Float)
        and isinstance(metadata_type, Numeric)
    ):
        return False
    if (
        key == ("order_items", "subtotal")
        and isinstance(inspected_type, Numeric)
        and inspected_type.precision == 10
        and isinstance(metadata_type, Numeric)
        and metadata_type.precision == 12
    ):
        return False
    return None


def run_migrations_offline() -> None:
    """Run migrations without a DB-API connection."""
    context.configure(
        url=_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=_compare_type,
        include_object=_include_object,
        render_as_batch=True,
        version_table="alembic_version",
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations with a connection configured for the operational SQLite DB."""
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = _database_url()
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        future=True,
    )
    try:
        with connectable.connect() as connection:
            if connection.dialect.name == "sqlite":
                connection.exec_driver_sql("PRAGMA foreign_keys=ON")
                connection.exec_driver_sql("PRAGMA busy_timeout=5000")
                if connection.engine.url.database != ":memory:":
                    connection.exec_driver_sql("PRAGMA journal_mode=WAL")
                connection.commit()
            context.configure(
                connection=connection,
                target_metadata=target_metadata,
                compare_type=_compare_type,
                include_object=_include_object,
                render_as_batch=True,
                version_table="alembic_version",
            )
            with context.begin_transaction():
                context.run_migrations()
    finally:
        connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
