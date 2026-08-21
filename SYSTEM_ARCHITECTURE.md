SYSTEM_ARCHITECTURE.md

Lottery Intelligence Platform (LIP)

System Architecture

Versión: 2.0

Estado: Activo — describe la implementación real del backend (Fases 0–17).

---

## 1. Visión general

Lottery Intelligence Platform (LIP) es una plataforma de análisis estadístico y generación asistida de combinaciones para loterías. El backend es una aplicación FastAPI organizada según una arquitectura hexagonal (puertos y adaptadores): los motores de dominio son paquetes Python puros que reciben datos mediante protocolos explícitos (seams `Provider`) y no importan infraestructura directamente; la capa de servicios orquesta motores, persistencia e idempotencia; y la capa API expone todo bajo `/api/v1` con un envelope de respuesta estándar (`SuccessEnvelope` / `ErrorEnvelope`).

Dimensiones verificadas del paquete `backend/src/backend/app/`:

| Métrica | Valor |
|---------|-------|
| Módulos de primer nivel | 25 directorios + `main.py` + `cli.py` |
| Archivos Python | 237 |
| Líneas de código | ≈ 23.6k (23.648) |

### Capas

| Capa | Ubicación | Responsabilidad |
|------|-----------|-----------------|
| API | `api/` | Errores de dominio (`errors.py`) y routers v1: 13 routers de dominio + `health`/`version` |
| Servicios | `services/` | Lógica de aplicación: 15 servicios que orquestan motores y persistencia |
| Motores de dominio | `statistics`, `probability`, `graph`, `ml`, `dl`, `opt`, `backtesting`, `experiments`, `meta`, `generators`, `feature_engineering`, `ai` | Cálculo puro y determinista |
| Persistencia | `repositories/`, `models/` | SQLAlchemy sobre SQLite: 38 entidades ORM; el esquema es propiedad de las migraciones Alembic |
| Transversal | `config/`, `core/`, `schemas/`, `utils/` | Configuración única (`Settings`), logging estructurado, caché de respuestas, envelope Pydantic |

Flujo de una petición:

```text
HTTP → api/v1/{router} → services/{motor}_service → motor de dominio
     → repositories/ + models/ (SQLAlchemy · SQLite · Alembic)
```

`main.py:create_app()` construye la aplicación: configura el logging con el formato estructurado del proyecto, monta CORS desde `Settings.allowed_origins`, incluye el router v1 bajo `settings.api_v1_prefix` y registra los manejadores globales que traducen toda falla al envelope `ErrorEnvelope`. El ciclo de vida (`lifespan`) garantiza la existencia del archivo SQLite mediante `init_db`; la creación de tablas nunca ocurre en código de aplicación — las migraciones Alembic son dueñas del esquema.

---

## 2. Estructura de módulos

Árbol real de `backend/src/backend/app/` (25 módulos + 2 archivos raíz):

```text
backend/src/backend/app/
├── main.py                  # Fábrica create_app(): logging, CORS, router, errores globales
├── cli.py                   # CLI `lip`: importación, generación de datasets y snapshots (FES-09)
├── ai/                      # Asistente IA determinista basado en reglas (Fase 15, A-06..A-10)
├── analytics/               # Scaffold Fase 0 sin implementar (composición prevista stats+probabilidad)
├── api/                     # Capa REST: errors.py + routers v1 (incluye etag.py auxiliar)
├── backtesting/             # Motor BT: validación walk-forward (Fase 10, BTE-01..18)
├── config/                  # Settings pydantic-settings: punto único de configuración
├── core/                    # Bootstrap transversal: db.py, logging.py, response_cache.py
├── dl/                      # Motores DL PyTorch: registro core-3 (MLP, LSTM) — sin router montado
├── experiments/             # Motor de experimentos: orquestación EXP-001 (Fase 11)
├── exporters/               # Capa de exportación de datos (Fase 2)
├── feature_engineering/     # Motor de features: cómputo puro compute(ctx) (FES-06)
│   └── features/            # Catálogo de features puras (base, counters, highlow, tail, …)
├── generators/              # Generador GEN: combinaciones deterministas (allocation, sampling, identity)
├── graph/                   # Motor de grafos: coocurrencia, centralidad, comunidades (GM-01..05)
├── importers/               # Capa de importación de datos (Fase 2)
├── meta/                    # Meta Learning: ranking y selección determinista de modelos
├── ml/                      # Motores ML clásicos: registro core-5 scikit-learn (MLE-04/07)
├── models/                  # 38 entidades ORM SQLAlchemy (esquema Fase 1+, migraciones Alembic)
├── opt/                     # Optimización: hiperparámetros GA/PSO/SA/Bayesiana (búsqueda determinista)
├── optimization/            # Scaffold Fase 0 sin implementar (el motor real es opt/)
├── probability/             # Motor de probabilidad: distribuciones, bayes, Monte Carlo (Fase 5)
├── repositories/            # Frontera de acceso a datos: Base, engine y sesión desde settings
├── schemas/                 # Esquemas Pydantic: envelopes Success/Error y contratos de API
├── services/                # Seam de lógica de aplicación: 15 servicios + errors.py + helpers.py
├── simulations/             # Scaffold Fase 0 sin implementar (Monte Carlo vive en probability/)
├── statistics/              # Motor estadístico: métricas puras y deterministas + checksums
└── utils/                   # Utilidades compartidas
```

