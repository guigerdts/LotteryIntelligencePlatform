"""Graph snapshot store (REQ-07, Task 9): lifecycle and persistence.

Implements snapshot store for graph engine, mirroring F3/F5 pattern.
Handles save/load/upsert of graph snapshots and values.

Pattern (A2, D7):
- Save snapshot header + values in single transaction
- Load snapshot by fingerprint
- Upsert: retire old active, create new active
- Empty snapshot handling (no production data required)
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models.graph_snapshot import GraphSnapshot
from backend.app.models.graph_value import GraphValue


def save_snapshot(
    db: Session,
    lottery_id: int,
    graph_type: str,
    version: str,
    generator_version: str,
    checksum: str,
    fingerprint: str,
    params_json: str,
    draw_count: int,
    draws_from: int,
    draws_to: int,
    values: Sequence[tuple[str, str, int | None, Decimal, str]],
) -> GraphSnapshot:
    """Save a graph snapshot with values.

    Args:
        db: Database session.
        lottery_id: Lottery ID.
        graph_type: Graph type (e.g. 'cooccurrence').
        version: Snapshot version.
        generator_version: Engine version.
        checksum: Deterministic checksum.
        fingerprint: Input fingerprint.
        params_json: Frozen params as JSON.
        draw_count: Number of draws used.
        draws_from: First draw number.
        draws_to: Last draw number.
        values: List of (metric_type, subject, draw_number, value, params_json).

    Returns:
        Created GraphSnapshot.
    """
    now = datetime.now(UTC)

    snapshot = GraphSnapshot(
        lottery_id=lottery_id,
        graph_type=graph_type,
        version=version,
        graph_generator_version=generator_version,
        checksum=checksum,
        input_fingerprint=fingerprint,
        params_json=params_json,
        status="active",
        is_locked=False,
        draw_count=draw_count,
        draws_from=draws_from,
        draws_to=draws_to,
        created_at=now,
        updated_at=now,
    )
    db.add(snapshot)
    db.flush()  # Get snapshot.id

    for metric_type, subject, draw_number, value, val_params in values:
        graph_value = GraphValue(
            snapshot_id=snapshot.id,
            metric_type=metric_type,
            subject=subject,
            draw_number=draw_number,
            value=value,
            params_json=val_params,
        )
        db.add(graph_value)

    db.commit()
    db.refresh(snapshot)
    return snapshot


def load_snapshot_by_fingerprint(
    db: Session,
    lottery_id: int,
    graph_type: str,
    fingerprint: str,
) -> GraphSnapshot | None:
    """Load active snapshot by fingerprint.

    Args:
        db: Database session.
        lottery_id: Lottery ID.
        graph_type: Graph type.
        fingerprint: Input fingerprint.

    Returns:
        GraphSnapshot if found, None otherwise.
    """
    stmt = (
        select(GraphSnapshot)
        .where(
            GraphSnapshot.lottery_id == lottery_id,
            GraphSnapshot.graph_type == graph_type,
            GraphSnapshot.input_fingerprint == fingerprint,
            GraphSnapshot.status == "active",
        )
        .limit(1)
    )
    return db.scalar(stmt)


def load_snapshot_values(
    db: Session,
    snapshot_id: int,
) -> list[GraphValue]:
    """Load all values for a snapshot.

    Args:
        db: Database session.
        snapshot_id: Snapshot ID.

    Returns:
        List of GraphValue.
    """
    stmt = (
        select(GraphValue)
        .where(GraphValue.snapshot_id == snapshot_id)
        .order_by(GraphValue.metric_type, GraphValue.subject)
    )
    return list(db.scalars(stmt))


def retire_snapshot(
    db: Session,
    snapshot_id: int,
) -> None:
    """Retire a snapshot (set status to 'retired').

    Args:
        db: Database session.
        snapshot_id: Snapshot ID.
    """
    snapshot = db.get(GraphSnapshot, snapshot_id)
    if snapshot is not None:
        snapshot.status = "retired"
        snapshot.updated_at = datetime.now(UTC)
        db.commit()


def upsert_snapshot(
    db: Session,
    lottery_id: int,
    graph_type: str,
    version: str,
    generator_version: str,
    checksum: str,
    fingerprint: str,
    params_json: str,
    draw_count: int,
    draws_from: int,
    draws_to: int,
    values: Sequence[tuple[str, str, int | None, Decimal, str]],
) -> GraphSnapshot:
    """Upsert: retire old active, create new active.

    Args:
        db: Database session.
        lottery_id: Lottery ID.
        graph_type: Graph type.
        version: Snapshot version.
        generator_version: Engine version.
        checksum: Deterministic checksum.
        fingerprint: Input fingerprint.
        params_json: Frozen params as JSON.
        draw_count: Number of draws used.
        draws_from: First draw number.
        draws_to: Last draw number.
        values: List of (metric_type, subject, draw_number, value, params_json).

    Returns:
        Created GraphSnapshot.
    """
    # Retire existing active snapshot for this (lottery, graph_type)
    existing = _load_active_snapshot(db, lottery_id, graph_type)
    if existing is not None:
        retire_snapshot(db, existing.id)

    return save_snapshot(
        db, lottery_id, graph_type, version, generator_version,
        checksum, fingerprint, params_json, draw_count, draws_from, draws_to, values,
    )


def _load_active_snapshot(
    db: Session,
    lottery_id: int,
    graph_type: str,
) -> GraphSnapshot | None:
    """Load active snapshot by lottery_id and graph_type.

    Args:
        db: Database session.
        lottery_id: Lottery ID.
        graph_type: Graph type.

    Returns:
        GraphSnapshot if found, None otherwise.
    """
    stmt = (
        select(GraphSnapshot)
        .where(
            GraphSnapshot.lottery_id == lottery_id,
            GraphSnapshot.graph_type == graph_type,
            GraphSnapshot.status == "active",
        )
        .limit(1)
    )
    return db.scalar(stmt)
