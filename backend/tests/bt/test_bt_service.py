"""Tests for BtService (BTS-04, BTE-12).

Verifies service layer: run, history, results, error handling, and
isolation.  Uses in-memory SQLite with ORM-level table creation.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session, sessionmaker

from backend.app.models.bt_snapshot import BtSnapshot
from backend.app.models.draw import Draw as DrawModel
from backend.app.models.draw_number import DrawNumber
from backend.app.models.lottery import Lottery
from backend.app.models.super_number import SuperNumber
from backend.app.repositories.base import Base
from backend.app.services.bt_service import BtService
from backend.app.services.errors import NotFoundError


def _setup_db():
    engine = sa.create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return engine


def _seed_lottery(session: Session, code: str = "PBA") -> Lottery:
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
    session.add(lottery)
    session.flush()
    return lottery


def _seed_draws(session: Session, lottery_id: int, count: int) -> None:
    base = date(2015, 1, 1)
    for i in range(count):
        draw = DrawModel(
            lottery_id=lottery_id,
            draw_number=i + 1,
            draw_date=base + timedelta(weeks=i),
            is_deleted=False,
        )
        session.add(draw)
        session.flush()
        for n in range(1, 6):
            dn = DrawNumber(draw_id=draw.id, position=n, number=n)
            session.add(dn)
        sn = SuperNumber(draw_id=draw.id, value=10)
        session.add(sn)
    session.flush()


class TestBtServiceRun:
    """BtService.run() — BTS-04, BTE-12."""

    def test_run_returns_outcome(self) -> None:
        engine = _setup_db()
        factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
        with factory() as session:
            lottery = _seed_lottery(session)
            _seed_draws(session, lottery.id, 200)
            session.commit()

            service = BtService(session)
            outcome = service.run(
                lottery_id=lottery.id,
                strategy_id="ml-core-5",
                train_years=2,
                eval_count=1,
                seed=42,
            )
            assert outcome.snapshot_id > 0
            assert outcome.lottery_id == lottery.id
            assert outcome.strategy_id == "ml-core-5"
            assert outcome.status == "active"

    def test_run_persists_snapshot(self) -> None:
        engine = _setup_db()
        factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
        with factory() as session:
            lottery = _seed_lottery(session)
            _seed_draws(session, lottery.id, 200)
            session.commit()

            service = BtService(session)
            outcome = service.run(
                lottery_id=lottery.id,
                strategy_id="ml-core-5",
                train_years=2,
                eval_count=1,
                seed=42,
            )

            snap = session.get(BtSnapshot, outcome.snapshot_id)
            assert snap is not None
            assert snap.status == "active"

    def test_run_unknown_lottery_raises(self) -> None:
        engine = _setup_db()
        factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
        with factory() as session:
            service = BtService(session)
            with pytest.raises(NotFoundError):
                service.run(lottery_id=9999, strategy_id="ml-core-5")

    def test_run_unknown_strategy_prefix_raises(self) -> None:
        engine = _setup_db()
        factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
        with factory() as session:
            lottery = _seed_lottery(session)
            _seed_draws(session, lottery.id, 200)
            session.commit()

            service = BtService(session)
            with pytest.raises(Exception, match="unknown strategy prefix"):
                service.run(
                    lottery_id=lottery.id,
                    strategy_id="bad-prefix",
                    train_years=2,
                    eval_count=1,
                )

    def test_run_idempotent_fingerprint(self) -> None:
        """Same config → same fingerprint → upsert (delete old, create new)."""
        engine = _setup_db()
        factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
        with factory() as session:
            lottery = _seed_lottery(session)
            _seed_draws(session, lottery.id, 200)
            session.commit()

            service = BtService(session)
            o1 = service.run(
                lottery_id=lottery.id,
                strategy_id="ml-core-5",
                train_years=2,
                eval_count=1,
                seed=42,
            )
            o2 = service.run(
                lottery_id=lottery.id,
                strategy_id="ml-core-5",
                train_years=2,
                eval_count=1,
                seed=42,
            )
            # Same fingerprint → upsert → version incremented
            assert o1.fingerprint == o2.fingerprint
            assert o2.version == "2"


class TestBtServiceHistory:
    """BtService.history() — read-only."""

    def test_history_empty(self) -> None:
        engine = _setup_db()
        factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
        with factory() as session:
            lottery = _seed_lottery(session)
            session.commit()

            service = BtService(session)
            entries = service.history(lottery.id)
            assert entries == []

    def test_history_returns_snapshots(self) -> None:
        engine = _setup_db()
        factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
        with factory() as session:
            lottery = _seed_lottery(session)
            _seed_draws(session, lottery.id, 200)
            session.commit()

            service = BtService(session)
            service.run(
                lottery_id=lottery.id,
                strategy_id="ml-core-5",
                train_years=2,
                eval_count=1,
            )
            entries = service.history(lottery.id)
            assert len(entries) == 1
            assert entries[0].strategy_id == "ml-core-5"

    def test_history_unknown_lottery_raises(self) -> None:
        engine = _setup_db()
        factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
        with factory() as session:
            service = BtService(session)
            with pytest.raises(NotFoundError):
                service.history(9999)


class TestBtServiceResults:
    """BtService.results() — read-only."""

    def test_results_active(self) -> None:
        engine = _setup_db()
        factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
        with factory() as session:
            lottery = _seed_lottery(session)
            _seed_draws(session, lottery.id, 200)
            session.commit()

            service = BtService(session)
            service.run(
                lottery_id=lottery.id,
                strategy_id="ml-core-5",
                train_years=2,
                eval_count=1,
            )
            raw = service.results(lottery.id)
            assert raw["snapshot_id"] > 0
            assert raw["lottery_id"] == lottery.id
            assert "aggregate_metrics" in raw

    def test_results_by_snapshot_id(self) -> None:
        engine = _setup_db()
        factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
        with factory() as session:
            lottery = _seed_lottery(session)
            _seed_draws(session, lottery.id, 200)
            session.commit()

            service = BtService(session)
            outcome = service.run(
                lottery_id=lottery.id,
                strategy_id="ml-core-5",
                train_years=2,
                eval_count=1,
            )
            raw = service.results(lottery.id, snapshot_id=outcome.snapshot_id)
            assert raw["snapshot_id"] == outcome.snapshot_id

    def test_results_no_active_raises(self) -> None:
        engine = _setup_db()
        factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
        with factory() as session:
            lottery = _seed_lottery(session)
            session.commit()

            service = BtService(session)
            with pytest.raises(NotFoundError, match="no active"):
                service.results(lottery.id)

    def test_results_unknown_snapshot_raises(self) -> None:
        engine = _setup_db()
        factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
        with factory() as session:
            lottery = _seed_lottery(session)
            session.commit()

            service = BtService(session)
            with pytest.raises(NotFoundError):
                service.results(lottery.id, snapshot_id=9999)


class TestBtServiceIsolation:
    """Multi-lottery isolation (BTE-14)."""

    def test_history_per_lottery(self) -> None:
        engine = _setup_db()
        factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
        with factory() as session:
            l1 = _seed_lottery(session, "PBA")
            l2 = _seed_lottery(session, "BAL")
            _seed_draws(session, l1.id, 200)
            _seed_draws(session, l2.id, 200)
            session.commit()

            service = BtService(session)
            service.run(lottery_id=l1.id, strategy_id="ml-core-5", train_years=2, eval_count=1)
            service.run(lottery_id=l2.id, strategy_id="dl-core-3", train_years=2, eval_count=1)

            h1 = service.history(l1.id)
            h2 = service.history(l2.id)
            assert len(h1) == 1
            assert len(h2) == 1
            assert h1[0].strategy_id == "ml-core-5"
            assert h2[0].strategy_id == "dl-core-3"
