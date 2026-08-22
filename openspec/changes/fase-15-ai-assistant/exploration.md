# Exploration — Fase 15: AI Assistant

Change: `fase-15-ai-assistant`
Status: research-only, no code written, nothing modified.
Base: `origin/main = 264ac59` (Fase 14 Dashboard closed).

## 1. Alcance real de Fase 15

Fuente única: `IMPLEMENTATION_ROADMAP.md:330-338` — cinco funciones, sin DoD ni criterios de aceptación:

> Explicar resultados · Interpretar gráficos · Generar reportes · Resumir experimentos · Asistir mediante lenguaje natural.

- Sin engine list, sin entregables, sin acceptance criteria (a diferencia de Fase 0 `:52-58`).
- Fronteras: Fase 14 Dashboard (termina en `:327`) y Fase 16 Performance (empieza en `:342`). Cadena de dependencia: `Dashboard → AI Assistant → Performance` (`:427-431`).
- Descompuestas, las cinco funciones consumen **outputs persistidos existentes**; no se implican nuevos engines de cómputo.

## 2. Requisitos identificados

| # | Requisito candidato | Fuente |
|---|---|---|
| F15-01 | Engine MUST exponer las 5 funciones (explain/interpret/report/summarize/assist) | Roadmap `:334-338` |
| F15-02 | Página IA consumirá el backend de Fase 15 (REQUIERE MODIFICAR R14) | R14, `openspec/changes/fase-14-dashboard/specs/frontend-dashboard/spec.md:335-349` |
| F15-03 | No llamar endpoints inexistentes (NFR-2); 12 páginas renderizan (NFR-4) | mismo spec `:562,:564` |
| F15-04 | Envelope `{success, data\|error, timestamp}` en todo endpoint nuevo | `backend/src/backend/app/schemas/envelope.py:22-33` |
| F15-05 | Nueva dependencia runtime requiere excepción allowlist firmada + test ban-gate | `backend/pyproject.toml:21-53`; `backend/tests/test_ml_pr1.py:157-181` |
| F15-06 | Separación estricta read/write, solo manual, sin scheduler/background (convención BTE-12) | `backend/src/backend/app/api/v1/bt.py:1-6` |
| F15-07 | Cultura de determinismo: sin float en valores persistidos, identidad de algoritmo versionada | `models/ml_metric.py:44-45` (Decimal); patrón `engine/version.py` |
| F15-08 | Config fuera del código; secrets solo por env | `config/settings.py:19-28` |

**Discrepancia detectada**: R14 (spec actual de la página IA) exige un stub que "SHALL NOT call any backend endpoint", pero el `IA.tsx` implementado llama 5 endpoints. Además `openspec/changes/fase-14-dashboard` NO está archivado — R14 sigue siendo el delta vivo. Fase 15 DEBE modificar R14 al recablear la página.

## 3. Dependencias existentes reutilizables

Datos persistidos (tablas SQLAlchemy, patrón snapshot activo `active|retired|failed`):

| Fuente (model) | Shape disponible |
|---|---|
| `models/draw.py` + `draw_number.py` | `lottery_id, draw_number, draw_date, jackpot Decimal(18,2) NULL, winners int NULL, is_deleted` + números por posición |
| `models/stat_snapshot.py` + `stat_frequency/stat_frequency_position/stat_gap/stat_average/stat_scalar` | counts por número, por (num,pos), gaps (count/min/max/avg `Numeric(20,6)`), medias NULL-aware jackpot/winners, **entropy scalar** |
| `models/prob_value.py` | `model_id, model_version, subject, draw_number NULL, value Numeric(20,8), params_json` |
| `models/ml_snapshot.py` + `ml_metric.py` | `{id, lottery_id, model_set='core-5', version, status, checksum, input_fingerprint, cut}`; métricas `model_id∈{rf,et,gb,svm,knn}`, `metric_name∈{accuracy,precision,recall,f1,roc_auc}`, `value Decimal, params_json` |
| `models/exp_experiment.py` + `exp_run.py` | `name, description, status, fingerprint, version, config_json`; runs con `engine_type CHECK('backtesting','ml','dl','optimization')`, `engine_snapshot_id` polimórfico; `compare()` → `comparison_json` |
| `models/bt_snapshot.py` + `bt_results` | `strategy_id, fingerprint, version, status, config_json`; métricas `hit_rate, average_matches, consistency_score, total_draws_evaluated` + historial por ventana |
| `models/graph_snapshot.py` + `graph_value.py` | `metric_type∈{cooccurrence, centrality_degree, community_id, density, modularity}`, `subject`, `value Decimal` |
| `models/meta_ranking*.py` / `meta_selection*.py` | entradas ranked/selected por lotería |

