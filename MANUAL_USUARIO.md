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
