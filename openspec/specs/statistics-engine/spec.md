# Spec — Statistics Engine

**Change**: `fase-3-statistics` · **Store**: `openspec` · **Date**: 2026-08-07
**Artifact**: spec — new capability `statistics-engine`, merged from change delta at archive.

## Purpose

A decoupled, reproducible, result-only descriptive statistics engine over F1 draws. It computes frequencies, gaps, distributions, trends, and entropy into immutable `stat_*` snapshots stamped `generator_version` + checksum, keyed by `draw_number`. Strictly read-only vs core domains; writes only to `stat_*`. Manual CLI/API update (D6); multi-lottery from day one; batched aggregation (C6). Probability, Scoring, Analytics, ML, and Prediction are out of scope (D5).

## Requirements

### STE-01: Independent `stat_*` Schema (D2)

Statistics MUST persist to a dedicated `stat_*` schema and MUST NOT reuse `datasets` (draw snapshots only).

#### Scenario: datasets untouched

- GIVEN a generation run over existing draws
- WHEN it completes
- THEN only `stat_*` rows are written and no `datasets`/`dataset_draws` row is created or changed.

### STE-02: Strict Read-Only (C3)

The engine MUST NOT modify `draw`, `draw_number`, `super_number`, `dataset`, or `import_*`; all writes target `stat_*` only.

#### Scenario: core rows unchanged

- GIVEN a generation run and an on-demand read
- WHEN both execute
- THEN all core rows are byte-identical before and after.

### STE-03: `draw_number` Time Axis (D3)

`draw_number` SHALL be the official series axis; `draw_date` is metadata only. Every series MUST be deterministic w.r.t. `draw_number`.

#### Scenario: non-monotonic dates

- GIVEN draws with non-monotonic `draw_date`
- WHEN any series is produced
- THEN values and order follow `draw_number`, never `draw_date`.

### STE-04: `generator_version` & No In-Place Recompute (C1)

Every `stat_*` snapshot SHALL carry a mandatory `generator_version`; any algorithm change bumps it. Snapshots MUST NEVER be recomputed in place; changes create a new version.

#### Scenario: locked snapshot survives bump

- GIVEN an immutable snapshot at v3
- WHEN a changed algorithm (v4) runs
- THEN a v4 snapshot is written and v3 stays untouched.

### STE-05: Bit-Identical Determinism (C2)

Same dataset/checksum + same `generator_version` MUST yield bit-identical results.

#### Scenario: identical rerun matches

- GIVEN the same draws, checksum, and version across two runs
- WHEN both complete
- THEN outputs and checksums are byte-identical.

### STE-06: Incremental vs Full Rebuild (C4)

The engine MUST NOT recompute full history when a valid snapshot exists; it folds in the delta only. A full rebuild is the ONLY acceptable recompute path, always as a new version (STE-04), never mutating a locked snapshot.

#### Scenario: delta folds into new snapshot

- GIVEN a valid snapshot for draws 1..100
- WHEN draws 101..105 are added
- THEN only the delta folds into a new snapshot, full history is not re-derived.

#### Scenario: full rebuild is a new version

- GIVEN a valid snapshot whose algorithm is stale
- WHEN a full rebuild is required
- THEN it runs as a new version and the old snapshot is never mutated in place.

### STE-07: NULL Ignored, Never Imputed (D4)

`jackpot`/`winners` metrics are optional; NULLs SHALL be ignored and SHALL NOT be imputed.

#### Scenario: NULL jackpot omitted

- GIVEN draws with some NULL `jackpot`
- WHEN the jackpot series is computed
- THEN NULLs are omitted and no synthesized value appears.

### STE-08: Batched Streaming (C6)

All large aggregations SHALL operate in batches; the engine MUST NOT load all draws into memory at once.

#### Scenario: bounded-memory aggregation

- GIVEN a one-million-draw lottery
- WHEN a frequency aggregation runs
- THEN it processes bounded batches without holding all draws in memory.

### STE-09: Required Index (C7)

`draw_numbers` SHALL carry the `(lottery_id, number)` index. Any additional index MUST be justified by a concrete query case in the design; none required here.

#### Scenario: index-backed number lookup

- GIVEN the `(lottery_id, number)` index
- WHEN a per-number lookup runs
- THEN it uses the index rather than a full `draw_numbers` scan.

### STE-10: Hybrid Execution (D1)

Costly/accumulative metrics SHALL be precomputed into snapshots; point queries and small windows (LAST N, bounded filters) SHALL be answered on demand and MUST NOT force a precompute.

#### Scenario: bounded read stays bounded

- GIVEN a valid snapshot
- WHEN a `last 10` read runs
- THEN it is answered on the bounded window without recomputing history.

### STE-11: Multi-Lottery (D3)

Every snapshot SHALL be scoped by `lottery_id`; lotteries MUST be independent.

#### Scenario: per-lottery isolation

- GIVEN two lotteries
- WHEN each is generated
- THEN snapshots are per-`lottery_id` with no cross-lottery coupling.

### STE-12: Manual Update Only (D6)

Generation/update SHALL be manual (CLI/API), never during import; the engine SHALL register NO import hooks.

#### Scenario: import never auto-generates

- GIVEN a completed import with no explicit stats invocation
- WHEN no manual trigger fires
- THEN no `stat_*` snapshot is created or updated.

### STE-13: Out of Scope (D5)

Probability, Scoring, Analytics, ML, and Prediction SHALL NOT be computed or stored here.

#### Scenario: unsupported output rejected

- GIVEN any stats invocation
- WHEN a probability/ML/prediction output is requested
- THEN it is unsupported and no such data is produced.

---

**Note**: New capability created at archive from change delta `fase-3-statistics` (2026-08-07). Lands in a domain subfolder.