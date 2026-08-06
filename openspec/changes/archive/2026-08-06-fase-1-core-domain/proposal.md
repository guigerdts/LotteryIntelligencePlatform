# Proposal: Fase 1 Core Domain

## Intent
Give the Fase 0 backend a persisted, reproducible core domain: five entities (Lottery, Draw, DrawNumber, SuperNumber, Dataset) with a dialect-portable schema, alembic migrations, per-entity repositories, CRUD, and tests. Solves the schema void left by REQ-05 (SQLite bootstrap, no schema) and unblocks Fase 2 import, F4 features, F7 ML, F10 backtesting, F11 experiments. Reproducibility is a first-class contract: raw-only persistence, immutable versioned datasets, and persisted generation metadata.

## Scope

### In Scope
- SQLAlchemy 2.0 models for `lottery`, `draw`, `draw_numbers`, `super_number`, `datasets`, `dataset_draws`, subclassing `Base` (`repositories.base`), re-exported in `models/__init__.py` as alembic `target_metadata` source.
- Constraint set as validated: rules as `lottery` columns [D1]; SuperNumber 0..1 with `UNIQUE(draw_id)` [D2]; `UNIQUE(lottery_id, draw_number)` + index `(lottery_id, draw_date)` [D3]; `UNIQUE(draw_id, position)` + `UNIQUE(draw_id, number)`; dataset global `UNIQUE(version)` [D16]; FK RESTRICT delete semantics; tz-aware UTC timestamps [D4].
- Alembic setup: `backend/alembic/`, `env.py` → `Base.metadata`, `batch_mode` for SQLite, portable ops only; add `alembic` dependency.
- Repositories per entity over the DI `Session` (`get_db`), `Numeric(18,2)`/`Integer` nullable for jackpot/winners [D7].
- CRUD endpoints under `api/v1` per API_SPEC §3/§4 (Lottery, Draw) + Pydantic `schemas/`; envelope response (Fase 0 pattern). `/draws/latest`, `/draws/import`, `/draws/upload` are Fase 2 (no contract here).
- Tests: existing 5 Fase 0 + new model/migration/CRUD tests via TestClient.
- Dataset is immutable-once-created (`is_locked`/version mechanism) [D5], persisted with reproducible metadata (`checksum`, `created_at`, `lottery_id`, `filters`, `generator_version`), with model `dataset_draws` join [D6] and FK RESTRICT to keep referenced draws [D8].

### Out of Scope
- Data ingestion/import, duplicate detection, normalization, dataset versioning logic (Fase 2).
- Derived features → `feature_value` (F4) — F1 stores raw-only [D13].
- Engines (Statistics F3, Probability F5, ML F7, DL F8, Optimization F9, Backtest F10, Experiments F11, Generator F13), Dashboard (F14).
- Frontend slice; PostgreSQL swap (already config-only via `settings.database_url`).
- Dataset CRUD endpoints (M4: no `/datasets` contract in API_SPEC until AP is updated or chained API delta).
- App-level rule validation beyond model constraints (e.g. draw_number count vs `numbers_to_select` [C8] — noted, enforced in F2).

## Capabilities
Research source: `openspec/specs/` holds only `backend/spec.md` (REQ-01..08 Foundation).

### New Capabilities
- `core-domain`: the persisted entity/relationship contract — five core entities + `dataset_draws` join, portable constraints, timestamps, soft-delete + FK RESTRICT delete semantics, and the reproducibility contracts (immutability, raw-only, dataset metadata incl. filters + generator_version).

### Modified Capabilities
- `backend`: REQ-05 evolves from "no schema / SQLite bootstrap" to "migrations own the schema; `init_db` still creates the file"; Fase 1 routes, envelope CRUD, and extended repository/schema seams extend the Foundation domain.

## Approach
Models in `backend/src/backend/app/models/<entity>.py` (SQLAlchemy 2.0 `Mapped`/`mapped_column`, `DateTime(timezone=True)` + `server_default=func.now()`, `Numeric(18,2)`, `Enum(native_enum=False)` if any [D11]). Alembic `backend/alembic/` → `env.py` `target_metadata = Base.metadata`, autogenerate, `batch_mode` for SQLite DDL, portable ops, no PG-only types. Repositories wrap the DI `Session` (`base.SessionLocal`/`get_db`); generic `BaseRepository` optional in design. CRUD under `api/v1` per API_SPEC §3/§4 with `?lottery=<code>` app-lookup, envelope responses (REQ-02). Tests via `TestClient`.

