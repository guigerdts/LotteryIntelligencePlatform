"""BtService — backtesting service layer (BTS-04, BTE-12).

Exposes ``BacktestEngine`` through a service boundary.  API and CLI call
``run()``; the service owns DB access, draw fetching, strategy creation,
engine invocation, and persistence via ``BtSnapshotStore``.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from backend.app.backtesting.engine import BacktestEngine
from backend.app.backtesting.snapshot_store import BtSnapshotStore
from backend.app.backtesting.strategy import StaticStrategy
from backend.app.backtesting.types import BacktestConfig, Draw
from backend.app.core.response_cache import ThreadSafeLRU, register_cache
from backend.app.models.bt_result import BtResult
from backend.app.models.bt_snapshot import BtSnapshot
from backend.app.models.draw import Draw as DrawModel
from backend.app.services.errors import InsufficientDataError, NotFoundError, ServiceError


class BtRunError(ServiceError):
    """Backtest execution failure."""

    code = "BT_RUN_ERROR"


_BT_CACHE: ThreadSafeLRU[tuple, object] = ThreadSafeLRU(maxsize=256)
register_cache(_BT_CACHE)


@dataclass(frozen=True)
class BtRunOutcome:
    snapshot_id: int
    lottery_id: int
    strategy_id: str
    fingerprint: str
    version: str
    status: str


@dataclass(frozen=True)
class BtHistoryEntry:
    snapshot_id: int
    lottery_id: int
    strategy_id: str
    fingerprint: str
    version: str
    status: str
    created_at: str


class BtService:
    """Backtesting service (BTS-04).  API and CLI call this layer."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def run(
        self,
        *,
        lottery_id: int,
        strategy_id: str,
        train_years: int = 5,
        eval_count: int = 1,
        step_count: int = 1,
        min_train_draws: int = 100,
        seed: int = 42,
    ) -> BtRunOutcome:
        """Execute a backtest and persist results (BTE-12: manual-only)."""
        self._resolve_lottery(lottery_id)
        draws = self._fetch_draws(lottery_id)
        config = BacktestConfig(
            train_years=train_years,
            eval_count=eval_count,
            step_count=step_count,
            min_train_draws=min_train_draws,
            seed=seed,
        )
        strategy = _make_strategy(strategy_id)
        try:
            result = BacktestEngine().run(
                strategy=strategy,
                draws=draws,
                config=config,
                lottery_id=lottery_id,
                parallel=True,
            )
        except InsufficientDataError:
            raise
        except Exception as exc:
            raise BtRunError(f"backtest failed: {exc}") from exc

        store = BtSnapshotStore(self._session)
        version = store.next_version(lottery_id, strategy_id)
        agg = {
            "hit_rate": float(result.aggregate_metrics.hit_rate),
            "average_matches": float(result.aggregate_metrics.average_matches),
            "consistency_score": float(result.aggregate_metrics.consistency_score),
            "total_draws_evaluated": result.aggregate_metrics.total_draws_evaluated,
        }
        wh = [
            {
                "window_index": w.window_index,
                "train_range": list(w.train_range),
                "eval_range": list(w.eval_range),
            }
            for w in result.window_history
        ]
        cfg_json = json.dumps(
            {
                "train_years": train_years,
                "eval_count": eval_count,
                "step_count": step_count,
                "min_train_draws": min_train_draws,
                "seed": seed,
            }
        )
        snapshot, _ = store.create_active(
            lottery_id=lottery_id,
            strategy_id=strategy_id,
            fingerprint=result.fingerprint,
            version=version,
            aggregate_metrics=agg,
            window_history=wh,
            config_json=cfg_json,
        )
        self._session.commit()
        return BtRunOutcome(
            snapshot_id=snapshot.id,
            lottery_id=lottery_id,
            strategy_id=strategy_id,
            fingerprint=result.fingerprint,
            version=version,
            status="active",
        )

    def history(self, lottery_id: int) -> list[BtHistoryEntry]:
        """List backtest snapshots for a lottery (read-only)."""
        self._resolve_lottery(lottery_id)
        stmt = (
            select(BtSnapshot)
            .where(BtSnapshot.lottery_id == lottery_id)
            .order_by(BtSnapshot.created_at.desc())
        )
        return [
            BtHistoryEntry(
                snapshot_id=r.id,
                lottery_id=r.lottery_id,
                strategy_id=r.strategy_id,
                fingerprint=r.fingerprint,
                version=r.version,
                status=r.status,
                created_at=r.created_at.isoformat(),
            )
            for r in self._session.execute(stmt).scalars().all()
        ]

    def results(self, lottery_id: int, snapshot_id: int | None = None) -> dict[str, Any]:
        """Return full result payload (read-only)."""
        self._resolve_lottery(lottery_id)
        if snapshot_id is not None:
            snap = self._session.get(BtSnapshot, snapshot_id)
            if snap is None or snap.lottery_id != lottery_id:
                raise NotFoundError(f"snapshot {snapshot_id} not found for lottery {lottery_id}")
        else:
            stmt = (
                select(BtSnapshot)
                .where(BtSnapshot.lottery_id == lottery_id, BtSnapshot.status == "active")
                .order_by(BtSnapshot.created_at.desc())
                .limit(1)
            )
            snap = self._session.execute(stmt).scalar_one_or_none()
            if snap is None:
                raise NotFoundError(f"no active backtest for lottery {lottery_id}")
        key = ("bt:results", snap.id)
        cached = _BT_CACHE.get(key)
        if cached is not None:
            return cached  # type: ignore[return-value]
        res = self._session.execute(
            select(BtResult).where(BtResult.snapshot_id == snap.id)
        ).scalar_one_or_none()
        if res is None:
            raise NotFoundError(f"no result for snapshot {snap.id}")
        payload = {
            "snapshot_id": snap.id,
            "lottery_id": snap.lottery_id,
            "strategy_id": snap.strategy_id,
            "fingerprint": snap.fingerprint,
            "version": snap.version,
            "status": snap.status,
            "aggregate_metrics": json.loads(res.aggregate_metrics_json),
            "window_history": json.loads(res.window_history_json),
        }
        _BT_CACHE.set(key, payload)
        return payload

    def _resolve_lottery(self, lottery_id: int) -> None:
        from backend.app.models.lottery import Lottery

        if self._session.get(Lottery, lottery_id) is None:
            raise NotFoundError(f"lottery {lottery_id} does not exist")

    def _fetch_draws(self, lottery_id: int) -> list[Draw]:
        stmt = (
            select(DrawModel)
            .where(DrawModel.lottery_id == lottery_id, DrawModel.is_deleted.is_(False))
            .order_by(DrawModel.draw_date)
            .options(selectinload(DrawModel.numbers), selectinload(DrawModel.super_number))
        )
        result: list[Draw] = []
        for d in self._session.execute(stmt).scalars().all():
            nums = tuple(sorted(dn.number for dn in d.numbers))
            super_num = d.super_number.value if d.super_number else None
            result.append(
                Draw(id=d.id, draw_date=d.draw_date, numbers=nums, super_number=super_num)
            )
        return result


def _make_strategy(strategy_id: str) -> Any:
    """Create a strategy from strategy_id (module-level builder, T-S3-01).

    Uses the module-level ``StaticStrategy`` (picklable across process
    pools); real ML/DL adapters arrive in later phases.
    """

    if strategy_id.startswith(("ml-", "dl-")):
        return StaticStrategy(strategy_id)
    raise BtRunError(f"unknown strategy prefix: {strategy_id!r}")
