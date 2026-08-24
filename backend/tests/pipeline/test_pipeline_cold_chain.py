"""R1/R3 RED — cold chain: one call runs all eight stages in canonical order."""

from __future__ import annotations

from sqlalchemy.orm import Session

from tests.pipeline.conftest import STAGE_ORDER


def test_cold_chain_runs_all_eight_stages_in_canonical_order(
    db: Session, pipeline_db: int, stage_recorder: list[tuple[str, str]], run_chain
) -> None:
    """An empty store runs all eight stages exactly once in canonical order."""
    outcome = run_chain(pipeline_db, count=2, seed=7)

    names = [stage.name for stage in outcome.stages]
    assert names == list(STAGE_ORDER)

    # All eight completed with artifact references where produced.
    for entry in outcome.stages:
        assert entry.status == "completed", f"{entry.name}: {entry.detail}"
        assert entry.fingerprint, f"{entry.name} missing fingerprint ref"
        assert entry.snapshot_id is not None, f"{entry.name} missing snapshot ref"

    # Execution order matches the canonical chain (unique start events).
    starts = [stage for stage, ev in stage_recorder if ev == "start"]
    unique_starts = list(dict.fromkeys(starts))
    assert unique_starts == list(STAGE_ORDER)

    # bt strictly before rank (R1).
    assert stage_recorder.index(("bt", "end")) < stage_recorder.index(("rank", "start"))

    # Final combinations returned.
    assert outcome.result is not None
    assert len(outcome.result.combinations) == 2
    for combo in outcome.result.combinations:
        assert combo.super_number is not None
        assert combo.score is not None


def test_cold_chain_report_entries_are_ordered_and_typed(
    db: Session, pipeline_db: int, run_chain
) -> None:
    """Every report entry carries the canonical name, status and detail fields."""
    outcome = run_chain(pipeline_db, count=1, seed=3)

    assert [s.name for s in outcome.stages] == list(STAGE_ORDER)
    allowed = {"skipped", "completed", "failed"}
    assert all(s.status in allowed for s in outcome.stages)
    assert outcome.stages[-1].name == "gen"
    assert outcome.result is not None
    assert outcome.result.snapshot_id == outcome.stages[-1].snapshot_id
