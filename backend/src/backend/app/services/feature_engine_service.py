"""FeatureEngineService: orchestration, versioning, and the single atomic tx (P2-04/P2-05).

Composition root for the Feature Engine slice. It owns:
- ``build_feature_registry()`` — the canonical registry: the ten Core-Domain features
  FE-01..FE-10 (``source="core"``) plus one ``future-statistics`` feature that is
  declared/versioned but NEVER scheduled (FES-08/design §6). FEATURE_GENERATOR_VERSION
  is pinned in ``feature_engineering/registry.py``; a bump never follows Statistics.
- ``generate()`` — full vs incremental orchestration over the DI session: resolve the
  lottery, validate scope, compute the pure FeatureEngine pass (reads only through the
  draw provider — never ``statistics``/``models``/repo internals, FES-06), fingerprint
  the inputs and checksum the outputs, then persist a NEW version in ONE atomic tx:
  create → lock → retire prior active. On any engine/batch exception it rolls back and
  persists a terminal ``failed`` snapshot — NEVER ``active``/``partial`` (design §7).

Both ``full`` and ``incremental`` recompute over the lottery's full non-deleted draw
set (windowed/tail features depend on the whole series, so a deterministic checksum
requires the whole series both times). The scope difference is purely idempotency:
``incremental`` reuses an existing ``active`` snapshot whose ``input_fingerprint``
matches (no new data → no duplicate version); ``full`` always writes a NEW version.

The service imports ONLY the feature-engine seams (registry/fingerprint) and
repositories; it never imports ``statistics`` internals, preserving the F3→F4
decoupling the provider Protocols enforce at the boundary (design §4).
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from decimal import Decimal

from sqlalchemy.orm import Session

from backend.app.config.settings import get_settings
from backend.app.feature_engineering.context import DrawRow, LotteryRules
from backend.app.feature_engineering.engine import ExecutionResult, FeatureEngine
from backend.app.feature_engineering.features import (
    consecutive_count,
    current_frequency,
    decade_distribution,
    draw_mean,
    draw_range,
    draw_sum,
    low_high_ratio,
    max_current_gap,
    odd_even_ratio,
    repeated_from_previous,
)
from backend.app.feature_engineering.providers import DrawProvider
from backend.app.feature_engineering.registry import (
    FEATURE_GENERATOR_VERSION,
    SOURCE_FUTURE_STATISTICS,
    FeatureDefinition,
    FeatureRegistry,
)
from backend.app.models.feature_snapshot import FeatureSnapshot
from backend.app.repositories.feature_snapshot_repository import FeatureSnapshotRepository
from backend.app.repositories.feature_value_repository import FeatureValueRepository
from backend.app.repositories.lottery_repository import LotteryRepository
from backend.app.services.errors import (
    GenerationError,
    NotFoundError,
    SnapshotNotFoundError,
    ValidationError,
)

# The supported feature bundles and generation scopes (P2-04/P2-05).
FEATURE_SET_CORE: str = "core"
SCOPE_FULL: str = "full"
SCOPE_INCREMENTAL: str = "incremental"
SCOPES: frozenset[str] = frozenset({SCOPE_FULL, SCOPE_INCREMENTAL})

# The value types persisted to the Numeric(20,8) ``feature_values.value`` cell.
# Mapping/sequence returns (FE-07 decade_distribution, FE-10 current_frequency) are
# computed and fingerprinted but carry no scalar cell (design §2, FES-05); float
# never reaches a persisted value.
SIMPLE_SCALAR_TYPES: tuple[type, ...] = (int, Decimal)


def build_feature_registry() -> FeatureRegistry:
    """Return the canonical registry: FE-01..FE-10 (core) + one future-statistics feature.

    Registers the ten deterministic Core-Domain features with their pure ``compute``
    callables (P2-04) and declares one ``future-statistics`` feature that is versioned
    and documented but never scheduled (FES-08 / GF2(b)).
    """

    def _def(
        feature_id: str,
        name: str,
        *,
        inputs: tuple[str, ...],
        algorithm: str,
        complexity: str,
    ) -> FeatureDefinition:
        return FeatureDefinition(
            id=feature_id,
            name=name,
            category="core",
            description=f"{name} ({feature_id}) core-domain feature",
            source="core",
            inputs=inputs,
            algorithm=algorithm,
            params={},
            dependencies=(),
            complexity=complexity,
            version="1.0.0",
            status="active",
            history=(),
        )

    defined = {
        "draw_sum": _def(
            "draw_sum", "Draw Sum", inputs=("numbers",), algorithm="sum", complexity="O(n)"
        ),
        "draw_mean": _def(
            "draw_mean", "Draw Mean", inputs=("numbers",), algorithm="mean", complexity="O(n)"
        ),
        "draw_range": _def(
            "draw_range", "Draw Range", inputs=("numbers",), algorithm="max-min", complexity="O(n)"
        ),
        "odd_even_ratio": _def(
            "odd_even_ratio",
            "Odd/Even Ratio",
            inputs=("numbers",),
            algorithm="odd/even",
            complexity="O(n)",
        ),
        "low_high_ratio": _def(
            "low_high_ratio",
            "Low/High Ratio",
            inputs=("numbers", "rules"),
            algorithm="below/above mid",
            complexity="O(n)",
        ),
        "consecutive_count": _def(
            "consecutive_count",
            "Consecutive Count",
            inputs=("numbers",),
            algorithm="adjacent pairs",
            complexity="O(n log n)",
        ),
        "decade_distribution": _def(
            "decade_distribution",
            "Decade Distribution",
            inputs=("numbers", "rules"),
            algorithm="band counts",
            complexity="O(n)",
        ),
        "repeated_from_previous": _def(
            "repeated_from_previous",
            "Repeated From Previous",
            inputs=("numbers", "draws"),
            algorithm="set overlap prev",
            complexity="O(n)",
        ),
        "max_current_gap": _def(
            "max_current_gap",
            "Max Current Gap",
            inputs=("draws", "rules"),
            algorithm="last-seen gap",
            complexity="O(n * m)",
        ),
        "current_frequency": _def(
            "current_frequency",
            "Current Frequency",
            inputs=("draws",),
            algorithm="cumulative count",
            complexity="O(n)",
        ),
    }
    computes = {
        "draw_sum": draw_sum,
        "draw_mean": draw_mean,
        "draw_range": draw_range,
        "odd_even_ratio": odd_even_ratio,
        "low_high_ratio": low_high_ratio,
        "consecutive_count": consecutive_count,
        "decade_distribution": decade_distribution,
        "repeated_from_previous": repeated_from_previous,
        "max_current_gap": max_current_gap,
        "current_frequency": current_frequency,
    }

    registry = FeatureRegistry()
    for fid, definition in sorted(defined.items()):
        registry.register(definition, computes.get(fid))

    # Declared, versioned, NEVER scheduled (FES-08 / GF2(b) / design §6).
    registry.register(
        FeatureDefinition(
            id="draw_correlation",
            name="Draw-Pair Correlation",
            category="statistics-derived",
            description="Correlation/co-occurrence between numbers (future-statistics)",
            source=SOURCE_FUTURE_STATISTICS,
            inputs=("draws",),
            algorithm="correlation",
            params={},
            dependencies=(),
            complexity="O(n^2)",
            version="1.0.0",
            status="active",
            history=(),
        )
    )
    return registry


class FeatureEngineService:
    """Feature-generation use cases over one DI session transaction (deterministic, atomic)."""

    def __init__(
        self,
        session: Session,
        *,
        registry: FeatureRegistry | None = None,
        provider: DrawProvider | None = None,
    ) -> None:
        self._session = session
        self._registry = registry if registry is not None else build_feature_registry()
        self._engine = FeatureEngine(self._registry)
        self._provider = provider if provider is not None else _SessionDrawProvider(session)
        self._lotteries = LotteryRepository(session)
        self._snapshots = FeatureSnapshotRepository(session)
        self._values = FeatureValueRepository(session)
        self._settings = get_settings()

    # --- generation ------------------------------------------------------------

    def generate(
        self,
        *,
        lottery_code: str | None = None,
        lottery_id: int | None = None,
        feature_set: str = FEATURE_SET_CORE,
        scope: str = SCOPE_INCREMENTAL,
    ) -> FeatureSnapshot:
        """Generate (or idempotently return) the feature snapshot for a lottery.

        ``lottery_code`` or ``lottery_id`` resolves the lottery (404-style when
        absent); ``feature_set`` must be a supported bundle (currently ``core``);
        ``scope`` is one of ``SCOPES``. Both scopes recompute over the full draw set
        and persist a NEW version (old ``active``→``retired``); ``incremental`` returns
        the existing ``active`` snapshot when it already reproduces the exact
        prospective fingerprint (no duplicate version, P2-05).
        """
        lottery = self._resolve_lottery(lottery_code=lottery_code, lottery_id=lottery_id)
        scope_obj = self._resolve_scope(scope)
        if feature_set != FEATURE_SET_CORE:
            raise ValidationError(
                f"unsupported feature_set {feature_set!r}; expected {FEATURE_SET_CORE!r}"
            )

        execution = self._compute_execution(lottery)
        if scope_obj == SCOPE_INCREMENTAL:
            existing = self._snapshots.find_by_fingerprint(
                lottery.id, feature_set, execution.fingerprint
            )
            if existing is not None:
                return existing

        return self._persist_new(lottery, feature_set, execution)

    # --- reads (served from the stored snapshot, never precompute, FES-05/09) ---

    def get_active(
        self,
        *,
        lottery_code: str | None = None,
        lottery_id: int | None = None,
        feature_set: str = FEATURE_SET_CORE,
    ) -> FeatureSnapshot:
        """Return the active ``feature_set`` snapshot for a lottery.

        A missing lottery surfaces ``NotFoundError``; a lottery with no active
        snapshot surfaces ``SnapshotNotFoundError`` (404 SNAPSHOT_NOT_FOUND). Reads
        NEVER trigger a precompute (FES-09).
        """
        lottery = self._resolve_lottery(lottery_code=lottery_code, lottery_id=lottery_id)
        snapshot = self._snapshots.get_active(lottery.id, feature_set)
        if snapshot is None:
            raise SnapshotNotFoundError(
                f"no feature snapshot for lottery {lottery.id!r} (feature_set={feature_set!r})"
            )
        return snapshot

    # --- resolution / validation -----------------------------------------------

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

    def _resolve_scope(self, scope: str) -> str:
        """Validate the generation scope against ``SCOPES``."""
        if scope not in SCOPES:
            raise ValidationError(f"unsupported scope {scope!r}; expected one of {sorted(SCOPES)}")
        return scope

    def _rules(self, lottery) -> LotteryRules:
        """Derive the immutable lottery rules for the engine from the ORM row."""
        return LotteryRules(
            min_number=lottery.min_number,
            max_number=lottery.max_number,
            numbers_to_select=lottery.numbers_to_select,
        )

    # --- payload computation ---------------------------------------------------

    def _compute_execution(self, lottery) -> ExecutionResult:
        """Compute the deterministic feature pass over the lottery's (ordered) draws.

        The engine receives the provider-streamed ``DrawRow`` list; it sorts by
        ``draw_number`` internally (FES-03) and folds the registry's runnable features.
        Only scalar values are persisted; mapping features are fingerprinted (design §2).
        """
        draws = list(self._provider.iter_draws(lottery.id))
        return self._engine.execute(draws, self._rules(lottery), lottery_id=lottery.id)

    def _persist_new(
        self, lottery, feature_set: str, execution: ExecutionResult
    ) -> FeatureSnapshot:
        """Atomically write a NEW version and its values, retiring the old active.

        Single atomic commit: create the header (active, locked) with the deterministic
        ``checksum`` + ``input_fingerprint``, bulk-insert the ``feature_values`` rows,
        retire the prior ``active`` (design §7), flush, commit. Any engine/batch
        exception rolls back and persists a terminal ``failed`` header (never
        ``active``/``partial``) before surfacing ``GenerationError``.
        """
        rows, checksum = self._build_rows(execution)
        version = self._snapshots.next_version(lottery.id, feature_set)
        draw_numbers = execution.draw_numbers
        draws_from = draw_numbers[0] if draw_numbers else 0
        draws_to = draw_numbers[-1] if draw_numbers else 0

        try:
            snapshot = self._snapshots.create_snapshot(
                lottery_id=lottery.id,
                feature_set=feature_set,
                version=version,
                feature_engine_version=FEATURE_GENERATOR_VERSION,
                checksum=checksum,
                input_fingerprint=execution.fingerprint,
                status="active",
                is_locked=True,
                draw_count=len(draw_numbers),
                draws_from=draws_from,
                draws_to=draws_to,
            )
            self._values.bulk_insert(snapshot.id, rows=rows)
            self._snapshots.retire_old_active(lottery.id, feature_set, keep_id=snapshot.id)
            self._session.commit()
            return snapshot
        except GenerationError:
            raise
        except Exception as exc:
            self._session.rollback()
            self._mark_failed(lottery.id, feature_set, version)
            raise GenerationError(
                f"feature generation failed for lottery {lottery.id}: {exc}"
            ) from exc

    def _mark_failed(self, lottery_id: int, feature_set: str, version: str) -> None:
        """Persist a terminal ``failed`` snapshot header (dead metadata only).

        Never ``active``/``partial`` and never reused/resumed by a later retry
        (design §7). Written and committed outside the rolled-back payload tx."""
        try:
            self._snapshots.create_snapshot(
                lottery_id=lottery_id,
                feature_set=feature_set,
                version=version,
                feature_engine_version=FEATURE_GENERATOR_VERSION,
                checksum="",
                input_fingerprint="",
                status="failed",
                is_locked=False,
                draw_count=0,
                draws_from=0,
                draws_to=0,
            )
            self._session.commit()
        except Exception:
            self._session.rollback()

    def _build_rows(
        self, execution: ExecutionResult
    ) -> tuple[list[tuple[str, str, int, object]], str]:
        """Flatten the deterministic scalar `feature_values` rows in insertion order.

        Returns the row list ``(feature_id, feature_version, draw_number, value)``
        sorted by ``(feature_id, draw_number)`` (matching ``bulk_insert`` key order,
        GF1) plus the canonical SHA-256 ``checksum`` over that exact content.
        """
        rows: list[tuple[str, str, int, object]] = []
        for feature_id in sorted(execution.values):
            definition = self._registry.get(feature_id)
            if definition is None:
                raise GenerationError(
                    f"feature '{feature_id}' produced values but is not registered"
                )
            series = execution.values[feature_id]
            for draw_number in sorted(series):
                value = series[draw_number]
                if isinstance(value, SIMPLE_SCALAR_TYPES):
                    rows.append((feature_id, definition.version, draw_number, value))
        checksum = _checksum(rows)
        return rows, checksum


def _checksum(rows: Iterable[tuple[str, str, int, object]]) -> str:
    """Canonical SHA-256 of the persisted ``feature_values`` content (FES-05).

    Serializes each row as ``feature_id|version|draw_number|value`` in the exact
    (already-sorted) order given, so two identical generation runs produce a
    byte-identical checksum (GF1) regardless of DB physical order.
    """
    canonical = json.dumps(
        [tuple((r[0], r[1], r[2], str(r[3]))) for r in rows],
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


# DrawProvider adapter: composition-root seam wrapping the value repository's
# deterministic ``iter_draws`` (order by draw_number, id — design §9).
class _SessionDrawProvider:
    """Read-only DrawProvider over one DI session (FES-06; adapts the value repo)."""

    def __init__(self, session: Session) -> None:
        self._values = FeatureValueRepository(session)

    def iter_draws(
        self,
        lottery_id: int,
        *,
        after_draw_number: int | None = None,
    ) -> Iterable[DrawRow]:
        return self._values.iter_draws(lottery_id, after_draw_number=after_draw_number)


__all__ = [
    "FEATURE_SET_CORE",
    "SCOPE_FULL",
    "SCOPE_INCREMENTAL",
    "SCOPES",
    "FeatureEngineService",
    "build_feature_registry",
]
