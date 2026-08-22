# Proposal: Fase 16 — Performance

- Change: `fase-16-performance`
- Status: **proposed**
- Store: **openspec**
- Date: 2026-08-17
- Source: [exploration.md](./exploration.md) (complete; baselines, hotspot inventory, evidence, proposed scope P0–P5 and slices S1–S7)
- Owner mandate: bind to exploration baseline; S1 correctness first; ≤400 authored lines/slice; measurements before/after per optimization; GF-1 transversal; risks+rollback per slice; no frontend/deap/optuna/unbacked work.

---

## 1. Executive summary

Fase 16 targets the **measured** hotspots: CPU-bound engine computation (ML ≈245 sequential sklearn fits, backtest window evaluation), two SQL problems (bt N+1 draw load, experiment-compare blob scan), cold start (25.3 s main import, torch 31.4 s), and a TEST-ENV fixture cost (~3 s/test). It also unblocks two defects before any perf work: the latent `StatValue` import bug (probability generate crashes when an active stats snapshot exists) and 6+2 stale migration-contract tests.

**Explicitly OUT of scope**: frontend (measured clean — memoized, no polling); installing `deap`/`optuna` (environment fix, exploration §9); new SQL indexes on payload/snapshot tables (already covered by migrations 0002/0004/0015); the full-suite OOM hang under ~1 GB free memory (documented TEST-ENV limitation, not a production bug — S7 documents it, does not "fix" it in production code); any optimization not backed by an exploration measurement.

## 2. Intent + Problem statement

Three real problems, one TEST-ENV problem, kept separate:

| # | Problem | Class | Env |
|---|---|---|---|
| P1 | ML training and backtest windows are **CPU-bound, sequential, embarrassingly parallel** — highest real latency ceiling | perf | REAL |
| P2 | `StatValue` import bug in `probability_service._StatsReaderAdapter.frequencies` → `ModuleNotFoundError` when `generate` runs with an active stats snapshot | correctness blocker | REAL |
| P3 | 8 pre-existing migration-test failures: `test_migrations.py` pins `HEAD_TABLES_0010` while head is now 0015; `tests/bt/test_migration.py` assumes head=0012 ("-1" now drops 0014/0015) | suite health | BOTH |
| P4 | Fixture setup ~3 s/test (fresh alembic upgrade per test) + torch import 25-31 s/process dominate suite time | TEST-ENV | TEST-ENV |

Environment separation: REAL = long-lived uvicorn + migrated prod schema; TEST-ENV = pytest process churn + memory-limited 3-core/2.4 GB-available box. P4 is TEST-ENV only; fixes must not trade REAL behavior for TEST-ENV gains.

## 3. Proposed scope — 7 slices, concretized (with sub-slices)

Each sub-slice ≤400 authored lines (see §9 partition review). Dependencies: S1a → S2a → S3; S1b → S2b; S5 depends on S1a; S4/S6/S7 independent.

### S1a — Probability StatValue fix (P0 correctness)
- **Goal**: `probability generate` works with an active stats snapshot.
- **Files**: `backend/src/backend/app/services/probability_service.py`; `backend/tests/probability/test_probability_service.py`.
- **Change**: replace the `from backend.app.models.stat_value import StatValue` import (probability_service.py:110) with `StatFrequency`; rewrite `_StatsReaderAdapter.frequencies` (107-125) to `select(StatFrequency).where(snapshot_id == ...)` and map `{number: count}` (no `metric_id` filter — the table has no such column). Add a regression test that seeds a lottery + active stats snapshot (`stat_frequency` rows) and asserts `generate` returns rows instead of crashing.
- **Estimate**: ~75 lines (15 service + ~60 test).
- **Dependencies**: none. **Risks**: field-shape mismatch (number vs subject) — mitigated by the regression test. **Rollback**: revert commit.

### S1b — Migration-contract refresh (P0 suite health)
- **Goal**: the 6 `test_migrations.py` + 2 `tests/bt/test_migration.py` failures pass by CORRECTLY updating expectations to the real 0015 head — never hiding/ignoring tests.
- **Files**: `backend/tests/test_migrations.py`; `backend/tests/bt/test_migration.py`.
- **Change**: extend the table/index expectation sets with the 0011 opt, 0012 bt, 0013 exp, 0014 meta, 0015 gen domains; replace stale `HEAD_TABLES_0010` with the true head set; in `test_migration.py` pin the downgrade to `0012`/`0011` revisions instead of `head`/"-1". No migration or production code changes.
- **Estimate**: ~160 lines.
- **Dependencies**: none. **Risks**: expectation drift elsewhere (grep-verified: only these two files pin head). **Rollback**: revert commit.

