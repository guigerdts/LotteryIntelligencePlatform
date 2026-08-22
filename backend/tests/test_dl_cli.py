"""DL CLI surface gates (REQ-12 dl paragraph): ``lip dl train|models|metrics``.

Verifies argparse wiring (--lottery required, --model-set default core-3,
--window default 10 validated 2..20, --cut optional), plain-JSON outputs
mirroring the ML shapes (per-family rows for train; snapshot dict or
``{"error": ...}`` for models), unknown-lottery error handling and that
``models``/``metrics`` read from the store only — they never train.
"""

from __future__ import annotations

import json
from decimal import Decimal
from unittest.mock import patch

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session, sessionmaker

# ---------------------------------------------------------------------------
# Helpers (mirrors tests/test_ml_pr5.py seeding)
# ---------------------------------------------------------------------------

_F4_FEATURES = [
    "consecutive_count",
    "draw_mean",
    "draw_range",
    "draw_sum",
    "low_high_ratio",
    "max_current_gap",
    "odd_even_ratio",
    "repeated_from_previous",
]

_METRIC_NAMES = ("accuracy", "precision", "recall", "f1", "roc_auc")


def _seed_lottery(session: Session, lottery_id: int = 1) -> None:
    """Insert a minimal lottery row."""
    session.execute(
        sa.text(
            "INSERT INTO lottery (id, code, name, country, min_number, max_number, "
            "numbers_to_select, created_at) "
            "VALUES (:id, :code, :name, :country, :min, :max, :sel, datetime('now'))"
        ),
        {
            "id": lottery_id,
            "code": f"L{lottery_id}",
            "name": f"Lot {lottery_id}",
            "country": "AR",
            "min": 1,
            "max": 50,
            "sel": 6,
        },
    )
    session.flush()


def _seed_draws(session: Session, lottery_id: int, count: int = 12) -> None:
    """Insert minimal draw rows with numbers."""
    for i in range(1, count + 1):
        session.execute(
            sa.text(
                "INSERT INTO draw (lottery_id, draw_number, draw_date, is_deleted, created_at) "
                "VALUES (:lid, :dn, :dd, 0, datetime('now'))"
            ),
            {"lid": lottery_id, "dn": i, "dd": f"2024-01-{i:02d}"},
        )
        draw_id = session.execute(sa.text("SELECT last_insert_rowid()")).scalar()
        for n in range(1, 7):
            session.execute(
                sa.text(
                    "INSERT INTO draw_numbers (draw_id, number, position) VALUES (:did, :num, :pos)"
                ),
                {"did": draw_id, "num": n + (i % 10), "pos": n},
            )
    session.flush()


def _seed_f4_snapshot(session: Session, lottery_id: int) -> None:
    """Insert a feature snapshot + values for all 8 features across 12 draws."""
    session.execute(
        sa.text(
            "INSERT INTO feature_snapshots "
            "(lottery_id, feature_set, version, feature_engine_version, "
            "checksum, input_fingerprint, draws_from, draws_to, "
            "draw_count, status, is_locked, created_at, updated_at) "
            "VALUES (:lid, 'core', '1', '1.0.0', 'abc', 'test_fp', "
            "1, 12, 12, 'active', 1, datetime('now'), datetime('now'))"
        ),
        {"lid": lottery_id},
    )
    snap_id = session.execute(sa.text("SELECT last_insert_rowid()")).scalar()

    for draw_num in range(1, 13):
        for j, fid in enumerate(_F4_FEATURES):
            session.execute(
                sa.text(
                    "INSERT INTO feature_values "
                    "(snapshot_id, feature_id, feature_version, "
                    "draw_number, value) "
                    "VALUES (:sid, :fid, '1', :dn, :val)"
                ),
                {
                    "sid": snap_id,
                    "fid": fid,
                    "dn": draw_num,
                    "val": float(j * 0.1 + draw_num * 0.01),
                },
            )
    session.flush()


def _seed_full_lottery(db: Session) -> None:
    """Seed one lottery with draws + an active F4 snapshot and commit."""
    _seed_lottery(db)
    _seed_draws(db, 1)
    _seed_f4_snapshot(db, 1)
    db.commit()


def _seed_active_snapshot(session: Session) -> int:
    """Commit one active DL snapshot with aggregate metrics via the store only."""
    from backend.app.dl.registry import MODEL_SET_CORE_3
    from backend.app.dl.snapshot_store import DlSnapshotStore
    from backend.app.models.dl_metric import DlMetric

    store = DlSnapshotStore(session)
    header = store.create_snapshot(
        lottery_id=1,
        model_set=MODEL_SET_CORE_3,
        version="1",
        dl_generator_version="1.0.0",
        checksum="cli-checksum",
        input_fingerprint="f" * 64,
        cut=7,
        window=3,
        status="active",
        is_locked=True,
        draw_count=10,
        draws_from=1,
        draws_to=10,
    )
    rows = [
        DlMetric(
            model_id=family,
            model_version="1.0.0",
            number=0,
            metric_name=name,
            value=Decimal("0.50000000"),
            params_json="{}",
        )
        for family in ("mlp", "lstm")
        for name in _METRIC_NAMES
    ]
    store.bulk_insert_metrics(header.id, rows)
    session.commit()
    return header.id


def _run_cli(session_factory: sessionmaker[Session], *argv: str) -> int:
    """Run ``lip <argv>`` against the test DB by patching the CLI SessionLocal."""
    from backend.app.cli import main

    with patch("backend.app.cli.SessionLocal", session_factory):
        return main(list(argv))


# ---------------------------------------------------------------------------
# Argparse wiring
# ---------------------------------------------------------------------------


