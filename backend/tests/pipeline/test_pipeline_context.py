"""D8 RED — bt-before-rank context derivation and stale-ranking detect-and-rerank."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.orm import Session


def test_rank_receives_context_derived_from_executed_bt(
    db: Session, pipeline_db: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ranking receives the context hash derived from the executed backtest identity."""
    """rank/select ctx must come from the executed bt run — never a hardcoded hash."""
    from backend.app.meta.context import compute_context_hash, resolve_context_vector
    from backend.app.services.meta_service import MetaService
    from backend.app.services.pipeline_service import PipelineService

    captured: dict[str, str | None] = {}
    original_select = MetaService.select

    def spying_select(self: object, **kwargs: object) -> object:
        captured["context_hash"] = kwargs.get("context_hash")  # type: ignore[assignment]
        return original_select(self, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(MetaService, "select", spying_select)

    outcome = PipelineService(db).run(lottery_id=pipeline_db, count=2, seed=5)

    assert outcome.result is not None
    expected = compute_context_hash(resolve_context_vector(pipeline_db, "backtesting", db))
    assert captured["context_hash"] == expected


def test_stale_ranking_triggers_exactly_one_rerank_then_fails(
    db: Session, pipeline_db: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    """One stale-ranking rerank is attempted; a second failure aborts the chain."""
    from backend.app.models.bt_snapshot import BtSnapshot
    from backend.app.models.meta_ranking import MetaRanking
    from backend.app.services.meta_service import MetaService
    from backend.app.services.pipeline_service import PipelineService, PipelineServiceError

    # First run builds a consistent chain.
    PipelineService(db).run(lottery_id=pipeline_db, count=2, seed=5)

    # Age the active ranking behind the newest active BtSnapshot (D8 staleness).
    ranking = (
        db.query(MetaRanking)
        .filter(
            MetaRanking.lottery_id == pipeline_db,
            MetaRanking.status == "active",
        )
        .one()
    )
    # SQLite-loaded datetimes are naive; age with a naive UTC stamp. Commit
    # so later service-internal rollbacks cannot discard the aging.
    ranking.created_at = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=1)
    db.commit()
    newest_bt = (
        db.query(BtSnapshot)
        .filter(BtSnapshot.lottery_id == pipeline_db, BtSnapshot.status == "active")
        .order_by(BtSnapshot.created_at.desc())
        .first()
    )
    assert newest_bt is not None
    assert ranking.created_at <= newest_bt.created_at

    rank_calls: list[int] = []
    original_rank = MetaService.rank

    def counting_rank(self: object, *args: object, **kwargs: object) -> object:
        rank_calls.append(1)
        return original_rank(self, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(MetaService, "rank", counting_rank)

    raised = None
    try:
        PipelineService(db).run(lottery_id=pipeline_db, count=2, seed=5)
    except PipelineServiceError as exc:
        raised = exc

    assert raised is not None
    assert raised.code == PipelineServiceError.PIPE_STAGE_FAILED
    assert "rank" in str(raised)
    # Initial attempt + exactly ONE repair attempt; no rerun loop.
    assert len(rank_calls) == 2
