# Design: Fase 9 — Optimization Engine

**Change**: `fase-9-optimization-engine` · **Store**: `openspec` · **Date**: 2026-08-10
**Predecessors**: exploration → proposal (D1–D9) → spec (`opt-engine` OE-01..15, OA-01..04; `backend` REQ-10/11/12 delta)

## Technical Approach

A new engine package `app/opt/` mirroring F7/F8 skeleton (engine, registry, fingerprint, determinism, providers, snapshot_store, version) plus four optimizer modules (ga, pso, bayesian, sa) and a convergence tracker. Pure engine stays DB-free; `OptService` is the composition root owning one atomic transaction per run. F7/F8 are imported only through Provider Protocols and direct engine calls at the composition root — the `opt/` package never imports concrete ML/DL implementations (OE-11 isolation). Deps: `deap` GA library + `optuna` Bayesian library, both exact-pinned with signed exceptions limited to F9. Optimizers run-scoped `core-4` (GA, PSO, Bayesian, SA all executed; no future-X declared).

## Architecture Decisions

| # | Decision | Alternatives | Rationale |
|---|---|---|---|
| D-A1 | **One `opt_snapshots` row per optimization run**, one `opt_results` row per target model | Per-algorithm snapshot | OE-09/10 require one active per `(lottery_id, optimizer_set)`; one run produces one best result per model trained |
| D-A2 | `opt/` 100% self-contained; duplicate `quantize_metric`/`compute_metrics_checksum` (~15 LOC) in `opt/determinism.py` | Import from `ml/determinism.py` or `dl/determinism.py` | OE-11 "Provider Protocols only" + F7/F8 frozen; zero-risk isolation, parity marked by comment |
| D-A3 | Objective function is a **closure** that wraps `ml.engine.train()` or `dl.engine.train()` | Pass pre-trained models; separate objective module | D5 "direct calls"; closure captures search space + data + split; optimizers are agnostic to target engine |
| D-A4 | Fingerprint is **run-scoped**: `{optimizer, algorithm_params, objective_metric, objective_direction, search_space, data_hash, seed, OPTIMIZER_GENERATOR_VERSION, termination_params}` | Per-algorithm fingerprint | One snapshot/run ⇒ one fingerprint key for OE-10 idempotency |
| D-A5 | Convergence history stored as JSON list of `{eval_num, fitness, timestamp}` in `opt_results` | Separate convergence table | Simplicity; one row per model result; history is append-only within a run |
| D-A6 | Search space defined as JSON schema with typed ranges (continuous/discrete/integer) | Python objects; numpy arrays | JSON-serializable = fingerprint-friendly; matches project's Decimal/JSON persistence pattern |
| D-A7 | Early stopping checked **after** each generation/iteration; when disabled, result is identical to fixed termination | Early stopping as separate code path | OE-06 "early stopping must NOT alter result when disabled"; same evaluation order = same numeric result |
| D-A8 | `INSUFFICIENT_DATA` = new `ServiceError` code → envelope 422; same as DL (D-A7) | 400; 500 | Clean result below floor (OE-08, never 500); consistent with DL precedent |

## Data Flow

    CLI lip opt train ─┐
    POST /opt/train ───┤→ OptService.train(lottery_id, optimizer, model_set, objective, termination)
                       │    1. count draws < 100 ⇒ INSUFFICIENT_DATA (no rows)
                       │    2. active F4 snapshot? None ⇒ SNAPSHOT_NOT_FOUND
                       │    3. Build objective function closure:
                       │       - ml.engine.train() or dl.engine.train() wrapped
                       │       - walk-forward split enforced
                       │       - metrics quantize → Decimal fitness
                       │    4. Optimizer.optimize(objective_fn, search_space, seed) → OptResult
                       │         GA: deap toolbox → generations loop → best individual
                       │         PSO: swarm loop → global best
                       │         Bayesian: optuna study → best trial
                       │         SA: temperature loop → best state
                       │    5. create_snapshot(active) → bulk results → retire_old
                       │       → commit; failure ⇒ rollback + terminal failed header
                       └→ opt_snapshots + opt_results (only opt_* touched, OE-02)

    GET /opt/models|metrics|params → OptStore reads active snapshot only; 404 SNAPSHOT_NOT_FOUND; never optimizes.

## Module Map (`backend/src/backend/app/opt/`)

