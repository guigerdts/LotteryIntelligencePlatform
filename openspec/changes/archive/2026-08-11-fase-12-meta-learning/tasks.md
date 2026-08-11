# Tasks: F12 — Meta Learning

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | 600–750 |
| 400-line budget risk | High |
| Chained PRs recommended | Yes |
| Suggested split | PR 1 (S1) → PR 2 (S2) → PR 3 (S3) |
| Delivery strategy | auto-chain |
| Chain strategy | stacked-to-main |

Decision needed before apply: No
Chained PRs recommended: Yes
Chain strategy: stacked-to-main
400-line budget risk: High

### Suggested Work Units

| Unit | Goal | Likely PR | Focused test command | Runtime harness | Rollback boundary |
|------|------|-----------|----------------------|-----------------|-------------------|
| S1 | Foundation: migration + models + types + package seam | PR 1 | `backend/.venv/bin/pytest tests/meta/test_types.py tests/meta/test_context.py -v` | N/A — unit tests only | Remove `meta/types.py`, `meta/context.py`, `meta/version.py`, `meta/__init__.py`, `models/meta_*.py`, migration 0014 |
| S2 | Core logic: normalization + scoring + ranking + selection + snapshot_store | PR 2 | `backend/.venv/bin/pytest tests/meta/test_normalization.py tests/meta/test_scoring.py tests/meta/test_ranking.py tests/meta/test_selection.py tests/meta/test_snapshot_store.py -v` | N/A — unit tests only | Remove `meta/normalization.py`, `meta/scoring.py`, `meta/ranking.py`, `meta/selection.py`, `meta/snapshot_store.py` |
| S3 | Surface: service + API + CLI + errors + integration tests | PR 3 | `backend/.venv/bin/pytest tests/meta/test_meta_service.py tests/meta/test_meta_api.py tests/meta/test_meta_cli.py -v` | `lip meta rank --lottery-id 1` | Remove `services/meta_service.py`, `api/v1/meta.py`, `schemas/meta.py`, `cli.py` additions |

## Phase 1: Foundation — Migration + Models + Types + Package Seam

- [x] T-META-001 | Create `alembic/versions/0014_meta_tables.py`: tables `meta_rankings`, `meta_ranking_entries`, `meta_selections`, `meta_selection_entries` with CHECK constraints, unique `(lottery_id, context_hash, fingerprint)`, indexes. Downgrade drops 4 tables in order. | `alembic/versions/0014_meta_tables.py` | None | META-015 | Test: `alembic upgrade 0014` creates 4 tables; `alembic downgrade -1` drops only meta_* | ~80 impl |
- [x] T-META-002 | Create ORM models: `MetaRanking` (8 cols), `MetaRankingEntry` (7 cols), `MetaSelection` (8 cols), `MetaSelectionEntry` (8 cols) mirroring snapshot pattern. | `models/meta_ranking.py`, `models/meta_ranking_entry.py`, `models/meta_selection.py`, `models/meta_selection_entry.py` | T-META-001 | META-015 | Test: models instantiate, `__table_args__` has correct constraints, FK RESTRICT | ~50 impl |
- [x] T-META-003 | Modify `models/__init__.py` to re-export `MetaRanking`, `MetaRankingEntry`, `MetaSelection`, `MetaSelectionEntry` for alembic `target_metadata`. | `models/__init__.py` | T-META-002 | META-015 | Test: `from backend.app.models import MetaRanking` succeeds | ~3 impl |
- [x] T-META-004 | Create `meta/types.py`: `ContextVector`, `WeightConfig`, `RankingEntry`, `SelectionEntry` frozen dataclasses. `WeightConfig.validate()` rejects zero sum. | `meta/types.py` | None | META-001, META-019 | Test: dataclass instantiation, immutability, zero-sum raises ValueError | ~35 impl |
- [x] T-META-005 | Create `meta/version.py`: `META_LEARNING_VERSION = "1.0.0"`. | `meta/version.py` | None | META-015 | Test: constant equals `"1.0.0"` | ~3 impl |
- [x] T-META-006 | Create `meta/context.py`: `resolve_context_vector(lottery_id, engine_type, db)` reads draws_from/draws_to/cut/window from engine snapshots; `compute_context_hash(vector)` returns SHA-256 hex. | `meta/context.py` | T-META-004 | META-003, META-011, META-012 | Test: same inputs → same hash; variable change → different hash; lottery isolation | ~35 impl |
- [x] T-META-007 | Create `meta/__init__.py` package seam — docstring only, no logic. | `meta/__init__.py` | None | — | Test: `import backend.app.meta` succeeds | ~3 impl |
- [x] T-META-008 | Write RED+GREEN tests for types and context: dataclass creation, WeightConfig validation, context hash determinism, context hash sensitivity, lottery isolation. | `tests/meta/__init__.py`, `tests/meta/test_types.py`, `tests/meta/test_context.py` | T-META-004, T-META-006 | META-001, META-003, META-012, NFR-META-01 | All type/context tests pass via `pytest tests/meta/test_types.py tests/meta/test_context.py` | ~60 test |

