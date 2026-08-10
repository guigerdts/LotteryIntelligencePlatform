"""E2E integration tests for Fase 10 Backtesting Engine (PR6).

Validates the complete pipeline: data → strategy → walk-forward split →
engine → metrics → benchmarks → fingerprint → snapshot store → service → API/CLI.
Covers: multi-lottery isolation, determinism, walk-forward integrity,
snapshot lifecycle, API/CLI parity, and error paths.
"""

from __future__ import annotations

import io
import json
from contextlib import redirect_stderr, redirect_stdout
from datetime import date, timedelta

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session, sessionmaker

import backend.app.cli as cli_module
from backend.app.backtesting.engine import BacktestEngine
from backend.app.backtesting.fingerprint import compute_bt_fingerprint
from backend.app.backtesting.snapshot_store import BtSnapshotStore
from backend.app.backtesting.splitter import WalkForwardSplitter
from backend.app.backtesting.types import BacktestConfig, Draw, DrawContext
from backend.app.models.bt_result import BtResult
from backend.app.models.bt_snapshot import BtSnapshot
from backend.app.models.draw import Draw as DrawModel
from backend.app.models.draw_number import DrawNumber
from backend.app.models.lottery import Lottery
from backend.app.models.super_number import SuperNumber
from backend.app.repositories.base import Base
from backend.app.services.bt_service import BtService
from backend.app.services.errors import InsufficientDataError, NotFoundError

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _setup_db():
    engine = sa.create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return engine


def _seed_lottery(session: Session, code: str = "PBA") -> Lottery:
    lottery = Lottery(
        code=code, name=f"Lottery {code}", country="CO",
        min_number=1, max_number=50, numbers_to_select=5,
        super_number_min=1, super_number_max=16,
    )
    session.add(lottery)
    session.flush()
    return lottery


def _seed_draws(session: Session, lottery_id: int, count: int) -> None:
    base = date(2015, 1, 1)
    for i in range(count):
        draw = DrawModel(
            lottery_id=lottery_id, draw_number=i + 1,
            draw_date=base + timedelta(weeks=i), is_deleted=False,
        )
        session.add(draw)
        session.flush()
        for n in range(1, 6):
            session.add(DrawNumber(draw_id=draw.id, position=n, number=n))
        session.add(SuperNumber(draw_id=draw.id, value=10))
    session.flush()


def _to_domain_draws(session: Session, lottery_id: int) -> list[Draw]:
    stmt = (
        sa.select(DrawModel)
        .where(DrawModel.lottery_id == lottery_id, DrawModel.is_deleted.is_(False))
        .order_by(DrawModel.draw_date)
    )
    result: list[Draw] = []
    for d in session.execute(stmt).scalars().all():
        nums = tuple(sorted(
            dn.number for dn in session.execute(
                sa.select(DrawNumber).where(DrawNumber.draw_id == d.id)
            ).scalars().all()
        ))
        super_num = d.super_number.value if d.super_number else None
        result.append(Draw(id=d.id, draw_date=d.draw_date, numbers=nums, super_number=super_num))
    return result


class _ConstantStrategy:
    """Always predicts [1,2,3,4,5] — deterministic, simple."""

    @property
    def strategy_id(self) -> str:
        return "constant-v1"

    def predict(self, ctx: DrawContext) -> list[int]:
        return [1, 2, 3, 4, 5]


# ---------------------------------------------------------------------------
# 1. Full Pipeline E2E
# ---------------------------------------------------------------------------


