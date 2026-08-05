DATABASE_SCHEMA.md

Lottery Intelligence Platform (LIP)

Database Schema

Versión: 1.0

Estado: Diseño

Motor: SQLite (Compatible con PostgreSQL)

---

1. Objetivos

La base de datos será el núcleo del sistema.

Deberá permitir:

- Almacenar resultados históricos.
- Gestionar múltiples loterías.
- Registrar features calculadas.
- Versionar datasets.
- Administrar modelos.
- Registrar experimentos.
- Ejecutar backtesting.
- Mantener auditoría completa.

---

2. Principios

- Normalización (3NF como base).
- Integridad referencial.
- Auditoría.
- Escalabilidad.
- Compatibilidad con PostgreSQL.
- Sin duplicación innecesaria.

---

3. Diagrama General

Lottery
    │
    ├──────── Draw
    │             │
    │             ├──── DrawNumber
    │             ├──── DrawFeature
    │             ├──── DrawStatistics
    │
Dataset
    │
    ├──── Feature
    ├──── FeatureValue
    │
Model
    │
    ├──── TrainingRun
    ├──── Prediction
    ├──── Backtest
    │
Experiment
    │
    ├──── ExperimentRun
    ├──── Metrics
    │
Generator
    │
    ├──── GeneratedCombination
    ├──── CombinationScore

---

4. Catálogo de Tablas

lottery

Información de cada lotería.

Campos:

- id
- code
- name
- country
- description
- min_number
- max_number
- numbers_to_select
- super_number_min
- super_number_max
- created_at

---

draw

Cada sorteo.

Campos:

- id
- lottery_id
- draw_number
- draw_date
- jackpot
- winners
- created_at

---

draw_numbers

Números ganadores.

Campos:

- id
- draw_id
- position
- number

---

super_number

Superbalota.

Campos:

- id
- draw_id
- value

---

datasets

Versiones de datasets.

Campos:

- id
- version
- description
- created_at
- checksum

---

dataset_draws

Relación Dataset ↔ Sorteos.

---

feature_definition

Catálogo de features.

Campos:

- id
- code
- name
- category
- description
- version
- enabled

---

feature_value

Valor calculado para cada feature.

Campos:

- id
- draw_id
- feature_id
- value

---

statistics_snapshot

Resumen estadístico precalculado.

---

probability_snapshot

Resultados probabilísticos.

---

graph_metrics

Métricas de teoría de grafos.

---

montecarlo_runs

Simulaciones Monte Carlo.

---

ml_models

Modelos registrados.

Campos:

- id
- name
- family
- framework
- version
- parameters
- created_at

---

model_versions

Versionado de modelos.

---

training_runs

Cada entrenamiento realizado.

Campos:

- id
- model_id
- dataset_id
- started_at
- finished_at
- duration
- status

---

model_metrics

Métricas obtenidas.

Ejemplos:

- precisión
- score
- estabilidad
- robustez

---

predictions

Predicciones históricas generadas.

---

backtests

Ejecuciones de backtesting.

---

backtest_results

Resultados detallados.

---

experiments

Experimentos científicos.

---

experiment_runs

Cada ejecución.

---

experiment_metrics

Resultados del experimento.

---

strategies

Catálogo de estrategias.

---

strategy_results

Resultados obtenidos por estrategia.

---

generated_combinations

Combinaciones generadas.

Campos:

- id
- strategy_id
- created_at

---

generated_numbers

Números de cada combinación.

---

combination_scores

Puntuaciones obtenidas.

---

ai_analysis

Resúmenes y análisis generados por IA.

---

system_configuration

Configuraciones globales.

---

audit_log

Auditoría completa.

---

application_log

Eventos del sistema.

---

scheduler_jobs

Tareas programadas.

---

imports

Historial de importaciones.

---

import_errors

Errores de importación.

---

users (Preparado para futuras versiones)

---

api_keys (Futuro)

---

5. Índices

Crear índices para:

- draw_date
- draw_number
- lottery_id
- feature_id
- model_id
- experiment_id
- dataset_id
- strategy_id

Los índices deberán revisarse periódicamente según el uso.

---

6. Restricciones

- No eliminar sorteos históricos.
- No modificar resultados oficiales.
- Toda modificación deberá registrarse en la auditoría.
- Las claves foráneas deberán mantenerse consistentes.

---

7. Versionado

Todo elemento relevante tendrá control de versión:

- Dataset.
- Feature.
- Modelo.
- Estrategia.
- Experimento.

---

8. Auditoría

Registrar:

- Usuario (si aplica).
- Fecha.
- Acción.
- Entidad.
- Valor anterior.
- Valor nuevo.

---

9. Escalabilidad

El diseño permitirá:

- Incorporar nuevas loterías.
- Agregar nuevas features.
- Añadir nuevos modelos.
- Registrar nuevos experimentos.
- Cambiar de SQLite a PostgreSQL con impacto mínimo.

---

10. Convenciones

Nombres

- snake_case
- claves primarias "id"
- claves foráneas "<tabla>_id"

Fechas

- UTC
- ISO 8601

Identificadores

- Enteros autoincrementales para entidades principales.
- UUID opcional para exportación o sincronización futura.

---

11. Flujo de Persistencia

Importación
      │
      ▼
draw
      │
      ▼
feature_value
      │
      ▼
statistics_snapshot
      │
      ▼
training_runs
      │
      ▼
model_metrics
      │
      ▼
backtests
      │
      ▼
generated_combinations

---

12. Objetivo Final

La base de datos deberá actuar como un repositorio científico centralizado, garantizando integridad, trazabilidad y reproducibilidad de todos los análisis, experimentos y resultados generados por Lottery Intelligence Platform.
