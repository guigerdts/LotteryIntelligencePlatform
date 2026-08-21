# Backend — Lottery Intelligence Platform

> API REST para análisis de loterías con motores de estadística, probabilidad,
> machine learning, deep learning, optimización y grafos.

## Inicio rápido

```bash
# Instalar dependencias
uv sync

# Activar entorno
source .venv/bin/activate

# Ejecutar migraciones
alembic upgrade head

# Iniciar servidor
uvicorn backend.app.main:app --reload
```

## Estructura

```
backend/
├── src/backend/app/
│   ├── api/v1/          # Rutas HTTP (14 routers)
│   ├── services/        # Capa de servicio
│   ├── models/          # Modelos SQLAlchemy
│   ├── repositories/    # Acceso a datos
│   ├── statistics/      # Motor de estadísticas
│   ├── probability/     # Motor de probabilidad
│   ├── feature_engineering/  # Motor de features
│   ├── graph/           # Motor de grafo
│   ├── ml/              # Motor de ML
│   ├── dl/              # Motor de DL (sin router)
│   ├── backtesting/     # Motor de backtesting
│   ├── opt/             # Motor de optimización
│   ├── generators/      # Motor de generadores
│   ├── ai/              # Asistente IA (rule-based)
│   ├── meta/            # Meta-selección
│   ├── experiments/     # Experimentos
│   └── config/          # Configuración
├── tests/               # Tests unitarios/integración
├── alembic/             # Migraciones DB
└── pyproject.toml       # Dependencias
```

## CLI `lip`

```bash
lip --help              # Ver todos los comandos
lip lottery list        # Listar loterías
lip statistics generate --lottery-id 1
```

## Tests

```bash
.venv/bin/pytest tests/ -v
```

## Lint

```bash
.venv/bin/ruff check .
```
