# Design: Statistics Engine (Fase 3)

**Change**: `fase-3-statistics` · **Store**: `openspec` · **Date**: 2026-08-07
**Artifact**: design · **Predecessors**: proposal, `statistics-engine` spec (STE-01..13), `backend` delta.

## 1. Technical Approach / Architecture

Hybrid (D1): values accumulative metrics are precomputed into immutable `stat_*` snapshots; point/small-window reads (LAST N, bounded filters) are answered on demand against those snapshots — never auto-precomputing (C5). A manual `POST /statistics/generate` and a `lip statistics …` CLI are the ONLY update paths (D6); statistics NEVER mutate `draw`/`draw_number`/`super_number`/`dataset`/`import_*` (D2/C3). Metric logic lives in the pure `statistics/` engine seam (mirrors `analytics/` seam ownership). Persistence/serialization follow house conventions (`models/`, `repositories/`, `services/`, `api/v1/`, `schemas/`).

```
statistics/
├── engine.py            pure metric engines (frequency, gaps, averages, distributions, entropy)
├── generator.py         metric-set definitions + STATS_GENERATOR_VERSION const + fold/scope rules
└── checksum.py          canonical SHA-256 checksum (determinism contract)
```

Layer map (each file mirrors an existing house seam):

| File | Action | Responsibility | Mirrors |
|------|--------|----------------|---------|
| `app/statistics/__init__.py` | Modify | seam docstring update | REQ-01 |
| `app/statistics/engine.py` | Create | pure stat aggregation (batched, deterministic); no DB | `analytics/` seam |
| `app/statistics/generator.py` | Create | metric definitions, draw-range fold, full-rebuild/regen rules | `importers/validate` |
| `app/statistics/checksum.py` | Create | SHA-256 canonical checksum over dataset+metrics | `import_service._dataset_checksum` |
| `app/models/stat_snapshot.py` | Create | snapshot header ORM |
| `app/models/stat_frequency.py` | Create | per-number raw frequency (overall) |
| `app/models/stat_frequency_position.py` | Create | per-(number,position) frequency |
| `app/models/stat_gap.py` | Create | normalized gap summary rows |
| `app/models/stat_average.py` | Create | per-(snapshot) jackpot/winners means |
| `app/models/stat_scalar.py` | Create | dataset-level distribution entropy/trend scalars |
| `app/repositories/stat_snapshot_repository.py` | Create | header CRUD + active/latest resolution + lock/retire |
| `app/repositories/stat_payload_repository.py` | Create | batched bulk insert of payload rows | `draw_repository.list_draws` batching |
| `app/services/statistics_service.py` | Create | snapshot orchestration (D1/C4/C6), single tx | `dataset_service.create_dataset` |
| `app/api/v1/statistics.py` | Create | POST generate + GET reads (never precompute) | `api/v1/lotteries.py` |
| `app/schemas/statistics.py` | Create | request/response pydantic | `schemas/lottery.py` |
| `app/cli.py` | Modify | `statistics generate`/`statistics rebuild` subcommands | `_cmd_dataset_generate` |
| `_code_to_status` + `api/errors.py` | Modify | register `generation_error` (500), `SNAPSHOT_NOT_FOUND` (404), `SNAPSHOT_LOCKED` (409) | existing taxonomy |
| `services/errors.py` | Modify | add stat domain errors | `DatasetLockedError` |
| `alembic/versions/0005_*` | Create | `stat_*` tables + new `stat_*` indexes ONLY (no core-table change) | 0001/0003 pattern |

No circular dependency: `api → service → repository + statistics/clean → models`; `statistics/` imports only stdlib. `statistics` never imports `import_service`.

## 2. Data Model — `stat_*` tables

Portable DDL only (REQ-09): PK, FK (RESTRICT), UNIQUE, CHECK. Performance indexes owned by migration 0005, not the models. Timestamps `DateTime(timezone=True)` with `datetime.now(UTC)` (CD-04). Immutability enforced by the service (no dialect triggers — same rationale as `datasets`).

> **Versioning contract**: every snapshot carries mandatory `generator_version` + immutable `version`; a NEW version is written on any change (C1/C4/STE-04). Old snapshots are never recomputed in place. `generator_version` = `statistics/generator.STATS_GENERATOR_VERSION` (local const, §8); `engine_version` = `settings.app_version` recorded for audit; `parser_version` not applicable here (no file parser — recorded as `None`), independent values per Requirement 8 note.

