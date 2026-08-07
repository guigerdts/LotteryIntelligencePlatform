# Exploration — Feature Engine (Fase 4)

**Change**: `fase-4-feature-engine` · **Store**: `openspec` · **Date**: 2026-08-07
**Artifact**: exploration (READ-ONLY investigation; no proposal/spec/design/tasks/code)

---

## Executive Summary

The Feature Engine (Fase 4) has a clean, evidence-backed path: the Statistics
Engine (Fase 3) already shipped a **stable, versioned, checksummed snapshot
contract** (`stat_snapshots` + `stat_*` payload tables, `STATS_GENERATOR_VERSION`
"1.0.0", canonical SHA-256 determinism, `active | retired | failed` lifecycle)
that the Feature Engine can consume through an interface **without any coupling
to Statistics' internals or its completeness**. The Core Domain (`draw`,
`draw_numbers`, `lottery` rules) plus the same deterministic read pattern
(`ORDER BY draw.draw_number, draw_numbers.id`) covers a large first slice
(pure per-draw features and windowed frequency features) that needs **no
statistics at all**. Pending Fase 3 metrics (distributions, trends,
correlations) map to explicit "future-sourced" features that the engine can
**declare and register but not compute** until Statistics publishes them.
The recommended first slice is: registry + provider interfaces + DAG-free
deterministic base features (Core-Domain-sourced) + a feature snapshot
persistence layer mirroring the `stat_*` pattern. See "Recommended scope".

---

## 1. Objective 1 — Minimum stable contract Statistics must expose

Evidence:
- `backend/src/backend/app/statistics/generator.py:17` — `STATS_GENERATOR_VERSION = "1.0.0"`, bumped ONLY on metric interpretation change (§8 design).
- `backend/src/backend/app/statistics/generator.py:21` — `CORE_METRICS = {frequency, positions, gaps, averages, entropy}` — the exact metric bundle delivered.
- `backend/src/backend/app/models/stat_snapshot.py` — header columns: `lottery_id`, `metric_set`, `version`, `generator_version`, `engine_version`, `checksum` (SHA-256, 64), `status` (`active|retired|failed`), `is_locked`, `draw_count`, `draws_from`, `draws_to`. UNIQUE `(lottery_id, metric_set, version)`.
- Payload tables: `stat_frequency` (number, count), `stat_frequency_positions` (number, position, count), `stat_gaps` (count, min_gap, max_gap, avg_gap), `stat_averages` (series_key, mean, non_null_count), `stat_scalars` (name, value — e.g. `entropy`).
- `backend/src/backend/app/repositories/stat_snapshot_repository.py:31` — `get_active(lottery_id, metric_set)` — one `active` row per (lottery, metric_set).
- `backend/src/backend/app/services/statistics_service.py:107-173` — read surface: `get_active`, `read_frequencies`, `read_gaps`, `read_averages`; reads NEVER precompute (STE-10/C5); missing snapshot → `SnapshotNotFoundError` (404 SNAPSHOT_NOT_FOUND).
- `openspec/specs/statistics-engine/spec.md` STE-01..13 — dedicated `stat_*` schema, strict read-only over Core, `draw_number` time axis, generator_version + no in-place recompute, bit-identical determinism, incremental vs full, NULL-never-imputed, batched streaming, multi-lottery, manual update only.

**Minimum contract (what a `StatisticsProvider` interface must expose — stable seams):**

1. **Snapshot identity**: `(lottery_id, metric_set='core') → active snapshot {version, generator_version, checksum, draws_from, draws_to, draw_count, is_locked}`. This is the *input fingerprint* for stats-sourced features (checksum + generator_version + range).
2. **Metric payload reads** (semantic, not table-bound): per-number frequencies; per-(number, position) frequencies; per-number gap summaries; series averages (jackpot/winners); dataset scalars (entropy). Returned as deterministic ordered structures (number ASC, (number, position) ASC, series_key ASC, name ASC — the insertion-order contract in `stat_payload_repository.py:111-170`).
3. **Availability semantics**: reads resolve the active snapshot only; no snapshot → explicit "not available" (not an error the Feature Engine must guess). The engine must be able to detect "Statistics present + core snapshot available" and otherwise skip stats-sourced features gracefully.
4. **No precompute**: the provider MUST NOT trigger generation (STE-10); the Feature Engine treats Statistics as a passive read source.

