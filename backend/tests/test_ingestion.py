"""Synthetic-only tests for the reusable dataset ingestion foundation."""

import csv
import json
import zipfile
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path
from threading import Barrier

import pytest
from app.ingestion import (
    BatchAlreadyInProgressError,
    ColumnMapping,
    DatabaseTarget,
    DataType,
    HmacPseudonymizer,
    IngestionError,
    IngestionService,
    IngestionSpec,
)
from app.models.historical_provenance import HistoricalDataProvenanceBatch
from app.models.provenance import DataProvenanceBatch
from openpyxl import Workbook
from sqlalchemy import (
    CheckConstraint,
    Column,
    Integer,
    MetaData,
    String,
    Table,
    UniqueConstraint,
    create_engine,
    select,
)


@pytest.fixture
def ingestion_setup(tmp_path: Path):
    engine = create_engine(f"sqlite:///{(tmp_path / 'ingestion.db').as_posix()}")
    provenance_table = DataProvenanceBatch.__table__
    provenance_table.create(engine)
    target_table = Table(
        "synthetic_rows",
        MetaData(),
        Column("external_id", String(50), primary_key=True),
        Column("quantity", Integer, nullable=False),
        Column("note", String(100)),
        UniqueConstraint("external_id"),
        CheckConstraint("quantity >= 0", name="quantity_nonnegative"),
    )
    target_table.create(engine)
    service = IngestionService(
        targets={DatabaseTarget.OPERATIONAL: (engine, provenance_table)},
        allowed_source_roots=[tmp_path],
        chunk_size=2,
    )
    try:
        yield tmp_path, engine, target_table, provenance_table, service
    finally:
        engine.dispose()


def _spec(
    target_table: Table,
    *,
    target_database: DatabaseTarget = DatabaseTarget.OPERATIONAL,
    sheet_name: str | None = None,
    sensitive_id: bool = False,
    transform_id=None,
) -> IngestionSpec:
    return IngestionSpec(
        dataset_identifier="synthetic.test",
        source_declaration="synthetic fixture for automated tests",
        target_database=target_database,
        target_table=target_table,
        columns=(
            ColumnMapping(
                "id",
                "external_id",
                nullable=False,
                sensitive=sensitive_id,
                report_original_value=sensitive_id,
                transform=transform_id,
            ),
            ColumnMapping(
                "quantity",
                "quantity",
                DataType.INTEGER,
                nullable=False,
                report_original_value=True,
            ),
            ColumnMapping("note", "note"),
        ),
        business_keys=("external_id",),
        sheet_name=sheet_name,
    )


def _write_csv(path: Path, rows: list[list[str]], header=None) -> Path:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(header or ["id", "quantity", "note"])
        writer.writerows(rows)
    return path


def test_csv_ingestion_validates_converts_and_tracks_provenance(ingestion_setup):
    root, engine, target_table, provenance_table, service = ingestion_setup
    path = _write_csv(root / "synthetic.csv", [["A-1", "3", "sample"]])

    result = service.ingest(path, _spec(target_table))

    assert (result.status, result.rows_read, result.rows_accepted, result.rows_rejected) == (
        "COMPLETED",
        1,
        1,
        0,
    )
    with engine.connect() as connection:
        row = connection.execute(select(target_table)).one()
        batch = connection.execute(select(provenance_table)).one()
        stage_tables = connection.exec_driver_sql(
            "SELECT name FROM sqlite_temp_master "
            "WHERE type='table' AND name LIKE 'ingest_stage_%'"
        ).all()
    assert tuple(row) == ("A-1", 3, "sample")
    assert batch.dataset_identifier == "synthetic.test"
    assert batch.source_file_name == path.name
    assert batch.source_file_sha256 == result.source_file_sha256
    assert batch.source_declaration == "synthetic fixture for automated tests"
    assert batch.target_database == "OPERATIONAL"
    assert (batch.rows_read, batch.rows_accepted, batch.status) == (1, 1, "COMPLETED")
    assert stage_tables == []


