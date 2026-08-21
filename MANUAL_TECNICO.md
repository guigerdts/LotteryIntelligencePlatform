# Manual Técnico — Lottery Intelligence Platform

> **Versión**: 1.0 · **Estado**: Activo · **Última actualización**: 2026-08-20
>
> Este manual describe la arquitectura técnica de los motores de análisis del backend.
> Cada sección es trazable al código fuente; no se inventan funciones ni parámetros.

---

## 1. Introducción

### 1.1 Propósito

Este manual documenta los motores de análisis del backend: estadísticas, probabilidad,
feature engineering y grafo. Cada motor es un módulo independiente con seam clara
(Protocol), determinismo garantizado (mismas entradas → mismas salidas) y persistencia
de snapshots versionados.

### 1.2 Convenciones

- **Idioma**: español
- **Código fuente**: inglés
- **Tipos numéricos**: `Decimal` (nunca `float`) en valores de salida
- **Determinismo**: todos los motores son deterministas; los modelos estocásticos
  (Monte Carlo) usan `random.Random(seed)` aislado
- **Envolvente**: todas las respuestas HTTP usan `SuccessEnvelope` o `ErrorEnvelope`

### 1.3 Dependencias entre motores

| Motor | Depende de | Lee | Escribe |
|-------|-----------|-----|---------|
| Estadísticas | `draw`, `lottery` | Core tables | `stat_*` |
| Probabilidad | Estadísticas, Feature Eng. | `stat_*`, `feature_*`, `draw` | `prob_*` |
| Feature Eng. | `draw`, `lottery` | Core tables | `feature_*` |
| Grafo | `draw` | Core tables | `graph_*` |

---

## 2. Motor de Estadísticas

**Módulo**: `backend.app.services.statistics_service`
**API**: `POST /statistics/generate`, `GET /statistics/{lottery_code}/snapshots`
**Snapshot store**: `backend.app.repositories.stat_snapshot_repository`

### 2.1 Funcionalidades

El motor calcula métricas estadísticas sobre sorteos históricos y las persiste como
snapshots inmutables versionados.

| Métrica | Función del motor | Descripción |
|---------|-------------------|-------------|
| Frecuencia | `statistics.engine.frequency` | Conteo de apariciones por número |
| Promedio posicional | `statistics.engine.positional_frequency` | Frecuencia por posición |
| Brechas (gaps) | `statistics.engine.gaps` | Sorteos entre apariciones |
| Promedio | `statistics.engine.null_aware_average` | Promedio de valores numéricos |
| Entropía | `statistics.engine.entropy_base2` | Aleatoriedad de la distribución |

### 2.2 Scopes de generación

| Scope | Comportamiento |
|-------|---------------|
| `full` | Siempre crea una nueva versión del snapshot |
| `incremental` | Reutiliza snapshot activo si el checksum coincide (idempotente) |

### 2.3 Ciclo de vida del snapshot

```
generar → checksum → validar → persistir NUEVA versión → retirar anterior (misma tx)
```

- En error: snapshot terminal `failed` (nunca `active`/`partial`)
- Reintentar: siempre crea versión nueva (no reutiliza `failed`)

### 2.4 Tablas persistidas

| Tabla | Contenido |
|-------|-----------|
| `stat_snapshot` | Metadatos de versión (checksum, generator_version, scope, status) |
| `stat_frequency` | Frecuencias por número |
| `stat_average` | Promedios por posición |
| `stat_gap` | Brechas entre apariciones |
| `stat_scalar` | Métricas escalares (entropía, etc.) |

---

## 3. Motor de Probabilidad

**Módulo**: `backend.app.services.probability_service`
**API**: `POST /probability/generate`, `GET /probability/{lottery_code}/snapshots`
**Snapshot store**: `backend.app.probability.snapshot_store`

### 3.1 Modelos matemáticos

