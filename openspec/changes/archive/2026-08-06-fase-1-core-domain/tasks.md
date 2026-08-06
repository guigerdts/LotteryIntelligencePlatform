# Tasks: Fase 1 Core Domain

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~2500–3200 across 5 PRs |
| 400-line budget risk | High |
| Chained PRs recommended | Yes |
| Suggested split | PR-1 → PR-2 → PR-3 → PR-4 → PR-5 |
| Delivery strategy | ask-on-risk → resolved: chained (user-confirmed) |
| Chain strategy | stacked-to-main |

Decision needed before apply: No
Chained PRs recommended: Yes
Chain strategy: stacked-to-main
400-line budget risk: High

Note: no git remote configured — PR push/creation deferred until a remote exists; each slice ships as work-unit commits mapping 1:1 to one PR (stacked-to-main).

### Work Units

| Unit | Goal | PR | Focused test command | Runtime harness | Rollback boundary |
|------|------|----|----------------------|-----------------|-------------------|
| 1 | alembic + models + migration | PR-1 | `uv run pytest tests/test_migrations.py -q` | `alembic upgrade head` → `downgrade base` → `upgrade head` on empty base | `alembic downgrade base`; delete `backend/alembic/` + models |
| 2 | repositories + integrity | PR-2 | `uv run pytest tests/test_integrity.py -q` | repo calls on tmp SQLite session | revert repo files; schema stays green |
| 3 | services + rules | PR-3 | `uv run pytest tests/test_services.py -q` | service calls on tmp SQLite session | revert service files; repos stay green |
| 4 | API CRUD + errors | PR-4 | `uv run pytest tests/test_crud_lotteries.py tests/test_crud_draws.py -q` | `uv run pytest -q` full suite via TestClient | revert `api/v1` + `schemas/`; services stay green |
| 5 | indexes + smoke + docs | PR-5 | `uv run pytest tests/test_dialect_compat.py -q` | full suite; PG dialect smoke (CI-gated, real PG) | `alembic downgrade 0001`; revert docs |

## Gates (every PR must pass ALL G1–G7)

- G1 `uv run ruff check .` + `uv run ruff format --check .` clean (line-length 100)
- G2 `uv run pytest -q` green (incl. 5 Fase 0 tests; `/health` unchanged)
- G3 `alembic upgrade head` on empty base succeeds
- G4 `alembic downgrade` then re-upgrade succeed (idempotent forward/back)
- G5 no regression vs Fase 0
- G6 SQLite + PostgreSQL portable ops — no dialect-specific DDL
- G7 self-contained PR: compilable, testable, no deferred debt within PR

## PR Dependency Matrix

| PR | Delivers | Blocks | Enables |
|----|----------|--------|---------|
| PR-1 | `alembic` dep; `backend/alembic/` (env.py→Base.metadata, batch_mode); 6 models + CD-01..05 constraints; `0001_initial_core_domain.py`; migration tests | PR-2 repos, PR-5 indexes (need schema) | PR-2 compiles vs real schema; F2 natural key `UNIQUE(lottery_id,draw_number)` |
| PR-2 | `BaseRepository[T]` + per-entity repos over DI Session; get_by_natural_key, upsert_draw (dialect-isolated), get_with_numbers; IntegrityError→typed errors; integrity tests | PR-3 services | PR-3 use cases compose on repo primitives |
| PR-3 | draw_service (atomic bundle, soft-delete/restore, is_deleted exclusion); dataset_service (create+compose+LOCK, DATASET_LOCKED, new version); error→envelope codes; service tests | PR-4 API | PR-4 thin HTTP layer over use cases |
| PR-4 | schemas (lottery/draw/dataset); lotteries+draws routers under `/api/v1`; envelope + error handlers 422/409/404; CRUD tests | PR-5 smoke | PR-5 end-to-end dialect smoke + accurate docs |
| PR-5 | `0002_performance_indexes.py`; N+1 loading strategies; dialect smoke test; docs (init→upgrade→boot); full gates | — terminal | Fase 2 importer contract complete |

## PR-1: Alembic + Models + Migration