def test_excel_sheet_is_selected_read_only_and_validated(ingestion_setup, monkeypatch):
    root, engine, target_table, _, service = ingestion_setup
    path = root / "synthetic.xlsx"
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Rows"
    sheet.append(["id", "quantity", "note"])
    sheet.append(["X-1", 8, "from workbook"])
    other = workbook.create_sheet("Ignore")
    other.append(["unrelated"])
    workbook.save(path)

    import app.ingestion.service as ingestion_module

    original_load_workbook = ingestion_module.load_workbook
    reader_options = []

    def read_only_workbook(*args, **kwargs):
        reader_options.append(kwargs.get("read_only"))
        return original_load_workbook(*args, **kwargs)

    monkeypatch.setattr(ingestion_module, "load_workbook", read_only_workbook)
    result = service.ingest(path, _spec(target_table, sheet_name="Rows"))

    assert result.rows_accepted == 1
    assert reader_options == [True]
    with engine.connect() as connection:
        assert connection.execute(select(target_table.c.quantity)).scalar_one() == 8


def test_missing_required_column_fails_batch_and_reports_failed_status(
    ingestion_setup,
):
    root, engine, target_table, provenance_table, service = ingestion_setup
    path = _write_csv(root / "missing.csv", [["A-1", "2"]], header=["id", "note"])

    with pytest.raises(IngestionError, match="Required source columns"):
        service.ingest(path, _spec(target_table))

    with engine.connect() as connection:
        batch = connection.execute(select(provenance_table)).one()
        target_rows = connection.execute(select(target_table)).all()
    assert batch.status == "FAILED"
    assert batch.rows_accepted == 0
    assert target_rows == []


def test_malformed_xlsx_fails_batch_without_leaking_parser_details(ingestion_setup):
    root, engine, target_table, provenance_table, service = ingestion_setup
    path = root / "malformed.xlsx"
    with zipfile.ZipFile(path, "w") as workbook:
        workbook.writestr("[Content_Types].xml", "<Types/>")
        workbook.writestr("xl/workbook.xml", "<workbook><broken></workbook>")

    with pytest.raises(IngestionError, match="sensitive values were withheld"):
        service.ingest(path, _spec(target_table))

    with engine.connect() as connection:
        batch = connection.execute(select(provenance_table)).one()
        assert connection.execute(select(target_table)).all() == []
    assert batch.status == "FAILED"
    assert "broken" not in batch.validation_summary_json


def test_mapping_schema_types_are_checked_before_batch_creation(ingestion_setup):
    root, engine, target_table, provenance_table, service = ingestion_setup
    path = _write_csv(root / "bad-mapping.csv", [["A-1", "1", "sample"]])
    spec = _spec(target_table)
    invalid_spec = replace(
        spec,
        columns=(
            spec.columns[0],
            replace(spec.columns[1], data_type=DataType.STRING),
            spec.columns[2],
        ),
    )

    with pytest.raises(ValueError, match="does not match the target schema"):
        service.ingest(path, invalid_spec)

    with engine.connect() as connection:
        assert connection.execute(select(provenance_table)).all() == []
        assert connection.execute(select(target_table)).all() == []


def test_invalid_types_are_rejected_with_safe_structured_report(ingestion_setup):
    root, _, target_table, _, service = ingestion_setup
    path = _write_csv(
        root / "invalid-type.csv",
        [["A-1", "bad-number", "safe preview"]],
    )

    result = service.ingest(path, _spec(target_table))

    assert result.rows_rejected == 1
    assert result.rows_accepted == 0
    assert result.rejection_issue_count == 1
    assert result.rejections[0].row_number == 2
    assert result.rejections[0].column_name == "quantity"
    assert result.rejections[0].original_value == "bad-number"


