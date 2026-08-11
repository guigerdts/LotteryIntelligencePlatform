# Exploration: Fase 12 — Meta Learning

**Change**: `fase-12-meta-learning` · **Date**: 2026-08-11 · **Phase**: sdd-explore

## 1. Hallazgos / Findings

- No existing `meta_learning` module, table, service, or API in the codebase. This is a greenfield capability.
- The project follows a consistent snapshot pattern across engines (ML, DL, Optimization, Backtesting): each has a header table (`*_snapshots`) with status lifecycle (`active|retired|failed`), versioning, SHA-256 fingerprints, and a payload table (`*_metrics` or `*_results`). F12 can reuse this pattern.
- F11 Experiment Engine provides the orchestration layer: it registers experiments, associates engine runs, computes cross-run comparisons, and exports results. F12 consumes these persisted outputs.
- Contextual data available for dynamic selection includes: `lottery_id`, draw characteristics (`jackpot`, `winners`, `draw_date`), snapshot metadata (`draws_from`, `draws_to`, `cut`, `window`), `engine_type`, metric values (Decimal), timestamps, and experiment configuration (`config_json`).
- The project uses NumPy (2.2.6) and scikit-learn (1.6.1) but no pandas. Scoring models must be implemented with NumPy or pure Python.
- Next migration number is `0014`. F12 will need additive tables.

## 2. Estado actual / Current State

### Core Domain
- `lottery` table: `id`, `code`, `name`, `country`, `min_number`, `max_number`, `numbers_to_select`, `super_number_min`, `super_number_max`.
- `draw` table: `id`, `lottery_id`, `draw_number`, `draw_date`, `jackpot`, `winners`, `is_deleted`.

### Engine Snapshots (consumable by F12)
- **ML**: `ml_snapshots` (id, lottery_id, model_set, version, ml_generator_version, checksum, input_fingerprint, cut, status, is_locked, draw_count, draws_from, draws_to) + `ml_metrics` (snapshot_id, model_id, model_version, number, metric_name, value, params_json).
- **DL**: `dl_snapshots` (id, lottery_id, model_set, version, dl_generator_version, checksum, input_fingerprint, cut, window, status, is_locked, draw_count, draws_from, draws_to) + `dl_metrics` (snapshot_id, model_id, model_version, number, metric_name, value, params_json).
- **Optimization**: `opt_snapshots` (id, lottery_id, optimizer, model_set, objective_metric, objective_direction, algorithm_params, search_space, termination, termination_params, fingerprint, version, status, is_locked, draw_count) + `opt_results` (snapshot_id, target_model, best_params, best_fitness, convergence_history, metrics, fingerprint).
- **Backtesting**: `bt_snapshots` (id, lottery_id, strategy_id, fingerprint, version, status, config_json) + `bt_results` (snapshot_id, aggregate_metrics_json, window_history_json).

### Experiment Engine (F11)
- `exp_experiments`: (id, lottery_id, name, description, status, fingerprint, version, config_json, created_at).
- `exp_runs`: (id, experiment_id, run_label, engine_type, engine_snapshot_id, engine_fingerprint, notes, created_at).
- `exp_comparisons`: (id, experiment_id, comparison_json, created_at).
- Service layer: `ExpService` provides CRUD, run association, comparison, and export. Comparison reads metrics from engine tables and persists a JSON matrix.

### Existing Patterns
- **Versioning**: monotonic version per (lottery, name/engine).
- **Fingerprints**: SHA-256 for idempotency and invalidation.
- **Lifecycle**: `active|retired|failed` with atomic transitions.
- **Isolation**: engines are read-only to each other; writes confined to own tables.

## 3. Datos reutilizables / Reusable Data

F12 can consume the following read-only:

