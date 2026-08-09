"""MlService: composition root for the ML engine (MLE-08, design §7).

Wires the ML engine to its Provider Protocols and ``MlSnapshotStore``.
Owns the single atomic transaction: create(active) → bulk_insert →
retire_old_active → commit. On failure → rollback + terminal ``failed``.
Manual-only: no auto-retire, no scheduler, no import hooks.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from sqlalchemy.orm import Session

from backend.app.ml.engine import MlEngine, TrainResult
from backend.app.ml.feature_reader import FeatureValueRow
from backend.app.ml.providers import DrawHistoryProvider, FeatureSnapshotProvider
from backend.app.ml.registry import MODEL_SET_CORE_5
from backend.app.ml.snapshot_store import MlSnapshotStore
from backend.app.ml.version import ML_GENERATOR_VERSION
from backend.app.models.ml_metric import MlMetric

# Core-5 families — the ONLY executed set (MLE-07).
_CORE_5_FAMILIES: tuple[str, ...] = (
    "random_forest",
    "extra_trees",
    "gradient_boosting",
    "svm",
    "knn",
)


@dataclass(frozen=True)
class TrainOutcome:
    """Result of one family training within the service."""

    family: str
    lottery_id: int
    status: str
    fingerprint: str
    snapshot_id: int | None = None
    metrics_checksum: str | None = None
    error: str | None = None


class MlService:
    """Composition root for ML — one atomic tx per training run (MLE-08)."""

    def __init__(
        self,
        session: Session,
        draw_reader: DrawHistoryProvider,
        feature_provider: FeatureSnapshotProvider,
        engine: MlEngine | None = None,
    ) -> None:
        self._session = session
        self._draws = draw_reader
        self._features = feature_provider
        self._engine = engine or MlEngine()

    def train(
        self,
        lottery_id: int,
        family: str | None = None,
        metadata: dict | None = None,
    ) -> list[TrainOutcome]:
        """Train one or all core-5 families for a lottery.

        When ``family`` is None, trains all five. Each family gets its own
        snapshot. The transaction is atomic per family (create → insert →
        retire → commit or rollback + failed).
        """
        families = (family,) if family is not None else _CORE_5_FAMILIES
        outcomes: list[TrainOutcome] = []

        for fam in families:
            outcome = self._train_one(lottery_id, fam, metadata)
            outcomes.append(outcome)

        return outcomes

    def _train_one(
        self,
        lottery_id: int,
        family: str,
        metadata: dict | None,
    ) -> TrainOutcome:
        """Train a single family within one atomic transaction (MLE-08)."""
        store = MlSnapshotStore(self._session)
        version = store.next_version(lottery_id, MODEL_SET_CORE_5)

        # Read features from the active F4 snapshot (MLE-06).
        snapshot_id = self._features.active_snapshot_id(lottery_id)
        if snapshot_id is None:
            return TrainOutcome(
                family=family,
                lottery_id=lottery_id,
                status="failed",
                fingerprint="",
                error=f"no active F4 feature snapshot for lottery {lottery_id}",
            )
        feature_rows: list[FeatureValueRow] = list(self._features.feature_rows(snapshot_id))

        # Read draw history for training records.
        records = list(self._draws.iter_draws(lottery_id))

        # Create header (status=active initially, retired on commit).
        header = store.create_snapshot(
            lottery_id=lottery_id,
            model_set=MODEL_SET_CORE_5,
            version=version,
            ml_generator_version=ML_GENERATOR_VERSION,
            checksum="",  # filled after training
            input_fingerprint="",  # filled after training
            cut=0,  # filled after training
            status="active",
            is_locked=True,
            draw_count=len(records),
            draws_from=records[0].draw_number if records else 0,
            draws_to=records[-1].draw_number if records else 0,
        )

        try:
            result: TrainResult = self._engine.train(
                family=family,
                lottery_id=lottery_id,
                records=records,
                snapshot_id=header.id,
                metadata=metadata,
                feature_rows=feature_rows,
            )

            # Update header with computed values.
            header.checksum = result.checksum
            header.input_fingerprint = result.fingerprint
            header.cut = result.cut

            # Build metric rows for bulk insert.
            metric_rows: list[MlMetric] = []
            params_json = json.dumps(self._engine.registry[family][1], sort_keys=True)
            for number, per_metric in result.quantized.items():
                for metric_name, value in per_metric.items():
                    metric_rows.append(
                        MlMetric(
                            snapshot_id=header.id,
                            model_id=family,
                            model_version=ML_GENERATOR_VERSION,
                            number=number,
                            metric_name=metric_name,
                            value=value,
                            params_json=params_json,
                        )
                    )

            # Bulk insert metrics, retire old, commit — one atomic tx.
            store.bulk_insert_metrics(header.id, metric_rows)
            store.retire_old_active(lottery_id, MODEL_SET_CORE_5, keep_id=header.id)
            self._session.commit()

            return TrainOutcome(
                family=family,
                lottery_id=lottery_id,
                status="active",
                fingerprint=result.fingerprint,
                snapshot_id=header.id,
                metrics_checksum=result.checksum,
            )

        except Exception as exc:
            self._session.rollback()
            store.mark_failed(header.id)
            self._session.commit()
            return TrainOutcome(
                family=family,
                lottery_id=lottery_id,
                status="failed",
                fingerprint="",
                snapshot_id=header.id,
                error=str(exc),
            )

    def get_active_snapshot(self, lottery_id: int) -> dict | None:
        """Return the active ML snapshot metadata for a lottery, or None."""
        store = MlSnapshotStore(self._session)
        snapshot = store.get_active(lottery_id, MODEL_SET_CORE_5)
        if snapshot is None:
            return None
        return {
            "id": snapshot.id,
            "lottery_id": snapshot.lottery_id,
            "model_set": snapshot.model_set,
            "version": snapshot.version,
            "status": snapshot.status,
            "checksum": snapshot.checksum,
            "input_fingerprint": snapshot.input_fingerprint,
            "cut": snapshot.cut,
        }

    def get_metrics(self, lottery_id: int, model_id: str | None = None) -> list[dict]:
        """Return persisted metrics for the active snapshot."""
        store = MlSnapshotStore(self._session)
        snapshot = store.get_active(lottery_id, MODEL_SET_CORE_5)
        if snapshot is None:
            return []
        rows = store.metrics_for_snapshot(snapshot.id, model_id=model_id)
        return [
            {
                "model_id": r.model_id,
                "number": r.number,
                "metric_name": r.metric_name,
                "value": float(r.value),
                "params_json": r.params_json,
            }
            for r in rows
        ]


__all__ = ["MlService", "TrainOutcome"]
