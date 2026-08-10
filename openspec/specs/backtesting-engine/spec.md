# Spec — Backtesting Engine (`backtesting-engine`)

**Change**: `fase-10-backtesting-engine` · **Store**: `openspec` · **Date**: 2026-08-10
**Artifact**: spec (this change) — new capability `backtesting-engine`, parallel to `opt-engine` (F9), `ml-engine` (F7), and `dl-engine` (F8).

## Purpose

A deterministic backtesting engine that evaluates prediction strategies against historical lottery data using walk-forward validation. Provides objective evidence of strategy performance before deployment, enabling comparison against random baselines and across strategies. Every strategy must prove its worth through backtesting before it can be recommended.

The engine is generic: it accepts any strategy via `StrategyProtocol`, not coupled to ML/DL. ML/DL engines from F7/F8 are initial adapters. Results persist as immutable `bt_*` snapshots with SHA-256 fingerprinting, seed-based determinism, and atomic lifecycle.

Engine requirements `BTE-01..18`; per-surface requirements `BTS-01..04`.

## Requirements Overview

| ID | Requirement | Priority | Mirrors |
|----|-------------|----------|---------|
| BTE-01 | Independent `bt_*` schema | P0 | OE-01/MLE-01 |
| BTE-02 | Strict read-only vs other engines | P0 | OE-02/MLE-02 |
| BTE-03 | Generic StrategyProtocol contract | P0 | new |
| BTE-04 | Walk-forward window splitter (configurable, anti-leakage) | P0 | OE-05/MLE-03 |
| BTE-05 | Determinism: seed-based, windows in fingerprint | P0 | OE-06/MLE-04 |
| BTE-06 | Fingerprint: strategy+config+data+seed+windows | P0 | OE-07/MLE-05 |
| BTE-07 | Data floor: configurable minimum draws; else INSUFFICIENT_DATA | P0 | OE-08/DLE-10 |
| BTE-08 | Lottery-specific metrics (hit rate, match distribution, avg matches) | P0 | new |
| BTE-09 | Dual benchmark: uniform random + F5 hypergeometric | P0 | new |
| BTE-10 | Snapshot lifecycle & atomicity, fingerprint idempotency | P0 | OE-10/MLE-08 |
| BTE-11 | Provider Protocols only (no module-level ML/DL coupling) | P0 | OE-11/MLE-06 |
| BTE-12 | Manual-only surface; no predict/rank/generate | P0 | OE-12/MLE-09 |
| BTE-13 | Migration `0012` additive; non-destructive rollback | P0 | OE-14/MLE-10 |
| BTE-14 | Multi-lottery isolation | P1 | OE-15/MLE-11 |
| BTE-15 | Convergence tracking (per-window evaluation history) | P0 | OE-13 |
| BTE-16 | Benchmark uses same evaluation period as strategy | P0 | new |
| BTE-17 | Temporal ordering: strict train-before-evaluate | P0 | new |
| BTE-18 | Walk-forward parameters in fingerprint when affecting reproducibility | P0 | new |

Per-surface requirements:
| ID | Requirement | Priority |
|----|-------------|----------|
| BTS-01 | API: POST /bt/run, GET /bt/history, GET /bt/results | P0 |
| BTS-02 | CLI: lip bt run\|history\|results (parity with API) | P0 |
| BTS-03 | Schemas: Pydantic v2 request/response models | P0 |
| BTS-04 | Service: atomic tx, idempotent runs, floor check | P0 |

## Requirements

### BTE-01: Independent `bt_*` Schema

The engine SHALL persist to a dedicated `bt_snapshots` (header) + `bt_results` (metrics + window history) schema, mirroring `stat_*`/`ml_*`/`dl_*`/`opt_*`. It MUST NOT reuse `datasets`, `ml_*`, `dl_*`, `opt_*`, or any Core/`stat_*`/`feature_*`/`prob_*`/`graph_*` table. Metric values SHALL be `Numeric(20,8)` Decimal — no float columns. `metrics_json` SHALL hold per-window and aggregate metrics.

