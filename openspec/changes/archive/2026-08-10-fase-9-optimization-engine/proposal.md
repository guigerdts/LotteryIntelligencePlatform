# Proposal: Fase 9 — Optimization Engine

**Change**: `fase-9-optimization-engine` · Store: openspec · Date: 2026-08-10 · Predecessor: exploration

## 1. Intent

Deterministic optimization engine that finds optimal hyperparameters for ML/DL lottery prediction models. Four algorithms (GA, PSO, Bayesian, SA) search configurable parameter spaces, evaluating fitness via walk-forward validation on existing ML/DL training pipelines. Single-objective per run with configurable metric (f1, roc_auc, accuracy, precision, recall). Results persist as immutable `opt_*` snapshots. No feature selection, no number selection, no backtesting — those belong to F10/F13.

## 2. Scope

**In**: `app/opt/` (registry, fingerprint, determinism, optimizers, providers); migration `0011_opt_tables` (`opt_snapshots`, `opt_results`); deap + optuna signed exceptions; CLI `lip opt train|models|metrics|params`; API `POST /opt/train`, `GET /opt/models`, `GET /opt/metrics`, `GET /opt/params`; new `opt-engine` spec + backend delta.

**Out**: Feature selection (F10/F13 territory); number selection/generation (F13); full backtesting (F10); experiment tracking/comparison (F11); multi-objective Pareto optimization; GPU/CUDA; weights download; `/opt/predict`.

## 3. Capabilities

- **New** `opt-engine` → `openspec/specs/opt-engine/spec.md` (engine `OE-..`, per-algorithm `OA-..`)
- **Modified** `backend` REQ-10/11/12 — `/opt/*` route + `lip opt` parity (delta)

## 4. Decisions

- **D1 Target**: Hyperparameters only. No feature selection, no number selection. F9 optimizes model params; F10 evaluates historically; F13 generates numbers.
- **D2 Deps**: `deap==1.4.1` (GA) + `optuna==4.0+` (Bayesian); PSO/SA custom (~50 lines each). 2 signed exceptions scoped to F9. Ban-gate test asserts deap/optuna absent from F7/F8 trees.
- **D3 Objective**: Single-objective configurable. Per-run: `objective_metric` (f1|roc_auc|accuracy|precision|recall) + `objective_direction` (maximize|minimize). One metric per optimization; metric is configurable, not hardcoded. Default: f1/maximize.
- **D4 Convergence**: Both fixed + early stopping. Default: `termination=fixed` (max_generations/evaluations). Configurable: `termination=early_stopping` (patience, min_delta). Early stopping must NOT alter result when disabled. Termination params MUST be in fingerprint.
- **D5 Integration**: Direct calls to `ml.engine.train()` and `dl.engine.train()`. F9 is composition root; engines are pure functions called inside optimizer loops. No pre-trained model objects passed between layers.
- **D6 Floor**: ≥100 real draws (consistent with DL). Clean `INSUFFICIENT_DATA` (422) below floor.
- **D7 Determinism**: Seed-based; `configure_deterministic_torch(0)` for DL-dependent runs; Decimal-quantized metrics; fingerprint `{optimizer, params, objective, data_hash, seed, OPTIMIZER_GENERATOR_VERSION, termination_params}`.
- **D8 Scope**: `core-4` = {ga, pso, bayesian, sa} executed. No future-X declared (all 4 implemented).
- **D9 PR chain** (≤400 LOC, stacked-to-main): deps+0011+models (~250) · opt core (registry+fingerprint+determinism+version) (~350) · optimizers (ga+pso+sa+bayesian) (~400) · engine+providers (~380) · service+API+CLI (~350) · e2e+docs (~300).

## 5. Approach

F7/F8 mirror: pure engine, composition-root service, own provider Protocols (`opt/providers.py`), stateless pure helpers shared by import (quantize, canonical digest), atomic active→retired→failed, fingerprint idempotency, manual-only reads (404 absent), additive `0011` (down_revision `0010_dl_tables`).

Optimizer architecture:
- Each optimizer implements `OptimizerProtocol.optimize(objective_fn, search_space, seed) -> OptResult`
- Objective function wraps `ml.engine.train()` or `dl.engine.train()`, returns `Decimal` fitness
- Search space is JSON-serializable parameter ranges (bounds, choices)
- Convergence tracked per-evaluation; termination checked after each generation/iteration

## 6. Affected Areas

| Area | Impact |
|---|---|
| `backend/pyproject.toml`, ban-gate tests | Modified (2 new signed exceptions) |
| `models/opt_snapshot.py`, `opt_result.py`, `0011_opt_tables.py` | New |
| `app/opt/**`, `services/opt_service.py` | New |
| `api/v1/opt.py`, `schemas/opt.py`, `cli.py` | New/Mod |
| `tests/opt/*`, `test_opt_pr1.py` | New |
| `specs/opt-engine`, README, PROJECT_STATUS, API_SPEC §10 | New/Mod |

## 7. Risks

| Risk | L | Mitigation |
|---|---|---|
| Optimizer overfitting to train set | High | Walk-forward validation enforced; optimizer only sees train metrics |
| Stochastic non-reproducibility | High | Seed-based; termination in fingerprint; same-env GF1 gate |
| New dep exception scope creep | Med | Signed comments, F9-bound ban-gate tests |
| Data scarcity | High | INSUFFICIENT_DATA floor; ≥100 draws |
| Convergence noise | Med | Multiple runs with different seeds; Decimal-quantized metrics |
| Optuna sklearn dep conflict | Low | optuna uses its own sklearn; no conflict with scikit-learn==1.6.1 |

## 8. Rollback

`alembic downgrade 0011` drops only `opt_*`; revert deap/optuna pins + exception comments; remove `app/opt/`, service, routes; F1–F8 untouched.

## 9. Dependencies

F1 draws + F4 active feature snapshot (providers); F7 ML engine (objective function); F8 DL engine (objective function); `deap` GA library; `optuna` Bayesian library; numpy shared; sklearn untouched; torch untouched.

## 10. Success Criteria

- GF1 two-DB e2e: identical fingerprint + checksum + metrics rows on CPU
- <100 draws ⇒ `INSUFFICIENT_DATA`, no snapshot written
- 4 optimizers execute: GA, PSO, Bayesian, SA
- Configurable objective: f1/maximize and roc_auc/maximize produce different results
- Fixed termination deterministic; early stopping configurable
- No feature selection, no number selection, no backtesting in F9
- 0011 up/down non-destructive; `ml_*`/`dl_*` untouched
- 6 PRs ≤400 LOC; pytest + ruff green

## Proposal question round

Relay to user — assumptions to confirm before specs: (1) core-4 = {ga, pso, bayesian, sa}; (2) single-objective configurable per D3; (3) termination params in fingerprint per D4; (4) direct engine calls per D5; (5) no feature selection, no number selection per D1 boundary. Correct any answer or request a second round.
