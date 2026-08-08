# Tasks: Fase 5 — Probability Engine

**Change**: fase-5-probability-engine · **Store**: openspec · **Date**: 2026-08-08
**Artifact**: tasks (this change) — implementation tasks.

## Overview

Implementation mirrors the F3/F4 snapshot contract inside a new `probability/` package: pure byte-identical engine (7 methods, Decimal/int only, fixed-seed `random.Random(seed)` Monte Carlo — D2/PES-05), own Provider Protocols (PES-06), `prob_snapshots` + `prob_values` persisted by a consolidated `snapshot_store`, orchestrated by `ProbabilityService` (idempotent generate, atomic retire-on-replace, `failed` on error), manual CLI + API (POST generate / GET reads, 404 `SNAPSHOT_NOT_FOUND`), migration 0007 with `prob_*`-only rollback, fixture-driven tests (live DB empty, PES-11). Out of scope: prediction/ML/graph/joint-pairwise/scheduler/new numeric deps. Stacked-to-main: PR1a → PR1b → PR2a → PR2b → PR3a → PR3b → PR4; every PR ≤400 LOC.

## Workload Forecast

```text
Decision needed before apply: No
Chained PRs recommended: Yes
Chain strategy: stacked-to-main
400-line budget risk: Low
```

| Field | Value |
|-------|-------|
| Estimated changed lines | ~1,540 (7 stacked PRs, each ≤390) |
| 400-line budget risk | Low — every PR ≤400 after the split |
| Chained PRs recommended | Yes — stacked-to-main (7 slices) |
| Chain strategy | stacked-to-main (each PR merges to main in order) |
| Delivery strategy | ask-on-risk — no size exception needed |
| Decision needed before apply | No — all PRs within budget |

## PR Plan

| PR | Scope | Est. LOC | Dependencies |
|----|-------|----------|--------------|
| PR1a | Package seam + fingerprint + determinism + registry + providers + their tests | 210 | None |
| PR1b | Engine puro (7 methods) + engine RED fixtures | 390 | PR1a |
| PR2a | `prob_*` ORM models + migration 0007 | 210 | PR1b |
| PR2b | snapshot_store + ProbabilityService + adapters + unit tests | 300 | PR2a |
| PR3a | Schemas + API router + API tests | 180 | PR2b |
| PR3b | CLI commands + E2E tests | 170 | PR3a |
| PR4 | Docs chores + final gates | 80 | PR3b |

## Tasks

### PR1a: Probability Package — Foundation

#### T-01: Package seam + version constant
- **Description**: Create `probability/__init__.py` (docstring-only seam, F0 rule) exposing `PROB_GENERATOR_VERSION` pinned independently of `STATS_`/`FEATURE_` versions.
- **Requirements**: PES-04 · **Design**: Module Layout, D2
- **Files**: `backend/src/backend/app/probability/__init__.py`
- **Dependencies**: None
- **Acceptance**: seam imports clean; `PROB_GENERATOR_VERSION` importable, independent; no logic in `__init__`.
- **Est. LOC**: 20

#### T-05: Input fingerprint
- **Description**: Create `probability/fingerprint.py` — canonical JSON (`sort_keys=True, separators=(",",":")`) → SHA-256 hex input fingerprint (PES-05).
- **Requirements**: PES-05 · **Design**: Seed/Determinism
- **Files**: `backend/src/backend/app/probability/fingerprint.py`
- **Dependencies**: None
- **Acceptance**: stable hex for equal inputs; stable across key ordering; matches design formula.
- **Est. LOC**: 35

#### T-06: Determinism + seed policy
- **Description**: Create `probability/determinism.py` — `seed = int.from_bytes(sha256(canonical_json({input_fingerprint, model_params, n_simulations, PROB_GENERATOR_VERSION})).digest()[:16], "big")`; `monte_carlo` uses isolated `random.Random(seed)`, never global. Write `tests/probability/test_determinism.py`.
- **Requirements**: PES-05, D2 · **Design**: Seed/Determinism
- **Files**: `probability/determinism.py`, `backend/tests/probability/test_determinism.py`
- **Dependencies**: T-05
- **Acceptance**: same inputs ⇒ identical seed + byte-identical MC rerun; `n_simulations` change ⇒ new seed, still deterministic (PES-05 scenarios).
- **Est. LOC**: 45