**Acceptance**
- [ ] A backtest commit writes rows in `bt_*` only; no other table changes.
- [ ] No float columns exist in `bt_*` tables; all metrics are Decimal(20,8).

#### Scenario: writes confined to bt_*
- GIVEN a completed backtest run over existing draws
- WHEN it commits
- THEN only `bt_*` rows are written; no Core, `ml_*`, `dl_*`, `opt_*`, `stat_*`, `feature_*`, `prob_*`, or `graph_*` row changes.

### BTE-02: Strict Read-Only vs Other Engines

The engine MUST NOT modify `lottery`, `draw`, `draw_numbers`, `super_number`, `dataset*`, `ml_*`, `dl_*`, `opt_*`, or any prior-engine table. Writes target `bt_*` only; reads are passive and never trigger backtesting, training, or optimization.

**Acceptance**
- [ ] All non-`bt_*` rows byte-identical before/after a run under concurrent reads.

#### Scenario: all non-bt rows unchanged
- GIVEN a backtest run and concurrent reads
- WHEN both execute
- THEN all Core and prior-engine rows are byte-identical before and after.

### BTE-03: Generic StrategyProtocol Contract

The engine SHALL accept strategies via `StrategyProtocol`:

```python
class StrategyProtocol(Protocol):
    @property
    def strategy_id(self) -> str: ...
    
    def predict(self, draw_context: DrawContext) -> list[int]: ...
```

`DrawContext` SHALL contain:
- `lottery_id`: int
- `draw_date`: datetime
- `historical_draws`: list of recent draws (expanding window, no future)
- `feature_set`: optional feature vector

ML/DL engines adapt via `MLStrategyAdapter` / `DLStrategyAdapter`. The engine MUST NOT import `ml.*`, `dl.*`, `opt.*`, `services.*`, or `repositories.*` at module level. Lazy imports inside functions are permitted.

**Acceptance**
- [ ] Any class implementing `StrategyProtocol` can be used as a backtest strategy.
- [ ] No module-level imports of ml/dl/opt/services/repositories in `backtesting/`.

#### Scenario: ML strategy adapter
- GIVEN an ML model trained on historical data
- WHEN wrapped in `MLStrategyAdapter` and passed to BacktestEngine
- THEN the engine calls `predict()` with valid `DrawContext` and receives predictions.

#### Scenario: DL strategy adapter
- GIVEN a DL model trained on historical data
- WHEN wrapped in `DLStrategyAdapter` and passed to BacktestEngine
- THEN the engine calls `predict()` with valid `DrawContext` and receives predictions.

#### Scenario: isolation enforcement
- GIVEN the backtesting module
- WHEN inspected for imports
- THEN no module-level imports of ml/dl/opt/services/repositories exist.

### BTE-04: Walk-Forward Window Splitter

The engine SHALL split historical data into walk-forward windows with configurable parameters:

- `train_years`: int (default 5) — years of training data
- `eval_count`: int (default 1) — number of draws to evaluate per window
- `step_count`: int (default 1) — draws to advance between windows
- `min_train_draws`: int (default 100) — minimum draws for training

Each window SHALL produce:
- `train_range`: [start, end) — exclusive end
- `eval_range`: [end, end+eval_count) — exclusive end

**Temporal ordering**: train data MUST precede eval data. No future data may enter training or feature computation for an evaluation point.

**Zero look-ahead**: signals use only data available at the evaluation point. Indicators use expanding/rolling windows. Never compute features on the full dataset before splitting.

**Acceptance**
- [ ] Each window's train_range precedes eval_range in time.
- [ ] No window overlaps train and eval data.
- [ ] Windows cover the entire historical range without gaps.

#### Scenario: standard walk-forward
- GIVEN 10 years of historical draws
- WHEN walk-forward runs with train_years=5, eval_count=1
- THEN windows are: [0,5)→[5,6), [1,6)→[6,7), ..., [4,9)→[9,10).