Row reason per table:

### `stat_snapshots` (header)

| Column | Type/Null | Reason |
|--------|-----------|--------|
| `id` | int PK | surrogate |
| `lottery_id` | int NOT NULL, FK→`lottery.id` RESTRICT | per-lottery scoping (STE-11); RESTRICT blocks orphan |
| `metric_set` | str(16) NOT NULL | identifies the metric bundle (e.g. `core`) |
| `version` | str(32) NOT NULL | human snapshot number, monotonic per (lottery, metric_set) |
| `generator_version` | str(32) NOT NULL | immutable algorithm identity (C1/STE-04) |
| `engine_version` | str(32) NOT NULL | settings.app_version audit: independent of generator_version |
| `checksum` | str(64) NOT NULL | canonical SHA-256 of dataset+metrics (STE-05/C2) |
| `status` | str(16) NOT NULL | `active` (current), `retired` (superseded) or `failed` (aborted mid-batch, dead metadata); `CHECK(status IN ('active','retired','failed'))` |
| `is_locked` | bool NOT NULL | immutable after commit (service sets True atomically) |
| `draw_count` | int NOT NULL | draws folded into snapshot (validates NOT NULL against `ranges`) |
| `draws_from` | int NOT NULL | min draw_number covered by this snapshot — incremental fold source |
| `draws_to` | int NOT NULL | max draw_number covered (latest fold bound) |
| `created_at` / `updated_at` | DateTime(tz) NOT NULL | audit/retention |
| `parser_version` (reserved, nullable) | str(32) NULL | reserved for future; not populated now |

CHECK: `ck_stat_snapshots_range` = `draws_from <= draws_to`. UNIQUE `(lottery_id, metric_set, version)` — one immutable version identity.

Active resolution: exactly one `status='active'` per `(lottery_id, metric_set)` is enforced by the service (flip old→`retired` in the same tx that creates the new active row — the same app-guard pattern as dataset immutability). Read path filters `status='active'`.

### `stat_frequency` (payload — overall)

| Column | Type/Null | Reason |
|--------|-----------|--------|
| `snapshot_id` | FK→`stat_snapshots.id` RESTRICT | branch of this snapshot's metrics |
| `number` | int NOT NULL | the drawn value — every `number` in `[min,max]` |
| `count` | int NOT NULL | total appearances of `number` (exact, INTEGER = deterministic accumulation) |
| PK | `(snapshot_id, number)` | one row per number |

### `stat_frequency_positions`

| Column | Type/Null | Reason |
|--------|-----------|--------|
| `snapshot_id` | FK RESTRICT | as above |
| `number` | int NOT NULL | number |
| `position` | int NOT NULL | ball slot (1..numbers_to_select); distribution |
| `count` | int NOT NULL | appearance at this `(number,position)` |
| PK | `(snapshot_id, number, position)` | per positional frequency |

### `stat_gaps`

| Column | Type/Null | Reason |
|--------|-----------|--------|
| `snapshot_id` | FK RESTRICT | as above |
| `number` | int NOT NULL | per-number gap series |
| `gap_count` | int NOT NULL | number of gaps observed for `number` |
| `min_gap` / `max_gap` / `avg_steps` | int / int / Numeric(20,6) | exact summary, computed in stable fold |
| PK | `(snapshot_id, number)` | — |

### `stat_averages`

| Column | Type/Null | Reason |
|--------|-----------|--------|
| `snapshot_id` | FK RESTRICT | aggregate over a snapshot |
| `series_key` | str(32) NOT NULL | `jackpot` \| `winners` (NULL-aware) |
| `mean` | Numeric(20,6) nullable | mean over NON-NULL draws only; NULL when count=0 (D4) |
| `non_null_count` | int NOT NULL | draws that actually contributed |
| PK | `(snapshot_id, series_key)` | one row per series |

`jackpot`/`winners` NULLs are ignored, NEVER imputed (D4/STE-07). If a series has zero non-NULL draws, `mean=NULL` with `non_null_count=0` — never a synthesized value.

### `stat_scalars` (distribution/trend scalars — E.g. entropy, distribution moments)