### S2a — bt N+1 + statistics LIMIT pushdown
- **Goal**: kill the 1-query-per-draw N+1 and the fetch-all-then-slice reads.
- **Files**: `backend/src/backend/app/services/bt_service.py`; `backend/src/backend/app/services/statistics_service.py`; `backend/tests/bt/`, `backend/tests/statistics/` tests.
- **Change**: `_fetch_draws` (bt_service.py:198-220) → `select(DrawModel).options(selectinload(DrawModel.numbers))` (pattern already proven in `draw_repository.list_draws`, draw_repository.py:67-87), mapping numbers the same way. `read_frequencies`/`read_gaps` (statistics_service.py:135-158) → append `.limit(last)` when `last > 0`, keeping `ORDER BY number` (deterministic order preserved).
- **Estimate**: ~95 lines (12 + 20 service, ~60 tests incl. an assert-queries regression for the N+1).
- **Dependencies**: S1a. **Risks**: Low — same rows, one round-trip; LIMIT keeps order. **Rollback**: revert commit.

### S2b — exp_comparisons indexed `run_ids`
- **Goal**: near-constant comparison cache lookup, no whole-blob `json.loads` scan.
- **Files**: `backend/src/backend/app/models/exp_comparison.py`; new `backend/alembic/versions/0016_exp_comparisons_run_ids.py`; `backend/src/backend/app/services/exp_service.py`; `backend/tests/exp/` tests.
- **Change**: add nullable `run_ids` (Text) column + non-unique index `ix_exp_comparisons_run_ids`; migration backfills from existing `comparison_json` (sorted run ids, comma-joined); `_find_cached_comparison` (exp_service.py:410-424) → single `WHERE experiment_id == ? AND run_ids == ?` indexed lookup; **legacy path kept during transition**: rows with `NULL run_ids` fall back to the JSON parse until backfilled; the `compare()` creation path (exp_service.py:394-401) writes `run_ids` on insert. Blob remains the source of truth for content; `run_ids` is a denormalized lookup key (immutability preserved).
- **Estimate**: ~180 lines (6 model + ~55 migration + ~35 service + ~85 tests).
- **Dependencies**: S1b (migration chain above 0015). **Risks**: backfill cost on large tables (SQLite `ALTER TABLE ADD COLUMN` + `UPDATE`); mitigated by nullable + legacy fallback. **Rollback**: `alembic downgrade 0015` (drops column); service revert.

### S3 — Backtest window parallelization
- **Goal**: parallel window evaluation, deterministic output.
- **Files**: `backend/src/backend/app/backtesting/engine.py`; `backend/tests/bt/test_determinism.py` (+ new parity test).
- **Change**: hoist the per-window evaluate body (engine.py:94-130) into a module-level picklable `_evaluate_window`; run windows via `concurrent.futures.ProcessPoolExecutor` with `max_workers=2` (3-core, memory-limited box; exploration §7 GIL note — CPU-bound → processes, NEVER threads). Results ordered by `window_index` before aggregation. RNG: benchmarks seeded from `config.seed` deterministically per window; iteration order frozen. Engine stays pure (no DB in workers).
- **Estimate**: ~140 lines (70 engine + ~70 new serial-vs-parallel byte-identical parity test; existing `test_determinism.py` gates unchanged).
- **Dependencies**: S2a (bt_service touch). **Risks**: strategy/benchmark picklability; process overhead on few small windows; any GF-1 break **blocks the slice**. **Rollback**: revert engine.py.

