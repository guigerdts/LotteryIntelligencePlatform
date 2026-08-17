"""Table-driven intent tests (A-10): ES keywords + unknown fallback."""

from __future__ import annotations

import pytest

from backend.app.ai.engine import classify_intent


@pytest.mark.parametrize(
    ("question", "expected"),
    [
        ("¿por qué sale tanto el 7?", "explain"),
        ("porque el 3 tiene frecuencia alta", "explain"),
        ("explícame el resultado", "explain"),
        ("cuál es la media de apariciones", "explain"),
        ("cual es el promedio del 5", "explain"),
        ("graficá las tendencias", "interpret"),
        ("qué significa ese grafico", "interpret"),
        ("interpreta la tabla", "interpret"),
        ("genera un reporte", "report"),
        ("quiero el informe del día", "report"),
        ("quiero el documento semanal", "report"),
        ("resumí el experimento 42", "summarize"),
        ("compara las corridas", "summarize"),
        ("cuál es el run ganador", "summarize"),
        ("¿qué hay para almorzar?", "unknown"),
        ("", "unknown"),
    ],
)
def test_classify_intent(question: str, expected: str) -> None:
    assert classify_intent(question) == expected