def test_duplicate_business_keys_are_reported_and_only_first_row_is_loaded(
    ingestion_setup,
):
    root, engine, target_table, _, service = ingestion_setup
    path = _write_csv(
        root / "duplicates.csv",
        [["A-1", "2", "first"], ["A-1", "7", "duplicate"]],
    )

    result = service.ingest(path, _spec(target_table))

    assert result.rows_read == 2
    assert result.rows_accepted == 1
    assert result.rows_rejected == 1
    assert "duplicate business key" in result.rejections[0].reason
    with engine.connect() as connection:
        row = connection.execute(select(target_table)).one()
    assert tuple(row) == ("A-1", 2, "first")


def test_existing_target_business_key_is_rejected_without_overwrite(ingestion_setup):
    root, engine, target_table, _, service = ingestion_setup
    with engine.begin() as connection:
        connection.execute(
            target_table.insert().values(
                external_id="A-1", quantity=2, note="existing"
            )
        )
    path = _write_csv(root / "target-duplicate.csv", [["A-1", "9", "new"]])

    result = service.ingest(path, _spec(target_table))

    assert result.rows_accepted == 0
    assert result.rows_rejected == 1
    assert "already exists in target" in result.rejections[0].reason
    with engine.connect() as connection:
        row = connection.execute(select(target_table)).one()
    assert tuple(row) == ("A-1", 2, "existing")


def test_sha256_is_recorded_and_identical_reimport_is_idempotent(ingestion_setup):
    root, engine, target_table, provenance_table, service = ingestion_setup
    path = _write_csv(root / "idempotent.csv", [["A-1", "5", "once"]])
    expected_hash = __import__("hashlib").sha256(path.read_bytes()).hexdigest()

    first = service.ingest(path, _spec(target_table))
    second = service.ingest(path, _spec(target_table))

    assert first.source_file_sha256 == expected_hash
    assert second.idempotent_replay
    assert second.batch_id == first.batch_id
    with engine.connect() as connection:
        assert len(connection.execute(select(target_table)).all()) == 1
        assert len(connection.execute(select(provenance_table)).all()) == 1


def test_transaction_rolls_back_target_rows_and_failed_batch_can_be_retried(
    ingestion_setup,
):
    root, engine, target_table, provenance_table, service = ingestion_setup
    path = _write_csv(root / "retry.csv", [["A-1", "4", "retry"]])
    with engine.begin() as connection:
        connection.exec_driver_sql(
            "CREATE TRIGGER reject_ingestion BEFORE INSERT ON synthetic_rows "
            "BEGIN SELECT RAISE(ABORT, 'test rollback'); END"
        )

    with pytest.raises(IngestionError, match="transaction failed"):
        service.ingest(path, _spec(target_table))

    with engine.connect() as connection:
        failed_batch = connection.execute(select(provenance_table)).one()
        assert failed_batch.status == "FAILED"
        assert connection.execute(select(target_table)).all() == []
    with engine.begin() as connection:
        connection.exec_driver_sql("DROP TRIGGER reject_ingestion")

    retried = service.ingest(path, _spec(target_table))

    assert retried.batch_id == failed_batch.batch_id
    assert retried.status == "COMPLETED"
    with engine.connect() as connection:
        assert len(connection.execute(select(target_table)).all()) == 1
        final_batch = connection.execute(select(provenance_table)).one()
        stage_tables = connection.exec_driver_sql(
            "SELECT name FROM sqlite_temp_master "
            "WHERE type='table' AND name LIKE 'ingest_stage_%'"
        ).all()
    assert final_batch.status == "COMPLETED"
    assert stage_tables == []


