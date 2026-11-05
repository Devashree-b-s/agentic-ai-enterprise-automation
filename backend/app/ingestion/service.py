"""Streaming CSV/Excel ingestion with explicit targets and transactional loading."""

import codecs
import csv
import hashlib
import hmac
import json
import re
import uuid
import zipfile
from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from pathlib import Path
from typing import Any, ClassVar

from openpyxl import load_workbook
from openpyxl.utils.exceptions import InvalidFileException
from sqlalchemy import (
    Boolean as SQLBoolean,
)
from sqlalchemy import (
    Column,
    Integer,
    MetaData,
    Table,
    UniqueConstraint,
    and_,
    select,
    true,
    update,
)
from sqlalchemy import (
    Date as SQLDate,
)
from sqlalchemy import (
    DateTime as SQLDateTime,
)
from sqlalchemy import (
    Float as SQLFloat,
)
from sqlalchemy import (
    Numeric as SQLNumeric,
)
from sqlalchemy import (
    String as SQLString,
)
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

from app.db.base import Base
from app.db.historical_base import HistoricalBase


class IngestionError(RuntimeError):
    """Raised when an import cannot be safely validated or completed."""


class BatchAlreadyInProgressError(IngestionError):
    """Raised when an identical import has a non-terminal batch already running."""


class DatabaseTarget(StrEnum):
    OPERATIONAL = "OPERATIONAL"
    HISTORICAL = "HISTORICAL"


TargetDatabase = DatabaseTarget


class BatchStatus(StrEnum):
    PENDING = "PENDING"
    VALIDATING = "VALIDATING"
    LOADING = "LOADING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class DataType(StrEnum):
    STRING = "string"
    INTEGER = "integer"
    DECIMAL = "decimal"
    BOOLEAN = "boolean"
    DATE = "date"
    DATETIME = "datetime"


ValueTransform = Callable[[Any], Any]


@dataclass(frozen=True)
class ColumnMapping:
    """Dataset-specific mapping and validation policy supplied to the engine."""

    source_column: str
    target_column: str
    data_type: DataType = DataType.STRING
    nullable: bool = True
    sensitive: bool = False
    report_original_value: bool = False
    transform: ValueTransform | None = field(default=None, repr=False, compare=False)


@dataclass(frozen=True)
class IngestionSpec:
    """Explicit source interpretation and destination table schema."""

    dataset_identifier: str
    source_declaration: str
    target_database: DatabaseTarget
    target_table: Table
    columns: tuple[ColumnMapping, ...]
    business_keys: tuple[str, ...] = ()
    sheet_name: str | None = None
    encoding: str = "utf-8-sig"
    delimiter: str | None = None
    excluded_source_columns: frozenset[str] = frozenset()


@dataclass(frozen=True)
class Rejection:
    row_number: int
    column_name: str
    reason: str
    original_value: str | None = None


@dataclass(frozen=True)
class ImportResult:
    batch_id: str
    dataset_identifier: str
    target_database: DatabaseTarget
    status: str
    source_file_name: str
    source_file_sha256: str
    rows_read: int
    rows_accepted: int
    rows_rejected: int
    rejection_issue_count: int
    rejections: tuple[Rejection, ...]
    rejections_truncated: bool
    idempotent_replay: bool = False


@dataclass(frozen=True)
class _Target:
    engine: Engine
    provenance_table: Table


@dataclass
class _ValidationReport:
    rows_read: int = 0
    staged_rows: int = 0
    rows_rejected: int = 0
    issue_count: int = 0
    rejections: list[Rejection] = field(default_factory=list)
    rejections_truncated: bool = False

    def reject(
        self,
        row_number: int,
        column_name: str,
        reason: str,
        original_value: str | None,
        limit: int,
    ) -> None:
        self.rows_rejected += 1
        self.add_issue(row_number, column_name, reason, original_value, limit)

    def add_issue(
        self,
        row_number: int,
        column_name: str,
        reason: str,
        original_value: str | None,
        limit: int,
    ) -> None:
        self.issue_count += 1
        if len(self.rejections) < limit:
            self.rejections.append(
                Rejection(
                    row_number=row_number,
                    column_name=column_name,
                    reason=reason,
                    original_value=original_value,
                )
            )
        else:
            self.rejections_truncated = True


class HmacPseudonymizer:
    """Keyed pseudonymization hook; the key is never persisted by ingestion."""

    def __init__(self, key: bytes) -> None:
        if len(key) < 32:
            raise ValueError("HMAC pseudonymization keys must be at least 32 bytes.")
        self._key = key

    def __call__(self, value: Any) -> str | None:
        if value is None:
            return None
        digest = hmac.new(
            self._key, str(value).encode("utf-8"), hashlib.sha256
        ).hexdigest()
        return digest


