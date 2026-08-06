# Design: Fase 2 Data Engine (Importation)

**Change**: `fase-2-data-engine` · **Store**: openspec · **Date**: 2026-08-06
**Inputs**: import-engine spec (IE-01..IE-11 + Non-Goals), proposal (D1-D6), F1 design (layers, tx, index, error strategy), CD-01..08, REQ-01..09, DATABASE_SCHEMA.md, API_SPECIFICATION §4/§17/§19, F1 code (`draw_service`, `dataset_service`, `services/errors`, repos, `api/v1/draws`).

## 1. Context

F1 ships ~60% of the contract: `UNIQUE(lottery_id,draw_number)` natural key, `create_draw_bundle` (atomic, idempotent, service-owned invariants), typed error taxonomy → envelope, N+1-free loaders, empty `importers/` seam, unmounted `/draws/import`+`/draws/upload`. F2 fills the gap: **stream-parse CSV → Phase A structural reject → normalize → Phase B per-row semantic errors → commit-per-draw bundle → auditable `imports`/`import_errors` → on-demand immutable dataset**. No scheduler (D3), CSV only (D1), no staging table, no full-file RAM load, no dataset auto-creation during import (D5). CD-01..08 and REQ-01..09 are durable and untouched.

## 2. Decisions & Alternatives

| # | Decision | Alternatives | Choice & Rationale |
|---|---|---|---|
| D-A | Approach | Staging tables; load-all-then-commit | **Stream→validate→commit-per-draw, no staging** (D6, IE-05). Bounded memory; crash rolls back only the in-flight draw; F1 natural key makes resume safe. |
| D-B | Source seam | Remote/external adapters now | **`sources.py` CSV `FileAdapter` only** (proposal scope). One concrete adapter; remote deferred — adapter interface isolates the swap. |
| D-C | `/draws/import` vs `/draws/upload` (IE-11 CRITICAL) | Single endpoint; import by reference only | **Two endpoints, one `ImportService.run()`**: `import` = JSON body referencing a server-side `source_file`; `upload` = multipart file streamed to a temp file. Both force `import_type="manual"` (channel-derived, never client-chosen). Contract in §6. |
| D-D | Counter/resume atomicity (IE-05/06) | Counters updated after each `create_draw_bundle` (2 commits/draw); re-scan on resume | **One transaction per draw** composing the F1 repository primitives that back `create_draw_bundle` (same validation rules, same repos) **plus** the run's counter row and `last_processed_row`, committed once. Crash can never leave counters ahead of draws; resume is positional (`last_processed_row+1`), so committed draws are never re-imported or misclassified as duplicates. |
| D-D2 | Resume contract (AJUSTE 2) | Resume blindly from `last_processed_row` | **Resume is valid ONLY when the new attempt matches the original run on: `checksum`, `parser_version`, `engine_version` (compatible), and `lottery_id`.** If ANY differs → do NOT continue the old run; create a NEW `imports` row (fresh run). NEVER resume a different file. Verified before the first row; a mismatch on a terminal run is also a fresh run (D-E). |
| D-E | State machine enforcement (IE-06) | DB trigger; app-only check | **Service-owned transition table + repository conditional-UPDATE backstop + portable `CHECK(status IN …)`**. Triggers are dialect-specific (REQ-09); CD-06 split: DB owns allowed values, service owns transitions, repo rejects illegal writes. Terminal rows are immutable. |
| D-F | `error_code` taxonomy (IE-03) | Generic `row_error` | **9 typed codes** (§7) written to `import_errors.error_code` with `message` + `raw_row`. Duplicates NEVER surface `DUPLICATE_RESOURCE` — natural-key hits count `duplicate_rows` (IE-04/IE-11). |
| D-G | `parser_version` semantics | Reuse app version | **Module constant `PARSER_VERSION` in `importers/version.py`**, bumped only when CSV interpretation logic changes (column mapping, delimiter, normalization, Phase A/B rule set); independent of `engine_version` (`settings.app_version`). Recorded per run → exact reproduction (IE-06/07). |
| D-H | Checksum re-import (IE-04) | Short-circuit on checksum match | **No short-circuit; always a new `imports` row.** The file re-streams, every row hits the natural key → `duplicate_rows=total_rows`, `imported_rows=0`, `status=completed`. Audit never loses an execution; counters reconcile regardless of content drift. |
| D-I | Dataset on demand (D5/IE-09) | Auto-generate after import | **Explicit CLI + service op only** (`generate_dataset`): filters → one batch draw query → SHA-256 checksum → `dataset_service.create_dataset` (now accepts `checksum`, additive default `None`) → immutable + locked (CD-03). Import never creates datasets. |
| D-J | Concurrency (AJUSTE 1) | Partial unique index on active runs | **For the SAME `lottery_id`, at most ONE `imports` row may be in `in_progress`.** A new import is rejected with `IMPORT_CONFLICT` (409) when another run for the same lottery is already `in_progress`. Imports of DIFFERENT lotteries run simultaneously without conflict. Service pre-check (not a dialect-specific partial index); a manual single-operator tool makes the small race acceptable (documented, verified). |

