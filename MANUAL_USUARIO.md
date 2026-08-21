# Manual de Usuario — Lottery Intelligence Platform

> **Versión**: 1.0 · **Estado**: Activo · **Última actualización**: 2026-08-20
>
> Guía de uso de la interfaz web y la CLI `lip` para análisis de loterías.

---

## 1. Introducción

### 1.1 ¿Qué es esta plataforma?

Lottery Intelligence Platform (LIP) es una herramienta de análisis de loterías que
combina estadísticas, probabilidad, machine learning, deep learning, optimización y
grafos para proporcionar insights sobre sorteos históricos.

### 1.2 Requisitos previos

- Navegador web moderno (Chrome, Firefox, Safari, Edge)
- Backend ejecutándose en `http://localhost:8000`
- Frontend ejecutándose en `http://localhost:5173`

### 1.3 Navegación

La plataforma usa un layout de dashboard con sidebar izquierda. Cada página tiene
una URL única y se carga de forma lazy (carga bajo demanda).

---

## 2. Página de Inicio (`/`)

**Componente**: `Home`

La página de inicio muestra un resumen general del estado de la plataforma:

- **Loterías disponibles**: lista de loterías cargadas en la base de datos
- **Último sorteo**: fecha y número del sorteo más reciente
- **Estado de motores**: indicadores de qué motores tienen snapshots activos
- **Acciones rápidas**: accesos directos a las funciones principales

### 2.1 Acciones disponibles

| Acción | Descripción |
|--------|-------------|
| Ver historial | Navegar a `/historial` |
| Estadísticas | Navegar a `/estadisticas` |
| Generar combinaciones | Navegar a `/generador` |

---

## 3. Historial (`/historial`)

**Componente**: `History`

Muestra el historial de sorteos de una lotería seleccionada.

### 3.1 Funcionalidades

- **Selección de lotería**: elegir entre las loterías disponibles
- **Tabla de sorteos**: lista cronológica de sorteos con fecha y números
- **Paginación**: navegación por páginas de resultados
- **Filtros**: filtrar por rango de fechas

### 3.2 Columnas de la tabla

| Columna | Descripción |
|---------|-------------|
| Fecha | Fecha del sorteo |
| Números | Números sorteados (main numbers) |
| Super número | Super número (si aplica) |

---

## 4. Estadísticas (`/estadisticas`)

**Componente**: `Statistics`

Análisis estadístico completo de frecuencias, promedios y distribuciones.

### 4.1 Métricas disponibles

| Métrica | Descripción |
|---------|-------------|
| Frecuencia | Veces que cada número ha salido |
| Promedio posicional | Frecuencia por posición en el sorteo |
| Brechas (gaps) | Sorteos entre apariciones de un número |
| Entropía | Aleatoriedad de la distribución |

### 4.2 Generación de snapshots

- **Generar**: crear un nuevo snapshot de estadísticas
- **Historial**: ver snapshots generados previamente
- **Comparar**: comparar métricas entre snapshots

---

## 5. Heatmaps (`/heatmaps`)

**Componente**: `Heatmaps`

Visualización en mapa de calor de frecuencias por posición.

### 5.1 Interpretación

- **Ejes**: números (filas) vs posiciones (columnas)
- **Colores**: intensidad proporcional a la frecuencia
- **Patrones**: busca clusters de alta/baja frecuencia

### 5.2 Controles

- **Rango de fechas**: filtrar sorteos por período
- **Lotería**: seleccionar lotería a analizar
- **Exportar**: descargar imagen del heatmap

---

## 6. Tendencias (`/tendencias`)

**Componente**: `Trends`

Análisis de tendencias temporales de números calientes y fríos.

### 6.1 Métricas de tendencia

| Métrica | Descripción |
|---------|-------------|
| Números calientes | Números con frecuencia creciente |
| Números fríos | Números con frecuencia decreciente |
| Racha | Apariciones consecutivas recientes |
| Estabilidad | Consistencia de la frecuencia en el tiempo |

### 6.2 Visualizaciones