class TestFullPipelineE2E:
    """Complete backtest flow from data to persisted results."""

    def test_full_pipeline(self) -> None:
        engine = _setup_db()
        factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
        with factory() as session:
            lottery = _seed_lottery(session)
            _seed_draws(session, lottery.id, 200)
            session.commit()

            # 1. Fetch draws
            draws = _to_domain_draws(session, lottery.id)
            assert len(draws) == 200

            # 2. Configure walk-forward
            config = BacktestConfig(train_years=2, eval_count=1, step_count=1, seed=42)

            # 3. Split windows
            splitter = WalkForwardSplitter(config)
            windows = splitter.split(draws)
            assert len(windows) > 0

            # 4. Run engine
            strategy = _ConstantStrategy()
            bt_engine = BacktestEngine()
            result = bt_engine.run(
                strategy=strategy, draws=draws, config=config, lottery_id=lottery.id,
            )

            # 5. Verify metrics
            assert result.aggregate_metrics.total_draws_evaluated > 0
            assert result.aggregate_metrics.hit_rate >= 0

            # 6. Verify benchmarks present
            for wr in result.window_history:
                assert wr.uniform_metrics is not None
                assert wr.hypergeometric_metrics is not None

            # 7. Verify fingerprint
            assert result.fingerprint is not None
            assert len(result.fingerprint) == 64  # SHA-256

            # 8. Persist via store
            store = BtSnapshotStore(session)
            version = store.next_version(lottery.id, strategy.strategy_id)
            snapshot, bt_result = store.create_active(
                lottery_id=lottery.id, strategy_id=strategy.strategy_id,
                fingerprint=result.fingerprint, version=version,
                aggregate_metrics={"hit_rate": float(result.aggregate_metrics.hit_rate)},
                window_history=[],
            )
            session.commit()
            assert snapshot.id > 0
            assert bt_result.snapshot_id == snapshot.id

            # 9. Service layer
            service = BtService(session)
            outcome = service.run(
                lottery_id=lottery.id, strategy_id="ml-core-5",
                train_years=2, eval_count=1, seed=42,
            )
            assert outcome.snapshot_id > 0
            assert outcome.status == "active"


# ---------------------------------------------------------------------------
# 2. Multi-Lottery Isolation E2E (BTE-14)
# ---------------------------------------------------------------------------


class TestMultiLotteryIsolationE2E:
    """Lottery A results never contaminate lottery B."""

    def test_isolation(self) -> None:
        engine = _setup_db()
        factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
        with factory() as session:
            l1 = _seed_lottery(session, "PBA")
            l2 = _seed_lottery(session, "BAL")
            _seed_draws(session, l1.id, 200)
            _seed_draws(session, l2.id, 200)
            session.commit()

            service = BtService(session)
            # Use different seeds to get different fingerprints
            o1 = service.run(lottery_id=l1.id, strategy_id="ml-core-5", train_years=2, seed=42)
            o2 = service.run(lottery_id=l2.id, strategy_id="ml-core-5", train_years=2, seed=99)

            # Different fingerprints → different snapshots
            assert o1.fingerprint != o2.fingerprint

            # History is isolated
            h1 = service.history(l1.id)
            h2 = service.history(l2.id)
            assert len(h1) == 1
            assert len(h2) == 1
            assert h1[0].lottery_id == l1.id
            assert h2[0].lottery_id == l2.id

            # Results are isolated
            r1 = service.results(l1.id)
            r2 = service.results(l2.id)
            assert r1["lottery_id"] == l1.id
            assert r2["lottery_id"] == l2.id

    def test_cross_lottery_snapshot_not_visible(self) -> None:
        engine = _setup_db()
        factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
        with factory() as session:
            l1 = _seed_lottery(session, "PBA")
            l2 = _seed_lottery(session, "BAL")
            _seed_draws(session, l1.id, 200)
            _seed_draws(session, l2.id, 200)
            session.commit()

            service = BtService(session)
            o1 = service.run(lottery_id=l1.id, strategy_id="ml-core-5", train_years=2, seed=42)

            # Snapshot from lottery 1 should not be visible via lottery 2
            with pytest.raises(NotFoundError):
                service.results(l2.id, snapshot_id=o1.snapshot_id)


# ---------------------------------------------------------------------------
# 3. Determinism E2E
# ---------------------------------------------------------------------------


class TestDeterminismE2E:
    """Same inputs → same outputs, byte-for-byte."""

    def test_deterministic_results(self) -> None:
        engine = _setup_db()
        factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
        with factory() as session:
            lottery = _seed_lottery(session)
            _seed_draws(session, lottery.id, 200)
            session.commit()
            draws = _to_domain_draws(session, lottery.id)

            config = BacktestConfig(train_years=2, eval_count=1, seed=42)
            strategy = _ConstantStrategy()
            bt_engine = BacktestEngine()

            r1 = bt_engine.run(strategy=strategy, draws=draws, config=config, lottery_id=lottery.id)
            r2 = bt_engine.run(strategy=strategy, draws=draws, config=config, lottery_id=lottery.id)

            assert r1.fingerprint == r2.fingerprint
            assert r1.aggregate_metrics == r2.aggregate_metrics
            assert len(r1.window_history) == len(r2.window_history)
            for w1, w2 in zip(r1.window_history, r2.window_history, strict=False):
                assert w1.strategy_metrics == w2.strategy_metrics

    def test_fingerprint_reproducible(self) -> None:
        fp1 = compute_bt_fingerprint(
            strategy_id="ml-core-5", config=BacktestConfig(seed=42),
            data_hash="200", benchmark_type="both",
        )
        fp2 = compute_bt_fingerprint(
            strategy_id="ml-core-5", config=BacktestConfig(seed=42),
            data_hash="200", benchmark_type="both",
        )
        assert fp1 == fp2

    def test_different_seed_different_result(self) -> None:
        engine = _setup_db()
        factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
        with factory() as session:
            lottery = _seed_lottery(session)
            _seed_draws(session, lottery.id, 200)
            session.commit()
            draws = _to_domain_draws(session, lottery.id)

            strategy = _ConstantStrategy()
            bt_engine = BacktestEngine()

            r1 = bt_engine.run(
                strategy=strategy, draws=draws,
                config=BacktestConfig(train_years=2, seed=42), lottery_id=lottery.id,
            )
            r2 = bt_engine.run(
                strategy=strategy, draws=draws,
                config=BacktestConfig(train_years=2, seed=99), lottery_id=lottery.id,
            )
            # Different seeds → different fingerprints (determinism context changes)
            # But same strategy predictions, so metrics may match
            assert r1.fingerprint != r2.fingerprint


