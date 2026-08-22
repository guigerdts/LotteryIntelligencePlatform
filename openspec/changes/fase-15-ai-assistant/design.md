# Design: F15 — AI Assistant (Deterministic v1)

## Technical Approach

Deterministic rule-based text generation behind a `TextGenerator` seam, consuming existing persisted snapshots through the service layer — no LLM, zero new runtime deps (F6 gate green, no `pyproject.toml` change). Mirrors the `probability/` engine precedent: pure `ai/` package (stdlib + `string.Template` + `Decimal`), thin `AiService` composition root, thin envelope-wrapped router. Output is Spanish (`es`), stateless (D5), synchronous, manual-only (BTE-12), byte-identical per `AI_GENERATOR_VERSION`. Implements A-01..A-12; the R14 delta spec is already written and is only referenced, never rewritten.

## Architecture Decisions

| Decision | Choice | Alternatives | Rationale |
|----------|--------|-------------|-----------|
| **Motor** | Rule-based stdlib+templates+Decimal | LLM SDK; local model | F6 gate stays green; determinism culture (G9); no key infra; fits BTE-12 |
| **LLM seam** | `TextGenerator` Protocol in `providers.py`, composed at `AiService` | Seam per function | Future LLM provider plugs in at composition root; 5 contracts unchanged (A-01) |
| **Data access** | `AiService` reads via existing services (`StatisticsService`/`ProbabilityService`/`ExpService`), passes pure dataclass carries to engine | Engine touches DB | Matches PES-06 parity: engine imports only its own Protocols/carries |
| **API shape (D3)** | Five explicit endpoints | Generic `/assistant/ask` | Mirrors roadmap; per-engine router pattern; NL-only makes sense with LLM only |
| **Missing data** | Empty-data Spanish text in success envelope | 404 on missing snapshot | Spec A-06/07/12 mandate success; scalars read is the only 404 path (A-11) |
| **summarize run_ids?** | Provided → `ExpService.compare` (cached); omitted → latest `ExpComparison`; none → empty-data text | Require run_ids | Mirrors compare body contract (A-09); graceful with no comparison |
| **assist summarize** | Route only when question has summarize keywords + extractable `experiment_id` (first int after keyword); else ask-for-id Spanish text | Fragile NLP extraction | Deterministic; unknown/ambiguous intent never errors (A-10) |
| **Panel shape (D4)** | Question box + Assist + 4 explicit buttons (Explain/Interpret/Report/Summarize w/ experiment_id input) | Buttons only; assist only | Guarantees all 5 endpoints callable; a11y; R14 NFR-2 |
| **Errors** | New `AssistantError` → `assistant_error` 500; reuse `RESOURCE_NOT_FOUND`/`SNAPSHOT_NOT_FOUND`/`EXPERIMENT_NOT_FOUND` (all 404) | New codes per function | Taxonomy parity; registered in `_CODE_TO_STATUS` |
| **Config** | No `Settings` change; `AI_ASSISTANT_LOCALE = "es"` constant in `prompts.py` | Settings field | Spec pins es; deterministic engine has no infra knobs (proposal `settings.py` entry dropped) |

## Data Flow

```
Client ──→ api/v1/assistant.py (parse, resolve lottery 404)
             └─→ AiService (reads via existing services)
                    ├─ StatisticsService.read_{frequencies,gaps,averages,scalars}  → carries
                    ├─ ProbabilityService.read_values                              → carries
                    └─ ExpService.get/compare                                      → comparison_json
             └─→ ai/engine.py (build context → generator.generate → fingerprint)
                    └─ providers.RuleBasedTextGenerator ─→ prompts.py (es templates)
             └─→ SuccessEnvelope{text, engine_version, fingerprint}
```

`GET /statistics/{code}/scalars` (A-11): router `_resolve_lottery` → `StatisticsService.read_scalars` (`get_active` → select `StatScalar` ORDER BY name; missing snapshot → `SNAPSHOT_NOT_FOUND` 404; never precomputes STE-10).

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `backend/src/backend/app/ai/__init__.py` | Create | Package docstring; exports `AI_GENERATOR_VERSION`, engine functions |
| `backend/src/backend/app/ai/version.py` | Create | `AI_GENERATOR_VERSION = "1.0.0"` identity (A-02), pinned independent of other engines |
| `backend/src/backend/app/ai/prompts.py` | Create | D1: Spanish template constants per function + empty-data + capabilities text + locale constant |
| `backend/src/backend/app/ai/generators.py` | Create | Decimal-safe formatting (`format_decimal` via `normalize():f` / quantize; `format_optional` → "sin datos"), template context builders |
| `backend/src/backend/app/ai/providers.py` | Create | `TextGenerator` Protocol (seam, A-01) + `RuleBasedTextGenerator` (stdlib renderer) |
| `backend/src/backend/app/ai/fingerprint.py` | Create | `compute_ai_fingerprint(version, function, inputs)` — SHA-256 over `sort_keys=True` JSON (A-02) |
| `backend/src/backend/app/ai/engine.py` | Create | 5 functions + `classify_intent`; each: validate/normalize inputs → context → `generator.generate` → `GenerationResult{text, engine_version, fingerprint}` |
| `backend/src/backend/app/services/ai_service.py` | Create | Composition root: resolve lottery (404), read persisted data, map missing→empty-data text, raise `AssistantError` on generation failure |
| `backend/src/backend/app/services/errors.py` | Modify | Add `AssistantError(code="assistant_error")` |
| `backend/src/backend/app/api/v1/assistant.py` | Create | 5 endpoints (below) |
| `backend/src/backend/app/schemas/assistant.py` | Create | `AssistantResponse`, `SummarizeRequest`, `AssistRequest` |
| `backend/src/backend/app/api/v1/statistics.py` | Modify | Add `GET /{lottery_code}/scalars` (A-11) |
| `backend/src/backend/app/schemas/statistics.py` | Modify | Add `ScalarRow{name, value:str}`, `ScalarList` (header + rows) |
| `backend/src/backend/app/services/statistics_service.py` | Modify | Add `read_scalars(lottery_code)` |
| `backend/src/backend/app/api/v1/router.py` | Modify | Mount `assistant_router` |
| `backend/src/backend/app/api/errors.py` | Modify | Add `"assistant_error": 500` |
| `frontend/src/services/assistant.ts` | Create | 5 wrappers via `apiClient` (envelope unwrap) |
| `frontend/src/types/assistant.ts` | Create | `AssistantResponse`, request types |
| `frontend/src/components/AssistantPanel.tsx` | Create | Panel: labeled textarea + Ask (assist), buttons Explain/Interpret/Report, Summarize w/ experiment_id input; Skeleton/ErrorState/EmptyState reuse (R20/R22) |
| `frontend/src/pages/IA.tsx` | Modify | Add `<AssistantPanel lotteryCode={...}/>` below status sections (sections untouched, D4) |
| `frontend/src/pages/IA.test.tsx` | Modify | MSW handlers for 5 endpoints; panel flows |

