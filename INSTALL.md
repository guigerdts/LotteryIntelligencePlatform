# Guía de Instalación — Lottery Intelligence Platform

> **Versión**: 1.0 · **Última actualización**: 2026-08-20

---

## 1. Requisitos previos

| Componente | Versión mínima | Verificar |
|------------|---------------|-----------|
| Python | 3.13+ | `python3 --version` |
| Node.js | 18+ | `node --version` |
| uv | latest | `uv --version` |
| PostgreSQL | 14+ (o SQLite para desarrollo) | `psql --version` |
| Git | 2.30+ | `git --version` |

---

## 2. Clonar el repositorio

```bash
git clone https://github.com/guigerdts/LotteryIntelligencePlatform.git
cd LotteryIntelligencePlatform
```

---

## 3. Backend

### 3.1 Instalar dependencias

```bash
cd backend
uv sync
```

Esto crea el entorno virtual en `backend/.venv` e instala todas las dependencias
incluyendo optuna, torch, deap (para ML/DL/optimización).

### 3.2 Configurar base de datos

Para desarrollo, SQLite es suficiente:

```bash
# No se requiere configuración adicional
# La DB se crea automáticamente en backend/lottery.db
```

Para PostgreSQL:

```bash
export DATABASE_URL="postgresql://user:password@localhost:5432/lottery"
```

### 3.3 Ejecutar migraciones

```bash
cd backend
source .venv/bin/activate
alembic upgrade head
```

Esto aplica todas las migraciones hasta la head `0016_exp_comparisons_run_ids`.

### 3.4 Cargar datos iniciales

```bash
# Cargar loterías y sorteos de ejemplo
lip import --file data/sample_loteries.json
```

### 3.5 Verificar instalación

```bash
# Ejecutar tests
.venv/bin/pytest tests/ -q

# Verificar lint
.venv/bin/ruff check .

# Verificar CLI
.venv/bin/lip --help
```

---

## 4. Frontend

### 4.1 Instalar dependencias

```bash
cd frontend
npm install
```

### 4.2 Verificar instalación

```bash
# Ejecutar tests
npm test -- --run

# Verificar lint
npx eslint src/
```

---

## 5. Ejecutar la plataforma

### 5.1 Backend

```bash
cd backend
source .venv/bin/activate
uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000
```

### 5.2 Frontend

```bash
cd frontend
npm run dev
```

### 5.3 Acceder

- **Frontend**: http://localhost:5173
- **API docs**: http://localhost:8000/docs
- **API raw**: http://localhost:8000/openapi.json

---

## 6. Scripts de utilidad

| Script | Descripción |
|--------|-------------|
| `scripts/run_backend.sh` | Iniciar backend con uvicorn |
| `scripts/init_db.sh` | Inicializar DB + migraciones |
| `scripts/seed_data.sh` | Cargar datos de ejemplo |

---

## 7. CI/CD

La plataforma usa GitHub Actions para CI:

- **ci.yml**: 6-shard matrix, tests + coverage + lint
- **performance.yml**: benchmarks de rendimiento (manual/scheduled)

### 7.1 Cobertura

- Backend: ≥80% (gate report-only con regla de 3 corridas)
- Frontend: ≥70% (gate report-only)

### 7.2 Lint

```bash
# Backend
cd backend && .venv/bin/ruff check .

# Frontend
cd frontend && npx eslint src/
```

---

## 8. Solución de problemas

### 8.1 Errores de importación

```bash
# Asegurar que .venv está activado
source backend/.venv/bin/activate

# Reinstalar dependencias
cd backend && uv sync
```

### 8.2 Errores de base de datos

```bash
# Resetear DB
rm backend/lottery.db
cd backend && alembic upgrade head
```

### 8.3 Tests fallan

```bash
# Ejecutar tests específicos
.venv/bin/pytest tests/meta/ -v

# Verificar entorno
.venv/bin/pip list | grep pytest
```
