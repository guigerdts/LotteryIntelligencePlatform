"""DL Engine algorithm identity (DLE-08 / design D-A6).

Pinned independently of ``ML_GENERATOR_VERSION``/``STATS_GENERATOR_VERSION``/etc.:
a bump here never follows another engine's bump. Bump ONLY when an algorithm/params
change alters the persisted output; internal changes that leave output byte-identical
do NOT bump. The value participates in the canonical ``input_fingerprint`` (DLE-08),
so any bump forces a new fingerprint/version — never a silent overwrite.
"""

from __future__ import annotations

from typing import Final

DL_GENERATOR_VERSION: Final[str] = "1.0.0"

__all__ = ["DL_GENERATOR_VERSION"]