| Column | Type/Null | Reason |
|--------|-----------|--------|
| `snapshot_id` | FK RESTRICT | as above |
| `name` | str(48) NOT NULL | e.g. `entropy`, `distribution_mean_by_pos` |
| `value` | Numeric(20,8) NOT NULL | exact decimal, deterministic fold |
| PK | `(snapshot_id, name)` | normalized, searchable |

**JSON-vs-tabular decision**: chosen **normalized tabular** over a JSON blob for every metric. Rationale: (1) SQL-searchable/indexable → STE-09-point reads and `GET …?last=N` can be served by equality + LIMIT without decoding blobs; (2) **determinism/portability** — a JSON dump is a byte-encoding whose key order and precision are dialect/float-lib-dependent and would leak float drift into the checksum; per-row Numeric INTEGER totals on stop binary store exact values, so the snapshot checksum is stable across SQLite/PostgreSQL (Requirement 9). Cost vs a blob: more rows on writes → mitigated by batched bulk-insert (C6) and a single payload write per snapshot. A scalar-only path (entropy) uses `stat_scalars` because it is non-joinable (no natural axis) — still tabular key/value, not one fat JSON cell.

## 3. Batch Strategy (STE-08/C6; SHA-256-atomic writes)

- **Not** load all draws: every aggregation iterates number rows in **batches of `BATCH_SIZE = 1_000` draw-number rows**, keyset-paginated over `draw_numbers` JOINed to `draw` on `draw.id = draw_numbers.draw_id`, screened by `draw.lottery_id = ? AND draw.is_deleted = 0`, `ORDER BY draw.draw_number, draw_numbers.id` (stable primary tie-break → deterministic; also when pruned by the delete-policy). Keyset > offset: stable across new inserts, O(1) page skip per batch. The batch query screens draws first via the existing `UNIQUE(lottery_id, draw_number)` index, then joins the equal `draw_numbers` set per batch — no cross-draw scan is needed, no denormalized column (Option A, §4).
- Accumulators are **bounded**: frequency uses a `dict[int,int]`/`dict[(number,position),int]` (≤ `(max-min+1)×numbers_to_select`), gaps use a last-seen `dict` — both O(distinct numbers), NOT O(n). We never materialize the draw list in memory (STE-08 scenario passes over 1M draws: `10^3`-row batches, constant heap).
- Time: O(n) draw reads + O(distinct numbers) accumulation = O(n) per full snapshot. Space: O(BATCH_SIZE + distinct numbers).
- **Incremental (C4/STE-06)** — when an `active` snapshot exists:
  - `delta = SELECT draw_number FROM draw WHERE lottery_id=:id AND is_deleted=0 AND draw_number > :draws_to ORDER BY draw_number` → if empty → return existing (no rewrite).
  - Fold delta into the **existing** `(number→count, (num,pos)→count, per-number gaps, null-aware averages)` accumulators by reprocessing only `delta` rows; **recompute the full metric outputs over the merged accumulator** inside the NEW snapshot's rows, but never read old draws (only the old summary) — the algorithm is "fold delta into a NEW snapshot", so a full scan of history is avoided and correctness is preserved. New `version = old.version + 1`, new checksum. Old stays `retired`.
- **Full rebuild (C4)** — no valid snapshot, or explicit `--scope=full`/rebuild CLI: recompute every metric from all draws of the lottery into a **new version** (never mutate a locked snapshot).
- **Checkpoints**: If a batch shows progress, optionally call `session.commit()` on a *separate* progress temp file — for simplicity, generation commits a single atomic transaction at the end (impossible to leave partial `stat_*` state on crash, matching dataset atomicity). For very long runs we keep the intermediate accumulator in memory (bounded, §above) and commit once; a crash discards no core change and regenerates cleanly.
- Strictly forbidden: `list_dataset_draw_ids`-style `list(...)` of every id, or loading full lot into memory.

### Batch failure policy (APPROVED)

