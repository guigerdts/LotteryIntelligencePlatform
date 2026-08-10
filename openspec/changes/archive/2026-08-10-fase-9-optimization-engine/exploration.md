# Exploration — Fase 9: Optimization Engine

**Date**: 2026-08-10 · **Change**: `fase-9-optimization-engine` · **Store**: openspec

## 1. Reusable Assets (F1–F8)

### Directly Reusable
| Asset | Source | Reuse in F9 |
|-------|--------|-------------|
| Registry pattern | `ml/registry.py`, `dl/registry.py` | Optimizer registry (core-4: ga, pso, bayesian, sa) |
| Fingerprint contract | `ml/fingerprint.py`, `dl/fingerprint.py` | Optimizer fingerprint over params+data+seed |
| Determinism utilities | `ml/determinism.py`, `dl/determinism.py` | `configure_deterministic_torch`, `quantize_metric`, `compute_metrics_checksum` |
| Walk-forward splitter | `ml/splitter.py`, `dl/splitter.py` | Temporal validation for optimizer evaluation |
| Provider protocols | `ml/providers.py`, `dl/providers.py` | DrawRow, FeatureRow, DrawHistoryProvider, FeatureSnapshotProvider |
| Snapshot lifecycle | `ml/snapshot_store.py`, `dl/snapshot_store.py` | `opt_*` snapshots with active\|retired\|failed |
| Version pattern | `ml/version.py`, `dl/version.py` | `OPTIMIZER_GENERATOR_VERSION` |
| Decimal metrics | Both engines | Quantized fitness scores for reproducibility |
| API/CLI patterns | `api/v1/ml.py`, `api/v1/dl.py` | `POST /opt/train`, `GET /opt/models`, `GET /opt/metrics` |
| Migration pattern | `0009_ml_tables`, `0010_dl_tables` | `0011_opt_tables` |

### Partially Reusable
| Asset | Source | Adaptation needed |
|-------|--------|-------------------|
| ML engine train loop | `ml/engine.py` | Wrap as objective function for optimizer |
| DL engine train loop | `dl/engine.py` | Wrap as objective function for optimizer |
| Weights format | `dl/weights.py` | Extend for optimizer state (not just model weights) |
| Feature matrix builder | `dl/sequence_builder.py` | Reuse for optimizer input representation |

### Not Reusable
| Asset | Reason |
|-------|--------|
| Specific model architectures | Optimizers are model-agnostic |
| ML/DL-specific persistence | Optimizers have different state (convergence history, best params) |

## 2. Dependency Analysis

### Current Deps (pyproject.toml)
- Core: fastapi, sqlalchemy, alembic, pydantic, httpx, uvicorn
- ML: numpy==2.2.6, scikit-learn==1.6.1
- DL: torch==2.13.0+cpu

### New Deps Needed Per Algorithm

| Algorithm | Candidate Deps | Custom? | Notes |
|-----------|---------------|---------|-------|
| Genetic Algorithm | `deap` (1.4.1) | Possible | Most mature GA library for Python. Alternatives: `pymoo` (multi-objective), custom |
| Particle Swarm | `pyswarm` (0.6) or custom | Custom preferred | PSO is simple enough (~50 lines). `pyswarm` is unmaintained |
| Bayesian Optimization | `scikit-optimize` (0.10.2) or `optuna` (4.0+) | `optuna` preferred | `scikit-optimize` depends on outdated `sklearn`. `optuna` is actively maintained, supports MLflow |
| Simulated Annealing | custom | Custom | SA is trivial (~40 lines). No dep needed |

**Recommendation**: Minimize new deps. GA via `deap`, Bayesian via `optuna`, PSO/SA custom. Total new deps: 2.

**Risk**: Each new dep is a signed exception to the F6 stdlib-only gate. Each needs:
- Ban-gate test assertion
- Exact pin for reproducibility
- Exception comment in pyproject.toml

## 3. Objective Function Landscape

### What Are We Optimizing?

The Optimization Engine finds optimal parameters for lottery prediction models. Three optimization targets:

#### A. Hyperparameter Optimization (Primary)
- **Target**: ML/DL model hyperparameters
- **Space**: `hidden_layers`, `lr`, `epochs`, `batch_size`, `n_estimators`, `dropout`, etc.
- **Objective**: Maximize validation metrics (f1, roc_auc, accuracy)
- **Constraints**: Walk-forward temporal split, no future leakage

#### B. Feature Selection (Secondary)
- **Target**: Subset of F4 features (10 canonical)
- **Space**: 2^10 = 1024 possible subsets
- **Objective**: Maximize metrics with minimum features (parsimony)
- **Constraints**: Feature order fixed, selection must be reproducible

#### C. Number Selection Strategy (Future)
- **Target**: Weights/thresholds for combining model outputs into number recommendations
- **Space**: Continuous (thresholds per number)
- **Objective**: Maximize historical hit rate
- **Constraints**: This overlaps with F10 Backtesting — needs clear boundary

