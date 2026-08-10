# Spec — Optimization Engine (`opt-engine`)

**Change**: `fase-9-optimization-engine` · **Store**: `openspec` · **Date**: 2026-08-10
**Artifact**: spec (this change) — new capability `opt-engine`, parallel to `ml-engine` (F7) and `dl-engine` (F8), all frozen and untouched.

## Purpose

A deterministic optimization engine that finds optimal hyperparameters for ML/DL lottery prediction models (D1/D2/D5). Four algorithms — Genetic Algorithm (GA), Particle Swarm Optimization (PSO), Bayesian Optimization, Simulated Annealing (SA) — search configurable parameter spaces, evaluating fitness via walk-forward validation on existing ML/DL training pipelines (D3/D4). Single-objective per run with configurable metric (f1, roc_auc, accuracy, precision, recall) and direction (maximize, minimize). Results persist as immutable `opt_*` snapshots (dedicated schema, canonical SHA-256 fingerprint over optimizer+params+objective+data_hash+seed+termination+`OPTIMIZER_GENERATOR_VERSION`, active|retired|failed lifecycle, atomic single-transaction writes, manual-only). Determinism is seed-based: same seed + same data + same params = identical convergence history and best result. The engine reads only its own Provider Protocols and ML/DL engines (direct calls); it never touches F1–F8 tables or F10–F13 concerns.

Engine requirements `OE-01..15`; per-algorithm contracts `OA-01..04`.

## Requirements Overview

| ID | Requirement | Priority | Mirrors |
|----|-------------|----------|---------|
| OE-01 | Independent `opt_*` schema | P0 | MLE-01/DLE-01 |
| OE-02 | Strict read-only vs other engines | P0 | MLE-02/DLE-02 |
| OE-03 | Configurable objective: metric + direction | P0 | new |
| OE-04 | Search space definition (JSON-serializable) | P0 | new |
| OE-05 | Walk-forward fitness evaluation (anti-leakage) | P0 | MLE-03/DLE-05 |
| OE-06 | Determinism: seed-based, termination in fingerprint | P0 | MLE-04/DLE-07 |
| OE-07 | Fingerprint & Decimal-quantized checksum | P0 | MLE-05/DLE-08 |
| OE-08 | Data floor: ≥100 real draws; else INSUFFICIENT_DATA | P0 | DLE-10 |
| OE-09 | Registry & scope `core-4` | P0 | MLE-07/DLE-11 |
| OE-10 | Snapshot lifecycle & atomicity, fingerprint idempotency | P0 | MLE-08/DLE-12 |
| OE-11 | Provider Protocols only | P0 | MLE-06/DLE-13 |
| OE-12 | Manual-only surface; no predict/rank | P0 | MLE-09/DLE-14 |
| OE-13 | Convergence tracking (evaluation history) | P0 | new |
| OE-14 | Migration `0011` additive; non-destructive rollback | P0 | MLE-10/DLE-16 |
| OE-15 | Multi-lottery | P1 | MLE-11 |

Per-algorithm requirements:
| ID | Requirement | Priority |
|----|-------------|----------|
| OA-01 | Genetic Algorithm (deap) | P0 |
| OA-02 | Particle Swarm Optimization (custom) | P0 |
| OA-03 | Bayesian Optimization (optuna) | P0 |
| OA-04 | Simulated Annealing (custom) | P0 |

## Requirements

### OE-01: Independent `opt_*` Schema

The engine SHALL persist to a dedicated `opt_snapshots` (header) + `opt_results` (best parameters + convergence) schema, mirroring `stat_*`/`ml_*`/`dl_*`. It MUST NOT reuse `datasets`, `ml_*`, `dl_*`, or any Core/`stat_*`/`feature_*`/`prob_*`/`graph_*` table. Metric values SHALL be `Numeric(20,8)` Decimal — no float columns. `params_json` SHALL hold optimizer-specific parameters and best-found hyperparameters.

**Acceptance**
- [ ] An optimization commit writes rows in `opt_*` only; no other table changes.
- [ ] No float columns exist in `opt_*` tables; all metrics are Decimal(20,8).

#### Scenario: writes confined to opt_*
- GIVEN a completed optimization run over existing draws
- WHEN it commits
- THEN only `opt_*` rows are written; no Core, `ml_*`, `dl_*`, `stat_*`, `feature_*`, `prob_*`, or `graph_*` row changes.

### OE-02: Strict Read-Only vs Other Engines

The engine MUST NOT modify `lottery`, `draw`, `draw_numbers`, `super_number`, `dataset*`, `ml_*`, `dl_*`, or any prior-engine table. Writes target `opt_*` only; reads are passive and never trigger training or optimization.

