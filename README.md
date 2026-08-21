# Lottery Intelligence Platform (LIP)

Plataforma de investigación estadística para loterías (Baloto y Revancha) que integra estadística, probabilidad, minería de datos, machine learning, deep learning y backtesting en un solo sistema reproducible.

El objetivo del proyecto **no es afirmar que puede predecir un sorteo aleatorio**, sino construir un laboratorio científico capaz de evaluar hipótesis, comparar modelos entre sí y generar combinaciones basadas en evidencia cuantitativa. Ningún modelo se considera válido por producir buenos resultados aparentes: toda estrategia debe demostrar su utilidad mediante validación y backtesting contra el comportamiento esperado del azar.

**Estado actual:** release candidate [`v1.0.0-rc.1`](https://github.com/guigerdts/LotteryIntelligencePlatform/releases/tag/v1.0.0-rc.1) · versión `1.0.0` · feature freeze activo (solo fixes hasta v1.0.0) · roadmap de 19 fases completado. Detalles en [PROJECT_STATUS.md](PROJECT_STATUS.md) y [RELEASE_VALIDATION.md](RELEASE_VALIDATION.md).

---

## Capacidades principales

- **Core domain**: historial centralizado de sorteos con carga manual e importación automática, validados e inmutables.
- **Datasets derivados**: generación determinista de datasets de entrenamiento a partir del historial.
- **Motores analíticos** (cada uno produce snapshots versionados e inmutables):
  - *Statistics* — frecuencias, gaps y promedios con contrato de determinismo verificado.
  - *Feature Engineering* — variables derivadas por sorteo para alimentar los modelos.
  - *Probability* — distribuciones binomial, hipergeométrica, Poisson, Bayes y Monte Carlo.
  - *Graph* — redes de coocurrencia, centralidad y comunidades.
  - *ML* — entrenamiento de modelos scikit-learn con métricas y ranking comparativo.
  - *DL* — MLP y LSTM en PyTorch (inferencia sin router HTTP montado, por diseño).
  - *Optimization* — algoritmos genéticos (deap) y optimización bayesiana (optuna) sobre combinaciones.
  - *Backtesting* — evaluación histórica sin acceso al futuro; obligatoria antes de considerar válida cualquier estrategia.
  - *Experiments* — registro y comparación objetiva de experimentos entre modelos.
- **Generador inteligente** (`gen`) — combina candidatos evaluados por múltiples modelos con puntuación compuesta.
- **Meta-evaluador** (`meta`) — compara el desempeño de todos los modelos mediante métricas de backtesting; no existe modelo dominante por decreto.
- **Asistente IA** (`ai`) — explica resultados y asiste consultas en lenguaje natural; los LLM no predicen números.
- **API REST v1** documentada + **dashboard web** React + **CLI** `lip` con 12 grupos de comandos.

## Stack tecnológico

| Capa | Tecnología |
|------|------------|
| Backend | Python ≥ 3.12, FastAPI, pydantic-settings |
| Datos | SQLAlchemy + Alembic (16 migraciones, único dueño del schema), SQLite por defecto (PostgreSQL opcional vía extra `dialect-pg`) |
| Ciencia | pandas, NumPy, SciPy, scikit-learn, PyTorch (CPU), optuna, deap |
| Frontend | React, Vite, TypeScript, Tailwind CSS, vitest, Playwright |
| Calidad | pytest + coverage, ruff, ESLint/Prettier, GitHub Actions |

## Arquitectura resumida

Arquitectura modular en capas: `api/v1` (rutas) → `services` → `repositories`/`models` (persistencia). Los motores analíticos son paquetes independientes bajo `backend/src/backend/app/` que leen del Core Domain **en modo solo lectura** y escriben únicamente sus propias tablas de snapshot.

Principios operativos reales del código:

- **Alembic es el único dueño del schema**: nunca se usa `Base.metadata.create_all`.
- **Snapshots versionados e inmutables**: cada `(lottería, metric_set)` tiene exactamente una versión `active`; las previas pasan a `retired` como audit trail. Generar nunca muta el historial.
- **Determinismo por checksums**: mismo dataset + misma versión de generador ⇒ resultado byte-idéntico (verificado por gates automáticos).
- **Configuración single-source** vía `pydantic-settings`; secretos solo del entorno (prefijo `LIP_`).

Detalle completo en [SYSTEM_ARCHITECTURE.md](SYSTEM_ARCHITECTURE.md).

## Estructura del repositorio

```
├── backend/
│   ├── pyproject.toml          # Dependencias, extras, pytest y ruff (single source)
│   ├── alembic/                # 16 migraciones (schema owner)
│   ├── src/backend/app/
│   │   ├── api/v1/             # Rutas REST (prefijo /api/v1)
│   │   ├── models/ repositories/ services/ schemas/
│   │   ├── statistics/ feature_engineering/ probability/ graph/
│   │   ├── ml/ dl/ optimization/ backtesting/ experiments/
│   │   ├── generators/ ai/ analytics/ meta/
│   │   ├── importers/ exporters/ simulations/ utils/
│   │   ├── cli.py              # CLI lip
│   │   └── main.py             # App factory FastAPI
│   └── tests/                  # Suite backend (1434 tests)
├── frontend/                   # React + Vite + TS (137 tests, E2E Playwright)
├── scripts/                    # run_backend.sh, init_db.sh
├── config/.env.example         # Plantilla de variables LIP_
├── database/                   # lip.db (ignorada por git)
├── .github/workflows/          # ci.yml, performance.yml
└── *.md                        # Documentación (ver sección Documentación)
```

## Instalación

Guía completa en [INSTALL.md](INSTALL.md). Resumen:

```bash
# Backend (uv gestiona el venv desde pyproject.toml + uv.lock)
cd backend && uv sync && uv run alembic upgrade head

# Frontend
cd frontend && npm install
```

## Configuración

Toda la configuración se centraliza en `backend/src/backend/config/settings.py` (pydantic-settings). Precedencia: defaults del código < variables `.env` con prefijo `LIP_`. Ejemplos: `LIP_APP_NAME`, `LIP_DATABASE_URL`, `LIP_ALLOWED_ORIGINS`, `LIP_LOGGING_LEVEL`. Plantilla sin secretos en [`config/.env.example`](config/.env.example).

## Ejecución

```bash
./scripts/init_db.sh            # crea database/lip.db vacía (sin schema)
cd backend && uv run alembic upgrade head   # aplica las 16 migraciones
./scripts/run_backend.sh        # backend con recarga (uvicorn)

# Frontend
cd frontend && npm run dev      # dev server Vite
npm run build                   # build producción (tsc -b && vite build)
```

## CLI (`lip`)

La CLI vive en `backend.app.cli` (entry point `lip`). Grupos disponibles:

| Grupo | Descripción |
|-------|-------------|
| `import` | Importación de historiales al Core Domain |
| `dataset-generate` | Generación de datasets derivados |
| `statistics` | Snapshots de estadísticas (generate/rebuild) |
| `feature-engine` | Snapshots de features derivadas |
| `probability` | Snapshots de probabilidad |
| `graph` | Snapshots de grafos de coocurrencia |
| `ml` | Entrenamiento ML, listado de snapshots y métricas |
| `opt` | Entrenamiento de optimizadores (genético/bayesiano) |
| `exp` | Creación, listado, comparación y export de experimentos |
| `bt` | Ejecución de backtests e histórico |
| `meta` | Comparación/ranking de modelos |
| `gen` | Generador inteligente de combinaciones |

Uso típico (orden natural del flujo): `import` → `dataset-generate` → `statistics` / `feature-engine` / `probability` / `graph` → `ml` / `opt` → `bt` / `exp` → `meta` → `gen`.

## API

- Prefijo `/api/v1`; docs interactivas en `/docs` (Swagger UI) con el servidor corriendo.
- Especificación completa: [API_SPECIFICATION.md](API_SPECIFICATION.md).
- Convención: escrituras son `POST`, lecturas son `GET` y jamás disparan cómputo (leen desde el snapshot `active`).
- Errores con envelope tipado (`RESOURCE_NOT_FOUND`, `SNAPSHOT_NOT_FOUND`, …).

## Testing

```bash
# Backend (desde backend/)
.venv/bin/pytest --cov=backend --cov-report=term-missing

# Frontend
cd frontend && npm test          # vitest run

# E2E
cd frontend && npx playwright test
```

Estado medido en la validación de release ([RELEASE_VALIDATION.md](RELEASE_VALIDATION.md)):

| Suite | Resultado |
|-------|-----------|
| Backend | 1434 passed / 1 skipped · cobertura ~92% |
| Frontend | 137 tests × 3 corridas consecutivas verdes |
| E2E (Playwright) | 1/1 PASS contra servidores reales |
| Performance | 3/3 PASS (baselines calibradas 2026-08-21) |

> Nota: la suite backend debe ejecutarse desde `backend/` (el conftest resuelve rutas relativas de alembic).

## Performance

Harness con tres operaciones calibradas (`cold_start`, `cached_statistics_get`, `parallel_bt_train`) con tolerancia ±20% sobre baselines medidas y archivadas en `backend/tests/performance/config.yaml`. El reporte de calibración está en `openspec/changes/archive/2026-08-21-fase-19-release-candidate/perf-report-f19.json`. El workflow [`.github/workflows/performance.yml`](.github/workflows/performance.yml) corre el harness semanalmente (lunes 02:00 UTC).

## CI

[`.github/workflows/ci.yml`](.github/workflows/ci.yml) ejecuta en cada push:

- `backend-tests`: suite sharding en 6 fragmentos con cobertura paralela.
- `coverage-finalize`: consolidación y % final de cobertura.
- `frontend`: lint + tests vitest.
- `gate`: verificación final del pipeline.

## Base de datos

SQLite en `<repo>/database/lip.db` por defecto. Flujo de inicialización: `init_db()` crea el archivo vacío → `alembic upgrade head` construye el schema (16 migraciones) → arranque de la app. El swap a PostgreSQL es config-only (URL + extra `dialect-pg`). Referencia de tablas: [DATABASE_SCHEMA.md](DATABASE_SCHEMA.md).

## Documentación

| Documento | Contenido |
|-----------|-----------|
| [INSTALL.md](INSTALL.md) | Instalación paso a paso |
| [MANUAL_USUARIO.md](MANUAL_USUARIO.md) | Manual de uso end-to-end |
| [MANUAL_TECNICO.md](MANUAL_TECNICO.md) | Manual técnico de operación |
| [SYSTEM_ARCHITECTURE.md](SYSTEM_ARCHITECTURE.md) | Arquitectura del sistema |
| [API_SPECIFICATION.md](API_SPECIFICATION.md) | Contrato completo de la API REST |
| [ENGINE_SPECIFICATIONS.md](ENGINE_SPECIFICATIONS.md) | Especificaciones de cada motor |
| [DATABASE_SCHEMA.md](DATABASE_SCHEMA.md) | Referencia del schema |
| [FEATURE_ENGINEERING.md](FEATURE_ENGINEERING.md) | Catálogo de features |
| [SCIENTIFIC_METHODOLOGY.md](SCIENTIFIC_METHODOLOGY.md) | Metodología científica del proyecto |
| [LOTTERY_THEORY.md](LOTTERY_THEORY.md) | Fundamentos teóricos |
| [CHARTER.md](CHARTER.md) | Carta del proyecto |
| [PROJECT_STATUS.md](PROJECT_STATUS.md) | Estado por fase (F1–F19) |
| [RELEASE_VALIDATION.md](RELEASE_VALIDATION.md) | Evidencia de validación de release |
| [CHANGELOG.md](CHANGELOG.md) / [RELEASE_NOTES.md](RELEASE_NOTES.md) | Historial de cambios y notas de versión |
| [CONTRIBUTING.md](CONTRIBUTING.md) | Guía de contribución |

## Contribución

Lee [CONTRIBUTING.md](CONTRIBUTING.md) (convenciones de commits, estilo, gates obligatorios antes de abrir PR). El proyecto está en **feature freeze**: solo se aceptan fixes hasta el corte de v1.0.0.

## Deuda conocida (documentada, no bloqueante)

- Sin type checker (mypy) ni linter de seguridad (bandit) configurados — post-1.0.
- Inferencia DL sin router HTTP montado (por diseño, `future-dl`).
- Gates de cobertura en CI en modo informativo (política de F17).

## Licencia

Distribuido bajo la [MIT License](LICENSE). Copyright © 2026 guigerdts.
