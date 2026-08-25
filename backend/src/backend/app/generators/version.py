"""Generator version constant — bumped on algorithm changes only (GEN-009).

3.0.0 (GEN-009 remix): dropped the meta prediction-chain ``entry.score`` from
sampling/allocation. Per-number weights are now F5 frequency × cold-coverage
boost (PM-08), computed transparently from draw history. Output identity
(``generation_seed`` / ``snapshot_fingerprint``) differs from every pre-3.0.0
value.
"""

from __future__ import annotations

GENERATOR_VERSION: str = "3.0.0"
