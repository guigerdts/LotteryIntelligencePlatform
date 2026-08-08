# Tasks: Feature Engine (Fase 4) — Core-Domain First Slice

## Review Workload Forecast

Decision needed before apply: Yes
Chained PRs recommended: Yes
Chain strategy: stacked-to-main
400-line budget risk: Low

| Field | Value |
|-------|-------|
| Estimated changed lines | ~960 (3 PRs × ~260/360/340) |
| 400-line budget risk | Low (3-PR split keeps each ≤400) |
| Chained PRs recommended | Yes — user-mandated 3-PR split |
| Chain strategy | stacked-to-main (mirrors Fase 3) |
| Decision needed before apply | Yes — interactive mode; orchestrator reviews before sdd-apply |

### Suggested Work Units

| Unit | Goal | Likely PR | Focused test command | Runtime harness | Rollback boundary |
|------|------|-----------|----------------------|-----------------|-------------------|
| 1 | Core: registry+topo/cycle, provider Protocols, pure engine+fingerprint, ORM, migration 0006 | PR 1 | `backend/.venv/bin/pytest backend/tests/feature_engineering/test_registry.py backend/tests/feature_engineering/test_engine.py -q` | N/A (pure funcs + migration-only DB) | Revert migration 0006 + feature_engineering/ package; core untouched |
| 2 | Orquestación: service + repos + FE-01..10 registration + full/incremental + GF1/GF2 | PR 2 | `backend/.venv/bin/pytest backend/tests/feature_engineering/test_feature_engine_service.py backend/tests/feature_engineering/test_determinism.py -q` | `lip feature-engine generate` on tmp migrated DB | Revert service+repos; no API surface shipped |
| 3 | Surface: API+schemas+errors+CLI+E2E+GF1/GF2 final | PR 3 | `backend/.venv/bin/pytest backend/tests/api/test_feature_engine_api.py backend/tests/test_migrations.py -q` | `fastapi TestClient` + `lip feature-engine generate/rebuild` | Revert API router + CLI + error registrations |

### Gates (mandatory — verification gate of PR3)

- **GF1 — Feature Determinism**: same dataset + same Statistics snapshot + same registry + same fingerprint ⇒ byte-identical `feature_values`. Tasks P2-07 (authoritative) + P3-08 (e2e).
- **GF2 — Registry Isolation**: (a) registering a new feature does NOT change existing features' results (task P2-09, e2e P3-09); (b) a `future-statistics` feature stays declared but produces NO values (task P2-08, e2e P3-09).

### Out of Scope (explicit, NO tasks): ML · Probability · Prediction · Scheduler · Parallelization · Premature optimization · Graph Engine.

## PR1 — Core del Feature Engine

- [x] P1-01 `feature_engineering/features/*.py` — pure `compute(ctx)` for FE-01..FE-10 (draw_sum, draw_mean, draw_range, odd_even_ratio, low_high_ratio, consecutive_count, decade_distribution, repeated_from_previous, max_current_gap, current_frequency); INTEGER/`Decimal`, no float. **Verif**: unit each scenario FE-01..10.
- [x] P1-02 `tests/test_engine.py` RED first: determinism same input → identical output; FE-01..10 scenarios. `backend/.venv/bin/pytest .../test_engine.py -q`.
- [x] P1-03 `engine/registry.py` — frozen `FeatureDefinition` + `FeatureRegistry`: register deps, Kahn topo sort, cycle fail-fast reporting set, disabled/future dep → skip. **Verif**: `tests/test_registry.py` cycle + skip tests. FES-07.
- [x] P1-04 `engine/providers.py` — `DrawProvider`, `StatisticsProvider`, `DatasetProvider` Protocols (read-only, no precompute). **Verif**: FES-06 contract test — no import of `statistics`/`models`/repos.
- [x] P1-05 `engine/fingerprint.py` — canonical `json.dumps(sort_keys=True, separators=(",",":"))` + SHA-256. **Verif**: `tests/test_fingerprint.py` stable/sort. FES-05.
- [x] P1-06 `engineering/engine.py` — pure orchestrator: topo-exec enabled features → feature_values; `future-statistics` declared, never scheduled. **Verif**: FES-08 test. GF2 base.
- [x] P1-07 `models/feature_snapshot.py` + `feature_value.py` — ORM per design §2. Register in `models/__init__.py`. FES-01/03/04.
- [x] P1-08 `alembic/versions/0006_feature_tables.py` — create `feature_snapshots`, `feature_values` + 3 indexes; `down_revision="0005_stat_tables"`. **Verif**: migration up/down in `tests/test_migrations.py` drops only `feature_*`. FES-10.

