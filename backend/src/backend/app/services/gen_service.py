"""GenService: orchestration of the Generator surface (GEN-001..GEN-013).

Composition root over the S1/S2 engine pieces. Owns:
- ``generate()`` — the selection→allocation→sampling→persist pipeline (GEN-001),
  with count validation (GEN-002), idempotency (GEN-008), seed derivation
  (GEN-009) and the full GEN-013 error taxonomy.
- ``get_combinations()`` / ``get_snapshots()`` — stored reads (GEN-010); they
  never recompute.
- ``update_snapshot()`` — lifecycle transition of a stored generator snapshot.

Boundaries: F5 is reused ONLY through ``generators.identity`` (GEN-015) —
``generation_seed``/``snapshot_fingerprint`` (GEN-008/GEN-009); F11/F12 is
consumed as the active selection + entry scores used as weights only — no
re-ranking, no re-scoring (GEN-016). Reads the
``prob_*``/``meta_*`` tables directly via SQLAlchemy (read-only); persists ONLY
``gen_*`` via :class:`GenSnapshotStore` (GEN-012).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.generators.allocation import SelectionEntry, allocate_count
from backend.app.generators.identity import generation_seed, snapshot_fingerprint
from backend.app.generators.sampling import WeightedPool, sample_combinations
from backend.app.generators.snapshot_store import GenSnapshotStore
from backend.app.generators.validation import validate_combination
from backend.app.generators.version import GENERATOR_VERSION
from backend.app.generators.weighting import build_weights
from backend.app.models.gen_snapshot import GenSnapshot
from backend.app.services.probability_service import _classify_coverage
from backend.app.repositories.stat_payload_repository import StatPayloadRepository
from backend.app.services.errors import GenServiceError
from backend.app.statistics.engine import frequency

DEFAULT_COUNT: int = 10
"""Default combination count when not provided (GEN-002)."""
MAX_COUNT: int = 100
"""Upper bound for the combination count (GEN-002)."""
MIN_COUNT: int = 1
"""Lower bound for the combination count (GEN-002)."""
SB_SPARSE_THRESHOLD: int = 32
"""Minimum SB observations before the empirical marginal is trusted (D2)."""


@dataclass(frozen=True)
class CombinationRow:
    """One stored combination: position, numbers, optional super_number and score."""

    position: int
    numbers: list[int]
    super_number: int | None
    score: float | None


@dataclass(frozen=True)
class GenerationResult:
    """Outcome of a ``generate()`` run — snapshot header plus its combinations."""

    snapshot_id: int
    lottery_id: int
    selection_id: int
    version: str
    status: str
    fingerprint: str
    seed: int
    count: int
    combinations: list[CombinationRow]


@dataclass(frozen=True)
class CombinationListResult:
    """Stored combinations of one generator snapshot (GEN-010 read)."""

    snapshot_id: int
    lottery_id: int
    combinations: list[CombinationRow]


@dataclass(frozen=True)
class SnapshotResult:
    """One stored generator snapshot header (GEN-010 read)."""

    snapshot_id: int
    lottery_id: int
    selection_id: int
    version: str
    status: str
    fingerprint: str
    created_at: str | None


@dataclass(frozen=True)
class SnapshotListResult:
    """All generator snapshots for a lottery (GEN-010 read)."""

    lottery_id: int
    snapshots: list[SnapshotResult]


class GenService:
    """Generator use cases over one DI session transaction (GEN-001..GEN-013)."""

    def __init__(self, session: Session) -> None:
        self._session = session
        self._store = GenSnapshotStore(session)

    # ------------------------------------------------------------------
    # Generation
    # ------------------------------------------------------------------

    def generate(
        self,
        *,
        lottery_id: int,
        count: int | None = None,
        seed: int | None = None,
        selection_id: int | None = None,
    ) -> GenerationResult:
        """Generate (or idempotently return) a lottery combination snapshot.

        Pipeline (GEN-001, GEN-009 remix): resolve the selection scope → validate
        count → load the F5 distribution → derive per-number weights from F5 ×
        cold-coverage boost (PM-08) → sample ``(combo, sb)`` pairs with
        ``isolated_rng`` (GEN-005, D1) → score each combo with its transparent
        mean sampling weight (R3/D3) → gate legality pre-persist (R1/D5) →
        fingerprint → persist a NEW active version atomically. The meta
        prediction-chain scores are NOT used (audit-proven zero effect). Same
        inputs reproduce the identical snapshot including Superbalotas and scores
        (GEN-008); a duplicate non-active fingerprint is a conflict (GEN-013).
        """
        lottery = self._resolve_lottery(lottery_id)
        effective_count = DEFAULT_COUNT if count is None else count
        self._validate_count(effective_count)
        selection = self._resolve_selection(lottery_id, selection_id)
        # GEN-09 remix: a single allocation unit carries the whole count; the
        # per-number weights (not a meta entry score) drive sampling below.
        allocations = allocate_count([SelectionEntry(score=1.0, rank=0)], effective_count)

        effective_seed = (
            generation_seed(selection.fingerprint, lottery_id, effective_count, GENERATOR_VERSION)
            if seed is None
            else seed
        )
        fingerprint = snapshot_fingerprint(
            lottery_id, selection.id, effective_count, effective_seed, GENERATOR_VERSION
        )

        # Idempotency (GEN-008): same fingerprint → return existing active.
        existing = self._store.find_by_fingerprint(fingerprint)
        if existing is not None:
            return self._build_generation_result(existing, effective_seed, effective_count)

        # Duplicate conflict (GEN-013): a retired/failed snapshot already owns it.
        duplicate = self._find_duplicate_fingerprint(lottery_id, selection.id, fingerprint)
        if duplicate is not None:
            raise GenServiceError(
                GenServiceError.GEN_DUPLICATE_SNAPSHOT,
                f"snapshot with fingerprint {fingerprint!r} already exists "
                f"(status={duplicate.status})",
            )

        probabilities = self._load_distribution(lottery_id)
        # Coverage (COLD/NORMAL/HOT) from draw history; only COLD numbers get a
        # boost (PM-08). With no imported draw numbers this map is all "normal".
        draws = [
            numbers
            for _dn, numbers, _j, _w in StatPayloadRepository(self._session).iter_draws(lottery.id)
        ]
        coverage = _classify_coverage(
            frequency(draws),
            lottery.min_number,
            lottery.max_number,
            lottery.numbers_to_select,
        )
        weights = build_weights(probabilities, coverage)
        sb_marginal = self._load_sb_marginal(lottery)
        pools = [WeightedPool(weights=weights) for _i, allocated in allocations if allocated > 0]
        sampled = sample_combinations(effective_seed, pools, effective_count, lottery, sb_marginal)

        # D3/R3: score is the transparent mean sampling weight of the combo's
        # numbers (F5 × cold boost) — no meta entry score involved.
        scored: list[tuple[list[int], int, float]] = []
        for combo, sb in sampled:
            mean_w = sum(weights.get(n, 0.0) for n in combo) / len(combo)
            scored.append((combo, sb, round(mean_w, 6)))

        # R1/D5: legality assert before anything is persisted.
        for combo, sb, _score in scored:
            if validate_combination(combo, sb, lottery):
                continue
            if sb is None or sb < lottery.super_number_min or sb > lottery.super_number_max:
                raise GenServiceError(
                    GenServiceError.GEN_INVALID_SUPER_NUMBER,
                    f"combination {combo} carries illegal super number {sb!r}",
                )
            raise GenServiceError(
                GenServiceError.GEN_INVALID_NUMBERS,
                f"combination {combo} violates lottery rules",
            )

        version = self._store.next_version(lottery_id, selection.id)
        combo_dicts = [
            {
                "position": i,
                "numbers": json.dumps(combo),
                "super_number": sb,
                "score": score,
            }
            for i, (combo, sb, score) in enumerate(scored)
        ]
        try:
            snapshot_id = self._store.create_active_snapshot(
                lottery_id=lottery_id,
                selection_id=selection.id,
                version=version,
                fingerprint=fingerprint,
                config_json={
                    "count": effective_count,
                    "seed": effective_seed,
                    "generator_version": GENERATOR_VERSION,
                },
                combinations=combo_dicts,
            )
            self._session.commit()
        except Exception:
            self._session.rollback()
            raise

        snapshot = self._session.get(GenSnapshot, snapshot_id)
        if snapshot is None:
            raise GenServiceError(
                GenServiceError.GEN_SNAPSHOT_NOT_FOUND,
                f"snapshot {snapshot_id} not found after persist",
            )
        return self._build_generation_result(snapshot, effective_seed, effective_count)

    # ------------------------------------------------------------------
    # Reads (GEN-010) — never recompute
    # ------------------------------------------------------------------

    def get_combinations(
        self, lottery_id: int, snapshot_id: int | None = None
    ) -> CombinationListResult:
        """Return the combinations of one snapshot; active snapshot by default."""
        self._resolve_lottery(lottery_id)
        if snapshot_id is not None:
            snapshot = self._get_snapshot_for_lottery(lottery_id, snapshot_id)
        else:
            snapshot = self._get_active_snapshot(lottery_id)
        rows = self._combination_rows(snapshot.id)
        return CombinationListResult(
            snapshot_id=snapshot.id,
            lottery_id=lottery_id,
            combinations=rows,
        )

    def get_snapshots(self, lottery_id: int) -> SnapshotListResult:
        """Return all stored snapshots for a lottery, ordered by version DESC."""
        self._resolve_lottery(lottery_id)
        snapshots = self._store.get_snapshots(lottery_id)
        if not snapshots:
            raise GenServiceError(
                GenServiceError.GEN_SNAPSHOT_NOT_FOUND,
                f"no generator snapshots for lottery {lottery_id}",
            )
        return SnapshotListResult(
            lottery_id=lottery_id,
            snapshots=[self._build_snapshot_result(s) for s in snapshots],
        )

    # ------------------------------------------------------------------
    # Lifecycle (GEN-007)
    # ------------------------------------------------------------------

    def update_snapshot(self, lottery_id: int, snapshot_id: int, status: str) -> SnapshotResult:
        """Transition a stored snapshot to a new lifecycle status (GEN-007).

        Activation is rejected with ``GEN_DUPLICATE_SNAPSHOT`` because it would
        create a second active snapshot for the (lottery, selection) scope.
        """
        self._resolve_lottery(lottery_id)
        snapshot = self._get_snapshot_for_lottery(lottery_id, snapshot_id)
        if status == "active":
            raise GenServiceError(
                GenServiceError.GEN_DUPLICATE_SNAPSHOT,
                f"activating snapshot {snapshot_id} would create a duplicate active "
                "for its (lottery, selection) scope",
            )
        snapshot.status = status
        self._session.commit()
        return self._build_snapshot_result(snapshot)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _resolve_lottery(self, lottery_id: int) -> Any:
        """Resolve a lottery row by id; ``GEN_LOTTERY_NOT_FOUND`` when absent."""
        from backend.app.repositories.lottery_repository import LotteryRepository

        lottery = LotteryRepository(self._session).get(lottery_id)
        if lottery is None:
            raise GenServiceError(
                GenServiceError.GEN_LOTTERY_NOT_FOUND,
                f"lottery {lottery_id!r} does not exist",
            )
        return lottery

    def _resolve_selection(self, lottery_id: int, selection_id: int | None) -> Any:
        """Resolve the selection to weight from; ``GEN_NO_SELECTION`` when absent.

        Without an override the active selection is used; an override must belong
        to the target lottery (GEN-003).
        """
        from backend.app.models.meta_selection import MetaSelection

        if selection_id is not None:
            stmt = select(MetaSelection).where(
                MetaSelection.id == selection_id,
                MetaSelection.lottery_id == lottery_id,
            )
            selection = self._session.execute(stmt).scalar_one_or_none()
            if selection is None:
                raise GenServiceError(
                    GenServiceError.GEN_NO_SELECTION,
                    f"selection {selection_id} not found for lottery {lottery_id}",
                )
            return selection

        stmt = (
            select(MetaSelection)
            .where(MetaSelection.lottery_id == lottery_id, MetaSelection.status == "active")
            .order_by(MetaSelection.version.desc())
            .limit(1)
        )
        selection = self._session.execute(stmt).scalar_one_or_none()
        if selection is None:
            raise GenServiceError(
                GenServiceError.GEN_NO_SELECTION,
                f"no active selection for lottery {lottery_id}",
            )
        return selection

    def _load_distribution(self, lottery_id: int) -> dict[int, float]:
        """Read the active F5 number→probability map; ``GEN_NO_DISTRIBUTION`` absent.

        Subjects that parse as integers within the lottery range are treated as
        numbers; everything else (grid/quantile rows) is ignored (GEN-014).
        """
        from backend.app.models.prob_snapshot import ProbSnapshot
        from backend.app.models.prob_value import ProbValue

        stmt = (
            select(ProbSnapshot)
            .where(ProbSnapshot.lottery_id == lottery_id, ProbSnapshot.status == "active")
            .order_by(ProbSnapshot.version.desc())
            .limit(1)
        )
        snapshot = self._session.execute(stmt).scalar_one_or_none()
        if snapshot is None:
            raise GenServiceError(
                GenServiceError.GEN_NO_DISTRIBUTION,
                f"no active probability distribution for lottery {lottery_id}",
            )

        rows = self._session.execute(
            select(ProbValue)
            .where(ProbValue.snapshot_id == snapshot.id)
            .order_by(ProbValue.subject)
        ).scalars()
        probabilities: dict[int, float] = {}
        for row in rows:
            try:
                number = int(row.subject)
            except (ValueError, TypeError):
                continue
            probabilities[number] = float(row.value)
        if not probabilities:
            raise GenServiceError(
                GenServiceError.GEN_NO_DISTRIBUTION,
                f"probability snapshot {snapshot.id} has no numeric subjects",
            )
        return probabilities

    def _load_sb_marginal(self, lottery: Any) -> dict[int, float]:
        """Load the historical SuperBalota marginal for a lottery (R2/D2).

        Empirical frequencies over imported ``SuperNumber.value`` rows of the
        lottery's draws. Fallbacks: fewer than ``SB_SPARSE_THRESHOLD``
        observations → uniform over the configured SB range; zero observations
        → ``GEN_NO_HISTORY`` (422), nothing persisted.
        """
        from backend.app.models.draw import Draw
        from backend.app.models.super_number import SuperNumber

        sb_min = int(lottery.super_number_min)
        sb_max = int(lottery.super_number_max)
        uniform = {n: 1.0 / (sb_max - sb_min + 1) for n in range(sb_min, sb_max + 1)}

        stmt = (
            select(SuperNumber.value)
            .join(Draw, SuperNumber.draw_id == Draw.id)
            .where(Draw.lottery_id == lottery.id)
        )
        values = list(self._session.execute(stmt).scalars())
        if not values:
            raise GenServiceError(
                GenServiceError.GEN_NO_HISTORY,
                f"no imported super numbers for lottery {lottery.id}",
            )
        if len(values) < SB_SPARSE_THRESHOLD:
            return uniform

        counts: dict[int, int] = {}
        for v in values:
            counts[v] = counts.get(v, 0) + 1
        total = len(values)
        # Keys span the declared SB range; unseen values keep zero weight.
        return {n: counts.get(n, 0) / total for n in range(sb_min, sb_max + 1)}

    def _find_duplicate_fingerprint(
        self, lottery_id: int, selection_id: int, fingerprint: str
    ) -> GenSnapshot | None:
        """Return a non-active snapshot that already owns the fingerprint, if any."""
        stmt = (
            select(GenSnapshot)
            .where(
                GenSnapshot.lottery_id == lottery_id,
                GenSnapshot.selection_id == selection_id,
                GenSnapshot.fingerprint == fingerprint,
                GenSnapshot.status != "active",
            )
            .limit(1)
        )
        return self._session.execute(stmt).scalar_one_or_none()

    def _get_snapshot_for_lottery(self, lottery_id: int, snapshot_id: int) -> GenSnapshot:
        """Return a snapshot scoped to the lottery; ``GEN_SNAPSHOT_NOT_FOUND`` absent."""
        stmt = select(GenSnapshot).where(
            GenSnapshot.id == snapshot_id,
            GenSnapshot.lottery_id == lottery_id,
        )
        snapshot = self._session.execute(stmt).scalar_one_or_none()
        if snapshot is None:
            raise GenServiceError(
                GenServiceError.GEN_SNAPSHOT_NOT_FOUND,
                f"generator snapshot {snapshot_id} not found for lottery {lottery_id}",
            )
        return snapshot

    def _get_active_snapshot(self, lottery_id: int) -> GenSnapshot:
        """Return the active snapshot for a lottery; ``GEN_SNAPSHOT_NOT_FOUND`` absent."""
        stmt = (
            select(GenSnapshot)
            .where(GenSnapshot.lottery_id == lottery_id, GenSnapshot.status == "active")
            .order_by(GenSnapshot.version.desc())
            .limit(1)
        )
        snapshot = self._session.execute(stmt).scalar_one_or_none()
        if snapshot is None:
            raise GenServiceError(
                GenServiceError.GEN_SNAPSHOT_NOT_FOUND,
                f"no active generator snapshot for lottery {lottery_id}",
            )
        return snapshot

    def _validate_count(self, count: int) -> None:
        """Reject counts outside ``[MIN_COUNT, MAX_COUNT]`` (GEN-002, GEN-013)."""
        if count < MIN_COUNT or count > MAX_COUNT:
            raise GenServiceError(
                GenServiceError.GEN_COUNT_INVALID,
                f"count must be between {MIN_COUNT} and {MAX_COUNT}, got {count}",
            )

    def _combination_rows(self, snapshot_id: int) -> list[CombinationRow]:
        """Load the stored combination rows of a snapshot."""
        return [
            CombinationRow(
                position=c.position,
                numbers=json.loads(c.numbers),
                super_number=c.super_number,
                score=c.score,
            )
            for c in self._store.get_combinations(snapshot_id)
        ]

    def _build_generation_result(
        self, snapshot: GenSnapshot, seed: int, count: int
    ) -> GenerationResult:
        """Build the generation result from a persisted snapshot and its rows."""
        rows = self._combination_rows(snapshot.id)
        return GenerationResult(
            snapshot_id=snapshot.id,
            lottery_id=snapshot.lottery_id,
            selection_id=snapshot.selection_id,
            version=snapshot.version,
            status=snapshot.status,
            fingerprint=snapshot.fingerprint,
            seed=seed,
            count=count,
            combinations=rows,
        )

    def _build_snapshot_result(self, snapshot: GenSnapshot) -> SnapshotResult:
        """Build a snapshot header result from a persisted row."""
        return SnapshotResult(
            snapshot_id=snapshot.id,
            lottery_id=snapshot.lottery_id,
            selection_id=snapshot.selection_id,
            version=snapshot.version,
            status=snapshot.status,
            fingerprint=snapshot.fingerprint,
            created_at=snapshot.created_at.isoformat() if snapshot.created_at else None,
        )


__all__ = [
    "DEFAULT_COUNT",
    "MAX_COUNT",
    "MIN_COUNT",
    "GenService",
    "GenerationResult",
    "CombinationListResult",
    "CombinationRow",
    "SnapshotResult",
    "SnapshotListResult",
]