## 3. Layered Architecture

| Layer | Files | Responsibility | Explicitly does NOT |
|---|---|---|---|
| **ORM models** | `models/import_job.py`, `models/import_error.py` | Mapped columns, PK/FK/CHECK, relationships (loading only) | No business logic, no transitions |
| **Repositories** | `repositories/import_repository.py`, `repositories/import_error_repository.py` | Create run, positional progress update, conditional terminal transition (rowcount guard), batch error insert; natural-key read via existing `draw_repository` | No orchestration, no HTTP |
| **Importers (domain)** | `importers/sources.py` (CSV `FileAdapter`, stream), `importers/normalize.py` (typed `NormalizedDraw`), `importers/validate.py` (Phase A structural, Phase B per-row), `importers/version.py` (`PARSER_VERSION`) | Parse/normalize/validate; pure functions, no DB | No session, no persistence |
| **Application** | `services/import_service.py` | Use case `run_import` (lifecycle, state machine, per-draw tx, counters, resume, checksum) + `generate_dataset`; error→envelope mapping | No raw SQL, no request parsing |
| **API** | `api/v1/draws.py` (modify) | Mount `POST /draws/import`, `POST /draws/upload`; envelope; `import_type="manual"` forced | No SQL, no business logic |
| **CLI** | `cli.py` (new) + `pyproject.toml` console script | `lip import --lottery --file [--resume]`, `lip dataset-generate …`; `import_type="cli"`, `started_by` from `getpass` | No API |
| **Alembic** | `versions/0003_imports_audit.py`, `0004_import_performance_indexes.py` | Additive portable DDL, `batch_mode` (REQ-09) | No seeding, no logic |

Flow: `API/CLI → ImportService.run_import → FileAdapter.stream → Phase A → normalize → Phase B → per-draw tx (draw repos + counters) → ImportRepository; errors → ImportErrorRepository.add_many (batched)`.

## 4. Data Model

`imports` (audit, one row per execution — every run, even rejected/partial):

| Column | Type | Constraint | Notes |
|---|---|---|---|
| `id` | Integer | PK | |
| `lottery_id` | Integer | FK→lottery.id RESTRICT, NOT NULL | |
| `status` | String(16) | NOT NULL, `CHECK (status IN ('rejected','in_progress','completed','partial','failed'))` | structural (CD-06) |
| `source_file` | String(512) | NOT NULL | |
| `checksum` | String(64) | NOT NULL | SHA-256 of file bytes, streamed |
| `import_type` | String(16) | NOT NULL, `CHECK (import_type IN ('manual','cli','runner'))` | channel-derived (D-C) |
| `started_by` | String(64) | NULL | CLI user or null (IE-07) |
| `engine_version` | String(32) | NOT NULL | `settings.app_version` |
| `parser_version` | String(32) | NOT NULL | `importers/version.PARSER_VERSION` (D-G) |
| `total_rows` / `imported_rows` / `skipped_rows` / `duplicate_rows` / `error_rows` | Integer | NOT NULL, `CHECK (col >= 0)` | reconcile `total = imported+skipped+duplicate+error` (service-confirmed, IE-06) |
| `duration_ms` | Integer | NOT NULL | |
| `started_at` / `finished_at` / `created_at` | DateTime(timezone=True) | NOT NULL | tz-aware UTC (CD-04) |
| `last_processed_row` | Integer | NULL | **additive** resume marker (D-D; IE-06 "AT MINIMUM" permits) |