**Contract stability guarantee**: `checksum` + `generator_version` + draw range fully identify a snapshot's content — the Feature Engine never needs to know *which* metrics exist beyond what it declares per feature.

---

## 2. Objective 2 — Features computable with ONLY the Core Domain (no Statistics)

Evidence: `draw` (draw_number, draw_date, jackpot, winners, is_deleted), `draw_numbers` (position, number, UNIQUE(draw_id, position), UNIQUE(draw_id, number)) in `backend/src/backend/app/models/draw.py`, `draw_number.py`; lottery rule columns in `models/lottery.py` (`min_number`, `max_number`, `numbers_to_select`, super range); deterministic read pattern `stat_payload_repository.iter_draws` (`ORDER BY draw.draw_number, draw_numbers.id`, batched, `is_deleted=False`).

| FEATURE_ENGINEERING.md family | Features | Source (Core only) |
|---|---|---|
| §6 Draw identity | parity (pairs/odds), primes, Fibonacci, multiples of 3/5, high/low counts | Pure function over ONE draw's `numbers`; lottery rules from `lottery` row |
| §7 Distributions (per-draw) | sum, mean, median, mode, range, variance, std, skew, kurtosis of a draw's numbers | Pure per-draw statistics over the draw's `numbers` |
| §9 Tens | distribution across 1–10, 11–20, 21–30, 31–40, 41–43 | Pure bucketing over `numbers`; band boundaries from lottery rules |
| §5 Group A (windowed) | frequency last 10/25/50/100 | Rolling window over `draw_number`-ordered draws (DrawProvider bounded read) |
| §5 Group A (current) | current gap ("age" of number), consecutive appearances | Tail of the draw series (last-N draws); requires only draws |
| §11 Time series (subset) | SMA, EMA, momentum, slope, acceleration over draw_number series | Rolling window transforms over the draw series (pure) |

Notes:
- `jackpot`/`winners` are raw draw columns (`draw.py:38-39`) — jackpot-averages features can consume Core directly; `stat_averages` is the precomputed alternative.
- The deterministic read iterator (`stat_payload_repository.iter_draws`, lines 43-109) is the pattern to reuse; the Feature Engine should own an equivalent keyset iterator in its own provider rather than importing the statistics repository.

---

## 3. Objective 3 — Features that REQUIRE Statistics (map onto existing `stat_*` data)

| FEATURE_ENGINEERING.md item | stat_* source | Table/column evidence |
|---|---|---|
| Group A historical frequency | `stat_frequency` (number, count) | `models/stat_frequency.py` |
| Group A gap average | `stat_gaps.avg_gap` | `models/stat_gap.py` (Numeric(20,6), D4 NULL semantics) |
| Group A gap max / min | `stat_gaps.max_gap` / `min_gap` | same |
| Group A gap count | `stat_gaps.count` | same |
| §8 per-position frequency | `stat_frequency_positions` | `models/stat_frequency_position.py` |
| §7 dataset entropy | `stat_scalars('entropy')` | `models/stat_scalar.py`; `engine.py:110-128` entropy_base2 |
| jackpot/winners means | `stat_averages` (series_key, mean, non_null_count) | `models/stat_average.py` |

These are one-to-one with the delivered `core` bundle (`generator.CORE_METRICS`). **Important**: the Feature Engine should NOT hard-code these table names — it declares per-feature *input selectors* against the provider contract (e.g. `input: {source: statistics, metric: frequency}`), so the mapping stays declarative.

---

## 4. Objective 4 — Features that must WAIT for future Statistics versions

