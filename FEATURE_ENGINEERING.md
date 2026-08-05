FEATURE_ENGINEERING.md

Lottery Intelligence Platform (LIP)

Feature Engineering Specification

Versión: 1.0

Estado: Diseño

---

1. Objetivo

El propósito del Feature Engineering es transformar cada sorteo en un conjunto de variables cuantificables que puedan ser utilizadas por los motores estadísticos, probabilísticos y de Inteligencia Artificial.

Las features constituyen el principal activo analítico del sistema.

Todos los modelos consumirán exclusivamente features; nunca accederán directamente a los datos históricos.

---

2. Principios

Cada feature deberá ser:

- Determinística.
- Reproducible.
- Independiente.
- Documentada.
- Versionada.
- Configurable.
- Calculable de forma incremental.

---

3. Arquitectura

Cada feature será implementada como un módulo independiente.

Feature
│
├── ID
├── Nombre
├── Categoría
├── Descripción
├── Variables de entrada
├── Algoritmo
├── Parámetros
├── Dependencias
├── Complejidad
└── Resultado

---

4. Categorías

El sistema clasificará las features en:

- Estadísticas
- Temporales
- Distribuciones
- Teoría de números
- Probabilidad
- Grafos
- Coocurrencias
- Simulación
- Tendencias
- Machine Learning
- Deep Learning
- Meta Features

---

5. Features Básicas

Grupo A

Por cada número:

- Frecuencia histórica
- Frecuencia últimos 10 sorteos
- Frecuencia últimos 25
- Frecuencia últimos 50
- Frecuencia últimos 100
- Gap actual
- Gap promedio
- Gap máximo
- Gap mínimo
- Edad del número
- Número de apariciones consecutivas

---

6. Features del Sorteo

- Cantidad de pares
- Cantidad de impares
- Cantidad de primos
- Cantidad de Fibonacci
- Cantidad de múltiplos de 3
- Cantidad de múltiplos de 5
- Cantidad de números altos
- Cantidad de números bajos

---

7. Distribuciones

- Suma total
- Media
- Mediana
- Moda
- Rango
- Varianza
- Desviación estándar
- Asimetría
- Curtosis
- Entropía

---

8. Posiciones

Para cada posición:

- Frecuencia
- Media
- Desviación
- Tendencia
- Entropía

---

9. Decenas

Distribución por:

- 1–10
- 11–20
- 21–30
- 31–40
- 41–43

---

10. Relaciones

- Coocurrencias
- Distancias entre números
- Diferencias consecutivas
- Matriz de adyacencia
- Centralidad
- Densidad del grafo

---

11. Series Temporales

- SMA
- EMA
- Momentum
- Tendencia
- Pendiente
- Aceleración
- Volatilidad histórica

---

12. Probabilidad

- Probabilidad empírica
- Probabilidad acumulada
- Probabilidad condicional
- Score Bayesiano
- Score Monte Carlo

---

13. Simulación

Cada simulación almacenará:

- Número de iteraciones
- Frecuencia simulada
- Intervalo de confianza
- Desviación
- Percentiles

---

14. Meta Features

El sistema podrá generar variables derivadas de otras variables.

Ejemplos:

- Promedio de gaps.
- Tendencia del gap.
- Cambio del score.
- Velocidad del cambio.
- Diferencia respecto al promedio histórico.

---

15. IA

Los modelos podrán crear nuevas features automáticamente.

Estas deberán:

- registrarse;
- documentarse;
- evaluarse;
- compararse con las existentes.

Las features generadas automáticamente nunca reemplazarán a las originales sin validación.

---

16. Versionado

Cada feature tendrá:

- ID
- Versión
- Fecha
- Autor
- Estado
- Descripción
- Historial de cambios

---

17. Pipeline

Histórico

↓

Validación

↓

Normalización

↓

Cálculo de Features

↓

Persistencia

↓

Selección

↓

Entrenamiento

↓

Backtesting

↓

Ranking

---

18. Selección de Features

No todas las variables serán utilizadas.

El sistema implementará técnicas como:

- Mutual Information
- Permutation Importance
- SHAP
- Recursive Feature Elimination
- PCA (opcional)
- LASSO
- Árboles de decisión

Las features con baja contribución podrán desactivarse sin eliminarse.

---

19. Registro

Toda feature calculará automáticamente:

- Tiempo de ejecución.
- Memoria consumida.
- Dependencias.
- Errores.
- Última actualización.

---

20. Objetivo Final

Construir un ecosistema extensible de miles de features donde cada nueva variable pueda incorporarse sin modificar la arquitectura principal.

La selección de variables será un proceso continuo basado en evidencia experimental y no en criterios subjetivos.