Endpoints existentes (registrados en `api/v1/router.py:26-38`, todos envelope-wrapped): `GET /health`, `GET /version`, `/lotteries` CRUD, `/draws` list/get/import/upload, `POST /statistics/generate` + `GET /statistics/{code}/{frequencies,gaps,averages}`, `POST /probability/generate` + `GET /probability/{code}/probabilities?model&subject&last`, `/graph` compute/list/read, `POST /ml/train` + `GET /ml/models` + `GET /ml/metrics`, `/opt` train/models/metrics/params, `/backtesting` run/history/results, `/experiment` CRUD/run/compare/export, `/meta` rank/select/ranking/selection, `/gen` generate/combinations/snapshot/snapshots.

Patrón de engine: paquete (`engine.py` + `snapshot_store.py` + `version.py` + `fingerprint.py` + `providers.py` Protocols), `services/*_service.py` delgado, router en `api/v1/*.py` montado en `router.py` (precedente: `probability/__init__.py:11-14`).

## 4. Gaps actuales

- No existe `ai/`/`assistant/`; `analytics/` es seam solo-docstring; `simulations/` vacío.
- No hay SDK/proveedor LLM: deps exactas `pyproject.toml:9-53` (fastapi, sqlalchemy, pydantic-settings, httpx, uvicorn, alembic, pytest, ruff, python-multipart, pre-commit, numpy, scikit-learn, torch, deap, optuna). `rg` en `uv.lock` por llm/openai/anthropic/langchain/assistant: cero hits. httpx es el único cliente HTTP.
- Gate de dependencias es restricción dura: stdlib-only con excepciones allowlist **firmadas, fechadas, por fase** (`pyproject.toml:21-53`) verificadas por tests ban-gate. Toda dependencia nueva de Fase 15 necesita excepción firmada + su propio test.
- Sin capa de prompts, sin routing de intención/NL, sin generación de texto.
- Sin persistencia de reportes ni sesiones de asistente (solo `experiment_exporter.py` para export).
- Sin contratos de endpoint para las 5 funciones; `Settings` no tiene campos AI.
- **Entropy persistida pero no expuesta**: `statistics/engine.py:110-128` + `generator.py:21` → `stat_scalars`, pero `api/v1/statistics.py` solo expone frequencies/gaps/averages. "Explicar resultados" no puede leer entropy vía API.
- Página IA actual = vista de estado (no asistente): compone system/ML/probability; sin texto, sin chat, sin streaming.
- Mismatch R14 spec/impl (ver §2).

## 5. Decisiones que requieren autorización

