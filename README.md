#Lottery Intelligence Platform (LIP)

Descripción

Lottery Intelligence Platform (LIP) es una plataforma de investigación estadística y análisis de datos diseñada para estudiar loterías como Baloto y Revancha mediante técnicas de estadística, probabilidad, minería de datos, aprendizaje automático y simulación.

El objetivo del proyecto no es afirmar que puede predecir un sorteo aleatorio, sino construir un laboratorio científico capaz de evaluar cientos de hipótesis, comparar modelos y generar combinaciones basadas en evidencia cuantitativa.

La plataforma está diseñada para ser extensible y permitir la incorporación de nuevas loterías, nuevos modelos matemáticos y nuevas técnicas de inteligencia artificial.

---
Plataforma de investigación estadística para loterías (Baloto, Revancha).
Stack: Python, FastAPI, React, Vite, Tailwind, SQLite.
Filosofía: evidencia antes que conclusiones. Backtesting obligatorio.
Estado: Fase 0 — Diseño y Arquitectura.
EOF

---

Objetivos

Objetivo General

Construir una plataforma profesional de análisis estadístico para loterías que permita investigar patrones históricos, evaluar modelos predictivos, generar combinaciones optimizadas y medir objetivamente el desempeño de cada estrategia mediante backtesting.

---

Objetivos Específicos

- Centralizar el historial completo de sorteos.
- Automatizar la descarga y actualización de resultados.
- Permitir la carga manual de datos históricos.
- Calcular cientos de métricas estadísticas.
- Analizar tendencias históricas.
- Construir modelos de Machine Learning.
- Implementar modelos de Deep Learning.
- Ejecutar simulaciones Monte Carlo.
- Comparar el rendimiento de múltiples algoritmos.
- Implementar un sistema de ranking automático de modelos.
- Generar combinaciones utilizando múltiples estrategias.
- Visualizar toda la información mediante un dashboard interactivo.

---

Filosofía del Proyecto

El proyecto parte de una premisa fundamental:

«Ningún modelo será considerado válido únicamente porque produzca buenos resultados aparentes.»

Toda estrategia deberá demostrar su utilidad mediante procesos de validación, backtesting y comparación con el comportamiento esperado del azar.

Los modelos competirán entre sí y únicamente aquellos que mantengan un rendimiento consistente permanecerán activos dentro del sistema.

---

Alcance

Versión inicial

- Baloto
- Revancha

Versiones futuras

- Cualquier lotería configurable mediante reglas.

---

Arquitectura General

El sistema estará dividido en módulos independientes.

Data Layer

Responsable de:

- Descarga automática de sorteos.
- Carga manual de información.
- Validación.
- Limpieza.
- Normalización.
- Almacenamiento.

---

Feature Engineering

Cada sorteo generará cientos de variables derivadas.

Ejemplos:

- Frecuencia
- Gap
- Edad del número
- Números calientes
- Números fríos
- Suma
- Varianza
- Desviación estándar
- Distribución por decenas
- Primos
- Fibonacci
- Entropía
- Tendencias
- Correlaciones
- Redes de coocurrencia

El objetivo es transformar un simple sorteo en un conjunto rico de variables para alimentar los modelos.

---

Motores Analíticos

Estadística

- Frecuencia absoluta
- Frecuencia relativa
- Frecuencia acumulada
- Percentiles
- Z-Score
- Skewness
- Kurtosis
- Entropía
- Correlaciones
- Covarianza

Probabilidad

- Distribución Binomial
- Distribución Hipergeométrica
- Poisson
- Bayes
- Probabilidad Condicional
- Intervalos de Confianza
- Monte Carlo

Series Temporales

- SMA
- EMA
- Holt
- Holt-Winters
- ARIMA
- SARIMA

Machine Learning

- Random Forest
- XGBoost
- LightGBM
- CatBoost
- Extra Trees
- Gradient Boosting
- SVM
- KNN
- Naive Bayes

Deep Learning

- MLP
- LSTM
- Transformers

Optimización

- Algoritmos Genéticos
- Particle Swarm Optimization
- Simulated Annealing
- Bayesian Optimization

Minería de Patrones

- Apriori
- FP-Growth
- Association Rules

Grafos

- Redes de Coocurrencia
- Centralidad
- Comunidades

---

Meta Learning

El sistema implementará un Meta Evaluador cuya función será analizar continuamente el desempeño de todos los modelos.

No existirá un modelo dominante.

Cada algoritmo competirá utilizando métricas objetivas obtenidas mediante backtesting.

