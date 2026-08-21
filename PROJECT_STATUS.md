# PROJECT_STATUS.md

Lottery Intelligence Platform (LIP)

Estado interno del proyecto — baseline actualizado.

Versión: 1.1 · Última actualización: 2026-08-21

---

## Estado

| Actividad | Estado |
|-----------|--------|
| Fase 1 — Core Domain | Archivada |
| Fase 2 — Data Engine (Import) | Archivada |
| Fase 3 — Statistics Engine | ✅ Archivada y cerrada |
| Fase 4 — Feature Engine | ✅ Archivada y cerrada |
| Fase 5 — Probability Engine | ✅ Archivada y cerrada |
| Fase 7 — Machine Learning | ✅ Archivada y cerrada |
| Fase 8 — Deep Learning | ✅ Archivada y cerrada |
| Fase 9 — Optimization Engine | ✅ Archivada y cerrada |
| Fase 10 — Backtesting Engine | ✅ Archivada y cerrada |
| Fase 11 — Experiment Engine | ✅ Archivada y cerrada |
| Fase 12 — Graph Engine | ✅ Archivada y cerrada |
| Fase 13 — Generator Engine | ✅ Archivada y cerrada |
| Fase 14 — Dashboard | ✅ Archivada y cerrada |
| Fase 15 — AI Assistant | ✅ Archivada y cerrada |
| Fase 16 — Performance | ✅ Archivada y cerrada |
| Fase 17 — Testing | ✅ Archivada y cerrada (2026-08-20) |
| Fase 18 — Documentation | ✅ Archivada y cerrada (2026-08-20) |
| Fase 19 — Release Candidate | ✅ Archivada y cerrada (2026-08-21) — tag `v1.0.0-rc.1`, MIT |

## Feature freeze (2026-08-21)

El código está **congelado para v1.0.0** a partir del tag `v1.0.0-rc.1`: solo se
aceptan correcciones de defectos hasta la liberación; no se agregan features.
Evidencia de validación: `RELEASE_VALIDATION.md`. Pendiente único de release:
decisión de LICENSE del owner (RC-009, S7).

## Capacidades disponibles

- **Core Domain** — entidades centrales, migraciones, repositorios, CRUD.
- **Import Engine** — importación CSV automática y manual, validación, limpieza, normalización, versionado de datasets.
- **Statistics Engine** — frecuencias, gaps, promedios NULL-aware; generation bajo demanda vía CLI y API; snapshots versionados e inmutables con policy `active | retired | failed`.
- **Feature Engine** — F4 features (10 core), snapshots con lifecycle activo.
- **Probability Engine** — predicción probabilística por número.
- **Machine Learning (Fase 7)** — scikit-learn core-5 (RF, Extra Trees, GB, SVM, KNN), walk-forward, anti-shuffle, fingerprints, Decimal(20,8) metrics, `ml_*` snapshots, CLI `lip ml`, API `POST /ml/train`, `GET /ml/models`, `GET /ml/metrics`. No `/ml/predict`.
- **Deep Learning (Fase 8)** — PyTorch CPU-only, MLP + LSTM (core-3), walk-forward, anti-leakage, GF1 byte-identical determinism, `dl_*` snapshots, weights BLOB custom format, CLI `lip dl`, API `POST /dl/train`, `GET /dl/models`, `GET /dl/metrics`. No `/dl/predict`. Transformers deferred (`future-dl`).
- **Optimization Engine (Fase 9)** — Hyperparameter optimization for ML/DL models, core-4 optimizers (GA, PSO, Bayesian, SA), walk-forward objective evaluation, `opt_*` snapshots, SHA-256 fingerprints, Decimal(20,8) metrics, CLI `lip opt`, API `POST /opt/train`, `GET /opt/models`, `GET /opt/metrics`, `GET /opt/params`. No `/opt/predict`.
- **Backtesting Engine (Fase 10)** — Walk-forward backtesting with configurable train/eval windows, anti-leakage temporal ordering, deterministic fingerprints (SHA-256), lottery-specific metrics (hit rate, match distribution, average matches, consistency score), dual benchmark (uniform random + F5 hypergeometric), `bt_*` snapshots with atomic lifecycle, CLI `lip bt run|history|results`, API `POST /backtesting/run`, `GET /backtesting/history`, `GET /backtesting/results`. Manual-only — no scheduler, no auto-execution.
- **Experiment Engine (Fase 11)** — Tracking/comparison layer over existing engines. Registers experiments, versions them, tracks run associations via polymorphic snapshot references (`bt_*`, `ml_*`, `dl_*`, `opt_*`), compares results across runs (persisted immutable JSON), exports to JSON/CSV. `exp_*` tables, CLI `lip exp create|list|compare|export`, API `POST /experiment/create`, `GET /experiment/{id}`, `PATCH /experiment/{id}`, `GET /experiments`, `POST /experiment/{id}/run`, `POST /experiment/{id}/compare`, `GET /experiment/{id}/export`. Does NOT execute engines.

## Garantías

- **Determinismo (G9)**: mismo dataset + misma `generator_version` + mismo checksum → resultado byte-idéntico (dos generaciones independientes verificadas).
- **Idempotencia**: `generate` incremental devuelve el snapshot `active` existente si ya reproduce el resultado; no duplica versiones.
- **Read-only sobre Core Domain (G10)**: `draw`, `draw_numbers`, `super_number`, `dataset`, `import_job`, `import_error` byte-idénticos antes/después de la generación; solo aparecen filas `stat_*` / `ml_*` / `dl_*` / `opt_*`.
- **Snapshots inmutables**: nunca se muta un snapshot persistido; `full`/`rebuild` siempre escribe una versión nueva.
- **Migraciones reversibles**: cadena alembic `0001 → 0016`, con harness de downgrade verificado.
- **Cobertura de gates G1–G10**: confirmada en verify-report (ruff, suite 642 passed / 1 skipped, alembic head, downgrade chain, no regression, portabilidad, API contract, sin deuda, determinismo, read-only).