def test_mid_insert_failure_rolls_back_all_rows_and_records_failed_batch(
    ingestion_setup,
):
    root, engine, target_table, provenance_table, service = ingestion_setup
    path = _write_csv(
        root / "mid-insert-failure.csv",
        [["A-1", "1", "first"], ["A-2", "2", "failure"], ["A-3", "3", "last"]],
    )
    with engine.begin() as connection:
        connection.exec_driver_sql(
            "CREATE TRIGGER reject_second_row BEFORE INSERT ON synthetic_rows "
            "WHEN NEW.external_id = 'A-2' "
            "BEGIN SELECT RAISE(ABORT, 'synthetic mid-insert failure'); END"
        )

    with pytest.raises(IngestionError, match="transaction failed"):
        service.ingest(path, _spec(target_table))

    with engine.connect() as connection:
        assert connection.execute(select(target_table)).all() == []
        batch = connection.execute(select(provenance_table)).one()
        stage_tables = connection.exec_driver_sql(
            "SELECT name FROM sqlite_temp_master "
            "WHERE type='table' AND name LIKE 'ingest_stage_%'"
        ).all()
    assert batch.status == "FAILED"
    assert batch.rows_accepted == 0
    assert stage_tables == []


def test_partial_failure_counts_malformed_and_invalid_rows(ingestion_setup):
    root, _, target_table, _, service = ingestion_setup
    path = _write_csv(
        root / "partial.csv",
        [["A-1", "2", "valid"], ["A-2", "bad", "invalid"], ["A-3", "3"]],
    )

    result = service.ingest(path, _spec(target_table))

    assert result.status == "COMPLETED"
    assert result.rows_read == 3
    assert result.rows_accepted == 1
    assert result.rows_rejected == 2
    assert result.rejection_issue_count == 2
    assert {item.reason.split(":")[0] for item in result.rejections} == {
        "invalid integer value",
        "malformed record",
    }


def test_batch_statuses_and_failure_summary_are_persisted(ingestion_setup):
    root, engine, target_table, provenance_table, service = ingestion_setup
    path = _write_csv(root / "failed.csv", [["A-1", "-1", "constraint"]])

    with pytest.raises(IngestionError, match="transaction failed"):
        service.ingest(path, _spec(target_table))

    with engine.connect() as connection:
        batch = connection.execute(select(provenance_table)).one()
    summary = json.loads(batch.validation_summary_json)
    assert batch.status == "FAILED"
    assert summary["fatal_error_type"] == "IntegrityError"
    assert "test rollback" not in batch.validation_summary_json


def test_batch_transitions_through_validation_and_loading(ingestion_setup):
    root, _, target_table, _, service = ingestion_setup
    path = _write_csv(root / "transitions.csv", [["A-1", "1", "status"]])
    transitions = []
    set_status = service._set_batch_status

    def record_transition(target, batch_id, status, *, report=None):
        transitions.append(status)
        set_status(target, batch_id, status, report=report)

    service._set_batch_status = record_transition
    result = service.ingest(path, _spec(target_table))

    assert transitions == ["VALIDATING", "LOADING"]
    assert result.status == "COMPLETED"


def test_sensitive_values_are_redacted_and_hmac_hook_pseudonymizes(ingestion_setup):
    root, engine, target_table, _, service = ingestion_setup
    path = _write_csv(root / "sensitive.csv", [["", "bad", "note"]])
    key = b"k" * 32
    spec = _spec(
        target_table,
        sensitive_id=True,
        transform_id=HmacPseudonymizer(key),
    )
    result = service.ingest(path, spec)

    sensitive_rejections = [
        item for item in result.rejections if item.column_name == "id"
    ]
    assert sensitive_rejections
    assert all(item.original_value is None for item in sensitive_rejections)
    valid_path = _write_csv(root / "sensitive-valid.csv", [["private-id", "1", "note"]])
    service.ingest(valid_path, spec)
    with engine.connect() as connection:
        stored_id = connection.execute(select(target_table.c.external_id)).scalar_one()
    assert stored_id != "private-id"
    assert len(stored_id) == 64


