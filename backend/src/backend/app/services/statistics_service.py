"""Statistics snapshot orchestration: idempotent/incremental/full generate (design §3/§7).

Implements the manual ``generate`` use case (STE-05/06/11 + C4/C5): resolve the
lottery, compute the deterministic metric payload, checksum it (STE-05), then
atomically write a NEW immutable ::class:`StatSnapshot` version with its payload
rows — flipping any prior ``active`` snapshot to ``retired`` in the SAME
transaction (design §7). A batch/engine failure marks the run terminal ``failed``
(NEVER ``active``/``partial``, design §3) and a retry ALWAYS creates a fresh new
version (design §3 "resume = new snapshot"; a failed snapshot is never reused).

Idempotency (design §5): when an ``active`` snapshot already encodes the same
checksum + generator_version + scope/metric_set, the prospective result is
identical, so the existing snapshot is returned — no duplicate version is
written. Scope ``incremental`` vs ``full`` selects whether an existing active
snapshot is consulted, but the metric fold is always deterministic over the same
batched, keyed read (design §3/§9): any run over the same dataset is
byte-identical, which makes "incremental == full-rebuild checksum" and the G9
determinism gate true. No HTTP/CLI/request parsing (PR-3 owns the surface).
Writes ``stat_*`` ONLY (STE-02) — core tables are never mutated (G10).
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.config.settings import get_settings
from backend.app.models.stat_average import StatAverage
from backend.app.models.stat_frequency import StatFrequency
from backend.app.models.stat_gap import StatGap
from backend.app.models.stat_snapshot import StatSnapshot
from backend.app.repositories.lottery_repository import LotteryRepository
from backend.app.repositories.stat_payload_repository import StatPayloadRepository
from backend.app.repositories.stat_snapshot_repository import StatSnapshotRepository
from backend.app.services.errors import (
    GenerationError,
    NotFoundError,
    SnapshotNotFoundError,
    ValidationError,
)
from backend.app.statistics.checksum import stat_checksum
from backend.app.statistics.engine import (
    entropy_base2,
    frequency,
    null_aware_average,
    positional_frequency,
)
from backend.app.statistics.engine import (
    gaps as engine_gaps,
)
from backend.app.statistics.generator import (
    SCOPE_INCREMENTAL,
    SCOPES,
    STATS_GENERATOR_VERSION,
)


class StatisticsService:
    """Statistics use cases over one DI session transaction (deterministic, atomic)."""

    def __init__(self, session: Session) -> None:
        self._session = session
        self._lotteries = LotteryRepository(session)
        self._snapshots = StatSnapshotRepository(session)
        self._payloads = StatPayloadRepository(session)
        self._settings = get_settings()

    def generate(
        self,
        *,
        lottery_code: str | None = None,
        lottery_id: int | None = None,
        metric_set: str = "core",
        scope: str = "incremental",
    ) -> StatSnapshot:
        """Generate (or idempotently return) a statistics snapshot for a lottery.

        ``lottery_code`` or ``lottery_id`` resolves the lottery (404-style when
        absent); ``metric_set`` must be a supported bundle (currently ``core``);
        ``scope`` is one of ``SCOPES``. Returns the existing ``active`` snapshot
        when it already reproduces the exact prospective result (design §5),
        otherwise persists a NEW version and returns it.
        """
        lottery = self._resolve_lottery(lottery_code=lottery_code, lottery_id=lottery_id)
        scope_obj = self._resolve_scope(scope)
        if metric_set != "core":
            raise ValidationError(f"unsupported metric_set {metric_set!r}; expected 'core'")

        payload = self._compute_payload(lottery, metric_set)
        checksum = payload["checksum"]

        # Idempotency (design §5): an active snapshot that already encodes this
        # exact result is returned — no duplicate version is written. It applies
        # only to the incremental scope: ``full`` always rebuilds as a NEW version
        # (STE-06/design §7) even if the content is identical.
        if scope_obj is SCOPE_INCREMENTAL:
            existing = self._snapshots.find_by_checksum_version(
                lottery.id, metric_set, checksum, STATS_GENERATOR_VERSION
            )
            if existing is not None:
                return existing

        return self._persist_new(lottery, metric_set, payload)

    # --- reads (design §5/STE-10: served from an existing snapshot, never precompute) ---

    def get_active(
        self, *, lottery_code: str | None = None, lottery_id: int | None = None
    ) -> StatSnapshot:
        """Resolve the lottery and return its active ``core`` snapshot.

        A missing lottery surfaces ``NotFoundError`` (404 RESOURCE_NOT_FOUND);
        a lottery with no active snapshot surfaces ``SnapshotNotFoundError``
        (404 SNAPSHOT_NOT_FOUND). Reads NEVER trigger precompute (STE-10/C5).
        """
        lottery = self._resolve_lottery(lottery_code=lottery_code, lottery_id=lottery_id)
        snapshot = self._snapshots.get_active(lottery.id, "core")
        if snapshot is None:
            raise SnapshotNotFoundError(
                f"no statistics snapshot for lottery {lottery.id!r} (metric_set='core')"
            )
        return snapshot

    def read_frequencies(
        self, *, lottery_code: str | None = None, lottery_id: int | None = None, last: int = 0
    ) -> tuple[StatSnapshot, list]:
        """Return the active snapshot and its frequency rows, bounded by ``last``.

        ``last=0`` returns all rows; ``last>0`` returns at most ``last`` rows.
        Rows are ordered by ``number`` ASC for a deterministic on-demand read
        (design §9). Never recomputes history (STE-10).
        """
        snapshot = self.get_active(lottery_code=lottery_code, lottery_id=lottery_id)
        rows = (
            self._session.execute(
                select(StatFrequency)
                .where(StatFrequency.snapshot_id == snapshot.id)
                .order_by(StatFrequency.number)
            )
            .scalars()
            .all()
        )
        return snapshot, list(rows)[:last] if last else list(rows)

    def read_gaps(
        self, *, lottery_code: str | None = None, lottery_id: int | None = None, last: int = 0
    ) -> tuple[StatSnapshot, list]:
        """Return the active gap summaries ordered by ``number``, bounded by ``last``."""
        snapshot = self.get_active(lottery_code=lottery_code, lottery_id=lottery_id)
        rows = (
            self._session.execute(
                select(StatGap).where(StatGap.snapshot_id == snapshot.id).order_by(StatGap.number)
            )
            .scalars()
            .all()
        )
        return snapshot, list(rows)[:last] if last else list(rows)

    def read_averages(
        self, *, lottery_code: str | None = None, lottery_id: int | None = None
    ) -> tuple[StatSnapshot, list]:
        """Return the active NULL-aware averages (jackpot/winners series, D4)."""
        snapshot = self.get_active(lottery_code=lottery_code, lottery_id=lottery_id)
        rows = (
            self._session.execute(
                select(StatAverage)
                .where(StatAverage.snapshot_id == snapshot.id)
                .order_by(StatAverage.series_key)
            )
            .scalars()
            .all()
        )
        return snapshot, list(rows)

    # --- resolution / validation ---------------------------------------------

    def _persist_new(self, lottery, metric_set: str, payload: dict) -> StatSnapshot:
        """Atomically write a NEW version and its payload, retiring the old active.

        Single atomic commit: create the header (active, locked) with the payload
        in the same transaction, retire the prior ``active`` (design §7), commit.
        On any batch/engine exception the pending state is rolled back and a
        terminal ``failed`` header is persisted (never ``active``/``partial``);
        the error surfaces as ``GenerationError`` (design §3). A retry bumps a
        fresh version — the failed row is never reused.
        """
        version = self._snapshots.next_version(lottery.id, metric_set)
        try:
            snapshot = self._snapshots.create_snapshot(
                lottery_id=lottery.id,
                metric_set=metric_set,
                version=version,
                generator_version=STATS_GENERATOR_VERSION,
                engine_version=self._settings.app_version,
                checksum=payload["checksum"],
                status="active",
                is_locked=True,
                draw_count=payload["draw_count"],
                draws_from=payload["draw_from"],
                draws_to=payload["draws_to"],
            )
            self._payloads.bulk_insert(
                snapshot.id,
                frequencies=payload["frequencies"],
                positions=payload["positions"],
                gaps=payload["gaps"],
                averages=payload["averages"],
                scalars=payload["scalars"],
            )
            self._snapshots.retire_old_active(lottery.id, metric_set, keep_id=snapshot.id)
            self._session.commit()
            return snapshot
        except GenerationError:
            raise
        except Exception as exc:
            self._session.rollback()
            self._mark_failed(lottery.id, metric_set, version)
            raise GenerationError(
                f"statistics generation failed for lottery {lottery.id}: {exc}"
            ) from exc

    def _mark_failed(self, lottery_id: int, metric_set: str, version: str) -> None:
        """Persist a terminal ``failed`` snapshot header (dead metadata only).

        The failed row is written and committed outside the rolled-back payload
        transaction so the audit survives (mirrors import_service ``_mark_failed``).
        It is never ``active``/``partial`` and is never reused/resumed by a later
        retry (design §3)."""
        try:
            self._snapshots.create_snapshot(
                lottery_id=lottery_id,
                metric_set=metric_set,
                version=version,
                generator_version=STATS_GENERATOR_VERSION,
                engine_version=self._settings.app_version,
                checksum="",
                status="failed",
                is_locked=False,
                draw_count=0,
                draws_from=0,
                draws_to=0,
            )
            self._session.commit()
        except Exception:
            self._session.rollback()

    # --- resolution / validation ---------------------------------------------

    def _resolve_lottery(self, *, lottery_code: str | None, lottery_id: int | None) -> object:
        """Resolve the lottery from ``code`` or ``id``; 404-style when absent."""
        lottery = None
        if lottery_code is not None:
            lottery = self._lotteries.get_by_code(lottery_code)
        elif lottery_id is not None:
            lottery = self._lotteries.get(lottery_id)
        if lottery is None:
            raise NotFoundError("lottery does not exist")
        return lottery

    def _resolve_scope(self, scope: str) -> object:
        """Validate the generation scope against ``SCOPES`` (generator module)."""
        if scope not in SCOPES:
            raise ValidationError(f"unsupported scope {scope!r}; expected one of {sorted(SCOPES)}")
        return SCOPES[scope]

    # --- payload computation -------------------------------------------------

    def _compute_payload(self, lottery, metric_set: str) -> dict:
        """Compute the deterministic metric payload over the lottery's draws.

        Reads draws via the batched keyset iterator (design §3) and folds the pure
        engine accumulators (INTEGER/Decimal only, design §9) so two runs over the
        same dataset are byte-identical. Returns a dict carrying the canonical
        ``checksum`` plus the metric structures the payload repository persists.
        """
        draws: list[list[int]] = []
        jackpots: list[object] = []
        winners: list[object] = []
        draw_numbers: list[int] = []
        for draw_number, numbers, jackpot, winner in self._payloads.iter_draws(lottery.id):
            draws.append(numbers)
            draw_numbers.append(draw_number)
            jackpots.append(jackpot)
            winners.append(winner)

        frequencies = {int(n): int(c) for n, c in frequency(draws).items()}
        positions = {
            (int(number), int(position)): int(count)
            for (number, position), count in positional_frequency(draws).items()
        }
        gap_results = engine_gaps(draws)
        gaps: dict[int, tuple[int, int | None, int | None, object]] = {}
        for number, gs in gap_results.items():
            gaps[int(number)] = (gs.count, gs.min_gap, gs.max_gap, gs.avg_gap)

        averages: dict[str, tuple[object, int]] = {}
        for series_key, values in (("jackpot", jackpots), ("winners", winners)):
            mean = null_aware_average(values)
            non_null = sum(1 for value in values if value is not None)
            averages[series_key] = (mean, non_null)

        scalars: dict[str, object] = {
            "entropy": entropy_base2(frequencies, lottery.min_number, lottery.max_number)
        }

        payload = {
            "frequencies": frequencies,
            "positions": positions,
            "gaps": gaps,
            "averages": averages,
            "scalars": scalars,
            "draw_from": draw_numbers[0] if draw_numbers else 0,
            "draws_to": draw_numbers[-1] if draw_numbers else 0,
            "draw_count": len(draws),
        }
        payload["checksum"] = stat_checksum(
            self._checksum_document(lottery.id, metric_set, lottery, payload)
        )
        return payload

    def _checksum_document(self, lottery_id: int, metric_set: str, lottery, payload: dict) -> dict:
        """Build the canonical checksum document (mirrors test_checksum shape).

        Keys are sorted by the serializer; Decimals are stringified so the digest
        never depends on float or JSON precision (design §9: no float in checksum).
        """
        numbers = {str(k): v for k, v in sorted(payload["frequencies"].items())}
        positions = {
            f"{number}:{position}": count
            for (number, position), count in sorted(payload["positions"].items())
        }
        gaps = {}
        for number, (count, min_gap, max_gap, avg_gap) in sorted(payload["gaps"].items()):
            gaps[str(number)] = {
                "count": count,
                "min_gap": min_gap,
                "max_gap": max_gap,
                "avg_gap": str(avg_gap),
            }
        averages = {
            key: {"mean": str(mean), "non_null_count": count}
            for key, (mean, count) in sorted(payload["averages"].items())
        }
        return {
            "lottery_id": lottery_id,
            "metric_set": metric_set,
            "range": {"draws_from": payload["draw_from"], "draws_to": payload["draws_to"]},
            "generator_version": STATS_GENERATOR_VERSION,
            "engine_version": self._settings.app_version,
            "numbers": numbers,
            "positions": positions,
            "gaps": gaps,
            "averages": averages,
            "scalars": {key: str(value) for key, value in sorted(payload["scalars"].items())},
        }
