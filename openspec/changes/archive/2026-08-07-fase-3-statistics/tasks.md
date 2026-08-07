# Tasks: Statistics Engine (Fase 3)

## Review Workload Forecast

Decision needed before apply: Yes
Chained PRs recommended: Yes
Chain strategy: stacked-to-main
400-line budget risk: Medium

| Field | Value |
|-------|-------|
| Estimated changed lines | ~1,050 (3 PRs × ~350) |
| 400-line budget risk | Medium (mitigated by 3-PR split) |
| Chained PRs recommended | Yes |
| Delivery strategy | chained |
| Chain strategy | stacked-to-main |
| Decision needed before apply | Yes — user reviews plan before sdd-apply |
| **G9 Determinism Gate** | **Mandatory before ANY Statistics PR is complete (see G9 below)** |
| **G10 Read-only Integrity Gate** | **Mandatory: `draw`, `draw_numbers`, `super_number`, `dataset`, `import_job`, `import_error` byte-identical before/after generation; only `stat_*` rows may appear (see G10 below)** |

### Suggested Work Units

| Unit | Goal | Likely PR | Focused test command | Runtime harness | Rollback boundary |
|------|------|-----------|----------------------|-----------------|-------------------|
| 1 | Engine + persistence skeleton: stat_* ORM + migration 0005 + checksum + pure metrics + config | PR 1 (stacked-to-main) | `uv run pytest backend/tests/statistics/test_engine.py backend/tests/statistics/test_checksum.py -q` | N/A (pure functions; no DB state) | Revert migration 0005 + models — no core change |
| 2 | Service orchestration: repos + idempotent/incremental generate + atomic commit + fail policy | PR 2 | `uv run pytest backend/tests/statistics/test_statistics_service.py -q` | `lip statistics generate --lottery <code>` on tmp migrated DB (integration conftest) | Remove service+stat_* repos; no API surface shipped |
| 3 | Surface: API `POST/GET` + schemas + error codes + CLI generate/rebuild + migration/G9 e2e tests | PR 3 | `uv run pytest backend/tests/api/test_statistics_api.py backend/tests/test_migrations.py -q` | `fastapi TestClient` + `lip statistics generate/rebuild` | Revert API router + CLI + error registrations |

### G9 — Determinism Gate (MANDATORY, per user)

Given same dataset + same checksum-dataset + same `generator_version` + **two independent generations** → produce **identical snapshots** (content AND checksum). Runs before ANY Statistics PR is considered complete.
- Assert **ALL** of: (1) snapshot `checksum` byte-identical; (2) row **count** per `stat_*` table identical; (3) **content of every `stat_*` table** identical (row-by-row); (4) **deterministic insertion order** (same physical `rowid`/insert sequence); (5) final snapshot **hash** identical — not the checksum alone.
- PR1 ships the **engine-output** determinism test (same input → identical engine outputs).
- PR2 ships the full **two-independent-generations** test on a tmp migrated DB — asserts all five G9 assertions (checksum + row count + content + insertion order + hash) — authoritative G9.
- PR3 records G9 as an explicit final verification step (end-to-end via API/CLI).
- If G9 fails, the PR is NOT complete; fix determinism before rolling forward.

### G10 — Read-only Integrity Gate (MANDATORY, per user)

Statistics MUST NOT mutate core domain tables. After generating statistics, `draw`, `draw_numbers`, `super_number`, `dataset`, `import_job`, `import_error` remain **byte-identical** to their pre-generation state. The only permitted DB change is the appearance of rows in `stat_*`. This protects the most important contract of Fase 3.
- PR2 ships the **authoritative G10 integration test**: snapshot the six core tables (canonical dump + checksum) before generation → run generation | | assert identical (row-by-row) after; only `stat_*` row counts changed.
- PR3 records G10 end-to-end (API `POST /statistics/generate` + CLI) with the same before/after audit of the six core tables.
- If G10 fails, the PR is NOT complete; any core-table mutation is a release blocker.

## Phase 1: Foundation / Persistence Skeleton (Unit 1 → PR1)

- [x] 1.1 `statistics/checksum.py` — `stat_checksum(...)`: canonical JSON `sort_keys=True`, compact separators (mirror `_dataset_checksum` `import_service.py:317`) over `{lottery_id, metric_set, range, generator_version, engine_version, numbers/positions/gaps/averages/scalars}`.
- [x] 1.2 `statistics/engine.py` — pure deterministic metric fns: frequency `dict[int,int]`, positional `dict[(num,pos),int]`, gaps last-seen, NULL-aware averages (Decimal), Shannon entropy base-2 over `[min..max]` iterating `number ASC` (design §10). INTEGER/Decimal accumulators only.
- [x] 1.3 `statistics/generator.py` — `STATS_GENERATOR_VERSION` const (§8) + `core` metric-set definition + fold/scope rules (incremental vs full).
- [x] 1.4 `models/stat_snapshot.py` — header: `FK lottery RESTRICT`, `UNIQUE(lottery_id, metric_set, version)`, `CHECK draws_from<=draws_to`, status `CHECK`, `is_locked`. RFC 3339 tz timestamps.
- [x] 1.5 `models/stat_frequency.py` (PK snapshot,number), `stat_frequency_position.py` (PK snapshot,number,position), `stat_gap.py` (PK snapshot,number), `stat_average.py` (PK snapshot,series_key; semantics NULL-aware), `stat_scalar.py` (PK snapshot,name).
- [x] 1.6 `models/__init__.py` — register all `stat_*` (feeds alembic `target_metadata`).
- [x] 1.7 `alembic/versions/0005_stat_tables.py` — create 6 `stat_*` tables (portable DDL, batch patterns from 0001/0003) + `stat_*` indexes ONLY (`ix_snap_lottery_metric_status`, `ix_stat_*_snapshot_id`); NO `draw`/`draw_numbers` change (Option A, §4).
- [x] 1.8 `config/settings.py` — add `stats_retention_generations: int = 10`.
- [x] 1.9 tests: `tests/statistics/test_engine.py` (determinism: same input → identical output), `test_checksum.py` (canonical/sort stable), migration 0005 up/down in `test_migrations.py` (stat_* at head; downgrade drops only stat_*; core untouched). Green before PR1.

