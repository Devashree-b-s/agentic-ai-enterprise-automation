"""Validate and explicitly stamp a legacy operational database baseline."""

import argparse
import sys
from pathlib import Path

from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import Float, MetaData, Numeric, create_engine, inspect, text
from sqlalchemy.engine import URL, make_url

import app.models  # noqa: F401
from alembic import command
from app.core.config import BACKEND_DIR, settings
from app.db.base import Base

PROVENANCE_TABLE = "data_provenance_batches"
ALEMBIC_VERSION_TABLE = "alembic_version"
BASELINE_REVISION = "71a342e826c8"


def _include_object(object_, name, type_, reflected, compare_to):
    return not (type_ == "table" and name in (PROVENANCE_TABLE, ALEMBIC_VERSION_TABLE))


def _compare_type(
    context_,
    inspected_column,
    metadata_column,
    inspected_type,
    metadata_type,
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


def _readonly_database_url(database_url: str) -> URL:
    url = make_url(database_url)
    if not url.drivername.startswith("sqlite") or not url.database:
        raise ValueError(
            "The V1 baseline validator currently supports SQLite files only."
        )
    if url.database == ":memory:":
        raise ValueError("The V1 baseline validator requires a SQLite file.")
    path = Path(url.database)
    if not path.is_absolute():
        raise ValueError("The operational SQLite database path must be absolute.")
    return URL.create(
        "sqlite+pysqlite",
        database=f"file:{path.as_posix()}",
        query={"mode": "ro", "uri": "true"},
    )


def validate_existing_schema(database_url: str = settings.DATABASE_URL) -> list[str]:
    """Return all unexpected schema differences without changing the database."""
    engine = create_engine(_readonly_database_url(database_url))
    try:
        with engine.connect() as connection:
            if connection.dialect.name != "sqlite":
                raise ValueError(
                    "The V1 baseline validator currently supports SQLite only."
                )
            if not inspect(connection).has_table("employees"):
                return ["Operational baseline tables are missing; refusing to stamp."]
            context = MigrationContext.configure(
                connection,
                opts={
                    "compare_type": _compare_type,
                    "include_object": _include_object,
                    "render_as_batch": True,
                },
            )
            metadata = Base.metadata
            employee_columns = {
                column["name"]: column
                for column in inspect(connection).get_columns("employees")
            }
            if employee_columns["id"]["nullable"] != Base.metadata.tables[
                "employees"
            ].c.id.nullable:
                # SQLite may report an implicit INTEGER PRIMARY KEY as nullable.
                metadata = MetaData()
                for table in Base.metadata.tables.values():
                    table.to_metadata(metadata)
                metadata.tables["employees"].c.id.nullable = employee_columns["id"][
                    "nullable"
                ]
            diffs = compare_metadata(context, metadata)
            return [repr(diff) for diff in diffs]
    finally:
        engine.dispose()


def stamp_existing_database(database_url: str = settings.DATABASE_URL) -> None:
    """Validate the legacy schema and stamp only the initial baseline revision."""
    differences = validate_existing_schema(database_url)
    if differences:
        raise RuntimeError(
            "Operational schema does not match the reviewed V1 baseline; "
            "refusing to stamp:\n" + "\n".join(differences)
        )

    engine = create_engine(_readonly_database_url(database_url))
    try:
        with engine.connect() as connection:
            inspector = inspect(connection)
            if inspector.has_table(ALEMBIC_VERSION_TABLE):
                current = connection.execute(
                    text(f"SELECT version_num FROM {ALEMBIC_VERSION_TABLE}")
                ).scalar_one_or_none()
                if current == BASELINE_REVISION:
                    return
                raise RuntimeError(
                    "Alembic version history already exists; refusing to overwrite it."
                )
    finally:
        engine.dispose()

    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))
    command.stamp(config, BASELINE_REVISION)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate or explicitly stamp the existing V1 operational DB."
    )
    parser.add_argument(
        "action",
        choices=("validate", "stamp"),
        help="validate is read-only; stamp records the reviewed initial revision.",
    )
    action = parser.parse_args().action
    if action == "validate":
        differences = validate_existing_schema()
        if differences:
            print("Baseline validation failed:", file=sys.stderr)
            for difference in differences:
                print(f"- {difference}", file=sys.stderr)
            raise SystemExit(1)
        print("Operational schema matches the reviewed V1 baseline.")
        return

    stamp_existing_database()
    print("Validated operational schema and stamped the V1 baseline.")


if __name__ == "__main__":
    main()
