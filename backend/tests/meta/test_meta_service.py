"""Tests for meta.meta_service — MetaService orchestration (META-001–META-012).

Spec refs: META-001 (weighted scoring), META-003 (context), META-004 (failed run exclusion),
META-005 (ranking), META-006 (selection), META-007 (idempotency), META-012 (lottery isolation).
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from backend.app.models.bt_result import BtResult
from backend.app.models.bt_snapshot import BtSnapshot
from backend.app.models.lottery import Lottery
from backend.app.services.errors import MetaServiceError
from backend.app.services.meta_service import MetaService


@pytest.fixture
def seeded_lottery(db) -> Lottery:
    lottery = Lottery(
        id=1,
        code="META",
        name="Meta Lottery",
        country="ES",
        min_number=1,
        max_number=49,
        numbers_to_select=6,
    )
    db.add(lottery)
    db.commit()
    return lottery


@pytest.fixture
def service(db) -> MetaService:
    return MetaService(db)


def _seed_bt(db, strategy_id: str, metrics: dict) -> BtSnapshot:
    snap = BtSnapshot(
        lottery_id=1,
        strategy_id=strategy_id,
        fingerprint=f"fp-{strategy_id}",
        version="1",
        status="active",
        config_json="{}",
    )
    db.add(snap)
    db.flush()
    db.add(
        BtResult(
            snapshot_id=snap.id,
            aggregate_metrics_json=__import__("json").dumps(metrics),
            window_history_json="[]",
        )
    )
    db.flush()
    return snap


def _seed_ml(db, model_set: str, metrics: dict) -> None:
    from backend.app.models.ml_metric import MlMetric
    from backend.app.models.ml_snapshot import MlSnapshot

    snap = MlSnapshot(
        lottery_id=1,
        model_set=model_set,
        version="1",
        ml_generator_version="g1",
        checksum="c" * 64,
        input_fingerprint="i" + "f" * 63,
        cut=10,
        status="active",
        is_locked=False,
        draw_count=100,
        draws_from=1,
        draws_to=100,
    )
    db.add(snap)
    db.flush()
    for name, val in metrics.items():
        db.add(
            MlMetric(
                snapshot_id=snap.id,
                model_id=model_set,
                model_version="1",
                number=1,
                metric_name=name,
                value=val,
                params_json="{}",
            )
        )
    db.flush()


class TestRankErrors:
    """Test rank error paths."""

    def test_rank_raises_no_engine_data(self, service: MetaService) -> None:
        """META-004: META_NO_ENGINE_DATA when no engine snapshots exist."""
        with patch(
            "backend.app.services.meta_service.resolve_context_vector",
            side_effect=ValueError("No active engine snapshot found"),
        ):
            with pytest.raises(MetaServiceError) as exc_info:
                service.rank(lottery_id=1)
            assert exc_info.value.code == "META_NO_ENGINE_DATA"

    def test_rank_raises_weights_invalid(self, service: MetaService) -> None:
        """META-001: META_WEIGHTS_INVALID when weights sum to zero."""
        with pytest.raises(MetaServiceError) as exc_info:
            service.rank(lottery_id=1, weights={"hit_rate": 0.0, "average_matches": 0.0})
        assert exc_info.value.code == "META_WEIGHTS_INVALID"


class TestSelectErrors:
    """Test select error paths."""

    def test_select_raises_no_engine_data(self, service: MetaService) -> None:
        """META_NO_ENGINE_DATA when no engine snapshots exist."""
        with patch(
            "backend.app.services.meta_service.resolve_context_vector",
            side_effect=ValueError("No active engine snapshot found"),
        ):
            with pytest.raises(MetaServiceError) as exc_info:
                service.select(lottery_id=1)
            assert exc_info.value.code == "META_NO_ENGINE_DATA"

    def test_select_raises_ranking_not_found(self, db, seeded_lottery) -> None:
        from backend.app.meta.context import compute_context_hash, resolve_context_vector

        _seed_bt(db, "strat-a", {"hit_rate": 0.85})
        svc = MetaService(db)
        vector = resolve_context_vector(1, "backtesting", db)
        ctx_hash = compute_context_hash(vector)
        with pytest.raises(MetaServiceError) as exc_info:
            svc.select(lottery_id=1, context_hash=ctx_hash)
        assert exc_info.value.code == "META_RANKING_NOT_FOUND"

    def test_select_raises_top_k_invalid(self, service: MetaService) -> None:
        """META_TOP_K_INVALID when top_k < 1."""
        with pytest.raises(MetaServiceError) as exc_info:
            service.select(lottery_id=1, top_k=0)
        assert exc_info.value.code == "META_TOP_K_INVALID"

    def test_select_raises_top_k_over_20(self, service: MetaService) -> None:
        """META_TOP_K_INVALID when top_k > 20."""
        with pytest.raises(MetaServiceError) as exc_info:
            service.select(lottery_id=1, top_k=21)
        assert exc_info.value.code == "META_TOP_K_INVALID"


class TestRankHappyPath:
    """rank() happy path against the real migrated DB (T-S3-05 regression)."""

    def test_rank_persists_active_ranking(self, db, seeded_lottery) -> None:
        _seed_bt(
            db, "strat-a", {"hit_rate": 0.85, "average_matches": 4.2, "consistency_score": 0.7}
        )
        _seed_bt(
            db, "strat-b", {"hit_rate": 0.75, "average_matches": 3.8, "consistency_score": 0.8}
        )
        db.commit()

        svc = MetaService(db)
        result = svc.rank(lottery_id=1)
        assert result.status == "active"
        assert result.lottery_id == 1
        assert result.context_hash
        assert len(result.entries) == 2
        assert result.entries[0]["model_id"].startswith("bt-strat-a-")
        assert result.entries[0]["score"] >= result.entries[1]["score"]

        stored = svc._store.get_rankings(1, result.context_hash)
        assert len(stored) == 1
        assert stored[0].status == "active"
        assert stored[0].fingerprint == result.fingerprint

    def test_rank_is_idempotent_by_fingerprint(self, db, seeded_lottery) -> None:
        _seed_bt(db, "strat-a", {"hit_rate": 0.85})
        db.commit()

        svc = MetaService(db)
        first = svc.rank(lottery_id=1)
        second = svc.rank(lottery_id=1)
        assert second.ranking_id == first.ranking_id
        assert second.fingerprint == first.fingerprint
        assert second.entries == []

    def test_rank_reads_ml_metrics(self, db, seeded_lottery) -> None:
        _seed_ml(db, "rf", {"precision": 0.8, "recall": 0.7})
        db.commit()

        svc = MetaService(db)
        result = svc.rank(lottery_id=1, engine_types=["ml"])
        assert len(result.entries) == 1
        assert result.entries[0]["model_id"].startswith("ml-rf-")
        assert result.entries[0]["score"] >= 0


class TestSelectHappyPath:
    def _seed_ranking(self, db) -> None:
        _seed_bt(db, "strat-a", {"hit_rate": 0.85})
        _seed_bt(db, "strat-b", {"hit_rate": 0.75})
        db.commit()
        svc = MetaService(db)
        svc.rank(lottery_id=1)

    def test_select_persists_active_selection(self, db, seeded_lottery) -> None:
        self._seed_ranking(db)
        svc = MetaService(db)
        result = svc.select(lottery_id=1, top_k=1)
        assert result.status == "active"
        assert result.lottery_id == 1
        assert result.entries[0]["rank"] == 1

        stored = svc._store.get_selections(1, result.context_hash)
        assert len(stored) == 1
        assert stored[0].status == "active"

    def test_select_min_score_filters(self, db, seeded_lottery) -> None:
        self._seed_ranking(db)
        svc = MetaService(db)
        result = svc.select(lottery_id=1, min_score=0.9)
        assert len(result.entries) < 2

    def test_select_is_idempotent_by_fingerprint(self, db, seeded_lottery) -> None:
        self._seed_ranking(db)
        svc = MetaService(db)
        first = svc.select(lottery_id=1, top_k=1)
        second = svc.select(lottery_id=1, top_k=1)
        assert second.selection_id == first.selection_id
        assert second.fingerprint == first.fingerprint
        assert second.entries == []


class TestGetHappyPath:
    def test_get_ranking_returns_snapshot(self, db, seeded_lottery) -> None:
        svc = MetaService(db)
        from backend.app.meta.snapshot_store import MetaSnapshotStore

        store = MetaSnapshotStore(db)
        store.create_active_ranking(
            lottery_id=1,
            context_hash="ctx-hash",
            version="1",
            fingerprint="fp-r1",
            entries=[
                {"model_id": "bt-strat-a-1", "engine_type": "backtesting", "score": 0.85},
            ],
            config_json={"weights": {}},
        )
        db.commit()

        snapshot = svc.get_ranking(1, context_hash="ctx-hash")
        assert snapshot.lottery_id == 1
        assert snapshot.context_hash == "ctx-hash"
        assert len(snapshot.rankings) == 1
        assert snapshot.rankings[0]["status"] == "active"

    def test_get_ranking_infers_context_hash_from_first(self, db, seeded_lottery) -> None:
        svc = MetaService(db)
        from backend.app.meta.snapshot_store import MetaSnapshotStore

        store = MetaSnapshotStore(db)
        store.create_active_ranking(
            lottery_id=1,
            context_hash="ctx-hash",
            version="1",
            fingerprint="fp-r1",
            entries=[],
            config_json={},
        )
        db.commit()

        snapshot = svc.get_ranking(1)
        assert snapshot.context_hash == "ctx-hash"

    def test_get_selection_returns_snapshot(self, db, seeded_lottery) -> None:
        svc = MetaService(db)
        from backend.app.meta.snapshot_store import MetaSnapshotStore

        store = MetaSnapshotStore(db)
        ranking_id = store.create_active_ranking(
            lottery_id=1,
            context_hash="ctx-hash",
            version="1",
            fingerprint="fp-r1",
            entries=[],
            config_json={},
        )
        store.create_active_selection(
            lottery_id=1,
            context_hash="ctx-hash",
            version="1",
            fingerprint="fp-s1",
            ranking_id=ranking_id,
            entries=[
                {"model_id": "bt-strat-a-1", "engine_type": "backtesting", "rank": 1, "score": 0.85}
            ],
            config_json={},
        )
        db.commit()

        snapshot = svc.get_selection(1, context_hash="ctx-hash")
        assert snapshot.lottery_id == 1
        assert snapshot.context_hash == "ctx-hash"
        assert len(snapshot.selections) == 1
        assert snapshot.selections[0]["status"] == "active"

    def test_get_selection_infers_context_hash_from_first(self, db, seeded_lottery) -> None:
        svc = MetaService(db)
        from backend.app.meta.snapshot_store import MetaSnapshotStore

        store = MetaSnapshotStore(db)
        ranking_id = store.create_active_ranking(
            lottery_id=1,
            context_hash="ctx-hash",
            version="1",
            fingerprint="fp-r1",
            entries=[],
            config_json={},
        )
        store.create_active_selection(
            lottery_id=1,
            context_hash="ctx-hash",
            version="1",
            fingerprint="fp-s1",
            ranking_id=ranking_id,
            entries=[],
            config_json={},
        )
        db.commit()

        snapshot = svc.get_selection(1)
        assert snapshot.context_hash == "ctx-hash"


def test_rank_refreshes_created_at_on_idempotent_return(db, seeded_lottery, service):
    """Regression (D8 healing): a second rank() for an unchanged context must
    refresh the ranking created_at so it is not perpetually 'stale' vs a newer
    bt_snapshot. Previously the idempotent return kept the old timestamp, which
    made pipeline_service._ranking_stale report stale forever after bt re-ran
    (PIPE_STAGE_FAILED: ranking stale for backtest context after one rerank)."""
    from datetime import datetime

    from backend.app.models.bt_snapshot import BtSnapshot
    from backend.app.models.meta_ranking import MetaRanking

    _seed_bt(
        db,
        "s1",
        {"sharpe": 1.2, "win_rate": 0.5, "max_drawdown": 0.1, "profit_factor": 1.5},
    )
    r1 = service.rank(lottery_id=seeded_lottery.id)
    ranking_id = r1.ranking_id

    # Simulate a newer bt_snapshot (the exact condition that previously broke):
    # bt "re-ran" and produced a snapshot with a later created_at but identical
    # data, so the ranking fingerprint is unchanged (idempotent return path).
    mid = datetime.now()
    snap1 = db.query(BtSnapshot).filter_by(lottery_id=1).first()
    snap1.created_at = mid
    db.commit()

    # Force the existing ranking into the past to reproduce staleness.
    row = db.get(MetaRanking, ranking_id)
    row.created_at = datetime(2000, 1, 1)
    db.commit()

    r2 = service.rank(lottery_id=seeded_lottery.id)
    assert r2.ranking_id == ranking_id
    db.refresh(row)
    # The idempotent return must refresh created_at so it is no longer stale
    # vs the newer bt_snapshot (row.created_at is now, which is >= mid).
    assert row.created_at >= mid, (
        "rank() must refresh created_at so the ranking is not stale vs newest bt"
    )
