# Exploration — Fase 1 Core Domain

**Change**: `fase-1-core-domain` · **Store**: openspec · **Artifact**: exploration
**Agnostic to engine**: dialect-portable SQLAlchemy model, no PG-only types, no per-migration SQLite-specific DDL.

## 1. Status

`success`

## 2. Executive Summary

Fase 1 models the five core entities (Lottery, Draw, DrawNumber, SuperNumber, Dataset) on the Fase 0 ORM seam (`repositories.base.Base`; engine/session from settings). The three primary sources (DATABASE_SCHEMA.md, SYSTEM_ARCHITECTURE.md, archived backend spec) are consistent for the Fase 1 tables, but expose three HARD items the user must validate before implementation: where lottery rules live (SQL columns vs external config), SuperNumber cardinality/optionality, and the Draw natural-key/dedup constraint that Fase 2 depends on. Everything else is a recorded CLARIFICATION or MINOR naming/formatting convention. The exploration is model-ready; no implementation code was written.

## 3. Inconsistency Audit Findings

Sources: **DS** = DATABASE_SCHEMA.md, **SA** = SYSTEM_ARCHITECTURE.md, **SP** = archived backend spec (`openspec/specs/backend/spec.md`, REQ-xx), plus **IM** = IMPLEMENTATION_ROADMAP.md, **AP** = API_SPECIFICATION.md, Fase 0 `design.md`/`exploration.md`.

### HARD — must resolve via user decision before modeling

**[H1] Lottery rules live in the DB vs outside code**
- DS §4 `lottery` columns: `id, code, name, country, description, min_number, max_number, numbers_to_select, super_number_min, super_number_max, created_at` — i.e. rule attributes persisted on the table.
- SA §9: "Toda config deberá almacenarse fuera del código. … Loterías. Rangos de números. …" and SA §11: "incorporar nuevas loterías únicamente agregando su config y reglas, sin modificar el núcleo."
- Prior interpretation: Fase 0 exploration.md line 104 defers "lotteries registry (rules live outside code per §9/§11 — actual registry in Fase 1/2)"; config.yaml context: "config outside code".
- Why it matters: decides whether `min_number…super_number_max` are columns persisted on `lottery` or are read from a file-based registry. Affects Fase 2 import validation, Generator (F13), Dashboard config, ML bounds.
- Note: "outside the code" ≠ "outside the DB"; a DB row satisfies the literal text. DS is the schema authority and prescribes the columns. → Decision **[D1]**.

**[H2] SuperNumber cardinality and optionality unstated**
- DS §6 `super_number` = one table `(id, draw_id, value)`, no `position`, no multiplicity; `lottery.super_number_min/max` implies a per-lottery optional superball; the general diagram shows a single `Draw→SuperNumber`.
- Why it matters: 1..1 vs 0..1 vs N changes the table (UNIQUE on draw_id) and ML feature alignment (single scalar superball vs a sequence); multi-star games (EuroMillions-type) need N. → **[D2]**.

**[H3] Draw natural dedup key absent**
- DS §8 indices only (`draw_date, draw_number, lottery_id`); no UNIQUE constraint anywhere. DS §6: "no eliminar sorteos históricos", "no modificar resultados oficiales". IM: Fase 2 "Detectar duplicados".
- Why it matters: AP §4 exposes `POST /draws/import` and `/draws/upload` → re-imports are expected; without a unique constraint duplicates corrupt every feature/ML/stat table. The constraint must ship in the Fase 1 migration or Fase 2 is blocked. → **[D3]**.

### CLARIFICATION — pick and record a convention