Notas honestas sobre el árbol:

- `analytics/`, `optimization/` y `simulations/` son scaffolds de la Fase 0: contienen únicamente el docstring de `__init__.py`. El optimizador real es `opt/` y la simulación Monte Carlo está implementada en `probability/engine.py`.
- `dl/` tiene motor completo (ventanas, secuencias, pesos, MLP/LSTM) pero no expone router en `api/v1`: no es accesible por HTTP.

---

## 3. Seams de motores

Los motores comparten un patrón de integración basado en seams explícitos (la presencia exacta varía por motor):

| Seam | Archivo típico | Rol |
|------|----------------|-----|
| Orquestación | `engine.py` | Punto de entrada que coordina las operaciones del motor |
| Despacho | `registry.py` | Registro dict-dispatch de métodos/modelos (sin herencia) |
| Determinismo | `fingerprint.py`, `determinism.py` | Huella SHA-256 de entradas y control de aleatoriedad |
| Datos | `providers.py` | Protocolo `Provider`: único punto de entrada de datos del motor |
| Persistencia | `snapshot_store.py` | Dueño de la E/S de las tablas `*_snapshot` (ciclo active→retired) |
| Versionado | `version.py` | Versión del generador incluida en huellas y snapshots |

### meta — Meta Learning

- `types.py`: `ContextVector` inmutable (`lottery_id`, `draws_from/to`, `cut`, `window`, `engine_type`) cuyo hash SHA-256 produce el `context_hash`; `WeightConfig` con pesos por defecto hit_rate=0.3, average_matches=0.3, consistency_score=0.2, precision=0.1, recall=0.1 (rechaza suma cero).
- `ranking.py` / `selection.py`: `rank()` y `select()` con idempotencia por fingerprint.
- `snapshot_store.py`: `MetaSnapshotStore` posee la E/S de `meta_rankings`/`meta_selections`: versionado monótono, retiro del registro activo previo (active→retired) y escritura atómica con entradas.
- Expuesto vía `api/v1/meta.py` (META-013).

### probability — Probabilidad (Fase 5)

- `providers.py`: contratos `Protocol` del Provider — el ÚNICO seam de datos del motor (PES-06).
- `registry.py`: despacho dict-dispatch sin dependencia de Kahn (D-A2); incluye el método `monte_carlo`.
- `engine.py`: distribuciones, probabilidad condicional/bayesiana y simulación Monte Carlo.
- `snapshot_store.py`, `fingerprint.py` y `determinism.py` completan el patrón.

### graph — Grafos

- `engine.py` orquesta GM-01..GM-05 con fingerprint determinista.
- Construcción: `cooccurrence.py` y `construction.py`; análisis: `centrality.py`, `community.py`; métricas en `metrics.py`.
- `snapshot_store.py` propio para la persistencia de snapshots del motor.

### ml — Machine Learning clásico (Fases 7-8)

- `registry.py`: registro core-5 solo scikit-learn (MLE-04/07, M-A2): `random_forest`, `extra_trees`, `gradient_boosting`, `svm`, `knn`.
- Completan el patrón `splitter.py`, `feature_reader.py`, providers/fingerprint/determinism/version y `snapshot_store.py`.

### bt — Backtesting (Fase 10)

- `types.py`: `DrawContext` con ventana histórica expansiva sin datos futuros (BTE-17); `BacktestConfig` walk-forward (train_years=5, seed=42, benchmark «both»); `MetricSet` cuantizado a Decimal(20,8) (BTE-08); `WindowResult` y `BacktestResult`.
- `benchmark.py` compara contra los benchmarks uniforme e hipergeométrico; `splitter.py` divide las ventanas walk-forward; `strategy.py` y `metrics.py` completan el motor.

### opt — Optimización

