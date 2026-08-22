# Tasks: F13 — Intelligent Generator

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | 650–800 (original estimate — see documentary note below) |
| 400-line budget risk | High |
| Chained PRs recommended | Yes |
| Suggested split | PR 1 (S1) → PR 2a (allocation+validation) → PR 2b (sampling) → PR 2c (snapshot_store) → PR 3a (identity) → PR 3b (generate) → PR 3b-2 (reads/lifecycle) → PR 3c (API) → PR 3d (CLI) |
| Delivery strategy | ask-on-risk |
| Chain strategy | stacked-to-main |

**Documentary note (2026-08-12, post-DRY)**: "Estimated changed lines 650–800" is the ORIGINAL pre-implementation estimate used to plan the split. Real observed sizes are HIGHER: S1 ≈ 424 real lines (PR1, accepted as within the approximate budget), S2 total ≈ 1004 real lines across PR2a (~298) + PR2b (~233) + PR2c (~435 after DRY, down from 506). The 5-way chain strategy remains in force: PR1 → PR2a → PR2b → PR2c → PR3, stacked-to-main. The ~400-line budget is APPROXIMATE; PR1 already established ~424 real lines as acceptable. NO size:exception is used. PR2c target after DRY: 435 real lines (158 impl + 277 tests), −71 from the pre-DRY 506.

**Documentary note (2026-08-13, S3 re-segmentation)**: S3 (Surface) was originally planned as a single PR3 (T-GEN-018..025). A full S3 audit measured the real implementation at 1874 lines (post-DRY, −62 from 1936): gen_service 507, schemas 106, api 99, router 2, cli 145, tests 1021 — far above the ~400 budget with no honest DRY left. Architecture review (GenService = composition root in repo norm: probability_service 538, meta_service 480) concluded the service must NOT be split. The ONLY clean extraction with repo precedent is identity (GEN-008/009) into `generators/identity.py` (probability/meta delegate fingerprint+seed to modules; GenService was the outlier inlining it). Tests split at the single use-case boundary: generate (TestGenerate + TestGenerateErrors) vs reads/lifecycle (TestGetCombinations + TestUpdateSnapshot + TestGetSnapshots) — verbatim moves, shared conftest, no weakened assertions. User-authorized topology (2026-08-13): S3a (identity) → S3b (generate) → S3b-2 (reads/lifecycle tests) → S3c (API) → S3d (CLI), stacked-to-main. Chain becomes PR1 → PR2a → PR2b → PR2c → PR3a → PR3b → PR3b-2 → PR3c → PR3d. NO size:exception. Estimated real sizes: S3a ~95, S3b ~771 (composition-root cost), S3b-2 ~104, S3c ~583, S3d ~373.

Decision needed before apply: Yes
Chained PRs recommended: Yes
Chain strategy: stacked-to-main
400-line budget risk: High
Delivery decisions (user-authorized 2026-08-11): split into 3 chained PRs = PR1(S1) → PR2(S2) → PR3(S3), each <~400 lines; NO size:exception; stacked-to-main (each PR merges to main in order); S1→S2→S3 strictly; no feature/tracker branch; each PR independently reviewable and revertible.
S2 re-slicing (user-authorized 2026-08-12): PR2 splits into PR2a → PR2b → PR2c because S2 totals 1037 lines — snapshot_store alone is 506 (158 impl + 348 tests) and cannot be split without an artificial unit; test DRY (fixtures consolidation) targets ~406-420. Chain becomes PR1 → PR2a → PR2b → PR2c → PR3. NO size:exception; stacked-to-main preserved; local commits already segmented per module (no git surgery needed).

### PR Plan (user-authorized)