A failed batch NEVER yields an `active` or `partial` snapshot. If any batch raises (DB error, timeout, engine exception), the generation run rolls back and marks the snapshot `status='failed'` (or writes no header at all — see below); it is never `ACTIVE`, never `PARTIAL`. Because generation commits a single atomic transaction at the end, a crash simply leaves NO snapshot row (nothing partial is persisted); an explicit engine failure during a (multi-commit, long-run) path marks `failed`. A resumed / retried generation ALWAYS creates a fresh snapshot row (new `version`), NEVER reuses or continues a `failed` snapshot. `failed` snapshots are dead metadata only and may be cleaned by retention, never read or continued.

## 4. Indexes (C7 / STE-09 reworded) — each justified

STE-09 is defined as: *"Frequency queries SHALL be indexed and justified by the access pattern they serve."* It does NOT mandate any specific `(lottery_id, number)` index. The `(lottery_id, number)` index on `draw_numbers` is REJECTED (no denormalization in Statistics v1 — avoids permanent redundancy and early denormalization of an FK already reachable via `DrawNumber→Draw→Lottery`; minimization over Core Domain).

Option chosen: **A (join-based filling)** — resolve the LOTTERY-SCOPED frequency access through the existing natural-join on `draw`; the only index needed is `draw_numbers(draw_id)` (already exists as FK? — verified; add if missing) to serve the batch keyset `JOIN draw ON draw.id = draw_numbers.draw_id WHERE draw.lottery_id = ? AND draw.is_deleted = 0`. Indexed `draw.points` (lottery_id) and `draw_number` columns are already covered by existing F2 indexes — `ix_draw_lottery_date` (0002) covers `lottery_id` leading and `draw_date`; `UNIQUE(lottery_id, draw_number)` covers `(lottery_id, draw_number)` for the batch `.` keyset over `draw_number`. Therefore **no new column** is required; STE-09 is satisfied by screening lotteries on `draw` and range/key-sset `draw_number` via existing `UNIQUE(lottery_id, draw_number)`, joined to `draw_numbers` on the FK `(draw_id)`. If benchmarks (Section `OPEN — evidence-gated`) show a residual full `draw_numbers` scan for frequency, the design documents (implicit) a desnormalization candidate for a FUTURE phase — never inside Statistics v1.

| Index | On | Access path it serves | Expected benefit |
|-------|----|------------------------|------------------|
| `ux_draw_lottery_draw_number` (EXISTING) | `draw(lottery_id, draw_number)` | lottery-scoped keyset `WHERE lottery_id=? AND draw_number>? ORDER BY draw_number` (batch generator + draw/window reads) | O(log n) range scan per lottery+keyset page; no full table read |
| `ix_draw_numbers_draw_id` (EXISTING FK, verify) | `draw_numbers(draw_id)` | join `draw_numbers→draw` for frequency / positions aggregation | turns the natural-key join into index-driven lookup, not nested-loops scan |
| `ix_draw_lottery_date` (EXISTING, 0002) | `draw(lottery_id, draw_date)` | optional last-window / metadata access on `draw_date` (metadata only, D3) | bounded window reads |
| `ix_snap_lottery_metric_status` (NEW) | `stat_snapshots(lottery_id, metric_set, status)` | `active` resolution on POST/incremental + every GET read | O(1) active lookup on small per-lottery list |
| `ix_stat_<payload>_snapshot_id` (NEW, explicit FK–index) | each `stat_*` payload `(snapshot_id)` | join active snapshot → payload in reads | join acceleration once snapshots large |

Decision: **no denormalization, no new column** — reuse existing `draw` indexes. Add NO new index without a concrete EXPLAIN/measure. If evidence (Section 11-EXPLAIN) shows a specific query still failing to scale, document a deferred denormalization proposal for a FUTURE phase (not v1). Risk: reused `ix_draw_lottery_date` leading covers lottery but frequency JOIN still reads `draw_numbers` via `(draw_id)=`; for large lotteries this index funnel is acceptable — the batch in section 3 already keyset-screens draws first and only joins the equal `draw_numbers(draw_id)` set relevant to each batch.

## 5. API (C5 / backend delta)

All responses in the standard envelope (REQ-02); `SuccessEnvelope` for 2xx, `ErrorEnvelope` for errors. Read/write strict separation — **no GET ever triggers generation** (C5/STE-10).

