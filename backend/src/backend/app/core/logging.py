"""Logging bootstrap: stdlib logging with the structured project format."""

from __future__ import annotations

import logging
import sys

# Structured, grep-friendly record format mandated by the project conventions.
LOG_FORMAT = "%(asctime)s|%(levelname)s|%(name)s|%(message)s"


def configure_logging(level: str | int = "INFO") -> None:
    """Configure the root logger for the application, using only the stdlib.

    Sets the record format and level globally (idempotent via ``force=True``).
    Per-module loggers use ``logging.getLogger("backend.app.<module>")`` so names
    mirror package paths, e.g. ``backend.app.api.v1.router``. The level is driven
    by ``settings.logging_level`` at startup.
    """
    logging.basicConfig(level=level, format=LOG_FORMAT, stream=sys.stdout, force=True)