**Acceptance**
- [ ] All non-`opt_*` rows byte-identical before/after a run under concurrent reads.

#### Scenario: all non-opt rows unchanged
- GIVEN an optimization run and concurrent reads
- WHEN both execute
- THEN all Core and prior-engine rows are byte-identical before and after.

### OE-03: Configurable Objective — Metric + Direction

The optimization objective SHALL be configurable per run with two fields:
- `objective_metric`: one of `f1`, `roc_auc`, `accuracy`, `precision`, `recall`
- `objective_direction`: one of `maximize`, `minimize`

Default: `objective_metric=f1`, `objective_direction=maximize`. The objective SHALL be part of the fingerprint (different objectives produce different fingerprints). The optimizer SHALL evaluate the specified metric on the evaluation split and return it as `Decimal(20,8)` quantized fitness.

**Acceptance**
- [ ] Two runs with different `objective_metric` values produce different fingerprints.
- [ ] Two runs with different `objective_direction` values produce different fingerprints.
- [ ] Fitness is Decimal(20,8) quantized; no raw float in persistence.

#### Scenario: default objective
- GIVEN an optimization run with no explicit objective
- WHEN it executes
- THEN `objective_metric=f1` and `objective_direction=maximize` are used.

#### Scenario: configurable objective
- GIVEN an optimization run with `objective_metric=roc_auc, objective_direction=maximize`
- WHEN it executes
- THEN the fitness is quantized roc_auc on the evaluation split.

#### Scenario: objective affects fingerprint
- GIVEN two identical optimization runs with different `objective_metric`
- WHEN both complete
- THEN their fingerprints differ.

### OE-04: Search Space Definition

Each optimizer SHALL accept a search space as JSON-serializable parameter ranges. The search space definition MUST be part of the fingerprint. Search space types:
- `continuous`: `{type: "continuous", low: float, high: float}`
- `discrete`: `{type: "discrete", choices: [value1, value2, ...]}`
- `integer`: `{type: "integer", low: int, high: int}`

Example for MLP hyperparameters:
```json
{
  "hidden_layers": {"type": "discrete", "choices": [[64, 32], [128, 64], [64, 64, 32]]},
  "lr": {"type": "continuous", "low": 1e-5, "high": 1e-1},
  "batch_size": {"type": "discrete", "choices": [16, 32, 64]},
  "dropout": {"type": "continuous", "low": 0.0, "high": 0.5}
}
```

**Acceptance**
- [ ] Search space is JSON-serializable and round-trips faithfully.
- [ ] Search space changes produce different fingerprints.
- [ ] Invalid search space types raise clear validation errors.

#### Scenario: search space in fingerprint
- GIVEN two identical runs with different search spaces
- WHEN both complete
- THEN their fingerprints differ.

#### Scenario: invalid search space rejected
- GIVEN a search space with unknown type
- WHEN optimization starts
- THEN a clear validation error is raised before any training.

### OE-05: Walk-Forward Fitness Evaluation (Anti-Leakage)

Fitness evaluation SHALL use walk-forward temporal split: train windows end `≤ cut`, eval windows start `> cut`. The optimizer MUST NOT see evaluation data during search. Straddle/shuffled windows SHALL raise `LeakageError`. The splitter reuses the ML/DL engine's walk-forward contract (MLE-03/DLE-05).

**Acceptance**
- [ ] Optimizer never accesses eval data during search.
- [ ] Straddle/shuffle raises LeakageError before any training.

#### Scenario: walk-forward enforced
- GIVEN an optimization run with walk-forward split
- WHEN the optimizer searches
- THEN fitness is computed only on eval data the optimizer has not seen.

#### Scenario: straddle rejected
- GIVEN a window that straddles the cut
- WHEN the split is validated
- THEN LeakageError is raised and no training occurs.

### OE-06: Determinism — Seed-Based, Termination in Fingerprint

Determinism SHALL be seed-based: same seed + same data + same params = identical convergence history and best result. For DL-dependent runs, `configure_deterministic_torch(seed)` SHALL be called before training. Termination parameters MUST be part of the fingerprint:
- `termination`: `fixed` | `early_stopping`
- `max_generations`: int (for GA, SA)
- `max_evaluations`: int (for Bayesian, PSO)
- `patience`: int (early_stopping only)
- `min_delta`: float (early_stopping only)

When `termination=fixed`, early stopping MUST NOT alter the result. The fingerprint payload includes `termination_params` as a nested object.