Roadmap evidence: `IMPLEMENTATION_ROADMAP.md:141-146` — pending Fase 3 slices: Distribuciones, Tendencias, Entropía (see discrepancy note), Correlaciones.
> **Doc discrepancy found**: roadmap line 145 lists "Entropía" as pending, but `statistics/engine.py:110-128` (`entropy_base2`) and `generator.py:21` (`CORE_METRICS` includes `entropy`) show **entropy is already delivered** in `core`. The roadmap's "Pendiente" list is stale on this point. Flag for the user; do not treat entropy as future-sourced.

Future-sourced (declare now, compute when Statistics publishes):

| FEATURE_ENGINEERING.md item | Requires (pending Fase 3) |
|---|---|
| §7 cross-draw distribution moments (dataset-level skew/kurtosis/distribution) | "Distribuciones" pending |
| §8 per-position mean/dev/trend/entropy | per-position moments + "Tendencias"/"Entropía" pending |
| §11 trend (dataset trend indicator) | "Tendencias" pending |
| Co-occurrence/relationship matrices (§10) | "Correlaciones" + Graph Engine (Fase 6) |

The engine must register these features with `status: future` / `source: future-statistics` so they are **declared, documented, and versioned** but not scheduled for computation — satisfying constraint #3/#4 (extensibility without depending on Statistics completeness).

---

## 5. Objective 5 — Versioning features INDEPENDENTLY of `generator_version`

Precedent: `statistics/generator.py` + `checksum.py` (canonical `sort_keys=True` SHA-256) + `stat_snapshots` storing `generator_version` + `engine_version` side-by-side for audit (design §8: "independent values").