#### Scenario: no look-ahead
- GIVEN a walk-forward window with eval on draw N
- WHEN the strategy is trained
- THEN only draws before N are used for training.

#### Scenario: minimum training data
- GIVEN a lottery with fewer than min_train_draws draws
- WHEN walk-forward runs
- THEN an error is raised (InsufficientDataError).

### BTE-05: Determinism — Seed-Based, Windows in Fingerprint

The engine SHALL be deterministic: same seed + same data + same configuration = identical results. Determinism is achieved via:

- `DeterminismContext` managing RNG states (numpy, random, hashlib)
- Seed propagated to strategy predictions where applicable
- Walk-forward windows deterministic given same parameters

**Acceptance**
- [ ] Two runs with same seed + same data + same config produce byte-identical results.
- [ ] Two runs with different seeds produce different results.

#### Scenario: reproducibility
- GIVEN two identical backtest runs with seed=42
- WHEN both complete
- THEN their fingerprints, metrics, and window histories are byte-identical.

#### Scenario: seed affects results
- GIVEN two identical backtest runs with different seeds
- WHEN both complete
- THEN their results differ.

### BTE-06: Fingerprint — Strategy+Config+Data+Seed+Windows

The engine SHALL compute a canonical SHA-256 fingerprint over:

- `strategy_id`
- `config` (JSON-serialized: train_years, eval_count, step_count, min_train_draws)
- `data_hash` (SHA-256 of dataset checksum)
- `seed`
- `window_params` (if affecting reproducibility)
- `benchmark_type` (uniform/hypergeometric/both)
- `BACKTEST_GENERATOR_VERSION`

The fingerprint SHALL be stored as `VARCHAR(64)` and used for idempotency: same fingerprint = same result, skip re-computation.

**Acceptance**
- [ ] Two runs with identical inputs produce the same fingerprint.
- [ ] Two runs with any different input produce different fingerprints.
- [ ] Fingerprint is stored and checked before re-computation.

#### Scenario: fingerprint idempotency
- GIVEN a completed backtest with fingerprint X
- WHEN a new run with the same fingerprint is requested
- THEN the existing result is returned without re-computation.

#### Scenario: fingerprint changes with config
- GIVEN two backtest runs with different train_years
- WHEN both complete
- THEN their fingerprints differ.

### BTE-07: Data Floor — Configurable Minimum Draws

The engine SHALL enforce a minimum number of historical draws before backtesting. Default: 100. Below the floor, the engine SHALL raise `InsufficientDataError` and write no `bt_*` rows.

**Acceptance**
- [ ] Backtest with < min_train_draws raises InsufficientDataError.
- [ ] No bt_* rows are written when InsufficientDataError is raised.

#### Scenario: sufficient data
- GIVEN a lottery with 500 historical draws
- WHEN backtest runs with min_train_draws=100
- THEN the backtest proceeds normally.

#### Scenario: insufficient data
- GIVEN a lottery with 50 historical draws
- WHEN backtest runs with min_train_draws=100
- THEN InsufficientDataError is raised and no bt_* rows are written.

### BTE-08: Lottery-Specific Metrics

The engine SHALL compute lottery-specific metrics per window and aggregate:

- **Hit Rate**: percentage of draws where at least k numbers match (configurable k, default 1)
- **Match Distribution**: histogram of k-of-n matches (k=0,1,2,...,n)
- **Average Matches**: mean number of matches per draw
- **Consistency Score**: standard deviation of matches (lower = more consistent)
- **Total Draws Evaluated**: count of draws in evaluation windows

All metric values SHALL be `Numeric(20,8)` Decimal. Metrics SHALL be stored in `bt_results.metrics_json` as JSON.

**Acceptance**
- [ ] All metrics are Decimal(20,8), no float.
- [ ] Metrics match manual calculation on same data.

#### Scenario: metrics calculation
- GIVEN a backtest with 10 evaluation draws, each matching 2 numbers on average
- WHEN metrics are computed
- THEN average_matches = 2.00000000, hit_rate depends on k threshold.