#### T-07: Method registry
- **Description**: Create `probability/registry.py` — `MethodDefinition` (id/version/params) + dict-dispatch registry (D-A2), registering the 7 canonical methods; unknown id → `None`; no Kahn/topo dependency.
- **Requirements**: PM-01..07, PES-04 · **Design**: Module Layout (D-A2)
- **Files**: `probability/registry.py`
- **Dependencies**: T-01
- **Acceptance**: all 6 canonical + univariate conditional registered; definitions frozen/versioned; lookup of unknown id returns `None`.
- **Est. LOC**: 50

#### T-08: Provider protocols
- **Description**: Create `probability/providers.py` — `DrawReader`, `StatSnapshotReader`, `FeatureSnapshotReader` Protocols + `DrawRow`/`LotteryRules`/`StatsRef` carries; reads `ORDER BY draw_number, id`; missing ⇒ skipped/absent (never guessed). Write `tests/probability/test_providers.py` protocol-contract test.
- **Requirements**: PES-06, PES-10 · **Design**: Providers (PES-06)
- **Files**: `probability/providers.py`, `tests/probability/test_providers.py`
- **Dependencies**: None
- **Acceptance**: protocol contract test — no concrete `statistics`/`feature_engineering`/models import; multi-lottery via `lottery_rules`; missing snapshots → `None`.
- **Est. LOC**: 60

### PR1b: Engine puro + engine tests

#### T-02 [RED]: Hand-computed engine fixtures
- **Description**: Write `tests/probability/test_engine.py` — PM-01..07 hand-computed fixtures: trio combinatorics (PM-01), binomial (PM-02), Poisson (PM-03), empirical freq/total (PM-04), seeded MC rerun equality (PM-05), Bayes rerun (PM-06), windowed conditional 8/20 (PM-07); assert no float in any value/checksum (PES-05).
- **Requirements**: PM-01..07, PES-05 · **Design**: Engine API, Seed/Determinism
- **Files**: `backend/tests/probability/test_engine.py`
- **Dependencies**: None
- **Acceptance**: RED tests fail with `ImportError`/`AssertionError` before `engine.py` exists (strict_tdd).
- **Est. LOC**: 180
- **Status**: [x] Done — 33 RED fixtures written first; collection failed with `ModuleNotFoundError` before engine.py existed (GREEN gate: 33 passed).

#### T-03 [GREEN]: Exact trio (hypergeometric + binomial + poisson)
- **Description**: Create `probability/engine.py` — `hypergeometric(N,n,r)` grid by match count via `math.comb`; `binomial(n,p)`; `poisson(λ,kmax)` at fixed Decimal precision context; all int/Decimal, no float.
- **Requirements**: PM-01/02/03, PES-05 · **Design**: Engine API
- **Files**: `probability/engine.py`
- **Dependencies**: T-02
- **Acceptance**: PM-01..03 scenarios pass; exact combinatorics; no float output.
- **Est. LOC**: 90
- **Status**: [x] Done — `hypergeometric(N,n,r)` grid, `binomial(n,p)`, `poisson(λ,kmax)` implemented; PM-01/02/03 hand fixtures all exact; ruff clean.

