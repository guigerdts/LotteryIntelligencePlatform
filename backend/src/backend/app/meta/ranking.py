"""Ranking computation for Meta Learning module.

Builds sorted ranking entries from scored snapshots using stable sort
(NFR-META-10). Computes SHA-256 fingerprint for idempotency (META-007/009).
"""

from __future__ import annotations

import hashlib
import json

import numpy as np

from backend.app.meta.types import RankingEntry


def build_ranking_entries(scored_snapshots: list[dict]) -> list[RankingEntry]:
    """Build sorted ranking entries from scored snapshots (META-005).

    Sorts by composite score descending using stable sort (NFR-META-10).
    Equal scores preserve insertion order.
    """
    if not scored_snapshots:
        return []

    scores = np.array([s["score"] for s in scored_snapshots])
    # Stable sort, descending: negate scores so highest sorts first
    sorted_indices = np.argsort(-scores, kind="stable")

    entries = []
    for idx in sorted_indices:
        snap = scored_snapshots[idx]
        entries.append(
            RankingEntry(
                model_id=snap["model_id"],
                engine_type=snap["engine_type"],
                score=snap["score"],
                metrics=snap.get("metrics", {}),
            )
        )
    return entries


def compute_fingerprint(lottery_id: int, context_hash: str, entries: list[RankingEntry]) -> str:
    """Compute SHA-256 fingerprint for ranking idempotency (META-007, META-009).

    Fingerprint = SHA-256(json.dumps({"lottery_id": L, "context_hash": H,
    "entries": [{"model_id": M, "score": S}...]}, sort_keys=True)).
    """
    entries_data = sorted(
        [{"model_id": e.model_id, "score": e.score} for e in entries],
        key=lambda x: x["model_id"],
    )
    payload = json.dumps(
        {
            "lottery_id": lottery_id,
            "context_hash": context_hash,
            "entries": entries_data,
        },
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode()).hexdigest()