| PR | Scope | Merge target | Depends on | Rollback |
|----|-------|-------------|------------|----------|
| PR1 | S1 Foundation (T-GEN-001..009) | main | — | `alembic downgrade -1` drops gen_* |
| PR2a | S2a Allocation + Validation (T-GEN-010..013) | main | PR1 | Remove allocation.py + validation.py + their tests |
| PR2b | S2b Sampling (T-GEN-014..015) | main | PR2a | Remove sampling.py + its tests |
| PR2c | S2c Snapshot Store (T-GEN-016..017) | main | PR2b | Remove snapshot_store.py + its tests (incl. conftest if added) |
| PR3a | S3a Identity (T-GEN-018a) | main | PR2c | Remove generators/identity.py + tests/gen/test_identity.py |
| PR3b | S3b Generate use case (T-GEN-018, T-GEN-023) + shared conftest | main | PR3a | Remove gen_service.py + tests/gen/conftest.py + tests/gen/test_gen_generate.py |
| PR3b-2 | S3b-2 Reads/Lifecycle tests (T-GEN-023a) | main | PR3b | Remove tests/gen/test_gen_reads.py |
| PR3c | S3c API surface (T-GEN-019..021, T-GEN-024) | main | PR3b | Remove schemas/gen.py + api/v1/gen.py + router.py addition + test_gen_schemas.py + test_gen_api.py |
| PR3d | S3d CLI surface (T-GEN-022, T-GEN-025) | main | PR3b | Remove cli.py gen additions + test_gen_cli.py |

**Required skill for sdd-apply (resolved via registry)**: `chained-pr` at `/root/.agents/skills/chained-pr/SKILL.md` — must be loaded and followed before planning or creating any PR.

### Suggested Work Units

| Unit | Goal | Likely PR | Focused test command | Runtime harness | Rollback boundary |
|------|------|-----------|----------------------|-----------------|-------------------|
| S1 | Foundation: migration + models + types + errors + version + package seam | PR 1 | `backend/.venv/bin/pytest tests/gen/test_types.py -v` | N/A — unit tests only | Remove `generators/types.py`, `generators/version.py`, `generators/__init__.py`, `models/gen_snapshot.py`, `models/gen_combination.py`, migration 0015 |
| S2a | Allocation + Validation (T-GEN-010..013) | PR 2a | `backend/.venv/bin/pytest tests/gen/test_allocation.py tests/gen/test_validation.py -v` | N/A — unit tests only | Remove `generators/allocation.py`, `generators/validation.py`, `tests/gen/test_allocation.py`, `tests/gen/test_validation.py` |
| S2b | Sampling (T-GEN-014..015) | PR 2b | `backend/.venv/bin/pytest tests/gen/test_sampling.py -v` | N/A — unit tests only | Remove `generators/sampling.py`, `tests/gen/test_sampling.py` |
| S2c | Snapshot Store (T-GEN-016..017) | PR 2c | `backend/.venv/bin/pytest tests/gen/test_snapshot_store.py -v` | N/A — unit tests only | Remove `generators/snapshot_store.py`, `tests/gen/test_snapshot_store.py`, shared `tests/gen/conftest.py` (if added for DRY) |
| S3a | Identity: `generators/identity.py` (GEN-008/009 fingerprint + seed, delegates to `_canonical_json`/`derive_seed` like probability/meta) | PR 3a | `backend/.venv/bin/pytest tests/gen/test_identity.py -v` | N/A — unit tests only | Remove `generators/identity.py`, `tests/gen/test_identity.py` |
| S3b | Generate use case: `gen_service.py` (without identity) + shared conftest + generate/errors tests | PR 3b | `backend/.venv/bin/pytest tests/gen/test_gen_generate.py -v` | `lip gen generate --lottery-id 1` (after S3c/S3d) | Remove `services/gen_service.py`, `tests/gen/conftest.py`, `tests/gen/test_gen_generate.py` |
| S3b-2 | Reads/lifecycle tests: `test_gen_reads.py` (TestGetCombinations + TestUpdateSnapshot + TestGetSnapshots) | PR 3b-2 | `backend/.venv/bin/pytest tests/gen/test_gen_reads.py -v` | N/A — unit tests only | Remove `tests/gen/test_gen_reads.py` |
| S3c | API surface: schemas + router + API tests | PR 3c | `backend/.venv/bin/pytest tests/gen/test_gen_schemas.py tests/gen/test_gen_api.py -v` | `lip gen generate --lottery-id 1` | Remove `schemas/gen.py`, `api/v1/gen.py`, `api/v1/router.py` addition, `test_gen_schemas.py`, `test_gen_api.py` |
| S3d | CLI surface: `lip gen` subcommands + CLI tests | PR 3d | `backend/.venv/bin/pytest tests/gen/test_gen_cli.py -v` | `lip gen generate --lottery-id 1` | Remove `cli.py` gen additions, `test_gen_cli.py` |

## Phase 1: Foundation — Migration + Models + Types + Errors + Seam

