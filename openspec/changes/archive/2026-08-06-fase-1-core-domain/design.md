# Design: Fase 1 Core Domain

**Change**: `fase-1-core-domain` · **Store**: openspec · **Date**: 2026-08-06
**Inputs**: spec.md (REQ-05 MODIFIED, REQ-09 ADDED, CD-01..CD-08), proposal.md, exploration.md [D1]–[D16], Fase 0 seams, DATABASE_SCHEMA.md, API_SPECIFICATION §3/§4.

## Technical Approach

Persist the five core entities + `dataset_draws` join on the Fase 0 ORM seam (`repositories.base.Base`, DI `get_db`) with a dialect-portable schema owned solely by one alembic initial migration (REQ-09). Layered data flow keeps models structural-only, repositories owning all loading/idempotency, domain services owning use cases and error mapping, API owning the HTTP/envelope contract. Reproducibility contracts (raw-only, immutable datasets, persisted metadata) are enforced in the service layer over DB-level structural constraints (CD-06).

## Layer Responsibilities (User Req 1)

| Layer | Responsibility | Explicitly does NOT |
|---|---|---|
| **ORM models** (`models/*.py`) | Declare mapped columns, PK/FK, UNIQUE/CHECK/index constraints, relationships (for loading only); subclass `Base` | **No business logic, no validation rules, no computed behavior** — persistence/structural only |
| **Repositories** (`repositories/*.py`) | CRUD + queries over DI `Session`; own loading strategies (eager/joined/batch); map `IntegrityError`→domain exceptions; idempotent primitives (natural-key lookup, upsert) | No HTTP, no use-case orchestration |
| **Domain services** (`services/*.py`) | Use cases: create draw bundle (atomic), create/lock dataset, soft-delete/restore, code lookup; cross-entity invariants (CD-06); error→envelope-code mapping | No raw SQL, no request parsing |
| **API** (`api/v1/*.py` + `schemas/*.py`) | HTTP contract, Pydantic validation, envelope wrapping (REQ-02), status codes | No SQL, no business logic; never lazy-loads in loops |
| **Alembic** (`backend/alembic/`) | Sole schema owner (REQ-09); `env.py` → `Base.metadata`; portable ops only, `batch_mode` | No data seeding, no logic |

## Architecture Decisions

| Decision | Alternatives | Choice & Rationale |
|---|---|---|
| Business logic placement | Logic in models (fat models) | **Models structural-only** (Req 1); services own behavior → testable, portable, models stay a pure schema contract |
| Transaction scope | Per-statement autocommit | **One session transaction per use case**, committed by the service (Req 2); `get_db` rolls back on error |
| Loading strategy owner | API/services pick per query | **Repositories own eager/joined/batch loading** (Req 6); API receives loaded graphs |
| DB error mapping | Let `IntegrityError` bubble as 500 | **Repository catches and re-raises typed domain errors**; service maps to envelope codes (Req 5) |
| Dataset immutability | DB trigger / ORM event | **Domain-service guard** — DB triggers are dialect-specific (breaks REQ-05/09); app check + RESTRICT FKs are portable |
| Repository shape | One bespoke repo per entity | **Generic `BaseRepository` (CRUD) + entity-specific subclasses**; de-duplicates CRUD, keeps custom queries in subclasses |
| Import idempotency | App-only duplicate check | **DB `UNIQUE(lottery_id, draw_number)` natural key ships in F1** (CD-02/D3); repo exposes upsert/on-conflict primitives (Req 4) |
| Migration count | Per-table revisions | **Single initial revision** creating all 6 tables (fresh DB, alembic owns from base); downgrade drops in reverse dependency order |
| Draw soft-delete | Hard delete / no delete | **`is_deleted` flag + FK RESTRICT** (CD-05, D8/D9); default queries exclude; restore keeps children |
| Timestamps/money | naive datetimes, float jackpot | **tz-aware UTC `DateTime(timezone=True)`, `Numeric(18,2)` nullable** (D4/D7) |

## Data Flow

```
Client → api/v1 router → Pydantic schema → domain service (use case, tx)
   → repository (eager/batch load; maps IntegrityError) → Session → DB
alembic env.py → Base.metadata (models package) → migration → schema
```

### Sequence: draw + numbers + super_number creation (atomic, Req 2)

```
Service:create_draw_bundle(lottery_id, draw_number, numbers[], super?)
  ── begin session tx ──► repo.create_draw() → flush (UNIQUE(lottery_id,draw_number))
  ──► repo.add_numbers(draw.id, numbers)      (UNIQUE(draw_id,position|number))
  ──► repo.add_super_number(draw.id, value)   (UNIQUE(draw_id))
  ── commit ──► DB
  any IntegrityError ──► rollback → DUPLICATE_RESOURCE/REFERENTIAL_CONSTRAINT (409)
```

