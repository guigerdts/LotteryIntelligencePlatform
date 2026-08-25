"""Numbers pipeline orchestrator service (S2, R1-R4).

Single entry point that executes the canonical chain
``stats → features(+probability) → gen``
in order (R1), heals missing/stale prerequisites by running exactly the
deficient stages (R2), reports per-stage status (R3), and stays
zero-side-effect on unchanged inputs via fingerprint reuse (R4).

The features stage covers both feature and probability snapshots (D9).
Stages ml, dl, bt, rank, and select have been removed from the numbers
path; backtesting retains its own independent pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.services.errors import PipelineServiceError

STAGE_ORDER: tuple[str, ...] = (
    "stats",
    "features",
    "gen",
)


@dataclass(frozen=True)
class StageRecord:
    """One ordered entry of the per-stage report (R3)."""

    name: str
    status: str
    snapshot_id: int | None = None
    fingerprint: str | None = None
    error_code: str | None = None
    detail: str = ""


@dataclass(frozen=True)
class PipelineRunOutcome:
    """Result of one orchestrator run: ordered report plus gen output."""

    stages: list[StageRecord] = field(default_factory=list)
    result: object | None = None


@dataclass(frozen=True)
class _Artifact:
    """Active artifact reference for one stage (None when absent)."""

    snapshot_id: int | None = None
    fingerprint: str | None = None


class _RunState:
    """Mutable per-run state (generator output)."""

    def __init__(self) -> None:
        self.gen_result: object | None = None


class PipelineService:
    """Orchestrates the canonical eight-stage numbers chain (R1-R4)."""

    def __init__(self, session: Session) -> None:
        self._db = session

    # ------------------------------------------------------------------
    # Entry point
    # ------------------------------------------------------------------

    def run(self, *, lottery_id: int, count: int | None = None, seed: int | None = None):
        """Execute the full chain once and return report + generation (R1/R3)."""
        from backend.app.services.gen_service import GenerationResult  # noqa: F401

        report: list[StageRecord] = []
        changed: dict[str, bool] = {}
        state = _RunState()

        for name in STAGE_ORDER:
            before = self._read_artifact(lottery_id, name)

            try:
                self._execute_stage(name, lottery_id, count, seed, state)
            except Exception as exc:
                failed = StageRecord(
                    name=name,
                    status="failed",
                    error_code=PipelineServiceError.PIPE_STAGE_FAILED,
                    detail=str(exc),
                )
                report.append(failed)
                error = PipelineServiceError(
                    PipelineServiceError.PIPE_STAGE_FAILED,
                    f"stage '{name}' failed: {exc}",
                )
                error.stages = report  # R3: failed entry travels with the error
                raise error from exc

            after = self._read_artifact(lottery_id, name)
            wrote = after != before and after.fingerprint is not None
            report.append(
                StageRecord(
                    name=name,
                    status="completed" if wrote else "skipped",
                    snapshot_id=after.snapshot_id,
                    fingerprint=after.fingerprint,
                    detail="new artifact persisted" if wrote else "active artifact reused",
                )
            )
            changed[name] = wrote

        return PipelineRunOutcome(stages=report, result=state.gen_result)

    # ------------------------------------------------------------------
    # Stage execution
    # ------------------------------------------------------------------

    def _execute_stage(
        self,
        name: str,
        lottery_id: int,
        count: int | None,
        seed: int | None,
        state: _RunState,
    ) -> None:
        """Invoke the stage service exactly as CLI handlers do."""
        db = self._db
        if name == "stats":
            from backend.app.services.statistics_service import StatisticsService

            StatisticsService(db).generate(lottery_id=lottery_id)
        elif name == "features":
            # D9: probability is folded into the features stage — gen's
            # distribution loader needs an active prob snapshot downstream.
            from backend.app.services.feature_engine_service import FeatureEngineService
            from backend.app.services.probability_service import ProbabilityService

            FeatureEngineService(db).generate(lottery_id=lottery_id)
            ProbabilityService(db).generate(lottery_id=lottery_id)
        elif name == "gen":
            from backend.app.services.gen_service import GenService

            state.gen_result = GenService(db).generate(
                lottery_id=lottery_id, count=count, seed=seed
            )
        else:  # pragma: no cover - STAGE_ORDER is closed
            raise ValueError(f"unknown stage {name!r}")

    # ------------------------------------------------------------------
    # Active artifact resolution (skip-vs-run classification)
    # ------------------------------------------------------------------

    def _read_artifact(self, lottery_id: int, stage: str) -> _Artifact:
        """Return the active artifact reference for a stage (absent → empty)."""
        if stage == "stats":
            from backend.app.models.stat_snapshot import StatSnapshot

            row = self._latest(
                select(StatSnapshot)
                .where(
                    StatSnapshot.lottery_id == lottery_id,
                    StatSnapshot.metric_set == "core",
                    StatSnapshot.status == "active",
                )
                .order_by(StatSnapshot.version.desc())
            )
            return _Artifact(row.id if row else None, row.checksum if row else None)
        if stage == "features":
            from backend.app.models.feature_snapshot import FeatureSnapshot
            from backend.app.models.prob_snapshot import ProbSnapshot

            row = self._latest(
                select(FeatureSnapshot)
                .where(
                    FeatureSnapshot.lottery_id == lottery_id,
                    FeatureSnapshot.feature_set == "core",
                    FeatureSnapshot.status == "active",
                )
                .order_by(FeatureSnapshot.version.desc())
            )
            prob = self._latest(
                select(ProbSnapshot)
                .where(
                    ProbSnapshot.lottery_id == lottery_id,
                    ProbSnapshot.model_set == "core",
                    ProbSnapshot.status == "active",
                )
                .order_by(ProbSnapshot.version.desc())
            )
            # The features stage covers both writers (D9); either rewriting
            # counts as a write, so the fingerprint folds both references.
            fp = None
            parts = [
                getattr(row, "input_fingerprint", None),
                getattr(prob, "input_fingerprint", None),
            ]
            if all(parts):
                fp = f"{parts[0]}|{parts[1]}"
            ids = [r.id for r in (row, prob) if r is not None]
            return _Artifact(ids[0] if ids else None, fp)
        if stage == "gen":
            from backend.app.models.gen_snapshot import GenSnapshot

            row = self._latest(
                select(GenSnapshot)
                .where(GenSnapshot.lottery_id == lottery_id, GenSnapshot.status == "active")
                .order_by(GenSnapshot.id.desc())
            )
            return _Artifact(row.id if row else None, row.fingerprint if row else None)
        raise ValueError(f"unknown stage {stage!r}")  # pragma: no cover

    def _latest(self, stmt):  # noqa: ANN001 - private helper over a typed select
        """Return the single row produced by a typed select statement."""
        return self._db.execute(stmt.limit(1)).scalars().first()
