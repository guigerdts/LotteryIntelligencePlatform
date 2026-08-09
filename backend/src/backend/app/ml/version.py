"""ML Engine algorithm identity (MLE-05 / design M-A6).

Pinned independently of ``STATS_GENERATOR_VERSION``/``FEATURE_GENERATOR_VERSION``/
``PROB_GENERATOR_VERSION``/``GRAPH_*`` versions: a bump here never follows another
engine's bump. Bump ONLY when an algorithm/params change alters the persisted
output; internal changes that leave output byte-identical do NOT bump. The value
participates in the canonical ``input_fingerprint`` (MLE-05), so any bump forces a
new fingerprint/version — never a silent overwrite.
"""

from __future__ import annotations

from typing import Final

ML_GENERATOR_VERSION: Final[str] = "1.0.0"

__all__ = ["ML_GENERATOR_VERSION"]