## Phase 2: Core Logic — Normalization + Scoring + Ranking + Selection + Store

- [x] T-META-009 | Create `meta/normalization.py`: `COMMON_METRICS` list, `ENGINE_EXCLUDED` set, `normalize_per_engine(snapshots)` returns per-engine min-max normalized metrics, `consistency_score` inverted. Missing metric → 0.0. Constant values → 0.0. | `meta/normalization.py` | T-META-004 | META-002 | Test: per-engine min-max correct; consistency inversion; missing→0.0; constant→0.0; engine-specific excluded | ~55 impl |
- [x] T-META-010 | Create `meta/scoring.py`: `DEFAULT_WEIGHTS` dict, `validate_weights(weights)`, `compute_score(normalized_metrics, weights)` weighted sum. | `meta/scoring.py` | T-META-004, T-META-009 | META-001, META-019 | Test: default weights sum=1.0; zero-sum raises; weighted sum correct; missing metric contributes 0.0 | ~40 impl |
- [x] T-META-011 | Create `meta/ranking.py`: `build_ranking_entries(scored_snapshots)` stable sort descending via `np.argsort(kind='stable')`, `compute_fingerprint(lottery_id, context_hash, entries)` SHA-256. | `meta/ranking.py` | T-META-004, T-META-010 | META-005, META-007, META-009, NFR-META-01, NFR-META-10 | Test: descending order; stable sort preserves equal-score order; fingerprint idempotent; different data → different fingerprint | ~50 impl |
- [x] T-META-012 | Create `meta/selection.py`: `select_top_k(ranking_entries, top_k, min_score)` filters by threshold, takes top-K. | `meta/selection.py` | T-META-004 | META-006, META-020 | Test: top-K correct; threshold filtering; insufficient qualifying returns fewer; default K=5 | ~30 impl |
- [x] T-META-013 | Create `meta/snapshot_store.py`: `MetaSnapshotStore` with `next_version(lottery_id, context_hash)`, `find_by_fingerprint(fp)`, `create_active_ranking(...)`, `create_active_selection(...)`, `get_rankings(lottery_id, context_hash)`, `get_selections(lottery_id, context_hash)`. Atomic writes, lifecycle transitions, idempotency. | `meta/snapshot_store.py` | T-META-002 | META-005, META-007, META-008, META-010 | Test: next_version monotonic; idempotent fingerprint; lifecycle active→retired; atomic write; lottery isolation | ~80 impl |
- [x] T-META-014 | Write RED+GREEN tests for normalization, scoring, ranking, selection, snapshot_store: min-max correctness, weighted sum, stable sort, top-K filtering, version monotonicity, fingerprint idempotency, lifecycle transitions, atomic writes. | `tests/meta/test_normalization.py`, `tests/meta/test_scoring.py`, `tests/meta/test_ranking.py`, `tests/meta/test_selection.py`, `tests/meta/test_snapshot_store.py` | T-META-009 through T-META-013 | META-001–META-012, NFR-META-01–NFR-META-05, NFR-META-10 | All core logic tests pass | ~120 test |

## Phase 3: Surface — Service + API + CLI + Errors + Integration