#### Scenario: metrics are deterministic
- GIVEN two identical backtest runs
- WHEN both compute metrics
- THEN their metrics_json are byte-identical.

### BTE-09: Dual Benchmark — Uniform Random + F5 Hypergeometric

The engine SHALL compute two benchmarks using the same evaluation windows as the strategy:

1. **Uniform Random Baseline**: random predictions from uniform distribution over the number pool. Seed-based for reproducibility.
2. **F5 Hypergeometric Null-Model**: predictions based on exact combinatorial probabilities from F5 Probability Engine. Lazy-imports `probability.*` only inside the benchmark function.

Both benchmarks SHALL produce the same metrics as the strategy (hit rate, match distribution, average matches). Benchmark results SHALL be stored alongside strategy results in `bt_results`.

**Acceptance**
- [ ] Uniform random baseline produces expected distribution (law of large numbers).
- [ ] Hypergeometric baseline matches F5 implementation.
- [ ] Benchmarks use the same evaluation windows as the strategy.

#### Scenario: uniform random baseline
- GIVEN a backtest with uniform random benchmark
- WHEN metrics are computed
- THEN hit_rate approaches theoretical probability for large sample.

#### Scenario: hypergeometric baseline
- GIVEN a backtest with hypergeometric benchmark
- WHEN metrics are computed
- THEN results match F5 probability engine output for same parameters.

#### Scenario: same evaluation period
- GIVEN a strategy backtest with specific evaluation windows
- WHEN benchmarks run
- THEN both benchmarks use the exact same evaluation windows.

### BTE-10: Snapshot Lifecycle & Atomicity

The engine SHALL persist results as immutable `bt_*` snapshots with lifecycle:

- `active`: current valid result for this fingerprint
- `retired`: superseded by newer run with same fingerprint
- `failed`: run that encountered an error

Lifecycle transitions:
- New run → `active` (atomic single-transaction write)
- Re-run with same fingerprint → old `active` → `retired`, new → `active`
- Error during run → `failed`

**Idempotency**: same fingerprint = return existing `active` result, skip re-computation.

**Acceptance**
- [ ] Single-transaction write: either all bt_* rows commit or none do.
- [ ] Only one `active` snapshot per fingerprint at any time.
- [ ] Re-run retires old snapshot atomically.

#### Scenario: atomic write
- GIVEN a backtest run producing 5 bt_* rows
- WHEN commit occurs
- THEN all 5 rows appear atomically (or none on failure).

#### Scenario: idempotent re-run
- GIVEN a completed backtest with fingerprint X
- WHEN a new run with same fingerprint is requested
- THEN the existing active result is returned; no new rows written.

### BTE-11: Provider Protocols Only

The engine SHALL interact with other engines only through Provider Protocols. It MUST NOT import `ml.*`, `dl.*`, `opt.*`, `services.*`, or `repositories.*` at module level. Lazy imports inside functions are permitted for benchmark (F5) and adapters (ML/DL).

**Acceptance**
- [ ] No module-level imports of ml/dl/opt/services/repositories in backtesting/.
- [ ] All external interactions go through protocols or lazy imports.

#### Scenario: protocol compliance
- GIVEN a strategy implementing StrategyProtocol
- WHEN passed to BacktestEngine
- THEN the engine uses only protocol methods, no direct engine imports.

### BTE-12: Manual-Only Surface

The engine SHALL expose only manual-trigger endpoints. No GET shall trigger backtesting. No `/bt/predict`, `/bt/rank`, or number-generation endpoints.

**Acceptance**
- [ ] Only POST /bt/run triggers backtesting.
- [ ] GET endpoints return stored results only.
- [ ] No predict/rank/generate endpoints exist.

#### Scenario: manual trigger only
- GIVEN a running app
- WHEN POST /bt/run is called
- THEN backtesting executes.