### S4 — ML per-number parallelization
- **Goal**: parallelize the 49-per-family fit loop.
- **Files**: `backend/src/backend/app/ml/engine.py`; `backend/tests/ml/test_ml_determinism_e2e.py` (+ parity test).
- **Change**: `MlEngine.train` per-number loop (ml/engine.py:124-135) → bounded `ProcessPoolExecutor(max_workers=2)`, one worker per number fit; collect results keyed by sorted number (freeze order), reconstruct `per_number`/`models` deterministically. **Family loop in `MlService.train` stays serial** (keeps atomic-per-family tx + no DB sessions in workers — scoped out). `random_state=0` already fixed in registry (D2, registry.py:36-39); no shuffle. Determinism gates: existing `test_ml_determinism_e2e.py`, root `tests/test_determinism.py` GF-1, plus new serial-vs-parallel `TrainResult` byte-identical parity test (checksum + fingerprint + quantized metrics).
- **Estimate**: ~140 lines (65 engine + ~75 test).
- **Dependencies**: none. **Risks**: pickling 49 fitted models back (memory ×workers — bounded by max_workers=2); sklearn `n_jobs` interplay; a GF-1 break **blocks the slice**. **Rollback**: revert engine.py.

### S5a — Snapshot read cache (immutable, version-keyed)
- **Goal**: repeated immutable snapshot reads served from memory.
- **Files**: new `backend/src/backend/app/core/response_cache.py`; `backend/src/backend/app/services/statistics_service.py`, `probability_service.py`, `graph_service.py`, `ml_service.py`, `bt_service.py` read paths.
- **Change**: in-process cache keyed on `(snapshot_id, endpoint)` for read-only paths over immutable payloads; no write-through (a new snapshot version is a new key — immutability makes invalidation trivial, exploration §6); bounded size (LRU) to respect the 2.4 GB-available box. Wrapped at the service read boundary, returning the identical payload object the DB path would build.
- **Estimate**: ~155 lines (70 new module + ~45 stats/prob wiring + ~40 graph/ml/bt).
- **Dependencies**: S1a (probability read correctness first). **Risks**: cache key collisions (mitigated by version-keying), memory growth (bounded LRU). **Rollback**: delete module / revert wiring.

### S5b — ETag/304 on read endpoints + cache tests
- **Goal**: HTTP-level 304 responses for unchanged snapshots.
- **Files**: `backend/src/backend/app/api/v1/statistics.py` (+ read endpoints for prob/graph/ml/bt); `backend/tests/api/` tests.
- **Change**: derive `ETag` from the snapshot checksum/version on read endpoints; honor `If-None-Match` → `304` without body. Add cache tests: hit/miss keying, version bump invalidates, ETag round-trip, 304 path, and a golden check that a cached read == fresh read byte-identical.
- **Estimate**: ~140 lines (50 endpoint wiring + ~90 tests).
- **Dependencies**: S5a. **Risks**: header correctness with envelope responses; mitigated by tests. **Rollback**: revert API wiring.

### S6 — Lazy torch / heavy-dep import
- **Goal**: `import backend.app.main` 25.3 s → seconds.
- **Files**: `backend/src/backend/app/dl/determinism.py`, `dl/engine.py`, `dl/lstm.py`, `dl/mlp.py`, `dl/weights.py`; `backend/src/backend/app/ml/engine.py`; import-graph audit via `main.py` transitive path.
- **Change**: move top-level `import torch`/torch.nn (and sklearn in ml/engine.py) to first-use inside the entry functions (`configure_deterministic_torch`, `engine.train`, model `forward`/builders). **Behavior identical**: `configure_deterministic_torch` already applies thread/seed config at call time, not import time (dl/determinism.py:28-41), so deferred import preserves semantics; DL determinism tests (`tests/dl/test_determinism.py`, `test_dl_determinism_e2e.py`) must stay green.
- **Estimate**: ~70 lines.
- **Dependencies**: none. **Risks**: accidental eager import reintroduces cost (audit gates); import-time side effects must move with the import. **Rollback**: revert.

### S7 — Test infrastructure (TEST-ENV only)
- **Goal**: fixture setup ~3 s/test → ≤0.3 s/test.
- **Files**: `backend/tests/conftest.py`; `backend/tests/api/conftest.py` (and subdir conftests as needed).
- **Change**: session-scoped migrated DB (alembic upgrade once per session to a session-scoped tmp file) + session-scoped engine/sessionmaker; keep per-test `db`/`client` isolation by restoring a clean transaction boundary per test (SAVEPOINT/rollback or per-test data reset) — the per-test isolation guarantee MUST be preserved. Add one guard test proving a test's seeded rows do not leak into the next. Document the ~1 GB-memory full-suite limitation as a known TEST-ENV constraint (not fixed in production code).
- **Estimate**: ~140 lines (110 conftest + ~30 api conftest).
- **Dependencies**: none. **Risks**: isolation regression across the app-backed dirs (statistics/api/gen/bt) — highest-risk TEST-ENV change; mitigated by the guard test + running those dirs green. **Rollback**: revert conftest.