- **[C1]** Nullability is not marked anywhere in DS (no NOT NULL annotations). Record: PK/FK/identity NOT NULL; `draw.jackpot`, `draw.winners` NULL; `lottery.super_number_min/max`, `description` NULL; `datasets.checksum` NULL (computed in F2).
- **[C2]** `jackpot`/`winners` types. Use `Numeric(18,2)` and integer (both nullable) for portability/safety (SQLite has no DECIMAL, float money is unsafe). → **[D7]**.
- **[C3]** `draw_date` is a calendar `Date`, not datetime, matching API `date_from/date_to` filters; ingestion time is `created_at`.
- **[C4]** Timestamps UTC, `DateTime(timezone=True)`, matching DS "UTC / ISO 8601" (§11) and future PostgreSQL TIMESTAMPTZ. → **[D4]**.
- **[C5/C6]** Dataset composition: `datasets` (version metadata + `checksum`) and a `dataset_draws` link (Dataset↔Draws). Model the link in F1 (structural); `checksum`=SHA-256 over canonical serialize of the draw set, computed in F2, stored nullable. → **[D5]**, **[D6]**.
- **[C7]** Intra-draw uniqueness: enforce `UNIQUE(draw_id, position)` and `UNIQUE(draw_id, number)` (numbers do not repeat within one draw); supports F2 validation and exporter integrity.
- **[C8]** `lottery.numbers_to_select` must equal `COUNT(draw_numbers)` per draw — a cross-row invariant not declarable portably; validate in F2 import application logic, document it.
- **[C9]** Alembic is not yet a dependency (`backend/pyproject.toml`). Place `backend/alembic/`, `env.py` → `target_metadata = Base.metadata`, autogenerate, use `batch_mode` for SQLite DDL changes, only portable ops, no PG-native types. → **[D10]**.
- **[C10]** Delete semantics vs DS §6. CRUD (IM Fase 1) and API list no `DELETE /draws`, and §6 forbids removing historical draws. Soft-delete (`is_deleted`) + FK RESTRICT, or omit draw DELETE entirely. → **[D8]**, **[D9]**.
- **[C11]** `draw.draw_number` column name collides with the `DrawNumber` entity name (winning-numbers list). Keep doc-conformant names and document the distinction; optionally alias the ORM attribute.
- **[C12]** `country` as ISO 3166-1 alpha-2 `String(2)`, app-validated; no separate country lookup table in F1.
- **[C13]** DS §10 allows optional UUID for future export/sync; **skip** UUID columns in F1 (surrogate int PK per convention), add via migration when export/sync lands.
- **[C14]** No DB-level enumerations anywhere; keep `String`/Python enums (`Enum(native_enum=False)` → VARCHAR+CHECK) so migrations stay dialect-neutral → **[D11]**.

### MINOR — naming/formatting

- **[M1]** Pluralization is inconsistent in DS (`draw_numbers` vs singular `super_number`); keep the DS table names verbatim as the migration contract.
- **[M2]** DS §5 index list includes future tables (feature_id, model_id, experiment_id, strategy_id). Only `draw_date/draw_number/lottery_id` are F1; create those now, the rest later.
- **[M3]** Docs Spanish vs artifacts English — already resolved convention (config.yaml context); no action.
- **[M4]** AP has no `/datasets` endpoints; Dataset CRUD has no API contract, and lottery filter uses `?lottery=<code>` → maps to `lottery.code`. CRUD must expose code-based lookup; Dataset endpoints are deferred until AP is updated (or a chained API delta).
- **[M5]** The migration dialect constraint is REQ-05 ("SQLite bootstrap / config-only dialect"), NOT REQ-04 (REQ-04 is Logging). Reason for quoting REQ-05 when citing Fase 0.
- **[M6]** DS §2, "3NF as base": verified — the F1 tables satisfy 3NF (attributes depend on PK, no transitive dependencies, `code` is a candidate key). H1 is a rules-placement tension, not a 3NF violation.

**Engine/dialect check — passed.** No PostgreSQL-only types (ARRAY/JSONB/ENUM/UUID) are used in the F1 tables, so the SQLite→PostgreSQL config-only swap (REQ-05) is safe at model scope. Confirmed consistent with DS header "Motor: SQLite (Compatible con PostgreSQL)" and DS §9 "Cambiar de SQLite a PostgreSQL con impacto mínimo".

## 4. Proposed Entity / Relationship Model

All models subclass `Base` (`repositories.base.py`, Fase 0 seam), located at `backend/app/models/<entity>.py`, re-exported in `models/__init__.py` (as the alembic `target_metadata = Base.metadata` source), SQLAlchemy 2.0 `Mapped`/`mapped_column`.

