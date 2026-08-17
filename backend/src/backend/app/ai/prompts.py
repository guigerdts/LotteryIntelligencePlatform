"""Spanish templates and constants for the AI engine (D1). Output is Spanish (es)."""

from __future__ import annotations

AI_ASSISTANT_LOCALE = "es"

EXPLAIN_TEMPLATE = (
    "Análisis de resultados de $lottery:$freq_sentence$gap_sentence$avg_sentence$entropy_sentence"
)
INTERPRET_TEMPLATE = (
    "Interpretación de los datos de $lottery:$freq_sentence$gap_sentence$avg_sentence$prob_sentence"
)
REPORT_TEMPLATE = "Informe de $lottery\n$body"
SUMMARIZE_TEMPLATE = "Resumen del experimento $experiment_id: $best_lines"

TEMPLATES = {
    "explain": EXPLAIN_TEMPLATE,
    "interpret": INTERPRET_TEMPLATE,
    "report": REPORT_TEMPLATE,
    "summarize": SUMMARIZE_TEMPLATE,
}

EXPLAIN_EMPTY = "No hay datos suficientes para explicar los resultados de esta lotería."
INTERPRET_EMPTY = "No hay datos suficientes para interpretar los gráficos de esta lotería."
REPORT_EMPTY = "No hay datos suficientes para generar el informe de esta lotería."
SUMMARIZE_EMPTY = "No hay una comparación disponible para este experimento."

EMPTY_DATA_TEXTS = {
    "explain": EXPLAIN_EMPTY,
    "interpret": INTERPRET_EMPTY,
    "report": REPORT_EMPTY,
    "summarize": SUMMARIZE_EMPTY,
}

CAPABILITIES_TEXT = (
    "Puedo explicar resultados, interpretar gráficos, generar informes y resumir "
    "experimentos. Escribe tu pregunta en español para comenzar."
)
ASSIST_ASK_ID_TEXT = "Para resumir un experimento, indica el ID del experimento en tu pregunta."
