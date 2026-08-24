"""Numbers pipeline orchestrator service (S2, R1-R4).

Single entry point that executes the canonical chain
``stats → features(+probability) → ml → dl → bt → rank → select → gen``
in order (R1), heals missing/stale prerequisites by running exactly the
deficient stages (R2), reports per-stage status (R3), and stays
zero-side-effect on unchanged inputs via fingerprint reuse (R4).

Classification strategy: every stage service in the chain is fingerprint-
idempotent EXCEPT two — ``MlService.train`` always persists a new snapshot
version and ``BtSnapshotStore.create_active`` delete+recreates rows. Those
two stages are therefore *gated*: they are invoked only when their active
artifact is missing or a dependency wrote during this run; all other stages
are invoked unconditionally and classified by comparing the active-artifact
fingerprint before/after the call (design §S2, task 5.1).

bt-before-rank (D8): the ranking context is derived post-bt via
``resolve_context_vector(lottery, "backtesting")`` + ``compute_context_hash``
and passed explicitly to ``MetaService.select(context_hash=...)`` — retiring
the hardcoded ``meta_service.py:242`` coupling without touching META logic.
A stale active ranking (created_at ≤ newest active BtSnapshot) triggers
exactly ONE rerank attempt, then ``PIPE_STAGE_FAILED(rank)``.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.services.errors import PipelineServiceError

STAGE_ORDER: tuple[str, ...] = (
    "stats",
    "features",
    "ml",
    "dl",
    "bt",
    "rank",
    "select",
    "gen",
)

# Canonical backtest parameters for the chain (CLI bt-run defaults).
BT_STRATEGY_ID = "ml-core-5"

# Stage dependencies within the chain. ``stats`` proxies draw coverage: its
# checksum-based idempotency rewrites iff the imported draw set changed.
_DEPS: dict[str, tuple[str, ...]] = {
    "ml": ("stats", "features"),
    "bt": ("stats",),
}

# Stage services that are NOT no-op on identical inputs (see module docstring).
_GATED_STAGES: frozenset[str] = frozenset({"ml", "bt"})


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
    """Mutable per-run state (ctx hash + generator output)."""

    def __init__(self) -> None:
        self.context_hash: str | None = None
        self.gen_result: object | None = None


def derive_context_hash(db: Session, lottery_id: int) -> str:
    """Derive the backtesting context hash from the executed bt run (D8).

    Raises ``ValueError`` when no active BtSnapshot exists — the orchestrator
    only calls this after the bt stage has run or been reused.
    """
    from backend.app.meta.context import compute_context_hash, resolve_context_vector

    vector = resolve_context_vector(lottery_id, "backtesting", db)
    return compute_context_hash(vector)


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
            if name in ("rank", "select") and state.context_hash is None:
                state.context_hash = self._safe_context_hash(lottery_id)

            before = self._read_artifact(lottery_id, name, state.context_hash)

            if self._gated_skip(name, before, changed):
                report.append(
                    StageRecord(
                        name=name,
                        status="skipped",
                        snapshot_id=before.snapshot_id,
                        fingerprint=before.fingerprint,
                        detail="active artifact reused",
                    )
                )
                changed[name] = False
                continue

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

            after = self._read_artifact(lottery_id, name, state.context_hash)
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
        elif name == "ml":
            from backend.app.services.ml_service import MlService

            MlService(db, _MlDrawAdapter(db), _MlFeatureAdapter(db)).train(lottery_id)
        elif name == "dl":
            from backend.app.services.dl_service import DlService

            ml_draws = _MlDrawAdapter(db)
            ml_features = _MlFeatureAdapter(db)
            DlService(
                db,
                _DlDrawAdapter(ml_draws),
                _DlFeatureAdapter(ml_features),
            ).train(lottery_id)
        elif name == "bt":
            from backend.app.services.bt_service import BtService

            BtService(db).run(lottery_id=lottery_id, strategy_id=BT_STRATEGY_ID)
        elif name == "rank":
            self._run_rank(lottery_id, state)
        elif name == "select":
            from backend.app.services.meta_service import MetaService

            if state.context_hash is None:
                state.context_hash = derive_context_hash(db, lottery_id)
            MetaService(db).select(lottery_id=lottery_id, context_hash=state.context_hash)
        elif name == "gen":
            from backend.app.services.gen_service import GenService

            state.gen_result = GenService(db).generate(
                lottery_id=lottery_id, count=count, seed=seed
            )
        else:  # pragma: no cover - STAGE_ORDER is closed
            raise ValueError(f"unknown stage {name!r}")

    def _run_rank(self, lottery_id: int, state: _RunState) -> None:
        """Rank, then detect-and-rerank once against bt freshness (D8)."""
        from backend.app.services.meta_service import MetaService

        meta = MetaService(self._db)
        meta.rank(lottery_id=lottery_id)

        if state.context_hash is None:
            state.context_hash = derive_context_hash(self._db, lottery_id)

        if self._ranking_stale(lottery_id, state.context_hash):
            meta.rank(lottery_id=lottery_id)  # exactly ONE repair attempt (D8)
            if self._ranking_stale(lottery_id, state.context_hash):
                raise RuntimeError("ranking stale for backtest context after one rerank")

    def _ranking_stale(self, lottery_id: int, context_hash: str) -> bool:
        """True when no active ranking exists for ctx or it predates bt (D8)."""
        from backend.app.models.bt_snapshot import BtSnapshot
        from backend.app.models.meta_ranking import MetaRanking

        bt = (
            self._db.execute(
                select(BtSnapshot)
                .where(BtSnapshot.lottery_id == lottery_id, BtSnapshot.status == "active")
                .order_by(BtSnapshot.created_at.desc())
                .limit(1)
            )
            .scalars()
            .first()
        )
        ranking = (
            self._db.execute(
                select(MetaRanking)
                .where(
                    MetaRanking.lottery_id == lottery_id,
                    MetaRanking.context_hash == context_hash,
                    MetaRanking.status == "active",
                )
                .limit(1)
            )
            .scalars()
            .first()
        )
        if bt is None or ranking is None or bt.created_at is None or ranking.created_at is None:
            return True
        return _naive(ranking.created_at) <= _naive(bt.created_at)

    def _gated_skip(self, name: str, before: _Artifact, changed: dict[str, bool]) -> bool:
        """Gate non-idempotent writers on missing/stale artifacts (D12)."""
        if name not in _GATED_STAGES:
            return False
        if before.fingerprint is None:
            return False
        deps_changed = any(changed.get(dep, False) for dep in _DEPS.get(name, ()))
        return not deps_changed

    def _safe_context_hash(self, lottery_id: int) -> str | None:
        try:
            return derive_context_hash(self._db, lottery_id)
        except ValueError:
            return None

    # ------------------------------------------------------------------
    # Active artifact resolution (skip-vs-run classification)
    # ------------------------------------------------------------------

    def _read_artifact(self, lottery_id: int, stage: str, context_hash: str | None) -> _Artifact:
        """Return the active artifact reference for a stage (absent → empty)."""
        db = self._db
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
        if stage == "ml":
            from backend.app.ml.registry import MODEL_SET_CORE_5
            from backend.app.models.ml_snapshot import MlSnapshot

            row = self._latest(
                select(MlSnapshot)
                .where(
                    MlSnapshot.lottery_id == lottery_id,
                    MlSnapshot.model_set == MODEL_SET_CORE_5,
                    MlSnapshot.status == "active",
                )
                .order_by(MlSnapshot.version.desc())
            )
            return _Artifact(row.id if row else None, row.input_fingerprint if row else None)
        if stage == "dl":
            from backend.app.dl.registry import MODEL_SET_CORE_3
            from backend.app.models.dl_snapshot import DlSnapshot

            row = self._latest(
                select(DlSnapshot)
                .where(
                    DlSnapshot.lottery_id == lottery_id,
                    DlSnapshot.model_set == MODEL_SET_CORE_3,
                    DlSnapshot.status == "active",
                )
                .order_by(DlSnapshot.version.desc())
            )
            return _Artifact(row.id if row else None, row.input_fingerprint if row else None)
        if stage == "bt":
            from backend.app.models.bt_snapshot import BtSnapshot

            row = self._latest(
                select(BtSnapshot)
                .where(
                    BtSnapshot.lottery_id == lottery_id,
                    BtSnapshot.strategy_id == BT_STRATEGY_ID,
                    BtSnapshot.status == "active",
                )
                .order_by(BtSnapshot.created_at.desc())
            )
            return _Artifact(row.id if row else None, row.fingerprint if row else None)
        if stage == "rank":
            from backend.app.models.meta_ranking import MetaRanking

            if context_hash is None:
                return _Artifact()
            row = (
                db.execute(
                    select(MetaRanking)
                    .where(
                        MetaRanking.lottery_id == lottery_id,
                        MetaRanking.context_hash == context_hash,
                        MetaRanking.status == "active",
                    )
                    .limit(1)
                )
                .scalars()
                .first()
            )
            return _Artifact(row.id if row else None, row.fingerprint if row else None)
        if stage == "select":
            from backend.app.models.meta_selection import MetaSelection

            if context_hash is None:
                return _Artifact()
            row = (
                db.execute(
                    select(MetaSelection)
                    .where(
                        MetaSelection.lottery_id == lottery_id,
                        MetaSelection.context_hash == context_hash,
                        MetaSelection.status == "active",
                    )
                    .limit(1)
                )
                .scalars()
                .first()
            )
            return _Artifact(row.id if row else None, row.fingerprint if row else None)
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


def _naive(value: object) -> object:
    """Strip tzinfo so SQLite-loaded datetimes compare uniformly."""
    return value.replace(tzinfo=None) if getattr(value, "tzinfo", None) else value


# ----------------------------------------------------------------------
# Provider adapters (mirror api/v1/ml.py + cli.py composition seams)
# ----------------------------------------------------------------------


class _MlDrawAdapter:
    """Minimal ML DrawHistoryProvider adapter over the draw tables."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def iter_draws(self, lottery_id: int, *, after_draw_number: int | None = None):
        """Yield ML ``DrawRow`` carriers in ascending draw-number order."""
        from sqlalchemy import select

        from backend.app.ml.providers import DrawRow
        from backend.app.models.draw import Draw
        from backend.app.models.draw_number import DrawNumber

        stmt = select(Draw).where(Draw.lottery_id == lottery_id).order_by(Draw.draw_number)
        if after_draw_number is not None:
            stmt = stmt.where(Draw.draw_number > after_draw_number)
        for draw in self._session.execute(stmt).scalars().all():
            nums_stmt = (
                select(DrawNumber.number)
                .where(DrawNumber.draw_id == draw.id)
                .order_by(DrawNumber.position)
            )
            numbers = tuple(self._session.execute(nums_stmt).scalars().all())
            yield DrawRow(draw_number=draw.draw_number, numbers=numbers)


