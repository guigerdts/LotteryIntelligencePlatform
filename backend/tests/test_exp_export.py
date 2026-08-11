"""Tests for ExpService.export() and ExperimentExporter — EXP-006, NFR-EXP-02/03.

Strict TDD: these tests reference code that does NOT exist yet.
Run them → they MUST FAIL. Then implement exporters and export().
"""

import csv
import io
import json

import pytest

from backend.app.models.lottery import Lottery
from backend.app.services.errors import ExperimentNotFoundError, ExportFormatInvalidError
from backend.app.services.exp_service import ExpService


@pytest.fixture
def seeded_lottery(db):
    """Seed a lottery row for FK compliance."""
    lottery = Lottery(
        id=1,
        code="TEST",
        name="Test Lottery",
        country="US",
        min_number=1,
        max_number=50,
        numbers_to_select=5,
    )
    db.add(lottery)
    db.commit()
    return lottery


def _create_bt_snapshot(db, lottery_id: int, *, fingerprint: str = "fp_aaa") -> int:
    """Insert a bt_snapshots row and return its id."""
    from backend.app.models.bt_snapshot import BtSnapshot

    snap = BtSnapshot(
        lottery_id=lottery_id,
        strategy_id="strat-a",
        fingerprint=fingerprint,
        version="1",
        status="active",
        config_json="{}",
    )
    db.add(snap)
    db.flush()
    return snap.id


def _create_bt_result(db, snapshot_id: int, metrics: dict) -> int:
    """Insert a bt_results row with aggregate_metrics_json."""
    from backend.app.models.bt_result import BtResult

    row = BtResult(
        snapshot_id=snapshot_id,
        aggregate_metrics_json=json.dumps(metrics),
        window_history_json="[]",
    )
    db.add(row)
    db.flush()
    return row.id


class TestExportJson:
    """JSON export: {experiment, runs, comparisons}."""

    def test_export_json_structure(self, db, seeded_lottery):
        """Export JSON returns valid JSON with experiment, runs, comparisons."""
        service = ExpService(db)
        snap_id = _create_bt_snapshot(db, 1)
        _create_bt_result(db, snap_id, {"hit_rate": 0.15})

        outcome = service.create(lottery_id=1, name="Export Test")
        service.add_run(
            outcome.experiment_id,
            run_label="baseline",
            engine_type="backtesting",
            engine_snapshot_id=snap_id,
        )

        result = service.export(outcome.experiment_id, format="json")

        data = json.loads(result)
        assert "experiment" in data
        assert "runs" in data
        assert "comparisons" in data
        assert data["experiment"]["experiment_id"] == outcome.experiment_id
        assert data["experiment"]["name"] == "Export Test"
        assert len(data["runs"]) == 1
        assert data["runs"][0]["run_label"] == "baseline"
        assert data["runs"][0]["engine_type"] == "backtesting"

    def test_export_json_includes_comparisons(self, db, seeded_lottery):
        """Export JSON includes persisted comparisons."""
        service = ExpService(db)
        snap_a = _create_bt_snapshot(db, 1, fingerprint="fp_a")
        snap_b = _create_bt_snapshot(db, 1, fingerprint="fp_b")
        _create_bt_result(db, snap_a, {"hit_rate": 0.10})
        _create_bt_result(db, snap_b, {"hit_rate": 0.20})

        outcome = service.create(lottery_id=1, name="Export With Comp")
        run1 = service.add_run(
            outcome.experiment_id,
            run_label="run1",
            engine_type="backtesting",
            engine_snapshot_id=snap_a,
        )
        run2 = service.add_run(
            outcome.experiment_id,
            run_label="run2",
            engine_type="backtesting",
            engine_snapshot_id=snap_b,
        )
        service.compare(outcome.experiment_id, run_ids=[run1.run_id, run2.run_id])

        result = service.export(outcome.experiment_id, format="json")
        data = json.loads(result)

        assert len(data["comparisons"]) >= 1

    def test_export_json_experiment_not_found(self, db, seeded_lottery):
        """Export non-existent experiment raises ExperimentNotFoundError."""
        service = ExpService(db)
        with pytest.raises(ExperimentNotFoundError):
            service.export(999, format="json")


class TestExportCsv:
    """CSV export with standard columns."""

    def test_export_csv_has_header(self, db, seeded_lottery):
        """Export CSV contains the correct header row."""
        service = ExpService(db)
        snap_id = _create_bt_snapshot(db, 1)
        _create_bt_result(db, snap_id, {"hit_rate": 0.15})

        outcome = service.create(lottery_id=1, name="CSV Export Test")
        service.add_run(
            outcome.experiment_id,
            run_label="test-run",
            engine_type="backtesting",
            engine_snapshot_id=snap_id,
        )

        result = service.export(outcome.experiment_id, format="csv")

        reader = csv.reader(io.StringIO(result))
        header = next(reader)
        assert header == [
            "run_id",
            "run_label",
            "engine_type",
            "engine_snapshot_id",
            "engine_fingerprint",
            "notes",
            "created_at",
        ]

    def test_export_csv_has_data_rows(self, db, seeded_lottery):
        """Export CSV contains data rows matching runs."""
        service = ExpService(db)
        snap_id = _create_bt_snapshot(db, 1)
        _create_bt_result(db, snap_id, {"hit_rate": 0.15})

        outcome = service.create(lottery_id=1, name="CSV Rows Test")
        service.add_run(
            outcome.experiment_id,
            run_label="row-run",
            engine_type="backtesting",
            engine_snapshot_id=snap_id,
        )

        result = service.export(outcome.experiment_id, format="csv")

        reader = csv.reader(io.StringIO(result))
        rows = list(reader)
        assert len(rows) == 2  # header + 1 data row
        assert rows[1][1] == "row-run"  # run_label
        assert rows[1][2] == "backtesting"  # engine_type

    def test_export_csv_experiment_not_found(self, db, seeded_lottery):
        """Export CSV for non-existent experiment raises ExperimentNotFoundError."""
        service = ExpService(db)
        with pytest.raises(ExperimentNotFoundError):
            service.export(999, format="csv")


class TestExportInvalidFormat:
    """Invalid export format → ExportFormatInvalidError."""

    def test_export_invalid_format_raises(self, db, seeded_lottery):
        """Export with unsupported format raises ExportFormatInvalidError."""
        service = ExpService(db)
        outcome = service.create(lottery_id=1, name="Invalid Format")
        with pytest.raises(ExportFormatInvalidError) as exc_info:
            service.export(outcome.experiment_id, format="xml")
        assert exc_info.value.code == "EXPORT_FORMAT_INVALID"