## PR2 — Orquestación

- [x] P2-01 `services/errors.py` + `api/errors.py` — feature errors: `FeatureDefinitionError`(definition_error→500), `SnapshotNotFoundError`(SNAPSHOT_NOT_FOUND→404), `SnapshotLockedError`(SNAPSHOT_LOCKED→409), `GenerationError`(generation_error→500), mapped to HTTP status (mirror api/errors.py + services/errors.py). **Verif**: `tests/test_api_errors.py` (13 passed).
- [x] P2-02 `repositories/feature_snapshot_repository.py` — create/list, `get_active(lottery,feature_set)`, `latest`, retire-active same-tx, `find_by_fingerprint` (mirror stat repo). FES-01.
- [x] P2-03 `repositories/feature_value_repository.py` — batched `bulk_insert` payload, deterministic `ORDER BY draw_number, id`. FES-01.
- [x] P2-04 `feature_engine_service.py` — canonical `FEATURE_GENERATOR_VERSION` + register FE-01..FE-10 (`source="core"`) + one `future-statistics` declared. FES-08.
- [x] P2-05 `feature_engine_service.py` — orchestrator: validate budget/draws; full vs incremental (delta>draws_to fold); compute + fingerprint + atomic single tx; lock→retire old active→new active; failed→`failed` never active. FES-04. 
- [x] P2-06 RED→GREEN `tests/feature_engine_service.py` (tmp migrated DB): incremental matches full-rebuild checksum; atomic; batch-fail→failed; read-only (Core/stat_* byte-identical). FES-01/02/04.
- [x] P2-07 `tests/test_determinism.py` — **GF1 authoritative**: two independent generations ⇒ identical `feature_values`. FES-05.
- [x] P2-08 `tests/test_registry_isolation.py` — **GF2(b)** future-statistics produces NO persisted valued. FES-08.
- [x] P2-09 `tests/test_registry_isolation.py` — **GF2(a)** registering a new feature doesn't alter existing feature outputs. FES-07.

## PR3 — Surface

- [x] P3-01 `schemas/feature_engine.py` — GenerateRequest(`lottery_code`, scope full/incremental), snapshot+feature read models (statistics parity). FES-09.
- [x] P3-02 `api/v1/feature_engine.py` — `POST /feature-engine/generate` (idempotent) + `GET /{code}/features?...`; reads never precompute; missing snapshot→404. FES-09.
- [x] P3-03 `api/v1/router.py` — `include_router(feature_engine_router)`.
- [x] P3-04 `cli.py` — `feature-engine generate`/`rebuild` (mirror statistics; argparse only), print snapshot JSON. FES-09.
- [x] P3-05 RED tests `tests/api/test_feature_engine_api.py` — POST idempotent, unknown lottery 404, GET missing snapshot 404+no-autocreate. FES-09.
- [x] P3-06 E2E tests — CLI generate/rebuild; import never auto-generates (FES-09). `tests/test_feature_engine_e2e.py`.
- [x] P3-07 `tests/test_migrations.py` — 0006 head + downgrade drops only `feature_*`; core/stat_* intact. FES-10.
- [x] P3-08 `tests/test_determinism.py` — **GF1 e2e** repeat determinism via CLI/API (checksum+row count+content+insertion order+hash). FES-05.
- [x] P3-09 `tests/test_registry_isolation.py` — **GF2 e2e** via surface: add feature → Δ only that feature; future feature no rows. FES-07/08.
- [x] P3-10 **Final gates GF1+GF2** recorded as verify step; G1 ruff, G2 pytest full, G3 upgrade head 0006, G4 downgrade chain, G7 API contract, no regression/debt.
- [x] P3-11 docs/comments: feature-engine determinism contract + GF1/GF2 explanations.

## Rules
- Strict TDD (`backend/.venv/bin/pytest`); RED tests before production. Tasks ordered by dependency across PR1→PR3 (stacked).