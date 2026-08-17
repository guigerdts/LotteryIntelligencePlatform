"""TextGenerator seam (A-01) + deterministic stdlib rule-based renderer (D1)."""

from __future__ import annotations

import string
from collections.abc import Mapping
from typing import Any, Protocol

from backend.app.ai.prompts import (
    ASSIST_ASK_ID_TEXT,
    CAPABILITIES_TEXT,
    EMPTY_DATA_TEXTS,
    TEMPLATES,
)


class TextGenerator(Protocol):
    """Generation seam: render Spanish text for one engine function (A-01)."""

    def generate(self, function: str, inputs: Mapping[str, Any]) -> str: ...


class RuleBasedTextGenerator:
    """Stdlib renderer over the es template constants (prompts.py)."""

    def generate(self, function: str, inputs: Mapping[str, Any]) -> str:
        if function == "unknown":
            return CAPABILITIES_TEXT
        if function == "assist":
            return ASSIST_ASK_ID_TEXT if inputs.get("ask_for_id") else CAPABILITIES_TEXT
        if inputs.get("empty"):
            return EMPTY_DATA_TEXTS[function]
        return string.Template(TEMPLATES[function]).substitute(inputs)
