"""ExperimentExporter — JSON and CSV export for experiment data (EXP-006).

Uses only stdlib json + csv (NFR-EXP-08). Accepts pre-built data dicts
from ExpService.export() and returns string content.
"""

from __future__ import annotations

import csv
import io
import json
from typing import Any


class ExperimentExporter:
    """Export experiment data to JSON or CSV format (EXP-006)."""

    @staticmethod
    def export_json(data: dict[str, Any]) -> str:
        """Serialize experiment data to a JSON string.

        ``data`` must contain ``experiment``, ``runs``, and ``comparisons`` keys.
        """
        return json.dumps(data, indent=2, default=str)

    @staticmethod
    def export_csv(runs: list[dict[str, Any]]) -> str:
        """Serialize run data to a CSV string with header row.

        Columns: run_id, run_label, engine_type, engine_snapshot_id,
        engine_fingerprint, notes, created_at.
        """
        fieldnames = [
            "run_id",
            "run_label",
            "engine_type",
            "engine_snapshot_id",
            "engine_fingerprint",
            "notes",
            "created_at",
        ]
        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for run in runs:
            writer.writerow({k: run.get(k, "") for k in fieldnames})
        return buf.getvalue()
