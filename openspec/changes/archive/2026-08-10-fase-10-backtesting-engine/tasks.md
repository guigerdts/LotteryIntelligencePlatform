# Tasks — Fase 10: Backtesting Engine

**Change**: `fase-10-backtesting-engine` · **Store**: `openspec` · **Date**: 2026-08-10
**Artifact**: tasks — implementation plan with 6 PRs, 22 requirements, test traceability.

## PR1: Foundation (~250 LOC impl)

### Tasks

- [ ] **T1.1: Migration 0012 — bt_* tables**
  - **Files**: `backend/alembic/versions/0012_bt_tables.py`
  - **Action**: Create `bt_snapshots` and `bt_results` tables with indexes
  - **Requirements**: BTE-13
  - **Acceptance**: `alembic upgrade head` creates tables; `alembic downgrade -1` drops only bt_*
  - **Tests**: `test_migration.py` — upgrade creates tables, downgrade drops only bt_*
  - **Depends**: —
  - **Est LOC**: ~80

- [ ] **T1.2: ORM models — BtSnapshot, BtResult**
  - **Files**: `backend/src/backend/app/models/bt_snapshot.py`, `bt_result.py`
  - **Action**: SQLAlchemy models with relationships, Decimal columns
  - **Requirements**: BTE-01
  - **Acceptance**: Models map to bt_* tables; no float columns; Decimal(20,8)
  - **Tests**: `test_types.py` — model creation, relationships, constraints
  - **Depends**: T1.1
  - **Est LOC**: ~70

- [ ] **T1.3: Domain types — DrawContext, BacktestConfig, MetricSet, WindowResult, BacktestResult**
  - **Files**: `backend/src/backend/app/backtesting/types.py`
  - **Action**: Dataclasses with frozen=True, proper types
  - **Requirements**: BTE-01, BTE-08, BTE-15
  - **Acceptance**: All types immutable; MetricSet uses Decimal; WindowResult tracks per-window
  - **Tests**: `test_types.py` — creation, immutability, Decimal quantization
  - **Depends**: —
  - **Est LOC**: ~60

- [ ] **T1.4: Version constant**
  - **Files**: `backend/src/backend/app/backtesting/version.py`
  - **Action**: `BACKTEST_GENERATOR_VERSION = "1.0.0"`
  - **Requirements**: BTE-06
  - **Acceptance**: Constant exists and is importable
  - **Tests**: `test_types.py` — version import
  - **Depends**: —
  - **Est LOC**: ~5

- [ ] **T1.5: Package seam — __init__.py**
  - **Files**: `backend/src/backend/app/backtesting/__init__.py`
  - **Action**: Docstring only, no logic
  - **Requirements**: —
  - **Acceptance**: Package importable; no logic
  - **Tests**: —
  - **Depends**: —
  - **Est LOC**: ~5

### PR1 Gate
- [ ] Migration 0012 upgrade/downgrade verified
- [ ] ORM models map correctly to bt_* tables
- [ ] All types created and importable
- [ ] ruff check + format clean
- [ ] Tests pass: test_types.py, test_migration.py

---

## PR2: Core Primitives (~300 LOC impl)

### Tasks

- [ ] **T2.1: Fingerprint computation**
  - **Files**: `backend/src/backend/app/backtesting/fingerprint.py`
  - **Action**: `compute_bt_fingerprint()` — SHA-256 over strategy+config+data+seed+windows+version
  - **Requirements**: BTE-06, BTE-18
  - **Acceptance**: Same inputs → same fingerprint; any change → different fingerprint
  - **Tests**: `test_fingerprint.py` — idempotency, input sensitivity, config affects fingerprint
  - **Depends**: T1.3, T1.4
  - **Est LOC**: ~50

- [ ] **T2.2: DeterminismContext — seed management**
  - **Files**: `backend/src/backend/app/backtesting/determinism.py`
  - **Action**: `DeterminismContext` class, `quantize_metric()` for Decimal(20,8)
  - **Requirements**: BTE-05, BTE-08
  - **Acceptance**: Same seed → identical RNG states; quantize_metric returns Decimal(20,8)
  - **Tests**: `test_determinism.py` — reproducibility, quantization precision
  - **Depends**: T1.3
  - **Est LOC**: ~60