## Interfaces / Contracts

```python
class TextGenerator(Protocol):                    # providers.py — seam (A-01)
    def generate(self, function: str, inputs: Mapping[str, Any]) -> str: ...

def compute_ai_fingerprint(engine_version: str, function: str, inputs: Mapping) -> str
def classify_intent(question: str) -> str         # "explain"|"interpret"|"report"|"summarize"|"unknown"
def explain(inputs, gen) / interpret(...) / report(...) / summarize(...) / assist(...) -> GenerationResult
```

**Intent taxonomy** (normalized lowercase, diacritic-folded, ordered first-match):

| Intent | Keywords |
|--------|----------|
| summarize | `experiment`, `compar`, `resum` (run/experiment context), `run ganador` |
| explain | `por qué`, `porque`, `explica`, `resultado`, `frecuencia`, `entrop`, `gap`, `media`, `promedio` |
| interpret | `interpret`, `grafic`, `chart`, `significa`, `tendencia` |
| report | `report`, `informe`, `documento` |
| unknown | → capabilities-listing Spanish text (success, A-10) |

## Endpoints

| Method | Path | Params/Body | Data | Errors |
|--------|------|-------------|------|--------|
| GET | `/assistant/explain` | `?lottery_code&subject?&context?` | `{text, engine_version, fingerprint}` | 404 RESOURCE_NOT_FOUND; empty-data success |
| GET | `/assistant/interpret` | `?lottery_code` | same | 404; empty-data success |
| GET | `/assistant/report` | `?lottery_code&scope?(Literal{frequency,gap,average,probability,experiment})` | same | 404; 422 scope; empty-data success |
| POST | `/assistant/summarize` | `{experiment_id, run_ids?}` | same | 404 EXPERIMENT_NOT_FOUND; 422 <2 runs; empty-data success |
| POST | `/assistant/assist` | `{question, lottery_code}` | same | 404; unknown → capabilities success |
| GET | `/statistics/{code}/scalars` | — | header + `scalars:[{name:"entropy", value:"0.123456"}]` | 404 RESOURCE_NOT_FOUND; 404 SNAPSHOT_NOT_FOUND |

## Testing Strategy

| Layer | What | Approach |
|-------|------|----------|
| Unit | Generators | Golden fixtures per function + empty-data variants; byte-identical repetition (A-04) |
| Unit | Intent classifier | Table-driven ES keyword cases incl. unknown fallback (A-10) |
| Unit | Fingerprint | Same inputs → identical digest; version/input change → differs (A-02) |
| Unit | Decimal formatting | `0.12345678` exact; NULL → "sin datos" (A-03) |
| Integration | Endpoints | Envelope shape (A-12), 404/422 mapping, empty-data success, scalars 404 + content |
| Frontend | MSW | Panel render, assist submit, loading skeletons, ErrorState retry, all-5-endpoints-only (NFR-2) |

## Threat Matrix

N/A — no shell, subprocess, VCS/PR automation, executable-file classification, or process-integration boundary. Rows (documentation-like paths, git selection, commit/push state, PR commands) each N/A: F15 adds declarative FastAPI routes over read-only services; no adversarial execution boundary introduced.

## Migration / Rollout

No migration, no schema change, no feature flag. Rollback: delete `ai/` + `ai_service.py`; un-mount `assistant_router`; revert statistics/router/errors deltas; revert IA.tsx/service/panel; drop R14 delta. All additive.

## Slice Sizing (measure: `git diff --numstat` additions+deletions per slice; goldens excluded per phase-common §E)

| Slice | Content | Est. lines |
|-------|---------|-----------|
| S1 engine core | `ai/` pkg + `ai_service.py` + unit/golden tests | ~330 code + ~130 tests |
| S2 API surface | assistant router/schemas + scalars delta + integration tests | ~230 code + ~180 tests |
| S3 frontend | panel/service/types + IA.tsx delta + MSW tests | ~225 code + ~150 tests |

## Open Questions

- [ ] None blocking — design judgment on panel Summarize button (experiment_id input) and assist summarize extraction (first int after keyword) to confirm in tasks.