#### T-04 [GREEN]: Conditional + empirical + bayes + monte_carlo
- **Description**: Extend `probability/engine.py` — `empirical(freq,total)` Decimal; `bayes(prior,like)` normalized fold; `conditional(window_counts, window_size)` univariate only (never joint/pairwise); `monte_carlo(rng, rules, params)` int counts → quantized Decimal + p50/p90/p99 quantiles; aggregates only, never raw histories (PES-01/D-A6).
- **Requirements**: PM-04/05/06/07, PES-01, PES-05 · **Design**: Engine API, Seed/Determinism
- **Files**: `probability/engine.py`
- **Dependencies**: T-02, T-06
- **Acceptance**: PM-04..07 pass; MC persists aggregates + quantiles only; conditional equals 8/20=0.4.
- **Est. LOC**: 120
- **Status**: [x] Done — `empirical`/`bayes`/`conditional`/`monte_carlo` implemented; MC returns only `counts`+`probabilities`+`quantiles` (PES-01/D-A6); seed rerun equality proven; ruff clean.

### PR2a: Persistence Foundation

#### T-09: `prob_*` ORM models
- **Description**: Create `prob_snapshot.py` + `prob_value.py` — surrogate id PK; lottery FK RESTRICT; Unique(lottery_id, model_set, version); checksum/input_fingerprint String(64); status CHECK active|retired|failed; is_locked, draw_count, draws_from/to; prob_values: model_id, model_version, subject, draw_number NULL (no FK to draw — PES-03), Numeric(20,8) value, params_json, Unique(snapshot_id, model_id, model_version, subject, draw_number). Register in `models/__init__.py`.
- **Requirements**: PES-01, PES-03, PES-04 · **Design**: Data Model
- **Files**: `backend/src/backend/app/models/prob_snapshot.py`, `models/prob_value.py`, `models/__init__.py`
- **Dependencies**: T-01
- **Acceptance**: ORM maps header + normalized payload; NULL draw_number grid rows OK; checks/unique per design.
- **Est. LOC**: 120
- **Status**: [x] Done — `ProbSnapshot` (surrogate id PK, model_set String(16)="core", uq_prob_snapshots_scope_version, range/status CHECKs) + `ProbValue` (surrogate id PK per D-A4, uq_prob_values_cell, nullable draw_number, params_json Text) registered in `models/__init__.py`; ORM smoke verified.

#### T-10: Migration 0007
- **Description**: Create `backend/alembic/versions/0007_probability_tables.py` — upgrade creates `prob_snapshots` + `prob_values` + 3 indexes (`ix_psnap_lottery_model_status`, `ix_pval_snapshot_id`, `ix_pval_subject`); downgrade drops ONLY `prob_*` (Core/stat_*/feature_* untouched); `down_revision="0006_feature_tables"`. Extend `tests/test_migrations.py`.
- **Requirements**: PES-09 · **Design**: Migration
- **Files**: `backend/alembic/versions/0007_probability_tables.py`, `backend/tests/test_migrations.py`
- **Dependencies**: T-09
- **Acceptance**: upgrade head; downgrade drops only prob; Core/stat_*/feature_* tables still present.
- **Est. LOC**: 90
- **Status**: [x] Done — leaf on 0006; 3 indexes (PES-09 names); 2 new migration tests (upgrade integrity + downgrade-only-prob); full suite 315 passed, 1 skipped.

### PR2b: Store + Service + Adapters

#### T-11: snapshot_store + tests
- **Description**: Create `probability/snapshot_store.py` — single prob-store owner (D-A3): get_active, find_by_fingerprint, next_version, create (active+locked), retire_old_active, mark_failed, ordered bulk-insert values, values_for_snapshot(model/subject/last). Write `tests/probability/test_snapshot_store.py`.
- **Requirements**: PES-07 · **Design**: Snapshot Store & Service, D-A3
- **Files**: `probability/snapshot_store.py`, `tests/probability/test_snapshot_store.py`
- **Dependencies**: T-10
- **Acceptance**: lifecycle active→retired in one tx; failed header never active/partial; ordered bulk insert deterministic.
- **Est. LOC**: 120