- [x] T-GEN-001 | Create `alembic/versions/0015_gen_tables.py`: tables `gen_snapshots` (id, lottery_id FK→lottery RESTRICT, selection_id FK→meta_selections RESTRICT, version, status CHECK active|retired|failed, fingerprint, config_json nullable, created_at) and `gen_combinations` (id, snapshot_id FK→gen_snapshots RESTRICT, position, numbers Text JSON, super_number nullable, score nullable, created_at). Unique `(lottery_id, selection_id, fingerprint)`. Indexes `ix_gen_snapshots_lottery_selection`, `ix_gen_combinations_snapshot`. Downgrade drops indexes + tables in reverse FK order. Template: `0014_meta_tables.py`. | `alembic/versions/0015_gen_tables.py` | T-GEN-001 | Test: `alembic upgrade 0015` creates 2 tables; `alembic downgrade -1` drops only gen_* | ~80 impl |
- [x] T-GEN-002 | Create `models/gen_snapshot.py` (GenSnapshot ORM: 8 cols, CHECK status, unique scope) and `models/gen_combination.py` (GenCombination ORM: 7 cols, nullable score). Mirror snapshot pattern from `models/meta_selection.py`. | `models/gen_snapshot.py`, `models/gen_combination.py` | T-GEN-001 | Test: models instantiate, `__table_args__` has correct constraints, FK RESTRICT | ~50 impl |
- [x] T-GEN-003 | Modify `models/__init__.py` to re-export `GenSnapshot`, `GenCombination` for alembic `target_metadata`. | `models/__init__.py` | T-GEN-002 | Test: `from backend.app.models import GenSnapshot` succeeds | ~3 impl |
- [x] T-GEN-004 | Create `generators/types.py`: `GenerationConfig` (lottery_id, count, seed, selection_id), `Combination` (position, numbers, super_number), `Allocation` (entry_index, count) frozen dataclasses. | `generators/types.py` | None | Test: dataclass creation, immutability | ~30 impl |
- [x] T-GEN-005 | Create `generators/version.py`: `GENERATOR_VERSION = "1.0.0"`. | `generators/version.py` | None | Test: constant equals `"1.0.0"` | ~3 impl |
- [x] T-GEN-006 | Create `generators/__init__.py` package seam — docstring only. | `generators/__init__.py` | None | Test: `import backend.app.generators` succeeds | ~3 impl |
- [x] T-GEN-007 | Modify `services/errors.py`: add `GenServiceError(ServiceError)` with 7 codes as class constants (`GEN_NO_SELECTION`→404, `GEN_NO_DISTRIBUTION`→404, `GEN_LOTTERY_NOT_FOUND`→404, `GEN_COUNT_INVALID`→422, `GEN_SNAPSHOT_NOT_FOUND`→404, `GEN_DUPLICATE_SNAPSHOT`→409, `GEN_SPACE_EXHAUSTED`→422). `__init__(code, message)`. | `services/errors.py` | None | Test: `GenServiceError.__mro__` includes `ServiceError`; each code correct | ~25 impl |
- [x] T-GEN-008 | Modify `api/errors.py`: add 7 entries to `_CODE_TO_STATUS` for GenServiceError codes. | `api/errors.py` | T-GEN-007 | Test: each code maps to correct HTTP status | ~8 impl |
- [x] T-GEN-009 | Write RED+GREEN tests for types, version, errors: dataclass creation, immutability, version constant, error code mapping, MRO. | `tests/gen/__init__.py`, `tests/gen/test_types.py` | T-GEN-004, T-GEN-005, T-GEN-007 | All type/version/error tests pass via `pytest tests/gen/test_types.py` | ~40 test |

## Phase 2: Core Logic — Allocation + Validation + Sampling + Snapshot Store

> Delivery grouping (2026-08-12): PR2a = T-GEN-010..013 (allocation+validation), PR2b = T-GEN-014..015 (sampling), PR2c = T-GEN-016..017 (snapshot_store). Each sub-PR is a work unit commit range; tasks themselves unchanged.