| Modelo | Función | Tipo | Descripción |
|--------|---------|------|-------------|
| Hipergeométrica | `probability.engine.hypergeometric` | Exacto | P(X=k) = C(r,k)·C(N-r,n-k)/C(N,n) |
| Binomial | `probability.engine.binomial` | Exacto | P(X=k) = C(n,k)·p^k·(1-p)^(n-k) |
| Poisson | `probability.engine.poisson` | Exacto | P(X=k) = λ^k·e^(-λ)/k! |
| Bayes | `probability.engine.bayes` | Exacto | P(A|B) = P(B|A)·P(A)/P(B) |
| Condicional | `probability.engine.conditional` | Exacto | P(A∩B) = P(A|B)·P(B) |
| Empírico | `probability.engine.empirical` | Exacto | Frecuencia observada como probabilidad |
| Monte Carlo | `probability.engine.monte_carlo` | Estocástico | Simulación con seed aislada |

### 3.2 Precisión numérica

- Contexto Decimal: `prec = 50` (alta precisión)
- Nunca `float` en valores de salida
- Monte Carlo usa `random.Random(seed)` aislado (nunca el módulo global)

### 3.3 Orquestación

```
resolve lottery → compute providers → execute registry → fingerprint → checksum → persist
```

- `ProbMethodRegistry`: registry de métodos registrados por el motor
- Lectura: solo desde snapshots almacenados (nunca precomputa en `read()`)

### 3.4 Tablas persistidas

| Tabla | Contenido |
|-------|-----------|
| `prob_snapshot` | Metadatos de versión |
| `prob_value` | Valores de probabilidad por número/método |

---

## 4. Motor de Feature Engineering

**Módulo**: `backend.app.services.feature_engine_service`
**API**: `POST /feature-engine/generate`, `GET /feature-engine/{code}/features`
**Snapshot store**: `backend.app.repositories.feature_snapshot_repository`

### 4.1 Features implementadas (FE-01..FE-10)

| ID | Función | Descripción |
|----|---------|-------------|
| FE-01 | `current_frequency` | Frecuencia actual en ventana |
| FE-02 | `consecutive_count` | Apariciones consecutivas |
| FE-03 | `draw_sum` | Suma de números del sorteo |
| FE-04 | `draw_mean` | Promedio del sorteo |
| FE-05 | `draw_range` | Rango (max - min) |
| FE-06 | `odd_even_ratio` | Proporción impar/par |
| FE-07 | `low_high_ratio` | Proporción bajo/alto |
| FE-08 | `max_current_gap` | Brecha máxima actual |
| FE-09 | `decade_distribution` | Distribución por decenas |
| FE-10 | `repeated_from_previous` | Repetidos del sorteo anterior |

### 4.2 Registry

El registry se construye con `build_feature_registry()` y contiene las 10 features
core-domain (FE-01..FE-10) más una feature `future-statistics` declarada pero nunca
programada.

### 4.3 Determinismo

- Ambos scopes (`full`/`incremental`) recomputan sobre el conjunto completo de sorteos
- La diferencia es solo idempotencia: `incremental` reutiliza si el fingerprint coincide
- `FEATURE_GENERATOR_VERSION` está fijado en `feature_engineering/registry.py`

### 4.4 Tablas persistidas

| Tabla | Contenido |
|-------|-----------|
| `feature_snapshot` | Metadatos de versión |
| `feature_value` | Valores de features por sorteo |

---

## 5. Motor de Grafo

**Módulo**: `backend.app.graph`
**API**: `POST /graph/generate`, `GET /graph/{lottery_code}/snapshots`
**Snapshot store**: `backend.app.graph.snapshot_store`

### 5.1 Componentes

| Módulo | GM | Descripción |
|--------|-----|-------------|
| `cooccurrence` | GM-01 | Matriz de co-ocurrencia entre números |
| `construction` | GM-02 | Construcción de adyacencia desde co-ocurrencia |
| `centrality` | GM-03 | Métricas de centralidad (grado, cercanía, intermediación) |
| `community` | GM-04 | Detección de comunidades (modularidad greedy) |
| `metrics` | GM-05 | Métricas globales del grafo |

### 5.2 Algoritmos de centralidad