1. **Naturaleza del motor** (fork bloqueante): generación determinista regla-basada (stdlib + templates + Decimal — cabe en el gate stdlib-first y la cultura de determinismo) vs LLM externo vía API (rompe gate, requiere manejo de keys, no determinista) vs modelo local (transformers — pesado, choca con exact-pin + gate). **Lean del explorador: determinista regla-basada v1** con seam `TextGenerator` para un backend LLM futuro. → AUTORIZACIÓN REQUERIDA.
2. **Provider (si LLM)**: SDK/proveedor/modelo; fallback offline; presupuesto por llamada.
3. **Dónde viven los prompts**: constantes en el paquete engine (consistente con "config fuera de código" para infra, determinista) vs persistidos en DB (tabla nueva + versionado).
4. **Persistencia de reportes**: síncrono on-demand (consistente con BTE-12 manual-only) vs tabla `assistant_reports`.
5. **Forma de la API**: un endpoint genérico `/assistant/ask` con intent routing vs cinco endpoints explícitos espejo del roadmap (los explícitos calzan con el patrón por-engine; el genérico NL solo tiene sentido si es LLM-backed).
6. **Recableado de la página IA**: mantener secciones de estado + panel asistente vs reemplazar; en ambos casos R14 debe MODIFICARSE.
7. **Estado de conversación**: stateless v1 (recomendado) vs sesiones persistidas.
8. **"Interpretar gráficos"**: confirmar que interpreta los **datos detrás** de los charts client-side (la plataforma no tiene chart data server-side), no input de imagen.

## 6. Riesgos técnicos

- **Dependencia**: SDK LLM viola el gate F6 → excepción firmada + gate test + exact pin + churn uv.lock (precedente torch `pyproject.toml:29-38`).
- **Seguridad**: prompt injection (texto de usuario fluye a prompts generados), datos jackpot/ganadores saliendo del proceso si provider externo, manejo de API keys (no existe infra de keys; secrets env-only), SSRF si la URL del provider es configurable.
- **Performance**: llamada LLM síncrona bloquearía el event loop — no hay convenciones async/timeout/retry en el codebase.
- **Costo**: gasto por request sin auth (v1 no tiene) — un chat endpoint abierto amplifica abuso.
- **Testabilidad**: salida LLM no determinista — choca con los gates checksum/fingerprint/byte-identical (G9). Generación determinista mantiene el contrato; LLM requiere capa mock.
- **Contrato**: dejar R14 sin modificar mientras se publica una página con API viola la fuente de verdad del spec.

## 7. Límites de alcance

Fase 15 NO debe incluir: ítems de Fase 16 Performance (`:342-350`), auth/JWT, endpoints backend `/dashboard/*` (diferidos indefinidamente, F14 D2), cómputo estadístico nuevo (pendientes F3 trends/distributions/correlations `:141-146`), nuevo entrenamiento/predicción ML, schedulers/background jobs, Docker/deploy, sesiones de chat persistentes (salvo mandato).

## 8. Propuesta de slices (provisional — requiere confirmación en proposal)

Cada slice ≤400 líneas authored (convención del proyecto):

1. **Slice 1 — engine core**: `backend/app/ai/` (version constant, seam `TextGenerator`, generadores deterministas explain/interpret/report/summarize consumiendo datos de servicios) + tests unitarios.
2. **Slice 2 — API surface**: `api/v1/assistant.py` con endpoints explícitos (o un NL endpoint, según decisión §5.5) + wiring `AiService` + envelope + tests integración + endpoint de lectura entropy si se autoriza.
3. **Slice 3 — frontend rewiring**: extender/reemplazar `IA.tsx` + `services/assistant.ts` + tests MSW + **MODIFICAR R14** en el delta spec de Fase 15.

Los límites exactos dependen de las decisiones §5 (especialmente la naturaleza del motor).

## 9. Método

Investigación read-only: roadmap, routers `api/v1/` (14), modelos SQLAlchemy (10+), patrón engine, pyproject/uv.lock, spec R14, IA.tsx. Sin archivos creados, sin modificaciones, sin persistir.

## Key Learnings

1. La sección roadmap de Fase 15 define cinco funciones sin DoD ni acceptance criteria más allá de la lista.
2. El proyecto impone un gate de dependencias stdlib-only con excepciones allowlist firmadas por fase y tests ban-gate que parsean pyproject.toml.
3. Entropy está computada y persistida en stat_scalars pero ningún endpoint la expone — bloquea lecturas de explicación de resultados.
4. R14 (spec IA) exige stub sin API calls mientras la página implementada llama cinco endpoints — mismatch de contrato.
5. Las carpetas openspec de Fase 14 y Fase 13 siguen sin commitear en git; sus delta specs son la fuente viva.