`import_errors` (per-row semantic failures, IE-03):

| Column | Type | Constraint |
|---|---|---|
| `id` | Integer | PK |
| `import_id` | Integer | FK→imports.id RESTRICT, NOT NULL |
| `row_number` | Integer | NOT NULL |
| `draw_number` | Integer | NULL (may be unparseable) |
| `message` | String(512) | NOT NULL |
| `error_code` | String(32) | NOT NULL (taxonomy §7) |
| `raw_row` | Text | NOT NULL (verbatim row) |

**Indexes** (integrity→0003, performance→0004, mirroring F1's 0001/0002 split):

| Index | Type | Justification |
|---|---|---|
| `pk_*` (implicit) | Integrity | PK identity |
| `fk imports.lottery_id`, `fk import_errors.import_id` | Integrity | FK RESTRICT (SQLite does not auto-index FKs — join cost, F1 learning #3) |
| `ix_imports_lottery_status_started` `(lottery_id, status, started_at)` | Performance | latest-run lookup, in-progress guard, per-lottery history (prompt-mandated) |
| `ix_imports_checksum` | Performance | exact-same-file audit correlation (IE-04) |
| `ix_import_errors_import_id` | Performance | per-run error listing |

**Portability**: no triggers, no partial/expression indexes, no PG/SQLite DDL; `batch_mode`; additive — existing tables untouched (IE-10).

**State machine** (IE-06; enforced per D-E):

| From | → To | Trigger | Terminal |
|---|---|---|---|
| `in_progress` | `completed` | all rows processed, no fatal error | yes |
| `in_progress` | `partial` | recoverable failure stopped the run | no (resumable) |
| `in_progress` | `failed` | fatal/unrecoverable failure | yes |
| `in_progress` | `rejected` | Phase A structural failure, nothing imported | yes |
| `partial` | `completed` | resume completes | yes |
| `partial` | `failed` | resume hit fatal error | yes |
| `completed`/`failed`/`rejected` | any | **FORBIDDEN** — terminal immutable; resume of a terminal run creates a NEW run (IE-06 scenario) | — |

## 5. Sequence Diagrams

**(a) Phase A reject flow (IE-02):**

```
Client ──► /draws/upload ──► ImportService.run_import
   FileAdapter.stream ──► sha256 (streamed)
   Phase A: UTF-8/delimiter/headers ──✗ fail
   ImportRepository.create(status=in_progress) ──► finish(rejected)
   ──► 422 {error:{code:"validation_error"}}   (imports row status=rejected; 0 draws)
```

**(b) Bulk per-draw commit + resume (IE-04/05/06):**

```
ImportService.run_import(lottery, source, resume?)
  ── create run (in_progress) ──► imports row
  loop rows (stream):
    Phase B row valid? no ──► ImportErrorRepository.add_many (batch) → error_rows++
    natural key exists?     yes ──► duplicate_rows++   (NEVER DUPLICATE_RESOURCE)
    else: one tx: draw.create → numbers.add_many → super.add
                 → counters++ , last_processed_row=n   ── commit (D-D)
  crash mid-row ──► in-flight tx rolls back; run marked partial
  resume: continue from last_processed_row+1 ──► partial → completed
```

**(c) On-demand dataset generation (D5/IE-09):**

```
CLI lip dataset-generate ──► ImportService.generate_dataset(filters, version, generator_version)
  ── draw selection: ONE batched query (filters, is_deleted=False)
  ── checksum = sha256(canonical {filters, generator_version, draw_ids})
  ── dataset_service.create_dataset(..., checksum, is_locked=True) ── commit
  ── immutable locked dataset; import itself created no datasets
```

## 6. API Contract (D-C; envelope REQ-02)

| | `POST /draws/import` | `POST /draws/upload` |
|---|---|---|
| Content-Type | `application/json` | `multipart/form-data` |
| Body/fields | `{lottery_code: str, source_file: str, resume?: bool=false}` | `lottery_code` (form), `file` (UploadFile), `resume` (form, default false) |
| `lottery_code` | required; resolved via `LotteryRepository.get_by_code` (CD-07) | same |
| `import_type` | **forced `manual`** server-side (never client-supplied) | **forced `manual`** |
| File handling | stream from server path (must exist → else 422) | streamed to temp file; sha-256 computed while streaming |
| 200 | envelope `data: {imports: {id, status, total_rows, imported_rows, skipped_rows, duplicate_rows, error_rows, duration_ms, checksum, started_at, finished_at}}` | same summary |
| 404 | `RESOURCE_NOT_FOUND` — unknown lottery | same |
| 409 | `IMPORT_CONFLICT` — another import for the SAME `lottery` is already `in_progress` (D-J); different lotteries are unaffected | same |
| 422 | `validation_error` — Phase A failure / bad body / source file missing / resume on terminal run | `validation_error` — Phase A failure / bad fields |
| Per-row dup | counted `duplicate_rows`, no error (IE-04/IE-11) | same |

**CLI**: `lip import --lottery baloto --file draws.csv [--resume]` (`import_type="cli"`, `started_by=getpass.getuser()`); `lip dataset-generate --version v2 --lottery baloto [--filters json]`. **Runner**: same `ImportService.run_import`, recorded `import_type="runner"` — reserved for a future on-demand caller; NO scheduler ships (IE-08).

## 7. Error Handling

**Phase B row codes** (IE-03, written to `import_errors.error_code` + `message` + `raw_row`; row-level, never abort the run):

| error_code | Condition |
|---|---|
| `bad_row_number` | `draw_number` missing / not int / ≤ 0 |
| `bad_draw_date` | `draw_date` missing / not `YYYY-MM-DD` / invalid |
| `too_few_numbers` | main numbers < `numbers_to_select` |
| `too_many_numbers` | main numbers > `numbers_to_select` |
| `number_out_of_range` | number outside `[min_number, max_number]` |
| `duplicate_in_draw` | same main number twice in one row (before DB, IE-03 scenario) |
| `bad_super_number` | super present but out of `[super_number_min, super_number_max]` / lottery has no super range |
| `bad_jackpot` | `jackpot` not a valid decimal |
| `bad_winners` | `winners` not a non-negative integer |

**Envelope mapping** (extends F1 taxonomy; Fase 0 codes kept):

| Error | Detection | Envelope code | HTTP |
|---|---|---|---|
| Phase A structural | validate.py → ImportService | `validation_error` (kept) | 422 |
| Missing lottery | `get_by_code` → None | `RESOURCE_NOT_FOUND` | 404 |
| Concurrent active run | ImportService pre-check | `IMPORT_CONFLICT` (new) | 409 |
| Illegal state transition | repo conditional update rowcount 0 | `IMPORT_STATE_CONFLICT` (new) | 409 |
| Duplicate draw | natural-key check (not an error) | — counted `duplicate_rows` | — |
| Unhandled | global handler | `internal_error` (kept) | 500 |

New codes `IMPORT_CONFLICT`/`IMPORT_STATE_CONFLICT` are registered in `api/errors.py` `_CODE_TO_STATUS` (both 409).

## 8. Concurrency & N+1

- **Lottery loaded once per run**, not per row. Per-row natural-key lookup is an indexed point query (O(log n), no relationship lazy-loading) — not N+1.
- **`import_errors` batched** via `add_many` flushed per commit window; never per-row flush.
- **Dataset generation**: draw selection in one filtered query; composition via `add_many` batch; `get_with_numbers`-style eager loads where serialized (CD-07).
- **Concurrency (AJUSTE 1)**: service pre-check rejects a NEW import when an `in_progress` run exists for the SAME `lottery_id` (`IMPORT_CONFLICT`). Runs for DIFFERENT lotteries execute concurrently without conflict. A `partial` run does NOT block new imports — it is only resumable via the resume contract (D-D2); starting a fresh import creates a new run. Race window accepted for a manual single-operator tool (D-J). Checksum path needs no lock — a same-file re-import is a fresh run (D-H).
- **Resume (AJUSTE 2 / D-D2)**: a `resume=true` request is honored ONLY when the new attempt matches the target run on `checksum`, `parser_version`, `engine_version` (compatible), and `lottery_id`. On ANY mismatch the service does NOT continue the old run — it creates a NEW `imports` row and imports from row 1. NEVER resume a different file.

## 9. Testing Strategy

| Layer | What | Approach |
|---|---|---|
| Unit | Phase A/B (`validate.py`), normalize, checksum, `PARSER_VERSION` stability | CSV fixture matrix: canonical header, unknown column, wrong delimiter, non-UTF-8, one row per error_code, in-file dup |
| Unit | State machine transitions | service `_assert_transition` table: legal/illegal pairs; terminal immutability |
| Integration | Full import: counters reconcile (`3+0+2+1=6`), statuses | tmp SQLite + `ImportService.run_import` over F1 session |
| Integration | Phase A reject → `imports.status=rejected`, 0 draws; Phase B → `import_errors` rows + `error_rows` | same harness |
| Integration | Exact-same-file re-import: new row, `imported=0, duplicate=total`, `completed`; resume: partial→completed, no dup, no re-insert; concurrent run → 409 | same harness |
| Integration | Concurrency (AJUSTE 1): second import of the SAME lottery while `in_progress` → `IMPORT_CONFLICT`; import of a DIFFERENT lottery concurrently → allowed | same harness |
| Integration | Resume contract (AJUSTE 2): resume valid on `checksum`+`parser_version`+`engine_version`+`lottery_id` match; ANY mismatch → fresh run, no continuation of old run, never resumes a different file | same harness |
| Integration | Duplicate NEVER raises `DUPLICATE_RESOURCE` (IE-11) | assert no envelope error on re-import |
| API | `POST /draws/upload` (multipart 200/422/404), `POST /draws/import` (404/409/422/200) | TestClient, existing F1 envelope patterns |
| Migration | 0003/0004 up: tables+CHECK+FKs; down: drop indexes then tables in order; PG-portable smoke (CI-gated, `dialect-pg` extra) | mirror `test_migrations.py`/`test_dialect_compat.py` |
| Regression | CD-01..08 contract-preservation tests stay green; `dataset_service.create_dataset` checksum param is additive | full pytest |

## 10. Risks

- `CRITICAL` — **IE-11 contract ambiguity**: RESOLVED normatively in §2 D-C / §6 (two endpoints, forced `manual`, summary envelope). Tasks must implement exactly this.
- `WARNING` — **counter/resume exactness**: mitigated by D-D (per-draw tx folds counters + `last_processed_row`); verified by resume tests.
- `WARNING` — **terminal immutability is app-enforced, not DB-enforced**: no portable trigger; service guard + repo conditional update + status CHECK (D-E); tests cover "resume on completed → new run".
- `WARNING` — **400-line review budget**: proposal forecasts 3 chained PR slices; `sdd-tasks` MUST respect and split accordingly.
- `LOW` — per-row natural-key lookups on huge files (indexed; revisit with benchmarks, F1 learning).
- `LOW` — concurrency pre-check race (single-operator manual tool; documented).

## 11. Rollback

`alembic downgrade -1` (or `base`) drops `0004` indexes then `0003` tables in reverse dependency order (`import_errors → imports`); `git revert`; CD-01..08 and draw/dataset data untouched (additive migration, IE-10). No partial multi-draw commits ever exist (per-draw tx), so no data repair is needed.

## Threat Matrix

N/A — no routing (shell/proxy), shell command, subprocess, VCS/PR automation, executable-file classification, or process-integration boundary. The new CLI is an argparse entry point that never shells out; FastAPI URL routing is out of the matrix's scope (mirrors F1). No RED tests required.

## Open Questions

- [ ] None blocking. (PG smoke-test CI gating deferred to tasks/CI, as in F1.)

## Key Learnings

1. The F1 per-batch design and IE-05 per-draw language are reconciled by folding run counters into each draw's transaction.
2. IE-06 "AT MINIMUM" permits additive columns — `parser_version` and `last_processed_row` are compliant additions.
3. `import_type` must be channel-derived, never client-supplied, or the audit contract (IE-07) is forgeable.
4. Checksum collision handling is a fresh-run policy (D-H), not a dedup gate — audit integrity outranks storage economy.
5. Terminal-state immutability reuses F1's portable guard pattern (service + repo backstop + CHECK), never a dialect trigger.
