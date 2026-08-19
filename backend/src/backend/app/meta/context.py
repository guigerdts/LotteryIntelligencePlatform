"""Context resolution for Meta Learning module.

Resolves context vectors from existing DB columns (META-003) and computes
deterministic SHA-256 context hashes. No artificial features — all variables
exist in current schema.
"""

from __future__ import annotations

import hashlib
import json
from typing import TYPE_CHECKING

from backend.app.meta.types import ContextVector

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


def compute_context_hash(vector: ContextVector) -> str:
    """Compute SHA-256 hex digest from a context vector (META-003).

    Deterministic: same inputs always produce the same hash.
    Includes draws_to for temporal bound enforcement (META-011).
    """
    payload = json.dumps(
        {
            "lottery_id": vector.lottery_id,
            "draws_from": vector.draws_from,
            "draws_to": vector.draws_to,
            "cut": vector.cut,
            "window": vector.window,
            "engine_type": vector.engine_type,
        },
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode()).hexdigest()


def resolve_context_vector(
    lottery_id: int,
    engine_type: str,
    db: Session,
) -> ContextVector:
    """Resolve a context vector from engine snapshots in the database.

    Reads draws_from, draws_to, cut, window from engine snapshots scoped
    to the given lottery_id (META-012, lottery_id isolation). draws_to
    serves as the temporal boundary (META-011, leakage prevention).

    Raises ValueError if no engine snapshots exist for the given lottery.
    """
    # Lazy imports to avoid module-level engine imports (NFR-META-08).
    if engine_type == "backtesting":
        from backend.app.models.bt_snapshot import BtSnapshot

        snapshot = (
            db.query(BtSnapshot)
            .filter(BtSnapshot.lottery_id == lottery_id, BtSnapshot.status == "active")
            .order_by(BtSnapshot.created_at.desc())
            .first()
        )
        if snapshot is None:
            raise ValueError(
                f"No active engine snapshot found for lottery {lottery_id}, engine {engine_type}"
            )
        # bt_snapshots has no draws_from/draws_to columns (migration 0012);
        # the header carries no draw range, so the temporal bound is unbounded.
        return ContextVector(
            lottery_id=lottery_id,
            draws_from=0,
            draws_to=0,
            cut=None,
            window=None,
            engine_type=engine_type,
        )
    elif engine_type == "ml":
        from backend.app.models.ml_snapshot import MlSnapshot

        snapshot = (
            db.query(MlSnapshot)
            .filter(MlSnapshot.lottery_id == lottery_id, MlSnapshot.status == "active")
            .order_by(MlSnapshot.created_at.desc())
            .first()
        )
        if snapshot is None:
            raise ValueError(
                f"No active engine snapshot found for lottery {lottery_id}, engine {engine_type}"
            )
        return ContextVector(
            lottery_id=lottery_id,
            draws_from=snapshot.draws_from,
            draws_to=snapshot.draws_to,
            cut=snapshot.cut,
            window=None,
            engine_type=engine_type,
        )
    elif engine_type == "dl":
        from backend.app.models.dl_snapshot import DlSnapshot

        snapshot = (
            db.query(DlSnapshot)
            .filter(DlSnapshot.lottery_id == lottery_id, DlSnapshot.status == "active")
            .order_by(DlSnapshot.created_at.desc())
            .first()
        )
        if snapshot is None:
            raise ValueError(
                f"No active engine snapshot found for lottery {lottery_id}, engine {engine_type}"
            )
        return ContextVector(
            lottery_id=lottery_id,
            draws_from=snapshot.draws_from,
            draws_to=snapshot.draws_to,
            cut=snapshot.cut,
            window=snapshot.window,
            engine_type=engine_type,
        )
    elif engine_type == "optimization":
        from backend.app.models.opt_snapshot import OptSnapshot

        snapshot = (
            db.query(OptSnapshot)
            .filter(OptSnapshot.lottery_id == lottery_id, OptSnapshot.status == "active")
            .order_by(OptSnapshot.created_at.desc())
            .first()
        )
        if snapshot is None:
            raise ValueError(
                f"No active engine snapshot found for lottery {lottery_id}, engine {engine_type}"
            )
        # opt_snapshots has no draws_from/draws_to columns (migration 0011);
        # the header carries no draw range, so the temporal bound is unbounded.
        return ContextVector(
            lottery_id=lottery_id,
            draws_from=0,
            draws_to=0,
            cut=None,
            window=None,
            engine_type=engine_type,
        )
    else:
        raise ValueError(f"Unknown engine_type: {engine_type}")