class IngestionService:
    """Ingest validated files only into explicitly supplied SQLite targets."""

    _DATASET_ID: ClassVar[re.Pattern[str]] = re.compile(
        r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,99}$"
    )
    _BATCH_STATUSES: ClassVar[frozenset[str]] = frozenset(
        status.value for status in BatchStatus
    )
    _SUPPORTED_EXTENSIONS: ClassVar[frozenset[str]] = frozenset(
        {".csv", ".xlsx"}
    )
    _HASH_CHUNK_BYTES: ClassVar[int] = 1024 * 1024
    _VALUE_PREVIEW_LIMIT: ClassVar[int] = 256
    _ALLOWED_TRANSITIONS: ClassVar[dict[str, frozenset[str]]] = {
        "PENDING": frozenset({"VALIDATING", "FAILED"}),
        "VALIDATING": frozenset({"LOADING", "FAILED"}),
        "LOADING": frozenset({"COMPLETED", "FAILED"}),
        "FAILED": frozenset({"PENDING"}),
        "COMPLETED": frozenset(),
    }

    def __init__(
        self,
        *,
        targets: Mapping[DatabaseTarget, tuple[Engine, Table]],
        allowed_source_roots: Sequence[Path],
        max_file_size_bytes: int = 2 * 1024 * 1024 * 1024,
        chunk_size: int = 1000,
        max_reported_rejections: int = 1000,
    ) -> None:
        if not targets:
            raise ValueError("At least one database target must be explicitly configured.")
        if not allowed_source_roots:
            raise ValueError("At least one allowed source root must be configured.")
        if max_file_size_bytes <= 0 or chunk_size <= 0 or max_reported_rejections < 0:
            raise ValueError("File, chunk, and report limits must be positive.")

        self._targets: dict[DatabaseTarget, _Target] = {}
        for target_name, (engine, provenance_table) in targets.items():
            if engine.dialect.name != "sqlite":
                raise ValueError("The ingestion foundation currently supports SQLite targets.")
            if target_name not in (DatabaseTarget.OPERATIONAL, DatabaseTarget.HISTORICAL):
                raise ValueError("An explicit operational or historical target is required.")
            expected_metadata = (
                Base.metadata
                if target_name == DatabaseTarget.OPERATIONAL
                else HistoricalBase.metadata
            )
            if provenance_table.metadata is not expected_metadata:
                raise ValueError(
                    f"The {target_name.value.lower()} target requires its own provenance model."
                )
            self._validate_provenance_table(provenance_table)
            self._targets[target_name] = _Target(engine, provenance_table)

        configured_engines = [target.engine for target in self._targets.values()]
        if len(configured_engines) != len(set(configured_engines)):
            raise ValueError("Operational and historical targets require separate engines.")
        database_paths = [
            Path(target.engine.url.database).resolve()
            for target in self._targets.values()
            if target.engine.url.database and target.engine.url.database != ":memory:"
        ]
        if len(database_paths) != len(set(database_paths)):
            raise ValueError("Operational and historical targets must use separate databases.")

        self._allowed_source_roots = tuple(
            Path(root).resolve(strict=True) for root in allowed_source_roots
        )
        self._max_file_size_bytes = max_file_size_bytes
        self._chunk_size = chunk_size
        self._max_reported_rejections = max_reported_rejections

    def ingest(self, source_path: Path, spec: IngestionSpec) -> ImportResult:
        """Validate, stage, transform, and load one file as a tracked batch."""
        target = self._get_target(spec.target_database)
        self._validate_spec(spec)
        path = self._validate_path(source_path)
        file_size = path.stat().st_size
        if file_size > self._max_file_size_bytes:
            raise IngestionError(
                f"Input file exceeds the configured {self._max_file_size_bytes}-byte limit."
            )
        self._validate_file_format(path, spec)
        source_sha256 = self._sha256(path)
        batch_id, existing_status = self._reserve_batch(
            target, path, source_sha256, spec
        )
        if existing_status == "COMPLETED":
            return self._completed_replay(
                target, batch_id, path, source_sha256, spec
            )
        if existing_status is not None:
            raise BatchAlreadyInProgressError(
                f"Batch {batch_id} for this dataset checksum is already {existing_status}."
            )

        report = _ValidationReport()
        accepted_rows = 0
        stage: Table | None = None
        try:
            self._set_batch_status(target, batch_id, "VALIDATING")
            with target.engine.connect() as connection:
                try:
                    with connection.begin():
                        stage = self._create_stage_table(connection, spec)
                        self._validate_and_stage(
                            connection, stage, path, spec, report
                        )

                    if self._sha256(path) != source_sha256:
                        raise IngestionError(
                            "The source file changed during validation."
                        )

                    self._set_batch_status(
                        target,
                        batch_id,
                        "LOADING",
                        report=report,
                    )
                    with connection.begin():
                        existing_rows = self._find_target_duplicates(
                            connection, stage, spec, report
                        )
                        self._load_stage(connection, stage, spec)
                        accepted_rows = report.staged_rows - existing_rows
                        self._complete_batch(
                            connection,
                            target.provenance_table,
                            batch_id,
                            spec,
                            path,
                            source_sha256,
                            report,
                            accepted_rows,
                        )
                        stage.drop(connection, checkfirst=True)
                    stage = None
                finally:
                    if stage is not None:
                        if connection.in_transaction():
                            connection.rollback()
                        with connection.begin():
                            stage.drop(connection, checkfirst=True)

            return self._result(
                batch_id,
                path,
                source_sha256,
                spec,
                "COMPLETED",
                report,
                accepted_rows,
            )
        except SQLAlchemyError as error:
            self._mark_failed(target, batch_id, report, type(error).__name__)
            raise IngestionError(
                "The database transaction failed; target changes were rolled back."
            ) from None
        except (
            IngestionError,
            UnicodeError,
            csv.Error,
            zipfile.BadZipFile,
            InvalidFileException,
            ValueError,
            TypeError,
        ) as error:
            self._mark_failed(target, batch_id, report, type(error).__name__)
            raise
        except Exception:  # noqa: BLE001 - mark unexpected parser failures without exposing input data
            self._mark_failed(target, batch_id, report, "InputProcessingError")
            raise IngestionError(
                "The source could not be processed; sensitive values were withheld."
            ) from None

    def _get_target(self, target_name: DatabaseTarget) -> _Target:
        target = self._targets.get(target_name)
        if target is None:
            raise IngestionError(
                f"The {target_name.value} database was not explicitly configured."
            )
        return target

    def _validate_spec(self, spec: IngestionSpec) -> None:
        if not self._DATASET_ID.fullmatch(spec.dataset_identifier):
            raise ValueError("Dataset identifier must be a short stable identifier.")
        if not spec.source_declaration.strip() or len(spec.source_declaration) > 1000:
            raise ValueError("A source declaration is required and limited to 1000 characters.")
        if spec.target_database not in self._targets:
            raise IngestionError("The requested database target is not configured.")
        if not spec.columns:
            raise ValueError("At least one source-to-target column mapping is required.")
        if any(not isinstance(mapping.data_type, DataType) for mapping in spec.columns):
            raise ValueError("Every mapping must declare a supported data type.")
        if spec.target_table.schema is not None:
            raise ValueError("Cross-schema destination tables are not supported.")
        if spec.target_table.name in {
            "data_provenance_batches",
            "alembic_version",
            "historical_alembic_version",
        }:
            raise ValueError("Ingestion cannot target a provenance or migration table.")
        source_columns = [column.source_column for column in spec.columns]
        target_columns = [column.target_column for column in spec.columns]
        if len(source_columns) != len(set(source_columns)):
            raise ValueError("Source column mappings must be unique.")
        if len(target_columns) != len(set(target_columns)):
            raise ValueError("Target column mappings must be unique.")
        if set(source_columns) & set(spec.excluded_source_columns):
            raise ValueError("Excluded source columns cannot also be mapped.")
        available_targets = set(spec.target_table.c.keys())
        if not set(target_columns) <= available_targets:
            raise ValueError("A mapped target column is absent from the configured table.")
        for mapping in spec.columns:
            target_column = spec.target_table.c[mapping.target_column]
            if mapping.nullable and not target_column.nullable:
                raise ValueError(
                    f"Mapping for {mapping.target_column} allows nulls but the target does not."
                )
            if not self._type_matches_target(mapping.data_type, target_column.type):
                raise ValueError(
                    f"Mapping type for {mapping.target_column} does not match the target schema."
                )
        if not set(spec.business_keys) <= set(target_columns):
            raise ValueError("Business keys must be included in the target column mappings.")
        if len(spec.business_keys) != len(set(spec.business_keys)):
            raise ValueError("Business key columns must be unique.")
        if spec.business_keys and not self._has_unique_target_key(
            spec.target_table, spec.business_keys
        ):
            raise ValueError(
                "Configured business keys must match a primary or unique target key."
            )

    @staticmethod
    def _validate_provenance_table(table: Table) -> None:
        required = {
            "batch_id",
            "dataset_identifier",
            "source_name",
            "source_file_name",
            "source_file_sha256",
            "source_declaration",
            "target_database",
            "source_row_count",
            "imported_row_count",
            "rejected_row_count",
            "rows_read",
            "rows_accepted",
            "status",
            "imported_at",
            "source_mappings_json",
            "validation_summary_json",
        }
        missing = required - set(table.c.keys())
        if missing:
            raise ValueError(
                "The provenance table is missing Phase 2 columns: "
                + ", ".join(sorted(missing))
            )

    def _validate_path(self, source_path: Path) -> Path:
        path = Path(source_path).resolve(strict=True)
        if not path.is_file():
            raise IngestionError("The input path must identify a regular file.")
        if not any(self._is_within(path, root) for root in self._allowed_source_roots):
            raise IngestionError("The input file is outside the configured source roots.")
        if path.suffix.lower() not in self._SUPPORTED_EXTENSIONS:
            raise IngestionError("Only CSV and XLSX input files are supported.")
        return path

    @staticmethod
    def _is_within(path: Path, root: Path) -> bool:
        try:
            path.relative_to(root)
            return True
        except ValueError:
            return False

    def _validate_file_format(self, path: Path, spec: IngestionSpec) -> None:
        with path.open("rb") as source:
            prefix = source.read(8192)
        if path.suffix.lower() == ".csv":
            if prefix.startswith(b"PK\x03\x04") or b"\x00" in prefix:
                raise IngestionError("CSV extension does not match the file contents.")
            try:
                codecs.getincrementaldecoder(spec.encoding)().decode(
                    prefix, final=False
                )
            except (LookupError, UnicodeDecodeError) as error:
                raise IngestionError(
                    "CSV content is not valid in the configured text encoding."
                ) from error
            return

        if not zipfile.is_zipfile(path):
            raise IngestionError("XLSX extension does not match the file contents.")
        with zipfile.ZipFile(path) as workbook:
            names = set(workbook.namelist())
            if "[Content_Types].xml" not in names or "xl/workbook.xml" not in names:
                raise IngestionError("The ZIP file is not a valid XLSX workbook.")
            if sum(member.file_size for member in workbook.infolist()) > self._max_file_size_bytes:
                raise IngestionError(
                    "Expanded XLSX content exceeds the configured file-size limit."
                )

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as source:
            while chunk := source.read(IngestionService._HASH_CHUNK_BYTES):
                digest.update(chunk)
        return digest.hexdigest()

    def _reserve_batch(
        self,
        target: _Target,
        path: Path,
        source_sha256: str,
        spec: IngestionSpec,
    ) -> tuple[str, str | None]:
        table = target.provenance_table
        with target.engine.begin() as connection:
            existing = connection.execute(
                select(table.c.batch_id, table.c.status).where(
                    table.c.dataset_identifier == spec.dataset_identifier,
                    table.c.source_file_sha256 == source_sha256,
                    table.c.target_database == spec.target_database.value,
                )
            ).first()
            if existing is not None:
                batch_id, status = existing
                if status == "FAILED":
                    connection.execute(
                        update(table)
                        .where(table.c.batch_id == batch_id, table.c.status == "FAILED")
                        .values(
                            status="PENDING",
                            source_file_name=path.name[:255],
                            source_declaration=spec.source_declaration,
                            source_row_count=0,
                            imported_row_count=0,
                            rejected_row_count=0,
                            rows_read=0,
                            rows_accepted=0,
                            imported_at=None,
                            source_mappings_json=self._mapping_json(spec),
                            validation_summary_json=None,
                        )
                    )
                    return batch_id, None
                return batch_id, status

            batch_id = uuid.uuid4().hex
            result = connection.execute(
                sqlite_insert(table)
                .values(
                    batch_id=batch_id,
                    dataset_identifier=spec.dataset_identifier,
                    source_name=spec.dataset_identifier,
                    source_file_name=path.name[:255],
                    source_file_sha256=source_sha256,
                    source_declaration=spec.source_declaration,
                    target_database=spec.target_database.value,
                    source_row_count=0,
                    imported_row_count=0,
                    rejected_row_count=0,
                    rows_read=0,
                    rows_accepted=0,
                    status="PENDING",
                    source_mappings_json=self._mapping_json(spec),
                    validation_summary_json=None,
                )
                .on_conflict_do_nothing(
                    index_elements=[
                        table.c.dataset_identifier,
                        table.c.source_file_sha256,
                        table.c.target_database,
                    ]
                )
            )
            if result.rowcount == 0:
                existing = connection.execute(
                    select(table.c.batch_id, table.c.status).where(
                        table.c.dataset_identifier == spec.dataset_identifier,
                        table.c.source_file_sha256 == source_sha256,
                        table.c.target_database == spec.target_database.value,
                    )
                ).one()
                return existing.batch_id, existing.status
            return batch_id, None

    def _set_batch_status(
        self,
        target: _Target,
        batch_id: str,
        status: str,
        *,
        report: _ValidationReport | None = None,
    ) -> None:
        if status not in self._BATCH_STATUSES:
            raise ValueError("Unsupported ingestion batch status.")
        from_statuses = [
            source
            for source, destinations in self._ALLOWED_TRANSITIONS.items()
            if status in destinations
        ]
        if not from_statuses:
            raise ValueError(f"No ingestion batch may transition to {status}.")
        values: dict[str, Any] = {"status": status}
        if report is not None:
            values.update(self._report_values(report))
        with target.engine.begin() as connection:
            result = connection.execute(
                update(target.provenance_table)
                .where(
                    target.provenance_table.c.batch_id == batch_id,
                    target.provenance_table.c.status.in_(from_statuses),
                )
                .values(**values)
            )
            if result.rowcount != 1:
                raise IngestionError("The provenance batch could not be updated.")

    def _create_stage_table(self, connection: Any, spec: IngestionSpec) -> Table:
        name = f"ingest_stage_{uuid.uuid4().hex}"
        metadata = MetaData()
        stage_columns = [
            Column(
                mapping.target_column,
                spec.target_table.c[mapping.target_column].type,
                nullable=mapping.target_column not in spec.business_keys,
            )
            for mapping in spec.columns
        ]
        stage_columns.append(Column("_ingest_row_number", Integer, nullable=False))
        constraints = (
            [UniqueConstraint(*spec.business_keys)]
            if spec.business_keys
            else []
        )
        stage = Table(
            name,
            metadata,
            *stage_columns,
            *constraints,
            prefixes=["TEMPORARY"],
        )
        stage.create(connection)
        return stage

    def _validate_and_stage(
        self,
        connection: Any,
        stage: Table,
        path: Path,
        spec: IngestionSpec,
        report: _ValidationReport,
    ) -> None:
        records = self._iter_records(path, spec)
        try:
            headers, iterator = next(records)
        except StopIteration as error:
            raise IngestionError("The input file is empty.") from error
        try:
            if len(headers) != len(set(headers)):
                raise IngestionError("The input header contains duplicate column names.")
            required = {mapping.source_column for mapping in spec.columns}
            missing = sorted(required - set(headers))
            if missing:
                raise IngestionError(
                    "Required source columns are missing: " + ", ".join(missing)
                )

            staged_buffer: list[dict[str, Any]] = []
            for row_number, raw_row, row_error in iterator:
                report.rows_read += 1
                if row_error is not None:
                    report.reject(
                        row_number,
                        "__row__",
                        row_error,
                        None,
                        self._max_reported_rejections,
                    )
                    continue
                if raw_row is None:
                    raise IngestionError("A parsed source row is missing.")
                values, row_issues = self._validate_row(raw_row, spec)
                if not row_issues:
                    values, transform_issues = self._transform_row(
                        values, raw_row, spec
                    )
                    row_issues.extend(transform_issues)

                if row_issues:
                    for column_name, reason, original_value in row_issues:
                        report.add_issue(
                            row_number,
                            column_name,
                            reason,
                            original_value,
                            self._max_reported_rejections,
                        )
                    report.rows_rejected += 1
                    continue

                values["_ingest_row_number"] = row_number
                staged_buffer.append(values)
                if len(staged_buffer) >= self._chunk_size:
                    self._flush_stage(connection, stage, staged_buffer, spec, report)
                    staged_buffer.clear()

            if staged_buffer:
                self._flush_stage(connection, stage, staged_buffer, spec, report)
        finally:
            records.close()

    def _iter_records(
        self, path: Path, spec: IngestionSpec
    ) -> Iterator[
        tuple[
            list[str],
            Iterator[tuple[int, dict[str, Any] | None, str | None]],
        ]
    ]:
        if path.suffix.lower() == ".csv":
            with path.open("r", encoding=spec.encoding, newline="") as source:
                reader = csv.reader(
                    source,
                    delimiter=spec.delimiter or ",",
                    strict=True,
                )
                headers = next(reader, None)
                if headers is None:
                    return

                def csv_rows() -> Iterator[tuple[int, dict[str, Any] | None, str | None]]:
                    for row_number, row in enumerate(reader, start=2):
                        if len(row) != len(headers):
                            yield row_number, None, "malformed record: field count differs from header"
                        else:
                            yield row_number, dict(zip(headers, row, strict=True)), None

                yield headers, csv_rows()
            return

        workbook = load_workbook(path, read_only=True, data_only=True)
        try:
            if spec.sheet_name is not None:
                if spec.sheet_name not in workbook.sheetnames:
                    raise IngestionError("The requested worksheet does not exist.")
                worksheet = workbook[spec.sheet_name]
            else:
                worksheet = workbook.active
            rows = worksheet.iter_rows(values_only=True)
            header_row = next(rows, None)
            if header_row is None:
                return
            headers = [
                str(value).strip() if value is not None else "" for value in header_row
            ]

            def excel_rows() -> Iterator[tuple[int, dict[str, Any] | None, str | None]]:
                for row_number, row in enumerate(rows, start=2):
                    if len(row) != len(headers):
                        yield row_number, None, "malformed record: field count differs from header"
                    else:
                        yield (
                            row_number,
                            dict(zip(headers, row, strict=True)),
                            None,
                        )

            yield headers, excel_rows()
        finally:
            workbook.close()

    def _flush_stage(
        self,
        connection: Any,
        stage: Table,
        rows: list[dict[str, Any]],
        spec: IngestionSpec,
        report: _ValidationReport,
    ) -> None:
        statement = sqlite_insert(stage).prefix_with("OR IGNORE")
        connection.execute(statement, rows)
        row_numbers = [row["_ingest_row_number"] for row in rows]
        present = set(
            connection.execute(
                select(stage.c._ingest_row_number).where(
                    stage.c._ingest_row_number.in_(row_numbers)
                )
            ).scalars()
        )
        for row in rows:
            row_number = row["_ingest_row_number"]
            if row_number not in present:
                report.reject(
                    row_number,
                    ",".join(spec.business_keys),
                    "duplicate business key in source file",
                    None,
                    self._max_reported_rejections,
                )
        report.staged_rows += len(present.intersection(row_numbers))

    def _validate_row(
        self, raw_row: dict[str, Any], spec: IngestionSpec
    ) -> tuple[dict[str, Any], list[tuple[str, str, str | None]]]:
        values: dict[str, Any] = {}
        issues: list[tuple[str, str, str | None]] = []
        for mapping in spec.columns:
            raw_value = raw_row[mapping.source_column]
            try:
                converted = self._convert(raw_value, mapping)
                if converted is None and (
                    not mapping.nullable
                    or mapping.target_column in spec.business_keys
                ):
                    raise ValueError("value is required")
                values[mapping.target_column] = converted
            except (ValueError, TypeError, InvalidOperation):
                reason = (
                    "missing required value"
                    if self._is_missing(raw_value)
                    and (
                        not mapping.nullable
                        or mapping.target_column in spec.business_keys
                    )
                    else f"invalid {mapping.data_type.value} value"
                )
                issues.append(
                    (
                        mapping.source_column,
                        reason,
                        self._safe_original_value(raw_value, mapping),
                    )
                )
        return values, issues

    def _transform_row(
        self,
        values: dict[str, Any],
        raw_row: dict[str, Any],
        spec: IngestionSpec,
    ) -> tuple[dict[str, Any], list[tuple[str, str, str | None]]]:
        transformed = dict(values)
        issues: list[tuple[str, str, str | None]] = []
        for mapping in spec.columns:
            transform = mapping.transform
            current_value = transformed[mapping.target_column]
            if transform is None or current_value is None:
                continue
            try:
                result = transform(current_value)
                converted = self._convert(result, mapping)
                if converted is None and (
                    not mapping.nullable
                    or mapping.target_column in spec.business_keys
                ):
                    raise ValueError("transform returned a missing required value")
                transformed[mapping.target_column] = converted
            except Exception:  # noqa: BLE001 - transformation exceptions may include source values
                issues.append(
                    (
                        mapping.source_column,
                        "configured transformation failed",
                        self._safe_original_value(
                            raw_row[mapping.source_column], mapping
                        ),
                    )
                )
        return transformed, issues

    def _find_target_duplicates(
        self,
        connection: Any,
        stage: Table,
        spec: IngestionSpec,
        report: _ValidationReport,
    ) -> int:
        if not spec.business_keys:
            return 0
        target = spec.target_table
        join_condition = and_(
            *[
                stage.c[key] == target.c[key]
                for key in spec.business_keys
            ]
        )
        statement = (
            select(stage.c._ingest_row_number)
            .select_from(stage.join(target, join_condition))
            .order_by(stage.c._ingest_row_number)
        )
        conflicts = 0
        for (row_number,) in connection.execute(statement):
            conflicts += 1
            report.reject(
                row_number,
                ",".join(spec.business_keys),
                "business key already exists in target",
                None,
                self._max_reported_rejections,
            )
        return conflicts

    @staticmethod
    def _load_stage(connection: Any, stage: Table, spec: IngestionSpec) -> None:
        target_columns = [mapping.target_column for mapping in spec.columns]
        statement = sqlite_insert(spec.target_table).from_select(
            target_columns,
            select(*[stage.c[name] for name in target_columns]).where(true()),
        )
        if spec.business_keys:
            statement = statement.on_conflict_do_nothing(
                index_elements=list(spec.business_keys)
            )
        connection.execute(statement)

    def _complete_batch(
        self,
        connection: Any,
        provenance_table: Table,
        batch_id: str,
        spec: IngestionSpec,
        path: Path,
        source_sha256: str,
        report: _ValidationReport,
        accepted_rows: int,
    ) -> None:
        values = self._report_values(report)
        values.update(
            {
                "status": "COMPLETED",
                "source_row_count": report.rows_read,
                "imported_row_count": accepted_rows,
                "rows_accepted": accepted_rows,
                "rejected_row_count": report.rows_rejected,
                "source_file_name": path.name[:255],
                "source_file_sha256": source_sha256,
                "source_declaration": spec.source_declaration,
                "dataset_identifier": spec.dataset_identifier,
                "target_database": spec.target_database.value,
                "imported_at": datetime.now(UTC).replace(tzinfo=None),
            }
        )
        result = connection.execute(
            update(provenance_table)
            .where(
                provenance_table.c.batch_id == batch_id,
                provenance_table.c.status == "LOADING",
            )
            .values(**values)
        )
        if result.rowcount != 1:
            raise IngestionError("The completed batch could not be recorded.")

    def _mark_failed(
        self,
        target: _Target,
        batch_id: str,
        report: _ValidationReport,
        error_type: str,
    ) -> None:
        values = self._report_values(report)
        values.update(
            {
                "status": "FAILED",
                "source_row_count": report.rows_read,
                "imported_row_count": 0,
                "rejected_row_count": report.rows_rejected,
                "rows_accepted": 0,
                "validation_summary_json": json.dumps(
                    {
                        "rows_read": report.rows_read,
                        "rows_staged": report.staged_rows,
                        "rows_rejected": report.rows_rejected,
                        "rejection_issue_count": report.issue_count,
                        "fatal_error_type": error_type,
                    },
                    sort_keys=True,
                ),
            }
        )
        with target.engine.begin() as connection:
            connection.execute(
                update(target.provenance_table)
                .where(
                    target.provenance_table.c.batch_id == batch_id,
                    target.provenance_table.c.status.in_(
                        ("PENDING", "VALIDATING", "LOADING")
                    ),
                )
                .values(**values)
            )

    @staticmethod
    def _report_values(report: _ValidationReport) -> dict[str, Any]:
        return {
            "source_row_count": report.rows_read,
            "rows_read": report.rows_read,
            "rejected_row_count": report.rows_rejected,
            "validation_summary_json": json.dumps(
                {
                    "rows_read": report.rows_read,
                    "rows_staged": report.staged_rows,
                    "rows_rejected": report.rows_rejected,
                    "rejection_issue_count": report.issue_count,
                    "rejections_truncated": report.rejections_truncated,
                },
                sort_keys=True,
            ),
        }

    @staticmethod
    def _mapping_json(spec: IngestionSpec) -> str:
        return json.dumps(
            {
                "columns": [
                    {
                        "source": mapping.source_column,
                        "target": mapping.target_column,
                        "type": mapping.data_type.value,
                        "sensitive": mapping.sensitive,
                    }
                    for mapping in spec.columns
                ],
                "business_keys": list(spec.business_keys),
                "excluded_source_columns": sorted(spec.excluded_source_columns),
                "sheet_name": spec.sheet_name,
            },
            sort_keys=True,
        )

    def _completed_replay(
        self,
        target: _Target,
        batch_id: str,
        path: Path,
        source_sha256: str,
        spec: IngestionSpec,
    ) -> ImportResult:
        with target.engine.connect() as connection:
            row = connection.execute(
                select(
                    target.provenance_table.c.rows_read,
                    target.provenance_table.c.rows_accepted,
                    target.provenance_table.c.rejected_row_count,
                    target.provenance_table.c.validation_summary_json,
                ).where(target.provenance_table.c.batch_id == batch_id)
            ).one()
        summary = json.loads(row.validation_summary_json or "{}")
        return ImportResult(
            batch_id=batch_id,
            dataset_identifier=spec.dataset_identifier,
            target_database=spec.target_database,
            status="COMPLETED",
            source_file_name=path.name,
            source_file_sha256=source_sha256,
            rows_read=row.rows_read,
            rows_accepted=row.rows_accepted,
            rows_rejected=row.rejected_row_count,
            rejection_issue_count=summary.get("rejection_issue_count", 0),
            rejections=(),
            rejections_truncated=summary.get("rejections_truncated", False),
            idempotent_replay=True,
        )

    @staticmethod
    def _result(
        batch_id: str,
        path: Path,
        source_sha256: str,
        spec: IngestionSpec,
        status: str,
        report: _ValidationReport,
        accepted_rows: int,
    ) -> ImportResult:
        return ImportResult(
            batch_id=batch_id,
            dataset_identifier=spec.dataset_identifier,
            target_database=spec.target_database,
            status=status,
            source_file_name=path.name,
            source_file_sha256=source_sha256,
            rows_read=report.rows_read,
            rows_accepted=accepted_rows,
            rows_rejected=report.rows_rejected,
            rejection_issue_count=report.issue_count,
            rejections=tuple(report.rejections),
            rejections_truncated=report.rejections_truncated,
        )

    @staticmethod
    def _has_unique_target_key(table: Table, keys: tuple[str, ...]) -> bool:
        key_set = set(keys)
        constraints = [
            {column.name for column in table.primary_key.columns},
            *[
                {column.name for column in constraint.columns}
                for constraint in table.constraints
                if isinstance(constraint, UniqueConstraint)
            ],
            *[
                {column.name for column in index.columns}
                for index in table.indexes
                if index.unique
            ],
        ]
        return key_set in constraints

    @staticmethod
    def _type_matches_target(data_type: DataType, target_type: Any) -> bool:
        expected_types = {
            DataType.STRING: (SQLString,),
            DataType.INTEGER: (Integer,),
            DataType.DECIMAL: (SQLNumeric, SQLFloat),
            DataType.BOOLEAN: (SQLBoolean,),
            DataType.DATE: (SQLDate,),
            DataType.DATETIME: (SQLDateTime,),
        }
        return isinstance(target_type, expected_types[data_type])

    @staticmethod
    def _convert(value: Any, mapping: ColumnMapping) -> Any:
        if value is None or (isinstance(value, str) and not value.strip()):
            if mapping.nullable:
                return None
            raise ValueError("value is required")
        if mapping.data_type == DataType.STRING:
            return str(value).strip()
        if mapping.data_type == DataType.INTEGER:
            if isinstance(value, bool):
                raise ValueError("boolean is not an integer")
            converted = Decimal(str(value).strip())
            if converted != converted.to_integral_value():
                raise ValueError("not an integer")
            return int(converted)
        if mapping.data_type == DataType.DECIMAL:
            converted = Decimal(str(value).strip())
            if not converted.is_finite():
                raise ValueError("decimal must be finite")
            return converted
        if mapping.data_type == DataType.BOOLEAN:
            if isinstance(value, bool):
                return value
            normalized = str(value).strip().lower()
            if normalized in {"true", "1", "yes"}:
                return True
            if normalized in {"false", "0", "no"}:
                return False
            raise ValueError("not a recognized boolean")
        if mapping.data_type == DataType.DATE:
            if isinstance(value, datetime):
                return value.date()
            if isinstance(value, date):
                return value
            return date.fromisoformat(str(value).strip())
        if mapping.data_type == DataType.DATETIME:
            if isinstance(value, datetime):
                return value
            if isinstance(value, date):
                return datetime.combine(value, datetime.min.time())
            normalized = str(value).strip()
            if normalized.endswith("Z"):
                normalized = normalized[:-1] + "+00:00"
            return datetime.fromisoformat(normalized)
        raise ValueError("unsupported data type")

    def _safe_original_value(
        self, value: Any, mapping: ColumnMapping
    ) -> str | None:
        if mapping.sensitive or not mapping.report_original_value or value is None:
            return None
        preview = str(value)
        return preview[: self._VALUE_PREVIEW_LIMIT]

    @staticmethod
    def _is_missing(value: Any) -> bool:
        return value is None or (isinstance(value, str) and not value.strip())
