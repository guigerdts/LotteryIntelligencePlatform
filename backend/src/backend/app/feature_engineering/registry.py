"""FeatureRegistry: dependency registration, Kahn topo sort, cycle detection (FES-07).

Features register declaratively with an explicit ``dependencies`` tuple. The registry
builds the directed feature-to-dependency graph and runs Kahn topological sort on
registration: if any node remains unresolved, a cycle exists and registration fails-fast
with the offending set — none of the cycle members registered (design §6 / FES-07). A
feature whose dependency is ``disabled``/``future``/``failed`` (or that is itself a
``future-statistics`` source) is ``skipped`` and never guessed (FES-07/FES-08).
"""

from __future__ import annotations

from collections import defaultdict, deque
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Final

# Feature Engine algorithm identity (design §6, spec FES-04). Independent of
# ``STATS_GENERATOR_VERSION`` (a bump on one never bumps the other). Bump ONLY when the
# engine's algorithm/meaning/params change the persisted output; internal changes that
# leave output byte-identical do NOT bump. Mirrors Statistics' ``STATS_GENERATOR_VERSION``.
FEATURE_GENERATOR_VERSION: Final = "1.0.0"

# Feature status values (design §6 / FES-07): a dependency with any of these blocks its
# dependents from the run stream. ``FUTURE`` also marks ``source == 'future-statistics'``
# definitions that are declared and versioned but never scheduled (FES-08).
DISABLED: Final = "disabled"
FAILED: Final = "failed"
FUTURE: Final = "future"

# Sources (design §6 / FES-08). ``source == 'future-statistics'`` is never scheduled.
SOURCE_CORE: Final = "core"
SOURCE_STATISTICS: Final = "statistics"
SOURCE_FUTURE_STATISTICS: Final = "future-statistics"
SOURCE_META: Final = "meta"

# A dependency with one of these statuses halts its dependents (FES-07).
_BLOCK_STATUSES: Final = frozenset({DISABLED, FAILED, FUTURE})
_BLOCK = _BLOCK_STATUSES


class FeatureCycleError(Exception):
    """A feature dependency graph contains a directed cycle.

    ``cycle`` is the reported offending set (the unresolved Kahn residual). When this is
    raised the new definition is NOT registered (fail-fast, design §6).
    """

    def __init__(self, cycle: set[str]) -> None:
        self.cycle: set[str] = cycle
        super().__init__(f"feature dependency cycle detected: {sorted(cycle)}")


@dataclass(frozen=True)
class FeatureDefinition:
    """Immutable declaration of one feature (design §6 / exploration §10)."""

    id: str
    name: str
    category: str
    description: str
    source: str = SOURCE_CORE
    inputs: tuple[str, ...] = ()
    algorithm: str = ""
    params: Mapping[str, object] = field(default_factory=dict)
    dependencies: tuple[str, ...] = ()
    complexity: str = ""
    version: str = "1.0.0"
    status: str = "active"
    history: tuple[str, ...] = ()


class FeatureRegistry:
    """Holds feature declarations + pure ``compute`` callables; resolves the run order.

    ``register`` records a definition (and optional compute) then re-runs Kahn over the
    whole graph. A new cycle raises ``FeatureCycleError`` and the new definition is NOT
    kept. ``topological_order`` returns the runnable feature ids in dependency order;
    ``skipped`` returns the ids excluded because they are future-statistics sourced or
    depend on a disabled/future/failed feature (all FES-07/FES-08).
    """

    def __init__(self) -> None:
        self._definitions: dict[str, FeatureDefinition] = {}
        self._computes: dict[str, Callable] = {}

    def register(
        self,
        definition: FeatureDefinition,
        compute: Callable | None = None,
    ) -> FeatureDefinition:
        """Register a feature definition (fail-fast on a dependency cycle).

        Re-runs Kahn over the candidate graph; a newly introduced cycle raises
        ``FeatureCycleError`` and keeps nothing new (design §6).
        """
        candidate = dict(self._definitions)
        candidate[definition.id] = definition
        # Fail-fast: if adding this def creates a cycle, raise and keep nothing new.
        self._check_acyclic(candidate)
        self._definitions = candidate
        if compute is not None:
            self._computes[definition.id] = compute
        return definition

    def _check_acyclic(self, definitions: Mapping[str, FeatureDefinition]) -> None:
        indegree: dict[str, int] = {fid: 0 for fid in definitions}
        dependents: dict[str, list[str]] = defaultdict(list)
        for fid, defn in definitions.items():
            for dep in defn.dependencies:
                if dep in definitions:
                    dependents[dep].append(fid)
                    indegree[fid] += 1
        queue: deque[str] = deque(fid for fid, d in indegree.items() if d == 0)
        resolved: list[str] = []
        while queue:
            node = queue.popleft()
            resolved.append(node)
            for dependent in dependents[node]:
                indegree[dependent] -= 1
                if indegree[dependent] == 0:
                    queue.append(dependent)
        unresolved = set(definitions) - set(resolved)
        if unresolved:
            raise FeatureCycleError(unresolved)

    def get(self, feature_id: str) -> FeatureDefinition | None:
        """Return the registered definition for ``feature_id`` or ``None``."""
        return self._definitions.get(feature_id)

    def compute(self, feature_id: str) -> Callable | None:
        """Return the registered compute callable for ``feature_id`` or ``None``."""
        return self._computes.get(feature_id)

    def definitions(self) -> Mapping[str, FeatureDefinition]:
        """Return a read-only mapping of all registered feature definitions."""
        return self._definitions

    def iter_computable(self) -> list[str]:
        """Return runnable (non-skipped) feature ids in dependency order."""
        skipped = self.skipped()
        runnable = [fid for fid in self._definitions if fid not in skipped]
        return self._kahn(runnable)

    def topological_order(self) -> list[str]:
        """Alias of ``iter_computable`` kept for spec/task parity (P1-03)."""
        return self.iter_computable()

    def skipped(self) -> set[str]:
        """Return the feature ids excluded from the run stream (FES-07/FES-08).

        A feature is skipped if it is ``future-statistics`` sourced, or if any of its
        declared dependencies is not registered or is disabled/future/failed/blocked.
        """
        out: set[str] = set()
        for fid, defn in self._definitions.items():
            if defn.source in (SOURCE_FUTURE_STATISTICS, FUTURE):
                out.add(fid)
                continue
            for dep in defn.dependencies:
                dep_defn = self._definitions.get(dep)
                if dep_defn is None:
                    out.add(fid)
                    break
                if dep_defn.source == SOURCE_FUTURE_STATISTICS or dep_defn.status in _BLOCK:
                    out.add(fid)
                    break
                if dep in out:
                    out.add(fid)
                    break
        return out

    def _kahn(self, ids: list[str]) -> list[str]:
        present = set(ids)
        indegree: dict[str, int] = {fid: 0 for fid in ids}
        dependents: dict[str, list[str]] = defaultdict(list)
        for fid in ids:
            defn = self._definitions[fid]
            for dep in defn.dependencies:
                if dep in present:
                    dependents[dep].append(fid)
                    indegree[fid] += 1
        queue: deque[str] = deque(fid for fid, d in indegree.items() if d == 0)
        order: list[str] = []
        pending = set(ids)
        while queue:
            node = queue.popleft()
            order.append(node)
            pending.discard(node)
            for dependent in dependents[node]:
                indegree[dependent] -= 1
                if indegree[dependent] == 0:
                    queue.append(dependent)
        if pending:  # pragma: no cover - only reachable if skipped() misclassified
            raise FeatureCycleError(pending)
        return order