- Buscadores deterministas de hiperparámetros para modelos ML/DL: `ga.py` (genético), `pso.py` (enjambre), `sa.py` (recocido simulado) y `bayesian.py`.
- `search_space.py`, `objective.py` y `convergence.py` definen espacios, función objetivo y criterios de parada; `registry.py` registra los espacios de parámetros por buscador.

### feature_engineering — Features (FES)

- `context.py`: `FeatureContext` entregado a cada `compute(ctx)` pura; `DrawRow` ordenada por el eje oficial `draw_number` (nunca `draw_date`) y `LotteryRules` inmutable.
- `features/`: catálogo de features puras registradas desde `base.py` (contadores, high/low, cola, …).
- Restricción FES-06: ningún módulo del motor importa `models`, `statistics` ni `repositories`.

### generators — Generador (GEN)

- `allocation.py`: aritmética entera exacta de micro-unidades (GEN-004); `sampling.py`: generación ponderada por F5 con remuestreo (GEN-005/006); `identity.py` y `validation.py` completan el pipeline determinista.
- `snapshot_store.py` y `version.py` persisten y versionan resultados; expuesto vía `api/v1/gen.py` (4 endpoints, GEN-010).

### ai — Asistente (Fase 15)

- `engine.py`: motor determinista basado en reglas — cinco funciones + clasificador de intenciones (A-06..A-10).
- `generators.py`: formateo seguro con Decimal (nunca float, A-03) y constructores de contexto de plantillas; `prompts.py` centraliza los textos.
- Expuesto vía `api/v1/assistant.py`: 5 endpoints con envelope (A-06..A-12). El asistente opera sobre datos ya calculados; el cálculo de combinaciones vive en `generators/`.

---

## 4. Ciclo de vida de snapshots

Cada motor materializa sus resultados como snapshots versionados e inmutables en SQLite. El ciclo de vida es común a todos los motores y vive en un único dueño de E/S por motor (`snapshot_store.py`, o el repositorio equivalente):

1. **Fingerprint** — las entradas relevantes se resumen en un hash SHA-256 (`fingerprint` / `input_fingerprint`), clave canónica de invalidación.
2. **Idempotencia** — si ya existe un snapshot `active` con el mismo fingerprint, se devuelve tal cual sin recomputar (`find_by_fingerprint`).
3. **Versión monótona** — `next_version()` calcula el siguiente número humano dentro del ámbito `(lottery_id, …)` propio del motor.
4. **Escritura atómica** — la nueva cabecera (`status='active'`) y su payload se insertan en la misma transacción que retira el activo previo (`status='retired'`).
5. **Fallo terminal** — ante un error, `mark_failed()` marca el snapshot como `failed` (terminal); nunca existen snapshots `active` parciales.

El dominio del ciclo lo posee la base de datos mediante restricciones `CHECK` (`status IN ('active', 'retired', 'failed')`); la inmutabilidad la aplica el servicio mediante el flip de `status`, nunca triggers del dialecto.

| Motor | Dueño de E/S | Ámbito del snapshot | Cabecera | Payload |
|-------|--------------|---------------------|----------|---------|
| meta | `MetaSnapshotStore` | `(lottery_id, context_hash)` | `MetaRanking` / `MetaSelection` | `MetaRankingEntry` / `MetaSelectionEntry` |
| probability | `SnapshotStore` (`probability/snapshot_store.py`) | `(lottery_id, model_set)` | `ProbSnapshot` | `ProbValue` |
| graph | funciones de módulo (`graph/snapshot_store.py`) | loto + tipo de grafo | `GraphSnapshot` | `GraphValue` |
| ml | `MlSnapshotStore` | `(lottery_id, model_set)` | `MlSnapshot` | `MlMetric` |
| bt | `BtSnapshotStore` | `(lottery_id, strategy_id)` | `BtSnapshot` | `BtResult` |
| opt | `OptSnapshotStore` | `(lottery_id, optimizer)` | `OptSnapshot` | `OptResult` |
| feature_engineering | `FeatureEngineService` + repositorios | `(lottery_id, feature_set)` | `FeatureSnapshot` | `FeatureValue` |

Notas sobre la tabla:

- `statistics` pertenece a la misma familia: `StatisticsService` persiste vía `StatSnapshotRepository` y `StatPayloadRepository` (payload repartido en las tablas `stat_*`).
- Variante `bt`: `create_active()` elimina primero las filas del mismo fingerprint — la unicidad `(lottery_id, strategy_id, fingerprint)` lo exige — y crea la nueva versión en una sola transacción.
- `dl`: las entidades `DlSnapshot` / `DlMetric` / `DlWeight` y sus tablas existen (migración `0010_dl_tables`), pero hoy ningún store ni servicio escribe snapshots DL; `meta_service` y `exp_service` únicamente leen filas `active` como candidatos.
- `generators`: `GenSnapshot` comparte el mismo trío de estados (`CHECK` idéntico) y `lip gen snapshot` transiciona su estado de ciclo de vida.