# ---------------------------------------------------------------------------
# 4. Walk-Forward / No-Leakage E2E (BTE-04, BTE-17)
# ---------------------------------------------------------------------------


class TestWalkForwardE2E:
    """Train-before-evaluate, consecutive windows, no look-ahead."""

    def test_train_before_evaluate(self) -> None:
        engine = _setup_db()
        factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
        with factory() as session:
            lottery = _seed_lottery(session)
            _seed_draws(session, lottery.id, 200)
            session.commit()
            draws = _to_domain_draws(session, lottery.id)

            config = BacktestConfig(train_years=2, eval_count=1, step_count=1)
            splitter = WalkForwardSplitter(config)
            windows = splitter.split(draws)

            for w in windows:
                last_train_date = max(d.draw_date for d in w.train_draws)
                first_eval_date = min(d.draw_date for d in w.eval_draws)
                assert last_train_date < first_eval_date, (
                    f"Window {w.index}: train {last_train_date} >= eval {first_eval_date}"
                )

    def test_consecutive_windows(self) -> None:
        engine = _setup_db()
        factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
        with factory() as session:
            lottery = _seed_lottery(session)
            _seed_draws(session, lottery.id, 200)
            session.commit()
            draws = _to_domain_draws(session, lottery.id)

            config = BacktestConfig(train_years=2, eval_count=1, step_count=5)
            splitter = WalkForwardSplitter(config)
            windows = splitter.split(draws)

            # Eval windows don't overlap and advance monotonically
            prev_eval_end = None
            for w in windows:
                eval_start = min(d.draw_date for d in w.eval_draws)
                if prev_eval_end is not None:
                    assert eval_start > prev_eval_end, (
                        f"Window {w.index}: eval overlap"
                    )
                prev_eval_end = max(d.draw_date for d in w.eval_draws)

    def test_no_look_ahead(self) -> None:
        """Strategy never sees future draws during prediction."""
        engine = _setup_db()
        factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
        with factory() as session:
            lottery = _seed_lottery(session)
            _seed_draws(session, lottery.id, 200)
            session.commit()
            draws = _to_domain_draws(session, lottery.id)

            config = BacktestConfig(train_years=2, eval_count=2, step_count=1)
            splitter = WalkForwardSplitter(config)
            windows = splitter.split(draws)

            for w in windows:
                eval_dates = {d.draw_date for d in w.eval_draws}
                train_dates = {d.draw_date for d in w.train_draws}
                # No date should appear in both
                assert eval_dates.isdisjoint(train_dates)

    def test_benchmark_same_eval_period(self) -> None:
        """BTE-16: strategy and benchmarks evaluate same draws."""
        engine = _setup_db()
        factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
        with factory() as session:
            lottery = _seed_lottery(session)
            _seed_draws(session, lottery.id, 200)
            session.commit()
            draws = _to_domain_draws(session, lottery.id)

            config = BacktestConfig(train_years=2, eval_count=1, seed=42)
            bt_engine = BacktestEngine()
            result = bt_engine.run(
                strategy=_ConstantStrategy(), draws=draws,
                config=config, lottery_id=lottery.id,
            )

            for wr in result.window_history:
                assert (
                    wr.strategy_metrics.total_draws_evaluated
                    == wr.uniform_metrics.total_draws_evaluated
                )
                assert (
                    wr.strategy_metrics.total_draws_evaluated
                    == wr.hypergeometric_metrics.total_draws_evaluated
                )


