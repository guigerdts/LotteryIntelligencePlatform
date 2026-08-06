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
├── pyproject.toml          # Dependencias, pytest y ruff (single source)
├── uv.lock                 # Pines reproducibles (REQ-08)
├── src/backend/app/
│   ├── main.py             # App factory FastAPI (create_app)
│   ├── api/v1/router.py    # GET /health, GET /version
│   ├── config/settings.py  # Config centralizada (pydantic-settings)
│   ├── core/               # logging.py, db.py
│   ├── repositories/       # base.py (Base declarativa + sesión)
│   ├── schemas/envelope.py # Envelope {success, data|error, timestamp}
│   └── <motores>/          # Seams vacíos (Fases 3+)
├── tests/                  # test_smoke.py, test_config.py
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

SQLite en `<repo>/database/lip.db`. Solo se crea el archivo vacío y el engine;
la construcción del schema (`Base.metadata.create_all`) **queda para migraciones
de Fase 1**. El dialecto se maneja por URL de configuración (SQLite hoy,
PostgreSQL después como swap config-only).

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