| Module | Responsibility | Public API |
|---|---|---|
| `__init__.py` | Package seam, docstrings only | — |
| `version.py` | `OPTIMIZER_GENERATOR_VERSION = "1.0.0"` | constant |
| `registry.py` | Dict-dispatch; `OPTIMIZER_SET_CORE_4`, no future families | `build_opt_registry()` → immutable `{slug: (optimizer_class, defaults)}`; unknown optimizer fails fast (OE-09) |
| `fingerprint.py` | Canonical SHA-256, `sort_keys=True` | `compute_opt_fingerprint(optimizer, algorithm_params, objective, search_space, data_hash, seed, version, termination_params)` |
| `determinism.py` | Seed-based; local quantize/checksum (F7/F8 parity) | `quantize_metric`, `compute_metrics_checksum` (OE-06/07) |
| `providers.py` | Protocols: `DrawHistoryProvider`, `FeatureSnapshotProvider` (OE-11) | Protocols + frozen dataclasses (DrawRow, FeatureRow) |
| `search_space.py` | Search space validation and sampling | `validate_search_space(schema)`, `sample_point(schema, rng)` |
| `convergence.py` | Convergence history tracking | `ConvergenceTracker` class: `record(eval_num, fitness)`, `history` property, `to_json()` |
| `ga.py` | Genetic Algorithm via deap | `GaOptimizer.optimize(objective_fn, search_space, seed, params) → OptResult` |
| `pso.py` | Particle Swarm Optimization (custom) | `PsoOptimizer.optimize(objective_fn, search_space, seed, params) → OptResult` |
| `bayesian.py` | Bayesian Optimization via optuna | `BayesianOptimizer.optimize(objective_fn, search_space, seed, params) → OptResult` |
| `sa.py` | Simulated Annealing (custom) | `SaOptimizer.optimize(objective_fn, search_space, seed, params) → OptResult` |
| `engine.py` | Orchestrator: wraps optimizer + objective function | `train(optimizer, objective_fn, search_space, seed, termination) → TrainResult` |
| `snapshot_store.py` | `OptSnapshotStore`: lifecycle enforcement (OE-10) | `get_active`, `find_by_fingerprint`, `next_version`, `create_snapshot`, `retire_old_active`, `mark_failed`, `bulk_insert_results` |

## Optimizer Designs

### GA (deap) — `opt/ga.py`

```python
# deap toolbox setup per optimization run
# Individual = list of sampled hyperparameter values
# Fitness = maximize objective_metric on eval split
# Selection = tournament (size 3)
# Crossover = uniform (per-parameter)
# Mutation = gaussian per-parameter
# Elitism = best individual preserved across generations
```

**Parameters**: `population_size=20`, `generations=50`, `crossover_prob=0.7`, `mutation_prob=0.2`
**Convergence**: one entry per generation (best fitness)
**Termination**: `fixed` (generations) or `early_stopping` (patience on no improvement)

### PSO (custom) — `opt/pso.py`

```python
# ~50 lines custom implementation
# Particle = list of hyperparameter values + velocity
# Global best = best fitness seen across swarm
# Update: v = w*v + c1*r1*(pbest-x) + c2*r2*(gbest-x)
# Position clamped to search space bounds
```

**Parameters**: `swarm_size=20`, `max_iterations=50`, `w=0.7`, `c1=1.5`, `c2=1.5`
**Convergence**: one entry per iteration (global best fitness)
**Termination**: `fixed` (iterations) or `early_stopping`

### Bayesian (optuna) — `opt/bayesian.py`

```python
# optuna.create_study(direction=objective_direction)
# For each trial: suggest params from TPE sampler → evaluate → report
# Best trial = trial with best value
```

**Parameters**: `n_trials=50`, `sampler=TPE(seed=seed)`
**Convergence**: one entry per trial (best value so far)
**Termination**: `fixed` (trials) or `early_stopping` (optuna native pruners)

### SA (custom) — `opt/sa.py`

```python
# ~40 lines custom implementation
# Current state = sampled hyperparameters
# Neighbor = perturb current state
# Accept if better or with probability exp(-delta/T)
# Temperature *= cooling_rate
```

**Parameters**: `max_iterations=50`, `initial_temperature=1.0`, `cooling_rate=0.95`, `perturbation_scale=0.1`
**Convergence**: one entry per iteration (best fitness)
**Termination**: `fixed` (iterations) or `early_stopping`

## Integration with ML/DL Engines

### Objective Function Closure