### `POST /api/v1/statistics/generate`
Body: `{ "lottery_code": str, "metrics": ["frequency","gaps","averages","positions","distributions","entropy"], "scope": "incremental"|"full" }` (`metrics` default `["core"]`; `scope` default `incremental`).
| | 200 | new/updated snapshot |
|---|---|---|
```json
{ "success": true, "data": {
    "snapshot_id": 7, "lottery_code": "pba",
    "version": "7", "generator_version": "1.0.0",
    "draws_from": 1, "draws_to": 112, "draw_count": 112,
    "checksum": "ab12…", "metric_set": "core", "incremental": true }
, "timestamp": "…|Z" }
```
**Idempotency (APPROVED)**: `POST /statistics/generate` MUST be idempotent. If an `active` snapshot already exists with the SAME `checksum` AND the SAME `generator_version` AND the same configuration (metric set + scope + lottery) — i.e. the request would reproduce an identical result — the endpoint returns that EXISTING snapshot (200) instead of generating a new row. It does NOT create a duplicate `version`. A request whose checksum/version/config differ from the active snapshot is NOT idempotent-equal and proceeds (incremental or new full version). Implementation: after computing the prospective checksum (without writing), compare against the active snapshot's `checksum`; on match return it; else persist normally.
Errors: unknown lottery → `RESOURCE_NOT_FOUND` 404 (matches `get_lottery_by_code`); unrecoverable engine failure → new `generation_error` (500); invalid payload → `validation_error` (422). Never fired during import (D6/STE-12).

### `GET /api/v1/statistics/{lottery_code}/frequencies?last=N`
| 200 | snapshot + `data.frequencies:[{number, count}]` (≤`last`, default 0=all) |
Missing snapshot → `SNAPSHOT_NOT_FOUND` (404), **never auto-precomputes** (STE-10/backend delta). Unknown lottery → `RESOURCE_NOT_FOUND` (404).

### `GET /api/v1/statistics/{lottery_code}/gaps?last=N`
Per-number gap summaries (`avg_steps`, `min_gap`, `max_gap`) from `stat_gaps`, bounded and on-demand.

### `GET /api/v1/statistics/{lottery_code}/averages`
`{ averages: { jackpot: {mean, non_null_count}, winners: {…} } }` (D4 NULL-handled), derived from `stat_averages`.

Error taxonomy to register: `generation_error → 500`, `SNAPSHOT_NOT_FOUND → 404`, `SNAPSHOT_LOCKED → 409` (attempted in-place mutation, actually unreachable by design).

## 6. CLI

Extends `cli.py` (argparse; `SessionLocal`; domain errors → stderr `error:[CODE] msg` + `exit 1`).

```
lip statistics generate --lottery <code> [--metrics core] [--scope incremental|full]
lip statistics rebuild  --lottery <code> --version <v>        # full rebuild as NEW version only
```
- `_cmd_statistics_generate`: resolve lottery (`NotFoundError`→404 path / exit 1), call service; print snapshot JSON (mirrors `_cmd_dataset_generate`).
- Scope `full` = full-rebuild. The rebuild command forces a new `version` and NEVER mutates a locked snapshot.
- No scheduler (D6/STE-12); trigger recorded `manual`/`cli`.

## 7. Snapshot Lifecycle
created (status active, is_locked=True, atomically written with payload) → **locked immutable** (never UPDATE after commit) → versioning (bump `version` on any new fold/rebuild) → replacement (new active, old → `retired` in same tx) → retention (configurable via **`Settings.stats_retention_generations`, default `10`** — a configuration value, NOT a hard-coded constant, per APPROVED decision; `retired` kept for repro until the retention job deletes beyond the configured count) → rollback (read `?version=`/point reads; old stays, no destructive mutate) → rebuild (new version). NEVER modify existing snapshots. A `failed` snapshot is dead metadata only (see §3 fail policy).

## 8. Generator Version

`STATS_GENERATOR_VERSION` in `statistics/generator.py` bumps ONLY when metric interpretation changes: metric definitions (e.g. gap meaning, distribution formula), rounding mode, or accumulated fold order that changes a sum (Requirement 8). NOT bumped on: app deploy, engine version, dataset re-import, or non-semantic changes. Independent of `settings.app_version` (engine_version) and of parser_version (F2). Each snapshot stores generator_version + engine_version side by side for audit and is compared in checksum (C2/STE-05).

## 9. Determinism Contract (C2/STE-05/Requirement 9)

