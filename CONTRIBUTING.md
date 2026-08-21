# Guía de Contribución — Lottery Intelligence Platform

> **Versión**: 1.0 · **Última actualización**: 2026-08-20

---

## 1. Bienvenido

Gracias por tu interés en contribuir a Lottery Intelligence Platform. Este documento
explica el proceso de desarrollo, los estándares de código y el flujo de trabajo.

---

## 2. Configuración del entorno

### 2.1 Requisitos

- Python 3.13+
- Node.js 18+
- uv
- Git

### 2.2 Primeros pasos

```bash
# Clonar
git clone https://github.com/guigerdts/LotteryIntelligencePlatform.git
cd LotteryIntelligencePlatform

# Backend
cd backend && uv sync && source .venv/bin/activate

# Frontend
cd frontend && npm install
```

---

## 3. Flujo de trabajo

### 3.1 Ramas

| Tipo | Nombre | Ejemplo |
|------|--------|---------|
| Feature | `feature/<descripción>` | `feature/add-dark-mode` |
| Fix | `fix/<descripción>` | `fix/null-pointer-statistics` |
| Chore | `chore/<descripción>` | `chore/update-deps` |

### 3.2 Commits

Usar convencional commits:

```
<tipo>(<scope>): <descripción>

Tipos: feat, fix, chore, docs, refactor, test, build, ci
Scope: backend, frontend, api, ml, etc.
```

Ejemplos:
```
feat(backend): add dark mode toggle
fix(statistics): handle null values in frequency calculation
docs(api): update API_SPECIFICATION.md
```

### 3.3 Pull Requests

1. Crear rama desde `main`
2. Hacer cambios con commits convencionales
3. Push y crear PR
4. Esperar review y CI verde
5. Merge (squash o merge commit)

---

## 4. Estándares de código

### 4.1 Backend (Python)

- **Lint**: ruff (`E`, `F`, `I`, `UP`, `B`), line-length 100
- **Format**: `ruff format`
- **Tests**: pytest, cobertura ≥80%
- **Packaging**: src-layout, import path `backend.app`
- **Docstrings**: responsabilidad primero

```bash
# Verificar lint
.venv/bin/ruff check .

# Formatear
.venv/bin/ruff format .

# Ejecutar tests
.venv/bin/pytest tests/ -v
```

### 4.2 Frontend (TypeScript/React)

- **Lint**: ESLint
- **Tests**: Vitest, cobertura ≥70%
- **E2E**: Playwright

```bash
# Verificar lint
npx eslint src/

# Ejecutar tests
npm test -- --run

# E2E
npx playwright test
```

### 4.3 Reglas generales

- **No AI attribution** en commits
- **No secrets** en código
- **No force push** a `main`
- **Documentar** cambios significativos

---

## 5. Flujo SDD (Spec-Driven Development)

Para cambios sustanciales, usar el flujo SDD:

1. **Explorar**: `sdd-explore` — investigar el problema
2. **Proponer**: `sdd-propose` — crear propuesta
3. **Especificar**: `sdd-spec` — escribir specs
4. **Diseñar**: `sdd-design` — diseño técnico
5. **Tareas**: `sdd-tasks` — dividir en tareas
6. **Aplicar**: `sdd-apply` — implementar
7. **Verificar**: `sdd-verify` — validar
8. **Archivar**: `sdd-archive` — cerrar cambio

---

## 6. Review

### 6.1 Presupuesto de review

- **Máximo por PR**: 400 líneas cambiadas
- **Si excede**: dividir en PRs encadenados (stacked PRs)

### 6.2 Checklist

- [ ] Tests pasan
- [ ] Lint limpio
- [ ] Cobertura no baja
- [ ] Docs actualizadas (si aplica)
- [ ] No hay secrets
- [ ] Commits convencionales

---

## 7. Problemas y discusiones

- **Issues**: para bugs y feature requests
- **Discussions**: para preguntas y debate
- **PRs**: para contribuciones concretas

---

## 8. Licencia

El proyecto se distribuye bajo la [MIT License](LICENSE). Copyright (c) 2026 guigerdts.