Proposed scheme (decoupled by construction):
- **Per-feature version**: each feature definition carries its own `feature_version` (FEATURE_ENGINEERING.md §16: ID, Version, Date, Author, Status, History). Bumped ONLY when that feature's meaning/algorithm/params change — never because Statistics bumped `generator_version`.
- **Feature-set snapshot**: a generation is identified by `(feature_set_id, feature_set_version)`; the header stores:
  - `feature_engine_version` (this engine's algorithm identity, audit only),
  - `feature_set_checksum` (SHA-256 over the ordered set of {feature_id, feature_version, params}),
  - `input_fingerprint` (see Objective 6).
- **No coupling**: a Statistics metric bump changes the snapshot `checksum` (the input fingerprint), which triggers *recomputation of affected features* — but the feature versions themselves do NOT bump. The engine compares input fingerprints, not generator_version strings.
- **Determinism/reproducibility** (FEATURE_ENGINEERING.md §2): same {draws checksum, snapshot checksum, feature set checksum} ⇒ same feature outputs, byte-identical.

---

## 6. Objective 6 — Determinism with MULTIPLE sources

Extend the G9-style contract (`openspec/specs/statistics-engine/spec.md` STE-05, design §9: mandatory `ORDER BY draw.draw_number, draw_numbers.id`, no unordered float reduction, `Decimal`-exact accumulators, canonical JSON serialization):

Each feature's computation is keyed by an **input fingerprint** = canonical SHA-256 of:
1. **Draw-set fingerprint**: `(lottery_id, draw_range[from,to], draw_set_checksum)` — the Core-Domain draws in `ORDER BY draw_number, id`.
2. **Stats fingerprint** (when stats-sourced): `(snapshot.checksum, snapshot.generator_version, snapshot.draws_from, snapshot.draws_to)` — the snapshot identity itself is the content proof.
3. **Feature version + parameters**: `(feature_id, feature_version, params)`.
4. **Feature-set checksum** (for meta-features that depend on other features): the ordered dependency outputs' fingerprints.

Rules to guarantee byte-identical outputs:
- Every accumulation uses INTEGER/`Decimal`-exact arithmetic; float never enters a checksum or a persisted feature value (mirrors design §9).
- Every iteration is explicitly ordered (never physical row order).
- Canonical serialization `json.dumps(sort_keys=True, separators=(",", ":"))` for all fingerprints (reuse `stat_checksum` pattern, `checksum.py:18-27`).
- Store the computed fingerprint on each feature snapshot for auditability/repro.

---

## 7. Objective 7 — Registering inter-feature dependencies WITHOUT cycles

Evidence: FEATURE_ENGINEERING.md §14 (Meta Features derive from other variables), §19 (auto-recorded dependencies).

Proposal:
- **Dependencies as first-class metadata** in each feature definition: `dependencies: [feature_id, ...]` (declarative, FEATURE_ENGINEERING.md §3 "Dependencias").
- **Registration-time validation**: on registry load, build the dependency graph and run cycle detection (DFS/Kahn topological sort). A cycle → registration error, the offending set is reported, nothing is registered (fail-fast, mirrors the engine's "never active/partial" fail policy philosophy).
- **Topological execution order**: the engine sorts enabled features topologically; a feature computes only after all its dependencies have a valid value in the same feature-set (or a prior one).
- **Meta-features** (§14) are ordinary features with dependencies — no special-casing: `avg_of_gaps` depends on `gap_current_*`; `change_of_score` depends on `score_*`, etc.
- **Disabled dependency handling**: a feature whose dependency is disabled/failed → itself becomes `skipped` (never silently computed with stale inputs).

---

## 8. Objective 8 — Hundreds/thousands of features WITHOUT coupling the engine

Evidence: FEATURE_ENGINEERING.md §3 (module-per-feature), §20 (thousands of features, extensible ecosystem), ENGINE_SPECIFICATIONS.md §7 (incremental, parallelizable, versioned, reproducible), SYSTEM_ARCHITECTURE.md:234-239 (independent components, decoupled), DATABASE_SCHEMA.md:159-185 (feature_definition / feature_value precedent).

Proposal (registry + declarative definitions + provider seams):
- **Registry pattern**: a `FeatureRegistry` maps `feature_id → FeatureDefinition {id, name, category, description, inputs, algorithm, params, dependencies, complexity, result, version, status, source}`. The engine iterates the registry; it never hard-codes feature implementations.
- **Plugin/module-per-feature**: each feature is a small module under `backend/src/backend/app/feature_engineering/features/<id>.py` exporting a pure `compute(context) -> FeatureValue` (mirrors `statistics/engine.py` pure-function pattern). Registration is declarative (registry list), no engine modification.
- **Provider interfaces**: `DrawProvider`, `StatisticsProvider`, `DatasetProvider` (interfaces only — see contract sketch below) — the ONLY data-access seams; features consume providers, never repositories/models directly.
- **Batched/incremental computation**: features compute per feature-set (snapshot) with draw-range bounds; delta computation folds new draws like `statistics` incremental (STE-06 pattern). Parallelizable per feature (independent features run concurrently; dependencies gate via topo order) — ENGINE_SPECIFICATIONS §7.
- **Persistence in a dedicated `feature_*` schema**: mirror the `stat_*` pattern — `feature_snapshots` (header: lottery_id, feature_set, version, feature_engine_version, checksum, input_fingerprint, status, is_locked, draw_count, draws_from, draws_to) + `feature_values` (snapshot_id, feature_id, draw_key | None, value — tabular, deterministic order; the `stat_*` "tabular over JSON blob" decision applies: design §2 "JSON-vs-tabular" rationale). Extends the DATABASE_SCHEMA.md precedent (`feature_definition`, `feature_value`) with the snapshot/determinism layer Statistics proved.
- **Future-proofing (constraint #6)**: new Statistics metrics arrive → new feature modules with `source: statistics`, `input: {metric: <new>}`; provider grows a new read method; engine architecture untouched.

---

## 9. Proposed Provider Contract Sketch (interfaces ONLY — design input, not implementation)

```python
# backend/src/backend/app/feature_engineering/providers.py  (exploration sketch)
class DrawProvider(Protocol):
    """Core-Domain read seam: deterministic, batched, read-only."""
    def iter_draws(self, lottery_id: int, *, after_draw_number: int | None = None,
                   before_draw_number: int | None = None) -> Iterator[DrawRow]: ...
    def lottery_rules(self, lottery_id: int) -> LotteryRules: ...   # min/max/numbers_to_select/super range

class StatisticsProvider(Protocol):
    """Statistics read seam: passive, active-snapshot-only, never precomputes."""
    def active_snapshot(self, lottery_id: int, metric_set: str = "core") -> StatsSnapshot | None: ...
    def frequencies(self, snapshot_id: int) -> Sequence[FrequencyRow]: ...
    def position_frequencies(self, snapshot_id: int) -> Sequence[PositionFrequencyRow]: ...
    def gaps(self, snapshot_id: int) -> Sequence[GapRow]: ...
    def averages(self, snapshot_id: int) -> Sequence[AverageRow]: ...
    def scalars(self, snapshot_id: int) -> Mapping[str, Decimal]: ...

class DatasetProvider(Protocol):
    """Dataset seam (Fase 2): immutable, checksummed datasets as draw sources."""
    def active_dataset(self, lottery_id: int) -> DatasetHeader | None: ...
    def iter_draws(self, dataset_id: int) -> Iterator[DrawRow]: ...
```

- These are **contracts the engine defines**; concrete adapters (wrapping `statistics_service`/`StatPayloadRepository` and `draw_service`/`draw_repository`) live at the composition root. The engine depends only on the protocols (constraint #5: no concrete implementations).

---

## 10. Proposed Registry + Versioning Sketch (design input)

```python
@dataclass(frozen=True)
class FeatureDefinition:
    id: str                    # stable slug, e.g. "gap_current_10"
    name: str
    category: str              # FEATURE_ENGINEERING.md §4
    description: str
    source: str                # "core" | "statistics" | "future-statistics" | "meta"
    inputs: tuple[str, ...]    # provider data selectors, e.g. ("draws:last:10", "stats:gap")
    algorithm: str             # module ref, e.g. "features/gap_current.py"
    params: Mapping[str, object]   # frozen params; part of fingerprint
    dependencies: tuple[str, ...]  # feature ids (empty for base features)
    complexity: str            # O(1) | O(n) | O(n log n) ...
    version: str               # per-feature version (FEATURE_ENGINEERING.md §16)
    status: str                # "active" | "future" | "disabled"
    history: tuple[str, ...]   # changelog refs
```

Feature-set fingerprint:
```
fingerprint = sha256(canonical_json({
    "feature_set": [(f.id, f.version, f.params) ...sorted...],
    "draws": {"lottery": id, "from": a, "to": b, "checksum": ...},
    "stats": {"checksum": ..., "generator_version": ...} | None,
}))
```

---

## 11. Risk Register

| Severity | Risk | Mitigation |
|----------|------|------------|
| HIGH | Cyclic or deeply nested meta-feature dependency graph blocks registration | Topological sort + cycle detection at registration; report offending cycle, fail-fast |
| HIGH | Determinism drift when a feature mixes draw + stats + other features (multiple sources) | Single canonical input fingerprint (Objective 6); INTEGER/Decimal-only accumulators; explicit ORDER BY on every pass |
| MEDIUM | Coupling to Statistics' concrete tables/services | Provider protocols as the only seam; engine never imports `statistics`/`models`/`repositories` |
| MEDIUM | Statistics `core` snapshot absent at feature-generation time | Provider returns `None` → stats-sourced features marked `skipped`, never guessed; engine runs Core-sourced features regardless (constraint #4) |
| MEDIUM | Feature explosion (thousands) hurts generation time / memory | Batched keyset reads, per-feature O(1) windowed accumulators, incremental fold (STE-06 pattern); parallelizable via topo layers |
| MEDIUM | Per-feature version drift (meaning changed without bump) | Registry review rule: any algorithm/param change bumps `version` + `history` (FEATURE_ENGINEERING.md §16); fingerprint includes version |
| LOW | Stale docs (roadmap lists entropy as pending though delivered) | Documented discrepancy; verify at proposal time |
| LOW | Physical row order assumed | Explicit `ORDER BY draw_number, id` on every read (design §9 contract) |

---

## 12. Open Decisions (pending user before proposal/spec)

1. **Persistence shape**: extend the `feature_value` (per-draw rows) precedent from DATABASE_SCHEMA.md vs. snapshot-scoped `feature_values (snapshot_id, feature_id, draw_key)` mirroring `stat_*`. Recommend the latter (incremental + checksummed), but user confirms.
2. **Feature identity axis**: per-draw feature values keyed by `draw_number` (recommended, STE-03 time axis) vs. per-lottery scalar features. Both will exist; confirm the primary axis is `draw_number`.
3. **First-slice feature set**: confirm the Core-Domain-only slice (§2) is the right scope for the first proposal (registry + providers + ~8-10 base features), with stats-sourced features as a second slice.
4. **Discrepancy handling**: roadmap lists "Entropía" pending but it is delivered; confirm we treat entropy as available (suggest yes).
5. **Naming**: `feature_*` tables vs. DATABASE_SCHEMA.md's `feature_definition`/`feature_value` — keep the doc's names or normalize to the `stat_*`-mirroring scheme?
6. **Co-occurrence/relationships**: explicitly deferred to Fase 6 (Graph Engine) or pre-computed by the Feature Engine from Core? Recommend deferred.

---

## 13. Recommended Scope — First Slice

1. `feature_engineering/` package seams: `registry.py`, `providers.py` (protocols), `engine.py` (pure, no DB), `fingerprint.py` (canonical SHA-256), `features/` (base feature modules).
2. `FeatureRegistry` with cycle detection + topological ordering.
3. `DrawProvider` adapter (reusing the keyset `ORDER BY draw_number, id` pattern) + `StatisticsProvider` adapter (passive active-snapshot reads).
4. ~8-10 **Core-Domain-only** base features (draw identity §6 + per-draw distribution §7 + tens bucketing §9 + current gap/age).
5. `feature_snapshots` + `feature_values` schema (migration 0006) with fingerprint + versioning, mirroring `stat_*` (deterministic insertion order).
6. Declare (not compute) `future-statistics` and stats-sourced feature definitions to prove extensibility (constraint #3/#4/#6) — no computation for those.
7. Strict TDD per config.yaml (runner `backend/.venv/bin/pytest`).

Second slice (later): stats-sourced features (frequencies/gaps/positions/entropy), meta-features (DAG), incremental fold.

---

## References

- `FEATURE_ENGINEERING.md` — §2 principles, §3 feature structure, §5 Group A, §6 draw features, §7 distributions, §8 positions, §9 tens, §10 relationships, §11 time series, §14 meta-features, §16 versioning, §19 registration, §20 scale goal.
- `ENGINE_SPECIFICATIONS.md` §7 — incremental, parallelizable, versioned, reproducible.
- `SYSTEM_ARCHITECTURE.md` §6 (Feature Engine), §14 (principle of decoupled evolution).
- `IMPLEMENTATION_ROADMAP.md` — Fase 3 status (lines 131-149), Fase 4 (153-168).
- `openspec/specs/statistics-engine/spec.md` — STE-01..13 (snapshot schema, read-only, determinism, incremental, multi-lottery, manual update, out-of-scope).
- `openspec/changes/archive/2026-08-07-fase-3-statistics/design.md` — §2 tables, §3 batch, §7 lifecycle, §8 generator version, §9 determinism contract, §10 entropy.
- `backend/src/backend/app/statistics/` — engine.py, generator.py, checksum.py.
- `backend/src/backend/app/services/statistics_service.py` — orchestration + read surface.
- `backend/src/backend/app/repositories/stat_snapshot_repository.py`, `stat_payload_repository.py` — active/latest/version + deterministic iter/bulk-insert.
- `backend/src/backend/app/models/stat_*.py` — payload schema.
- `backend/src/backend/app/models/draw.py`, `draw_number.py`, `lottery.py` — Core read sources.
- `backend/src/backend/app/services/draw_service.py`, `lottery_service.py` — Core service seams.
- `DATABASE_SCHEMA.md` §3-4 — `feature_definition` / `feature_value` / `DrawFeature` precedent.
- `openspec/config.yaml` — project rules, TDD, test runner.