def test_target_isolation_and_explicit_configuration(tmp_path: Path):
    operational = create_engine("sqlite:///:memory:")
    historical = create_engine("sqlite:///:memory:")
    operational_provenance = DataProvenanceBatch.__table__
    historical_provenance = HistoricalDataProvenanceBatch.__table__
    operational_provenance.create(operational)
    historical_provenance.create(historical)
    target_table = Table(
        "isolated_rows",
        MetaData(),
        Column("external_id", String(50), primary_key=True),
        Column("quantity", Integer, nullable=False),
        Column("note", String(100)),
        UniqueConstraint("external_id"),
    )
    target_table.create(operational)
    target_table.create(historical)
    service = IngestionService(
        targets={
            DatabaseTarget.OPERATIONAL: (operational, operational_provenance),
            DatabaseTarget.HISTORICAL: (historical, historical_provenance),
        },
        allowed_source_roots=[tmp_path],
    )
    path = _write_csv(tmp_path / "historical.csv", [["H-1", "9", "history"]])

    result = service.ingest(
        path,
        _spec(target_table, target_database=DatabaseTarget.HISTORICAL),
    )

    assert result.target_database == DatabaseTarget.HISTORICAL
    with operational.connect() as connection:
        assert connection.execute(select(operational_provenance)).all() == []
        assert connection.execute(select(target_table)).all() == []
    with historical.connect() as connection:
        assert connection.execute(select(historical_provenance)).one().target_database == (
            "HISTORICAL"
        )
        assert len(connection.execute(select(target_table)).all()) == 1
    operational.dispose()
    historical.dispose()


def test_operational_and_historical_provenance_targets_cannot_be_swapped():
    operational = create_engine("sqlite:///:memory:")
    with pytest.raises(ValueError, match="own provenance model"):
        IngestionService(
            targets={
                DatabaseTarget.OPERATIONAL: (
                    operational,
                    HistoricalDataProvenanceBatch.__table__,
                )
            },
            allowed_source_roots=[Path.cwd()],
        )
    operational.dispose()


def test_concurrent_same_checksum_imports_create_one_completed_batch(tmp_path: Path):
    database_path = tmp_path / "concurrent.db"
    engine = create_engine(
        f"sqlite:///{database_path.as_posix()}",
        connect_args={"timeout": 15},
    )
    provenance_table = DataProvenanceBatch.__table__
    provenance_table.create(engine)
    target_table = Table(
        "concurrent_rows",
        MetaData(),
        Column("external_id", String(50), primary_key=True),
        Column("quantity", Integer, nullable=False),
        Column("note", String(100)),
        UniqueConstraint("external_id"),
    )
    target_table.create(engine)
    service = IngestionService(
        targets={DatabaseTarget.OPERATIONAL: (engine, provenance_table)},
        allowed_source_roots=[tmp_path],
    )
    path = _write_csv(tmp_path / "concurrent.csv", [["A-1", "1", "shared"]])
    spec = _spec(target_table)
    reservation_barrier = Barrier(2)
    reserve_batch = service._reserve_batch

    def synchronized_reservation(*args, **kwargs):
        reservation_barrier.wait(timeout=10)
        return reserve_batch(*args, **kwargs)

    service._reserve_batch = synchronized_reservation

    def import_or_contend():
        try:
            return service.ingest(path, spec)
        except BatchAlreadyInProgressError:
            return None

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: import_or_contend(), range(2)))

    with engine.connect() as connection:
        batches = connection.execute(select(provenance_table)).all()
        rows = connection.execute(select(target_table)).all()
    assert len(batches) == 1
    assert batches[0].status == "COMPLETED"
    assert len(rows) == 1
    completed_results = [result for result in results if result is not None]
    assert len(completed_results) in {1, 2}
    assert sum(not result.idempotent_replay for result in completed_results) == 1
    if len(completed_results) == 2:
        assert sum(result.idempotent_replay for result in completed_results) == 1
        assert len({result.batch_id for result in completed_results}) == 1
    engine.dispose()


