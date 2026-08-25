"""R1 RED — stage failure aborts cleanly: PIPE_STAGE_FAILED names the stage."""

from __future__ import annotations

import pytest
from sqlalchemy.orm import Session


@pytest.fixture
def fail_features(monkeypatch: pytest.MonkeyPatch) -> None:
    """Force the features stage service to raise."""
    from backend.app.services.feature_engine_service import FeatureEngineService

    def failing(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("features exploded")

    monkeypatch.setattr(FeatureEngineService, "generate", staticmethod(failing))


def test_features_failure_aborts_before_gen(db: Session, pipeline_db: int, fail_features: None) -> None:
    """A features-stage failure aborts the chain before generation runs."""
    from backend.app.models.gen_snapshot import GenSnapshot
    from backend.app.models.stat_snapshot import StatSnapshot
    from backend.app.services.pipeline_service import PipelineService, PipelineServiceError

    with pytest.raises(PipelineServiceError) as excinfo:
        PipelineService(db).run(lottery_id=pipeline_db, count=2, seed=7)

    error = excinfo.value
    assert error.code == PipelineServiceError.PIPE_STAGE_FAILED
    assert "features" in str(error)

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
    db: Session, pipeline_db: int, fail_features: None
) -> None:
    """The failed report entry carries the originating service error code."""
    """R3: the failed entry carries its error code on the attached report."""
    from backend.app.services.pipeline_service import PipelineService, PipelineServiceError

    with pytest.raises(PipelineServiceError) as excinfo:
        PipelineService(db).run(lottery_id=pipeline_db, count=1, seed=1)

    report = getattr(excinfo.value, "stages", [])
    failed = [s for s in report if s.status == "failed"]
    assert len(failed) == 1
    assert failed[0].name == "features"
    assert failed[0].error_code == PipelineServiceError.PIPE_STAGE_FAILED


def test_gen_succeeds_without_active_meta_selection(db: Session, pipeline_db: int) -> None:
    """Gen completes successfully using deterministic seed fallback when no MetaSelection exists."""
    from backend.app.models.gen_snapshot import GenSnapshot
    from backend.app.models.meta_selection import MetaSelection
    from backend.app.services.pipeline_service import PipelineService

    # Ensure no MetaSelection exists
    db.query(MetaSelection).filter(MetaSelection.lottery_id == pipeline_db).delete()
    db.flush()

    outcome = PipelineService(db).run(lottery_id=pipeline_db, count=2, seed=7)

    # Gen completed successfully
    gen_stage = next(s for s in outcome.stages if s.name == "gen")
    assert gen_stage.status == "completed"
    assert outcome.result is not None
    assert len(outcome.result.combinations) == 2

    # A GenSnapshot was created with selection_id=0 (fallback)
    gen_snapshot = db.query(GenSnapshot).filter(GenSnapshot.lottery_id == pipeline_db).first()
    assert gen_snapshot is not None
    assert gen_snapshot.selection_id == 0