---

## 5. Base de datos y migraciones

SQLite en un único archivo (ruta resuelta por `Settings`), accedido mediante SQLAlchemy. La frontera de acceso a datos es `repositories/base.py`: declara `Base` (`DeclarativeBase`), construye el `engine` desde la configuración y expone la fábrica de sesiones `SessionLocal` junto a `get_db()`, la dependencia FastAPI que hace rollback ante errores y siempre cierra la sesión.

El esquema es propiedad exclusiva de las migraciones Alembic: `Base.metadata.create_all` no se usa en ninguna parte; el `lifespan` de la aplicación solo garantiza la existencia del archivo SQLite (`init_db`). `alembic/env.py` fija `target_metadata = Base.metadata` (importar el paquete `models` registra todas las tablas), habilita `render_as_batch=True` para DDL portátil en SQLite y resuelve la URL de la base desde el override `sqlalchemy.url` de `alembic.ini` (usado por tests) o, en su defecto, desde los settings de la aplicación. Los comandos se ejecutan desde `backend/`, donde vive `alembic.ini`:

```bash
alembic upgrade head   # aplica todas las migraciones hasta 0016
alembic heads          # 0016_exp_comparisons_run_ids (head)
```

Migraciones reales (`backend/alembic/versions/`, 16 en total):

| Migración | Contenido |
|-----------|-----------|
| `0001_initial_core_domain` | Esquema núcleo del dominio (loterías, sorteos, datasets, importaciones) |
| `0002_performance_indexes` | Índices de rendimiento |
| `0003_imports_audit` | Auditoría de importaciones |
| `0004_import_performance_indexes` | Índices de rendimiento de importación |
| `0005_stat_tables` | Tablas `stat_*` del motor estadístico |
| `0006_feature_tables` | Tablas de features |
| `0007_probability_tables` | Tablas de probabilidad |
| `0008_graph_tables` | Tablas de grafos |
| `0009_ml_tables` | Tablas de ML |
| `0010_dl_tables` | Tablas de DL |
| `0011_opt_tables` | Tablas de optimización |
| `0012_bt_tables` | Tablas de backtesting |
| `0013_exp_tables` | Tablas de experimentos |
| `0014_meta_tables` | Tablas de Meta Learning |
| `0015_gen_tables` | Tablas del generador |
| `0016_exp_comparisons_run_ids` | **(head)** comparaciones de experimentos por IDs de run |

Las 38 entidades ORM de `models/` se agrupan por familias: dominio núcleo (`Lottery`, `Draw`, `DrawNumber`, `SuperNumber`, `Dataset`, `DatasetDraw`, `ImportJob`, `ImportError`), una familia por motor (`Stat*`, `Feature*`, `Prob*`, `Graph*`, `Ml*`, `Dl*`, `Opt*`, `Bt*`, `Exp*`, `Meta*`, `Gen*`). En `repositories/` conviven `base.py`, el CRUD genérico `base_repository.py`, `errors.py` y 12 repositorios de dominio (draws, datasets, lotteries, imports, features, stats, super_numbers, …).

---

## 6. CLI `lip`

El entry point está declarado en `backend/pyproject.toml` (`[project.scripts]`: `lip = "backend.app.cli:main"`). La CLI es argparse puro: resuelve el código de lotería vía repositorio y delega todo el trabajo en los servicios; nunca hace shell-out ni toca la capa HTTP. No existe scheduler: todas las operaciones son explícitas y bajo demanda (IE-08). `lip import` registra la corrida con `import_type="cli"` y `started_by` tomado del usuario invocante; ante un `ServiceError` imprime `[código] mensaje` por stderr y sale con código 1.

Los 12 grupos (`lip --help`):

