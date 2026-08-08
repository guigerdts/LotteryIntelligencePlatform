# Spec — Feature Engine

**Change**: `fase-4-feature-engine` · **Store**: `openspec` · **Date**: 2026-08-07
**Artifact**: spec (this change) — new capability `feature-engine` (delta for archive merge).

## Purpose

An independent, deterministic, provider-driven engine turning raw draws into immutable, versioned,
fingerprinted ML-ready features. It mirrors the Fase 3 snapshot contract: dedicated `feature_*` schema,
canonical SHA-256 fingerprint, `draw_number` axis, `active|retired|failed` lifecycle, manual generation
only, multi-lottery. The engine depends ONLY on provider interfaces (never Core/Statistics internals) and
writes ONLY to `feature_*`. First slice delivers the 10 Core-Domain-only base features (FE-01..FE-10);
advanced-Statistics-dependent features are registered as `future-statistics` and never computed. Graphs,
co-occurrences, ML, Probability, Prediction are out of scope (Fase 6).

Engine-level requirements are `FES-01..`; the 10 base features are `FE-01..FE-10`.

## Requirements

### FES-01: Independent `feature_*` Schema (D1/D2)

The engine SHALL persist to a dedicated `feature_snapshots` (header) + `feature_values` (normalized
payload) schema independent from Core and `stat_*`, mirroring the `stat_*` pattern. It MUST NOT reuse
`datasets` or the old `feature_value`/`feature_definition` precedent (D5 rejected).

#### Scenario: writes confined to feature_*
- GIVEN a generation run over existing draws
- WHEN it completes
- THEN only `feature_*` rows are written; no `stat_*`, `datasets`, `dataset_draws`, or Core row changes.

### FES-02: Strict Read-Only vs Core/Statistics (C3/D)

The engine MUST NOT modify `draw`, `draw_numbers`, `super_number`, `lottery`, `dataset*`, or `stat_*`;
all writes target `feature_*` only. Reads are passive — never trigger a precompute.

#### Scenario: all non-feature rows unchanged
- GIVEN a generation run and an on-demand read
- WHEN both execute
- THEN all Core and `stat_*` rows are byte-identical before and after.

### FES-03: `draw_number` Axis, No FK to Draw

`draw_number` SHALL be the official series axis; `draw_date` is metadata. `feature_values.draw_number`
is a logical identifier — the schema MUST NOT add a physical FK to `draw` (stat_* parity); joins use
`draw_number` only.

#### Scenario: non-monotonic dates
- GIVEN draws with non-monotonic `draw_date`
- WHEN any feature series is produced
- THEN order and values follow `draw_number`, never `draw_date`.

### FES-04: `feature_engine_version` & No In-Place Recompute

Every `feature_snapshots` snapshot SHALL carry `feature_engine_version`, independent of
`STATS_GENERATOR_VERSION` (a bump on one never bumps the other), plus per-feature `feature_version`.
Snapshots MUST NEVER be recomputed in place; changes create a new version. Lifecycle SHALL be
`active|retired|failed`.

#### Scenario: locked snapshot survives bump
- GIVEN an immutable active snapshot at v3
- WHEN a changed engine/feature version runs
- THEN a new version is written and v3 stays untouched.

### FES-05: Bit-Identical Determinism (C2)

Same {draws checksum, feature versions/params, optional stats identity} + same `feature_engine_version`
MUST yield byte-identical results. Every read SHALL be `ORDER BY draw_number, id`; accumulators are
INTEGER/`Decimal`-exact; `float` never enters a checksum or persisted value; canonical JSON is
`json.dumps(sort_keys=True, separators=(",", ":"))`; fingerprint = canonical SHA-256.

#### Scenario: identical rerun matches
- GIVEN the same draws, feature set, and version across two runs
- WHEN both complete
- THEN outputs, checksums, and `input_fingerprint` are byte-identical.

### FES-06: Provider Protocols Only

The engine defines `DrawProvider`, `StatisticsProvider`, `DatasetProvider` as `Protocol`s at the
composition root. The engine MUST import ONLY these interfaces and MUST NEVER import a concrete
`statistics`/`models`/repository implementation (no circular dependency). `StatisticsProvider` SHALL
resolve only the active snapshot/scalars and MUST NOT precompute (STE-10).

#### Scenario: decoupled from statistics internals
- GIVEN statistics internals change behind its service
- WHEN the Feature Engine reads through the provider
- THEN it needs no code change and never imports statistics.

### FES-07: Registry, Topo Order, Cycle Detection

Features SHALL register with explicit dependencies. `FeatureRegistry` SHALL run Kahn topological sort and
cycle detection at registration — any cycle fails-fast with the offending set, none registered. A feature
whose dependency is `future`/`disabled`/`failed` MUST be `skipped`, never guessed.

#### Scenario: cyclic meta-features rejected
- GIVEN two features whose dependencies form a cycle
- WHEN the registry loads
- THEN registration fails-fast and the cycle set is reported.

#### Scenario: disabled dependency skipped
- GIVEN a feature that depends on a `disabled` feature
- THEN it is `skipped` and produces no guessed/zero value.

### FES-08: `future-statistics` Declared, Never Computed