- [ ] **T2.3: WalkForwardSplitter — window construction**
  - **Files**: `backend/src/backend/app/backtesting/splitter.py`
  - **Action**: `WalkForwardSplitter.split()` — generate windows from sorted draws
  - **Requirements**: BTE-04, BTE-07, BTE-17
  - **Acceptance**: Train < eval in time; no overlap; min_train_draws enforced; covers full range
  - **Tests**: `test_splitter.py` — standard walk-forward, no look-ahead, min draws, first/last windows, edge cases
  - **Depends**: T1.3
  - **Est LOC**: ~100

- [ ] **T2.4: StrategyProtocol and adapters**
  - **Files**: `backend/src/backend/app/backtesting/strategy.py`
  - **Action**: `StrategyProtocol`, `MLStrategyAdapter`, `DLStrategyAdapter`
  - **Requirements**: BTE-03, BTE-11
  - **Acceptance**: Protocol defines predict(); adapters use lazy imports; no module-level ml/dl coupling
  - **Tests**: `test_strategy.py` — protocol compliance, adapter isolation, lazy imports verified
  - **Depends**: T1.3
  - **Est LOC**: ~80

### PR2 Gate
- [ ] Fingerprint idempotency verified
- [ ] DeterminismContext produces reproducible RNG states
- [ ] WalkForwardSplitter enforces temporal ordering
- [ ] StrategyProtocol adapters use lazy imports
- [ ] ruff check + format clean
- [ ] Tests pass: test_fingerprint.py, test_determinism.py, test_splitter.py, test_strategy.py

---

## PR3: Metrics + Benchmarks (~350 LOC impl)

### Tasks

- [ ] **T3.1: Lottery-specific metrics calculator**
  - **Files**: `backend/src/backend/app/backtesting/metrics.py`
  - **Action**: `LotteryMetrics.compute()` — hit_rate, match_distribution, average_matches, consistency_score
  - **Requirements**: BTE-08
  - **Acceptance**: Metrics match manual calculation; all Decimal(20,8); deterministic
  - **Tests**: `test_metrics.py` — calculation accuracy, Decimal quantization, deterministic, empty input
  - **Depends**: T1.3, T2.2
  - **Est LOC**: ~100

- [ ] **T3.2: Uniform random benchmark**
  - **Files**: `backend/src/backend/app/backtesting/benchmark.py`
  - **Action**: `UniformRandomBenchmark` — random predictions from uniform distribution
  - **Requirements**: BTE-09
  - **Acceptance**: Seed-based reproducibility; expected distribution for large samples
  - **Tests**: `test_benchmark.py` — reproducibility, distribution convergence
  - **Depends**: T2.2, T2.4
  - **Est LOC**: ~60

- [ ] **T3.3: F5 hypergeometric benchmark**
  - **Files**: `backend/src/backend/app/backtesting/benchmark.py`
  - **Action**: `HypergeometricBenchmark` — lazy-import F5 probability engine
  - **Requirements**: BTE-09, BTE-11
  - **Acceptance**: Lazy import of probability.engine; matches F5 output; no module-level coupling
  - **Tests**: `test_benchmark.py` — F5 integration, lazy import verified, output matches F5
  - **Depends**: T2.4
  - **Est LOC**: ~60

- [ ] **T3.4: Benchmark evaluation-period alignment**
  - **Files**: `backend/src/backend/app/backtesting/benchmark.py`
  - **Action**: Ensure both benchmarks use same evaluation windows as strategy
  - **Requirements**: BTE-16
  - **Acceptance**: Benchmark eval windows == strategy eval windows
  - **Tests**: `test_benchmark.py` — same evaluation period verification
  - **Depends**: T2.3, T3.2, T3.3
  - **Est LOC**: ~30

