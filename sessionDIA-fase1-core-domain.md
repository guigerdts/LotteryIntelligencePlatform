# Session DIA — Fase 1: Core Domain

> Slice: `fase-1-core-domain` (SDD change next)
> Estado de referencia: Fase 0 backend completa y archivada (2026-08-06)
> Artefacto previo: `openspec/changes/archive/2026-08-06-fase-0-foundation/` → `openspec/specs/backend/spec.md`

## Objetivo del slice

Implementar las entidades principales del dominio sobre la base Fase 0 (FastAPI + SQLAlchemy + SQLite), cerrando el primer ciclo de datos reales: **modelos → migraciones → repositorios → CRUD → tests**. Todo detrás de la capa de repositorios ya existente, sin hardcodear SQLite.

## Alcance (del roadmap IMPLEMENTATION_ROADMAP.md, Fase 1)

Entidades:

- `Lottery` — juego de lotería (configurable por reglas externas, no hardcode)
- `Draw` — sorteo de un lottery
- `DrawNumber` — número extraído en un draw (relación N:1)
- `SuperNumber` — número extra especial del draw (0..1 por draw; opcional)
- `Dataset` — conjunto de datos derivado (link a draws/fuente)

Entregables (Definición de Done Fase 1):

- Modelos SQLAlchemy ORM (`backend/src/backend/app/models/`)
- Migraciones Alembic (reemplaza el `init_db` vacío de Fase 0)
- Repositorios sobre `repositories/base.py` (patrón ya definido)
- CRUD (API v1: `/lotteries`, `/draws`, ...)
- Tests (pytest)

## Fuera de alcance (boundary explícito)

- Motores de análisis/probabilidad/ML (Fases 3+)
- Frontend dashboard (Fase 14)
- PostgreSQL swap (solo config — dialecto por URL, ya soportado)
- Reglas de lotería en código (viven fuera del código; registry en Fases 1/2)

## Decisiones técnicas heredadas (no reabrir)

| Decisión | Valor |
|---|---|
| Stack | Python >=3.12, uv, FastAPI + pydantic v2, SQLAlchemy, SQLite |
| Lint/format | ruff (E,F,I,UP,B) line-length 100 + `ruff format` |
| DB path | repo-root `database/lip.db` (ignorado por git) |
| Migraciones | Alembic — `Base.metadata.create_all` queda OUT en Fase 0; Fase 1 lo adopta |
| Dialecto | config-only swap SQLite→PostgreSQL via URL (repositorios sin código sqlite) |
| Commits | conventional, work-units, `--no-verify` (GGA) validando ruff+pytest antes |
| SDD | preflight cacheado: interactive, openspec, ask-on-risk, 400 líneas, stacked-to-main |

## Verificación esperada (criterios de aceptación del slice)

1. `uv run ruff check .` → pass; `uv run ruff format --check .` → 0 reformables
2. `uv run pytest -q` → todos los tests verdes (nuevos + 5 existentes de Fase 0)
3. `uv run alembic upgrade head` → crea las tablas en `database/lip.db`
4. Boot uvicorn real → `/api/v1/health` y los endpoints CRUD del slice responden con envelope
5. CRUD verificado por TestClient: crear/listar/obtener lottery + draw (sin datos reales de sorteo)

## Riesgos / puntos de atención

- **Alembic vs init_db Fase 0**: coordinar que `init_db` (archivo vacío) no pise el esquema; la app debe seguir creando el archivo pero las tablas vienen de migraciones.
- **Diseño de entidades**: seguir DATABASE_SCHEMA (3NF, FKs, índices) — leer el doc antes de modelar.
- **Reglas de lotería externas**: `Lottery` no debe codificar números máx/min en el modelo si van a ser configuración; decidir qué se persiste vs qué se configura.
- **CRUD scope**: los draws reales necesitan importación (Fase 2); el CRUD de este slice es estructural, con fixtures de prueba.

## Próximos pasos (al iniciar sesión)

1. Leer `openspec/specs/backend/spec.md` (source of truth Fase 0) y `DATABASE_SCHEMA.md`/`API_SPECIFICATION.md`.
2. `/sdd-new fase-1-core-domain` → exploración + proposal con los puntos de riesgo arriba.
3. Seguir pipeline SDD: spec → design → tasks → apply → verify → archive (mismo patrón que Fase 0).
