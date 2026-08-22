# Tasks: Fase 16 — Performance

Status: **planned** · Store: openspec · Date: 2026-08-18
Slice order (dependency): S1a → S2a → S3; S1b → S2b; S5a → S5b; S4/S6/S7 independent (S5a also depends on S1a). Canonical apply order: **S1a → S1b → S2a → S2b → S3 → S4 → S5a → S5b → S6 → S7**. Each slice = one stacked-to-main PR, conventional commits `[T-Sx-yy]`, `--no-verify`, no AI attribution, sub-agents restore `.atl/` before commit (`.atl/` is git-tracked runtime state). Strict TDD backend: RED test first, green via `backend/.venv/bin/pytest`. Planning only — no implementation, no code modification, no commits/PRs (owner mandate).

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~1295 total (S1a 75, S1b 160, S2a 95, S2b 180, S3 140, S4 140, S5a 155, S5b 140, S6 70, S7 140); goldens excluded |
| 400-line budget risk | Low per slice / High total |
| Chained PRs recommended | Yes |
| Suggested split | 10 PRs, one per slice: S1a → S1b → S2a → S2b → S3 → S4 → S5a → S5b → S6 → S7 |
| Delivery strategy | ask-on-risk |
| Chain strategy | stacked-to-main (fase-15 precedent) |

Decision needed before apply: Yes
Chained PRs recommended: Yes
Chain strategy: stacked-to-main
400-line budget risk: Low

**Split-on-overage rule (owner condition 4 / PFM-03):** if the authored diff of any slice exceeds 400 additions+deletions at apply (measured via `git diff --numstat`, goldens excluded), the slice is split into chained PRs. NO `size:exception` is permitted. Each PR keeps its own focused test command, runtime harness, and rollback boundary.

### Suggested Work Units

| Unit | Goal | PR | Focused test command | Runtime harness | Rollback boundary |
|------|------|----|----------------------|-----------------|-------------------|
| S1a | Probability StatValue correctness fix + regression | PR 1 | `backend/.venv/bin/pytest tests/probability` | `probability generate` with active stats snapshot succeeds (test) | Revert commit (reader rewrite) |
| S1b | Migration-contract refresh (8 tests) | PR 2 | `backend/.venv/bin/pytest tests/test_migrations.py tests/bt/test_migration.py` | 14/14 + 7/7 pass, none skipped | Revert commit (test expectations) |
| S2a | bt N+1 + statistics LIMIT pushdown | PR 3 | `backend/.venv/bin/pytest tests/bt/test_assert_queries.py -q` + `tests/bt -q -k run_returns_200 --durations=1` ≤5.0 s | assert-queries shows ≤2 draw SELECTs | Revert commit (service SQL) |
| S2b | exp run_ids indexed lookup + migration 0016 | PR 4 | `backend/.venv/bin/pytest tests/test_exp_comparison.py -q -k compare --durations=1` (design cmd references nonexistent `tests/exp` — see risk) | 0016 up/down round-trip + backfill green | `alembic downgrade 0015` + revert model/service |
| S3 | Backtest window parallelization | PR 5 | `backend/.venv/bin/pytest tests/bt/test_parallel_parity.py tests/bt/test_determinism.py tests/test_determinism.py -q` + `tests/bt -q -k run_returns_200 --durations=1` ≤3.5 s | parity test serial==parallel byte-identical | Revert `engine.py` (+ strategy module) |
| S4 | ML per-number parallelization | PR 6 | `backend/.venv/bin/pytest tests/ml/test_ml_parallel_parity.py tests/ml/test_ml_determinism_e2e.py tests/test_determinism.py -q` + `tests/ml -q -k test_train_basic --durations=1` ≤4.5 s | parity test checksum/fingerprint/quantized metrics byte-identical | Revert `engine.py` (`parallel=False` restores serial) |
| S5a | In-process LRU snapshot read cache | PR 7 | `backend/.venv/bin/pytest tests/test_response_cache.py tests/statistics -q --durations=1` | golden: cached == fresh byte-identical | Delete `core/response_cache.py` + revert wiring |
| S5b | ETag/304 on read endpoints | PR 8 | `backend/.venv/bin/pytest tests/api/test_etag.py tests/api -q` | 304 round-trip; 200 envelope byte-identical with/without ETag | Revert API ETag wiring |
| S6 | Lazy torch/sklearn import | PR 9 | `backend/.venv/bin/pytest tests/test_cold_start.py tests/dl/test_determinism.py -q` | `time python -c "import backend.app.main"` ≤8 s; module-presence guard | Revert import moves |
| S7 | Session-scoped test fixtures + isolation | PR 10 | `backend/.venv/bin/pytest tests/test_isolation_guard.py tests/api -q --durations=10` | setup ≤0.3 s/test; app-backed dirs full pass | Revert `conftest.py` |