| Métrica | Algoritmo | Complejidad |
|---------|-----------|-------------|
| Grado | Vecinos / (V-1) | O(1)/nodo |
| Cercanía | (V-1) / Σ(caminos más cortos) | O(V²) |
| Intermediación | Brandes con conteo entero | O(VE) |

### 5.3 Detección de comunidades

- Algoritmo: modularidad greedy pura (sin PRNG)
- Orden canónico de nodos, tie-break por ID
- Complejidad: O(VE)

### 5.4 Co-ocurrencia

- Matriz simétrica de frecuencia de aparición conjunta
- Ventana paramétrica (parámetro `window`)
- El fingerprint incluye el parámetro de ventana (REQ-06, A6)

### 5.5 Construcción de adyacencia

- Convierte co-ocurrencia en grafo ponderado
- Función `build_adjacency(cooccurrence_matrix)` → `dict[int, dict[int, int]]`
- Filtra aristas por umbral mínimo

### 5.6 Métricas globales

- `graph.metrics`: métricas derivadas del grafo completo
- Número de nodos, aristas, peso total, modularidad

### 5.7 Tablas persistidas

| Tabla | Contenido |
|-------|-----------|
| `graph_snapshot` | Metadatos de versión |
| `graph_node` | Nodos del grafo (números) |
| `graph_edge` | Aristas ponderadas |
| `graph_community` | Asignación de comunidades |
| `graph_centrality` | Scores de centralidad por nodo |

---

## 6. Motor de Machine Learning

**Módulo**: `backend.app.ml`
**API**: `POST /ml/generate`, `GET /ml/{lottery_code}/snapshots`
**Snapshot store**: `backend.app.ml.snapshot_store`

### 6.1 Familias de modelos

El motor entrena modelos de clasificación para predecir la participación de cada número
en el próximo sorteo. Usa walk-forward split y métricas cuantizadas a Decimal.

| Componente | Módulo | Descripción |
|------------|--------|-------------|
| Engine | `ml.engine` | Orquesta training con ProcessPoolExecutor (2 workers) |
| Features | `ml.features` | ML_FEATURE_ORDER — orden fijo de features de F4 |
| Splitter | `ml.splitter` | Walk-forward split (train ≤ cut < eval) |
| Registry | `ml.registry` | Familias de modelos registradas |
| Determinism | `ml.determinism` | Cuantización de métricas a Decimal(20,8) |

### 6.2 Métricas

| Métrica | Descripción |
|---------|-------------|
| `accuracy` | Precisión global |
| `precision` | Precisión por clase positiva |
| `recall` | Exhaustividad |
| `f1` | Media armónica precision/recall |
| `roc_auc` | Área bajo la curva ROC |

### 6.3 Datos de entrada

- **X**: vector F4 por sorteo (features de Feature Engineering, orden fijo)
- **y**: participación de cada número en sorteo n+1 (label binario)
- Split: walk-forward (train ≤ cut < eval)

### 6.4 Tablas persistidas

| Tabla | Contenido |
|-------|-----------|
| `ml_snapshot` | Metadatos de versión |
| `ml_metric` | Métricas por familia/lotería |
| `ml_value` | Predicciones por número |

---

## 7. Motor de Backtesting

**Módulo**: `backend.app.backtesting`
**API**: `POST /backtesting/run`, `GET /backtesting/{lottery_code}/snapshots`
**Snapshot store**: `backend.app.backtesting.snapshot_store`

### 7.1 Orquestación

El motor ejecuta un ciclo completo de backtesting walk-forward:

```
validar datos → generar ventanas → evaluar estrategia + benchmark → computar métricas → agregar
```

### 7.2 Componentes

| Módulo | Descripción |
|--------|-------------|
| `backtesting.engine` | Orquestador principal (ProcessPoolExecutor, 2 workers) |
| `backtesting.strategy` | `StaticStrategy` — estrategia estática basada en predicciones |
| `backtesting.benchmark` | `HypergeometricBenchmark`, `UniformRandomBenchmark` |
| `backtesting.splitter` | `WalkForwardSplitter` — generación de ventanas |
| `backtesting.metrics` | `LotteryMetrics` — métricas específicas de lotería |
| `backtesting.types` | Tipos: `BacktestConfig`, `BacktestResult`, `Draw`, `Window` |

