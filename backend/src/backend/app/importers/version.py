"""Parser engine versioning: identifies the exact CSV interpretation logic (D-G)."""

from __future__ import annotations

# Version of the CSV interpretation logic (column mapping, delimiter, number
# normalization and the Phase A/B rule set). Independent of the running
# application version (``settings.app_version`` / engine version): it is bumped
# only when the parsing/validation contract changes semantics, and it is
# recorded on every import run so any run can be reproduced exactly (IE-06/D-G).
PARSER_VERSION: str = "1.0"


def get_parser_version() -> str:
    """Return the opaque parser version string for the import engine.

    This is a stable, single-sourced constant kept separate from
    ``settings.app_version`` so a parser contract change never couples to an app
    release. There is no database or engine version behind it.
    """
    return PARSER_VERSION