## Partition Rules (owner conditions 4, 13, 14)

- Each slice = exactly one PR (10 total), sized ≤400 authored lines.
- S5a and S5b are SEPARATE PRs (condition 13) — LRU primitive+wiring ≠ ETag/304; never merged into one diff.
- S6 validated by `tests/test_cold_start.py` (condition 14) — module-presence guard, not just a timing run.
- S1b and S7 are test/test-infra only (condition 10) — no production changes.
- S4/S6/S7 may land anytime after S1a/S1b; canonical order is used for stack management.
- If any slice's authored diff exceeds 400 at apply: split into chained PRs — no `size:exception`.

## Slice S1a — Probability StatValue fix [~75 ln]

| ID | Scope | Description | Files | Notes | Lines |
|----|-------|-------------|-------|-------|-------|
| T-S1a-01 | PM-04 | RED regression test: seed lottery + draws + active stats snapshot (`stat_frequency` rows) → `probability generate` succeeds (no `ModuleNotFoundError`) and returns rows; reader maps `{number: count}` | modify `backend/tests/probability/test_probability_service.py` | RED-first (strict TDD); PM-04 scenarios 2-3 (generate-succeeds, payload read) | 35 |
| T-S1a-02 | PM-04 | Delete `from backend.app.models.stat_value import StatValue` (line 110); rewrite `_StatsReaderAdapter.frequencies` (107-125) → `select(StatFrequency.number, StatFrequency.count).where(StatFrequency.snapshot_id == snapshot_id)` → `{int(number): int(count)}`; no `metric_id` filter | modify `backend/src/backend/app/services/probability_service.py` | GF-1: none (no engine math change); other `_StatsReaderAdapter` methods untouched | 15 |
| T-S1a-03 | PM-04 | Measurement gate + record: `backend/.venv/bin/pytest tests/probability` full pass (baseline 80 passed) + regression green | modify `backend/tests/probability/test_probability_service.py` | acceptance = test pass/fail (PFM-02 exempt — correctness); rollback = revert commit | 25 |

## Slice S1b — Migration-contract refresh (test-only) [~160 ln]

| ID | Scope | Description | Files | Notes | Lines |
|----|-------|-------------|-------|-------|-------|
| T-S1b-01 | n/a (test-infra) | Extend table/index expectation sets with 0011 opt, 0012 bt, 0013 exp, 0014 meta, 0015 gen domains; replace stale `HEAD_TABLES_0010` pins (6 failing tests) with the true 0015 head set | modify `backend/tests/test_migrations.py` | never hide/skip; grep-verified only these files pin head | 110 |
| T-S1b-02 | n/a (test-infra) | Pin `tests/bt/test_migration.py` downgrade to `command.downgrade(cfg, "0012")` / `"0011"` instead of `"-1"`/`head` (2 failing tests) | modify `backend/tests/bt/test_migration.py` | test-only; NO production or migration code changes | 30 |
| T-S1b-03 | n/a (test-infra) | Measurement gate + record: `test_migrations.py` 14/14 + `tests/bt/test_migration.py` 7/7 pass, none skipped | — | unblocks S2b chain 0016 `down_revision=0015`; rollback = revert commit | 20 |