### Available Fitness Factors
From ML/DL engines:
- `accuracy` — per-number classification accuracy
- `precision` — positive predictive value
- `recall` — sensitivity
- `f1` — harmonic mean of precision/recall
- `roc_auc` — area under ROC curve
- All quantized to `Decimal(20,8)` for reproducibility

## 4. Integration Points

### ML Engine Integration
```
Optimizer → calls → ml.engine.train(family, hyperparams) → returns TrainResult.metrics
         ↓
    evaluates fitness
         ↓
    updates population/parameters
```

### DL Engine Integration
```
Optimizer → calls → dl.engine.train(family, hyperparams) → returns TrainResult.metrics
         ↓
    evaluates fitness
         ↓
    updates population/parameters
```

### Feature Engineering Integration
```
Optimizer → reads → FeatureSnapshotProvider.active_snapshot_id()
         ↓
    selects feature subset
         ↓
    passes to engine.train(features=[...])
```

### Backtesting Boundary (F10)
- **F9**: Finds optimal parameters (optimization loop)
- **F10**: Evaluates found parameters historically (walk-forward backtest)
- **F11**: Tracks which optimization runs produced which results

## 5. Risk Register

### Leakage Risks
| Risk | Severity | Mitigation |
|------|----------|------------|
| Optimizer sees test data during search | HIGH | Walk-forward split enforced; optimizer only sees train metrics |
| Feature selection leaks via correlation with target | HIGH | Feature selection must use train-only data |
| Temporal leakage in convergence history | MED | Convergence logged per-evaluation with timestamps |

### Overfitting Risks
| Risk | Severity | Mitigation |
|------|----------|------------|
| Optimizer overfits to train set | HIGH | Validation metrics required; early stopping |
| Too many generations/iterations | MED | Configurable max_generations, max_evaluations |
| Multiple testing bias | MED | Corrected p-values or holdout set |

### Determinism Risks
| Risk | Severity | Mitigation |
|------|----------|------------|
| Stochastic optimizers non-reproducible | HIGH | Seed-based; `use_deterministic_algorithms(True)` |
| Float32 accumulation drift | MED | Decimal-quantized metrics; same-env verification |
| GPU/CUDA differences | LOW | CPU-only (same as DL) |

### Data Floor
| Risk | Severity | Mitigation |
|------|----------|------------|
| Insufficient data for optimization | HIGH | ≥100 draws (same as DL); cleaner error |
| Small eval set gives noisy fitness | MED | Minimum eval window size |

## 6. Persistence Design

### New Tables (migration `0011_opt_tables`)

```sql
-- Optimization run header
CREATE TABLE opt_snapshots (
    id INTEGER PRIMARY KEY,
    lottery_id INTEGER NOT NULL,
    optimizer TEXT NOT NULL,          -- 'ga', 'pso', 'bayesian', 'sa'
    model_set TEXT NOT NULL,          -- 'core-5' or 'core-3'
    algorithm_params JSON NOT NULL,   -- optimizer-specific params
    fingerprint TEXT NOT NULL,
    version TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',  -- active|retired|failed
    is_locked BOOLEAN NOT NULL DEFAULT 0,
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL,
    parent_id INTEGER REFERENCES opt_snapshots(id)
);

-- Best found parameters
CREATE TABLE opt_results (
    id INTEGER PRIMARY KEY,
    snapshot_id INTEGER NOT NULL REFERENCES opt_snapshots(id),
    target_model TEXT NOT NULL,       -- 'mlp', 'lstm', 'random_forest', etc.
    best_params JSON NOT NULL,
    best_fitness REAL NOT NULL,
    convergence_history JSON,         -- list of (generation, best_fitness)
    metrics JSON NOT NULL,            -- full metrics dict
    fingerprint TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL
);

-- Indexes
CREATE INDEX idx_opt_snapshots_lottery ON opt_snapshots(lottery_id, status);
CREATE INDEX idx_opt_results_snapshot ON opt_results(snapshot_id);
```

### Snapshot Lifecycle
- `active` — current best optimization result for this lottery/optimizer
- `retired` — superseded by newer run
- `failed` — optimization failed (timeout, convergence failure, etc.)

## 7. API/CLI Surface

### API Endpoints
| Method | Path | Description |
|--------|------|-------------|
| POST | `/opt/train` | Run optimization (params: lottery_id, optimizer, model_set, max_generations) |
| GET | `/opt/models` | List optimizer registry + active snapshot |
| GET | `/opt/metrics` | Get optimization metrics (best fitness, convergence) |
| GET | `/opt/params` | Get best found parameters for a model |

### CLI Commands
| Command | Description |
|---------|-------------|
| `lip opt train --lottery <code> --optimizer <ga\|pso\|bayesian\|sa>` | Run optimization |
| `lip opt models --lottery <code>` | List optimizer registry + active snapshot |
| `lip opt metrics --lottery <code>` | Show optimization metrics |
| `lip opt params --lottery <code> --model <name>` | Show best parameters |