#### Scenario: reads never trigger backtesting
- GIVEN a lottery without bt_* snapshot
- WHEN GET /bt/results targets it
- THEN the response is 404 SNAPSHOT_NOT_FOUND; POST /bt/run is never fired.

### BTE-13: Migration `0012` Additive

The migration SHALL create `bt_snapshots` and `bt_results` tables only. It MUST NOT modify existing tables. Downgrade SHALL drop only `bt_*` objects.

**Acceptance**
- [ ] `alembic upgrade head` creates bt_snapshots and bt_results.
- [ ] `alembic downgrade -1` drops only bt_* tables.
- [ ] No existing table is modified.

#### Scenario: migration creates bt_* tables
- GIVEN a fresh DB with migration 0011 applied
- WHEN alembic upgrade head runs
- THEN bt_snapshots and bt_results exist with correct schema.

#### Scenario: rollback affects only bt_*
- GIVEN a DB with bt_* tables
- WHEN alembic downgrade -1 runs
- THEN only bt_* tables are dropped; all other tables unchanged.

### BTE-14: Multi-Lottery Isolation

The engine SHALL support multiple lotteries independently. Each lottery's backtest is isolated: separate snapshots, separate metrics, no cross-contamination.

**Acceptance**
- [ ] Backtest on lottery A does not affect lottery B's snapshots.
- [ ] Each lottery's metrics are independent.

#### Scenario: isolated lotteries
- GIVEN two lotteries A and B
- WHEN backtest runs on A
- THEN B's bt_* snapshots are unchanged.

### BTE-15: Convergence Tracking

The engine SHALL track per-window evaluation history in `bt_results.window_history_json`. Each entry SHALL contain:
- `window_index`: int
- `train_range`: [start, end)
- `eval_range`: [end, end+eval_count)
- `metrics`: per-window metrics

This enables analysis of strategy performance over time.

**Acceptance**
- [ ] window_history_json contains one entry per walk-forward window.
- [ ] Each entry has complete train/eval ranges and metrics.

#### Scenario: window history
- GIVEN a backtest with 5 walk-forward windows
- WHEN results are persisted
- THEN window_history_json has 5 entries with correct ranges and metrics.

### BTE-16: Benchmark Uses Same Evaluation Period

Both benchmarks SHALL use the exact same evaluation windows as the strategy. No separate windowing for benchmarks.

**Acceptance**
- [ ] Benchmark evaluation windows match strategy evaluation windows exactly.

#### Scenario: synchronized windows
- GIVEN a strategy backtest with specific evaluation windows
- WHEN benchmarks compute
- THEN both use the identical evaluation windows.

### BTE-17: Temporal Ordering — Strict Train-Before-Evaluate

The engine SHALL enforce strict temporal ordering: train data MUST precede eval data in time. No future data may enter training or feature computation for an evaluation point.

**Acceptance**
- [ ] All train draws have dates before all eval draws in each window.
- [ ] No window has train data after eval data.

#### Scenario: temporal separation
- GIVEN a walk-forward window
- WHEN train and eval ranges are inspected
- THEN max(train_dates) < min(eval_dates).

### BTE-18: Walk-Forward Parameters in Fingerprint

Walk-forward parameters that affect reproducibility SHALL be included in the fingerprint: train_years, eval_count, step_count, min_train_draws. Changing any parameter produces a different fingerprint.

**Acceptance**
- [ ] Two runs with different train_years produce different fingerprints.
- [ ] Two runs with different eval_count produce different fingerprints.

#### Scenario: parameter affects fingerprint
- GIVEN two identical backtest runs with different train_years
- WHEN both complete
- THEN their fingerprints differ.

## API Requirements (BTS-01..04)

### BTS-01: API Endpoints

The engine SHALL expose:

- `POST /bt/run` — trigger backtest run
  - Request: `{lottery_id: int, strategy_id: str, config?: BacktestConfig, seed?: int}`
  - Response: `{success: true, data: BacktestResult}`
  - Errors: 404 RESOURCE_NOT_FOUND, 422 VALIDATION_ERROR, 500 training_error, InsufficientDataError