**Acceptance**
- [ ] Same seed + same data + same params = byte-identical convergence history.
- [ ] Early stopping disabled does not change result vs. a run without early stopping config.
- [ ] Termination params in fingerprint; different termination = different fingerprint.

#### Scenario: deterministic convergence
- GIVEN two identical optimization runs with same seed
- WHEN both complete
- THEN convergence history and best result are byte-identical.

#### Scenario: early stopping off does not alter result
- GIVEN a fixed-termination run
- AND the same run with early_stopping disabled
- WHEN both complete
- THEN best fitness and convergence history are identical.

#### Scenario: termination in fingerprint
- GIVEN two identical runs with different `max_generations`
- WHEN both complete
- THEN their fingerprints differ.

### OE-07: Fingerprint & Decimal-Quantized Checksum

The canonical fingerprint SHALL be SHA-256 over `sort_keys=True` JSON of: `{optimizer, algorithm_params, objective_metric, objective_direction, search_space, data_hash, seed, OPTIMIZER_GENERATOR_VERSION, termination_params}`. Metrics checksum SHALL digest only Decimal-quantized values. The fingerprint SHALL change when any input changes.

**Acceptance**
- [ ] Equal inputs ⇒ identical hex fingerprint.
- [ ] Key order irrelevant (sort_keys=True).
- [ ] Checksum over Decimal-only values.

#### Scenario: fingerprint stability
- GIVEN the same inputs
- WHEN fingerprint is computed twice
- THEN the hex digest is identical.

#### Scenario: key order irrelevant
- GIVEN inputs with different key ordering
- WHEN fingerprint is computed
- THEN the hex digest is identical.

### OE-08: Data Floor — ≥100 Real Draws

Optimization SHALL require ≥100 real draws. Below that, a clean `INSUFFICIENT_DATA` (422) response with no snapshot or results written. Synthetic fixtures are for structural/E2E testing only.

**Acceptance**
- [ ] <100 draws ⇒ 422 INSUFFICIENT_DATA, zero opt_* rows.

#### Scenario: insufficient data
- GIVEN a lottery with 50 real draws
- WHEN optimization is requested
- THEN response is 422 INSUFFICIENT_DATA and no opt_* rows are written.

### OE-09: Registry & Scope `core-4`

The registry SHALL expose exactly 4 executed optimizers under `optimizer_set="core-4"`: `ga`, `pso`, `bayesian`, `sa`. No future-X families are declared. Unknown optimizer SHALL fail-fast listing known IDs.

**Acceptance**
- [ ] Registry returns exactly 4 optimizers.
- [ ] Unknown optimizer raises clear error with known IDs.

#### Scenario: core-4 registry
- GIVEN the optimizer registry
- WHEN it is built
- THEN it contains exactly {ga, pso, bayesian, sa}.

#### Scenario: unknown optimizer rejected
- GIVEN a request for optimizer "gradient_descent"
- WHEN the registry is queried
- THEN a clear error lists the 4 known optimizers.

### OE-10: Snapshot Lifecycle & Atomicity, Fingerprint Idempotency

Optimization SHALL follow the same lifecycle pattern: `active|retired|failed`. A new optimization run SHALL retire the old `active` snapshot atomically. Failure SHALL result in terminal `failed` status only (no partial results). `find_by_fingerprint` SHALL be idempotent — same fingerprint returns existing snapshot.

**Acceptance**
- [ ] New run atomically replaces old active.
- [ ] Failure creates only `failed` header, zero result rows.
- [ ] Same fingerprint returns existing snapshot without duplicate.

#### Scenario: atomic replace
- GIVEN an existing active optimization snapshot
- WHEN a new optimization with different params runs
- THEN the old snapshot is retired and the new one is active in one transaction.

#### Scenario: idempotent fingerprint
- GIVEN a completed optimization with fingerprint X
- WHEN the same optimization is requested again
- THEN the existing snapshot is returned without a new run.

### OE-11: Provider Protocols Only

The engine SHALL define its own read-only Provider Protocols (`DrawHistoryProvider`, `FeatureSnapshotProvider`) — never import concrete implementations from F1–F8. Adapters live at the composition root.

**Acceptance**
- [ ] `opt/` directory has zero imports from `ml/`, `dl/`, `services/`, `repositories/`.

#### Scenario: no concrete imports
- GIVEN the opt/ package
- WHEN module imports are scanned
- THEN zero imports from ml/, dl/, services/, or repositories/ exist.

### OE-12: Manual-Only Surface; No Predict/Rank

Optimization SHALL be manual-only via CLI and API. No automatic triggers, no scheduling. No `/opt/predict` endpoint — optimization finds parameters, not predictions. No ranking or recommendation surface.