- [x] T-GEN-010 | Create `generators/allocation.py`: `allocate_count(entries, count)` with micro-unit integer arithmetic (`SCORE_SCALE=10**6`). Step 1: scale scores to int micros. Step 2: floor division `micros * count // total_micros`. Step 3: distribute remainder by desc score rank. Assert `Σcᵢ == count`. | `generators/allocation.py` | T-GEN-004 | Test: `allocate_count` pure function | ~50 impl |
- [x] T-GEN-011 | **RED**: Write `tests/gen/test_allocation.py` with parametrized precision regression tests: `([0.7, 0.3], 90, [63, 27])` — **mandatory case**: verifies `round(0.7*1e6)*90//1000000 == 63` (not 62). Plus `([0.5,0.3,0.2], 10, [5,3,2])`, `([0.34,0.33,0.33], 10, [4,3,3])`, `([0.999999,0.000001], 100, [100,0])`, `([0.333,0.333,0.334], 100, [33,33,34])`. **Assertion**: `sum == count` AND `sorted(allocations, reverse=True) == sorted(expected, reverse=True)` for every case. The `[0.7, 0.3], 90` case MUST assert `allocations[0] == 63` specifically. | `tests/gen/test_allocation.py` | T-GEN-010 | Tests RED then GREEN after T-GEN-010 impl | ~50 test |
- [x] T-GEN-012 | Create `generators/validation.py`: `validate_combination(numbers, super_number, lottery_config)` returns bool. Checks: distinct numbers in `[min_number, max_number]`, sorted, `super_number` in range. | `generators/validation.py` | T-GEN-004 | Test: pure function | ~30 impl |
- [x] T-GEN-013 | Write `tests/gen/test_validation.py`: valid combo → True; unsorted → False; out-of-range → False; duplicate → False; super_number out-of-range → False. Parametrized. | `tests/gen/test_validation.py` | T-GEN-012 | All validation tests pass | ~40 test |
- [x] T-GEN-014 | Create `generators/sampling.py`: `sample_combinations(rng, distributions, count, lottery_config, max_attempts=1000)`. Weighted sampling per entry using `rng.choices`. Resampling loop with duplicate rejection `set[frozenset[tuple[int]]]`. On MAX_ATTEMPTS → raise `GenServiceError(GEN_SPACE_EXHAUSTED)`. Zero combos persisted on exhaustion. | `generators/sampling.py` | T-GEN-004, T-GEN-012, T-GEN-007 | Test: pure function (mock distributions) | ~60 impl |
- [x] T-GEN-015 | Write `tests/gen/test_sampling.py`: determinism (same seed → same output), duplicate rejection, MAX_ATTEMPTS exhaustion → `GEN_SPACE_EXHAUSTED`, valid combos respect lottery rules. | `tests/gen/test_sampling.py` | T-GEN-014 | All sampling tests pass | ~50 test |
- [x] T-GEN-016 | Create `generators/snapshot_store.py`: `GenSnapshotStore(db)` with `next_version(lottery_id, selection_id)`, `find_by_fingerprint(fp)`, `create_active_snapshot(...)`, `retire_active(lottery_id, selection_id)`, `get_snapshots(lottery_id)`, `get_combinations(snapshot_id)`. Atomic writes, lifecycle transitions, idempotency. | `generators/snapshot_store.py` | T-GEN-002 | Test: next_version monotonic; idempotent fingerprint; lifecycle active→retired; atomic write; lottery isolation | ~70 impl |
- [x] T-GEN-017 | Write `tests/gen/test_snapshot_store.py`: next_version monotonic, fingerprint idempotency (same → return existing), lifecycle active→retired, atomic write (rollback leaves DB clean), lottery isolation. SQLite test DB. | `tests/gen/test_snapshot_store.py` | T-GEN-016 | All snapshot_store tests pass | ~60 test |

## Phase 3: Surface — Service + API + CLI + Integration

> Delivery grouping (2026-08-13, S3 re-segmentation): PR3a = T-GEN-018a (identity), PR3b = T-GEN-018 + T-GEN-023 + shared conftest (generate use case), PR3b-2 = T-GEN-023a (reads/lifecycle tests), PR3c = T-GEN-019..021 + T-GEN-024 (API), PR3d = T-GEN-022 + T-GEN-025 (CLI). Tasks themselves unchanged; the only additions are T-GEN-018a (identity extraction, repo-precedent pattern) and T-GEN-023a (reads/lifecycle tests split at the use-case boundary).