## 4. DoD + measurable acceptance criteria

**Phase-level DoD (IMPLEMENTATION_ROADMAP.md:441-451)**: all tasks implemented; corresponding tests pass; documentation updated; no critical open errors; acceptance criteria met; changes reproducible and traceable (conventional commits, no AI attribution, AGENTS.md).

**Per-slice acceptance**:

| Slice | Acceptance gates |
|---|---|
| S1a | Regression test green; `tests/probability` full pass; probability `generate` with active stats snapshot succeeds |
| S1b | `tests/test_migrations.py` 14/14 + `tests/bt/test_migration.py` 7/7 pass; no skipped/hidden tests |
| S2a | Assert-queries test shows ≤2 draw queries; bt + statistics dirs green; target met (§6) |
| S2b | Migration 0016 up/down round-trip; compare() indexed lookup test; exp dir green; target met |
| S3 | bt determinism + parity byte-identical test green; target met; GF-1 verified (§7) |
| S4 | ml determinism e2e + parity byte-identical test green; target met; GF-1 verified (§7) |
| S5a | Cache hit/miss + version-keying tests green; cached == fresh byte-identical |
| S5b | ETag/304 tests green; read dirs green |
| S6 | Cold-start target met (§6); DL determinism tests green; `import torch` still works on first DL use |
| S7 | Setup ≤0.3 s/test; isolation guard green; app-backed dirs full pass |

Every perf slice also gates on **≤400 authored lines** and a **baseline→target measurement run recorded before and after**.

## 5. Baseline → target per hotspot (measurement commands exact)

| Hotspot | Slice | Baseline | Target | Measurement command |
|---|---|---|---|---|
| BT API run 200 | S2a/S3 | 6.35 s → 5.0 s (S2a) → ≤3.5 s (S3) | `pytest tests/bt -q -k run_returns_200 --durations=1` |
| BT `_fetch_draws` N+1 | S2a | 2 001 SELECTs | ≤2 SELECTs | assert-queries regression test |
| Exp compare cache scan | S2b | O(N) blob `json.loads` | 1 indexed lookup | `pytest tests/exp -q -k compare --durations=1` |
| ML `test_train_basic` | S4 | 8.18 s | ≤4.5 s | `pytest tests/ml -q -k test_train_basic --durations=1` |
| ML engine train basic | S4 | 5.37 s | ≤3.0 s | `pytest tests/ml -q -k test_engine_train_basic --durations=1` |
| Statistics reads | S5a/S5b | 0.06 s (cProfile) | cached ~0 s / 304 | `pytest tests/statistics -q --durations=1` + ETag test |
| Cold start `import backend.app.main` | S6 | 25.3 s | ≤8 s | `time python -c "import backend.app.main"` |
| Fixture setup | S7 | ~3 s/test | ≤0.3 s/test | `pytest tests/api -q --durations=10` (setup col) |
| Torch determinism setup | — | 22.7 s | unchanged (one-shot/process) | — |

## 6. GF-1 verification strategy (transversal)

Rule: **a GF-1 violation blocks the slice** — it is a hard gate, not a warning.

- **S3 (parallel windows)**: existing `tests/bt/test_determinism.py` + new parity test asserting `BacktestEngine.run` output (fingerprint, `window_history`) is byte-identical serial vs parallel; window order frozen by `window_index`; per-window benchmark RNG derived deterministically from `config.seed`.
- **S4 (parallel fits)**: existing `tests/ml/test_ml_determinism_e2e.py` + root `tests/test_determinism.py` GF-1 e2e + new parity test (checksum/fingerprint/quantized metrics byte-identical serial vs parallel); fit order frozen by sorted number; `random_state=0` per worker; engine never shuffles (D2).
- **S5 (cache)**: cached payload == fresh DB-built payload byte-identical (golden check); cache keyed on snapshot version so a new version is a new key; generation output unchanged (determinism tests re-run).
- **S6 (lazy import)**: no computation changes; DL determinism tests verify behavior after deferral.
- Existing determinism suite acts as the aggregate gate: `tests/test_determinism.py` (GF-1 two-indep-gen + CLI/API byte-identical), `tests/statistics/test_statistics.py::test_g9_two_independent_generations_are_byte_identical`, ML and DL determinism e2e, and bt determinism — all must remain green after every parallelization/caching slice.