# ---------------------------------------------------------------------------
# 5. Snapshot Lifecycle E2E (BTE-10)
# ---------------------------------------------------------------------------


class TestSnapshotLifecycleE2E:
    """active → versioning, failed on error, atomicity, idempotency."""

    def test_active_lifecycle(self) -> None:
        engine = _setup_db()
        factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
        with factory() as session:
            lottery = _seed_lottery(session)
            _seed_draws(session, lottery.id, 200)
            session.commit()

            service = BtService(session)
            o1 = service.run(lottery_id=lottery.id, strategy_id="ml-core-5", train_years=2, seed=42)
            o2 = service.run(lottery_id=lottery.id, strategy_id="ml-core-5", train_years=2, seed=42)

            # Version incremented
            assert o1.version == "1"
            assert o2.version == "2"

            # Only latest is active
            h = service.history(lottery.id)
            active = [e for e in h if e.status == "active"]
            assert len(active) == 1
            assert active[0].version == "2"

    def test_idempotent_fingerprint(self) -> None:
        engine = _setup_db()
        factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
        with factory() as session:
            lottery = _seed_lottery(session)
            _seed_draws(session, lottery.id, 200)
            session.commit()

            service = BtService(session)
            o1 = service.run(lottery_id=lottery.id, strategy_id="ml-core-5", train_years=2, seed=42)
            o2 = service.run(lottery_id=lottery.id, strategy_id="ml-core-5", train_years=2, seed=42)

            # Same config → same fingerprint → upsert
            assert o1.fingerprint == o2.fingerprint
            assert o2.version == "2"

    def test_atomicity(self) -> None:
        """Snapshot + result created in same transaction."""
        engine = _setup_db()
        factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
        with factory() as session:
            lottery = _seed_lottery(session)
            _seed_draws(session, lottery.id, 200)
            session.commit()

            service = BtService(session)
            outcome = service.run(
                lottery_id=lottery.id, strategy_id="ml-core-5", train_years=2, seed=42,
            )

            snap = session.get(BtSnapshot, outcome.snapshot_id)
            assert snap is not None
            res = session.execute(
                sa.select(BtResult).where(BtResult.snapshot_id == snap.id)
            ).scalar_one_or_none()
            assert res is not None


# ---------------------------------------------------------------------------
# 6. API E2E
# ---------------------------------------------------------------------------


class TestApiE2E:
    """POST /run → GET /history → GET /results — full API cycle."""

    def test_api_full_cycle(self, client, db: Session) -> None:
        lottery = _seed_lottery(db)
        _seed_draws(db, lottery.id, 200)
        db.commit()

        # Run
        resp = client.post("/api/v1/backtesting/run", json={
            "lottery_id": lottery.id, "strategy_id": "ml-core-5",
            "train_years": 2, "eval_count": 1, "seed": 42,
        })
        assert resp.status_code == 200
        run_data = resp.json()["data"]
        assert run_data["status"] == "active"

        # History
        resp = client.get(f"/api/v1/backtesting/history?lottery_id={lottery.id}")
        assert resp.status_code == 200
        history = resp.json()["data"]
        assert len(history) == 1
        assert history[0]["snapshot_id"] == run_data["snapshot_id"]

        # Results
        resp = client.get(f"/api/v1/backtesting/results?lottery_id={lottery.id}")
        assert resp.status_code == 200
        results = resp.json()["data"]
        assert results["snapshot_id"] == run_data["snapshot_id"]
        assert "aggregate_metrics" in results


# ---------------------------------------------------------------------------
# 7. CLI E2E
# ---------------------------------------------------------------------------


class TestCliE2E:
    """lip bt run → lip bt history → lip bt results — full CLI cycle."""

    def _run(self, argv, factory):
        original = cli_module.SessionLocal
        cli_module.SessionLocal = factory
        stdout, stderr = io.StringIO(), io.StringIO()
        try:
            with redirect_stdout(stdout), redirect_stderr(stderr):
                rc = cli_module.main(argv)
        finally:
            cli_module.SessionLocal = original
        return rc, stdout.getvalue(), stderr.getvalue()

    def test_cli_full_cycle(self, db: Session, session_factory) -> None:
        lottery = _seed_lottery(db)
        _seed_draws(db, lottery.id, 200)
        db.commit()

        # Run
        rc, stdout, _ = self._run(
            ["bt", "run", "--lottery-id", str(lottery.id),
             "--strategy", "ml-core-5", "--train-years", "2", "--seed", "42"],
            session_factory,
        )
        assert rc == 0
        run_data = json.loads(stdout)
        assert run_data["status"] == "active"

        # History
        rc, stdout, _ = self._run(
            ["bt", "history", "--lottery-id", str(lottery.id)], session_factory,
        )
        assert rc == 0
        history = json.loads(stdout)
        assert len(history) == 1

        # Results
        rc, stdout, _ = self._run(
            ["bt", "results", "--lottery-id", str(lottery.id)], session_factory,
        )
        assert rc == 0
        results = json.loads(stdout)
        assert "aggregate_metrics" in results


