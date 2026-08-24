"""R2 RED — healing matrix: exact skip/run sets per partial-chain precondition."""

from __future__ import annotations

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.models.draw import Draw
from tests.pipeline.conftest import STAGE_ORDER, artifact_versions, clear_stages

ALL = set(STAGE_ORDER)

# (stages already done → expected run set for the next orchestrator call)
HEALING_ROWS: list[tuple[set[str], set[str]]] = [
    (set(), ALL),  # cold chain: everything runs
    ({"stats"}, ALL - {"stats"}),
    ({"stats", "features"}, ALL - {"stats", "features"}),
    # stats/features/bt current; ml/dl/rank/select/gen missing.
    ({"stats", "features", "bt"}, {"ml", "dl", "rank", "select", "gen"}),
    # everything but select/gen is current.
    ({"stats", "features", "ml", "dl", "bt", "rank"}, {"select", "gen"}),
]

ROW_IDS = [
    "cold",
    "stats-only",
    "stats-features",
    "thru-bt-missing-ml-dl",
    "thru-rank-missing-select-gen",
]


def _build_full_chain(db: Session, lottery_id: int) -> None:
    from backend.app.services.pipeline_service import PipelineService

    outcome = PipelineService(db).run(lottery_id=lottery_id, count=2, seed=11)
    assert outcome.result is not None


@pytest.mark.parametrize("keep,expected_run", HEALING_ROWS, ids=ROW_IDS)
def test_healing_matrix(
    db: Session, pipeline_db: int, keep: set[str], expected_run: set[str]
) -> None:
    """Each missing-prerequisite combination triggers exactly the expected repair stages."""
    _build_full_chain(db, pipeline_db)
    clear_stages(db, pipeline_db, keep)

    from backend.app.services.pipeline_service import PipelineService

    outcome = PipelineService(db).run(lottery_id=pipeline_db, count=2, seed=11)

    got_run = {s.name for s in outcome.stages if s.status == "completed"}
    got_skip = {s.name for s in outcome.stages if s.status == "skipped"}
    assert got_run == expected_run
    assert got_skip == ALL - expected_run
    assert outcome.result is not None


def test_fresh_draw_invalidates_coverage_stages_and_then_settles(
    db: Session, pipeline_db: int, add_fresh_draw
) -> None:
    """A fresh draw invalidates coverage stages; the rerun settles idempotently."""
    _build_full_chain(db, pipeline_db)

    # One newly imported draw invalidates draw-coverage fingerprints downstream.
    stmt = select(func.max(Draw.draw_number)).where(Draw.lottery_id == pipeline_db)
    next_number = int(db.execute(stmt).scalar()) + 1
    add_fresh_draw(pipeline_db, draw_number=next_number)

    from backend.app.services.pipeline_service import PipelineService

    outcome = PipelineService(db).run(lottery_id=pipeline_db, count=2, seed=11)
    rerun = {s.name for s in outcome.stages if s.status == "completed"}
    assert rerun == ALL, f"coverage-dependent stages must re-run, skipped={ALL - rerun}"
    assert outcome.result is not None

    # With NO new coverage, a further run leaves every stage untouched.
    before = artifact_versions(db, pipeline_db)
    outcome2 = PipelineService(db).run(lottery_id=pipeline_db, count=2, seed=11)
    assert all(s.status == "skipped" for s in outcome2.stages)
    assert artifact_versions(db, pipeline_db) == before