### 7.3 Métricas de backtesting

| Métrica | Descripción |
|---------|-------------|
| Hit rate | Aciertos por ventana |
| ROI | Retorno de inversión simulado |
| Drawdown | Caída máxima acumulada |
| Sharpe ratio | Rentabilidad ajustada a riesgo |

### 7.4 Tablas persistidas

| Tabla | Contenido |
|-------|-----------|
| `bt_snapshot` | Metadatos de versión |
| `bt_result` | Resultados por ventana/estrategia |

---

## 8. Motor de Optimización

**Módulo**: `backend.app.opt`
**API**: `POST /opt/run`, `GET /opt/{lottery_code}/snapshots`
**Snapshot store**: `backend.app.opt.snapshot_store`

### 8.1 Optimizadores disponibles

| Optimizador | Módulo | Algoritmo |
|-------------|--------|-----------|
| Bayesiano | `opt.bayesian` | Gaussian Process (Optuna) |
| Algoritmo Genético | `opt.ga` | Evolución diferencial |
| Enjambre de Partículas | `opt.pso` | PSO |
| Recocido Simulado | `opt.sa` | Simulated Annealing |

### 8.2 Métricas objetivo

| Métrica | Dirección | Descripción |
|---------|-----------|-------------|
| `f1` | maximize | Media armónica precision/recall |
| `roc_auc` | maximize | Área bajo curva ROC |
| `accuracy` | maximize | Precisión global |
| `precision` | maximize | Precisión por clase |
| `recall` | maximize | Exhaustividad |

### 8.3 Espacio de búsqueda

- `opt.search_space`: define rangos de parámetros por optimizador
- Cada optimizador tiene defaults registados en `opt.registry`

### 8.4 Determinismo

- `opt.determinism`: cuantización de métricas
- `opt.fingerprint`: fingerprint del input para idempotencia

### 8.5 Tablas persistidas

| Tabla | Contenido |
|-------|-----------|
| `opt_snapshot` | Metadatos de versión |
| `opt_params` | Mejores parámetros encontrados |
| `opt_metric` | Métricas de la optimización |

---

## 9. Motor de Generadores

**Módulo**: `backend.app.generators`
**API**: `POST /generator/run`, `GET /generator/{lottery_code}/snapshots`
**Snapshot store**: `backend.app.generators.snapshot_store`

### 9.1 Funcionalidad

El motor genera combinaciones de números basadas en reglas de asignación y validación.

| Módulo | Descripción |
|--------|-------------|
| `generators.allocation` | Asignación de números por categoría |
| `generators.sampling` | Muestreo determinista |
| `generators.validation` | Validación de combinaciones generadas |
| `generators.identity` | Identidad de la generación |

### 9.2 Tablas persistidas

| Tabla | Contenido |
|-------|-----------|
| `gen_snapshot` | Metadatos de versión |
| `gen_value` | Combinaciones generadas |

---

## 10. Asistente IA (Rule-Based)

**Módulo**: `backend.app.ai`
**API**: `POST /assistant/chat`
**Tipo**: Determinista, basado en reglas (NO es LLM)

### 10.1 Funciones

| Función | Descripción |
|---------|-------------|
| `build_stats_context` | Contexto de estadísticas para respuesta |
| `build_report_context` | Contexto de reporte |
| `build_summarize_context` | Contexto de resumen |

### 10.2 Características

- **Determinista**: misma entrada → misma salida (fingerprint incluido)
- **Sin LLM**: usa `TextGenerator` (provider de texto) con reglas predefinidas
- **Clasificador de intención**: `_fold()` normaliza preguntas
- **Idioma**: español

### 10.3 Determinismo

- `ai.fingerprint`: fingerprint de la función + inputs
- `ai.version`: versión del motor
- Output: `GenerationResult` (text + engine_version + fingerprint)
