# Tasks: Fase 9 — Optimization Engine

**Change**: `fase-9-optimization-engine` · **Store**: openspec · **Date**: 2026-08-10
**Predecessors**: proposal, specs (opt-engine + backend delta), design complete

## Review Workload Forecast

| Metric | Value |
|--------|-------|
| Estimated total changed lines | ~2,050 |
| PR count | 6 (stacked-to-main) |
| Chain strategy | stacked-to-main |
| PR budget risk | Medium (6 PRs, each ≤400 LOC) |
| Decision needed before apply: No |

## PR Plan

```
PR1: Foundation (~250 LOC) — deps, migration, ORM models, ban-gate
  ↓
PR2: Core Engine (~350 LOC) — registry, fingerprint, determinism, providers, search_space, convergence, snapshot_store
  ↓
PR3: Optimizers (~400 LOC) — GA (deap), PSO (custom), Bayesian (optuna), SA (custom)
  ↓
PR4: Engine + Objective (~380 LOC) — orchestrator, objective function closure
  ↓
PR5: Service + API + CLI (~350 LOC) — opt_service, routes, schemas, CLI
  ↓
PR6: E2E + Docs (~300 LOC) — GF1 determinism test, docs, archive
```

## Dependency Diagram

```
📍 PR1: Foundation
    ├── pyproject.toml (deap + optuna pins + signed exceptions)
    ├── alembic/versions/0011_opt_tables.py
    ├── models/opt_snapshot.py + opt_result.py
    ├── models/__init__.py (register entities)
    └── tests/test_opt_pr1.py (ban-gate)

📍 PR2: Core Engine (depends: PR1)
    ├── app/opt/__init__.py
    ├── app/opt/version.py
    ├── app/opt/registry.py
    ├── app/opt/fingerprint.py
    ├── app/opt/determinism.py
    ├── app/opt/providers.py
    ├── app/opt/search_space.py
    ├── app/opt/convergence.py
    ├── app/opt/snapshot_store.py
    └── tests/opt/test_{registry,fingerprint,determinism,search_space,convergence,snapshot_store}.py

📍 PR3: Optimizers (depends: PR2)
    ├── app/opt/ga.py
    ├── app/opt/pso.py
    ├── app/opt/bayesian.py
    ├── app/opt/sa.py
    └── tests/opt/test_{ga,pso,bayesian,sa}.py

📍 PR4: Engine + Objective (depends: PR2, PR3)
    ├── app/opt/objective.py
    ├── app/opt/engine.py
    └── tests/opt/test_{objective,engine}.py

📍 PR5: Service + API + CLI (depends: PR1, PR4)
    ├── services/opt_service.py
    ├── api/v1/opt.py
    ├── api/v1/router.py (mount /opt)
    ├── schemas/opt.py
    ├── cli.py (lip opt commands)
    └── tests/opt/test_{service,api,cli}.py

📍 PR6: E2E + Docs (depends: PR5)
    ├── tests/opt/test_opt_determinism_e2e.py (GF1)
    ├── specs/opt-engine/spec.md
    ├── API_SPECIFICATION.md §10
    ├── README.md updates
    ├── PROJECT_STATUS.md updates
    └── openspec/changes/fase-9-optimization-engine/archive/
```

## Tasks

### PR1: Foundation

- [x] **T1.1: pyproject.toml — deap + optuna pins**
- **Files**: `backend/pyproject.toml`
- **Action**: Add `deap==1.4.1` and `optuna==4.0.0` to `[project.dependencies]` with signed exception comments
- **Acceptance**: Both deps present; comments reference Fase-9, D2, OE-09
- **Tests**: Ban-gate test asserts both present
- **Depends**: —
- **Est LOC**: ~20

- [x] **T1.2: ORM models — opt_snapshot + opt_result**
- **Files**: `backend/src/backend/app/models/opt_snapshot.py`, `opt_result.py`, `__init__.py`
- **Action**: Create ORM models matching design schema; register in `__init__.py`
- **Acceptance**: Models match SQL schema; Numeric(20,8) for fitness/metrics
- **Tests**: Import check, model attributes
- **Depends**: —
- **Est LOC**: ~80

- [x] **T1.3: Migration 0011_opt_tables**
- **Files**: `backend/alembic/versions/0011_opt_tables.py`
- **Action**: Create migration with `down_revision="0010_dl_tables"`; creates opt_snapshots + opt_results + indexes
- **Acceptance**: Upgrade creates tables; downgrade drops only opt_*; prior tables byte-identical
- **Tests**: Migration up/down test
- **Depends**: T1.2
- **Est LOC**: ~80

- [x] **T1.4: Ban-gate tests**
- **Files**: `backend/tests/test_opt_pr1.py`, modify `test_ml_pr1.py`, `test_dl_pr1.py`
- **Action**: Create PR1 dependency gate test; extend ML/DL ban-gates to scan for deap/optuna
- **Acceptance**: deap + optuna present in F9 tree; absent from F7/F8 trees
- **Tests**: `test_opt_pr1.py` passes
- **Depends**: T1.1, T1.2
- **Est LOC**: ~70