- [ ] **T3.5: Metric aggregation across windows**
  - **Files**: `backend/src/backend/app/backtesting/metrics.py`
  - **Action**: `LotteryMetrics.aggregate()` — combine per-window metrics
  - **Requirements**: BTE-08, BTE-15
  - **Acceptance**: Aggregate metrics correctly weighted by window size
  - **Tests**: `test_metrics.py` — aggregation accuracy, edge cases
  - **Depends**: T3.1
  - **Est LOC**: ~50

### PR3 Gate
- [ ] Metrics match manual calculation
- [ ] Uniform benchmark produces expected distribution
- [ ] Hypergeometric benchmark matches F5
- [ ] Both benchmarks use same evaluation period
- [ ] ruff check + format clean
- [ ] Tests pass: test_metrics.py, test_benchmark.py

---

## PR4: Engine + Snapshot Store (~300 LOC impl)

### Tasks

- [ ] **T4.1: BtSnapshotStore — bt_* I/O owner**
  - **Files**: `backend/src/backend/app/backtesting/snapshot_store.py`
  - **Action**: `BtSnapshotStore` — get_active, find_by_fingerprint, next_version, create_active
  - **Requirements**: BTE-10
  - **Acceptance**: Atomic write (all or nothing); idempotent (same fingerprint → return active); lifecycle enforcement
  - **Tests**: `test_snapshot_store.py` — atomicity, idempotency, lifecycle transitions, version increment
  - **Depends**: T1.2
  - **Est LOC**: ~100

- [ ] **T4.2: BacktestEngine orchestrator**
  - **Files**: `backend/src/backend/app/backtesting/engine.py`
  - **Action**: `BacktestEngine.run()` — orchestrate walk-forward with strategy + benchmarks
  - **Requirements**: BTE-02, BTE-07, BTE-10, BTE-15, BTE-17
  - **Acceptance**: No non-bt_* writes; data floor enforced; window history tracked; temporal ordering
  - **Tests**: `test_engine.py` — isolation, data floor, window history, temporal ordering, full workflow
  - **Depends**: T2.1, T2.3, T2.4, T3.1, T3.2, T3.3, T3.4, T3.5, T4.1
  - **Est LOC**: ~150

- [ ] **T4.3: Engine integration tests**
  - **Files**: `backend/tests/bt/test_engine.py`
  - **Action**: Full engine workflow with mock strategy
  - **Requirements**: BTE-02, BTE-07, BTE-10, BTE-15
  - **Acceptance**: End-to-end engine pass; no non-bt_* writes; metrics computed
  - **Tests**: `test_engine.py` — full workflow, isolation, metrics
  - **Depends**: T4.2
  - **Est LOC**: ~50

### PR4 Gate
- [ ] BtSnapshotStore atomic writes verified
- [ ] Idempotency (same fingerprint → return existing)
- [ ] BacktestEngine produces valid results
- [ ] No non-bt_* table modifications
- [ ] ruff check + format clean
- [ ] Tests pass: test_snapshot_store.py, test_engine.py

---

## PR5: Service + API + CLI (~350 LOC impl)

### Tasks

- [ ] **T5.1: BtService composition root**
  - **Files**: `backend/src/backend/app/services/bt_service.py`
  - **Action**: `BtService.run()` — validate lottery, check floor, compute fingerprint, run engine, persist
  - **Requirements**: BTS-04, BTE-07, BTE-12
  - **Acceptance**: Atomic tx; idempotent; floor enforced; manual-only
  - **Tests**: `test_bt_service.py` — full service workflow, idempotency, floor, 404
  - **Depends**: T1.2, T2.1, T4.1, T4.2
  - **Est LOC**: ~100

- [ ] **T5.2: Pydantic v2 schemas**
  - **Files**: `backend/src/backend/app/schemas/bt.py`
  - **Action**: BacktestConfigSchema, BacktestRequest, MetricSetSchema, BacktestResultSchema, BacktestSummarySchema
  - **Requirements**: BTS-03
  - **Acceptance**: Pydantic v2; Decimal in metrics; validation works
  - **Tests**: `test_bt_schemas.py` — schema creation, validation, Decimal handling
  - **Depends**: T1.3
  - **Est LOC**: ~60

