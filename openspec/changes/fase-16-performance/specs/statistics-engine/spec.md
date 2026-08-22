# Delta for Statistics Engine (`statistics-engine`)

**Change**: `fase-16-performance` · **Date**: 2026-08-18
**Slice**: S2a — `read_frequencies`/`read_gaps` LIMIT pushdown (statistics read-path SQL).

## MODIFIED Requirements

### STE-10: Hybrid Execution (D1)

Costly/accumulative metrics SHALL be precomputed into snapshots; point queries and small windows (LAST N, bounded filters) SHALL be answered on demand and MUST NOT force a precompute. `read_frequencies`/`read_gaps` SHALL honor `last` at the SQL level by appending `.limit(last)` when `last > 0`, keeping `ORDER BY number` so the deterministic result order is preserved.
(Previously: `last` was applied in Python after loading all rows (`list(rows)[:last]`), a fetch-all-then-slice read.)

#### Scenario: bounded read stays bounded

- GIVEN a valid snapshot
- WHEN a `last 10` read runs
- THEN it is answered on the bounded window without recomputing history
- AND the query itself is limited at the SQL level (no full-row fetch)

#### Scenario: deterministic order preserved under LIMIT

- GIVEN a snapshot with frequency rows for numbers 1..45
- WHEN `read_frequencies(last=10)` and `read_gaps(last=10)` execute
- THEN the returned rows are the first 10 in ascending `number` order, identical to the pre-pushdown result set

#### Scenario: no limit reads everything ordered

- GIVEN `last` unset or `last <= 0`
- WHEN the read executes
- THEN all rows are returned in ascending `number` order (unchanged behavior)