| Source Table | Key Columns for F12 | Purpose |
|--------------|---------------------|---------|
| `ml_snapshots` | `lottery_id`, `model_set`, `version`, `status`, `draws_from`, `draws_to`, `cut` | ML snapshot context |
| `ml_metrics` | `snapshot_id`, `model_id`, `metric_name`, `value`, `number` | ML performance metrics |
| `dl_snapshots` | `lottery_id`, `model_set`, `version`, `status`, `window`, `draws_from`, `draws_to` | DL snapshot context |
| `dl_metrics` | `snapshot_id`, `model_id`, `metric_name`, `value`, `number` | DL performance metrics |
| `opt_snapshots` | `lottery_id`, `optimizer`, `model_set`, `objective_metric`, `status`, `draw_count` | Optimization context |
| `opt_results` | `snapshot_id`, `target_model`, `best_fitness`, `best_params` | Optimization performance |
| `bt_snapshots` | `lottery_id`, `strategy_id`, `status`, `config_json` | Backtest context |
| `bt_results` | `snapshot_id`, `aggregate_metrics_json`, `window_history_json` | Backtest performance |
| `exp_experiments` | `lottery_id`, `name`, `status`, `config_json` | Experiment metadata |
| `exp_runs` | `experiment_id`, `engine_type`, `engine_snapshot_id` | Run-to-engine mapping |
| `exp_comparisons` | `experiment_id`, `comparison_json` | Precomputed comparison matrix |
| `draw` | `lottery_id`, `jackpot`, `winners`, `draw_date` | Contextual draw characteristics |

## 4. Dependencias / Dependencies

### F11 → F12 coupling
- F12 reads `exp_*` tables to obtain experiment context and precomputed comparisons.
- F12 may also read engine metrics directly (`ml_metrics`, `dl_metrics`, etc.) for fine-grained scoring.
- F12 does NOT write to `exp_*` tables; it produces its own output tables.

### F12 → F13 coupling
- F13 (Intelligent Generator) will need a selected model/strategy ranking from F12.
- F12 output could be a snapshot of selected models with scores, which F13 consumes to generate combinations.

## 5. Frontera F11/F12/F13 / Boundaries

| Phase | Responsibility | Input | Output |
|-------|----------------|-------|--------|
| F11 Experiment | Register, version, compare, export experiments | Engine snapshots | `exp_*` tables, comparison JSON |
| F12 Meta Learning | Evaluate historical performance, rank models, select dynamically | `exp_*` + engine metrics + contextual data | Ranking snapshots, selection history |
| F13 Generator | Generate combinations, filter, evaluate, score, select, show | Selected models from F12 | Number combinations |