- [ ] T-GEN-018a | Create `generators/identity.py`: `generation_seed(selection_fingerprint, lottery_id, count, version)` building `input_fingerprint = SHA-256(_canonical_json({selection_fingerprint, lottery_id, count, GENERATOR_VERSION}))` then delegating to `derive_seed(input_fingerprint, model_params={"lottery_id", "count"}, n_simulations=count)`; `snapshot_fingerprint(lottery_id, selection_id, count, seed, version)` via `_canonical_json({lottery_id, selection_id, count, seed, VERSION})` + SHA-256 (GEN-008/009, design §Determinism). Follows repo precedent: probability delegates to `probability/determinism.py` + `probability/fingerprint.py`; meta to `meta/ranking.py::compute_fingerprint`. GenService consumes these instead of inlining identity. | `generators/identity.py` | T-GEN-004 | Test: deterministic seed, fingerprint stability, no cross-lottery collision | ~45 impl |
- [ ] T-GEN-018 | Create `services/gen_service.py`: `GenService(db)` with `generate(lottery_id, count?, seed?, selection_id?)`, `get_combinations(lottery_id, snapshot_id?)`, `update_snapshot(lottery_id, snapshot_id, status)`, `get_snapshots(lottery_id)`. Pipeline: resolve selection → validate count → allocate → load F5 distributions → sample → persist. Error mapping to `GenServiceError`. Identity (GEN-008/009) consumed from `generators/identity.py` (T-GEN-018a), not inlined. | `services/gen_service.py` | T-GEN-018a, T-GEN-006..016, T-GEN-007 | Test: full generate workflow, idempotency, 404 paths, count validation 422, space exhausted 422 | ~90 impl |
- [ ] T-GEN-019 | Create `schemas/gen.py`: Pydantic v2 request/response (`GenerateRequest`, `GenerationResult`, `CombinationList`, `SnapshotUpdateRequest`, `SnapshotResult`, `SnapshotList`). | `schemas/gen.py` | None | Test: schema creation, validation, extra fields rejected | ~50 impl |
- [ ] T-GEN-020 | Create `api/v1/gen.py`: API router with 4 endpoints (POST /gen/generate, GET /gen/combinations, POST /gen/snapshot, GET /gen/snapshots). Standard envelope `{success, data|error, timestamp}`. | `api/v1/gen.py` | T-GEN-018, T-GEN-019 | Test: each endpoint returns correct status and payload; 404 for missing lottery | ~60 impl |
- [ ] T-GEN-021 | Modify `api/v1/router.py`: include `gen_router` with prefix `/gen`. | `api/v1/router.py` | T-GEN-020 | Test: `GET /gen/snapshots` route resolves | ~3 impl |
- [ ] T-GEN-022 | Modify `cli.py`: add `lip gen` subparser with 4 subcommands (`generate`, `combinations`, `snapshot`, `snapshots`). stdlib argparse. JSON output. | `cli.py` | T-GEN-018 | Test: `lip gen generate --lottery-id 1` outputs JSON; parity with API | ~50 impl |
- [ ] T-GEN-023 | Write `tests/gen/test_gen_generate.py`: full generate→get workflow, idempotency (same fingerprint returns existing), 404 GEN_NO_SELECTION, 404 GEN_NO_DISTRIBUTION, 422 GEN_COUNT_INVALID, 422 GEN_SPACE_EXHAUSTED, 409 GEN_DUPLICATE_SNAPSHOT, lottery isolation, version monotonicity. Classes TestGenerate + TestGenerateErrors (S3b). | `tests/gen/test_gen_generate.py` | T-GEN-018 | All service tests pass | ~80 test |
- [ ] T-GEN-023a | Write `tests/gen/test_gen_reads.py`: reads/lifecycle tests split at the use-case boundary (S3b-2): TestGetCombinations (active default, snapshot_id, unknown snapshot, no active, unknown lottery), TestUpdateSnapshot (retire, fail, activate→409, unknown), TestGetSnapshots (ordered list, empty→404). Verbatim move from the original single test_gen_service.py; shared conftest; assertions unchanged. | `tests/gen/test_gen_reads.py` | T-GEN-018, T-GEN-023 | All reads/lifecycle tests pass | ~104 test |
- [ ] T-GEN-024 | Write `tests/gen/test_gen_api.py`: 4 endpoints, error codes (404, 422, 409), envelope format, idempotent responses. FastAPI TestClient. | `tests/gen/test_gen_api.py` | T-GEN-020 | All API tests pass | ~60 test |
- [ ] T-GEN-025 | Write `tests/gen/test_gen_cli.py`: 4 commands, JSON output, parity with API. subprocess + JSON parse. | `tests/gen/test_gen_cli.py` | T-GEN-022 | All CLI tests pass | ~40 test |