The objective function is created at the composition root (OptService) and passed to the optimizer. It captures:
- Target engine (`ml` or `dl`)
- Training data (draws, features)
- Walk-forward split (cut)
- Objective metric + direction

```python
def _build_objective_fn(
    engine: str,          # "ml" or "dl"
    draws: list[DrawRow],
    features: list[FeatureRow],
    cut: int,
    objective_metric: str,
    objective_direction: str,
) -> Callable[[dict[str, object]], Decimal]:
    """Build an objective function for the optimizer."""
    def objective(params: dict[str, object]) -> Decimal:
        if engine == "ml":
            result = ml_engine.train(
                family=params["family"],
                draws=draws,
                features=features,
                cut=cut,
                **{k: v for k, v in params.items() if k != "family"},
            )
        else:
            result = dl_engine.train(
                family=params["family"],
                train_batch=...,
                eval_batch=...,
                **{k: v for k, v in params.items() if k != "family"},
            )
        fitness = result.metrics[objective_metric]
        return fitness if objective_direction == "maximize" else -fitness
    return objective
```

### Walk-Forward in Objective

The objective function enforces walk-forward split internally:
1. Build windows from draws + features
2. Split at cut (train ≤ cut, eval > cut)
3. Build tensors from train/eval windows
4. Train model on train tensors
5. Evaluate on eval tensors
6. Return quantized metric as fitness

The optimizer never sees eval data — it only receives the fitness `Decimal`.

## Persistence Design

### Tables (migration `0011_opt_tables`)

```sql
CREATE TABLE opt_snapshots (
    id INTEGER PRIMARY KEY,
    lottery_id INTEGER NOT NULL REFERENCES lottery(id) RESTRICT,
    optimizer TEXT NOT NULL,                    -- 'ga', 'pso', 'bayesian', 'sa'
    model_set TEXT NOT NULL,                    -- 'core-5' or 'core-3'
    objective_metric TEXT NOT NULL DEFAULT 'f1',
    objective_direction TEXT NOT NULL DEFAULT 'maximize',
    algorithm_params JSON NOT NULL,             -- optimizer-specific params
    search_space JSON NOT NULL,                 -- parameter ranges
    termination TEXT NOT NULL DEFAULT 'fixed',  -- 'fixed' or 'early_stopping'
    termination_params JSON,                    -- {max_generations, patience, etc.}
    fingerprint TEXT NOT NULL,
    version TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    is_locked BOOLEAN NOT NULL DEFAULT 0,
    draw_count INTEGER NOT NULL,
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL,
    parent_id INTEGER REFERENCES opt_snapshots(id),
    UNIQUE(lottery_id, optimizer, fingerprint)
);

CREATE TABLE opt_results (
    id INTEGER PRIMARY KEY,
    snapshot_id INTEGER NOT NULL REFERENCES opt_snapshots(id) RESTRICT,
    target_model TEXT NOT NULL,                 -- 'mlp', 'lstm', 'random_forest', etc.
    best_params JSON NOT NULL,                  -- best found hyperparameters
    best_fitness REAL NOT NULL,                 -- quantized to Decimal(20,8) in app
    convergence_history JSON,                   -- [{eval_num, fitness, timestamp}, ...]
    metrics JSON NOT NULL,                      -- full metrics dict
    fingerprint TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL
);

CREATE INDEX idx_opt_snapshots_lottery ON opt_snapshots(lottery_id, status);
CREATE INDEX idx_opt_results_snapshot ON opt_results(snapshot_id);
```

### Snapshot Lifecycle

- `active` — current best optimization result for this lottery/optimizer
- `retired` — superseded by newer run
- `failed` — optimization failed (timeout, convergence failure, etc.)

Atomic replace: new run creates new snapshot + retires old in ONE transaction. Failure = rollback + terminal `failed` header only, zero result rows.

## Dependency Isolation

### deap Exception (GA)
```
# Fase 9 — Optimization Engine. ALLOWLIST EXCEPTION to the F6 stdlib-only gate
# (proposal D2, OE-09): deap is the ONLY permitted runtime dep for opt/ga.py;
# signed exception registered 2026-08-10, limited to opt/Fase-9. Exact-pinned
# for reproducibility. The dependency gate test asserts deap is present in F9
# tree and absent from F7/F8 trees.
"deap==1.4.1",
```