# ---------------------------------------------------------------------------
# 8. Error-Path E2E
# ---------------------------------------------------------------------------


class TestErrorPathE2E:
    """All error paths return proper codes."""

    def test_unknown_lottery(self) -> None:
        engine = _setup_db()
        factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
        with factory() as session:
            service = BtService(session)
            try:
                service.run(lottery_id=9999, strategy_id="ml-core-5")
                raise AssertionError("should have raised")
            except NotFoundError as e:
                assert e.code == "RESOURCE_NOT_FOUND"

    def test_insufficient_data(self) -> None:
        engine = _setup_db()
        factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
        with factory() as session:
            lottery = _seed_lottery(session)
            _seed_draws(session, lottery.id, 5)
            session.commit()
            service = BtService(session)
            try:
                service.run(lottery_id=lottery.id, strategy_id="ml-core-5", min_train_draws=100)
                raise AssertionError("should have raised")
            except InsufficientDataError:
                pass

    def test_invalid_strategy_prefix(self) -> None:
        engine = _setup_db()
        factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
        with factory() as session:
            lottery = _seed_lottery(session)
            _seed_draws(session, lottery.id, 200)
            session.commit()
            service = BtService(session)
            try:
                service.run(lottery_id=lottery.id, strategy_id="bad-xyz")
                raise AssertionError("should have raised")
            except Exception as e:
                assert "unknown strategy prefix" in str(e)

    def test_no_active_snapshot(self) -> None:
        engine = _setup_db()
        factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
        with factory() as session:
            lottery = _seed_lottery(session)
            session.commit()
            service = BtService(session)
            try:
                service.results(lottery.id)
                raise AssertionError("should have raised")
            except NotFoundError as e:
                assert "no active" in str(e)

    def test_api_unknown_lottery_404(self, client, db: Session) -> None:
        resp = client.post("/api/v1/backtesting/run", json={
            "lottery_id": 9999, "strategy_id": "ml-core-5",
        })
        assert resp.status_code == 404

    def test_api_missing_body_422(self, client) -> None:
        resp = client.post("/api/v1/backtesting/run", json={})
        assert resp.status_code == 422

    def test_cli_unknown_lottery(self, db: Session, session_factory) -> None:
        original = cli_module.SessionLocal
        cli_module.SessionLocal = session_factory
        try:
            stderr = io.StringIO()
            with redirect_stderr(stderr):
                rc = cli_module.main(
                    ["bt", "run", "--lottery-id", "9999", "--strategy", "ml-core-5"]
                )
            assert rc == 1
            assert "RESOURCE_NOT_FOUND" in stderr.getvalue()
        finally:
            cli_module.SessionLocal = original


# ---------------------------------------------------------------------------
# 9. Data Floor E2E (BTE-07)
# ---------------------------------------------------------------------------


class TestDataFloorE2E:
    """Configurable minimum draws; raises InsufficientDataError."""

    def test_below_floor_raises(self) -> None:
        engine = _setup_db()
        factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
        with factory() as session:
            lottery = _seed_lottery(session)
            _seed_draws(session, lottery.id, 10)
            session.commit()
            draws = _to_domain_draws(session, lottery.id)

            bt_engine = BacktestEngine()
            try:
                bt_engine.run(
                    strategy=_ConstantStrategy(), draws=draws,
                    config=BacktestConfig(min_train_draws=100), lottery_id=lottery.id,
                )
                raise AssertionError("should have raised")
            except InsufficientDataError:
                pass

    def test_above_floor_proceeds(self) -> None:
        engine = _setup_db()
        factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
        with factory() as session:
            lottery = _seed_lottery(session)
            _seed_draws(session, lottery.id, 200)
            session.commit()
            draws = _to_domain_draws(session, lottery.id)

            bt_engine = BacktestEngine()
            result = bt_engine.run(
                strategy=_ConstantStrategy(), draws=draws,
                config=BacktestConfig(min_train_draws=100, train_years=2),
                lottery_id=lottery.id,
            )
            assert result is not None