## Slice S2a — bt N+1 + statistics LIMIT pushdown [~95 ln]

| ID | Scope | Description | Files | Notes | Lines |
|----|-------|-------------|-------|-------|-------|
| T-S2a-01 | BTS-04 | RED assert-queries test (new): draw load emits ≤2 SELECTs (draw query + one eager numbers load) and mapped rows identical to pre-optimization | create `backend/tests/bt/test_assert_queries.py` | proves BTS-04 "draw load is not N+1" (baseline 2 001 SELECTs) | 40 |
| T-S2a-02 | BTS-04 | `_fetch_draws` (bt_service.py 198-220) → `select(DrawModel).options(selectinload(DrawModel.numbers))`, keep `order_by(draw_date)`, map numbers/super_number identically | modify `backend/src/backend/app/services/bt_service.py` | pattern from `draw_repository.list_draws`; GF-1: none (same rows) | 12 |
| T-S2a-03 | STE-10 | `read_frequencies`/`read_gaps` (statistics_service.py 135-158) append `.limit(last)` when `last > 0`, keep `ORDER BY number`; tests: bounded read, order preserved, no-limit unchanged | modify `backend/src/backend/app/services/statistics_service.py` + `backend/tests/statistics/` | STE-10 scenarios 1-3; deterministic order preserved | 28 |
| T-S2a-04 | BTS-04, STE-10 | Measurement gate + record: `backend/.venv/bin/pytest tests/bt -q -k run_returns_200 --durations=1` ≤5.0 s (baseline 6.35) | — | PFM-02 evidence; Depends S1a; rollback = revert commit | 15 |

## Slice S2b — exp_comparisons indexed run_ids + migration 0016 [~180 ln]

| ID | Scope | Description | Files | Notes | Lines |
|----|-------|-------------|-------|-------|-------|
| T-S2b-01 | EXP-009 | Add `run_ids: Mapped[str \| None] = mapped_column(Text, nullable=True)` to `ExpComparison` | modify `backend/src/backend/app/models/exp_comparison.py` | indexes owned by migrations (repo pattern) | 6 |
| T-S2b-02 | EXP-009 | Create migration `0016_exp_comparisons_run_ids.py`: `revision="0016_exp_comparisons_run_ids"`, `down_revision="0015_gen_tables"`; `op.add_column` (nullable) + `op.create_index("ix_exp_comparisons_run_ids", ...)`; Python chunked backfill (500-row batches) using shared derivation `run_ids = ",".join(str(i) for i in sorted(r["run_id"] for r in json.loads(row.comparison_json)["runs"]))`; downgrade drops index+column only | create `backend/alembic/versions/0016_exp_comparisons_run_ids.py` | up/down round-trip test; Depends S1b | 55 |
| T-S2b-03 | EXP-009, EXP-005 | Module-level `_run_ids_key(sorted_run_ids)` single-source helper; `_find_cached_comparison` (410-424) → single `WHERE experiment_id == ? AND run_ids == ?` indexed lookup; legacy JSON-scan fallback while `run_ids IS NULL` rows exist; `compare()` insert path (394-401) sets `run_ids` | modify `backend/src/backend/app/services/exp_service.py` | no blob parse on hit path; JSON stays source of truth | 35 |
| T-S2b-04 | EXP-009, EXP-005 | Tests: 0016 up/down round-trip + backfill; single indexed lookup (assert no `json.loads` on hit); NULL-run_ids legacy fallback; compare() writes run_ids; idempotent compare | modify `backend/tests/test_exp_*.py` (root-level; see risk) + `backend/tests/test_migrations.py` | RED→GREEN; root-level files, not `tests/exp/` | 70 |
| T-S2b-05 | EXP-009 | Measurement gate + record: `backend/.venv/bin/pytest tests/test_exp_comparison.py -q -k compare --durations=1` (near-constant) | — | design/proposal command references `tests/exp` — does not exist (see risk); PFM-02; rollback = `alembic downgrade 0015` + revert service | 14 |