Los modelos con bajo rendimiento podrán ser descartados automáticamente.

---

Inteligencia Artificial

Los modelos de lenguaje (LLM) no se utilizarán para predecir números.

Su función será:

- Explicar resultados.
- Resumir análisis.
- Detectar anomalías.
- Generar hipótesis.
- Asistir en consultas mediante lenguaje natural.
- Documentar automáticamente experimentos.

---

Backtesting

Todos los modelos deberán validarse utilizando información histórica sin acceso al futuro.

El proceso consistirá en entrenar con datos pasados y evaluar únicamente sorteos posteriores.

El objetivo es medir si una estrategia presenta ventajas consistentes frente al azar.

---

Dashboard

El sistema contará con múltiples paneles, entre ellos:

- Historial
- Estadísticas generales
- Heatmaps
- Frecuencias
- Gap
- Hot Numbers
- Cold Numbers
- Distribución de pares e impares
- Distribución por decenas
- Distribución de sumas
- Coocurrencias
- Redes
- Monte Carlo
- Comparador de modelos
- Ranking de estrategias
- Laboratorio de análisis
- Simulador
- Generador inteligente
- Backtesting
- Explorador de Features

---

Generador Inteligente

El sistema generará un gran conjunto de combinaciones candidatas.

Cada combinación será evaluada mediante múltiples modelos.

Posteriormente será clasificada utilizando un sistema de puntuación compuesto.

Finalmente se presentarán únicamente las dos combinaciones con mayor puntuación según la estrategia seleccionada.

---

Tecnologías

Backend

- Python
- FastAPI

Frontend

- React
- Vite
- Tailwind CSS

Base de Datos

- SQLite

Machine Learning

- Scikit-Learn
- XGBoost
- LightGBM
- CatBoost

Deep Learning

- PyTorch
- TensorFlow (opcional)

Visualización

- Plotly
- ECharts

Procesamiento

- Pandas
- NumPy
- SciPy
- Polars

---

Principios

- Arquitectura Modular
- Separación de Responsabilidades
- Escalabilidad
- Reproducibilidad
- Backtesting Obligatorio
- Configuración mediante archivos
- Código desacoplado
- Métricas antes que opiniones
- Evidencia antes que conclusiones

---

Estado del Proyecto

Fase 0 — Diseño y Arquitectura.

---

# Fase 0 — Fundación Backend (implementada)

El backend base ya está operativo (src-layout): arranca con FastAPI, centraliza
la configuración, configura logging estructurado, crea la base SQLite vacía y
expone los endpoints mínimos. **No hay lógica de negocio ni de motores** — eso
pertenece a fases posteriores (1–19).

## Estructura del repositorio

```
backend/
├── pyproject.toml          # Dependencias, extras, pytest y ruff (single source)
├── uv.lock                 # Pines reproducibles (REQ-08)
├── alembic.ini             # Config alembic (dialecto por URL, REQ-09)
├── alembic/                # Sole schema owner (env.py → Base.metadata)
│   └── versions/           # 0001_initial_core_domain, 0002_performance_indexes
├── src/backend/app/
│   ├── main.py             # App factory FastAPI (create_app)
│   ├── api/v1/router.py    # /health, /version + lotteries + draws
│   ├── config/settings.py  # Config centralizada (pydantic-settings)
│   ├── core/               # logging.py, db.py (engine + init_db file-only)
│   ├── models/             # Lottery, Draw, DrawNumber, SuperNumber, Dataset, DatasetDraw
│   ├── repositories/       # base.py + BaseRepository + per-entity repos
│   ├── services/           # draw_service, dataset_service, lottery_service
│   ├── schemas/            # envelope.py, lottery.py, draw.py, dataset.py
│   └── <motores>/          # Seams vacíos (Fases 3+)
├── tests/                  # test_smoke, test_migrations, test_dialect_compat, CRUD...
config/.env.example         # Plantilla de variables (sin secretos)
scripts/                    # run_backend.sh, init_db.sh
database/                   # lip.db (ignorado por git)
```

## Seams de paquetes

`analytics/` compone los motores `statistics` + `probability` (no inventa un
árbol `domain/`). Los motores (`statistics`, `probability`, `feature_engineering`,
`ml`, `dl`, `generators`, `backtesting`, `experiments`, `optimization`,
`simulations`, `importers`, `exporters`, `utils`) existen solo como `__init__.py`
vacíos con docstring de responsabilidad — **sin lógica**.