- [x] T-META-015 | Modify `services/errors.py`: add `MetaServiceError(ServiceError)` and 6 error codes as class constants (`META_RANKING_NOT_FOUND`→404, `META_SELECTION_NOT_FOUND`→404, `META_NO_ENGINE_DATA`→404, `META_WEIGHTS_INVALID`→422, `META_TOP_K_INVALID`→422, `META_DUPLICATE_RANKING`→409). | `services/errors.py` | None | META-016 | Test: `MetaServiceError.__mro__` includes `ServiceError`; each code correct | ~25 impl |
- [x] T-META-016 | Modify `api/errors.py`: add 6 entries to `_CODE_TO_STATUS` mapping for MetaServiceError codes. | `api/errors.py` | T-META-015 | META-016 | Test: each code maps to correct HTTP status | ~8 impl |
- [x] T-META-017 | Create `services/meta_service.py`: `MetaService` with `rank(lottery_id, weights?)`, `get_ranking(lottery_id, context_hash?)`, `select(lottery_id, top_k?, min_score?)`, `get_selection(lottery_id, context_hash?)`. Orchestrates context→normalize→score→rank→select→persist. Session injection. | `services/meta_service.py` | T-META-006, T-META-009 through T-META-013, T-META-015 | META-001–META-012, META-016, META-018 | Test: full rank→select workflow, idempotency, 404 for missing lottery, weight validation, top_k validation | ~90 impl |
- [x] T-META-018 | Create `schemas/meta.py`: Pydantic v2 request/response schemas (`RankRequest`, `RankingResult`, `RankingSnapshot`, `SelectRequest`, `SelectionResult`, `SelectionSnapshot`). | `schemas/meta.py` | None | META-013 | Test: schema creation, validation, extra fields rejected | ~50 impl |
- [x] T-META-019 | Create `api/v1/meta.py`: API router with 4 endpoints (`POST /meta/rank`, `GET /meta/ranking`, `POST /meta/select`, `GET /meta/selection`). Standard envelope `{success, data|error, timestamp}`. | `api/v1/meta.py` | T-META-017, T-META-018 | META-013 | Test: each endpoint returns correct status and payload; 404 for missing lottery | ~70 impl |
- [x] T-META-020 | Modify `api/v1/router.py`: include `meta_router` with prefix `/meta`. | `api/v1/router.py` | T-META-019 | META-013 | Test: `GET /meta/ranking` route resolves | ~3 impl |
- [x] T-META-021 | Modify `cli.py`: add `lip meta` subparser with 4 subcommands (`rank`, `ranking`, `select`, `selection`). stdlib argparse. JSON output. | `cli.py` | T-META-017 | META-014 | Test: `lip meta rank --lottery-id 1` outputs JSON; parity with API | ~50 impl |
- [x] T-META-022 | Write RED+GREEN tests for service: rank→select workflow, idempotency (same fingerprint returns existing), 404 META_NO_ENGINE_DATA, weight validation 422, top_k validation 422, lottery isolation, failed-run exclusion. | `tests/meta/test_meta_service.py` | T-META-017 | META-001–META-012, META-016 | All service tests pass via `pytest tests/meta/test_meta_service.py` | ~90 test |
- [x] T-META-023 | Write RED+GREEN integration tests for API: 4 endpoints, error codes (404, 422, 409), envelope format, idempotent responses. | `tests/meta/test_meta_api.py` | T-META-019 | META-013, META-016 | All API tests pass via `pytest tests/meta/test_meta_api.py` | ~70 test |
- [x] T-META-024 | Write RED+GREEN tests for CLI: 4 commands, JSON output, parity with API. | `tests/meta/test_meta_cli.py` | T-META-021 | META-014 | All CLI tests pass via `pytest tests/meta/test_meta_cli.py` | ~40 test |

## Traceability Matrix

| Requirement | Tasks | Test Scenarios |
|-------------|-------|----------------|
| META-001 Weighted scoring | T-META-004,010,017,022 | default weights, per-lottery override, zero-sum rejected |
| META-002 Normalization | T-META-009,014,022 | per-engine min-max, engine-specific excluded, missing→0.0 |
| META-003 Context resolution | T-META-006,008 | deterministic hash, hash changes on variable, lottery isolation |
| META-004 Failed run exclusion | T-META-009,017,022 | failed snapshot excluded, active included |
| META-005 Ranking | T-META-011,013,014 | descending order, supersedes old, stable sort, version monotonic |
| META-006 Selection | T-META-012,013,014 | top-K, threshold filtering, insufficient qualifying |
| META-007 Idempotency | T-META-011,013,017 | same fingerprint returns existing, no new rows |
| META-008 Lifecycle | T-META-013,014 | active→retired transition, atomic write |
| META-009 Fingerprint | T-META-011,014 | different data → different fingerprint |
| META-010 History | T-META-013 | all snapshots retained, version per context |
| META-011 Leakage prevention | T-META-006,017 | draws_to ≤ selection point enforced |
| META-012 lottery_id isolation | T-META-006,013,017 | no cross-lottery contamination |
| META-013 API | T-META-019,020,023 | 4 endpoints, error codes, envelope |
| META-014 CLI | T-META-021,024 | 4 commands, JSON output |
| META-015 Persistence | T-META-001,002,003 | migration creates/rolls back 4 tables |
| META-016 Error taxonomy | T-META-015,016 | 6 codes map to correct HTTP status |
| META-017 Freshness ext. | T-META-017 | config_json accepted, not used in MVP scoring |
| META-018 Boundary F11/F12/F13 | T-META-017 | no exp_* writes, no engine execution |
| META-019 Weight config | T-META-004,010,017 | global defaults, per-lottery override |
| META-020 Top-K defaults | T-META-012,017 | default K=5, min=1, max=20 |
| NFR-META-01 Determinism | T-META-006,008,011 | same inputs → same fingerprint and order |
| NFR-META-02 Idempotency | T-META-013,017 | fingerprint dedup, no duplicate rows |
| NFR-META-03 Immutability | T-META-013 | snapshots never mutated after persist |
| NFR-META-04 Isolation | T-META-006,013,017 | lottery-scoped queries |
| NFR-META-05 Performance | T-META-014,022 | ranking ≤ 500ms p95 |
| NFR-META-06 Rollback | T-META-001 | `alembic downgrade -1` drops meta_* only |
| NFR-META-07 No new deps | T-META-009,011 | NumPy only, no pandas |
| NFR-META-08 Engine boundary | T-META-017 | no module-level engine imports |
| NFR-META-09 Error handling | T-META-015,016 | ServiceError subclass, HTTP mapping |
| NFR-META-10 Stable sort | T-META-011 | `np.argsort(kind='stable')` |

---

**Ready for implementation (sdd-apply) via stacked-to-main PRs.**