| Entity / table | Key columns | PK / FK / relationships | Constraints |
|---|---|---|---|
| **Lottery** `lottery` | id: Int PK; code: String(32) NN UNIQUE; name: String(128) NN; country: String(2) NN; description: Text; min_number: Int NN; max_number: Int NN; numbers_to_select: Int NN; super_number_min: Int; super_number_max: Int; created_at: DateTime(tz) NN | PK id; `lottery.draws` 1:N | CHECK min<max; CHECK numbers_to_select ≤ max−min+1; CHECK super_min ≤ super_max (portable) |
| **Draw** `draw` | id: Int PK; lottery_id: Int NN FK idx; draw_number: Int NN; draw_date: Date NN; jackpot: Numeric(18,2); winners: Int; created_at: DateTime(tz) NN | FK→lottery.id; **UNIQUE(lottery_id, draw_number)** 🔗[D3]; index (lottery_id, draw_date); `draw.numbers` 1:N; `draw.super_number` 1:0..1 | FK + UNIQUE per above |
| **DrawNumber** `draw_numbers` | id: Int PK; draw_id: Int NN FK idx; position: Int NN; number: Int NN | FK→draw.id | UNIQUE(draw_id, position); UNIQUE(draw_id, number) 🔗[C7] |
| **SuperNumber** `super_number` | id: Int PK; draw_id: Int NN FK **UNIQUE**; value: Int NN | FK→draw.id, UNIQUE(draw_id) → 0..1 per draw 🔗[D2] | CHECK value in lottery super range (application) |
| **Dataset** `datasets` | id: Int PK; version: String(32) NN UNIQUE; description: Text; checksum: String(64); created_at: DateTime(tz) NN | PK id | UNIQUE(version) 🔗[D16] |
| **DatasetDraws** (join) `dataset_draws` | id: Int PK; dataset_id: Int NN FK; draw_id: Int NN FK; created_at: DateTime(tz) NN | FK→datasets.id; FK→draw.id (idx) | UNIQUE(dataset_id, draw_id) 🔗[D5] |

SQLAlchemy / alembic mapping notes:
- Repos: Fase 0 `base.py` only defines `Base`, `engine`, `SessionLocal`, `get_db`. Fase 1 adds per-entity repositories (e.g. `repositories/lottery_repository.py`) doing CRUD over the DI `Session`; whether a generic `BaseRepository` is introduced is a design-phase decision.
- Pydantic `schemas/` Create/Update/Read per entity feed the CRUD endpoints under `api/v1`; envelope per REQ-02; note: `code`-based lookup must be exposed for the AP `?lottery=<code>` filter.
- Money: `Numeric(18,2)`; timestamps `DateTime(timezone=True)` + `server_default=func.now()`; no DB-level enums (C14).

## 5. Cross-Phase Modeling Decisions (for user validation)

Each decision lists: the decision, why it affects later phases, options, recommendation.

- **[D1] Rules registry location — persist lottery rules as columns vs external file registry. Matters: F2 import validation, Generator F13, Dashboard config, ML bounds; resolves H1. Recommendation: persist rules on `lottery` (DS authority); seed initial registry via config; state "outside code" satisfied because a DB row is not code.**
- **[D2] SuperNumber cardinality — 0..1 (UNIQUE draw_id) vs 1..1 vs N. Matters: ML feature alignment, F2 import mapping, multi-star games; H2. Recommendation: 0..1, document multi-star as future migration.**
- **[D3] Draw dedup key — UNIQUE(lottery_id, draw_number) vs (lottery_id, draw_date) vs both. Matters: F2 duplicate detection (roadmap criterion), re-import idempotency, data integrity. H3. Recommendation: (lottery_id, draw_number) as the primary/unique; keep (lottery_id, draw_date) as index (lotteries can draw multiple times a day).**
- **[D4] Timestamp policy — tz-aware UTC `DateTime(timezone=True)` vs naive. Matters: backtest windows F10, time-series features F4, reproducibility, PG parity (REQ-05). Recommendation: tz-aware UTC.**
- **[D5] Dataset composition — immutable link (datasets + dataset_draws M:N) vs materialized snapshot vs view. Matters: F2 versioning, F4 feature scoping, ML splits F7, reproducibility. Recommendation: link composition now; materialize later only if ML perf demands.**
- **[D6] dataset_draws timing — model the join in F1 or F2. Matters: F1 CRUD completeness, avoids F2 schema churn. Recommendation: F1 (Dataset CRUD meaningless without the link), F2 builds versioning logic on it.**
- **[D7] jackpot/winners typing & optionality — Numeric(18,2) nullable + int winners nullable vs non-null or int-cents. Matters: F2 normalization, statistics summaries, backtesting. Recommendation: Numeric(18,2) nullable; winners int nullable.**
- **[D8] Draw delete semantics — no DELETE (hard) / soft-delete `is_deleted` flag / hard delete. Matters: §6 "no eliminar sorteos", audit F8, re-import corrections, dataset integrity. Recommendation: soft-delete flag + FK RESTRICT; no hard `DELETE /draws`.**
- **[D9] Lottery delete semantics — RESTRICT vs CASCADE vs soft-delete. Matters: §6; API spec exposes `DELETE /lotteries/{id}`. Recommendation: RESTRICT when draws exist.**
- **[D10] Alembic placement & portability — backend/alembic/ (env.py → Base.metadata, batch_mode for SQLite) vs Database/migrations. Matters: REQ-05 config-only dialect swap, reproducibility (DoD). Recommendation: backend/alembic/ + add alembic dep, portable operations only.**
- **[D11] Enum handling — Python enum + String(varchar) vs SQLAlchemy Enum(native_enum=False) vs PG-native ENUM. Matters: future status columns (training_runs, model_versions), dialect swap. Recommendation: no DB-native enums; Enum(native_enum=False) if an enum is ever needed.**
- **[D12] draw_date semantics — `Date` calendar vs `DateTime`. Matters: time-series alignment F4/F7, API filters. Recommendation: `Date` + separate `created_at`.**
- **[D13] Raw vs derived persistence — F1 stores ONLY raw official results (draw / draw_numbers / super_number); derived values land later in `feature_value` (F4). Matters: ML leakage prevention, reproducibility. Recommendation: raw-only in F1.**
- **[D14] country normalization — ISO 3166-1 alpha-2 `String(2)` vs free text. Matters: multi-country expansion §11, dashboard grouping. Recommendation: alpha-2 code, app-validated.**
- **[D15] draw_number naming collision — keep DS column `draw_number` vs `official_number`. Matters: API surface, F2 importer mapping, readability. Recommendation: keep doc-conformant `draw_number`; docstring note.**
- **[D16] Dataset version uniqueness — `UNIQUE(version)` global (datasets are not lottery-scoped per DS) vs per-lottery. Matters: training_runs.dataset_id, reproducibility. Recommendation: global `UNIQUE(version)`.**
- **[D17] Lottery DELETE after draws — RESTRICT / CASCADE supersede [D9] if combined; keep a single delete policy decision covering #D8+#D9 to avoid contradiction.**