## Slice S3 — Backtest window parallelization [~140 ln]

| ID | Scope | Description | Files | Notes | Lines |
|----|-------|-------------|-------|-------|-------|
| T-S3-01 | BTE-05 | Move function-local `_Dummy` in `bt_service._make_strategy` to module-level `StaticStrategy` in `backtesting/strategy.py` (implements `StrategyProtocol`, returns `[1,2,3,4,5]`); `_make_strategy` → module-level builder | modify `backend/src/backend/app/backtesting/strategy.py` + `backend/src/backend/app/services/bt_service.py` | local classes unpicklable → pool crash; module-level is picklable + behavior-identical | 30 |
| T-S3-02 | BTE-05, PFM-04 | Extract module-level `_evaluate_window(window, strategy_id, config, lottery_id, number_pool, pick_count)` → `(window_index, strategy_metrics, uniform_metrics, hyper_metrics)`; builds DrawContexts + StaticStrategy + per-window `random.Random(config.seed + window_index)` sub-seed in-worker | modify `backend/src/backend/app/backtesting/engine.py` | pure worker: no DB, plain-data payloads; deterministic + injective sub-seeds | 40 |
| T-S3-03 | BTE-05, PFM-04 | `BacktestEngine.run(..., parallel=False)`: serial path unchanged; parallel = `concurrent.futures.ProcessPoolExecutor(max_workers=2).map(...)` used only when `len(windows) >= 2`; order by window_index; `BtService.run` passes `parallel=True`; aggregate + fingerprint unchanged | modify `backend/src/backend/app/backtesting/engine.py` + `backend/src/backend/app/services/bt_service.py` | bounded pool (2); map preserves input order; small-window serial fallback | 30 |
| T-S3-04 | BTE-05, PFM-01 | RED→GREEN `tests/bt/test_parallel_parity.py` (new): serial vs parallel byte-identical (fingerprint, aggregate_metrics, window_history); window_index ordering; pickling round-trip; no-DB-in-worker structural assert | create `backend/tests/bt/test_parallel_parity.py` | GF-1 HARD GATE — any byte diff blocks slice | 30 |
| T-S3-05 | BTE-05, PFM-01/02 | GF-1 gate run: `tests/bt/test_determinism.py` + parity + root `tests/test_determinism.py` all green; measurement `tests/bt -q -k run_returns_200 --durations=1` ≤3.5 s (baseline 6.35) | — | Depends S2a; gate decides, never silent; rollback = revert engine.py | 10 |

## Slice S4 — ML per-number parallelization [~140 ln]

| ID | Scope | Description | Files | Notes | Lines |
|----|-------|-------------|-------|-------|-------|
| T-S4-01 | MLE-04, PFM-04 | Extract module-level `_fit_number(X_train, X_eval, y_train, y_eval, estimator_name, params, number)` → `(number, {metric: Decimal}, model)`; metrics computed in-worker and quantized; `random_state=0`, no shuffle | modify `backend/src/backend/app/ml/engine.py` | pure worker: no DB session/engine; MLE-04 allowlist bounded | 45 |
| T-S4-02 | MLE-04, PFM-04 | `MlEngine.train(..., parallel=False)`: parallel = `ProcessPoolExecutor(max_workers=2).map` over sorted `all_numbers`, results keyed by number; parent reconstructs per_number/models/metrics/fingerprint/checksum identically; **family loop in `MlService.train` stays serial** | modify `backend/src/backend/app/ml/engine.py` | bounded pool (2); sorted-number freeze; atomic per-family tx preserved | 35 |
| T-S4-03 | MLE-05, PFM-01 | RED→GREEN `tests/ml/test_ml_parallel_parity.py` (new): serial vs parallel `TrainResult` byte-identical (checksum, fingerprint, quantized per-number metrics); pickling round-trip; no-DB-in-worker structural assert | create `backend/tests/ml/test_ml_parallel_parity.py` | GF-1 HARD GATE — any byte diff blocks slice | 45 |
| T-S4-04 | MLE-04/05 | GF-1 gate run: `tests/ml/test_ml_determinism_e2e.py` + root `tests/test_determinism.py` green; measurement `tests/ml -q -k test_train_basic --durations=1` ≤4.5 s (baseline 8.18) + `-k test_engine_train_basic` ≤3.0 s (baseline 5.37) | — | BLAS oversubscription: per-family serial fallback on quantized parity failure; rollback = revert engine.py | 15 |

