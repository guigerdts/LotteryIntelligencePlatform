"""Optimization Engine version identity (OE-07).

``OPTIMIZER_GENERATOR_VERSION`` participates in the canonical fingerprint;
changing it invalidates all prior optimization snapshots.
"""

from __future__ import annotations

OPTIMIZER_GENERATOR_VERSION: str = "1.0.0"
