# PROJECT_STATUS.md

Lottery Intelligence Platform (LIP)

Estado interno del proyecto — baseline actualizado.

Versión: 1.0 · Fecha de cierre: 2026-08-07

---

## Estado

| Actividad | Estado |
|-----------|--------|
| Fase 1 — Core Domain | Archivada |
| Fase 2 — Data Engine (Import) | Archivada |
| Fase 3 — Statistics Engine | ✅ Archivada y cerrada |
| Fase 4 — Feature Engine | ✅ Archivada y cerrada |
| Fase 5 — Probability Engine | ✅ Archivada y cerrada |

- Último tag estable: `fase-3-statistics-complete` (anotado)
- Commit final de la fase: `8c01f50` (docs(openspec): archive fase-3-statistics change)
- Fecha de cierre: 2026-08-07
- Change archivado: `openspec/changes/archive/2026-08-07-fase-3-statistics/`
- OpenSpec sincronizado: `openspec/specs/statistics-engine/spec.md` (STE-01..13) + `openspec/specs/backend/spec.md` (REQ-10..12)

## Capacidades disponibles

- **Core Domain** — entidades centrales, migraciones, repositorios, CRUD.
- **Import Engine** — importación CSV automática y manual, validación, limpieza, normalización, versionado de datasets.
- **Statistics Engine** — frecuencias, gaps, promedios NULL-aware; generation bajo demanda vía CLI y API; snapshots versionados e inmutables con policy `active | retired | failed`.

## Garantías

- **Determinismo (G9)**: mismo dataset + misma `generator_version` + mismo checksum → resultado byte-idéntico (dos generaciones independientes verificadas).
- **Idempotencia**: `generate` incremental devuelve el snapshot `active` existente si ya reproduce el resultado; no duplica versiones.
- **Read-only sobre Core Domain (G10)**: `draw`, `draw_numbers`, `super_number`, `dataset`, `import_job`, `import_error` byte-idénticos antes/después de la generación; solo aparecen filas `stat_*`.
- **Snapshots inmutables**: nunca se muta un snapshot persistido; `full`/`rebuild` siempre escribe una versión nueva.
- **Migraciones reversibles**: cadena alembic `0001 → 0005`, con harness de downgrade verificado.
- **Cobertura de gates G1–G10**: confirmada en verify-report (ruff, suite 190 passed / 1 skipped, alembic head, downgrade chain, no regression, portabilidad, API contract, sin deuda, determinismo, read-only).

## Próximo objetivo

**Fase 4 — Feature Engine** (según `IMPLEMENTATION_ROADMAP.md`): calcular features automáticamente y preparar el sistema para miles de features. Solo se registra como próximo hito — sin diseño ni implementación por ahora.