### Sequence: dataset composition + locking

```
Service:create_dataset(version, lottery_id, filters, draw_ids)
  ── begin tx ──► repo.datasets.create(version)   (UNIQUE(version))
  ──► repo.dataset_draws.add_many(dataset_id, draw_ids)  (UNIQUE(dataset_id,draw_id))
  ──► set is_locked=True, commit ──► DB
  locked dataset update attempt ──► service raises DATASET_LOCKED (409); DB untouched
```

### Sequence: soft-delete + restore

```
Service:soft_delete_draw(id) → repo.update(is_deleted=True) → commit
Service:restore_draw(id)     → repo.update(is_deleted=False) → commit
   children (draw_numbers, super_number) unchanged; FK RESTRICT keeps them (CD-05)
   DELETE /lotteries/{id} with draws → IntegrityError → rollback → 409 REFERENTIAL_CONSTRAINT
```

## Transaction Boundaries (User Req 2)

| Operation | Atomic unit (one session tx) | Rollback behavior |
|---|---|---|
| Create lottery | insert lottery | rollback on UNIQUE(code)/CHECK failure |
| **Create draw bundle** (draw + numbers + super_number) | insert draw, flush, insert all children, commit | any child constraint failure rolls back the whole draw |
| Update lottery (PUT) | update row | rollback on UNIQUE(code) conflict |
| Delete lottery | delete row | FK RESTRICT (`draw.lottery_id`) → rollback → 409 |
| Soft-delete / restore draw | update `is_deleted` | rollback on missing row (404) |
| **Create dataset + composition + lock** | insert dataset, insert join rows, set `is_locked`, commit | UNIQUE(version) or UNIQUE(dataset_id,draw_id) → rollback all |
| Reads (list/get) | autobegin read; `get_db` closes | n/a — no write |

## Indexes (User Req 3)

| Index | Columns | Type | Justification (trace) |
|---|---|---|---|
| `pk_*` (implicit) | each `id` | Integrity | PK identity (DS §10) |
| `uq_lottery_code` | `lottery.code` | Integrity | CD-01 duplicate-code rejection |
| `uq_draw_lottery_draw_number` | `(lottery_id, draw_number)` | Integrity | CD-02/D3 dedup; **idempotent-import natural key (Req 4)** |
| `ix_draw_lottery_date` | `(lottery_id, draw_date)` | Performance | CD-07 draw list `?lottery=` + `date_from/date_to` filters (API_SPEC §19); D3 |
| `ix_draw_lottery_id` | `draw.lottery_id` | Performance | FK joins; SQLite does not auto-index FKs |
| `uq_draw_numbers_draw_position` | `(draw_id, position)` | Integrity | C7/CD-02 |
| `uq_draw_numbers_draw_number` | `(draw_id, number)` | Integrity | C7/CD-02 repeated-number rejection |
| `ix_draw_numbers_draw_id` | `draw_numbers.draw_id` | Performance | children load (CD-07 serialization) |
| `uq_super_number_draw_id` | `super_number.draw_id` | Integrity | D2/CD-02 0..1 cardinality (doubles as FK index) |
| `uq_datasets_version` | `datasets.version` | Integrity | D16/CD-03 global version uniqueness |
| `uq_dataset_draws_pair` | `(dataset_id, draw_id)` | Integrity | D5/CD-03 composition uniqueness |
| `ix_dataset_draws_draw_id` | `dataset_draws.draw_id` | Performance | composition joins + reverse draw→dataset lookups |

## Error Taxonomy (User Req 5)

| Error | Detection layer | Envelope code | HTTP |
|---|---|---|---|
| Validation error (request shape / field rules) | API (Pydantic) + service invariant checks | `validation_error` (Fase 0 code, kept) | 422 |
| Duplicate resource | DB UNIQUE → repo `IntegrityError` → `DuplicateError` | `DUPLICATE_RESOURCE` | 409 |
| Referential constraint (FK RESTRICT) | DB FK → repo → `ReferentialError` | `REFERENTIAL_CONSTRAINT` | 409 |
| Locked dataset (immutability) | Domain service guard (CD-03) | `DATASET_LOCKED` | 409 |
| Soft-deleted draw | Service explicit access check (CD-05) | `RESOURCE_SOFT_DELETED` | 404 |
| Not found | Repo returns None → service | `RESOURCE_NOT_FOUND` (API_SPEC §2) | 404 |
| Unhandled | Global handler (Fase 0) | `internal_error` (kept) | 500 |