Features depending on advanced Statistics SHALL be registered and versioned with
`source="future-statistics"` but MUST NOT be computed and MUST NOT return a fake value or default 0.

#### Scenario: declared not scheduled
- GIVEN a registered future-statistics feature (e.g. correlation/trend)
- WHEN the engine executes the Core slice
- THEN it is declared/versioned but never scheduled and produces no persisted value.

### FES-09: No Scheduler — Manual Only (D6)

Generation/rebuild SHALL be manual (CLI `lip feature-engine generate` or API), never during import; the
engine SHALL register no import hooks. Read endpoints MUST answer from stored `feature_*` and MUST NOT
precompute.

#### Scenario: import never auto-generates
- GIVEN a completed import with no explicit feature invocation
- WHEN no manual trigger fires
- THEN no `feature_*` snapshot is created or updated.

#### Scenario: bounded read stays bounded
- GIVEN a valid snapshot
- WHEN a read for one draw/feature is requested
- THEN it is answered from stored values without recomputing.

### FE-01: `draw_sum`

The Feature Engine SHALL compute `draw_sum` as the exact sum of a draw's numbers (integer-exact).

#### Scenario: sum of numbers
- GIVEN a draw with numbers [1, 4, 7]
- WHEN `draw_sum` is computed
- THEN the value is 12 for that `draw_number`.

### FE-02: `draw_mean`

The engine SHALL compute `draw_mean` as the exact mean of a draw's numbers (`Decimal`, never float).

#### Scenario: exact mean
- GIVEN a draw with numbers [1, 4, 7] (numbers_to_select=3)
- WHEN `draw_mean` is computed
- THEN the value is 4 (exact, Decimal).

### FE-03: `draw_range`

The engine SHALL compute `draw_range` as max − min of a draw's numbers.

#### Scenario: single-number range
- GIVEN numbers [5, 3, 8]
- THEN `draw_range` is 5 (8−3).

### FE-04: `odd_even_ratio`

The engine SHALL compute `odd_even_ratio` as (odd count : even count) of a draw's numbers.

#### Scenario: equal odds
- GIVEN numbers [2, 3, 5, 8] (2 odds, 2 evens)
- THEN `odd_even_ratio` is 1 (or 1/1), exact.

### FE-05: `low_high_ratio`

The engine SHALL compute `low_high_ratio` as the ratio of numbers below/above the mid derived from
`lottery` rules (`min_number`/`max_number`).

#### Scenario: rule-derived mid
- GIVEN lottery min=1,max=45, numbers [1, 44]
- THEN `low_high_ratio` is 1 (1 low : 1 high) with mid=23 from rules.

### FE-06: `consecutive_count`

The engine SHALL count the number of adjacent (difference-1) pairs within a draw's sorted numbers.

#### Scenario: adjacent pair counted
- GIVEN numbers [5, 6, 12]
- THEN `consecutive_count` is 1 (the 5-6 pair); 6-12 is not.

### FE-07: `decade_distribution`

The engine SHALL produce per-decade-band counts (1-10, 11-20, 21-30, 31-40, >max) with band boundaries
derived from lottery rules.

#### Scenario: bands from max
- GIVEN numbers [7, 15, 42] with max=45
- THEN counts 1-10:1, 11-20:1, 41-45:1.

### FE-08: `repeated_from_previous`

The engine SHALL count numbers that equal any number of the immediately previous draw
(`draw_number − 1`).

#### Scenario: repeated numbers counted
- GIVEN draw 10 = [3, 9, 44] and draw 9 = [3, 7, 44]
- THEN `repeated_from_previous` at draw 10 is 2 (3 and 44).

### FE-09: `max_current_gap`

The engine SHALL compute the max gap, in `draw_number` units, since each number last appeared (or since
first draw for never-seen), over the ordered series.

#### Scenario: never-seen number gap
- GIVEN a number that has never appeared by draw 12 of a lottery
- WHEN `max_current_gap` is computed at draw 12
- THEN the gap is measured from the first draw (12 − 1), the largest gap in the series.

### FE-10: `current_frequency`

The engine SHALL compute each number's occurrence count over the `draw_number`-ordered series (windowed or
cumulative per the feature's params).

#### Scenario: cumulative frequency
- GIVEN number 7 appears in draws 1, 4, 9 across a lottery
- THEN `current_frequency` for 7 at draw 9 is 3.

### FES-10: Migration & Indexes (D)

New migration `0006_feature_tables` (`down_revision = "0005_stat_tables"`) SHALL add `feature_snapshots`
and `feature_values`; rollback drops ONLY `feature_*`, never Core/`stat_*`. New indexes (3)
`ix_fsnap_lottery_set_status`, `ix_fval_snapshot_id`, `ix_fval_feature_draw` SHALL be justified by the
access paths in the design.

#### Scenario: rollback is non-destructive
- GIVEN a DB with Core + statistics tables
- WHEN migration 0006 is downgraded
- THEN `feature_*` is dropped and Core/`stat_*` remain intact.

---

**Note**: New capability created at archive from change delta `fase-4-feature-engine` (2026-08-07). The
10 base features (FE-01..FE-10) constitute the approved, deterministic first-slice contract. Lands in a
domain subfolder at merge-archive.