F12 does NOT:
- Duplicate F11 comparison logic (it can use F11's comparison_json or recompute from raw metrics).
- Execute backtesting, ML training, DL training, or optimization.
- Generate number combinations (F13).
- Provide UI/dashboard (F14).

## 6. Requisitos potenciales / Potential Requirements (Draft)

1. **Ranking Engine**: Compute a weighted score for each model/strategy based on metrics (accuracy, precision, recall, F1, ROC AUC, hit rate, etc.) across experiments.
2. **Context-Aware Selection**: Select top-K models per context bucket (e.g., per lottery, per draw range, per engine type).
3. **Performance History**: Persist ranking snapshots with timestamps, context, and scores.
4. **Version Comparison**: Compare ranking across different versions of the same model.
5. **Deterministic Ranking**: Same inputs → same ranking (seed-based if stochastic).
6. **Idempotent Updates**: Recomputing ranking with same data returns existing snapshot.
7. **API Endpoints**: `POST /meta/rank`, `GET /meta/ranking`, `GET /meta/selection`, `POST /meta/select`.
8. **CLI Commands**: `lip meta rank`, `lip meta ranking`, `lip meta select`.
9. **Migration 0014**: Additive tables for ranking snapshots and selection history.

## 7. Preguntas abiertas / Open Questions

1. **Scoring Model**: Should ranking use a simple metric-weighted score (transparent, interpretable) or a learned meta-model (potentially more accurate but opaque)? The project currently has no pandas; scoring must use NumPy or pure Python.
2. **Context Buckets**: What defines a "context"? Options: (a) per lottery, (b) per lottery + draw range, (c) per lottery + engine type, (d) per lottery + metric thresholds. Need to decide granularity.
3. **Ranking Persistence**: Should ranking be an immutable snapshot (like other engines) or a mutable view that updates in place? The snapshot pattern suggests immutable.
4. **Selection Determinism**: Should selection be deterministic given (lottery_id, context)? If ranking uses stochastic methods (e.g., Monte Carlo sampling), determinism may require seeding.
5. **Cross-Engine Comparison**: How to compare models across different engine types (ML vs DL vs Optimization vs Backtesting)? They have different metric sets. Need a common scoring normalization.
6. **Freshness**: Should ranking consider model freshness (newer snapshots rank higher) or only performance?
7. **Overfitting Prevention**: How to avoid selecting models that overfit to historical data? Possibly use out-of-sample metrics only.

## 8. Decisiones que requieren autorización / Decisions Needing Authorization

1. **Scoring Algorithm**: Simple weighted sum vs learned meta-model (requires authorization due to complexity and interpretability tradeoff).
2. **Context Definition**: Which contextual dimensions to include (lottery, draw range, engine type, metric thresholds).
3. **Ranking Snapshot Immutability**: Whether to follow the immutable snapshot pattern or allow updates.
4. **Cross-Engine Normalization**: How to normalize metrics across different engine types for fair comparison.
5. **Selection Strategy**: Top-K static vs dynamic threshold vs learned policy.

## 9. Riesgos / Risks

- **Leakage**: Selection using future data (e.g., selecting models based on metrics from draws that haven't occurred yet). Must ensure ranking uses only historical data up to the selection point.
- **Overfitting**: Selecting models that perform well on training data but fail on unseen data. Need to use out-of-sample metrics (e.g., from walk-forward backtesting).
- **Retrospective Selection (Survivorship Bias)**: Only evaluating models that succeeded, ignoring those that failed early. Must consider all models, including those with `status='failed'`.
- **Determinism Across Runs**: If ranking involves stochastic elements, results may differ between runs. Need seed-based determinism.
- **Context Drift**: Context definitions may change over time, making historical rankings non-comparable. Need versioned context schemas.
- **Complexity Creep**: Scoring models could become overly complex, maintainability suffer. Start simple, iterate.
- **Dependency on F11**: If F11 comparison logic changes, F12 rankings may become inconsistent. Need to document assumptions.

## 10. Propuesta preliminar de alcance / Preliminary Scope Proposal (Draft)

**Phase 12 — Meta Learning** will implement a ranking and dynamic selection system that consumes persisted outputs from F7/F8/F9/F10/F11 to evaluate model performance and select the most promising models per context.

### Core Components
1. **Ranking Service**: Computes scores for each model/strategy based on configurable metric weights.
2. **Context Resolver**: Determines context bucket from lottery_id, draw characteristics, and snapshot metadata.
3. **Selection Service**: Selects top-K models per context based on ranking scores.
4. **Persistence Layer**: Stores ranking snapshots and selection history in immutable tables.
5. **API/CLI Surface**: Endpoints and commands for ranking, selection, and history.

### Tables (Migration 0014)
- `meta_rankings`: Ranking snapshot per (lottery_id, context_hash, version).
- `meta_ranking_entries`: Individual model scores within a ranking.
- `meta_selections`: Selection history per (lottery_id, context_hash).
- `meta_selection_entries`: Selected models within a selection.

### Dependencies
- Read-only access to `exp_*`, `ml_*`, `dl_*`, `opt_*`, `bt_*`, `draw`.
- NumPy for scoring computations.
- No new external dependencies.

### Non-Goals
- No model training or evaluation (F7/F8/F9/F10).
- No combination generation (F13).
- No UI/dashboard (F14).
- No real-time selection (batch only).

## 11. Elementos explícitamente fuera de F12 / Explicitly OUT of F12

- **Model Training**: F7 (ML) and F8 (DL) train models; F12 only evaluates their persisted metrics.
- **Optimization**: F9 optimizes hyperparameters; F12 only uses optimization results.
- **Backtesting**: F10 runs backtests; F12 only uses backtest results.
- **Experiment Management**: F11 registers experiments; F12 reads experiment data but does not manage experiments.
- **Number Generation**: F13 generates combinations; F12 only selects models/strategies.
- **Dashboard/UI**: F14 provides visualization; F12 is backend-only.
- **Real-time Scoring**: F12 is batch-oriented; real-time selection is out of scope.
- **Meta-Learning Algorithms**: F12 does NOT implement online learning or adaptive models; it uses static scoring.

---

**Ready for proposal (sdd-propose) upon confirmation.**