New codes are ADDED to the envelope contract; Fase 0 `http_error`/`validation_error`/`internal_error` remain unchanged.

## Idempotent Import Contract (User Req 4)

Fase 2 owns the importer; **F1 guarantees the contract**:
- **Natural key**: `UNIQUE(lottery_id, draw_number)` in the F1 migration → any conflict strategy can rely on it.
- **Resume semantics**: each batch = one session transaction, committed independently; a crash rolls back only the in-flight batch; completed batches are never re-inserted (natural-key rejection).
- **Conflict strategy**: repository exposes dialect-portable idempotent primitives — `get_by_natural_key(lottery_id, draw_number)` (existence check) and insert-ignore/on-conflict-do-nothing (SQLAlchemy ORM bulk path; dialect-specific statement isolated inside the repository, never in API/services).
- Draw children (numbers/super_number) ride the persisted `draw_id`, so batch retry is safe without new unique keys.

## N+1 Avoidance (User Req 6)

| Relationship path | Strategy (generic) | Owner |
|---|---|---|
| draw → draw_numbers (1:N) | eager loading (selectin) when serializing | repository `get_with_numbers` |
| draw → super_number (1:0..1) | eager loading (joined/selectin) | repository |
| draw → lottery (N:1) | joined loading in list queries | repository `list_draws` |
| dataset → dataset_draws → draw (M:N) | batch load: join rows, then draw set in one IN query | repository |
| **Rule**: API/services never lazy-load inside loops; paginated draw list loads only the page with batch-loaded children. Repository owns every loading decision (Req 6).

## Interfaces / Contracts

```python
class BaseRepository(Generic[ModelT]):            # repositories/base_repository.py
    def get(self, id: int) -> ModelT | None: ...
    def list(self, *, page: int, page_size: int, ...) -> Page[ModelT]: ...
    def create(self, data: dict) -> ModelT: ...
    def update(self, id: int, data: dict) -> ModelT: ...

class DrawRepository(BaseRepository[Draw]):
    def get_by_natural_key(self, lottery_id: int, draw_number: int) -> Draw | None: ...
    def get_with_numbers(self, id: int) -> Draw | None: ...      # eager loads children
    def list_draws(self, *, lottery_code: str | None, date_from, date_to, order, page) -> Page[Draw]: ...
    def upsert_draw(self, ...) -> Draw: ...                       # Req 4, dialect isolated

# services/draw_service.py
class DrawService:
    def create_draw_bundle(self, *, lottery_code, draw_number, numbers, super_number) -> Draw  # one tx
    def soft_delete(self, id: int) -> None / restore(self, id) -> Draw
```

## File Changes

| File | Action | Description |
|---|---|---|
| `backend/src/backend/app/models/{lottery,draw,draw_number,super_number,dataset,dataset_draw}.py` | Create | ORM entities, constraints as declared (CD-01..05) |
| `backend/src/backend/app/models/__init__.py` | Modify | re-export models → alembic `target_metadata` source |
| `backend/alembic/` (`env.py`, `alembic.ini`, `script.py.mako`, `versions/0001_initial_core_domain.py`) | Create | REQ-09 sole schema owner |
| `backend/src/backend/app/repositories/{base_repository,lottery_repository,draw_repository,draw_number_repository,super_number_repository,dataset_repository,dataset_draw_repository}.py` | Create | CD-07 CRUD over DI `Session` |
| `backend/src/backend/app/services/{draw_service,dataset_service}.py` | Create | use cases: draw bundle, dataset+lock, soft-delete/restore, error mapping |
| `backend/src/backend/app/schemas/{lottery,draw,dataset}.py` | Create | Pydantic Create/Update/Read |
| `backend/src/backend/app/api/v1/{lotteries,draws}.py` | Create | CRUD endpoints (API_SPEC §3/§4; `/draws/latest|import|upload` excluded) |
| `backend/src/backend/app/api/v1/router.py` | Modify | mount lotteries/draws routers |
| `backend/pyproject.toml` + `uv.lock` | Modify | add `alembic` dependency |
| `backend/src/backend/app/core/db.py` | Modify | docstring only — migrations own schema; behavior unchanged |
| `backend/tests/{test_models,test_migrations,test_crud_lotteries,test_crud_draws,test_services,test_dialect_compat}.py` | Create | per Req 7 matrix |

## Alembic Design

