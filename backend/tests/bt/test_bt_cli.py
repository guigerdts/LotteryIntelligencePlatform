"""Tests for Backtesting CLI commands (BTS-02).

Verifies `lip bt run`, `lip bt history`, and `lip bt results` with
session monkeypatching.
"""

from __future__ import annotations

import io
import json
from contextlib import redirect_stderr, redirect_stdout
from datetime import date, timedelta

from sqlalchemy.orm import Session

import backend.app.cli as cli_module
from backend.app.models.draw import Draw as DrawModel
from backend.app.models.draw_number import DrawNumber
from backend.app.models.lottery import Lottery
from backend.app.models.super_number import SuperNumber


def _seed_lottery(db: Session, code: str = "PBA") -> int:
    lottery = Lottery(
        code=code,
        name=f"Lottery {code}",
        country="CO",
        min_number=1,
        max_number=50,
        numbers_to_select=5,
        super_number_min=1,
        super_number_max=16,
    )
    db.add(lottery)
    db.flush()
    return lottery.id


def _seed_draws(db: Session, lottery_id: int, count: int) -> None:
    base = date(2015, 1, 1)
    for i in range(count):
        draw = DrawModel(
            lottery_id=lottery_id,
            draw_number=i + 1,
            draw_date=base + timedelta(weeks=i),
            is_deleted=False,
        )
        db.add(draw)
        db.flush()
        for n in range(1, 6):
            dn = DrawNumber(draw_id=draw.id, position=n, number=n)
            db.add(dn)
        sn = SuperNumber(draw_id=draw.id, value=10)
        db.add(sn)
    db.flush()


def _run_cli(argv: list[str], session_factory) -> tuple[int, str, str]:
    """Run CLI with monkeypatched SessionLocal; return (rc, stdout, stderr)."""
    original = cli_module.SessionLocal
    cli_module.SessionLocal = session_factory
    stdout = io.StringIO()
    stderr = io.StringIO()
    try:
        with redirect_stdout(stdout), redirect_stderr(stderr):
            rc = cli_module.main(argv)
    finally:
        cli_module.SessionLocal = original
    return rc, stdout.getvalue(), stderr.getvalue()


class TestBtRunCLI:
    """lip bt run — BTS-02."""

    def test_run_returns_json(self, db: Session, session_factory) -> None:
        lottery_id = _seed_lottery(db)
        _seed_draws(db, lottery_id, 200)
        db.commit()

        rc, stdout, stderr = _run_cli(
            [
                "bt",
                "run",
                "--lottery-id",
                str(lottery_id),
                "--strategy",
                "ml-core-5",
                "--train-years",
                "2",
                "--eval-count",
                "1",
            ],
            session_factory,
        )
        assert rc == 0
        data = json.loads(stdout)
        assert data["snapshot_id"] > 0
        assert data["lottery_id"] == lottery_id
        assert data["strategy_id"] == "ml-core-5"
        assert data["status"] == "active"

    def test_run_unknown_lottery_exits_1(self, db: Session, session_factory) -> None:
        rc, stdout, stderr = _run_cli(
            ["bt", "run", "--lottery-id", "9999", "--strategy", "ml-core-5"],
            session_factory,
        )
        assert rc == 1
        assert "RESOURCE_NOT_FOUND" in stderr

    def test_run_bad_strategy_exits_1(self, db: Session, session_factory) -> None:
        lottery_id = _seed_lottery(db)
        _seed_draws(db, lottery_id, 200)
        db.commit()

        rc, stdout, stderr = _run_cli(
            ["bt", "run", "--lottery-id", str(lottery_id), "--strategy", "bad-xyz"],
            session_factory,
        )
        assert rc == 1


class TestBtHistoryCLI:
    """lip bt history — BTS-02."""

    def test_history_empty(self, db: Session, session_factory) -> None:
        lottery_id = _seed_lottery(db)
        db.commit()

        rc, stdout, stderr = _run_cli(
            ["bt", "history", "--lottery-id", str(lottery_id)],
            session_factory,
        )
        assert rc == 0
        data = json.loads(stdout)
        assert data == []

    def test_history_with_snapshots(self, db: Session, session_factory) -> None:
        lottery_id = _seed_lottery(db)
        _seed_draws(db, lottery_id, 200)
        db.commit()

        # Run a backtest first
        _run_cli(
            [
                "bt",
                "run",
                "--lottery-id",
                str(lottery_id),
                "--strategy",
                "ml-core-5",
                "--train-years",
                "2",
                "--eval-count",
                "1",
            ],
            session_factory,
        )

        rc, stdout, stderr = _run_cli(
            ["bt", "history", "--lottery-id", str(lottery_id)],
            session_factory,
        )
        assert rc == 0
        data = json.loads(stdout)
        assert len(data) == 1
        assert data[0]["strategy_id"] == "ml-core-5"

    def test_history_unknown_lottery_exits_1(self, db: Session, session_factory) -> None:
        rc, stdout, stderr = _run_cli(
            ["bt", "history", "--lottery-id", "9999"],
            session_factory,
        )
        assert rc == 1
        assert "RESOURCE_NOT_FOUND" in stderr


class TestBtResultsCLI:
    """lip bt results — BTS-02."""

    def test_results_active(self, db: Session, session_factory) -> None:
        lottery_id = _seed_lottery(db)
        _seed_draws(db, lottery_id, 200)
        db.commit()

        # Run a backtest
        _run_cli(
            [
                "bt",
                "run",
                "--lottery-id",
                str(lottery_id),
                "--strategy",
                "ml-core-5",
                "--train-years",
                "2",
                "--eval-count",
                "1",
            ],
            session_factory,
        )

        rc, stdout, stderr = _run_cli(
            ["bt", "results", "--lottery-id", str(lottery_id)],
            session_factory,
        )
        assert rc == 0
        data = json.loads(stdout)
        assert data["snapshot_id"] > 0
        assert "aggregate_metrics" in data

    def test_results_no_active_exits_1(self, db: Session, session_factory) -> None:
        lottery_id = _seed_lottery(db)
        db.commit()

        rc, stdout, stderr = _run_cli(
            ["bt", "results", "--lottery-id", str(lottery_id)],
            session_factory,
        )
        assert rc == 1
        assert "RESOURCE_NOT_FOUND" in stderr
