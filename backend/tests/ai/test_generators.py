"""Golden per function (A-04) + byte-identical + empty-data + assist routing."""

from __future__ import annotations

import json
from decimal import Decimal

from backend.app.ai.engine import assist, explain, interpret, report, summarize
from backend.app.ai.providers import RuleBasedTextGenerator

GEN = RuleBasedTextGenerator()
STATS = {
    "frequencies": [{"number": 7, "count": 12}, {"number": 2, "count": 3}],
    "gaps": [{"number": 7, "avg": Decimal("9.75")}, {"number": 2, "avg": Decimal("1.5")}],
    "averages": [{"series": "jackpot", "mean": Decimal("5.25")}],
}
EXPLAIN = {
    **STATS,
    "lottery_code": "ISO",
    "scalars": [{"name": "entropy", "value": Decimal("4.5")}],
}
PROB = [{"model": "hypergeometric", "subject": "7", "value": Decimal("0.5")}]
REPORT = {**STATS, "lottery_code": "ISO", "probabilities": PROB, "scope": None}
COMPARISON = json.dumps(
    {
        "experiment_id": 42,
        "metric_names": ["accuracy", "f1"],
        "runs": [
            {
                "run_id": 1,
                "run_label": "A",
                "engine_type": "ml",
                "engine_snapshot_id": 1,
                "metrics": {"accuracy": 0.9, "f1": 0.85},
            },
            {
                "run_id": 2,
                "run_label": "B",
                "engine_type": "ml",
                "engine_snapshot_id": 2,
                "metrics": {"accuracy": 0.95, "f1": 0.8},
            },
        ],
    }
)


def test_explain_golden_and_byte_identical() -> None:
    result = explain(EXPLAIN, GEN)
    assert result.text == (
        "Análisis de resultados de ISO: el número más frecuente es 7 (12) y el menos"
        " frecuente es 2 (3). el hueco mayor es 7 (9.75) y el menor es 2 (1.5)."
        " el promedio de jackpot es 5.25. la entropía es 4.5."
    )
    assert result.engine_version == "1.0.0"
    assert len(result.fingerprint) == 64
    again = explain(EXPLAIN, GEN)
    assert (result.text, result.fingerprint) == (again.text, again.fingerprint)


def test_interpret_golden() -> None:
    assert interpret({**STATS, "lottery_code": "ISO", "probabilities": PROB}, GEN).text == (
        "Interpretación de los datos de ISO: las frecuencias van de 3 a 12 apariciones."
        " el hueco mayor es 7 (9.75) y el menor es 2 (1.5). el promedio de jackpot es 5.25."
        " hay 1 fila(s) de probabilidad."
    )


def test_report_golden_and_scope() -> None:
    assert report(REPORT, GEN).text == (
        "Informe de ISO\n## Frecuencias\n- 2: 3\n- 7: 12\n\n## Huecos\n- 2: promedio 1.5\n"
        "- 7: promedio 9.75\n\n## Promedios\n- jackpot: 5.25\n\n## Probabilidades\n"
        "- hypergeometric (7): 0.5"
    )
    assert "## Huecos" not in report({**REPORT, "scope": "frequency"}, GEN).text


def test_summarize_golden() -> None:
    assert summarize({"experiment_id": 42, "comparison_json": COMPARISON}, GEN).text == (
        "Resumen del experimento 42: en accuracy, la mejor corrida es B con 0.95 (delta 0.05); "
        "en f1, la mejor corrida es A con 0.85 (delta 0.05)"
    )


def test_empty_data_is_success_text() -> None:
    assert explain({"lottery_code": "ISO"}, GEN).text == (
        "No hay datos suficientes para explicar los resultados de esta lotería."
    )
    assert report({"lottery_code": "ISO"}, GEN).text == (
        "No hay datos suficientes para generar el informe de esta lotería."
    )
    assert summarize({"experiment_id": 42}, GEN).text == (
        "No hay una comparación disponible para este experimento."
    )


def test_assist_routing() -> None:
    routed = assist(
        {"question": "explícame el resultado", "lottery_code": "ISO", "data": EXPLAIN}, GEN
    )
    assert routed.text == explain(EXPLAIN, GEN).text
    assert assist({"question": "¿qué hay para almorzar?", "lottery_code": "ISO"}, GEN).text == (
        "Puedo explicar resultados, interpretar gráficos, generar informes y resumir experimentos. "
        "Escribe tu pregunta en español para comenzar."
    )
    assert assist({"question": "resumí el experimento", "lottery_code": "ISO"}, GEN).text == (
        "Para resumir un experimento, indica el ID del experimento en tu pregunta."
    )
