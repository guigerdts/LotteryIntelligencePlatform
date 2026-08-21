# Frontend — Lottery Intelligence Platform

> Interfaz web para análisis de loterías con React + TypeScript + Tailwind CSS.

## Inicio rápido

```bash
# Instalar dependencias
npm install

# Iniciar servidor de desarrollo
npm run dev

# Acceder
open http://localhost:5173
```

## Estructura

```
frontend/
├── src/
│   ├── pages/           # 12 páginas + 404
│   ├── components/      # Componentes reutilizables
│   ├── layouts/         # Layouts (DashboardLayout)
│   ├── services/        # API client
│   └── App.tsx          # Configuración de rutas
├── e2e/                 # Tests E2E (Playwright)
└── package.json
```

## Páginas

| Ruta | Componente | Descripción |
|------|------------|-------------|
| `/` | Home | Inicio |
| `/historial` | History | Historial de sorteos |
| `/estadisticas` | Statistics | Estadísticas |
| `/heatmaps` | Heatmaps | Mapas de calor |
| `/tendencias` | Trends | Tendencias |
| `/redes` | Networks | Grafos |
| `/monte-carlo` | MonteCarlo | Simulación |
| `/ia` | IA | Asistente |
| `/modelos` | Models | Modelos ML |
| `/experimentos` | Experiments | Experimentos |
| `/backtesting` | Backtesting | Backtesting |
| `/generador` | Generator | Generador |

## Tests

```bash
npm test -- --run
```

## Lint

```bash
npx eslint src/
```

## E2E

```bash
npx playwright test
```
