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

4. Estructura del Proyecto

lip/

backend/
    app/
    api/
    core/
    config/
    models/
    schemas/
    repositories/
    services/
    analytics/
    ml/
    dl/
    optimization/
    experiments/
    generators/
    backtesting/
    simulations/
    feature_engineering/
    statistics/
    probability/
    importers/
    exporters/
    utils/

frontend/
    src/
    pages/
    layouts/
    components/
    charts/
    hooks/
    services/
    store/

database/

docs/

datasets/

experiments/

tests/

scripts/

logs/

---

5. Base de Datos

Inicialmente:

SQLite

Preparada para migrar a PostgreSQL en el futuro sin modificar la lógica de negocio.

---

6. Motores

Data Engine

Responsabilidades:

- Importar datos.
- Validar.
- Limpiar.
- Normalizar.
- Versionar.

---

Statistics Engine

Responsable del cálculo de:

- Frecuencias.
- Distribuciones.
- Tendencias.
- Correlaciones.
- Entropía.
- Indicadores.

---

Probability Engine

Responsable de:

- Monte Carlo.
- Bayes.
- Distribuciones.
- Simulación.
- Probabilidades condicionales.

---

Feature Engine

Generará todas las variables derivadas utilizadas por los modelos.

Cada Feature será un componente independiente.

---

Machine Learning Engine

Responsable de:

- Entrenamiento.
- Predicción.
- Persistencia.
- Comparación.
- Optimización.

---

Deep Learning Engine

Responsable de modelos neuronales.

Ejemplos:

- LSTM
- Transformers
- Redes densas

---

Optimization Engine

Implementará:

- Algoritmos Genéticos.
- PSO.
- Simulated Annealing.
- Bayesian Optimization.

---

Generator Engine

Construirá millones de combinaciones candidatas.

Posteriormente:

- filtrará,
- puntuará,
- clasificará,
- devolverá las mejores.

---

Backtesting Engine

Responsable de:

- Walk-Forward.
- Validación.
- Comparación.
- Benchmark.

---

Experiment Engine

Gestionará:

- Experimentos.
- Versiones.
- Parámetros.
- Resultados.
- Historial.

---

AI Assistant

Integración con LLM.

Funciones:

- Explicar análisis.
- Generar resúmenes.
- Interpretar gráficos.
- Asistir al usuario mediante lenguaje natural.

No participará directamente en el cálculo de combinaciones.

---

7. Dashboard

Módulos principales.

Inicio

Resumen general.

---

Historial

Resultados completos.

---

Estadísticas

Indicadores globales.

---

Heatmaps

Frecuencias visuales.

---

Tendencias

Series temporales.

---

Redes

Coocurrencias.

---

Monte Carlo

Resultados de simulaciones.

---

Machine Learning

Estado y rendimiento de modelos.

---

Backtesting

Comparación histórica.

---

Experimentos

Historial de ejecuciones.

---

Generador

Selección de estrategias y generación de combinaciones.

---

Configuración

Parámetros globales del sistema.

---

8. Flujo General

Importar Datos

↓

Validar

↓

Limpiar

↓

Guardar

↓

Generar Features

↓

Entrenar Modelos

↓

Evaluar

↓

Backtesting

↓

Ranking

↓

Generar Combinaciones

↓

Dashboard

---

9. Configuración

Toda configuración deberá almacenarse fuera del código.

Ejemplos:

- Loterías.
- Rangos de números.
- Parámetros de modelos.
- Número de simulaciones.
- Semillas aleatorias.
- Umbrales.
- Estrategias.

---

10. Observabilidad

El sistema registrará:

- Logs.
- Errores.
- Tiempos.
- Consumo de recursos.
- Versiones de modelos.
- Resultados de experimentos.

---

11. Escalabilidad

La arquitectura permitirá incorporar nuevas loterías únicamente agregando su configuración y reglas, sin modificar el núcleo del sistema.

---

12. Seguridad

- Validación de entradas.
- Control de errores.
- Protección de la base de datos.
- Gestión de configuraciones sensibles mediante variables de entorno.

---

13. Futuras Extensiones

- PostgreSQL.
- Motor distribuido.
- Entrenamiento en GPU.
- API pública.
- Aplicación móvil.
- Notificaciones.
- Integración con nuevas fuentes de datos.
- Módulo de investigación colaborativa.

---

14. Principio Fundamental

Cada componente del sistema deberá poder evolucionar, reemplazarse o ampliarse sin afectar al resto de la plataforma.

La arquitectura prioriza mantenibilidad, reproducibilidad y extensibilidad sobre la complejidad de cualquier algoritmo individual.