- [ ] **T5.3: API routes**
  - **Files**: `backend/src/backend/app/api/v1/bt.py`, `router.py` update
  - **Action**: POST /backtesting/run, GET /backtesting/history, GET /backtesting/results
  - **Requirements**: BTS-01, BTE-12
  - **Acceptance**: Manual-only; 404 for missing lottery; InsufficientDataError mapped; no predict/rank
  - **Tests**: `test_bt_api.py` — endpoint behavior, error mapping, no predict/rank
  - **Depends**: T5.1, T5.2
  - **Est LOC**: ~100

- [ ] **T5.4: CLI commands**
  - **Files**: `backend/src/backend/app/cli.py` additions
  - **Action**: `lip bt run|history|results` with parity to API
  - **Requirements**: BTS-02, BTE-12
  - **Acceptance**: CLI mirrors API; JSON output; floor behavior
  - **Tests**: `test_bt_cli.py` — command behavior, parity with API
  - **Depends**: T5.1
  - **Est LOC**: ~80

- [ ] **T5.5: Router registration**
  - **Files**: `backend/src/backend/app/api/v1/router.py`
  - **Action**: Mount bt_router
  - **Requirements**: BTS-01
  - **Acceptance**: bt_router mounted; routes discoverable
  - **Tests**: `test_bt_api.py` — route discovery
  - **Depends**: T5.3
  - **Est LOC**: ~10

### PR5 Gate
- [ ] BtService runs full workflow
- [ ] API endpoints respond correctly
- [ ] CLI parity with API
- [ ] No predict/rank/generate endpoints
- [ ] Error mapping correct (404, 422, 500)
- [ ] ruff check + format clean
- [ ] Tests pass: test_bt_service.py, test_bt_api.py, test_bt_cli.py, test_bt_schemas.py

---

## PR6: E2E Tests + Docs (~200 LOC impl)

### Tasks

- [ ] **T6.1: Multi-lottery isolation E2E**
  - **Files**: `backend/tests/bt/test_bt_e2e.py`
  - **Action**: Run backtests on two lotteries; verify isolation
  - **Requirements**: BTE-14
  - **Acceptance**: Lottery A backtest does not affect lottery B
  - **Tests**: `test_bt_e2e.py` — multi-lottery isolation
  - **Depends**: T4.2, T5.1
  - **Est LOC**: ~80

- [ ] **T6.2: Full workflow E2E**
  - **Files**: `backend/tests/bt/test_bt_e2e.py`
  - **Action**: Complete backtest workflow with ML adapter mock
  - **Requirements**: All (integration)
  - **Acceptance**: End-to-end pass; all metrics computed; snapshot persisted
  - **Tests**: `test_bt_e2e.py` — full workflow
  - **Depends**: T4.2, T5.1
  - **Est LOC**: ~80

- [ ] **T6.3: PROJECT_STATUS.md update**
  - **Files**: `PROJECT_STATUS.md`
  - **Action**: Add F10 Backtesting Engine status
  - **Requirements**: —
  - **Acceptance**: F10 documented
  - **Tests**: —
  - **Depends**: T6.1, T6.2
  - **Est LOC**: ~20

- [ ] **T6.4: Ruff check + format**
  - **Files**: All modified files
  - **Action**: `ruff check` + `ruff format`
  - **Requirements**: —
  - **Acceptance**: Clean lint and format
  - **Tests**: —
  - **Depends**: T6.1, T6.2, T6.3
  - **Est LOC**: ~0

### PR6 Gate
- [ ] Multi-lottery isolation verified
- [ ] Full workflow E2E passes
- [ ] PROJECT_STATUS.md updated
- [ ] ruff check + format clean
- [ ] All tests pass: test_bt_e2e.py

---

## Final Acceptance Criteria — 22 Requirements