- `GET /bt/history` — list backtest runs
  - Query: `lottery_id: int`
  - Response: `{success: true, data: list[BacktestSummary]}`

- `GET /bt/results` — get detailed results
  - Query: `lottery_id: int, snapshot_id?: int`
  - Response: `{success: true, data: BacktestResult}`

All responses SHALL use the standard envelope `{success, data|error, timestamp}`.

**Acceptance**
- [ ] POST /bt/run triggers backtesting.
- [ ] GET /bt/history returns list of runs.
- [ ] GET /bt/results returns detailed results.
- [ ] Missing lottery returns 404.
- [ ] Below data floor returns InsufficientDataError.

### BTS-02: CLI Parity

The CLI SHALL expose:

- `lip bt run --lottery-id <id> --strategy <id> [--train-years 5] [--eval-count 1] [--seed 42]`
- `lip bt history --lottery-id <id>`
- `lip bt results --lottery-id <id> [--snapshot-id <id>]`

Same behavior as API. JSON output.

**Acceptance**
- [ ] CLI commands mirror API behavior.
- [ ] Floor behavior matches API.

### BTS-03: Schemas

Pydantic v2 models:
- `BacktestRequest` — request for POST /bt/run
- `BacktestConfig` — walk-forward parameters
- `BacktestResult` — full result with metrics
- `BacktestSummary` — list summary
- `MetricSet` — lottery-specific metrics

**Acceptance**
- [ ] All schemas use Pydantic v2.
- [ ] No float in metric fields (Decimal).

### BTS-04: Service Layer

`BacktestService.run()` SHALL:
1. Validate lottery exists (404 if not)
2. Check data floor (InsufficientDataError if below)
3. Compute fingerprint
4. Check idempotency (return existing if active)
5. Run walk-forward with strategy + benchmarks
6. Compute metrics
7. Persist bt_* snapshot atomically
8. Return result

**Acceptance**
- [ ] Atomic write: all or nothing.
- [ ] Idempotent: same fingerprint returns existing.
- [ ] Floor enforced.

## Traceability: Proposal → Requirements

| Proposal Item | Requirements |
|---------------|--------------|
| Generic strategy/provider contract | BTE-03, BTE-11 |
| Walk-forward semantics | BTE-04, BTE-17, BTE-18 |
| Lottery-specific metrics | BTE-08 |
| Dual benchmark | BTE-09, BTE-16 |
| Fingerprint inputs | BTE-06 |
| Snapshot lifecycle | BTE-10 |
| Data-floor behavior | BTE-07 |
| F10/F11 boundary | BTE-12 (no cross-run comparison) |
| F10/F13 boundary | BTE-12 (no generate/rank) |
| Migration and API/CLI | BTE-13, BTS-01..04 |

## Conflicts or Ambiguities

None discovered. All requirements are consistent with proposal decisions D1-D6.

## Backend/API Delta

New capability `backtesting-engine` added to backend spec:
- REQ-13 (new): Manual backtesting endpoints and CLI commands
- Parity with REQ-10 (stats/ml/dl/opt) pattern

## Migration Requirements

- Migration 0012: create bt_snapshots, bt_results
- Additive only: no existing table modified
- Downgrade: drop only bt_* objects
- Follows pattern of 0009 (ml), 0010 (dl), 0011 (opt)

## Tests/Scenarios Required

Per requirement, positive/negative/boundary scenarios. Key test areas:
1. Walk-forward splitter correctness (temporal ordering, no look-ahead)
2. StrategyProtocol adapter compliance
3. Metrics calculation accuracy
4. Benchmark reproducibility (uniform + hypergeometric)
5. Fingerprint idempotency
6. Snapshot lifecycle atomicity
7. Data floor enforcement
8. Multi-lottery isolation
9. API/CLI parity
10. Migration up/down

## Decisions Requiring Approval

None. All decisions (D1-D6) were confirmed in proposal approval.

---

**Ready for design (sdd-design) upon confirmation.**
