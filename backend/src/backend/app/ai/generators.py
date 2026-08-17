"""Decimal-safe formatting + template context builders (A-03). Never float()."""

from __future__ import annotations

import json
from decimal import Decimal
from typing import Any


def format_decimal(value: Decimal) -> str:
    """Exact fixed-point string via normalize():f (probability precedent)."""
    return f"{value.normalize():f}"


def format_optional(value: Decimal | None) -> str:
    """Decimal, or the documented NULL placeholder 'sin datos' (A-03)."""
    return "sin datos" if value is None else format_decimal(value)


def _rows(inputs: dict[str, Any], key: str) -> list[dict]:
    return list(inputs.get(key, []) or [])


def build_stats_context(inputs: dict[str, Any], mode: str) -> dict[str, Any]:
    """Build the explain/interpret context (``empty`` when there is no data)."""
    f, g, a = _rows(inputs, "frequencies"), _rows(inputs, "gaps"), _rows(inputs, "averages")
    extra = _rows(inputs, "scalars" if mode == "explain" else "probabilities")
    if not (f or g or a or extra):
        return {"empty": True}
    ctx: dict[str, Any] = {"lottery": str(inputs.get("lottery_code", ""))}
    if f:
        hot, cold = max(f, key=lambda r: r["count"]), min(f, key=lambda r: r["count"])
        if mode == "explain":
            ctx["freq_sentence"] = (
                f" el número más frecuente es {hot['number']} ({hot['count']}) y el menos "
                f"frecuente es {cold['number']} ({cold['count']})."
            )
        else:
            counts = [r["count"] for r in f]
            ctx["freq_sentence"] = (
                f" las frecuencias van de {min(counts)} a {max(counts)} apariciones."
            )
    else:
        ctx["freq_sentence"] = ""
    ga = [row for row in g if row.get("avg") is not None]
    if ga:
        high, low = max(ga, key=lambda r: r["avg"]), min(ga, key=lambda r: r["avg"])
        ctx["gap_sentence"] = (
            f" el hueco mayor es {high['number']} ({format_decimal(high['avg'])}) y el menor es "
            f"{low['number']} ({format_decimal(low['avg'])})."
        )
    else:
        ctx["gap_sentence"] = ""
    ctx["avg_sentence"] = (
        f" el promedio de {a[0]['series']} es {format_optional(a[0]['mean'])}." if a else ""
    )
    if mode == "explain":
        entropy = next((x for x in extra if x.get("name") == "entropy"), None)
        ctx["entropy_sentence"] = (
            f" la entropía es {format_decimal(entropy['value'])}." if entropy else ""
        )
    else:
        ctx["prob_sentence"] = f" hay {len(extra)} fila(s) de probabilidad." if extra else ""
    return ctx


def build_report_context(inputs: dict[str, Any]) -> dict[str, Any]:
    """Build the report context for ``inputs['scope']`` (``empty`` when no data)."""
    scope = inputs.get("scope")
    data = {
        "frequency": _rows(inputs, "frequencies"),
        "gap": _rows(inputs, "gaps"),
        "average": _rows(inputs, "averages"),
        "probability": _rows(inputs, "probabilities"),
    }
    sections = (
        [s for s in ("frequency", "gap", "average", "probability") if data[s]]
        if scope is None
        else [scope]
        if data.get(scope)
        else []
    )
    if not sections:
        return {"empty": True}
    blocks: list[str] = []
    if "frequency" in sections:
        lines = "\n".join(
            f"- {r['number']}: {r['count']}"
            for r in sorted(data["frequency"], key=lambda r: r["number"])
        )
        blocks.append(f"## Frecuencias\n{lines}")
    if "gap" in sections:
        lines = "\n".join(
            f"- {r['number']}: promedio {format_optional(r['avg'])}"
            for r in sorted(data["gap"], key=lambda r: r["number"])
        )
        blocks.append(f"## Huecos\n{lines}")
    if "average" in sections:
        lines = "\n".join(
            f"- {r['series']}: {format_optional(r['mean'])}"
            for r in sorted(data["average"], key=lambda r: r["series"])
        )
        blocks.append(f"## Promedios\n{lines}")
    if "probability" in sections:
        lines = "\n".join(
            f"- {r['model']} ({r['subject']}): {format_decimal(r['value'])}"
            for r in sorted(data["probability"], key=lambda r: (r["model"], r["subject"]))
        )
        blocks.append(f"## Probabilidades\n{lines}")
    return {"lottery": str(inputs.get("lottery_code", "")), "body": "\n\n".join(blocks)}


def build_summarize_context(inputs: dict[str, Any]) -> dict[str, Any]:
    """Best run per metric + delta (``empty`` when there is no comparison)."""
    comparison = inputs.get("comparison_json")
    if not comparison:
        return {"empty": True}
    data = json.loads(comparison)
    runs = data.get("runs", [])
    if len(runs) < 2:
        return {"empty": True}
    best_lines: list[str] = []
    for metric in sorted(data.get("metric_names", [])):
        ranked = sorted(
            runs,
            key=lambda r: Decimal(str(r["metrics"].get(metric, 0))),
            reverse=True,
        )
        best, second = ranked[0], ranked[1]
        best_value = Decimal(str(best["metrics"].get(metric, 0)))
        second_value = Decimal(str(second["metrics"].get(metric, 0)))
        best_lines.append(
            f"en {metric}, la mejor corrida es {best['run_label']} con "
            f"{format_decimal(best_value)} (delta {format_decimal(best_value - second_value)})"
        )
    return {"experiment_id": inputs.get("experiment_id"), "best_lines": "; ".join(best_lines)}