### optuna Exception (Bayesian)
```
# Fase 9 — Optimization Engine. ALLOWLIST EXCEPTION to the F6 stdlib-only gate
# (proposal D2, OE-09): optuna is the ONLY permitted runtime dep for opt/bayesian.py;
# signed exception registered 2026-08-10, limited to opt/Fase-9. Exact-pinned
# for reproducibility. The dependency gate test asserts optuna is present in F9
# tree and absent from F7/F8 trees.
"optuna==4.0.0",
```

### Ban-Gate Tests
- `test_opt_pr1.py`: asserts `deap` and `optuna` present in installable deps
- `test_ml_pr1.py`: asserts `deap` and `optuna` ABSENT from ML tree
- `test_dl_pr1.py`: asserts `deap` and `optuna` ABSENT from DL tree

## File Changes

| File | Action | Description |
|---|---|---|
| `backend/pyproject.toml` | Modify | Exact-pin `deap==1.4.1` + `optuna==4.0.0` + signed exception comments (D2) |
| `backend/tests/test_ml_pr1.py` (ban-gate) | Modify | Extend scan to `app/opt/`; deap/optuna absent from ML tree |
| `backend/tests/test_dl_pr1.py` (ban-gate) | Modify | deap/optuna absent from DL tree |
| `backend/src/backend/app/models/opt_snapshot.py`, `opt_result.py` | Create | Header + result entity |
| `backend/src/backend/app/models/__init__.py` | Modify | Register the 2 entities |
| `backend/alembic/versions/0011_opt_tables.py` | Create | `down_revision="0010_dl_tables"`; creates 2 tables + indexes |
| `backend/src/backend/app/opt/{__init__,registry,fingerprint,determinism,version,providers,search_space,convergence,ga,pso,bayesian,sa,engine,snapshot_store}.py` | Create | Pure engine package |
| `backend/src/backend/app/services/opt_service.py` | Create | Composition root, atomic lifecycle |
| `backend/src/backend/app/api/v1/opt.py` + `router.py` | Create/Modify | 4 routes + adapters |
| `backend/src/backend/app/schemas/opt.py` | Create | TrainRequest/ModelsList/MetricsRead/ParamsRead |
| `backend/src/backend/app/cli.py` | Modify | `lip opt train|models|metrics|params` |
| `backend/tests/opt/*`, `tests/test_opt_pr1.py` | Create | Unit/integration/e2e suites + PR1 dependency-gate |
| `specs/opt-engine`, README, PROJECT_STATUS, API_SPEC §10 | New/Mod | Docs update |

## Testing Strategy

| Layer | What | Approach |
|---|---|---|
| Unit | Search space validation/sampling; convergence tracker; fingerprint digest; determinism; registry dispatch; optimizer protocol compliance; floor (<100 ⇒ INSUFFICIENT_DATA) | `tests/opt/test_search_space.py`, `test_convergence.py`, `test_fingerprint.py`, `test_determinism.py`, `test_registry.py`, `test_floor.py` |
| Integration | Store lifecycle (atomic replace, failure ⇒ only failed, fingerprint idempotent); migration 0011 up/down non-destructive (dl_* intact); API 4 routes (404/422 maps, no predict route); CLI parity; ban-gate (opt/ no ml/dl imports, deap/optuna scoped) | `tests/opt/test_snapshot_store.py`, `test_migration.py`, `test_api.py`, `test_cli.py`, `tests/test_opt_pr1.py` |
| E2E | GF1: two seeded runs on identical synthetic 130-draw fixture ⇒ identical fingerprint + convergence history + best params; anti-leakage e2e; all 4 optimizers produce convergence | `tests/opt/test_opt_determinism_e2e.py` |

## Threat Matrix

| Threat | Risk | Mitigation |
|---|---|---|
| Optimizer overfits to train set | High | Walk-forward enforced in objective closure; optimizer only sees eval fitness |
| Stochastic non-reproducibility | High | Seed-based; termination in fingerprint; GF1 same-env gate |
| New dep exception scope creep | Med | Signed comments, F9-bound ban-gate tests |
| deap/optuna version drift | Med | Exact-pinned; lockfile enforced |
| Convergence noise | Med | Decimal-quantized metrics; multiple seeds for validation |
| Early stopping alters fixed result | Med | Same evaluation order; unit test asserts identical output when disabled |
| Optuna sklearn conflict | Low | optuna uses bundled sklearn; no conflict with scikit-learn==1.6.1 |