#### T-12: ProbabilityService
- **Description**: Create `services/probability_service.py` — orchestration: resolve lottery; provider adapters (D2/D5 — never repo internals); registry execute over registered methods; fingerprint + checksum; persist header+values same tx, retire old active; map errors → `failed`; idempotent incremental (same fingerprint → existing) vs forced full new version; empty draws → draws_from=0, draws_to=0; reads from `prob_*` only, never precompute. Write service unit tests.
- **Requirements**: PES-02, PES-04, PES-07, PES-08, PES-11 · **Design**: Snapshot Store & Service, Traceability
- **Files**: `services/probability_service.py`
- **Dependencies**: T-03..08, T-11
- **Acceptance**: unit tests — deterministic generate, idempotent incremental, replace retires, failure → failed, empty-DB header 0..0.
- **Est. LOC**: 150

#### T-13: Service-seam adapters + import gate
- **Description**: Add private adapters in `probability_service.py` wrapping `statistics_service.read_*` / `feature_engine_service.read_*`; concrete-module grep gate: `probability/` + service import no `statistics`/`feature_engineering` internals.
- **Requirements**: PES-06 · **Design**: Providers — Adapter
- **Files**: `services/probability_service.py` (+ private adapters)
- **Dependencies**: T-12
- **Acceptance**: grep gate clean; adapters read-only contract test within T-12 suite.
- **Est. LOC**: 30

### PR3a: Schemas + API

#### T-14: Pydantic schemas
- **Description**: Create `schemas/probability.py` — `GenerateRequest(lottery_code, model_set, scope)`, `GenerateSnapshot`, `ProbabilityRow`, `ProbabilityList` (mirror `schemas/feature_engine.py`); envelope reuse.
- **Requirements**: PES-08 · **Design**: API Routes
- **Files**: `backend/src/backend/app/schemas/probability.py`
- **Dependencies**: T-12
- **Acceptance**: pydantic v2 models compile; envelope schema valid.
- **Est. LOC**: 60

#### T-15: API route + api tests
- **Description**: Create `api/v1/probability.py` — POST `/probability/generate` (200/201 idempotent), GET `/probability/{code}/probabilities` + per-model grid; mount in `api/v1/router.py`; missing snapshot → 404; reads never precompute. Write `tests/api/test_probability_api.py`.
- **Requirements**: PES-08 · **Design**: API Routes
- **Files**: `api/v1/probability.py`, `api/v1/router.py`, `tests/api/test_probability_api.py`
- **Dependencies**: T-14
- **Acceptance**: api tests — generate 201/200, GET 404 no-precompute, model/subject filters.
- **Est. LOC**: 120

### PR3b: CLI + E2E

#### T-16: CLI commands
- **Description**: Extend `cli.py` — `lip probability generate --lottery X [--scope]` / `lip probability rebuild --lottery X`; print snapshot JSON; argparse only, no scheduler/hook. Mirror `_cmd_feature_generate` pattern.
- **Requirements**: PES-08 · **Design**: CLI
- **Files**: `backend/src/backend/app/cli.py`
- **Dependencies**: T-12
- **Acceptance**: CLI/API parity; prints snapshot header JSON.
- **Est. LOC**: 40

#### T-17: E2E tests
- **Description**: Write `tests/probability/test_probability_e2e.py` — fixture CSV → import → generate → GET reads; API/CLI parity; 404; empty-DB fixture (`draws_from=0..draws_to=0`, engine, no crash); snapshot lifecycle through surface; read-only gate (Core/stat_*/feature_* byte-identical after run).
- **Requirements**: PES-02, PES-11 · **Files**: `backend/tests/probability/test_probability_e2e.py`
- **Dependencies**: T-15, T-16
- **Acceptance**: e2e green on fixture DB; read-only FULL gate.
- **Est. LOC**: 130

### PR4: Chores / Docs

#### T-18: Docs refresh
- **Description**: Refresh `README.md` + `PROJECT_STATUS.md` — probability section, CLI (`lip probability generate|rebuild`) / API (`GET /probability/{code}/probabilities`) examples, determinism-gate note.
- **Requirements**: C5 · **Files**: `README.md`, `PROJECT_STATUS.md`
- **Dependencies**: T-17
- **Acceptance**: docs state `lip probability` + `GET /probability/…`, Fase 5 marked complete.
- **Est. LOC**: 80