## Slice S5a — Snapshot read cache (in-process LRU) [~155 ln]

| ID | Scope | Description | Files | Notes | Lines |
|----|-------|-------------|-------|-------|-------|
| T-S5a-01 | PFM-05 | Create `core/response_cache.py`: `ThreadSafeLRU(maxsize=256)` = `OrderedDict` + `threading.RLock`; `get`/`set` atomic; eviction on insert past maxsize | create `backend/src/backend/app/core/response_cache.py` | in-process only (D3); no Redis/external store; bounds the 2.4 GB box | 40 |
| T-S5a-02 | PFM-05 | Wire read boundaries: statistics `read_frequencies/read_gaps/read_averages/read_scalars`, probability `read_values`, ml `get_metrics`, graph read, bt `results`; key `(snapshot_id, endpoint, *params)` with `last` folded in; returned payloads treated read-only | modify `backend/src/backend/app/services/statistics_service.py`, `probability_service.py`, `graph_service.py`, `ml_service.py`, `bt_service.py` | key folding prevents cross-param collision; no write-through (new snapshot = new key) | 45 |
| T-S5a-03 | PFM-05 | `tests/test_response_cache.py` (new): hit/miss keying incl. `last` folding; eviction; thread-safety (concurrent reads); golden cached == fresh byte-identical; version bump → new key | create `backend/tests/test_response_cache.py` | GF-1: golden byte-identical cached vs fresh DB-built | 55 |
| T-S5a-04 | PFM-05, PFM-01 | Measurement gate + record: `backend/.venv/bin/pytest tests/statistics -q --durations=1` + cache tests; determinism suite re-run after wiring | — | Depends S1a; memory bounded (≤256 × ≤2 MB); rollback = delete module + revert wiring | 15 |

## Slice S5b — ETag/304 on read endpoints [~140 ln]

| ID | Scope | Description | Files | Notes | Lines |
|----|-------|-------------|-------|-------|-------|
| T-S5b-01 | REQ-13 | Create `api/v1/etag.py`: `etag_for(snapshot)` → strong `"<checksum>"` (statistics `checksum`; ml `checksum`/`input_fingerprint`; bt `fingerprint`) else weak `W/"<snapshot_id>:<version>"`; `should_not_modify(request, etag)` compares `If-None-Match` | create `backend/src/backend/app/api/v1/etag.py` | checksum content-derived → strong ETag correct under immutability | 35 |
| T-S5b-02 | REQ-13 | Apply to read endpoints (statistics frequencies/gaps/averages/scalars, probability values, graph read, ml metrics, bt results): `Response` param; match → `304` empty body; else 200 with unchanged envelope + `ETag` header | modify `backend/src/backend/app/api/v1/statistics.py`, `probability.py`, `graph.py`, `ml.py`, `bt.py` | never recompute (REQ-11 preserved); envelope untouched on 200 | 45 |
| T-S5b-03 | REQ-13, PFM-05 | `tests/api/test_etag.py` (new): ETag derivation; `If-None-Match` → 304 no body; version bump → new ETag (never stale 304); 200 envelope byte-identical with/without ETag; no recompute | create `backend/tests/api/test_etag.py` | GF-1 golden | 50 |
| T-S5b-04 | REQ-13 | Measurement gate + record: `backend/.venv/bin/pytest tests/api -q` + ETag tests | — | Depends S5a; PFM-02; rollback = revert API wiring | 10 |

