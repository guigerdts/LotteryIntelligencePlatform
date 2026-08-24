"""R1 RED — stage failure aborts cleanly: PIPE_STAGE_FAILED names the stage."""

from __future__ import annotations

import pytest
from sqlalchemy.orm import Session


@pytest.fixture
def fail_rank(monkeypatch: pytest.MonkeyPatch) -> None:
    """Force the rank stage service to raise."""
    from backend.app.services.meta_service import MetaService

    def failing(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("rank exploded")

    monkeypatch.setattr(MetaService, "rank", staticmethod(failing))


def test_rank_failure_aborts_before_gen(db: Session, pipeline_db: int, fail_rank: None) -> None:
    """A rank-stage failure aborts the chain before generation runs."""
    from backend.app.models.gen_snapshot import GenSnapshot
    from backend.app.models.stat_snapshot import StatSnapshot
    from backend.app.services.pipeline_service import PipelineService, PipelineServiceError

    with pytest.raises(PipelineServiceError) as excinfo:
        PipelineService(db).run(lottery_id=pipeline_db, count=2, seed=7)

    error = excinfo.value
    assert error.code == PipelineServiceError.PIPE_STAGE_FAILED
    assert "rank" in str(error)

    # gen never ran; earlier artifacts persist.
    assert db.query(GenSnapshot).filter(GenSnapshot.lottery_id == pipeline_db).count() == 0
    active_stats = (
        db.query(StatSnapshot)
        .filter(
            StatSnapshot.lottery_id == pipeline_db,
            StatSnapshot.status == "active",
        )
        .count()
    )
    assert active_stats == 1


def test_failure_report_entry_carries_error_code(
    db: Session, pipeline_db: int, fail_rank: None
) -> None:
    """The failed report entry carries the originating service error code."""
    """R3: the failed entry carries its error code on the attached report."""
    from backend.app.services.pipeline_service import PipelineService, PipelineServiceError

    with pytest.raises(PipelineServiceError) as excinfo:
        PipelineService(db).run(lottery_id=pipeline_db, count=1, seed=1)

    report = getattr(excinfo.value, "stages", [])
    failed = [s for s in report if s.status == "failed"]
    assert len(failed) == 1
    assert failed[0].name == "rank"
    assert failed[0].error_code == PipelineServiceError.PIPE_STAGE_FAILED