- [x] P1-01 Add `alembic` to `backend/pyproject.toml`; run `uv lock && uv sync`
- [x] P1-02 Create `backend/alembic/` — `alembic.ini`, `env.py` (target_metadata = `Base.metadata` from models package, `render_as_batch=True`, engine from `settings.database_url`), `script.py.mako`
- [x] P1-03 Create `backend/src/backend/app/models/lottery.py` — CD-01 columns (UNIQUE code, country String(2), nullable super range), CHECKs, tz-aware UTC created_at
- [x] P1-04 Create `backend/src/backend/app/models/draw.py` — UNIQUE(lottery_id,draw_number), Date draw_date, Numeric(18,2) nullable jackpot, is_deleted. **NO performance indexes here** (FK columns WITHOUT index=True; `(lottery_id, draw_date)` index deferred to 0002 per user rule)
- [x] P1-05 Create `models/draw_number.py` + `models/super_number.py` — UNIQUE(draw_id,position), UNIQUE(draw_id,number), UNIQUE(draw_id)
- [x] P1-06 Create `models/dataset.py` + `models/dataset_draw.py` — UNIQUE(version), UNIQUE(dataset_id,draw_id), metadata columns
- [x] P1-07 Update `models/__init__.py` re-exports (alembic target_metadata source)
- [x] P1-08 Write `alembic/versions/0001_initial_core_domain.py` — 6 tables in dependency order, downgrade reversed, portable ops only. **0001 creates ONLY PK/FK/UNIQUE/CHECK + constraint-implied indexes; NO performance indexes** (user rule: 0002 owns them)
- [x] P1-09 Create `tests/test_migrations.py` — zero tables pre-upgrade; upgrade head → 6 tables + constraints; downgrade base drops all
- [x] P1-10 Run gates G1–G4, G6, G7

## PR-2: Repositories + Transactions + Integrity

- [x] P2-01 Create `repositories/base_repository.py` — generic `BaseRepository(ModelT)` CRUD over DI Session
- [x] P2-02 Create lottery/draw/draw_number/super_number/dataset/dataset_draw repositories; draw: get_by_natural_key, get_with_numbers, list_draws, upsert_draw (dialect-isolated)
- [x] P2-03 Map IntegrityError→DuplicateError/ReferentialError typed domain errors in repo layer
- [x] P2-04 Create `tests/test_integrity.py` — DB rejects dup draw, dup number, 2nd super, dup code, FK RESTRICT delete
- [x] P2-05 Run gates G1, G2, G6, G7

## PR-3: Domain Services + Business Rules

- [x] P3-01 Create `services/draw_service.py` — create_draw_bundle (draw+numbers+super, one tx), soft_delete/restore, default is_deleted exclusion
- [x] P3-02 Create `services/dataset_service.py` — create + composition + LOCK; DATASET_LOCKED immutability guard; new version on change
- [x] P3-03 Map errors→envelope codes: DUPLICATE_RESOURCE, REFERENTIAL_CONSTRAINT, DATASET_LOCKED, RESOURCE_SOFT_DELETED
- [x] P3-04 Create `tests/test_services.py` — unit (mocked session) + integration: locked-update rejected, new version created, restore keeps children, soft-deleted excluded
- [x] P3-05 Run gates G1, G2, G6, G7

## PR-4: API CRUD + Error Handling + Validations

- [x] P4-01 Create `schemas/lottery.py`, `schemas/draw.py`, `schemas/dataset.py` (Create/Update/Read)
- [x] P4-02 Create `api/v1/lotteries.py` — GET/POST/PUT/DELETE per API_SPEC §3
- [x] P4-03 Create `api/v1/draws.py` — GET /draws (pagination, `?lottery=`, date filters), GET /draws/{id}; `/latest|import|upload` and dataset CRUD excluded
- [x] P4-04 Mount routers in `api/v1/router.py`; error handlers map domain errors→codes+HTTP 422/409/404, envelope REQ-02
- [x] P4-05 Create `tests/test_crud_lotteries.py` + `tests/test_crud_draws.py` — dup→409, FK→409, 404 envelope, `?lottery=` filter, no business logic in API
- [x] P4-06 Run gates G1, G2, G5, G7

## PR-5: Indexes + Optimization + Dialect Smoke + Docs

- [x] P5-01 Write `alembic/versions/0002_performance_indexes.py` — ix_draw_lottery_date, ix_draw_lottery_id, ix_draw_numbers_draw_id, ix_dataset_draws_draw_id (portable, batch_mode). **0002 MUST be functionally optional**: verified by running the FULL suite at 0001-only (`LIP_TEST_MIGRATION_TARGET=0001_initial_core_domain`) — green, app works without indexes
- [x] P5-02 Wire N+1-avoidance loading in repos — already wired in PR-2 (selectin/contains_eager in draw_repository; batch IN in dataset_draw_repository); re-proven by the V5 SELECT-counter tests (get_with_numbers=3, list_draws=3, draws_for_dataset=2, child/page-size independent)
- [x] P5-03 Create `tests/test_dialect_compat.py` — identical migrations + repo/service/API smoke on SQLite (always) and PostgreSQL (CI-gated; skips cleanly without TEST_POSTGRES_URL/DATABASE_URL_PG or psycopg); optional `dialect-pg` extra adds psycopg[binary]
- [x] P5-04 Update README + main.py + init_db.sh docs — ordering init_db → `alembic upgrade head` → boot, alembic sole owner, upgrade/downgrade, fresh-install bootstrap
- [x] P5-05 Run ALL gates G1–G7; no-debt review — PASSED (ruff, format, 97 pytest green +1 PG skip, alembic base→0001→0002→down→re-up cycle, portable-ops review, no regression)