## Configuración (precedencia LIP_)

Regla determinista: **defaults del código < variables de entorno `.env` con
prefijo `LIP_`**. Los secretos solo vienen del entorno, nunca hardcodeados.
Ejemplos: `LIP_APP_NAME`, `LIP_DATABASE_URL`, `LIP_ALLOWED_ORIGINS`,
`LIP_LOGGING_LEVEL`. Ver `config/.env.example`.

## Scripts

- `scripts/run_backend.sh` → `uv run uvicorn backend.app.main:create_app --reload`
- `scripts/init_db.sh` → crea `database/lip.db` vacía (sin schema)

## Base de datos

SQLite en `<repo>/database/lip.db` por defecto. **Alembic es el único dueño del
schema (REQ-09)**: `init_db()` solo crea el archivo vacío y el engine; el schema
no se construye con `Base.metadata.create_all` sino exclusivamente vía
`alembic upgrade head`. El dialecto se maneja por URL de configuración (SQLite
hoy, PostgreSQL después como swap config-only, ver `pyproject.toml` extra
`dialect-pg`).

## Database Initialization & Migration Flow (Fase 1)

Schema is owned entirely by the Alembic migration set (`backend/alembic/`,
`env.py` → `Base.metadata`). Execution order is deterministic:

1. **`init_db()`** — creates the empty database file at the configured path
   (`database/lip.db`) with **zero tables** (file-only bootstrap; `init_db` never
   creates schema).
2. **`alembic upgrade head`** — applies the Fase 1 migration set. Current head is
   **0002**:
   - `0001_initial_core_domain` — the six tables (`lottery`, `draw`,
     `draw_numbers`, `super_number`, `datasets`, `dataset_draws`) with
     PK/FK/UNIQUE/CHECK and constraint-implied indexes only.
   - `0002_performance_indexes` — the four pre-approved performance indexes
     (`ix_draw_lottery_date`, `ix_draw_lottery_id`, `ix_draw_numbers_draw_id`,
     `ix_dataset_draws_draw_id`). **Additive and functionally optional**: the app
     works with only `0001`, merely slower on those paths.
3. **Boot** — start the backend (`./scripts/run_backend.sh`); the app reads
   through the ORM/repositories over the migrated schema.

Fresh-install bootstrap: `./scripts/init_db.sh && alembic upgrade head`
(from `backend/`), then run the backend.

Upgrade / downgrade (from `backend/`):

```bash
uv run alembic upgrade head     # apply all revisions (base → 0001 → 0002)
uv run alembic upgrade +1        # single step forward
uv run alembic downgrade 0001_initial_core_domain   # drop the perf indexes only
uv run alembic downgrade base     # drop the whole schema
```

The execution order is `init_db()` → `alembic upgrade head` → boot. Never call
`Base.metadata.create_all`; Alembic alone owns the schema.

## Límite del frente

El **frontend (React + Vite + Tailwind) se entrega como un slice encadenado
separado**, NO en este cambio. Aquí no aterriza código de frontend, ni schema
(Fase 1), ni algoritmos de motores (Fases 3+).

## Comandos de desarrollo

```bash
# Tests (desde backend/)
cd backend && uv run pytest

# Lint y formato
cd backend && uv run ruff check .   && uv run ruff format --check .

# Backend con recarga
./scripts/run_backend.sh
```

---

# Fase 3 — Statistics Engine (implementada)

El motor de estadísticas calcula métricas agregadas sobre el historial de
sorteos de una lotería y las persiste como **snapshots** versionados e
inmutables. No predice ni simula: solo describe evidencia cuantitativa de
forma determinista y reproducible.

## Statistics Engine

`backend/src/backend/app/statistics/` implementa el motor:

- `engine.py` — cálculo de frecuencias, gaps y promedios sobre una ventana de
  sorteo, sin estado compartido.
- `generator.py` — orquesta el cómputo del payload y deriva el checksum de
  contenido; define `STATS_GENERATOR_VERSION = "1.0.0"`, la identidad del
  algoritmo que participa en el contrato de determinismo.
- `checksum.py` — hashing determinista del contenido agregado.

El valor que produce es **función de**: el dataset de sorteos + la versión del
generador + el bundle de métricas. Con esos tres fijos, el checksum y el
resultado son idénticos en cualquier ejecución.

## Flujo de generación manual

No hay scheduler: la generación es **bajo demanda**. Se dispara por CLI o por
API, y el resultado queda persistido como snapshot antes de poder leerse.
Generar nunca muta el Historial (Core Domain): solo se escriben filas `stat_*`.

