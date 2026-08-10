# Archive Report — Fase 9: Optimization Engine

**Change**: `fase-9-optimization-engine`  
**Store**: `openspec`  
**Archived**: `2026-08-10`  
**Archived to**: `openspec/changes/archive/2026-08-10-fase-9-optimization-engine/`

## Purpose

Hyperparameter optimization engine with 4 algorithms (GA, PSO, Bayesian, SA), seed-based determinism, SHA-256 fingerprint, atomic snapshot lifecycle (active→retired→failed), and full API/CLI surface parity.

## Scope

- **In scope**: Hyperparameter optimization only — search space, convergence, fingerprint, determinism, registry, providers (GA, PSO, Bayesian, SA), objective function closure, engine orchestrator, service, API (4 endpoints), CLI (4 commands), E2E determinism/isolation tests
- **Out of scope**: F10 (backtesting), F11 (experiments/comparison), F13 (number generation), `/opt/predict`, ranking surfaces

## Final State

### Commits on Main

| # | Hash | Description | LOC Impl |
|---|------|-------------|----------|
| 1 | `6e27f08` | Foundation — pyproject.toml (deap+optuna pins), migration 0011, ORM models, ban-gate tests | 256 |
| 2 | `5d76ec1` | Core primitives — registry, fingerprint, determinism, providers | 236 |
| 3 | `cb490f5` | Search/persistence — search_space, convergence, snapshot_store | 364 |
| 4 | `064e611` | GA + SA optimizers + shared types (OptimizerProtocol, TerminationConfig, OptResult) | 306 |
| 5 | `974dbf0` | PSO + Bayesian optimizers | 228 |
| 6 | `610ccb6` | Engine + Objective — orchestrator, objective function closure | 216 |
| 7 | `eee0efa` | Service + API + CLI — opt_service, 4 endpoints, 4 CLI commands, schemas | 343 |
| 8 | `1c59b42` | E2E determinism/isolation tests (21 tests) + PROJECT_STATUS update | docs/tests |
| 9 | `f6d8f04` | OE-08 data floor fix — InsufficientDataError, MIN_DRAWS=100, 10 new tests | 10 tests |

**Total LOC impl**: ~1,949  
**Total tests**: 129

### Test Results

- **Verify**: ALL 13 items PASS (OE-01..15, REQ-10/11/12, migration, isolation, GF1, anti-leakage, data floor, fingerprint, 4 optimizers, manual-only, multi-lottery, suite+Ruff, working tree)
- **OE-08 fix**: Data floor check (<100 draws → INSUFFICIENT_DATA) was found missing during verify; fixed in commit `f6d8f04`

### Tasks

All T1–T6 tasks marked [x] in `tasks.md` (6 PRs × task groups = 21 tasks total).

## Specs Synced

| Domain | Action | Details |
|--------|--------|---------|
| `opt-engine` | Created | New spec — 15 requirements (OE-01..15) + 4 per-algorithm (OA-01..04) |
| `backend` | Updated | REQ-10/11/12 modified — added /opt/* surface (train, models, metrics, params) |

## Source of Truth Updated

The following specs now reflect the delivered behavior:
- `openspec/specs/opt-engine/spec.md` — full spec for OE-01..15 + OA-01..04
- `openspec/specs/backend/spec.md` — REQ-10/11/12 updated with /opt/* endpoints

## Key Design Decisions

1. **OE-11 Isolation**: `opt/` never imports `ml/`, `dl/`, `services/`, or `repositories/` at module level; lazy imports inside functions only
2. **Seed-based determinism**: `DeterminismGuard` manages RNG states; all optimizers consume shared `DeterminismContext`
3. **SHA-256 fingerprint**: `Fingerprint.compute()` hashes config + search space + seed for idempotency
4. **Decimal(20,8) quantization**: All fitness/metric values stored as `Decimal(20,8)` for precision
5. **Atomic snapshot lifecycle**: `active→retired→failed` state machine with DB transactions
6. **Objective function closure**: Wraps `ml.engine.train()`/`dl.engine.train()` with kwargs binding
7. **100-draw floor**: `InsufficientDataError` with `MIN_DRAWS=100` enforced at service/API/CLI level

## Files Changed

### New Files
- `backend/src/backend/app/opt/` — 15 modules (registry, fingerprint, determinism, providers, search_space, convergence, snapshot_store, optimizer_types, ga, pso, bayesian, sa, objective, engine)
- `backend/src/backend/app/services/opt_service.py`
- `backend/src/backend/app/api/v1/opt.py`
- `backend/src/backend/app/schemas/opt.py`
- `backend/src/backend/app/models/opt_snapshot.py`
- `backend/src/backend/app/models/opt_result.py`
- `backend/alembic/versions/0011_opt_tables.py`
- `backend/tests/opt/` — 15 test files

### Modified Files
- `backend/pyproject.toml` — deap + optuna signed exceptions
- `backend/src/backend/app/services/errors.py` — InsufficientDataError added
- `backend/src/backend/app/api/v1/router.py` — opt_router mounted
- `backend/src/backend/app/cli.py` — 4 CLI commands + _cli_count_draws
- `PROJECT_STATUS.md` — updated with F9 status

## SDD Cycle Complete

The change has been fully planned, implemented, verified, and archived.
Ready for the next change (F10: backtesting).
