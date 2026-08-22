"""DlService: composition root for the DL engine (design DlService.train flow, ADR-1..4).

Wires ``dl.engine`` to its Provider Protocols and ``DlSnapshotStore``. ONE atomic
transaction covers a whole model-set run — both families in registry order
(mlp→lstm): placeholder header → per-family train → fill header → bulk metrics →
weight blobs → retire old active → single commit (ADR-1: the store is flush-only,
the service owns the only commit). On any failure after the F4 check the transaction
rolls back and a terminal ``failed`` header is re-created via ``mark_failed``
(recreate-pattern gotcha: after a rollback the placeholder identity no longer
exists, so an UPDATE-style mark would persist nothing). Idempotent reruns
short-circuit on the shared run fingerprint BEFORE any write. torch never loads at
import time — ``dl.engine`` is imported lazily inside ``train`` (DLE-17).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy.orm import Session

from backend.app.core.response_cache import ThreadSafeLRU, register_cache
from backend.app.dl.determinism import DL_SEED, compute_metrics_checksum
from backend.app.dl.fingerprint import compute_dl_fingerprint
from backend.app.dl.providers import (
    DrawHistoryProvider,
    FeatureRow,
    FeatureSnapshotProvider,
)
from backend.app.dl.registry import MODEL_SET_CORE_3, build_dl_registry
from backend.app.dl.sequence_builder import build_tensors
from backend.app.dl.snapshot_store import DlSnapshotStore
from backend.app.dl.splitter import split_windows
from backend.app.dl.version import DL_GENERATOR_VERSION
from backend.app.dl.weights import FORMAT_VERSION
from backend.app.dl.window import DEFAULT_WINDOW, build_windows
from backend.app.models.dl_metric import DlMetric
from backend.app.models.dl_weight import DlWeight

# Read cache for persisted metric payloads; registered so clear_all_caches()
# resets it (test isolation). Keys are ("dl:metrics", snapshot_id, model_id).
_DL_CACHE: ThreadSafeLRU[tuple, object] = ThreadSafeLRU(maxsize=256)
register_cache(_DL_CACHE)

# Registry insertion order IS the canonical training order (design: mlp→lstm).
_TRAIN_ORDER: tuple[str, ...] = ("mlp", "lstm")


@dataclass(frozen=True)
class DlTrainOutcome:
    """Result of one model-set training run (one snapshot covers both families)."""

    lottery_id: int
    model_set: str
    status: str
    fingerprint: str
    snapshot_id: int | None = None
    metrics_checksum: str | None = None
    error: str | None = None


class DlService:
    """Composition root for DL — one atomic tx per model-set run (ADR-1)."""

    def __init__(
        self,
        session: Session,
        draw_reader: DrawHistoryProvider,
        feature_provider: FeatureSnapshotProvider,
    ) -> None:
        self._session = session
        self._draws = draw_reader
        self._features = feature_provider

    def train(
        self,
        lottery_id: int,
        model_set: str = MODEL_SET_CORE_3,
        *,
        window: int = DEFAULT_WINDOW,
        cut: int | None = None,
        epochs: int | None = None,
        batch_size: int | None = None,
        lr: float | None = None,
    ) -> DlTrainOutcome:
        """Train both core-3 families for a lottery inside ONE atomic transaction.

        Sequence (design): resolve providers → drop the last draw from the window
        frame so every window end keeps its n+1 target → default the walk-forward
        boundary to ``len(frame)*4//5`` when ``cut`` is omitted (R2) → build
        windows/split/tensors → compute ONE shared run fingerprint over the tensor
        bytes, registry hyperparameters, seed, W, real cut and engine version →
        return the existing snapshot untouched on a fingerprint hit (zero writes) →
        otherwise create the active placeholder, train mlp→lstm with the injected
        fingerprint, fill the header, bulk-insert Decimal metrics and weight blobs,
        retire the old active (deleting its weights), and commit exactly once.
        """
        store = DlSnapshotStore(self._session)

        # Early F4 gate: absence fails BEFORE any header write (ML precedent).
        f4_snapshot_id = self._features.active_snapshot_id(lottery_id)
        if f4_snapshot_id is None:
            return DlTrainOutcome(
                lottery_id=lottery_id,
                model_set=model_set,
                status="failed",
                fingerprint="",
                error=f"no active F4 feature snapshot for lottery {lottery_id}",
            )

        version = store.next_version(lottery_id, model_set)
        # Dead-metadata defaults survive exceptions raised before resolution.
        real_cut = cut if cut is not None else 0
        w = window
        draw_count = draws_from = draws_to = 0
        try:
            records = list(self._draws.iter_draws(lottery_id))
            feature_rows: list[FeatureRow] = list(self._features.feature_rows(f4_snapshot_id))

            # Drop the last draw so every window end keeps its n+1 target row;
            # all draws stay available for target lookup in build_tensors.
            frame = records[:-1]
            draw_count = len(frame)
            draws_from = frame[0].draw_number if frame else 0
            draws_to = frame[-1].draw_number if frame else 0
            # Walk-forward boundary (R2): an omitted cut defaults to the
            # ``len(frame)*4//5`` index converted onto the draw-number axis;
            # an explicit cut is used verbatim. Windows are then BUILT PER SIDE
            # (train range / eval range) exactly like the GF-1 harness: building
            # over the full contiguous frame would straddle the cut by
            # construction for W >= 3 and be rejected by the splitter.
            if cut is None:
                k = len(frame) * 4 // 5
                if not frame[:k] or not frame[k:]:
                    raise ValueError(
                        f"frame of {len(frame)} draws cannot be split at "
                        f"index {k} for walk-forward training"
                    )
                train_frame = frame[:k]
                eval_frame = frame[k:]
                real_cut = train_frame[-1].draw_number
            else:
                real_cut = cut
                train_frame = [d for d in frame if d.draw_number <= real_cut]
                eval_frame = [d for d in frame if d.draw_number > real_cut]
            train_features = [f for f in feature_rows if f.draw_number <= real_cut]
            eval_features = [f for f in feature_rows if f.draw_number > real_cut]

            train_windows = build_windows(train_frame, train_features, W=w)
            eval_windows = build_windows(eval_frame, eval_features, W=w)
            # Anti-leakage validation + chronological partition (DLE-05).
            train_windows, eval_windows = split_windows([*train_windows, *eval_windows], real_cut)
            train_batch = build_tensors(train_windows, records)
            eval_batch = build_tensors(eval_windows, records)

            data_hash = hashlib.sha256(
                train_batch.X.tobytes()
                + train_batch.y.tobytes()
                + eval_batch.X.tobytes()
                + eval_batch.y.tobytes()
            ).hexdigest()
            registry = build_dl_registry()
            run_fp = compute_dl_fingerprint(
                data_hash=data_hash,
                hyperparameters={slug: registry[slug] for slug in _TRAIN_ORDER},
                architecture=model_set,
                seed=DL_SEED,
                window=w,
                cut=real_cut,
                version=DL_GENERATOR_VERSION,
            )

            existing = store.find_by_fingerprint(lottery_id, model_set, run_fp)
            if existing is not None:
                # Idempotent rerun: return existing metadata, ZERO writes (DLE-12).
                return DlTrainOutcome(
                    lottery_id=lottery_id,
                    model_set=model_set,
                    status="active",
                    fingerprint=existing.input_fingerprint,
                    snapshot_id=existing.id,
                    metrics_checksum=existing.checksum,
                )

            header = store.create_snapshot(
                lottery_id=lottery_id,
                model_set=model_set,
                version=version,
                dl_generator_version=DL_GENERATOR_VERSION,
                checksum="",  # filled after training
                input_fingerprint="",  # filled after training
                status="active",
                is_locked=True,
                draw_count=draw_count,
                draws_from=draws_from,
                draws_to=draws_to,
            )

            from backend.app.dl.engine import train as engine_train  # noqa: PLC0415

            metric_rows: list[DlMetric] = []
            weight_rows: list[DlWeight] = []
            checksum_payload: dict[str, Decimal] = {}
            for slug in _TRAIN_ORDER:
                params = registry[slug]
                result = engine_train(
                    slug,
                    train_batch,
                    eval_batch,
                    epochs=int(params["epochs"]) if epochs is None else epochs,
                    batch_size=(int(params["batch_size"]) if batch_size is None else batch_size),
                    lr=float(params["lr"]) if lr is None else lr,
                    seed=DL_SEED,
                    cut=real_cut,
                    fingerprint=run_fp,
                )
                checksum_payload.update(
                    {f"{slug}.{name}": value for name, value in result.metrics.items()}
                )
                params_json = json.dumps(params, sort_keys=True)
                for name, value in result.metrics.items():
                    metric_rows.append(
                        DlMetric(
                            model_id=slug,
                            model_version=DL_GENERATOR_VERSION,
                            number=0,  # cross-number aggregate sentinel
                            metric_name=name,
                            value=value,
                            params_json=params_json,
                        )
                    )
                weight_rows.append(
                    DlWeight(
                        snapshot_id=header.id,
                        model_id=result.family,
                        weights_blob=result.weights_blob,
                        weights_size_bytes=len(result.weights_blob),
                        weights_fingerprint=run_fp,
                        format_version=FORMAT_VERSION,
                    )
                )

            header.checksum = compute_metrics_checksum(checksum_payload)
            header.input_fingerprint = run_fp
            header.cut = real_cut
            header.window = w

            store.bulk_insert_metrics(header.id, metric_rows)
            store.insert_weights(weight_rows)
            store.retire_old_active(lottery_id, model_set, keep_id=header.id)
            self._session.commit()  # ← SINGLE transaction boundary

            return DlTrainOutcome(
                lottery_id=lottery_id,
                model_set=model_set,
                status="active",
                fingerprint=run_fp,
                snapshot_id=header.id,
                metrics_checksum=header.checksum,
            )

        except Exception as exc:
            self._session.rollback()
            # Recreate pattern: the rolled-back placeholder no longer exists, so
            # re-insert a minimal terminal failed header under the freed UNIQUE slot.
            terminal = store.mark_failed(
                lottery_id=lottery_id,
                model_set=model_set,
                version=version,
                dl_generator_version=DL_GENERATOR_VERSION,
                cut=real_cut,
                window=w,
                draw_count=draw_count,
                draws_from=draws_from,
                draws_to=draws_to,
            )
            self._session.commit()
            return DlTrainOutcome(
                lottery_id=lottery_id,
                model_set=model_set,
                status="failed",
                fingerprint="",
                snapshot_id=terminal.id,
                error=str(exc),
            )

    def get_active_snapshot(self, lottery_id: int) -> dict | None:
        """Return the active DL snapshot metadata for a lottery, or None."""
        snapshot = DlSnapshotStore(self._session).get_active(lottery_id, MODEL_SET_CORE_3)
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
            "window": snapshot.window,
        }

    def get_metrics(self, lottery_id: int, model_id: str | None = None) -> list[dict]:
        """Return persisted metrics for the active snapshot (cached read).

        Rows are cached under ``("dl:metrics", snapshot.id, model_id)``; floats
        appear ONLY here at the JSON response edge — storage stays Decimal-only.
        """
        store = DlSnapshotStore(self._session)
        snapshot = store.get_active(lottery_id, MODEL_SET_CORE_3)
        if snapshot is None:
            return []
        key = ("dl:metrics", snapshot.id, model_id)
        cached = _DL_CACHE.get(key)
        if cached is not None:
            return cached  # type: ignore[return-value]
        rows = store.metrics_for_snapshot(snapshot.id, model_id=model_id)
        payload = [
            {
                "model_id": r.model_id,
                "number": r.number,
                "metric_name": r.metric_name,
                "value": float(r.value),
                "params_json": r.params_json,
            }
            for r in rows
        ]
        _DL_CACHE.set(key, payload)
        return payload


__all__ = ["DlService", "DlTrainOutcome"]