| ID | Requirement | Status | Evidence |
|----|-------------|--------|----------|
| BTE-01 | Independent `bt_*` schema | — | test_types.py, test_migration.py |
| BTE-02 | Strict read-only vs other engines | — | test_engine.py |
| BTE-03 | Generic StrategyProtocol | — | test_strategy.py |
| BTE-04 | Walk-forward window splitter | — | test_splitter.py |
| BTE-05 | Determinism: seed-based | — | test_determinism.py |
| BTE-06 | Fingerprint inputs | — | test_fingerprint.py |
| BTE-07 | Data floor | — | test_engine.py, test_bt_service.py |
| BTE-08 | Lottery-specific metrics | — | test_metrics.py |
| BTE-09 | Dual benchmark | — | test_benchmark.py |
| BTE-10 | Snapshot lifecycle & atomicity | — | test_snapshot_store.py |
| BTE-11 | Provider Protocols only | — | test_strategy.py |
| BTE-12 | Manual-only surface | — | test_bt_api.py, test_bt_cli.py |
| BTE-13 | Migration 0012 additive | — | test_migration.py |
| BTE-14 | Multi-lottery isolation | — | test_bt_e2e.py |
| BTE-15 | Convergence tracking | — | test_engine.py |
| BTE-16 | Benchmark same evaluation period | — | test_benchmark.py |
| BTE-17 | Temporal ordering | — | test_splitter.py |
| BTE-18 | Walk-forward params in fingerprint | — | test_fingerprint.py |
| BTS-01 | API endpoints | — | test_bt_api.py |
| BTS-02 | CLI parity | — | test_bt_cli.py |
| BTS-03 | Schemas (Pydantic v2) | — | test_bt_schemas.py |
| BTS-04 | Service layer | — | test_bt_service.py |

---

## Summary

| Metric | Value |
|--------|-------|
| **Total PRs** | 6 |
| **Total Tasks** | 24 |
| **Total LOC Est.** | ~1,750 |
| **Requirements** | 22 (18 engine + 4 surface) |
| **Test Files** | 12 |
| **Max LOC/PR** | ~350 (PR3, PR5) |

### LOC by PR

| PR | LOC Est. | ≤400 |
|----|----------|------|
| PR1 | ~250 | ✅ |
| PR2 | ~300 | ✅ |
| PR3 | ~350 | ✅ |
| PR4 | ~300 | ✅ |
| PR5 | ~350 | ✅ |
| PR6 | ~200 | ✅ |

### Dependencies Between PRs

```
PR1 (Foundation) → PR2 (Core) → PR3 (Metrics) → PR4 (Engine) → PR5 (Service) → PR6 (E2E)
```

### Test Coverage

| Requirement | Test File | Positive | Negative | Boundary |
|-------------|-----------|----------|----------|----------|
| BTE-01 | test_types.py | ✅ | — | — |
| BTE-02 | test_engine.py | ✅ | ✅ | — |
| BTE-03 | test_strategy.py | ✅ | ✅ | — |
| BTE-04 | test_splitter.py | ✅ | ✅ | ✅ |
| BTE-05 | test_determinism.py | ✅ | ✅ | — |
| BTE-06 | test_fingerprint.py | ✅ | ✅ | — |
| BTE-07 | test_engine.py | ✅ | ✅ | ✅ |
| BTE-08 | test_metrics.py | ✅ | ✅ | ✅ |
| BTE-09 | test_benchmark.py | ✅ | ✅ | — |
| BTE-10 | test_snapshot_store.py | ✅ | ✅ | — |
| BTE-11 | test_strategy.py | ✅ | ✅ | — |
| BTE-12 | test_bt_api.py | ✅ | ✅ | — |
| BTE-13 | test_migration.py | ✅ | ✅ | — |
| BTE-14 | test_bt_e2e.py | ✅ | — | — |
| BTE-15 | test_engine.py | ✅ | — | — |
| BTE-16 | test_benchmark.py | ✅ | — | — |
| BTE-17 | test_splitter.py | ✅ | ✅ | ✅ |
| BTE-18 | test_fingerprint.py | ✅ | ✅ | — |
| BTS-01 | test_bt_api.py | ✅ | ✅ | — |
| BTS-02 | test_bt_cli.py | ✅ | ✅ | — |
| BTS-03 | test_bt_schemas.py | ✅ | ✅ | — |
| BTS-04 | test_bt_service.py | ✅ | ✅ | — |

---

**Ready for implementation upon authorization.**
