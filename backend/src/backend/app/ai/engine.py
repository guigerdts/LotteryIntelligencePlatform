"""Deterministic rule-based AI engine: five functions + intent classifier (A-06..A-10)."""

from __future__ import annotations

import unicodedata
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from backend.app.ai.fingerprint import compute_ai_fingerprint
from backend.app.ai.generators import (
    build_report_context,
    build_stats_context,
    build_summarize_context,
)
from backend.app.ai.providers import TextGenerator
from backend.app.ai.version import AI_GENERATOR_VERSION


@dataclass(frozen=True)
class GenerationResult:
    """One deterministic output: rendered Spanish text + engine identity (A-02)."""

    text: str
    engine_version: str
    fingerprint: str


def _generate(
    function: str, inputs: Mapping[str, Any], gen: TextGenerator, context: Mapping[str, Any]
) -> GenerationResult:
    return GenerationResult(
        text=gen.generate(function, context),
        engine_version=AI_GENERATOR_VERSION,
        fingerprint=compute_ai_fingerprint(AI_GENERATOR_VERSION, function, inputs),
    )


def _fold(question: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", question.lower()) if not unicodedata.combining(c)
    )


_INTENT_KEYWORDS = (
    ("summarize", ("experiment", "compar", "resum", "run ganador")),
    (
        "explain",
        (
            "por que",
            "porque",
            "explica",
            "resultado",
            "frecuencia",
            "entrop",
            "gap",
            "media",
            "promedio",
        ),
    ),
    ("interpret", ("interpret", "grafic", "chart", "significa", "tendencia")),
    ("report", ("report", "informe", "documento")),
)


def classify_intent(question: str) -> str:
    """Ordered first-match keyword intent over the folded question (A-10)."""
    folded = _fold(question)
    for intent, keywords in _INTENT_KEYWORDS:
        if any(keyword in folded for keyword in keywords):
            return intent
    return "unknown"


def explain(inputs: Mapping[str, Any], gen: TextGenerator) -> GenerationResult:
    """Explain a lottery's results from its statistics snapshot (A-06)."""
    return _generate("explain", inputs, gen, build_stats_context(dict(inputs), "explain"))


def interpret(inputs: Mapping[str, Any], gen: TextGenerator) -> GenerationResult:
    """Interpret the data behind the client-side charts (A-07)."""
    return _generate("interpret", inputs, gen, build_stats_context(dict(inputs), "interpret"))


def report(inputs: Mapping[str, Any], gen: TextGenerator) -> GenerationResult:
    """Render a structured markdown-ish plain-text report (A-08)."""
    return _generate("report", inputs, gen, build_report_context(inputs))


def summarize(inputs: Mapping[str, Any], gen: TextGenerator) -> GenerationResult:
    """Summarize an experiment comparison: best run per metric + delta (A-09)."""
    return _generate("summarize", inputs, gen, build_summarize_context(inputs))


def assist(inputs: Mapping[str, Any], gen: TextGenerator) -> GenerationResult:
    """Route a free-text question to the matching generator (A-10/A-11)."""
    intent = classify_intent(str(inputs.get("question", "")))
    if intent == "unknown":
        return _generate("assist", inputs, gen, {"empty": True})
    if intent == "summarize":
        if inputs.get("experiment_id") is None:
            return _generate("assist", inputs, gen, {"ask_for_id": True})
        return summarize(
            {
                "experiment_id": inputs["experiment_id"],
                "run_ids": inputs.get("run_ids"),
                "comparison_json": inputs.get("comparison_json"),
            },
            gen,
        )
    sub = {**inputs.get("data", {}), "lottery_code": inputs.get("lottery_code")}
    if intent in ("explain", "interpret"):
        return _generate(intent, sub, gen, build_stats_context(sub, intent))
    return _generate("report", sub, gen, build_report_context(sub))