class TestDlCliArgParsing:
    """``lip dl`` group registration and argument validation."""

    def test_dl_group_help_exits_cleanly(self) -> None:
        """``lip dl --help`` exits 0 once the group is registered."""
        from backend.app.cli import main

        with pytest.raises(SystemExit) as exc_info:
            main(["dl", "--help"])
        assert exc_info.value.code == 0

    def test_dl_train_help_exits_cleanly(self) -> None:
        """``lip dl train --help`` documents the train options."""
        from backend.app.cli import main

        with pytest.raises(SystemExit) as exc_info:
            main(["dl", "train", "--help"])
        assert exc_info.value.code == 0

    def test_dl_models_help_exits_cleanly(self) -> None:
        """``lip dl models --help`` exits cleanly."""
        from backend.app.cli import main

        with pytest.raises(SystemExit) as exc_info:
            main(["dl", "models", "--help"])
        assert exc_info.value.code == 0

    def test_dl_metrics_help_exits_cleanly(self) -> None:
        """``lip dl metrics --help`` exits cleanly."""
        from backend.app.cli import main

        with pytest.raises(SystemExit) as exc_info:
            main(["dl", "metrics", "--help"])
        assert exc_info.value.code == 0

    @pytest.mark.parametrize("window", ["1", "21"])
    def test_window_outside_bounds_is_rejected(
        self, session_factory: sessionmaker[Session], window: str, capsys
    ) -> None:
        """--window outside 2..20 is rejected by argparse before any handler runs."""
        from backend.app.cli import main

        with pytest.raises(SystemExit) as exc_info:
            main(["dl", "train", "--lottery", "L1", "--window", window])
        assert exc_info.value.code == 2
        assert "window" in capsys.readouterr().err.lower(), "rejection must cite the window bounds"


# ---------------------------------------------------------------------------
# Error paths
# ---------------------------------------------------------------------------


class TestDlCliErrors:
    """Domain errors surface through the CLI exit code."""

    def test_unknown_lottery_returns_rc1_with_message(
        self, session_factory: sessionmaker[Session], capsys
    ) -> None:
        """An unknown --lottery code prints an error to stderr and exits 1."""
        rc = _run_cli(session_factory, "dl", "train", "--lottery", "NOPE")

        assert rc == 1
        captured = capsys.readouterr()
        assert "does not exist" in captured.err

    def test_models_without_active_snapshot_prints_error_object(
        self, session_factory: sessionmaker[Session], db: Session, capsys
    ) -> None:
        """``lip dl models`` with no snapshot prints {"error": ...} and exits 0."""
        _seed_lottery(db)
        db.commit()

        rc = _run_cli(session_factory, "dl", "models", "--lottery", "L1")

        assert rc == 0
        payload = json.loads(capsys.readouterr().out)
        assert "error" in payload


# ---------------------------------------------------------------------------
# Store-only reads (never train — DLE-14)
# ---------------------------------------------------------------------------


class TestDlCliStoreReads:
    """``lip dl models|metrics`` print persisted rows only."""

    def test_models_prints_active_snapshot_json(
        self, session_factory: sessionmaker[Session], db: Session, capsys
    ) -> None:
        """A store-seeded active snapshot is printed as its metadata dict."""
        _seed_lottery(db)
        _seed_active_snapshot(db)

        rc = _run_cli(session_factory, "dl", "models", "--lottery", "L1")

        assert rc == 0
        payload = json.loads(capsys.readouterr().out)
        assert payload["model_set"] == "core-3"
        assert payload["status"] == "active"
        assert payload["cut"] == 7
        assert payload["input_fingerprint"] == "f" * 64

    def test_metrics_prints_rows_and_supports_model_filter(
        self, session_factory: sessionmaker[Session], db: Session, capsys
    ) -> None:
        """All 10 aggregate rows print by default; --model mlp filters to 5."""
        _seed_lottery(db)
        _seed_active_snapshot(db)

        rc_all = _run_cli(session_factory, "dl", "metrics", "--lottery", "L1")
        assert rc_all == 0
        rows = json.loads(capsys.readouterr().out)
        assert len(rows) == 10
        assert {r["model_id"] for r in rows} == {"mlp", "lstm"}
        for row in rows:
            assert row["number"] == 0
            assert isinstance(row["value"], float)

        rc_mlp = _run_cli(session_factory, "dl", "metrics", "--lottery", "L1", "--model", "mlp")
        assert rc_mlp == 0
        filtered = json.loads(capsys.readouterr().out)
        assert len(filtered) == 5
        assert {r["model_id"] for r in filtered} == {"mlp"}


# ---------------------------------------------------------------------------
# Train output shape
# ---------------------------------------------------------------------------


class TestDlCliTrain:
    """``lip dl train`` prints per-family JSON rows."""

    def test_train_prints_per_family_plain_json(
        self, session_factory: sessionmaker[Session], db: Session, capsys
    ) -> None:
        """Training prints a JSON list with one row per family carrying the run
        outcome fields, then the snapshot is readable back from the store."""
        _seed_full_lottery(db)

        rc = _run_cli(session_factory, "dl", "train", "--lottery", "L1", "--window", "2")

        assert rc == 0
        rows = json.loads(capsys.readouterr().out)
        assert isinstance(rows, list)
        assert {r["family"] for r in rows} == {"mlp", "lstm"}
        for row in rows:
            assert set(row) == {
                "family",
                "status",
                "snapshot_id",
                "fingerprint",
                "metrics_checksum",
                "error",
            }
            assert row["status"] == "active"
            assert isinstance(row["snapshot_id"], int)