class _MlFeatureAdapter:
    """Minimal ML FeatureSnapshotProvider adapter over feature_values."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def active_snapshot_id(self, lottery_id: int) -> int | None:
        """Return the newest active ML snapshot id for the lottery, if any."""
        from sqlalchemy import select

        from backend.app.models.feature_snapshot import FeatureSnapshot

        stmt = (
            select(FeatureSnapshot)
            .where(
                FeatureSnapshot.lottery_id == lottery_id,
                FeatureSnapshot.status == "active",
            )
            .order_by(FeatureSnapshot.version.desc())
            .limit(1)
        )
        snap = self._session.execute(stmt).scalar_one_or_none()
        return snap.id if snap is not None else None

    def feature_rows(self, snapshot_id: int):
        """Yield ML feature-value carriers ordered by draw then feature."""
        from sqlalchemy import select

        from backend.app.ml.feature_reader import FeatureValueRow
        from backend.app.models.feature_value import FeatureValue

        stmt = (
            select(FeatureValue)
            .where(FeatureValue.snapshot_id == snapshot_id)
            .order_by(FeatureValue.draw_number, FeatureValue.feature_id)
        )
        for fv in self._session.execute(stmt).scalars().all():
            yield FeatureValueRow(
                feature_id=fv.feature_id,
                draw_number=fv.draw_number,
                value=float(fv.value),
            )


class _DlDrawAdapter:
    """Converts ML draw carriers to DL carriers at the composition root (DLE-13)."""

    def __init__(self, inner: _MlDrawAdapter) -> None:
        self._inner = inner

    def iter_draws(self, lottery_id: int, *, after_draw_number: int | None = None):
        """Yield DL ``DrawRow`` carriers in ascending draw-number order."""
        from backend.app.dl.providers import DrawRow

        for row in self._inner.iter_draws(lottery_id, after_draw_number=after_draw_number):
            yield DrawRow(draw_number=row.draw_number, numbers=tuple(row.numbers))


class _DlFeatureAdapter:
    """Converts ML feature carriers to DL carriers at the composition root (DLE-13)."""

    def __init__(self, inner: _MlFeatureAdapter) -> None:
        self._inner = inner

    def active_snapshot_id(self, lottery_id: int) -> int | None:
        """Return the newest active DL snapshot id for the lottery, if any."""
        return self._inner.active_snapshot_id(lottery_id)

    def feature_rows(self, snapshot_id: int):
        """Yield DL feature carriers ordered by draw then feature."""
        from backend.app.dl.providers import FeatureRow

        for row in self._inner.feature_rows(snapshot_id):
            yield FeatureRow(
                feature_id=row.feature_id,
                draw_number=row.draw_number,
                value=float(row.value),
            )