- **Gráfico de líneas**: evolución temporal de frecuencias
- **Tabla de ranking**: números ordenados por tendencia
- **Indicadores**: flechas de dirección (↑ ↓ →)

---

## 7. Redes (`/redes`)

**Componente**: `Networks`

Visualización de grafos de co-ocurrencia entre números.

### 7.1 Conceptos

- **Nodos**: números de la lotería
- **Aristas**: conexión entre números que aparecen juntos
- **Peso**: frecuencia de co-ocurrencia
- **Comunidades**: grupos de números relacionados

### 7.2 Métricas de grafo

| Métrica | Descripción |
|---------|-------------|
| Centralidad de grado | Número de conexiones de un nodo |
| Cercanía | Qué tan cerca está un nodo de todos los demás |
| Intermediación | Cuántos caminos pasan por un nodo |
| Comunidades | Grupos detectados por modularidad |

### 7.3 Controles

- **Tipo de grafo**: co-ocurrencia, correlación
- **Umbral mínimo**: filtro de aristas por peso
- **Layout**: disposición visual del grafo

---

## 8. Monte Carlo (`/monte-carlo`)

**Componente**: `MonteCarlo`

Simulación estocástica para estimar probabilidades de combinaciones.

### 8.1 ¿Qué es Monte Carlo?

Monte Carlo es un método de simulación que usa números aleatorios para estimar
resultados cuando el cálculo exacto es prohibitivamente caro.

### 8.2 Parámetros

| Parámetro | Descripción |
|-----------|-------------|
| Número de simulaciones | Cantidad de iteraciones (default: 10,000) |
| Semilla | Seed para reproducibilidad |
| Lotería | Lotería a simular |

### 8.3 Resultados

- **Distribución estimada**: probabilidad de cada número
- **Intervalo de confianza**: rango de incertidumbre
- **Convergencia**: gráfico de estabilización

---

## 9. Asistente IA (`/ia`)

**Componente**: `IA`

Asistente basado en reglas (no LLM) para responder preguntas sobre datos.

### 9.1 Capacidades

| Función | Descripción |
|---------|-------------|
| Resumen | Resumir estadísticas de una lotería |
| Reporte | Generar reporte detallado |
| Contexto | Proporcionar contexto de datos |

### 9.2 Limitaciones

- **No es un chatbot**: responde solo preguntas sobre datos de lotería
- **Determinista**: misma pregunta → misma respuesta
- **Sin memoria**: no recuerda conversaciones previas

### 9.3 Ejemplos de uso

```
¿Cuáles son los números más frecuentes en Lotería Nacional?
¿Qué tendencia muestra el número 42 en los últimos 30 sorteos?
Genera un reporte de probabilidad para Lotería Federal.
```

---

## 10. Modelos (`/modelos`)

**Componente**: `Models`

Gestión y visualización de modelos de machine learning entrenados.

### 10.1 Modelos disponibles

| Modelo | Tipo | Descripción |
|--------|------|-------------|
| XGBoost | Gradient Boosting | Modelo principal de predicción |
| LightGBM | Gradient Boosting | Alternativa más rápida |
| RandomForest | Ensemble | Bosque aleatorio |

### 10.2 Métricas por modelo

| Métrica | Descripción |
|---------|-------------|
| Accuracy | Precisión global |
| Precision | Precisión por clase positiva |
| Recall | Exhaustividad |
| F1 | Media armónica precision/recall |
| ROC AUC | Área bajo curva ROC |

### 10.3 Acciones

- **Entrenar**: iniciar entrenamiento de un modelo
- **Comparar**: comparar métricas entre modelos
- **Exportar**: descargar modelo entrenado

---

## 11. Experimentos (`/experimentos`)

**Componente**: `Experiments`

Gestión de experimentos comparativos entre motores.

### 11.1 Tipos de experimento

| Tipo | Descripción |
|------|-------------|
| ML vs DL | Comparar machine learning con deep learning |
| Estrategias | Comparar estrategias de predicción |
| Optimización | Comparar algoritmos de optimización |

