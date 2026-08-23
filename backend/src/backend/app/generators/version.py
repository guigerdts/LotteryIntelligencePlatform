"""Generator version constant — bumped on algorithm changes only (GEN-009).

2.0.0 (D6): SuperBalota sampling joined the numbers' isolated RNG stream
(R2/D1), changing stream consumption — output identity (``generation_seed`` /
``snapshot_fingerprint``) differs from every pre-2.0.0 value.
"""

from __future__ import annotations

GENERATOR_VERSION: str = "2.0.0"
