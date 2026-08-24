"""R4 RED — fingerprint idempotency: identical double run writes nothing new."""

from __future__ import annotations

from sqlalchemy.orm import Session

from tests.pipeline.conftest import artifact_versions


def test_double_run_identical_payload_zero_new_versions(db: Session, pipeline_db: int) -> None:
    """Running twice with identical payloads reuses snapshots and creates zero new versions."""
    from backend.app.services.pipeline_service import PipelineService

    first = PipelineService(db).run(lottery_id=pipeline_db, count=2, seed=7)
    assert first.result is not None
    versions_after_first = artifact_versions(db, pipeline_db)

    second = PipelineService(db).run(lottery_id=pipeline_db, count=2, seed=7)
    assert second.result is not None

    # Identical payloads (result echo).
    assert second.result.snapshot_id == first.result.snapshot_id
    assert second.result.fingerprint == first.result.fingerprint
    assert len(second.result.combinations) == len(first.result.combinations)
    assert [
        (c.position, c.numbers, c.super_number, c.score) for c in second.result.combinations
    ] == [(c.position, c.numbers, c.super_number, c.score) for c in first.result.combinations]

    # Zero side-effect writes: no store gained rows (R4).
    assert artifact_versions(db, pipeline_db) == versions_after_first

    # Every stage reports reuse on the warm run.
    assert all(s.status == "skipped" for s in second.stages)


def test_different_count_is_a_new_generation_not_a_reuse(db: Session, pipeline_db: int) -> None:
    """A different count produces a new generation instead of reusing the old one."""
    """Triangulation: changed request inputs must NOT be classified as reuse."""
    from backend.app.services.pipeline_service import PipelineService

    PipelineService(db).run(lottery_id=pipeline_db, count=2, seed=7)
    other = PipelineService(db).run(lottery_id=pipeline_db, count=3, seed=7)

    gen_stage = next(s for s in other.stages if s.name == "gen")
    assert gen_stage.status == "completed"
    assert other.result is not None
    assert len(other.result.combinations) == 3