### PR2: Core Engine

- [x] **T2.1: Package init + version** (incluido en PR1)
- **Files**: `backend/src/backend/app/opt/__init__.py`, `version.py`
- **Action**: Package seam with docstrings; `OPTIMIZER_GENERATOR_VERSION = "1.0.0"`
- **Acceptance**: Import succeeds; version constant available
- **Tests**: Import check
- **Depends**: PR1
- **Est LOC**: ~10

- [x] **T2.2: Registry**
- **Files**: `backend/src/backend/app/opt/registry.py`
- **Action**: `build_opt_registry()` → immutable dict with ga, pso, bayesian, sa; unknown optimizer fails fast
- **Acceptance**: Returns exactly 4 optimizers; unknown raises ValueError with known IDs
- **Tests**: `tests/opt/test_registry.py`
- **Depends**: T2.1
- **Est LOC**: ~50

- [x] **T2.3: Fingerprint**
- **Files**: `backend/src/backend/app/opt/fingerprint.py`
- **Action**: `compute_opt_fingerprint()` → SHA-256 canonical JSON; sort_keys=True
- **Acceptance**: Equal inputs → identical hex; key order irrelevant; changes on any input change
- **Tests**: `tests/opt/test_fingerprint.py`
- **Depends**: T2.1
- **Est LOC**: ~40

- [x] **T2.4: Determinism**
- **Files**: `backend/src/backend/app/opt/determinism.py`
- **Action**: `quantize_metric()`, `compute_metrics_checksum()` (F7/F8 parity)
- **Acceptance**: Decimal(20,8) quantization; checksum over quantized values only
- **Tests**: `tests/opt/test_determinism.py`
- **Depends**: T2.1
- **Est LOC**: ~30

- [x] **T2.5: Providers**
- **Files**: `backend/src/backend/app/opt/providers.py`
- **Action**: `DrawHistoryProvider`, `FeatureSnapshotProvider` Protocols + frozen dataclasses
- **Acceptance**: Protocols defined; zero imports from ml/dl/services/repositories
- **Tests**: `tests/opt/test_providers.py` (mock-based)
- **Depends**: T2.1
- **Est LOC**: ~40

- [x] **T2.6: Search space**
- **Files**: `backend/src/backend/app/opt/search_space.py`
- **Action**: `validate_search_space()`, `sample_point()`, type validation
- **Acceptance**: Invalid types raise clear error; continuous/discrete/integer supported
- **Tests**: `tests/opt/test_search_space.py`
- **Depends**: T2.1
- **Est LOC**: ~50

- [x] **T2.7: Convergence tracker**
- **Files**: `backend/src/backend/app/opt/convergence.py`
- **Action**: `ConvergenceTracker` class: record, history, to_json
- **Acceptance**: Append-only; monotonically increasing eval_num; JSON-serializable
- **Tests**: `tests/opt/test_convergence.py`
- **Depends**: T2.1
- **Est LOC**: ~40

- [x] **T2.8: Snapshot store**
- **Files**: `backend/src/backend/app/opt/snapshot_store.py`
- **Action**: `OptSnapshotStore` with get_active, find_by_fingerprint, next_version, create_snapshot, retire_old_active, mark_failed, bulk_insert_results
- **Acceptance**: Atomic replace; failure = only failed header; fingerprint idempotent
- **Tests**: `tests/opt/test_snapshot_store.py`
- **Depends**: T1.2, T1.3
- **Est LOC**: ~80

### PR3: Optimizers

- [x] **T3.1: GA optimizer (deap)** (en PR3A)
- **Files**: `backend/src/backend/app/opt/ga.py`
- **Action**: `GaOptimizer.optimize()` using deap toolbox; tournament selection, elitism
- **Acceptance**: Produces convergence history with `generations` entries; best preserved
- **Tests**: `tests/opt/test_ga.py`
- **Depends**: PR2
- **Est LOC**: ~120

- [x] **T3.2: PSO optimizer (custom)** (en PR3B)
- **Files**: `backend/src/backend/app/opt/pso.py`
- **Action**: `PsoOptimizer.optimize()` — custom swarm implementation
- **Acceptance**: Produces convergence history with `max_iterations` entries; global best tracked
- **Tests**: `tests/opt/test_pso.py`
- **Depends**: PR2
- **Est LOC**: ~60

- [x] **T3.3: Bayesian optimizer (optuna)** (en PR3B)
- **Files**: `backend/src/backend/app/opt/bayesian.py`
- **Action**: `BayesianOptimizer.optimize()` using optuna TPE sampler
- **Acceptance**: Produces convergence history with `n_trials` entries; params improve
- **Tests**: `tests/opt/test_bayesian.py`
- **Depends**: PR2
- **Est LOC**: ~70

- [x] **T3.4: SA optimizer (custom)** (en PR3A)
- **Files**: `backend/src/backend/app/opt/sa.py`
- **Action**: `SaOptimizer.optimize()` — custom annealing implementation
- **Acceptance**: Produces convergence history with `max_iterations` entries; temperature decreases
- **Tests**: `tests/opt/test_sa.py`
- **Depends**: PR2
- **Est LOC**: ~50

