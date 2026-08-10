# Proposal: Fase 10 — Backtesting Engine

## Intent

Evaluate prediction strategies (ML/DL models, generators, rules) against historical lottery data using walk-forward validation. Provides objective evidence of strategy performance before deployment, enabling comparison against random baselines and across strategies. Every strategy must prove its worth through backtesting before it can be recommended.

## Scope

### In Scope
- Walk-forward validation engine with configurable train/eval windows
- Generic strategy/provider abstraction (not coupled to ML/DL)
- Lottery-specific metrics: hit rate, match distribution, average matches
- Dual benchmark: uniform random + F5 hypergeometric null-model
- Deterministic, reproducible runs with SHA-256 fingerprinting
- `bt_*` snapshot persistence (immutable, versioned, active|retired|failed)
- API surface: `POST /bt/run`, `GET /bt/history`, `GET /bt/results`
- CLI parity: `lip bt run|history|results`
- Data floor: `InsufficientDataError` for insufficient historical draws

### Out of Scope
- F11: Experiment tracking, cross-run comparison, versioning
- F13: Number generation, combination selection
- F9: Hyperparameter optimization (already complete)
- Real-time prediction
- File export (API/CLI only)
- Dashboard visualization (F14)
- Trading metrics (Sharpe, Sortino, Calmar) — not relevant for lottery

## Capabilities

### New Capabilities
- `backtesting-engine`: Walk-forward validation, strategy abstraction, benchmarks, lottery-specific metrics, bt_* snapshots, API/CLI surface

### Modified Capabilities
- `backend`: REQ-13 (new) — Manual backtesting endpoints and CLI commands

## Approach

### Architecture

```
backtesting/
├── __init__.py
├── types.py              # BacktestConfig, BacktestResult, MetricSet (shared types)
├── fingerprint.py        # SHA-256 fingerprint over config+data+seed
├── determinism.py        # Seed management, DeterminismContext
├── splitter.py           # Walk-forward window splitter (train/eval pairs)
├── metrics.py            # Lottery-specific metrics calculator
├── benchmark.py          # Uniform random + hypergeometric baselines
├── strategy.py           # StrategyProtocol + adapter interface
├── engine.py             # BacktestEngine orchestrator
└── snapshot_store.py     # bt_* snapshot persistence
```

### Key Design Decisions

1. **Generic Strategy Contract**: `StrategyProtocol` defines `predict(draw_context) -> List[int]`. ML/DL engines adapt via `MLStrategyAdapter` / `DLStrategyAdapter`. No module-level coupling.

2. **Walk-Forward Semantics**: User-configurable windows. Strict temporal ordering: train on [t0, tN), evaluate on [tN, tN+1). Zero look-ahead. Parameters in fingerprint.

3. **Lottery-Specific Metrics**: Hit rate (exact matches), match distribution (k-of-n), average matches, consistency score. No trading metrics.

4. **Dual Benchmark**: Uniform random (baseline) + F5 hypergeometric null-model. Same evaluation period as strategy.

5. **Fingerprint Inputs**: strategy_id + config + data_hash + seed + window_params + benchmark_type.

6. **Snapshot Lifecycle**: `bt_*` tables. Active → retired → failed. Atomic writes. Manual-only trigger.

7. **Data Floor**: Minimum draws required (configurable, default 100). `InsufficientDataError` below floor.

8. **F10/F11 Boundary**: F10 produces single-run results. F11 tracks and compares across runs. Ranking within a run is F10; cross-run ranking is F11.

9. **F10/F13 Boundary**: F10 evaluates existing strategies. F13 generates new combinations. F10 never generates numbers.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `backend/src/backend/app/backtesting/` | New | Core engine modules |
| `backend/src/backend/app/models/bt_snapshot.py` | New | ORM model |
| `backend/src/backend/app/models/bt_result.py` | New | ORM model |
| `backend/alembic/versions/0012_bt_tables.py` | New | Migration |
| `backend/src/backend/app/services/bt_service.py` | New | Service layer |
| `backend/src/backend/app/api/v1/bt.py` | New | API routes |
| `backend/src/backend/app/api/v1/router.py` | Modified | Mount bt_router |
| `backend/src/backend/app/schemas/bt.py` | New | Pydantic schemas |
| `backend/src/backend/app/cli.py` | Modified | Add bt commands |
| `backend/tests/bt/` | New | Test suite |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Look-ahead bias in walk-forward | Medium | Strict temporal splitter; tests verify no future data leakage |
| Overfitting detection missing | Low | Deferred to F11; F10 provides raw metrics only |
| Performance with large histories | Medium | Vectorized numpy/pandas; configurable window limits |
| F5 hypergeometric coupling | Low | Reuse existing prob engine; lazy import inside function |

## Rollback Plan

1. Remove `bt_*` migration (0012)
2. Remove `backtesting/` package
3. Remove API routes, CLI commands, service
4. Revert `router.py` and `cli.py` changes
5. No data loss (bt_* tables only)

## Dependencies

- F5 Probability Engine (hypergeometric baseline) — already complete
- F7 ML Engine (adapter for ML strategies) — already complete
- F8 DL Engine (adapter for DL strategies) — already complete
- numpy/pandas — already present

## Success Criteria

- [ ] Walk-forward produces valid train/eval splits with zero look-ahead
- [ ] StrategyProtocol allows ML/DL adapters without module-level coupling
- [ ] Uniform random benchmark produces expected distribution
- [ ] Hypergeometric benchmark matches F5 implementation
- [ ] Same seed + same data + same config = identical results
- [ ] bt_* snapshots are immutable and versioned
- [ ] API/CLI parity with established envelope pattern
- [ ] Data floor enforced via InsufficientDataError
- [ ] All tests pass; ruff clean
