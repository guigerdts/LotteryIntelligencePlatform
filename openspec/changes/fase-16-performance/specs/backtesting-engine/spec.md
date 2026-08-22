# Delta for Backtesting Engine (`backtesting-engine`)

**Change**: `fase-16-performance` · **Date**: 2026-08-18
**Slices**: S2a (bt draw-load N+1 removal) + S3 (parallel window evaluation).

## MODIFIED Requirements

### BTE-05: Determinism — Seed-Based, Windows in Fingerprint

The engine SHALL be deterministic: same seed + same data + same configuration = identical results. Determinism is achieved via:

- `DeterminismContext` managing RNG states (numpy, random, hashlib)
- Seed propagated to strategy predictions where applicable
- Walk-forward windows deterministic given same parameters

When windows are evaluated in parallel (S3), the engine SHALL produce byte-identical results to a serial run: per-window benchmark RNG is derived deterministically from `config.seed`, results are ordered by `window_index` before aggregation, and the GF-1 parity gate (serial vs parallel byte-identical) is mandatory.

**Acceptance**
- [ ] Two runs with same seed + same data + same config produce byte-identical results.
- [ ] Two runs with different seeds produce different results.
- [ ] Serial vs parallel runs produce byte-identical results (GF-1 hard gate).

#### Scenario: reproducibility

- GIVEN two identical backtest runs with seed=42
- WHEN both complete
- THEN their fingerprints, metrics, and window histories are byte-identical.

#### Scenario: seed affects results

- GIVEN two identical backtest runs with different seeds
- WHEN both complete
- THEN their results differ.

#### Scenario: serial-vs-parallel byte-identical parity (S3)

- GIVEN the same run executed once serially and once through the parallel window path
- WHEN both complete
- THEN fingerprints, metrics, and `window_history` are byte-identical
- AND any byte difference blocks the slice (GF-1 gate)

#### Scenario: deterministic ordering by window_index

- GIVEN parallel evaluation of N independent windows
- WHEN results are collected and aggregated
- THEN they are ordered by `window_index` in ascending order, never by completion time

### BTS-04: Service Layer

`BacktestService.run()` SHALL:
1. Validate lottery exists (404 if not)
2. Check data floor (InsufficientDataError if below)
3. Compute fingerprint
4. Check idempotency (return existing if active)
5. Load draw history with numbers (S2a: single query with `selectinload`, no per-draw N+1)
6. Run walk-forward with strategy + benchmarks
7. Compute metrics
8. Persist bt_* snapshot atomically
9. Return result

**Acceptance**
- [ ] Atomic write: all or nothing.
- [ ] Idempotent: same fingerprint returns existing.
- [ ] Floor enforced.
- [ ] Draw-history load issues ≤2 SELECTs per run (assert-queries regression).

#### Scenario: draw load is not N+1 (S2a)

- GIVEN a run over 2 000 draws (baseline 2 001 SELECTs)
- WHEN the assert-queries regression runs
- THEN the draw history loads in ≤2 SELECTs (one draw query + one eager numbers load)
- AND the mapped result set is identical to the pre-optimization rows

#### Scenario: run_returns_200 meets target (S2a/S3)

- GIVEN the exact command `pytest tests/bt -q -k run_returns_200 --durations=1`
- WHEN measured before and after S2a/S3
- THEN the result is ≤5.0 s after S2a and ≤3.5 s after S3 (baseline 6.35 s, proposal §5)