- [x] **T3.5: Optimizer protocol + shared types** (en PR3A)
- **Files**: `backend/src/backend/app/opt/optimizers/__init__.py` (or inline in each module)
- **Action**: `OptimizerProtocol`, `OptResult`, `ConvergenceEntry` dataclasses
- **Acceptance**: All 4 optimizers conform to protocol
- **Tests**: Protocol compliance in each optimizer test
- **Depends**: T2.1
- **Est LOC**: ~40

### PR4: Engine + Objective

- [x] **T4.1: Objective function**
- **Files**: `backend/src/backend/app/opt/objective.py`
- **Action**: `ObjectiveFunction` class wrapping ml.engine/dl.engine; walk-forward split; returns Decimal fitness
- **Acceptance**: Closure captures engine + data + split; returns quantized Decimal; never exposes eval data to optimizer
- **Tests**: `tests/opt/test_objective.py`
- **Depends**: PR2, PR3
- **Est LOC**: ~100

- [x] **T4.2: Engine orchestrator**
- **Files**: `backend/src/backend/app/opt/engine.py`
- **Action**: `train()` function: build objective → select optimizer → run optimize → return TrainResult
- **Acceptance**: Orchestrates all components; deterministic with same seed
- **Tests**: `tests/opt/test_engine.py`
- **Depends**: T4.1
- **Est LOC**: ~80

- [x] **T4.3: Engine integration tests**
- **Files**: `tests/opt/test_engine_integration.py`
- **Action**: Test engine with all 4 optimizers on mock objective
- **Acceptance**: All optimizers produce valid results; convergence tracked
- **Tests**: `tests/opt/test_engine_integration.py`
- **Depends**: T4.2
- **Est LOC**: ~60

### PR5: Service + API + CLI

- [x] **T5.1: Service layer**
- **Files**: `backend/src/backend/app/services/opt_service.py`
- **Action**: `OptService.train()` — floor check → providers → objective → optimize → snapshot
- **Acceptance**: Atomic tx; INSUFFICIENT_DATA below floor; fingerprint idempotent
- **Tests**: `tests/opt/test_service.py`
- **Depends**: PR1, PR4
- **Est LOC**: ~100

- [x] **T5.2: API routes**
- **Files**: `backend/src/backend/app/api/v1/opt.py`, `router.py`
- **Action**: POST /opt/train, GET /opt/models, GET /opt/metrics, GET /opt/params
- **Acceptance**: 404/422 maps; no /opt/predict; envelope responses
- **Tests**: `tests/opt/test_api.py`
- **Depends**: T5.1
- **Est LOC**: ~120

- [x] **T5.3: Schemas**
- **Files**: `backend/src/backend/app/schemas/opt.py`
- **Action**: TrainRequest, ModelsList, MetricsRead, ParamsRead, response schemas
- **Acceptance**: Match design; Pydantic v2
- **Tests**: Schema validation tests
- **Depends**: —
- **Est LOC**: ~60

- [x] **T5.4: CLI commands**
- **Files**: `backend/src/backend/app/cli.py`
- **Action**: `lip opt train|models|metrics|params` with same options as API
- **Acceptance**: Parity with API; JSON output; floor behavior
- **Tests**: `tests/opt/test_cli.py`
- **Depends**: T5.1
- **Est LOC**: ~80

### PR6: E2E + Docs

- [x] **T6.1: GF1 determinism E2E**
- **Files**: `backend/tests/opt/test_opt_determinism_e2e.py`
- **Action**: Two seeded runs on identical synthetic fixture → identical fingerprint + convergence + params
- **Acceptance**: Byte-identical results; all 4 optimizers produce convergence
- **Tests**: `tests/opt/test_opt_determinism_e2e.py`
- **Depends**: PR5
- **Est LOC**: ~100

- [x] **T6.2: Specs update**
- **Files**: `openspec/specs/opt-engine/spec.md`, `openspec/specs/backend/spec.md`
- **Action**: Finalize specs with delivered state
- **Acceptance**: Specs match implementation
- **Tests**: —
- **Depends**: PR5
- **Est LOC**: ~50

- [x] **T6.3: Docs + archive**
- **Files**: README.md, PROJECT_STATUS.md, API_SPECIFICATION.md §10, openspec archive
- **Action**: Update docs; archive change
- **Acceptance**: All docs reflect F9 delivery
- **Tests**: —
- **Depends**: T6.1, T6.2
- **Est LOC**: ~80

## Risk Register

| Risk | L | Mitigation | Task |
|------|---|------------|------|
| Optimizer overfits to train set | High | Walk-forward in objective closure | T4.1 |
| Stochastic non-reproducibility | High | Seed-based; termination in fingerprint | T6.1 |
| deap/optuna scope creep | Med | Signed comments, ban-gate tests | T1.1, T1.4 |
| Convergence noise | Med | Decimal-quantized metrics | T2.4 |
| Early stopping alters fixed result | Med | Same evaluation order | T3.1-T3.4 |
| Optuna sklearn conflict | Low | optuna uses bundled sklearn | T3.3 |
