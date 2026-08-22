# Delta for Experiment Engine (`experiment-engine`)

**Change**: `fase-16-performance` · **Date**: 2026-08-18
**Slice**: S2b — indexed `run_ids` comparison lookup + migration 0016 + legacy fallback.

## ADDED Requirements

### EXP-009: Indexed `run_ids` Lookup & Migration 0016

The comparison cache lookup SHALL resolve an existing comparison by a single indexed lookup instead of scanning and parsing every `comparison_json` blob. `exp_comparisons` SHALL gain a nullable `run_ids` (Text) column storing the sorted, comma-joined run ids of the comparison, with a non-unique index `ix_exp_comparisons_run_ids`, added by migration `0016_exp_comparisons_run_ids` (down_revision 0015, S1b dependency). Migration SHALL backfill `run_ids` from existing `comparison_json` rows. During transition, rows with `NULL run_ids` SHALL fall back to the legacy JSON-parse path until backfilled (legacy path kept). The `compare()` creation path SHALL write `run_ids` on insert. The JSON blob remains the source of truth for content; `run_ids` is a denormalized lookup key (immutability preserved).

#### Scenario: single indexed lookup (S2b)

- GIVEN an experiment with many persisted comparisons and a request for `run_ids=[R1, R2]`
- WHEN the comparison is looked up
- THEN exactly one `WHERE experiment_id == ? AND run_ids == ?` query runs, backed by `ix_exp_comparisons_run_ids`
- AND no `comparison_json` blob is parsed during lookup

#### Scenario: legacy fallback for NULL run_ids

- GIVEN a row whose `run_ids` is still NULL (pre-backfill)
- WHEN a comparison lookup matches it
- THEN the legacy JSON-parse path resolves it, and behavior is unchanged for that row

#### Scenario: migration 0016 up/down round-trip

- GIVEN a DB at revision 0015 with existing `exp_comparisons` rows
- WHEN migration 0016 applies and backfills
- THEN `run_ids` is populated from `comparison_json` for existing rows
- AND `alembic downgrade 0015` drops the column and index without touching other tables

#### Scenario: compare target met (S2b)

- GIVEN the exact command `pytest tests/exp -q -k compare --durations=1`
- WHEN measured after S2b
- THEN the comparison lookup is near-constant (O(1) indexed), replacing the O(N) whole-blob scan (proposal §5)

## MODIFIED Requirements

### EXP-005: Comparison

The system SHALL compute side-by-side metric comparison across 2+ runs within an experiment. The comparison SHALL be persisted as an immutable snapshot in `exp_comparisons.comparison_json`. Comparisons are within-experiment only (no cross-experiment comparison in MVP). Idempotent re-requests SHALL resolve the cached comparison by the indexed `run_ids` lookup (EXP-009) without recomputation or blob parsing.

**Entities touched**: `exp_comparisons`

#### Scenario: compare two runs

- GIVEN an experiment with 2 runs (R1, R2) referencing bt_snapshots
- WHEN POST /experiment/{id}/compare with run_ids=[R1, R2]
- THEN comparison matrix is returned and persisted

#### Scenario: insufficient runs

- GIVEN an experiment with 1 run
- WHEN POST /experiment/{id}/compare with 1 run
- THEN validation error: at least 2 runs required

#### Scenario: comparison idempotent

- GIVEN a persisted comparison for run_ids=[R1, R2]
- WHEN the same comparison is requested again
- THEN the existing comparison is returned via the indexed `run_ids` lookup without recomputation
- AND no `comparison_json` blob is parsed on the lookup path
(Previously: the lookup loaded every comparison row of the experiment and parsed each `comparison_json` blob in Python.)