## Traceability Matrix

| Requirement | Tasks | Test Scenarios | PR |
|-------------|-------|----------------|----|
| GEN-001 Pipeline | T-GEN-018,023 | selection→allocation→sample→persist, exactly count combos | PR3b |
| GEN-002 Count | T-GEN-018,023 | count=0→422, count>100→422, default=10 | PR3b |
| GEN-003 Selection | T-GEN-018,023 | no active selection→404, selection_id override | PR3b |
| GEN-004 Allocation | T-GEN-010,011 | precision regression [0.7,0.3]×90→[63,27], Σ=count, tie-break by rank | PR2a |
| GEN-005 Determinism | T-GEN-015,023 | same inputs→identical output, isolated_rng | PR2b/PR3b |
| GEN-006 Lottery rules | T-GEN-012,013,014,015 | distinct, sorted, super in range, resample invalid | PR2a/PR2b |
| GEN-007 Lifecycle | T-GEN-016,017,023,023a | active→retired, atomic, version monotonic | PR2c/PR3b/PR3b-2 |
| GEN-008 Fingerprint | T-GEN-016,017,023,018a | same→return existing, no new rows | PR2c/PR3a/PR3b |
| GEN-009 Seed | T-GEN-018a,018 | derive_seed SHA-256, optional override | PR3a/PR3b |
| GEN-010 API | T-GEN-020,021,024 | 4 endpoints, error codes, envelope | PR3c |
| GEN-011 CLI | T-GEN-022,025 | 4 commands, JSON output | PR3d |
| GEN-012 Persistence | T-GEN-001,002,003 | migration creates/rolls back 2 tables | PR1 |
| GEN-013 Errors | T-GEN-007,008,018,023 | 7 codes, correct HTTP status, space exhausted 422 | PR1/PR3b |
| GEN-014 No-distribution | T-GEN-018,023 | no F5→404, zero combos | PR3b |
| GEN-015 F5 boundary | T-GEN-014 | reuse only derive_seed/isolated_rng/_canonical_json | PR2b |
| GEN-016 F11/F12 boundary | T-GEN-018 | scores as weights only, no re-rank | PR3b |
| GEN-017 No eval MVP | T-GEN-018 | no evaluation logic | PR3b |
| GEN-018 No filters MVP | T-GEN-014,018 | no filtering | PR2b/PR3b |
| NFR-GEN-01 Determinism | T-GEN-009,011,015,018a | same inputs→identical seed and combos | PR1/PR2a/PR2b/PR3a |
| NFR-GEN-02 Correctness | T-GEN-011,023 | exactly count combinations | PR2a/PR3b |
| NFR-GEN-03 Performance | T-GEN-014,023 | bounded by max count=100 | PR2b/PR3b |
| NFR-GEN-04 Security | T-GEN-004,018 | inputs validated, no secrets | PR1/PR3b |
| NFR-GEN-05 Maintainability | T-GEN-006,014,018a | generators/ isolated, F5 boundary | PR1/PR2b/PR3a |
| NFR-GEN-06 Testability | T-GEN-009..025,018a,023a | strict TDD, pytest verifiable | all PRs |

## Key Learnings

1. Micro-unit arithmetic with SCORE_SCALE=10**6 eliminates float drift: `round(0.7*1e6)*90//1000000 == 63` exactly.
2. GEN_SPACE_EXHAUSTED(422) means zero combos persisted — no partial count, no warning fallback.
3. F5 boundary: generators/ reuses only derive_seed, isolated_rng, _canonical_json from probability.determinism and probability.fingerprint.
4. Snapshot lifecycle (active|retired|failed) with monotonic version per (lottery_id, selection_id) follows F12 precedent exactly.
5. Mandatory precision regression test [0.7, 0.3]×90→[63,27] catches float drift that [0.5,0.3,0.2]×10 does not.

---

**Ready for implementation (sdd-apply) via stacked-to-main PRs.**