Reconciliation with Fase 0 REQ-05: the model uses only portable columns (`Numeric`, `Date`, `DateTime(timezone=True)`, `String`), no PG-only types and no DB enums → the SQLite→PostgreSQL config-only swap and REQ-05 "no SQLite-only path outside the ORM boundary" both hold. No hard‑coded SQLite path is referenced; the engine stays `settings.database_url`-driven per REQ-05 (not REQ-04 — M5).

## 6. Artifacts

- `openspec/changes/fase-1-core-domain/exploration.md` (this file, flat-file convention)
- Engram: topic `sdd/fase-1-core-domain/explore`, type architecture, `capture_prompt=false`

## 7. Next Recommended

`propose`. No hard blocker blocks proposing: surface the HARD decisions `[D1]`, `[D2]`, `[D3]` (and the D-list) to the user, then feed resolutions into spec & design.

## 8. Risks

- `CRITICAL` — **[D1]** unresolved rules location → wrong `lottery` columns cascade through F2–F14.
- `CRITICAL` — **[D2]** wrong SuperNumber cardinality → F2 import mapping and ML feature alignment broken.
- `CRITICAL` — **[D3]** missing dedup key → F2 duplicate detection impossible; statistics/ML silently corrupted by re-imports.
- `WARNING` — **C1/C2/C7/C10**: if not pinned in design, nullability, money type, intra-draw uniqueness and delete semantics drift from DS (integrity gaps).
- `WARNING` — **REQ-05** portability: a migration using PG-only types or SQLite-isms breaks the config-only swap; enforce in design and verify.
- `WARNING` — **[D10]** alembic not yet a dependency; it is F1 implementation scope and must be planned around `Base.metadata`.
- `LOW` — [M4] Dataset API contract gap; [M1] pluralization cosmetics; [M6] verified non-issue.

## 9. Skill Resolution

`paths-injected` — 3 skills loaded from orchestrator-provided paths (sdd-explore, _shared/sdd-phase-common, _shared/openspec-convention).

## Key Learnings

1. DATABASE_SCHEMA persists lottery rules as `lottery` columns while SYSTEM_ARCHITECTURE §9/§11 demand rules outside the code — the central HARD decision [D1].
2. The Draw dedup unique constraint must ship in the Fase 1 migration for Fase 2 duplicate detection (roadmap criterion).
3. The authoritative SQLite dialect constraint is archived REQ-05 (SQLite bootstrap / config-driven), not REQ-04 (Logging).
4. No PG-only types or DB-level enums appear in the F1 entity tables, so the SQLite→PostgreSQL config swap is safe at model scope.
5. Alembic is not a declared dependency yet; adding it and wiring `Base.metadata` is a planned F1 seam, not Fase 0 code.