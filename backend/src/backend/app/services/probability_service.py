"""ProbabilityService: orchestration, versioning, and atomic tx (PES-07/D-A3).

Composition root for the Probability Engine slice. It owns:
- ``generate()`` — full vs incremental orchestration: resolve lottery, compute
  provider data, execute engine over registered methods, fingerprint + checksum,
  persist NEW version in ONE atomic tx. On error → terminal ``failed`` snapshot.
- ``read()`` — served from stored snapshot only, never precompute (PES-08).

Reads Core/``stat_*``/``feature_*`` ONLY via own Provider Protocols (PES-6);
writes ONLY ``prob_*`` (PES-01/02).
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from decimal import Decimal

from sqlalchemy.orm import Session

from backend.app.config.settings import get_settings
from backend.app.models.prob_snapshot import ProbSnapshot
from backend.app.models.prob_value import ProbValue
from backend.app.probability.determinism import derive_seed, isolated_rng
from backend.app.probability.engine import (
    bayes,
    binomial,
    conditional,
    empirical,
    hypergeometric,
    monte_carlo,
    poisson,
)
from backend.app.probability.fingerprint import probability_input_fingerprint
from backend.app.probability.providers import (
    DrawReader,
    FeatureSnapshotReader,
    LotteryRules,
    StatSnapshotReader,
)
from backend.app.probability.registry import ProbMethodRegistry, build_prob_registry
from backend.app.probability.snapshot_store import SnapshotStore
from backend.app.services.errors import (
    GenerationError,
    NotFoundError,
    SnapshotNotFoundError,
    ValidationError,
)

# Supported model bundles and scopes (mirrors F3/F4).
PROB_MODEL_SET_CORE: str = "core"
SCOPE_FULL: str = "full"
SCOPE_INCREMENTAL: str = "incremental"
SCOPES: frozenset[str] = frozenset({SCOPE_FULL, SCOPE_INCREMENTAL})


class ProbabilityService:
    """Probability generation use cases over one DI session transaction."""

    def __init__(
        self,
        session: Session,
        *,
        registry: ProbMethodRegistry | None = None,
        draw_reader: DrawReader | None = None,
        stats_reader: StatSnapshotReader | None = None,
        feature_reader: FeatureSnapshotReader | None = None,
    ) -> None:
        self._session = session
        self._registry = registry if registry is not None else build_prob_registry()
        self._draw_reader = draw_reader
        self._stats_reader = stats_reader
        self._feature_reader = feature_reader
        self._store = SnapshotStore(session)
        self._settings = get_settings()

    # --- generation -----------------------------------------------------------

    def generate(
        self,
        *,
        lottery_code: str | None = None,
        lottery_id: int | None = None,
        model_set: str = PROB_MODEL_SET_CORE,
        scope: str = SCOPE_INCREMENTAL,
    ) -> ProbSnapshot:
        """Generate (or idempotently return) the probability snapshot for a lottery.

        ``scope=incremental`` returns existing active snapshot when fingerprint
        matches; ``scope=full`` always writes a NEW version (PES-04).
        """
        lottery = self._resolve_lottery(lottery_code=lottery_code, lottery_id=lottery_id)
        lid = lottery.id
        self._validate_scope(scope)
        if model_set != PROB_MODEL_SET_CORE:
            raise ValidationError(
                f"unsupported model_set {model_set!r}; expected {PROB_MODEL_SET_CORE!r}"
            )

        # Compute the engine pass.
        execution = self._compute_execution(lottery)

        # Idempotent incremental: same fingerprint → existing active (PES-04).
        if scope == SCOPE_INCREMENTAL:
            existing = self._store.find_by_fingerprint(lid, model_set, execution["fingerprint"])
            if existing is not None:
                return existing

        return self._persist_new(lid, model_set, execution)

    # --- reads (never precompute, PES-08) ------------------------------------

    def get_active(
        self,
        *,
        lottery_code: str | None = None,
        lottery_id: int | None = None,
        model_set: str = PROB_MODEL_SET_CORE,
    ) -> ProbSnapshot:
        """Return the active snapshot; 404 when absent."""
        lottery = self._resolve_lottery(lottery_code=lottery_code, lottery_id=lottery_id)
        snapshot = self._store.get_active(lottery.id, model_set)
        if snapshot is None:
            raise SnapshotNotFoundError(
                f"no prob snapshot for lottery {lottery.id!r} (model_set={model_set!r})"
            )
        return snapshot

    def read_values(
        self,
        *,
        lottery_code: str | None = None,
        lottery_id: int | None = None,
        model: str | None = None,
        subject: str | None = None,
        last: int = 0,
    ) -> tuple[ProbSnapshot, list[ProbValue]]:
        """Return the active snapshot and its persisted prob_values (PES-08 read)."""
        snapshot = self.get_active(lottery_code=lottery_code, lottery_id=lottery_id)
        rows = self._store.values_for_snapshot(snapshot.id, model=model, subject=subject, last=last)
        return snapshot, rows

    # --- internal -------------------------------------------------------------

    def _resolve_lottery(self, *, lottery_code: str | None, lottery_id: int | None) -> object:
        """Resolve the lottery from code or id; 404-style when absent."""
        from backend.app.repositories.lottery_repository import LotteryRepository

        repo = LotteryRepository(self._session)
        lottery = None
        if lottery_code is not None:
            lottery = repo.get_by_code(lottery_code)
        elif lottery_id is not None:
            lottery = repo.get(lottery_id)
        if lottery is None:
            raise NotFoundError("lottery does not exist")
        return lottery

    def _validate_scope(self, scope: str) -> None:
        if scope not in SCOPES:
            raise ValidationError(f"unsupported scope {scope!r}; expected one of {sorted(SCOPES)}")

    def _compute_execution(self, lottery) -> dict:
        """Compute the deterministic probability pass over the lottery's draws.

        Returns dict with: values, fingerprint, checksum, draw_numbers, draw_range.
        """
        from datetime import date

        lid = lottery.id

        # Collect draws via Provider Protocol.
        draws = list(self._draw_reader.iter_draws(lid))
        draw_numbers = sorted(d.draw_number for d in draws)
        draws_from = draw_numbers[0] if draw_numbers else 0
        draws_to = draw_numbers[-1] if draw_numbers else 0

        rules = LotteryRules(
            min_number=lottery.min_number,
            max_number=lottery.max_number,
            numbers_to_select=lottery.numbers_to_select,
        )

        # Read statistical snapshots via Provider Protocol.
        stats_ref = self._stats_reader.active(lid) if self._stats_reader else None
        stat_frequencies: dict[int, int] = {}
        if stats_ref is not None:
            stat_frequencies = dict(self._stats_reader.frequencies(stats_ref.snapshot_id))

        # Read feature snapshot via Provider Protocol.
        feature_ref = self._feature_reader.active(lid) if self._feature_reader else None

        # Execute all registered methods.
        all_values: dict[str, dict] = {}
        for method_id in self._registry.ids():
            definition = self._registry.get(method_id)
            if definition is None:
                continue
            params = dict(definition.params)
            try:
                if method_id == "hypergeometric":
                    N = rules.max_number - rules.min_number + 1
                    n = rules.numbers_to_select
                    r = params.get("r") or n
                    raw = hypergeometric(N, n, r)
                    all_values[method_id] = {"dist": raw, "params": params}
                elif method_id == "binomial":
                    n = params.get("n") or 10
                    p = Decimal(str(params.get("p") or 0.5))
                    raw = binomial(n, p)
                    all_values[method_id] = {"dist": raw, "params": params}
                elif method_id == "poisson":
                    lam = Decimal(str(params.get("lam") or 2.0))
                    kmax = params.get("kmax") or 10
                    raw = poisson(lam, kmax)
                    all_values[method_id] = {"dist": raw, "params": params}
                elif method_id == "empirical":
                    total = sum(stat_frequencies.values()) if stat_frequencies else 0
                    raw = empirical(stat_frequencies, total) if total > 0 else {}
                    all_values[method_id] = {"freq": raw, "params": params}
                elif method_id == "monte_carlo":
                    seed = derive_seed(
                        input_fingerprint="pending",
                        model_params=params,
                        n_simulations=params.get("n_simulations", 10000),
                    )
                    rng = isolated_rng(seed)
                    raw = monte_carlo(rng, rules, params)
                    all_values[method_id] = {"mc": raw, "params": params}
                elif method_id == "bayes":
                    prior_raw = params.get("prior")
                    likelihood_raw = params.get("likelihood")
                    prior = prior_raw if isinstance(prior_raw, dict) else {"0": 0.5, "1": 0.5}
                    likelihood = likelihood_raw if isinstance(likelihood_raw, dict) else {"0": 0.8, "1": 0.2}
                    raw = bayes(prior, likelihood)
                    all_values[method_id] = {"posterior": raw, "params": params}
                elif method_id == "conditional":
                    window_raw = params.get("window")
                    window = window_raw if isinstance(window_raw, dict) else {}
                    window_size = params.get("window_size") or 10
                    raw = conditional(window, window_size)
                    all_values[method_id] = {"cond": raw, "params": params}
            except Exception as exc:
                raise GenerationError(f"method {method_id!r} failed: {exc}") from exc

        # Compute fingerprint (needs final values for MC seed recalculation).
        input_data = {
            "lottery_id": lid,
            "draws_from": draws_from,
            "draws_to": draws_to,
            "draw_count": len(draw_numbers),
            "model_set": "core",
            "methods": list(sorted(all_values.keys())),
            "params": {k: v.get("params", {}) for k, v in all_values.items()},
        }
        fingerprint = probability_input_fingerprint(input_data)

        # Re-derive MC seed with actual fingerprint.
        if "monte_carlo" in all_values:
            mc_params = all_values["monte_carlo"]["params"]
            seed = derive_seed(
                input_fingerprint=fingerprint,
                model_params=mc_params,
                n_simulations=mc_params.get("n_simulations", 10000),
            )
            rng = isolated_rng(seed)
            all_values["monte_carlo"]["mc"] = monte_carlo(rng, rules, mc_params)

        # Build rows and checksum.
        rows, checksum = self._build_rows(all_values)

        return {
            "fingerprint": fingerprint,
            "checksum": checksum,
            "draw_numbers": draw_numbers,
            "draws_from": draws_from,
            "draws_to": draws_to,
            "rows": rows,
        }

    def _persist_new(self, lottery_id: int, model_set: str, execution: dict) -> ProbSnapshot:
        """Atomically write a NEW version and its values, retiring the old active."""
        version = self._store.next_version(lottery_id, model_set)
        rows = execution["rows"]

        try:
            snapshot = self._store.create_snapshot(
                lottery_id=lottery_id,
                model_set=model_set,
                version=version,
                prob_generator_version="1.0.0",
                checksum=execution["checksum"],
                input_fingerprint=execution["fingerprint"],
                status="active",
                is_locked=True,
                draw_count=len(execution["draw_numbers"]),
                draws_from=execution["draws_from"],
                draws_to=execution["draws_to"],
            )
            self._store.bulk_insert_values(snapshot.id, rows)
            self._store.retire_old_active(lottery_id, model_set, keep_id=snapshot.id)
            self._session.commit()
            return snapshot
        except GenerationError:
            raise
        except Exception as exc:
            self._session.rollback()
            self._mark_failed(lottery_id, model_set, version)
            raise GenerationError(
                f"probability generation failed for lottery {lottery_id}: {exc}"
            ) from exc

    def _mark_failed(self, lottery_id: int, model_set: str, version: str) -> None:
        """Persist a terminal failed snapshot header (dead metadata only)."""
        try:
            self._store.create_snapshot(
                lottery_id=lottery_id,
                model_set=model_set,
                version=version,
                prob_generator_version="1.0.0",
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
        self, all_values: dict
    ) -> tuple[list[ProbValue], str]:
        """Flatten all method values into ProbValue rows and compute checksum."""
        rows: list[ProbValue] = []
        for method_id in sorted(all_values.keys()):
            data = all_values[method_id]
            params = data.get("params", {})
            # Flatten distributions into (subject, draw_number, value) rows.
            if "dist" in data:
                for k, prob in data["dist"]:
                    rows.append(ProbValue(
                        model_id=method_id,
                        model_version="1.0.0",
                        subject=str(k),
                        draw_number=None,
                        value=prob if isinstance(prob, Decimal) else Decimal(str(prob)),
                        params_json=json.dumps(params, sort_keys=True, separators=(",", ":")),
                    ))
            elif "freq" in data:
                for num, prob in data["freq"].items():
                    rows.append(ProbValue(
                        model_id=method_id,
                        model_version="1.0.0",
                        subject=str(num),
                        draw_number=None,
                        value=prob if isinstance(prob, Decimal) else Decimal(str(prob)),
                        params_json=json.dumps(params, sort_keys=True, separators=(",", ":")),
                    ))
            elif "mc" in data:
                mc = data["mc"]
                for key in ("mean", "p50", "p90", "p99"):
                    if key in mc:
                        rows.append(ProbValue(
                            model_id=method_id,
                            model_version="1.0.0",
                            subject=key,
                            draw_number=None,
                            value=mc[key] if isinstance(mc[key], Decimal) else Decimal(str(mc[key])),
                            params_json=json.dumps(params, sort_keys=True, separators=(",", ":")),
                        ))
            elif "posterior" in data:
                for state, prob in data["posterior"].items():
                    rows.append(ProbValue(
                        model_id=method_id,
                        model_version="1.0.0",
                        subject=str(state),
                        draw_number=None,
                        value=prob if isinstance(prob, Decimal) else Decimal(str(prob)),
                        params_json=json.dumps(params, sort_keys=True, separators=(",", ":")),
                    ))
            elif "cond" in data:
                for val, prob in data["cond"].items():
                    rows.append(ProbValue(
                        model_id=method_id,
                        model_version="1.0.0",
                        subject=str(val),
                        draw_number=None,
                        value=prob if isinstance(prob, Decimal) else Decimal(str(prob)),
                        params_json=json.dumps(params, sort_keys=True, separators=(",", ":")),
                    ))

        checksum = _checksum(rows)
        return rows, checksum


def _checksum(rows: Iterable[ProbValue]) -> str:
    """Canonical SHA-256 of the persisted prob_values content (PES-05)."""
    canonical = json.dumps(
        [
            (r.model_id, r.model_version, r.subject, str(r.value))
            for r in rows
        ],
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


__all__ = [
    "PROB_MODEL_SET_CORE",
    "SCOPE_FULL",
    "SCOPE_INCREMENTAL",
    "SCOPES",
    "ProbabilityService",
]