## Slice S6 — Lazy torch / heavy-dep import [~70 ln]

| ID | Scope | Description | Files | Notes | Lines |
|----|-------|-------------|-------|-------|-------|
| T-S6-01 | DLE-17 | Move `import torch` from module top into `configure_deterministic_torch` (determinism.py) + into `train()` (dl/engine.py) + into `encode_weights` (weights.py); defer `dl.lstm`/`dl.mlp` imports into `_build_model` (first use per family) | modify `backend/src/backend/app/dl/determinism.py`, `dl/engine.py`, `dl/weights.py` | import-time side effects already call-time (thread/seed config preserved); no computation change | 20 |
| T-S6-02 | DLE-17 | Move `from sklearn.metrics import ...` into `MlEngine.train` (ml/engine.py); move sklearn estimator imports from `ml/registry` module top into `build_ml_registry` (first call) | modify `backend/src/backend/app/ml/engine.py`, `ml/registry.py` | sklearn is the dominant eager cost (~12.8 s); deferral set matches spec | 20 |
| T-S6-03 | DLE-17, PFM-06 | `tests/test_cold_start.py` (new): fresh `import backend.app.main` → assert `"torch" not in sys.modules` and `"sklearn" not in sys.modules`; DL determinism tests green; torch/sklearn importable + functional at first use | create `backend/tests/test_cold_start.py` | module-presence guard is the regression; validated by test_cold_start (condition 14) | 20 |
| T-S6-04 | PFM-06 | Measurement gate + record: `time python -c "import backend.app.main"` ≤8 s (baseline 25.3 s, re-measured 30-40 s loaded) | — | GF-1: none (no computation); DL determinism suite is the behavior gate; rollback = revert import moves | 10 |

## Slice S7 — Test infrastructure (TEST-ENV only) [~140 ln]

| ID | Scope | Description | Files | Notes | Lines |
|----|-------|-------------|-------|-------|-------|
| T-S7-01 | n/a (test-infra) | `migrated_db` → session-scoped (alembic upgrade once to session tmp file); `api_engine`/`session_factory` → session-scoped; session-scoped `connection` fixture (one connection, `connect_args={"check_same_thread": False}`) | modify `backend/tests/conftest.py` | TEST-ENV only; no production changes (condition 10) | 55 |
| T-S7-02 | n/a (test-infra) | Per-test `db` = `sessionmaker(bind=connection, join_transaction_mode="create_savepoint")` session, teardown `connection.rollback()`; `client` override binds the SAME connection/savepoint | modify `backend/tests/conftest.py` + `backend/tests/api/conftest.py` | test's own commit() releases only its savepoint → seeded rows never leak; fallback = per-test data reset | 45 |
| T-S7-03 | n/a (test-infra) | `tests/test_isolation_guard.py` (new): test A seeds + commits; test B asserts tables empty (no leakage) | create `backend/tests/test_isolation_guard.py` | guard is the isolation regression net | 20 |
| T-S7-04 | n/a (test-infra) | Document ~1 GB-memory full-suite limitation as known TEST-ENV constraint; measurement gate `backend/.venv/bin/pytest tests/api -q --durations=10` setup ≤0.3 s/test (baseline ~3 s); app-backed dirs (statistics/api/gen/bt) full pass | modify `backend/tests/conftest.py` (docstring) | highest-risk TEST-ENV change; rollback = revert conftest | 20 |

## Dependency Graph + Apply Order

```
S1a (correctness) ──→ S2a ──→ S3          S5a ──→ S5b
                        │                     │
S1b (suite health) ──→ S2b                   └─ (also depends on S1a)
S4 ── independent
S6 ── independent
S7 ── independent
```

