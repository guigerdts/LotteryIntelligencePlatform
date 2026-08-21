"""Generate the API path reference block in ``API_SPECIFICATION.md`` (DOC-001).

Extracts the live OpenAPI schema from the FastAPI application factory and
splices a deterministic markdown reference between the
``GENERATED-API-REFERENCE`` marker blocks. Output is byte-stable, so re-running
the script is idempotent (a second run produces no diff). Run manually from
the repository root:

    backend/.venv/bin/python docs/api/generate_reference.py

The script is intentionally NOT wired into CI (F17 CI surface is frozen);
``backend/tests/api/test_docs_contract.py`` enforces path parity instead.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SRC_PATH = _REPO_ROOT / "backend" / "src"
if str(_SRC_PATH) not in sys.path:
    # Make the src-layout package importable regardless of the invocation
    # directory (precedent: alembic/env.py).
    sys.path.insert(0, str(_SRC_PATH))

from backend.app.main import create_app

DOC_PATH = _REPO_ROOT / "API_SPECIFICATION.md"
START_MARKER = "<!-- GENERATED-API-REFERENCE:START -->"
END_MARKER = "<!-- GENERATED-API-REFERENCE:END -->"
# Sorted HTTP methods; anything else in a path entry (e.g. "parameters") is
# schema metadata, not an operation.
HTTP_METHODS = ("delete", "get", "patch", "post", "put")
_BLOCK_RE = re.compile(
    re.escape(START_MARKER) + r"\n.*?" + re.escape(END_MARKER), re.DOTALL
)


def _schema_type(schema: dict[str, Any]) -> str:
    """Resolve a JSON-schema fragment to a type name or component name."""
    if "type" in schema:
        return str(schema["type"])
    ref = schema.get("$ref", "")
    if ref:
        return str(ref).rsplit("/", maxsplit=1)[-1]
    for candidate in schema.get("anyOf", []):
        resolved = _schema_type(candidate)
        if resolved and resolved != "null":
            return resolved
    return "unknown"


def _format_parameters(operation: dict[str, Any]) -> list[str]:
    """Render the operation parameters as nested markdown bullets."""
    parameters = operation.get("parameters", [])
    if not parameters:
        return []
    lines = ["- Parameters:"]
    for parameter in parameters:
        required = "required" if parameter.get("required") else "optional"
        p_type = _schema_type(parameter.get("schema", {}))
        lines.append(
            f"  - `{parameter.get('name', '?')}` "
            f"({parameter.get('in', '?')}, {required}, {p_type})"
        )
    return lines


def _format_request_body(operation: dict[str, Any]) -> list[str]:
    """Render the request body content type and schema name, if any."""
    content = operation.get("requestBody", {}).get("content", {})
    if not content:
        return []
    media_type = min(content)
    schema = content[media_type].get("schema", {})
    return [f"- Request body: {media_type} — {_schema_type(schema)}"]


def _format_response(operation: dict[str, Any]) -> list[str]:
    """Render the lowest 2xx response code and its schema name."""
    codes = sorted(
        code for code in operation.get("responses", {}) if code.startswith("2")
    )
    if not codes:
        return []
    code = codes[0]
    content = operation["responses"][code].get("content", {})
    schema = content.get(min(content), {}).get("schema", {}) if content else {}
    name = _schema_type(schema) if schema else "(no content)"
    return [f"- Response {code}: {name}"]


def render_reference(schema: dict[str, Any]) -> str:
    """Render the full generated reference body (ends with a newline)."""
    paths = schema.get("paths", {})
    lines: list[str] = []
    for path in sorted(paths):
        handlers = paths[path]
        for method in HTTP_METHODS:
            if method not in handlers:
                continue
            operation = handlers[method]
            lines.append(f"### {method.upper()} {path}")
            lines.append("")
            lines.append(f"- Summary: {operation.get('summary', '-')}")
            tags = operation.get("tags", [])
            if tags:
                lines.append(f"- Tags: {', '.join(tags)}")
            lines.extend(_format_parameters(operation))
            lines.extend(_format_request_body(operation))
            lines.extend(_format_response(operation))
            lines.append("")
    return "\n".join(lines)


def build_block(schema: dict[str, Any]) -> str:
    """Wrap the rendered reference between the marker lines."""
    return f"{START_MARKER}\n{render_reference(schema)}{END_MARKER}"


def splice(doc_text: str, block: str) -> str:
    """Replace the marker block in ``doc_text``, creating one if absent."""
    if _BLOCK_RE.search(doc_text):
        # Lambda replacement keeps backticks/special chars in the block literal.
        return _BLOCK_RE.sub(lambda _: block, doc_text, count=1)
    section = f"\n## Generated API Reference\n\n{block}\n"
    return doc_text.rstrip("\n") + "\n" + section


def main() -> int:
    """Regenerate the reference block; report whether the file changed."""
    schema = create_app().openapi()
    operations = sum(
        1
        for handlers in schema.get("paths", {}).values()
        for method in handlers
        if method in HTTP_METHODS
    )
    original = DOC_PATH.read_text(encoding="utf-8")
    updated = splice(original, build_block(schema))
    changed = updated != original
    if changed:
        DOC_PATH.write_text(updated, encoding="utf-8")
    state = "updated" if changed else "already up to date"
    print(f"API reference {state}: {len(schema['paths'])} paths / {operations} ops")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