## Phase 2: Service Orchestration (PR 2 → stacked on PR1)

- [x] 2.1 `services/errors.py` — add `GenerationError`(generation_error→500), `SnapshotNotFoundError`(SNAPSHOT_NOT_FOUND→404), `SnapshotLockedError`(SNAPSHOT_LOCKED→409).
- [x] 2.2 `repositories/stat_snapshot_repository.py` — create/add, `get_active(lottery,mt)`, `latest`, retire-old-active (same tx), idempotent `find_by_checksum_version`.
- [x] 2.3 `repositories/stat_payload_repository.py` — `bulk_insert` payload batches (BATCH_SIZE) over `draw JOIN draw_numbers ON draw.id=draw_numbers.draw_id WHERE draw.lottery_id=? AND draw.is_deleted=0 ORDER BY draw.draw_number, draw_numbers.id` (deterministic keyset, §3/§9).
- [x] 2.4 `services/statistics_service.py` — preview checksum → idempotent match returns existing active (200, no dup version) else incremental (delta `draw_number > draws_to`) / full rebuild as NEW version; single atomic commit; failed batch → `status='failed'` never active/partial (§3).
- [x] 2.5 RED→GREEN: `test_statistics.py` (integration, tmp migrated DB): incremental matches full-rebuild checksum; **G9 two-independent-generations — asserts checksum + row count + per-table content + insertion order + final snapshot hash identical**; idempotent no-dup; batch-fail → failed, resume → new snapshot.
- [x] 2.6 RED→GREEN: **G10 read-only integrity test** — canonical dump+checksum of `draw`, `draw_numbers`, `super_number`, `dataset`, `import_job`, `import_error` before generation → generate → assert byte-identical after (row-by-row); only `stat_*` rows changed.

## Phase 3: Surface (PR 3 → stacks on PR2)

- [x] 3.1 `schemas/statistics.py` — GenerateRequest(`lottery_code`, `metrics` default core, `scope` default incremental), snapshot + read response models.
- [x] 3.2 `api/errors.py` — register `generation_error`→500, `SNAPSHOT_NOT_FOUND`→404, `SNAPSHOT_LOCKED`→409.
- [x] 3.3 `api/v1/statistics.py` — `POST /statistics/generate` (idempotent) + `GET /{code}/{frequencies,gaps,averages}?last=N` — reads NEVER precompute; missing snapshot → SnapshotNotFound.
- [x] 3.4 `api/v1/router.py` — `include_router(statistics_router)`.
- [x] 3.5 `cli.py` — `statistics generate`/`rebuild` subcommand (mirror `_cmd_dataset_generate`; argparse only, never shells out), print snapshot JSON.
- [x] 3.6 RED→GREEN: API contract (POST idempotent, unknown lottery 404, GET missing snapshot 404+no-autocreate), CLI generate/rebuild, G9 end-to-end, G10 e2e (API `POST` + CLI: six core tables byte-identical), `test_migrations.py` 0005 head/downgrade.

## Phase 4: Cleanup / Verification (Final)

- [x] 4.1 README/comments: `statistics` usage + determinism contract + G9 explanation. (README.md → Fase 3 section; IMPLEMENTATION_ROADMAP.md → scope note; evidence in verify-report.md)
- [x] 4.2 G1 ruff, G2 pytest full, G3 alembic upgrade head, G4 downgrade chain, G5 no regression CD/REQ, G6 portability (PG+SQLite), G7 API contract, G8 issue/no-debt. (verify-report.md: 190 passed / 1 skipped; ruff clean; head 0005; migrations 8 passed; no TODO/FIXME/XXX)
- [x] 4.3 **G9 Determinism Gate final**: repeat two independent generations → assert checksum + row count + per-table content + insertion order + final snapshot hash identical. Pass required before PR complete.
- [x] 4.4 **G10 Read-only Integrity Gate final**: before/after audit confirms `draw`, `draw_numbers`, `super_number`, `dataset`, `import_job`, `import_error` byte-identical; only `stat_*` rows appeared. Pass required before PR complete.

## Rules

- RED tests (failing) written before production code where determinism is involved (TDD); tasks reference concrete paths; ordered by dependency (Phase N never depends on Phase N+1).