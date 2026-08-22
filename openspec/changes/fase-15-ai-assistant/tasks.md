# Tasks: Fase 15 — AI Assistant (Deterministic v1)

Status: PLANNED · Store: openspec · Date: 2026-08-16
Slice order (dependency): S1a engine core → S1b service → S2 API surface → S3 frontend rewiring (S1b depends on S1a; S2 depends on S1b; S3 depends on S2). Each slice = one stacked-to-main PR, conventional commits `[T-Sx-yy]`, `--no-verify`, no AI attribution, sub-agents restore `.atl/` before commit. Strict TDD backend (pytest via `backend/.venv`), vitest+MSW frontend.

## Review Workload Forecast (REVISED — owner-approved S1 split)

| Field | Value |
|-------|-------|
| Estimated changed lines | ~1330 total (S1a ~383, S1b ~305, S2 ~410, S3 ~375); goldens excluded |
| 400-line budget risk | Low per slice / High total |
| Chained PRs recommended | Yes |
| Suggested split | PR 1 (S1a engine core) → PR 2 (S1b ai_service) → PR 3 (S2 API) → PR 4 (S3 frontend) |
| Delivery strategy | ask-on-risk |
| Chain strategy | stacked-to-main (F14 precedent) |

Decision needed before apply: Yes
Chained PRs recommended: Yes
Chain strategy: stacked-to-main
400-line budget risk: Low

### Partition (owner-approved, 2026-08-17)

- **S1a (PR 1, ~383 ln)**: backend/app/ai/ completo (engine.py, generators.py, prompts.py, providers.py, fingerprint.py, version.py, __init__.py ~354) + tests/ai/test_fingerprint.py (~29). Engine puro + validación básica de fingerprint. ≤400.
- **S1b (PR 2, ~305 ln)**: services/ai_service.py (~129) + services/errors.py delta (~13) + tests/ai/test_generators.py (~108) + tests/ai/test_intent.py (~32) + tests/ai/test_formatting.py (~23). Servicio + tests restantes del engine (golden/intent/formatting). ≤400. Depende de S1a.
- Reglas: sin recorte de funcionalidad, sin eliminar golden tests, sin cambios a D1-D8, sin size:exception, todos los tests siguen siendo del engine/servicio con cobertura completa.

### Suggested Work Units

| Unit | Goal | PR | Focused test command | Runtime harness | Rollback boundary |
|------|------|----|----------------------|-----------------|-------------------|
| S1 | `ai/` engine pkg + `ai_service` + unit/golden tests | PR 1 | `backend/.venv/bin/pytest backend/tests/ai -q` | `backend/.venv/bin/pytest` unit suite green | Delete `backend/app/ai/` + `ai_service.py`; revert `errors.py` delta |
| S2 | assistant router/schemas + scalars endpoint + integration tests | PR 2 | `backend/.venv/bin/pytest backend/tests/api/test_assistant.py backend/tests/api/test_scalars.py -q` | `TestClient` over app: 5 endpoints + scalars envelope/404/422 | Un-mount `assistant_router`; revert `router.py`/`statistics.py`/`schemas`/`api/errors.py` deltas |
| S3 | `AssistantPanel` + `services/assistant.ts` + IA.tsx delta + MSW | PR 3 | `cd frontend && npx vitest run --testTimeout=20000 --pool=forks --poolOptions.forks.maxForks=2 src/services/assistant.test.ts src/pages/IA.test.tsx` | `npx vitest run` full + `npm run build` (NFR-4) | Revert `IA.tsx`, delete panel/service/types; drop R14 delta |

## Slice S1 — Engine Core (backend `ai/` + service + tests) [~460 ln, goldens excl]