| Grupo | Subcomandos | Propósito |
|-------|-------------|-----------|
| `import` | — | Importa un CSV de historial (`--resume` reanuda corridas parciales coincidentes) |
| `dataset-generate` | — | Genera un dataset inmutable y bloqueado |
| `statistics` | `generate`, `rebuild` | Snapshot estadístico bajo demanda |
| `feature-engine` | `generate`, `rebuild` | Snapshot de features bajo demanda |
| `probability` | `generate`, `rebuild` | Snapshot de probabilidad bajo demanda |
| `graph` | `compute`, `list`, `show` | Computa y consulta snapshots de grafos |
| `ml` | `train`, `models`, `metrics` | Entrena las familias core-5 y consulta snapshots/métricas |
| `opt` | `train`, `models`, `metrics`, `params` | Pasadas de optimización y resultados |
| `exp` | `create`, `list`, `compare`, `export` | Experimentos: creación, comparación y exportación JSON/CSV |
| `bt` | `run`, `history`, `results` | Backtests walk-forward e histórico |
| `meta` | `rank`, `ranking`, `select`, `selection` | Rankings y selecciones de Meta Learning |
| `gen` | `generate`, `combinations`, `snapshot`, `snapshots` | Generación y consulta de combinaciones |

Ejemplos de uso:

```bash
lip --help                                      # descubrimiento de grupos
lip import --lottery <codigo> --file <ruta.csv> # importación con auditoría JSON
lip import --lottery <codigo> --file <ruta.csv> --resume   # reanudar parcial
lip <grupo> --help                              # ayuda detallada por grupo
```

---

## 7. Frontend

SPA en React 19 + TypeScript construida con Vite. Dependencias declaradas en `package.json`: `react-router-dom` 7 (enrutamiento con `createBrowserRouter`), `zustand` 5 (estado), `recharts` 3 (gráficos) y `react-force-graph-2d` (grafos). Las 13 entradas de `App.tsx` renderizan dentro de `DashboardLayout`; cada página se carga lazy con un fallback `Suspense` compartido (`PageFallback` sobre `Skeleton`).

Tabla de rutas real (`App.tsx`):

| Ruta | Componente (`frontend/src/pages/`) |
|------|------------------------------------|
| `/` (index) | `Home.tsx` |
| `/historial` | `History.tsx` |
| `/estadisticas` | `Statistics.tsx` |
| `/heatmaps` | `Heatmaps.tsx` |
| `/tendencias` | `Trends.tsx` |
| `/redes` | `Networks.tsx` |
| `/monte-carlo` | `MonteCarlo.tsx` |
| `/ia` | `IA.tsx` |
| `/modelos` | `Models.tsx` |
| `/experimentos` | `Experiments.tsx` |
| `/backtesting` | `Backtesting.tsx` |
| `/generador` | `Generator.tsx` |
| `*` | `NotFound` (404 inline en `App.tsx`) |

Estructura de `frontend/src/`:

```text
frontend/src/
├── App.tsx        # Tabla de rutas + fallback 404
├── main.tsx       # Bootstrap React + router
├── charts/        # 5 gráficos: frecuencia, gaps, medias, heatmap, distribución
├── components/    # 11 compartidos: Sidebar, DataTable, LotterySelector, estados, …
├── hooks/         # useApi, useLotteries
├── layouts/       # DashboardLayout (shell común del dashboard)
├── pages/         # 12 páginas, cada una con su .test.tsx
├── services/      # api.ts + 11 módulos de dominio
├── store/         # useLotteryStore, useModuleStore (zustand)
└── types/         # contratos TS: envelope y dominios
```

`services/api.ts` centraliza el acceso HTTP: `apiClient()` resuelve la base como `VITE_API_BASE_URL` o `/api/v1` por defecto, desenvuelve el `SuccessEnvelope` y traduce el `ErrorEnvelope` y los códigos HTTP a errores tipados (`NotFoundError` 404, `ConflictError` 409, `ValidationError` 422, `ServerError` 5xx). Sobre él se apoyan los 11 módulos de dominio (`assistant`, `backtesting`, `draws`, `experiments`, `gen`, `graph`, `lotteries`, `ml`, `probability`, `statistics`, `system`), uno por área de la API.

---

## 8. Despliegue

No hay demonios ni schedulers: toda operación pesada es bajo demanda, vía API REST o CLI. Dos procesos de desarrollo y un archivo SQLite componen todo el despliegue.

Backend (uvicorn contra la fábrica, layout `src`):

```bash
scripts/run_backend.sh
# ≡ uv run --directory backend uvicorn backend.app.main:create_app \
#     --app-dir backend/src --reload
```

Base de datos: `scripts/init_db.sh` ejecuta `init_db()` para crear el archivo SQLite vacío; el esquema se aplica después con `alembic upgrade head` desde `backend/` (deja la base en `0016`). CORS se configura desde `Settings.allowed_origins`.

Frontend (Vite, puerto 5173 en desarrollo):

```bash
npm run dev       # servidor de desarrollo Vite
npm run build     # tsc -b && vite build
npm run lint      # eslint .
npm run test      # vitest run
```