- `env.py`: imports `models` package; `target_metadata = Base.metadata`; `context.configure(..., render_as_batch=True)` → SQLite `batch_mode`; engine from `settings.database_url` (dialect-driven).
- Revision `0001_initial_core_domain`: creates tables in dependency order `lottery → draw → draw_numbers, super_number → datasets → dataset_draws`; UNIQUE/CHECK/FK constraints inline (portable `op.create_table`/`op.create_index`); **no PG-only or SQLite-only DDL** (REQ-05/09). 0001 owns integrity only.
- Revision `0002_performance_indexes` (PR-5): adds ONLY the four Performance-type indexes from the Indexes table via portable `op.create_index`/`op.drop_index` (batch-mode compatible). Strictly additive and functionally optional — no tables/columns/constraints change; the app works with only 0001 applied, merely slower.
- Downgrade drops in reverse dependency order: `dataset_draws → datasets → super_number, draw_numbers → draw → lottery`.
- `init_db` never creates schema; ordering: `init_db` (file) → `alembic upgrade head` (schema) → app boot.

## Testing Strategy (User Req 7)

| Requirement | Unit | Integration | Migration | Compat |
|---|---|---|---|---|
| CD-01 entities/relationships | model column mapping | — | constraints present post-upgrade | — |
| CD-02 draw/number constraints | — | DB rejects dup draw, dup number, 2nd super | UNIQUEs in schema | — |
| CD-03 dataset immutability | service guard logic | locked-update rejected; new version created | UNIQUE(version) | — |
| CD-04 raw-only/columns | model nullability | null jackpot persists | — | — |
| CD-05 soft-delete/restore | — | filtered lists, restore keeps children, 409 delete | — | — |
| CD-06 DB vs app validation | — | constraint rejects w/o app checks | — | — |
| CD-07 repositories & CRUD | repo unit (mocked session) | TestClient CRUD + `?lottery=` + 404 envelope | — | — |
| CD-08 portability | — | — | — | dialect smoke test |
| REQ-09 migration ownership | — | — | upgrade head creates 6 tables; downgrade base | same migration runs on PG (optional, CI-gated) |

- **Migration tests**: tmp SQLite file, `alembic upgrade head`, assert tables/constraints; `downgrade base` drops in order.
- **Compat**: portable-ops review gate (no dialect DDL) + **dialect smoke test** running the identical migration against Postgres — **needs a real Postgres, optional/CI-gated**; everything else SQLite-only.

## Threat Matrix

N/A — no routing (shell/proxy), shell commands, subprocesses, VCS/PR automation, executable-file classification, or process-integration boundary. FastAPI URL routing is not in scope of the matrix; no RED tests required.

## Migration / Rollout

Fresh DB path: `scripts/init_db.sh` creates file → `alembic upgrade head` → boot. Rollback: `alembic downgrade base` (or delete `database/lip.db`) — zero data loss (dev); fail-fast `batch_mode` per revision; `git revert` restores F0.

## Risks & Rollback

- `WARNING` — **alembic vs `init_db` coordination**: `init_db` must stay file-only; ordering documented (init → upgrade → boot); verify test asserts zero tables pre-upgrade.
- `LOW` — **migration ordering**: single revision with explicit dependency order; downgrade reversed.
- `WARNING` — **dataset immutability is app-enforced, not DB-enforced** (no portable trigger); documented contract, service guard + `DATASET_LOCKED`; verify tests cover it.
- `LOW` — **UNIQUE(draw_id, number) bulk-insert cost** (F2 millions of rows): per-batch tx + FK indexes mitigate; revisit with F2 benchmarks.
- `WARNING` — **400-line review budget**: models+migration+repos+services+API+tests likely exceed; sdd-tasks to recommend chained PR slices.
- Rollback plan per proposal: `alembic downgrade base` / delete DB / `git revert`; F0 `/health` behavior unchanged.

## Open Questions

- [ ] None blocking. (F2 owns importer; PG smoke test CI-gating decision deferred to tasks/CI.)

## Key Learnings

1. Fase 0 already commits to migrations owning schema (`core/db.py` comment), so REQ-09 is a contract formalization, not a behavior break.
2. Existing envelope codes are lowercase (`validation_error`) while API_SPEC examples are uppercase (`RESOURCE_NOT_FOUND`); new codes follow API_SPEC style.
3. SQLite does not auto-index FKs, so every FK column needs an explicit index for join performance.
4. Dataset immutability cannot be a DB trigger portably — the service-layer guard is the only portable enforcement point.
5. The F1 natural key `UNIQUE(lottery_id, draw_number)` is the single schema contract that unblocks F2 idempotent re-imports.