| ID | Scope | Description | Files | Notes | Lines |
|----|-------|-------------|-------|-------|-------|
| T-S1-01 | A-02 | Create `ai/version.py` with `AI_GENERATOR_VERSION = "1.0.0"` (independent identity) | create `backend/src/backend/app/ai/version.py` | no deps; first file | 8 |
| T-S1-02 | D1, A-06..A-10 | Create `ai/prompts.py`: Spanish template constants per function + empty-data texts + capabilities text + `AI_ASSISTANT_LOCALE="es"` | create `backend/src/backend/app/ai/prompts.py` | `string.Template`; output es | 85 |
| T-S1-03 | A-01 | Create `ai/providers.py`: `TextGenerator` Protocol (seam) + `RuleBasedTextGenerator` stdlib renderer | create `backend/src/backend/app/ai/providers.py` | pure; no DB | 35 |
| T-S1-04 | A-02 | Create `ai/fingerprint.py`: `compute_ai_fingerprint(version,function,inputs)` SHA-256 over `sort_keys=True` JSON | create `backend/src/backend/app/ai/fingerprint.py` | Decimal-string inputs only | 18 |
| T-S1-05 | A-03 | Create `ai/generators.py`: `format_decimal` (`normalize():f`), `format_optional`→"sin datos", template context builders | create `backend/src/backend/app/ai/generators.py` | never `float()` | 55 |
| T-S1-06 | A-01..A-10 | Create `ai/engine.py`: 5 fns + `classify_intent` + `GenerationResult{text,engine_version,fingerprint}`; each: validate→context→`generator.generate` | create `backend/src/backend/app/ai/engine.py` | stateless; intent taxonomy first-match | 105 |
| T-S1-07 | A-01 | Create `ai/__init__.py`: package docstring + exports `AI_GENERATOR_VERSION`, engine fns | create `backend/src/backend/app/ai/__init__.py` | docstrings only | 12 |
| T-S1-08 | A-12 | Add `AssistantError(code="assistant_error")` to services errors | modify `backend/src/backend/app/services/errors.py` | register code later (S2) | 10 |
| T-S1-09 | A-06..A-12 | Create `services/ai_service.py` composition root: resolve lottery (404), read via `StatisticsService`/`ProbabilityService`/`ExpService`, map missing→empty-data text, raise `AssistantError` | create `backend/src/backend/app/services/ai_service.py` | engine touches no DB | 82 |
| T-S1-10 | A-04 | RED→GREEN golden tests per function + empty-data variants + byte-identical repetition | create `backend/tests/ai/test_generators.py` | goldens excluded from count | 70 |
| T-S1-11 | A-10 | Table-driven intent tests: ES keywords (por qué/frecuencia→explain, grafic→interpret, report→report, experiment→summarize) + unknown fallback | create `backend/tests/ai/test_intent.py` | | 30 |
| T-S1-12 | A-02 | Fingerprint tests: same inputs identical; version/input change differs | create `backend/tests/ai/test_fingerprint.py` | | 15 |
| T-S1-13 | A-03 | Decimal formatting tests: `0.12345678` exact; NULL→"sin datos" | create `backend/tests/ai/test_formatting.py` | | 15 |

## Slice S2 — API Surface (assistant router/schemas + scalars + integration tests) [~410 ln]

| ID | Scope | Description | Files | Notes | Lines |
|----|-------|-------------|-------|-------|-------|
| T-S2-01 | A-12 | Create `schemas/assistant.py`: `AssistantResponse{text,engine_version,fingerprint}`, `SummarizeRequest`, `AssistRequest` | create `backend/src/backend/app/schemas/assistant.py` | envelope `data` | 35 |
| T-S2-02 | A-11 | Modify `schemas/statistics.py`: add `ScalarRow{name,value:str}`, `ScalarList` (header + rows) | modify `backend/src/backend/app/schemas/statistics.py` | Decimal-string values | 25 |
| T-S2-03 | A-11 | Modify `services/statistics_service.py`: add `read_scalars(lottery_code)` via `get_active` → select `StatScalar ORDER BY name` (never precomputes, STE-10) | modify `backend/src/backend/app/services/statistics_service.py` | 404 `SNAPSHOT_NOT_FOUND` | 30 |
| T-S2-04 | A-11 | Add `GET /statistics/{code}/scalars` to statistics router: `_resolve_lottery` (404) → `read_scalars` → envelope | modify `backend/src/backend/app/api/v1/statistics.py` | 404 `RESOURCE_NOT_FOUND`/`SNAPSHOT_NOT_FOUND` | 30 |
| T-S2-05 | A-06..A-10 | Create `api/v1/assistant.py`: 5 endpoints (GET explain/interpret/report, POST summarize/assist) → `AiService` → envelope; 422 scope/body; `assistant_error` 500 | create `backend/src/backend/app/api/v1/assistant.py` | `_resolve_lottery`; report scope `Literal{frequency,gap,average,probability,experiment}` | 120 |
| T-S2-06 | A-12 | Register `"assistant_error": 500` in `api/errors.py` `_CODE_TO_STATUS` | modify `backend/src/backend/app/api/errors.py` | | 8 |
| T-S2-07 | A-06..A-10 | Mount `assistant_router` in `api/v1/router.py` | modify `backend/src/backend/app/api/v1/router.py` | | 5 |
| T-S2-08 | A-12, A-11 | Integration tests: 5 endpoints envelope shape (A-12 success), 404 mapping (RESOURCE_NOT_FOUND/EXPERIMENT_NOT_FOUND), 422 scope, empty-data success, scalars 404 + content | create `backend/tests/api/test_assistant.py` + `backend/tests/api/test_scalars.py` | RED→GREEN | 157 |