### No Surface (Deferred)
- No `/opt/predict` (use ML/DL predict endpoints)
- No `/opt/compare` (F11 Experiment Engine)
- No weights download (optimizer state is parameters, not weights)

## 8. Boundary Analysis: F9 vs F10 vs F11

| Concern | F9 Optimization | F10 Backtesting | F11 Experiment |
|---------|----------------|-----------------|----------------|
| **Goal** | Find best parameters | Evaluate strategies historically | Track and compare runs |
| **Input** | Objective function + search space | Strategy + historical data | Experiment definitions |
| **Output** | Best parameters + convergence | Performance metrics + reports | Experiment results + comparisons |
| **Temporal** | Train/eval split during search | Walk-forward over full history | Cross-run comparison |
| **Persistence** | `opt_*` snapshots | `bt_*` snapshots | `exp_*` snapshots |
| **API** | `POST /opt/train` | `POST /bt/run` | `POST /exp/create` |
| **CLI** | `lip opt ...` | `lip bt ...` | `lip exp ...` |

### Key Boundary Decisions
1. **F9 finds parameters, F10 evaluates them** — F9 uses walk-forward during search; F10 does full historical backtest
2. **F11 tracks F9+F10 results** — Experiment engine links optimization runs to backtest results
3. **F9 does NOT generate number recommendations** — That's F13 (Intelligent Generator)

## 9. Decisions Required Before sdd-propose

### D1: Optimization Target
**Question**: Should F9 optimize hyperparameters only, or also feature selection?
- Option A: Hyperparameters only (simpler, clear scope)
- Option B: Hyperparameters + feature selection (more powerful, larger search space)
- Option C: Hyperparameters + feature selection + number selection strategy (overlaps F10/F13)

**Recommendation**: Option A for F9 core, Option B as optional extension. Option C deferred to F10/F13.

### D2: New Dependencies
**Question**: Which optimization libraries to use?
- Option A: `deap` (GA) + `optuna` (Bayesian) + custom (PSO/SA) — 2 new deps
- Option B: All custom — 0 new deps, more control, more code
- Option C: `pymoo` (multi-objective GA) + `optuna` — 2 deps, multi-objective support

**Recommendation**: Option A for minimal deps. Option B is viable for PSO/SA (simple algorithms).

### D3: Multi-Objective Support
**Question**: Should F9 support multi-objective optimization (e.g., maximize f1 AND minimize feature count)?
- Option A: Single-objective only (simpler, clear scope)
- Option B: Multi-objective with Pareto front (more powerful, `pymoo` needed)

**Recommendation**: Option A for F9 core. Multi-objective deferred to F11 (Experiment Engine can compare tradeoffs).

### D4: Convergence Criteria
**Question**: How does optimization terminate?
- Option A: Fixed generations/evaluations (simple, deterministic)
- Option B: Early stopping on convergence (adaptive, non-deterministic)
- Option C: Both (configurable)

**Recommendation**: Option C (configurable). Default: fixed generations for determinism.

### D5: Integration with Existing Engines
**Question**: Should F9 call ML/DL engines directly, or accept pre-trained models?
- Option A: Call engines directly (tighter integration, simpler API)
- Option B: Accept pre-trained models (looser coupling, more flexible)

**Recommendation**: Option A. F9 is the composition root that calls ML/DL engines.

### D6: Data Floor
**Question**: What minimum data is needed for optimization?
- Option A: Same as DL (≥100 draws) — consistency
- Option B: Higher floor (≥200 draws) — optimization needs more data
- Option C: Configurable floor

**Recommendation**: Option A for consistency. Optimization quality is user's responsibility.

## 10. Open Questions

1. **F10 overlap**: Does F9 need its own walk-forward, or reuse F10's? (Answer: F9 has its own simplified walk-forward during search; F10 does full backtest)
2. **GPU support**: Should optimizers support GPU for DL model training? (Answer: No, CPU-only same as DL)
3. **Parallelization**: Should optimization runs be parallelized? (Answer: Not in F9 core; deferred)
4. **Export**: Should best parameters be exportable? (Answer: Yes, via API/CLI; no file export in F9)
5. **MLflow integration**: Should optimization runs be tracked in MLflow? (Answer: Not in F9 core; F11 Experiment Engine)

## Summary

Fase 9 is a **parameter search engine** that wraps ML/DL training in optimization loops. It reuses the entire F7/F8 infrastructure (registry, fingerprint, determinism, splitter, providers, snapshots) and adds:
- 4 optimizer algorithms (GA, PSO, Bayesian, SA)
- Optimizer registry pattern (mirroring ML/DL)
- `opt_*` persistence schema
- API/CLI surface (train, models, metrics, params)
- Convergence tracking

**Estimated scope**: ~1,500–2,000 LOC across 5–6 PRs (stacked-to-main).
**New dependencies**: 2 (`deap`, `optuna`) — signed exceptions needed.
**Blocked on**: Decisions D1–D6 before sdd-propose.