def test_large_csv_is_processed_in_bounded_chunks(ingestion_setup):
    root, engine, target_table, _, service = ingestion_setup
    rows = [[f"L-{number}", str(number), "large synthetic row"] for number in range(2500)]
    path = _write_csv(root / "large.csv", rows)
    flush_sizes = []
    flush_stage = service._flush_stage

    def observe_flush(connection, stage, chunk, spec, report):
        flush_sizes.append(len(chunk))
        return flush_stage(connection, stage, chunk, spec, report)

    service._flush_stage = observe_flush
    result = service.ingest(path, _spec(target_table))

    assert result.rows_read == 2500
    assert result.rows_accepted == 2500
    assert len(flush_sizes) > 1
    assert max(flush_sizes) <= 2
    with engine.connect() as connection:
        assert len(connection.execute(select(target_table)).all()) == 2500


def test_chunked_processing_and_bounded_rejection_report(ingestion_setup):
    root, engine, target_table, _, _ = ingestion_setup
    service = IngestionService(
        targets={
            DatabaseTarget.OPERATIONAL: (
                engine,
                DataProvenanceBatch.__table__,
            )
        },
        allowed_source_roots=[root],
        chunk_size=2,
        max_reported_rejections=1,
    )
    rows = [[f"ID-{number}", str(number), "row"] for number in range(5)]
    rows.extend([["BAD-1", "nope", "x"], ["BAD-2", "nope", "y"]])
    path = _write_csv(root / "chunked.csv", rows)

    result = service.ingest(path, _spec(target_table))

    assert result.rows_read == 7
    assert result.rows_accepted == 5
    assert result.rows_rejected == 2
    assert len(result.rejections) == 1
    assert result.rejections_truncated
    with engine.connect() as connection:
        assert len(connection.execute(select(target_table)).all()) == 5


def test_paths_formats_size_and_worksheet_are_validated(ingestion_setup, tmp_path):
    root, engine, target_table, _, service = ingestion_setup
    outside_root = tmp_path.parent / f"{tmp_path.name}-outside"
    outside_root.mkdir()
    outside = outside_root / "outside.csv"
    _write_csv(outside, [["A-1", "1", "outside"]])
    with pytest.raises(IngestionError, match="outside"):
        service.ingest(outside, _spec(target_table))
    traversal = root / ".." / outside_root.name / outside.name
    with pytest.raises(IngestionError, match="outside"):
        service.ingest(traversal, _spec(target_table))

    symlink = root / "linked-outside.csv"
    try:
        symlink.symlink_to(outside)
    except OSError:
        pytest.skip("File symlinks are unavailable in this Windows environment.")
    with pytest.raises(IngestionError, match="outside"):
        service.ingest(symlink, _spec(target_table))

    bad_extension = root / "not-a-csv.csv"
    bad_extension.write_bytes(b"PK\x03\x04binary")
    with pytest.raises(IngestionError, match="extension"):
        service.ingest(bad_extension, _spec(target_table))

    workbook_path = root / "wrong-sheet.xlsx"
    workbook = Workbook()
    workbook.active.title = "Actual"
    workbook.active.append(["id", "quantity", "note"])
    workbook.save(workbook_path)
    with pytest.raises(IngestionError, match="worksheet"):
        service.ingest(
            workbook_path,
            _spec(target_table, sheet_name="Missing"),
        )

    limited = IngestionService(
        targets={
            DatabaseTarget.OPERATIONAL: (
                engine,
                DataProvenanceBatch.__table__,
            )
        },
        allowed_source_roots=[root],
        max_file_size_bytes=5,
    )
    with pytest.raises(IngestionError, match="configured .*byte limit"):
        limited.ingest(
            _write_csv(root / "too-large.csv", [["A-1", "1", "too large"]]),
            _spec(target_table),
        )


def test_identical_batch_in_progress_is_not_started_twice(ingestion_setup):
    root, engine, target_table, provenance_table, service = ingestion_setup
    path = _write_csv(root / "in-progress.csv", [["A-1", "1", "pending"]])
    first = service.ingest(path, _spec(target_table))
    with engine.begin() as connection:
        connection.execute(
            provenance_table.update()
            .where(provenance_table.c.batch_id == first.batch_id)
            .values(status="LOADING")
        )

    with pytest.raises(BatchAlreadyInProgressError):
        service.ingest(path, _spec(target_table))