Same lottery + `draw_count` set (`is_deleted=False`) + same generator_version ⇒ bit-identical outputs + equal snapshot checksum, across PG and SQLite.

- **Mandatory deterministic ORDER BY on EVERY aggregation** (augmented Requirement 9): each pass, fold, and delta MUST run with an explicit `ORDER BY draw.draw_number, draw_numbers.id`. The design NEVER relies on physical row order; the storage engine's default scan order is never assumed. This ordering is part of `generator_version` identity (a change to it bumps the version, §8).
- Stable iteration: `ORDER BY draw_number, id` (explicit id tie-break) for every pass/delta.
- No unordered float reduction: all accumulators are INTEGER exact sums/counts; averages use `Decimal` exact (non-unrolled). Float never enters the checksum path.
- Checksum = SHA-256 of canonical JSON `{lottery_id, metric_set, range [draws_from,draws_to], generator_version, engine_version, number[]:count/…, positions, gaps, averages, scalars}` with `sort_keys=True`, compact separators (copy the canonical serializer pattern from `import_service._dataset_checksum`).

## 10. Entropy (Shannon — APPROVED)

Stored as `stat_scalars(name='entropy')`. Fully deterministic; computed over normalized positional counts of ONE snapshot.

- **Formula**: `H = -Σᵢ pᵢ · log_b(pᵢ)` where `pᵢ = count(number=i) / Σⱼ count(j)` over main numbers in the lottery's range `[min_number..max_number]` (each drawn main number counted once per draw; positions not collapsed). `n` = distinct observed numbers in `[min..max]`; `Σ pᵢ = 1`.
- **Base**: `log_b` with **base 2** → unit = bits. Universe is `[min_number..max_number]` from the lottery rules (CD-08), NOT the observed sample, so the deterministic universe is fixed by rules.
- **Normalization**: distribution normalized by total draws in the covering snapshot's draw range (`draws_from..draws_to`), `is_deleted=False`; pᵢ = `draw_appearances(i)/total_main_draws`. Zero-appearance numbers contribute `pᵢ·log_b(pᵢ)=0` and are ENUMERATED (all `min..max` present in the Σ), so determinism holds even with sparse samples.
- **Interpretation**: higher H ⇒ flatter / more uniform frequency spread; H=0 ⇒ a single number always drawn. Reported with `generator_version`; any formula/base/universe change bumps `STATS_GENERATOR_VERSION` (§8).
- Determinism guard: every Σ iterates `number ASC` over `[min..max]`, all arithmetic in exact `Decimal`/integer accumulators; entropy value stored as `Numeric(20,8)` in `stat_scalars`; never float in the checksum path.

## 11. Risks

| Severity | Risk | Mitigation |
|----------|------|------------|
| CRITICAL | `draw_numbers` full scan for frequency | lottery-scoped keyset through existing `UX(lottery_id, draw_number)` + FK join on `draw_numbers(draw_id)` (Option A, §4); evidence-gated future denormalization documented, not shipped |
| CRITICAL | All-draws-in-memory blow-up (STE-08) | keyset batches (BATCH_SIZE) + bounded accumulators (O(distinct numbers)); bulk `list()` forbidden |
| WARNING | determinism drift across PG/SQLite float | INTEGER exact accumulators + Decimal means; never float in checksum |
| WARNING | retention creep (unbounded `retired`) | `RETENTION` generations config + retire-then-delete job |
| WARNING | N+1 in read serializer | repositories eager-load/selectin (`list_` with `selectinload`), never lazy in loops (pattern from `draw_repository`) |
| WARNING | lock contention on generation vs reads | snapshot reads immutable rows; single tx replaces atomically |
| LOW | crash mid-generate leaves no partial | single atomic commit at end; a failed batch marks `failed`, never `active`/`partial` (fail policy, §3) |

## 12. Rollback

- Alembic: `0005_…` downgrade drops `stat_*` + the `draw_numbers` index and its added column — exclusive, never touches `draw`/`draw_number` values or any F1/F2 table beyond that column.
- Git: `git revert` of the PR is safe because stats never mutates core rows.
- Data: old `retired` snapshots keep history; reads can `?version=` — no destructive rollback.
- Guarantee: no effect on F1/F2 tables/imports — statistics writes only `stat_*` (C3); no core-table change at all (Option A keeps `draw`/`draw_numbers` untouched).