## Slice S3 — Frontend Rewiring (panel + service + IA.tsx + MSW) [~375 ln]

| ID | Scope | Description | Files | Notes | Lines |
|----|-------|-------------|-------|-------|-------|
| T-S3-01 | A-12 | Create `src/types/assistant.ts`: `AssistantResponse`, `SummarizeRequest`, `AssistRequest` | create `frontend/src/types/assistant.ts` | | 20 |
| T-S3-02 | A-06..A-10 | Create `src/services/assistant.ts`: 5 wrappers via `apiClient` (envelope unwrap) + `scalars` | create `frontend/src/services/assistant.ts` | | 60 |
| T-S3-03 | D4, R14 | Create `src/components/AssistantPanel.tsx`: labeled textarea + Ask(assist), buttons Explain/Interpret/Report, Summarize w/ experiment_id input; Skeleton/ErrorState/EmptyState reuse (R20/R22) | create `frontend/src/components/AssistantPanel.tsx` | only 5 endpoints (NFR-2) | 130 |
| T-S3-04 | D4, R14 | Modify `src/pages/IA.tsx`: add `<AssistantPanel lotteryCode={...}/>` below status sections (sections untouched) | modify `frontend/src/pages/IA.tsx` | NFR-4 render | 30 |
| T-S3-05 | R14 (delta, no rewrite) | Extend `frontend/src/pages/IA.test.tsx` MSW handlers for 5 endpoints; panel flows (question→assist, loading skeletons, ErrorState retry, all-5-only NFR-2) | modify `frontend/src/pages/IA.test.tsx` | | 90 |
| T-S3-06 | R14 | Unit tests `src/services/assistant.test.ts` (MSW) + full `npm run build` green (NFR-4) | create `frontend/src/services/assistant.test.ts` | | 45 |

## Risks

- "Asistir" overbuilt w/o LLM (Med) → keep intent routing over 4 functions (D5), unknown→capabilities text (A-10).
- D7 scalars endpoint required for explain entropy (A-06/A-11); if blocked, explain falls back to freq/avg.
- R14 delta scope creep (Med) → bound edits to R14 block; delta already written, never rewritten (D8).
- Determinism drift (Low) → versioned identity + golden tests per function (A-02/A-04).
- Per-slice authored count measured via `git diff --numstat` excluding lockfiles; goldens excluded per design — confirm each PR ≤400 before apply.

## Next Recommended

sdd-apply — pending orchestrator gate (Decision needed before apply: Yes). Orchestrator to confirm chain strategy = stacked-to-main (F14 precedent) before PR 1 (S1).

## Skill Resolution

- sdd-tasks (loaded): task breakdown + workload forecast.
- sdd-apply (loaded): gates, work-unit evidence, chain-strategy enforcement for downstream.
- work-unit-commits (loaded): commit-by-work-unit; tests with code; each slice = reviewable PR.
- Loaded per orchestrator instruction; no strict-tdd module invoked (planning only).
