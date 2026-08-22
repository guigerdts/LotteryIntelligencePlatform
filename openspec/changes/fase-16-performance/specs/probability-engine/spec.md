# Delta for Probability Engine (`probability-engine`)

**Change**: `fase-16-performance` · **Date**: 2026-08-18
**Slice**: S1a — probability `generate` with an active statistics snapshot (P0 correctness, no perf target).

## MODIFIED Requirements

### PM-04: Empirical Probability

The engine SHALL compute the empirical probability `P(subject) = observed_count(subject) / total_draws` from the active `stat_*` frequency/`stat` snapshot (via `StatSnapshotReader`), per subject number. Same snapshot ⇒ identical values. The statistics-reader adapter SHALL read the real `stat_frequency` payload (`select(StatFrequency).where(snapshot_id == ...)` → `{number: count}`, no `metric_id` filter) and SHALL NOT import a nonexistent `StatValue` model. Probability `generate` SHALL succeed when an active statistics snapshot exists (currently silently crashes — `ModuleNotFoundError` on the stale import).
(Previously: the reader imported the nonexistent `backend.app.models.stat_value`, so `generate` crashed whenever an active stats snapshot existed; probability tests passed only because no snapshot was seeded.)

#### Scenario: frequency-derived rate

- GIVEN a stat snapshot with count 12 occurrences of number 7 over 60 draws
- WHEN PM-04 runs
- THEN the value for number 7 is 12/60 = 0.2 (Decimal).

#### Scenario: generate succeeds with an active stats snapshot (regression)

- GIVEN a lottery with draws AND an active statistics snapshot seeded with `stat_frequency` rows
- WHEN probability `generate` is invoked
- THEN it returns generated rows instead of crashing
- AND a regression test seeds the active snapshot and asserts the successful `generate` (S1a acceptance)

#### Scenario: `stat_frequency` payload read

- GIVEN an active statistics snapshot
- WHEN the statistics-reader reads frequencies
- THEN it maps `stat_frequency` rows to `{number: count}` with no nonexistent-model import