## 13. Verification / Traceability (mandatory)

| Requirement | Coverage (design section) |
|-------------|---------------------------|
| STE-01 (independent stat_* schema, D2) | §2 all `stat_*` tables |
| STE-02 (strict read-only, C3) | §1 layer contract |
| STE-03 (draw_number axis/date metadata) | §3, §9 keypath `draw_number` |
| STE-04 (generator_version, no in-place) | §2 versioning, §7, §8 |
| STE-05 (bit-identical determinism) | §9 checksum |
| STE-06 (incremental vs full rebuild) | §3 incremental/full |
| STE-07 (NULL never impute) | §2 stat_averages (non_null_count) |
| STE-08 (batched streaming, C6) | §3 batch strategy |
| STE-09 (indexed frequency queries justified by access pattern) | §4 (Option A: existing `draw` indexes + FK join; NO denormalization) |
| STE-10 (hybrid; NO GET precompute) | §5 GET read contract |
| STE-11 (multi-lottery independence) | §2 snapshot lottery FK, §7 |
| STE-12 (manual only, no import hooks) | §5/§6 CLI/API, no import hooks |
| STE-13 (out of scope D5) | §6; Probability/ML/Prediction absent throughout |
| C1 (version bump rules) | §8 |
| C2 (determinism) | §9 |
| C4 (incremental bounding) | §3 |
| C5 (POST vs GET separation) | §5 |
| C7 (index justification) | §4 |
| APPROVED: Shannon entropy formula/base/normalization | §10 |
| APPROVED: retention as config (not constant) | §7 (`Settings.stats_retention_generations`) |
| APPROVED: mandatory deterministic ORDER BY in every aggregation | §9 |
| APPROVED: batch failure → never active/partial; resume = new snapshot | §3 fail policy |
| APPROVED: idempotent `POST /statistics/generate` (checksum+version+config match ⇒ return existing) | §5 |

**Decision → location** trace: D1→§1; D2→§2; D3→§2/§9; D4→§2/averages; D5→§6/STE-13; D6→§6; C1→§8; C2→§9; C3→§1/§3; C4→§3; C5→§5; C6→§3; C7→§4.

## Testing Strategy

| Unit | engine pure functions (fold, averages, gaps, entropy, distribution) deterministic fast tests |
| Integration | generation→snapshot→read path with tmp migrated DB (per `conftest`); incremental fold matches full-rebuild checksums |
| E2E | CLI `generate`/`rebuild`; POST/GET vs empty DB — SNAPSHOT_NOT_FOUND (no auto-compute); migration 0005 up/down in `test_migrations.py` |
| Migration test | assert `stat_*` tables + `stat_*` indexes exist at head; downgrade drops ONLY `stat_*`; core `draw`/`draw_numbers` untouched |

## Open Questions

- [ ] Exact entropy definition to pin in generator (default Shannon entropy over normalized positional counts) — resolved §10 (base-2 Shannon, rule-bounded universe); assert in tasks/test expectations.
- [ ] `RETENTION_GENERATIONS` default **RESOLVED** = 10, as config `Settings.stats_retention_generations` (not a constant); confirm value at archive.

## Threat Matrix (applicability)

Not applicable — this change introduces NO routing, shell-command, subprocess, VCS/PR automation, executable-classification, or process-integration boundary. The CLI is argparse-only (mirrors existing `lip`), never shells out, and only invokes in-process services. Matrix recorded as N/A.

## Migration / Rollout

Additive `0005_*` only. New `stat_*` tables + `stat_*` indexes. **No core-table change** (Option A: STE-09 satisfied by reusing existing `draw` indexes; `draw`/`draw_numbers` untouched). All `stat_*` tables empty until first manual generate; feature default on, no flag. Rollback drops all of it cleanly; nothing touches F1/F2.

**Evidence-gated denormalization (Option C)**: if — and only if — post-implementation benchmarks (EXPLAIN/measurement) prove the reindexed JOIN path still fails to scale for a specific real query, the design records a candidate denormalization (e.g. `draw_numbers.lottery_id` + index) as a DOCUMENTED proposal for a **future** phase, never implemented in Statistics v1.