## Affected Areas
| Area | Impact | Description |
|------|--------|-------------|
| `.config/` `backend/app/models/{lottery,draw,draw_number,super_number,dataset,dataset_draw}.py` | New | Core domain ORM models |
| `backend/alembic/` + `env.py`, migration(s) | New | Schema migrations owning `Base.metadata` |
| `backend/app/repositories/*_repository.py` | New | Per-entity CRUD over DI Session |
| `backend/app/schemas/*.py` | New | Pydantic Create/Update/Read + envelope |
| `backend/app/api/v1/{lotteries,draws}.py` + `router.py` | New / Modified | CRUD endpoints + mounting |
| `backend/pyproject.toml` / `uv.lock` | Modified | add `alembic` dependency |
| `backend/src/.../core/db.py` (`init_db`) | Modified | unchanged behavior; migrations own schema now |
| `openspec/specs/backend/spec.md` | Modified (delta) | REQ-05 scope shift (Foundation change) |
| `openspec/specs/core-domain/spec.md` | New | new capability spec |

## Cross-Phase Impact & Reproducibility
- **D5 immutability**: dataset snapshot can never change silently; any F7 (feature) / F10 (backtest) / F11 (experiment) run references a frozen dataset → result reproduction identical.
- **Dataset metadata** (`checksum`, `filters`, `generator_version`) makes every artifact fully reproducible: same `generator_version` + `filters` + raw set ⇒ same feature/backtest/experiment.
- **D13 raw-only** stores only official results in F1; derived ML inputs land in `feature_value` (F4) → no accidental leakage at source.
- **Soft-delete excluded by default**: `is_deleted` rows are excluded in every query but the row persists → audit trail intact (DS §6 "no eliminar sorteos"); FK RESTRICT on `dataset_draws → draw` blocks a referenced draw's deletion (dataset integrity).
- **Dedup [D3]** unique key ships in F1 migration → F2 duplicate detection + re-import idempotency guaranteed; protects statistics/ML from silent corruption.
- **REQ-05 portability**: portable columns only → SQLite↔PostgreSQL config-only swap preserved.

## Risks
| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Alembic vs `init_db` bootstrap conflict | Med | Migrations own schema; `init_db` only guarantees the file exists; document ordering in design |
| PG-only/SQLite-specific migration DDL breaks swap | Med | Review gate in design/verify; portable ops only |
| Wrong dataset/metadata model cascades to F7/F10 | Low | D5 immutability + metadata fields fixed in this proposal |
| 400-line review budget exceeded | Med | sdd-tasks to recommend chained PR slices |

## Rollback Plan
- DB is disposable in dev: `alembic downgrade base` (or delete `database/lip.db` via `init_db`) removes all F1 tables with zero data loss.
- Fail-fast per-revision migrations (`batch_mode`); on partial failure, `downgrade` to prior revision.
- Revert commit (git revert) restores F0 state; `init_db` still recreates the file. Fase 0 `create_app`/`/health` behavior unchanged.

## Dependencies
- Fase 0 (landed): `Base`, DI `engine`/`SessionLocal`/`get_db`, envelope, settings, TestClient pattern.
- `alembic` added to `backend/pyproject.toml` (not yet declared). sqlalchemy/pydantic/httpx already present.

## Success Criteria
- [ ] `uv run ruff check .` and `ruff format --check .` pass; pre-commit green.
- [ ] `pytest` green: existing 5 Fase 0 tests + new Fase 1 (model/constraint, migration-create, CRUD) tests.
- [ ] `alembic upgraded head` creates the F1 tables in `database/lip.db`.
- [ ] CRUD verified via TestClient (Lottery Create/Get/List/Update; Delete returning 409/RESTRICT with draws; Draw CRUD with constraint rejection).
- [ ] `uvicorn` boot serves `/health` 200 envelope.
- [ ] No PG-only or SQLite-only construct in migrations (config-only swap preserved).

## Boundaries / Decisions Recorded
- H1 → D1: lottery rules persisted as `lottery` columns (DB row ≠ code; "outside code" satisfied).
- H2 → D2: super_number 0..1 per draw `UNIQUE(draw_id)`.
- H3 → D3: `UNIQUE(lottery_id, draw_number)` + index `(lottery_id, draw_date)`.
- D5 adjusted: dataset immutable; closes auto-update. D8 adjusted: soft-delete for audit only; RESTRICT keeps referenced draws; default query excludes `is_deleted`.
- Added: `draw_numbers.position` (1..N) + `UNIQUE(draw_id, position)` + `UNIQUE(draw_id, number)`; dataset metadata (`checksum`, `created_at`, `lottery_id`, `filters`, `generator_version`).
- D4/D7/D9/D10/D11/D12/D13/D14/D15/D16/C1-C14 carry as validated (see exploration).

## Proposal question round
None required: all items user-validated (D1–D16 + amendments + additional requirements) — no blocker surfaced.

## Next
`sdd-spec`.