Canonical apply sequence: **S1a → S1b → S2a → S2b → S3 → S4 → S5a → S5b → S6 → S7**. S4/S6/S7 are independent and may land anytime after S1a/S1b; the canonical order keeps the stacked-to-main stack linear. Any edge broken (e.g. S3 before S2a) blocks the slice.

## Verification / Gates Strategy (per slice)

- **Measurements (PFM-02)**: every perf slice records baseline + result with the exact proposal §5 command and threshold before acceptance — S2a `tests/bt -q -k run_returns_200` ≤5.0 s; S3 ≤3.5 s; S2b compare near-constant; S4 `test_train_basic` ≤4.5 s + `test_engine_train_basic` ≤3.0 s; S5a `tests/statistics -q --durations=1`; S5b `tests/api -q`; S6 `time python -c "import backend.app.main"` ≤8 s; S7 setup ≤0.3 s/test. S1a/S1b exempt (test pass/fail).
- **GF-1 hard gate (PFM-01)**: S3/S4 parity tests (new) + existing determinism suite (`tests/test_determinism.py`, statistics g9, ML/DL/bt determinism e2e) must stay green after every parallelization/caching slice. Any serial-vs-parallel byte difference BLOCKS the slice. S5a golden cached==fresh; S5b 200-envelope byte-identical; S6 DL determinism suite.
- **≤400-line check**: per PR `git diff --numstat` additions+deletions (goldens excluded); overage → split into chained PRs, no `size:exception`.
- **Lint/tests**: `backend/.venv/bin/ruff check` touched dirs + strict TDD pytest via `backend/.venv/bin/pytest`. Full backend suite may hang under memory pressure → per-directory runs with timeouts.
- **Pre-existing failures tracked, NOT regressions** (must not reappear in touched dirs after each slice): bt migration 2 (until S1b), `test_migrations.py` 6 (until S1b), opt test_engine 1 (missing deap/optuna, out of scope), ruff meta.py 2 (pre-existing).

## Risks

- `tests/exp/` referenced by design §7/proposal §5 does NOT exist — exp tests are root-level `tests/test_exp_*.py` (S2b). Corrected commands used above; flag for sdd-apply/verify.
- Full-suite OOM hang under ~1 GB available (TEST-ENV) → per-directory runs only; documented in S7, not fixed in production.
- S7 isolation regression across app-backed dirs → guard test + full-dir runs; SAVEPOINT-incompatible fixtures → documented fallback (per-test data reset).
- S3/S4 pickling + process overhead on small workloads → module-level picklable callables, serial fallback on <2 windows, bounded pool (2), gate decides.
- BLAS thread oversubscription under 2 workers (S4) → per-family serial fallback on quantized parity failure.
- Lazy-import behavior drift (S6) → import-time side effects audited (already call-time); module-presence guard.
- Migration backfill on large `exp_comparisons` (S2b) → nullable + chunked (500-row batches) + legacy JSON fallback while NULL rows exist.
- Slice estimates match design §6 exactly (none grew); no file collisions — all 7 new test files and `core/response_cache.py`/`api/v1/etag.py` verified absent.

## Next Recommended

`sdd-apply` for `fase-16-performance` — pending orchestrator gate (Decision needed before apply: Yes). Orchestrator to confirm chain strategy = stacked-to-main (fase-15 precedent) before PR 1 (S1a).

## Skill Resolution

- sdd-tasks (loaded): task breakdown + workload forecast + per-slice tables.
- chained-pr (loaded): PR slicing discipline — 10 single-slice PRs, split-on-overage rule, no size:exception.
- work-unit-commits (loaded): commit-by-work-unit; tests with code; each slice = reviewable PR with focused test command, runtime harness, rollback boundary.
- code-optimization (loaded): CPU-bound → ProcessPoolExecutor (never threads), bounded workers, vectorization-first, determinism gate — applied to S3/S4 task framing.