#### T-19: Final gates
- **Description**: Record full results — `backend/.venv/bin/pytest -q`; ruff `check .`; migration up/down; 7 methods + conditional univariate only; no scheduler in code.
- **Files**: none · **Dependencies**: T-18
- **Acceptance**: final gate results recorded.
- **Est. LOC**: 0

## Mandatory Gates

- **Byte-identical determinism** incl. Monte Carlo (`n_simulations` change ⇒ new seed/run, PES-05) — T-04, T-06
- **Persistence confined to `prob_*`** — real run never writes Core/stat_*/feature_* (PES-02) — T-11/T-12 write-path + T-17 read-only gate
- **Lifecycle** active|retired|failed, one active per (lottery, model_set); failed never active/partial (PES-07) — T-11/T-12
- **Idempotent writes** — incremental finds by fingerprint; full always bumps (PES-04) — T-12
- **GET never precomputes** — reads from stored `prob_*`; missing snapshot ⇒ 404 `SNAPSHOT_NOT_FOUND` (PES-08) — T-12/T-15
- **Migration reversible** — 0007 downgrade drops ONLY prob_* (PES-09) — T-10
- **Empty DB acceptance** — draws_from=0..draws_to=0, no crash (PES-11) — T-12/T-17
- **7 canonical methods registered** (PM-01..07) + **conditional = univariate only** (never joint) — T-04/T-07

## Risks & Decisions Needed

- **Risk low now**: the 4-PR plan (410-580 LOC each) split into 7 PRs; every PR ≤390 LOC — no `size:exception` needed; `Decision needed before apply: No`.
- PR1b (engine + its fixtures, 390) is the largest chunk; if the engine's Decimal/MC detail overruns, split T-04 into its own PR (PR1c) before review — still within stacked-to-main.
- Out-of-scope guard: no NumPy/SciPy; no prediction/pairwise conditional; no scheduler (PES-08).

## Suggested Work Units

| Unit | Goal | Likely PR | Focused test command | Runtime harness | Rollback boundary |
|------|------|-----------|----------------------|-----------------|-------------------|
| 1 | Foundation: seam, fingerprint, determinism, registry, providers | PR1a | `backend/.venv/bin/pytest backend/tests/probability/test_determinism.py backend/tests/probability/test_providers.py -q` | N/A — seam/providers, no DB seam; no real runtime until engine exists | Delete `probability/*` (non-engine) + their tests; no tables touched |
| 2 | Engine puro + fixtures (RED→GREEN) + engine-method seam | PR1b | `backend/.venv/bin/pytest backend/tests/probability/test_engine.py -q` | `python -c "from backend.app.probability import engine"` smoke + ref fixtures (PM-01..07) | Delete `engine.py` + `test_engine.py`; no DB |
| 3 | `prob_*` models + migration 0007 | PR2a | `backend/.venv/bin/pytest backend/tests/test_migrations.py -q` | `alembic upgrade head && alembic downgrade -1` on a scratch DB | Downgrade 0007 drops only prob_* tables |
| 4 | snapshot_store + ProbabilityService + adapters | PR2b | `backend/.venv/bin/pytest backend/tests/probability/test_snapshot_store.py -q` | `lip statistics generate --lottery X` precon commands to produce draws, then store keep/retire/failed scenarios | Revert store + service; Core/stat_*/feature_* untouched |
| 5 | Reading schemas + API | PR3a | `backend/.venv/bin/pytest backend/tests/api/test_probability_api.py -q` | fastapi TestClient — tableless 404, 200/201 | Drop router mount + revert schemas + route |
| 6 | CLI + E2E | PR3b | `backend/.venv/bin/pytest backend/tests/probability/test_probability_e2e.py -q` | fixture CSV → `lip probability generate|rebuild` on fixture DB; read-only FULL gate | Revert `cli.py` diff + test file |
| 7 | Docs chores + final gates | PR4 | `backend/.venv/bin/pytest -q && backend/.venv/bin/ruff check backend` | same runtime scenario as PR3b | Revert doc edits only |