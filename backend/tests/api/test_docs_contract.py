"""Path-parity contract between API_SPECIFICATION.md and live OpenAPI (DOC-001).

Anti-drift guard for the generated API reference: every endpoint documented in
the ``GENERATED-API-REFERENCE`` marker block MUST exist in the OpenAPI schema
(no fiction), and every OpenAPI operation MUST appear in the block (no
omission). Schema-only by design — ``create_app().openapi()`` never touches
the database, so no DB fixtures are required here.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest

from backend.app.main import create_app

_REPO_ROOT = Path(__file__).resolve().parents[3]
_DOC_PATH = _REPO_ROOT / "API_SPECIFICATION.md"
_START_MARKER = "<!-- GENERATED-API-REFERENCE:START -->"
_END_MARKER = "<!-- GENERATED-API-REFERENCE:END -->"
_OPERATION_RE = re.compile(r"^### (?P<method>[A-Z]+) (?P<path>\S+)$", re.MULTILINE)
_BLOCK_RE = re.compile(
    re.escape(_START_MARKER) + r"\n(?P<body>.*?)" + re.escape(_END_MARKER),
    re.DOTALL,
)
_HTTP_METHODS = frozenset({"delete", "get", "patch", "post", "put"})


def _openapi_operations(schema: dict[str, Any]) -> set[str]:
    """Return ``METHOD path`` strings for every HTTP operation in the schema."""
    operations: set[str] = set()
    for path, handlers in schema["paths"].items():
        for method in handlers:
            if method in _HTTP_METHODS:
                operations.add(f"{method.upper()} {path}")
    return operations


@pytest.fixture(scope="module")
def openapi_operations() -> set[str]:
    """Live OpenAPI operations extracted from the real app factory."""
    return _openapi_operations(create_app().openapi())


@pytest.fixture(scope="module")
def documented_operations() -> set[str]:
    """Operations listed inside the generated reference block of the doc."""
    match = _BLOCK_RE.search(_DOC_PATH.read_text(encoding="utf-8"))
    assert match is not None, (
        f"{_DOC_PATH.name} is missing the {_START_MARKER} / {_END_MARKER} block; "
        "run docs/api/generate_reference.py to generate it"
    )
    found = {
        f"{operation['method']} {operation['path']}"
        for operation in _OPERATION_RE.finditer(match.group("body"))
    }
    assert found, "generated reference block parsed zero operations"
    return found


def test_documented_paths_exist_in_openapi(
    documented_operations: set[str], openapi_operations: set[str]
) -> None:
    """No fictional endpoints: every documented path exists in live OpenAPI."""
    fictional = sorted(documented_operations - openapi_operations)
    assert not fictional, f"documented but absent from OpenAPI: {fictional}"


def test_openapi_paths_are_documented(
    openapi_operations: set[str], documented_operations: set[str]
) -> None:
    """No omissions: every OpenAPI operation is present in the doc block."""
    missing = sorted(openapi_operations - documented_operations)
    assert not missing, f"in OpenAPI but undocumented: {missing}"