- `generate` — genera con scope `incremental` por defecto. Si ya existe un
  snapshot `active` que reproduce exactamente el resultado prospectivo,
  devuelve ese mismo snapshot (idempotente, no duplica versión). Con scope
  `full`, siempre escribe una versión nueva.
- `rebuild` — fuerza un rebuild completo como **nueva versión** (scope
  `full`); nunca muta un snapshot ya persistido.

## CLI

```bash
cd backend

# Generar un snapshot incremental para una lotería (código natural)
lip statistics generate --lottery <code> [--metrics core] [--scope incremental|full]

# Forzar un rebuild completo como NUEVA versión
lip statistics rebuild --lottery <code> [--metrics core]
```

Cada comando imprime el snapshot generado en JSON: `snapshot_id`, `version`,
`generator_version`, `draws_from`, `draws_to`, `draw_count`, `checksum` y `incremental`.

## API

Prefijo `/statistics`. Generar es un `POST` (escribe); leer es un `GET`
(nunca precompute).

| Método | Ruta | Descripción |
|--------|------|-------------|
| POST | `/statistics/generate` | Genera (o devuelve idempotente) un snapshot. `201` si se crea una versión nueva; `200` si se devuelve un `active` idéntico. |
| GET | `/statistics/{code}/frequencies?last=0` | Frecuencia por número desde el snapshot activo. `last=0` → todos; `last>0` limita. |
| GET | `/statistics/{code}/gaps?last=0` | Resumen de gaps por número (count, min, max, avg) desde el snapshot activo. |
| GET | `/statistics/{code}/averages` | Promedios NULL-aware de las series (D4: jackpot/winners) desde el snapshot activo. |

Errores: lotería desconocida → `RESOURCE_NOT_FOUND` (404); snapshot ausente →
`SNAPSHOT_NOT_FOUND` (404); fallo irrecuperable del motor → `generation_error` (500).

## Contrato de determinismo (G9)

El motor es reproducible si y solo si se cumplen **las tres invariantes**:

1. **mismo dataset** de sorteos (caracterizado por su checksum de origen);
2. **misma versión de generador** (`generator_version` = `1.0.0`);
3. **mismo checksum de contenido** del payload agregado.

Bajo esas tres condiciones, dos ejecuciones independientes producen checksum,
conteo de filas, contenido por tabla, orden de inserción y hash final del
snapshot **byte-idénticos**. El gate G9 lo prueba con dos generaciones
independientes. Si una ejecución se aparta de la especificación del generador,
el resultado ya no es comparable.

## Garantía de solo lectura sobre Core Domain

La generación de snapshots **no modifica** ninguna tabla del Core Domain. Los
gates de integridad verifican que `draw`, `draw_numbers`, `super_number`,
`dataset`, `import_job` e `import_error` quedan byte-idénticos antes/después;
solo aparecen filas `stat_*`. Las lecturas (`GET`) nunca fuerzan generación, no
precompute: sirven desde el snapshot activo.

## Diferencia entre generación y consultas

- **Generación (`POST /statistics/generate`)** — crea/persiste una versión de
  snapshot (transacción con commit); puede retirar la `active` previa y volverla
  `retired`. Es el único path de escritura.
- **Consultas (`GET`)** — de solo lectura: leen la versión activa, nunca
  generan ni mutan estado. `Read `frequencies`, `gaps` y `averages` son puros.

## Política de snapshots (`active | retired | failed`)

Cada `(lottery_id, metric_set)` tiene **exactamente una** snapshot `active`. El
ciclo de vida:

- `active` — la versión vigente desde la que se atienden las lecturas.
- `retired` — una versión que fue activa y quedó superada; se conserva como
  audit trail, no se lee.
- `failed` — una generación que no pudo completarse; la fila queda marcada en
  la misma transacción para auditar el intento fallido sin contaminar la
  versión vigente.

La migración `0005_stat_tables` impone la restricción
`status IN ('active', 'retired', 'failed')` y alembic es el único dueño del
schema. Al generar una versión nueva, la `active` anterior se pasa a `retired`
en la misma transacción (no hay dos `active` simultáneas).

## Comandos de desarrollo (Fase 3)

```bash
cd backend && ./../backend/.venv/bin/pytest tests/statistics -q -p no:cacheprovider  # foco
cd backend && uv run pytest   # suite
cd backend && uv run ruff check . && uv run ruff format --check .  # lint/formato
```