### 11.2 Métricas de experimento

- **Hit rate**: aciertos por ventana
- **ROI**: retorno de inversión simulado
- **Drawdown**: caída máxima acumulada
- **Sharpe ratio**: rentabilidad ajustada a riesgo

---

## 12. Backtesting (`/backtesting`)

**Componente**: `Backtesting`

Prueba de estrategias sobre datos históricos.

### 12.1 Conceptos

- **Walk-forward**: división temporal train/test
- **Estrategia**: regla de selección de números
- **Benchmark**: comparación con referencia (hipergeométrica, aleatorio)

### 12.2 Configuración

| Parámetro | Descripción |
|-----------|-------------|
| Ventana de entrenamiento | Período para entrenar |
| Ventana de prueba | Período para evaluar |
| Número de ventanas | Cantidad de splits |

### 12.3 Resultados

- **Métricas por ventana**: rendimiento en cada período
- **Métricas agregadas**: resumen global
- **Gráficos**: evolución del rendimiento

---

## 13. Generador (`/generador`)

**Componente**: `Generator`

Generador de combinaciones de números basado en reglas.

### 13.1 Métodos de generación

| Método | Descripción |
|--------|-------------|
| Frecuencia | Basado en frecuencias históricas |
| Balance | Balance entre pares/impares, altos/bajos |
| Patrones | Seguimiento de patrones detectados |
| Aleatorio | Generación aleatoria pesada |

### 13.2 Parámetros

| Parámetro | Descripción |
|-----------|-------------|
| Cantidad | Número de combinaciones a generar |
| Tamaño | Cantidad de números por combinación |
| Método | Algoritmo de generación |
| Filtros | Restricciones adicionales |

---

## 14. Página no encontrada (`*`)

Cuando se accede a una ruta que no existe, la plataforma muestra una página 404
con un mensaje "Page not found" y un estado vacío.

### 14.1 Solución

- Verificar la URL en la barra de direcciones
- Usar la navegación del sidebar
- Volver a la página de inicio (`/`)

---

## 15. CLI `lip` (Avanzado)

La CLI `lip` proporciona acceso de línea de comandos a todas las funcionalidades.

### 15.1 Instalación

```bash
cd backend
uv sync
source .venv/bin/activate
```

### 15.2 Grupos de comandos

| Grupo | Comando | Descripción |
|-------|---------|-------------|
| Loterías | `lip lottery list` | Listar loterías |
| Sorteos | `lip draw list --lottery-id 1` | Listar sorteos |
| Estadísticas | `lip statistics generate --lottery-id 1` | Generar estadísticas |
| Probabilidad | `lip probability generate --lottery-id 1` | Generar probabilidades |
| Features | `lip feature-engine generate --lottery-id 1` | Generar features |
| Grafo | `lip graph generate --lottery-id 1` | Generar grafo |
| ML | `lip ml generate --lottery-id 1` | Generar modelo ML |
| DL | `lip dl generate --lottery-id 1` | Generar modelo DL |
| Backtesting | `lip backtesting run --lottery-id 1` | Ejecutar backtesting |
| Optimización | `lip opt run --lottery-id 1` | Ejecutar optimización |
| Generador | `lip generator run --lottery-id 1` | Generar combinaciones |
| Meta | `lip meta select --lottery-id 1` | Selección meta |

### 15.3 Ejemplos

```bash
# Listar loterías disponibles
lip lottery list

# Generar estadísticas para Lotería Nacional
lip statistics generate --lottery-id 1 --scope full

# Generar probabilidades
lip probability generate --lottery-id 1 --scope incremental

# Ejecutar backtesting
lip backtesting run --lottery-id 1 --windows 10

# Generar combinaciones
lip generator run --lottery-id 1 --count 5 --method frequency
```

### 15.4 Ayuda

```bash
lip --help                  # Ayuda general
lip <grupo> --help          # Ayuda de un grupo
lip <grupo> <comando> --help # Ayuda de un comando específico
```