## 7. Risks + rollback per slice

| Slice | What breaks | Rollback | Dependency edges |
|---|---|---|---|
| S1a | Wrong field mapping in reader | revert commit | unblocks S2a/S5 |
| S1b | Wrong head expectations encode drift | revert commit | unblocks S2b |
| S2a | Result-order change from LIMIT | revert commit | needs S1a |
| S2b | Migration backfill error / column leak | `alembic downgrade 0015` | needs S1b |
| S3 | Non-deterministic ordering; pickling failure | revert engine.py | needs S2a |
| S4 | Model pickle cost / determinism break | revert engine.py | none |
| S5a/S5b | Stale cache / wrong ETag / memory growth | delete module / revert wiring | needs S1a |
| S6 | Eager import reintroduced; behavior drift | revert | none |
| S7 | Test isolation regression | revert conftest | none |

## 8. Slice partition review (≤400 compliance, honest)

| Slice | Est. authored lines | Verdict |
|---|---|---|
| S1a | ~75 | OK, single |
| S1b | ~160 | OK, single |
| S2a | ~95 | OK, single |
| S2b | ~180 | OK, single |
| S3 | ~140 | OK, single |
| S4 | ~140 | OK, single |
| S5a | ~155 | OK, single |
| S5b | ~140 | OK, single |
| S6 | ~70 | OK, single |
| S7 | ~140 | OK, single |

**Split decisions**: S1 splits into S1a/S1b (two independent P0 fixes — probability correctness vs migration contracts; the combined slice would blur review focus, though ~235 total stays <400). S2 splits into S2a/S2b (SQL read-path vs migration+backfill; keeps the exp migration a self-contained PR). S5 splits into S5a/S5b (cache primitive+wiring vs ETag/304+tests) — combined ~295 stays <400 but the split keeps each PR autonomous and reviewable. S3/S4 stay single: even with determinism parity tests they are ~140 each. No slice requires a `size:exception`. Estimated total authored ≈ 1 450 lines across 10 PRs.

## 9. P0 separation statement

S1 (correctness) is **phase-zero**, NOT a performance optimization. Its acceptance is functional correctness — probability `generate` succeeds with an active stats snapshot, and all 8 migration-contract tests pass — measured by test pass/fail, not seconds. No perf slice begins until S1a/S1b land. Perf slices (S2-S7) are measured against the P1-P4 baseline table; correctness and speed are never conflated.

## 10. Capabilities

**New**: None (perf refactor + correctness fixes; no new user-facing capability).

**Modified**: none at spec-requirement level — behavior-preserving refactors. Note for sdd-spec: S5b adds observable HTTP behavior (ETag/304) and S1a corrects the statistics-reader contract so probability `generate` honors active stats snapshots (existing requirement scenario, currently silently broken); both MAY warrant scenario-level delta updates to `backend` / `probability-engine` specs during the spec phase, but are treated here as implementation-level.

## 11. Decisions to confirm with the user

1. **Migration-failure count**: owner mandate cites 6; verified 6 in `test_migrations.py` **plus 2** in `tests/bt/test_migration.py` (same root cause — head moved 0010→0015). Include all 8 in S1b.
2. **S4 scope**: engine-level per-number parallel only; `MlService` family loop stays serial (keeps atomic per-family tx, no DB sessions in workers). Confirm before spec.
3. **S5 cache**: in-process LRU keyed on `(snapshot_id, endpoint)`; no Redis/external store. Confirm.
4. **S6 deferral set**: torch in `dl/*` + sklearn in `ml/engine.py`; verified behavior-identical via DL determinism tests.
5. **S7**: session-scoped migrated DB with per-test rollback isolation; document (not fix) the full-suite OOM constraint.

## 12. Next recommended

`sdd-spec` for `fase-16-performance` (pending owner gate on §11).