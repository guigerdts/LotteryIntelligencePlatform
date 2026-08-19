"""MetaService — meta-learning service layer (META-001–META-012, META-016–META-018).

Exposes ranking and selection through a service boundary.  API and CLI call
rank/select/get_ranking/get_selection; the service owns DB access, context
resolution, normalization, scoring, ranking, selection, and persistence via
MetaSnapshotStore.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.orm import Session

from backend.app.meta.context import compute_context_hash, resolve_context_vector
from backend.app.meta.normalization import normalize_per_engine
from backend.app.meta.ranking import build_ranking_entries, compute_fingerprint
from backend.app.meta.scoring import DEFAULT_WEIGHTS, compute_score, validate_weights
from backend.app.meta.selection import select_top_k
from backend.app.meta.snapshot_store import MetaSnapshotStore
from backend.app.services.errors import MetaServiceError


@dataclass(frozen=True)
class RankingResult:
    """Outcome of a rank operation."""

    ranking_id: int
    lottery_id: int
    context_hash: str
    version: str
    status: str
    fingerprint: str
    entries: list[dict[str, Any]] = field(default_factory=list)


@dataclass(frozen=True)
class SelectionResult:
    """Outcome of a select operation."""

    selection_id: int
    lottery_id: int
    ranking_id: int
    context_hash: str
    version: str
    status: str
    fingerprint: str
    entries: list[dict[str, Any]] = field(default_factory=list)


@dataclass(frozen=True)
class RankingSnapshot:
    """Snapshot of rankings for a lottery + context."""

    lottery_id: int
    context_hash: str
    rankings: list[dict[str, Any]] = field(default_factory=list)


@dataclass(frozen=True)
class SelectionSnapshot:
    """Snapshot of selections for a lottery + context."""

    lottery_id: int
    context_hash: str
    selections: list[dict[str, Any]] = field(default_factory=list)


class MetaService:
    """Meta-learning service (META-001–META-012).  API and CLI call this layer."""

    def __init__(self, session: Session) -> None:
        self._session = session
        self._store = MetaSnapshotStore(session)

    # ------------------------------------------------------------------
    # Rank
    # ------------------------------------------------------------------

    def rank(
        self,
        *,
        lottery_id: int,
        engine_types: list[str] | None = None,
        weights: dict[str, float] | None = None,
    ) -> RankingResult:
        """Compute a ranking for the given lottery (META-001–META-005, META-012).

        Orchestrates: context resolution → normalization → scoring → ranking → persistence.
        """
        # 1. Resolve weights
        effective_weights = weights if weights else dict(DEFAULT_WEIGHTS)
        try:
            validate_weights(effective_weights)
        except ValueError as exc:
            raise MetaServiceError(MetaServiceError.META_WEIGHTS_INVALID, str(exc)) from exc

        # 2. Determine engine types to rank
        if not engine_types:
            engine_types = ["backtesting", "ml", "dl", "optimization"]

        # 3. Resolve context and read engine snapshots per engine type
        all_snapshots: list[dict[str, Any]] = []
        context_hash = None
        for et in engine_types:
            try:
                vector = resolve_context_vector(lottery_id, et, self._session)
            except ValueError:
                continue  # Skip engine types with no data
            if context_hash is None:
                context_hash = compute_context_hash(vector)
            snapshots = _read_engine_snapshots(lottery_id, et, self._session)
            all_snapshots.extend(snapshots)

        if not all_snapshots:
            raise MetaServiceError(
                MetaServiceError.META_NO_ENGINE_DATA,
                f"No engine snapshots found for lottery {lottery_id}",
            )

        if context_hash is None:
            raise MetaServiceError(
                MetaServiceError.META_NO_ENGINE_DATA,
                f"No engine context found for lottery {lottery_id}",
            )

        # 4. Normalize, score, rank
        normalized = normalize_per_engine(all_snapshots)
        for snap in normalized:
            snap["score"] = compute_score(snap, effective_weights)
        entries = build_ranking_entries(normalized)
        fp = compute_fingerprint(lottery_id, context_hash, entries)

        # 5. Idempotency check
        existing = self._store.find_by_fingerprint(fp)
        if existing is not None:
            return RankingResult(
                ranking_id=existing.id,
                lottery_id=lottery_id,
                context_hash=context_hash,
                version=existing.version,
                status=existing.status,
                fingerprint=fp,
                entries=[],
            )

        # 6. Persist
        version = self._store.next_version(lottery_id, context_hash)
        entry_dicts = [
            {
                "model_id": e.model_id,
                "engine_type": e.engine_type,
                "score": e.score,
                "metrics": e.metrics,
            }
            for e in entries
        ]
        ranking_id = self._store.create_active_ranking(
            lottery_id=lottery_id,
            context_hash=context_hash,
            version=version,
            fingerprint=fp,
            entries=entry_dicts,
            config_json={"weights": effective_weights},
        )
        self._session.commit()

        return RankingResult(
            ranking_id=ranking_id,
            lottery_id=lottery_id,
            context_hash=context_hash,
            version=version,
            status="active",
            fingerprint=fp,
            entries=entry_dicts,
        )

    # ------------------------------------------------------------------
    # Get ranking
    # ------------------------------------------------------------------

    def get_ranking(
        self,
        lottery_id: int,
        context_hash: str | None = None,
    ) -> RankingSnapshot:
        """Retrieve ranking snapshot (META-010)."""
        rankings = self._store.get_rankings(lottery_id, context_hash)
        if not rankings:
            raise MetaServiceError(
                MetaServiceError.META_RANKING_NOT_FOUND,
                f"No ranking found for lottery {lottery_id}",
            )
        # Use context_hash from first ranking if not provided
        ch = context_hash or rankings[0].context_hash
        return RankingSnapshot(
            lottery_id=lottery_id,
            context_hash=ch,
            rankings=[
                {
                    "ranking_id": r.id,
                    "version": r.version,
                    "status": r.status,
                    "fingerprint": r.fingerprint,
                    "config_json": r.config_json,
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                }
                for r in rankings
            ],
        )

    # ------------------------------------------------------------------
    # Select
    # ------------------------------------------------------------------

    def select(
        self,
        *,
        lottery_id: int,
        top_k: int | None = None,
        min_score: float | None = None,
        context_hash: str | None = None,
    ) -> SelectionResult:
        """Compute a selection from the active ranking (META-006, META-020).

        Orchestrates: context resolution → ranking lookup → selection → persistence.
        """
        # 1. Validate top_k
        effective_top_k = top_k if top_k is not None else 5
        if effective_top_k < 1 or effective_top_k > 20:
            raise MetaServiceError(
                MetaServiceError.META_TOP_K_INVALID,
                f"top_k must be between 1 and 20, got {effective_top_k}",
            )

        effective_min_score = min_score if min_score is not None else 0.0

        # 2. Resolve context and get active ranking
        try:
            vector = resolve_context_vector(lottery_id, "backtesting", self._session)
        except ValueError as exc:
            raise MetaServiceError(
                MetaServiceError.META_NO_ENGINE_DATA,
                f"No engine snapshots found for lottery {lottery_id}",
            ) from exc

        ctx_hash = context_hash or compute_context_hash(vector)

        # 3. Get active ranking entries
        rankings = self._store.get_rankings(lottery_id, ctx_hash)
        if not rankings:
            raise MetaServiceError(
                MetaServiceError.META_RANKING_NOT_FOUND,
                f"No ranking found for lottery {lottery_id}, context {ctx_hash}",
            )

        active_ranking = next((r for r in rankings if r.status == "active"), rankings[0])
        # Read ranking entries from DB
        from backend.app.models.meta_ranking_entry import MetaRankingEntry

        db_entries = (
            self._session.query(MetaRankingEntry)
            .filter(MetaRankingEntry.ranking_id == active_ranking.id)
            .all()
        )
        ranking_entries = []
        for de in db_entries:
            from backend.app.meta.types import RankingEntry

            metrics = json.loads(de.metrics_json) if de.metrics_json else {}
            ranking_entries.append(
                RankingEntry(
                    model_id=de.model_id,
                    engine_type=de.engine_type,
                    score=de.score,
                    metrics=metrics,
                )
            )

        # 4. Select top-K
        selected = select_top_k(
            ranking_entries, top_k=effective_top_k, min_score=effective_min_score
        )

        # 5. Compute selection fingerprint
        import hashlib

        entries_data = sorted(
            [{"model_id": e.model_id, "score": e.score} for e in selected],
            key=lambda x: x["model_id"],
        )
        sel_fp = hashlib.sha256(
            json.dumps(
                {
                    "lottery_id": lottery_id,
                    "context_hash": ctx_hash,
                    "ranking_fingerprint": active_ranking.fingerprint,
                    "top_k": effective_top_k,
                    "min_score": effective_min_score,
                    "entries": entries_data,
                },
                sort_keys=True,
            ).encode()
        ).hexdigest()

        # 6. Idempotency check
        existing_sel = self._store.find_by_fingerprint(sel_fp)
        if existing_sel is not None:
            return SelectionResult(
                selection_id=existing_sel.id,
                lottery_id=lottery_id,
                ranking_id=active_ranking.id,
                context_hash=ctx_hash,
                version=existing_sel.version,
                status=existing_sel.status,
                fingerprint=sel_fp,
                entries=[],
            )

        # 7. Persist
        version = self._store.next_version(lottery_id, ctx_hash)
        entry_dicts = [
            {
                "model_id": e.model_id,
                "engine_type": e.engine_type,
                "rank": e.rank,
                "score": e.score,
            }
            for e in selected
        ]
        selection_id = self._store.create_active_selection(
            lottery_id=lottery_id,
            context_hash=ctx_hash,
            version=version,
            fingerprint=sel_fp,
            ranking_id=active_ranking.id,
            entries=entry_dicts,
        )
        self._session.commit()

        return SelectionResult(
            selection_id=selection_id,
            lottery_id=lottery_id,
            ranking_id=active_ranking.id,
            context_hash=ctx_hash,
            version=version,
            status="active",
            fingerprint=sel_fp,
            entries=entry_dicts,
        )

    # ------------------------------------------------------------------
    # Get selection
    # ------------------------------------------------------------------

    def get_selection(
        self,
        lottery_id: int,
        context_hash: str | None = None,
    ) -> SelectionSnapshot:
        """Retrieve selection snapshot (META-010)."""
        selections = self._store.get_selections(lottery_id, context_hash)
        if not selections:
            raise MetaServiceError(
                MetaServiceError.META_SELECTION_NOT_FOUND,
                f"No selection found for lottery {lottery_id}",
            )
        ch = context_hash or selections[0].context_hash
        return SelectionSnapshot(
            lottery_id=lottery_id,
            context_hash=ch,
            selections=[
                {
                    "selection_id": s.id,
                    "version": s.version,
                    "status": s.status,
                    "fingerprint": s.fingerprint,
                    "config_json": s.config_json,
                    "created_at": s.created_at.isoformat() if s.created_at else None,
                }
                for s in selections
            ],
        )


# ------------------------------------------------------------------
# Engine snapshot reading (lazy imports, NFR-META-08)
# ------------------------------------------------------------------


def _read_engine_snapshots(
    lottery_id: int,
    engine_type: str,
    db: Session,
) -> list[dict[str, Any]]:
    """Read engine snapshots for scoring (NFR-META-08: lazy imports only).

    Returns a list of dicts with engine-specific metric fields and metadata.
    """
    if engine_type == "backtesting":
        from backend.app.models.bt_result import BtResult
        from backend.app.models.bt_snapshot import BtSnapshot

        snaps = (
            db.query(BtSnapshot)
            .filter(BtSnapshot.lottery_id == lottery_id, BtSnapshot.status == "active")
            .all()
        )
        result = []
        for s in snaps:
            bt_result = (
                db.query(BtResult)
                .filter(BtResult.snapshot_id == s.id)
                .order_by(BtResult.created_at.desc())
                .first()
            )
            metrics = json.loads(bt_result.aggregate_metrics_json) if bt_result else {}
            result.append(
                {
                    "model_id": f"bt-{s.strategy_id}-{s.id}",
                    "engine_type": "backtesting",
                    **{k: v for k, v in metrics.items() if k not in ("total_draws_evaluated",)},
                }
            )
        return result

    elif engine_type == "ml":
        from backend.app.models.ml_metric import MlMetric
        from backend.app.models.ml_snapshot import MlSnapshot

        snaps = (
            db.query(MlSnapshot)
            .filter(MlSnapshot.lottery_id == lottery_id, MlSnapshot.status == "active")
            .all()
        )
        result = []
        for s in snaps:
            metrics: dict[str, float] = {}
            for row in db.query(MlMetric).filter(MlMetric.snapshot_id == s.id).all():
                key = row.metric_name
                val = float(row.value)
                if key in metrics:
                    metrics[key] = (metrics[key] + val) / 2
                else:
                    metrics[key] = val
            result.append(
                {
                    "model_id": f"ml-{s.model_set}-{s.id}",
                    "engine_type": "ml",
                    **metrics,
                }
            )
        return result

    elif engine_type == "dl":
        from backend.app.models.dl_metric import DlMetric
        from backend.app.models.dl_snapshot import DlSnapshot

        snaps = (
            db.query(DlSnapshot)
            .filter(DlSnapshot.lottery_id == lottery_id, DlSnapshot.status == "active")
            .all()
        )
        result = []
        for s in snaps:
            metrics: dict[str, float] = {}
            for row in db.query(DlMetric).filter(DlMetric.snapshot_id == s.id).all():
                key = row.metric_name
                val = float(row.value)
                if key in metrics:
                    metrics[key] = (metrics[key] + val) / 2
                else:
                    metrics[key] = val
            result.append(
                {
                    "model_id": f"dl-{s.model_set}-{s.id}",
                    "engine_type": "dl",
                    **metrics,
                }
            )
        return result

    elif engine_type == "optimization":
        from backend.app.models.opt_result import OptResult
        from backend.app.models.opt_snapshot import OptSnapshot

        snaps = (
            db.query(OptSnapshot)
            .filter(OptSnapshot.lottery_id == lottery_id, OptSnapshot.status == "active")
            .all()
        )
        result = []
        for s in snaps:
            metrics: dict[str, float] = {}
            for row in db.query(OptResult).filter(OptResult.snapshot_id == s.id).all():
                metrics[f"best_fitness_{row.target_model}"] = float(row.best_fitness)
            result.append(
                {
                    "model_id": f"opt-{s.optimizer}-{s.id}",
                    "engine_type": "optimization",
                    **metrics,
                }
            )
        return result

    return []