**Acceptance**
- [ ] No `/opt/predict` route exists.
- [ ] No auto-trigger or scheduler integration.

#### Scenario: manual only
- GIVEN a configured lottery
- WHEN `POST /opt/train` is called
- THEN optimization runs and returns the envelope; no auto-trigger on import or schedule.

#### Scenario: no predict route
- GIVEN the API router after F9
- WHEN route discovery runs
- THEN `/opt/predict` does not exist.

### OE-13: Convergence Tracking (Evaluation History)

Each optimization run SHALL record convergence history: a list of `(evaluation_number, best_fitness, timestamp)` tuples. The history SHALL be stored in `opt_results.convergence_history` as JSON. The history enables plotting convergence curves and detecting stagnation.

**Acceptance**
- [ ] Convergence history is a list of (eval_num, fitness, timestamp) tuples.
- [ ] History is JSON-serializable and round-trips faithfully.

#### Scenario: convergence recorded
- GIVEN an optimization run with 50 evaluations
- WHEN the run completes
- THEN convergence_history contains exactly 50 entries with monotonically increasing evaluation numbers.

### OE-14: Migration `0011` Additive; Non-Destructive Rollback

Migration `0011_opt_tables` (down_revision `0010_dl_tables`) SHALL add `opt_snapshots` + `opt_results` + indexes. Downgrade SHALL drop only `opt_*`. Core + `ml_*` + `dl_*` + `stat_*` + `feature_*` + `prob_*` + `graph_*` MUST remain intact.

**Acceptance**
- [ ] Upgrade creates opt_* tables and indexes.
- [ ] Downgrade drops only opt_*.
- [ ] All prior tables byte-identical after up/down cycle.

#### Scenario: migration up/down
- GIVEN a database with all F1–F8 tables
- WHEN migration 0011 upgrades and then downgrades
- THEN all prior tables are byte-identical.

### OE-15: Multi-Lottery (P1)

All endpoints SHALL accept `lottery_id` or lottery code. Optimization is per-lottery; cross-lottery optimization is out of scope.

**Acceptance**
- [ ] Each endpoint accepts lottery_id parameter.

#### Scenario: per-lottery optimization
- GIVEN two lotteries
- WHEN optimization runs for each
- THEN separate opt_* snapshots are created per lottery.

## Per-Algorithm Requirements

### OA-01: Genetic Algorithm (deap)

GA SHALL use `deap` library with configurable: `population_size` (default 20), `generations` (default 50), `crossover_probability` (default 0.7), `mutation_probability` (default 0.2). Selection: tournament (size 3). Elitism: best individual preserved. The GA SHALL evolve a population of hyperparameter vectors, evaluating fitness via walk-forward on ML/DL training.

**Acceptance**
- [ ] GA produces convergence history with `generations` entries.
- [ ] Best individual is preserved across generations (elitism).

### OA-02: Particle Swarm Optimization (custom)

PSO SHALL use custom implementation (~50 lines) with configurable: `swarm_size` (default 20), `max_iterations` (default 50), `inertia_weight` (default 0.7), `cognitive_coefficient` (default 1.5), `social_coefficient` (default 1.5). The PSO SHALL optimize a swarm of particles in the hyperparameter space.

**Acceptance**
- [ ] PSO produces convergence history with `max_iterations` entries.
- [ ] Global best is tracked across iterations.

### OA-03: Bayesian Optimization (optuna)

Bayesian SHALL use `optuna` library with configurable: `n_trials` (default 50), `sampler` (default TPE). The sampler SHALL build a probabilistic model of the objective surface and suggest promising hyperparameters.

**Acceptance**
- [ ] Bayesian produces convergence history with `n_trials` entries.
- [ ] Suggested params improve over trials (probabilistic model learning).

### OA-04: Simulated Annealing (custom)

SA SHALL use custom implementation (~40 lines) with configurable: `max_iterations` (default 50), `initial_temperature` (default 1.0), `cooling_rate` (default 0.95), `perturbation_scale` (default 0.1). The SA SHALL start from a random point and cool down, accepting worse solutions with decreasing probability.

**Acceptance**
- [ ] SA produces convergence history with `max_iterations` entries.
- [ ] Temperature decreases monotonically.

## Non-Goals (Explicit)

- Feature selection (F10/F13 territory)
- Number selection or combination generation (F13 territory)
- Full historical backtesting (F10 territory)
- Experiment tracking and comparison (F11 territory)
- Multi-objective Pareto optimization
- GPU/CUDA acceleration
- Weights download or model export
- Automatic triggering or scheduling
