"""Graph API router: compute + stored-value reads (REQ-08, D7).

Strict read/write separation: ``POST /graph/compute`` is the ONLY write path —
it is idempotent (a snapshot with matching fingerprint is returned, not duplicated).
``GET /graph/{lottery_code}/snapshots`` and ``GET /graph/{lottery_code}/snapshots/{id}``
are read-only and NEVER precompute. All responses use the Fase 0 envelope (REQ-02).
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from backend.app.repositories.base import get_db
from backend.app.repositories.lottery_repository import LotteryRepository
from backend.app.schemas.envelope import SuccessEnvelope
from backend.app.schemas.graph import (
    ComputeRequest,
    ComputeSnapshot,
    GraphSnapshotList,
    GraphValuesResponse,
)
from backend.app.services.errors import NotFoundError, SnapshotNotFoundError
from backend.app.services.graph_service import GraphService

router = APIRouter(prefix="/graph", tags=["graph"])

DbSession = Annotated[Session, Depends(get_db)]


@router.post(
    "/compute",
    response_model=SuccessEnvelope[ComputeSnapshot],
    summary="Compute a graph snapshot (idempotent)",
)
def compute_snapshot(
    payload: ComputeRequest, db: DbSession, response: Response
) -> SuccessEnvelope[ComputeSnapshot]:
    """Trigger graph computation; idempotent (REQ-08).

    Resolves ``lottery_code`` (unknown -> 404 ``RESOURCE_NOT_FOUND``), delegates
    to ``GraphService.compute``. When an active snapshot reproduces the prospective
    result, the existing snapshot is returned with HTTP 200; a new version is created
    and returned with HTTP 201.
    """
    lottery = _resolve_lottery(db, payload.lottery_code)
    snapshot = GraphService(db).compute(
        lottery_id=lottery.id,
        graph_type=payload.graph_type,
        window=payload.window,
        threshold=payload.threshold,
    )
    data = ComputeSnapshot(
        snapshot_id=snapshot.snapshot.id,
        lottery_code=payload.lottery_code,
        graph_type=snapshot.snapshot.graph_type,
        version=snapshot.snapshot.version,
        generator_version=snapshot.snapshot.graph_generator_version,
        draws_from=snapshot.snapshot.draws_from,
        draws_to=snapshot.snapshot.draws_to,
        draw_count=snapshot.snapshot.draw_count,
        checksum=snapshot.snapshot.checksum,
        fingerprint=snapshot.snapshot.input_fingerprint,
    )
    # New snapshot created (version incremented)
    response.status_code = status.HTTP_201_CREATED
    return SuccessEnvelope(data=data)


@router.get(
    "/{lottery_code}/snapshots",
    response_model=SuccessEnvelope[GraphSnapshotList],
    summary="List graph snapshots for a lottery",
)
def list_snapshots(
    lottery_code: str,
    db: DbSession,
    graph_type: str = Query("cooccurrence", description="Graph type filter"),
) -> SuccessEnvelope[GraphSnapshotList]:
    """List all snapshots for a lottery, filtered by graph type (REQ-08)."""
    lottery = _resolve_lottery(db, lottery_code)

    from sqlalchemy import select

    from backend.app.models.graph_snapshot import GraphSnapshot

    stmt = (
        select(GraphSnapshot)
        .where(
            GraphSnapshot.lottery_id == lottery.id,
            GraphSnapshot.graph_type == graph_type,
        )
        .order_by(GraphSnapshot.version.desc())
    )
    snapshots = db.scalars(stmt).all()
    items = [
        GraphSnapshotList.SnapshotItem(
            snapshot_id=s.id,
            version=s.version,
            status=s.status,
            draw_count=s.draw_count,
            checksum=s.checksum,
            created_at=s.created_at.isoformat() if s.created_at else None,
        )
        for s in snapshots
    ]
    return SuccessEnvelope(data=GraphSnapshotList(snapshots=items))


@router.get(
    "/{lottery_code}/snapshots/{snapshot_id}",
    response_model=SuccessEnvelope[GraphValuesResponse],
    summary="Read graph values from a specific snapshot",
)
def read_snapshot_values(
    lottery_code: str,
    snapshot_id: int,
    db: DbSession,
) -> SuccessEnvelope[GraphValuesResponse]:
    """Read all values for a specific snapshot (REQ-08, no precompute)."""
    lottery = _resolve_lottery(db, lottery_code)

    from sqlalchemy import select

    from backend.app.models.graph_snapshot import GraphSnapshot

    stmt = select(GraphSnapshot).where(
        GraphSnapshot.id == snapshot_id,
        GraphSnapshot.lottery_id == lottery.id,
    )
    snapshot = db.scalar(stmt)
    if snapshot is None:
        raise SnapshotNotFoundError(
            f"snapshot {snapshot_id!r} not found for lottery {lottery_code!r}"
        )

    from backend.app.graph.snapshot_store import load_snapshot_values
    db_values = load_snapshot_values(db, snapshot_id)
    rows = [
        GraphValuesResponse.Row(
            metric_type=v.metric_type,
            subject=v.subject,
            draw_number=v.draw_number,
            value=float(v.value),
        )
        for v in db_values
    ]
    return SuccessEnvelope(data=GraphValuesResponse(rows=rows, count=len(rows)))


def _resolve_lottery(db: Session, code: str) -> object:
    """Resolve a ``lottery_code`` natural key to its lottery record."""
    lottery = LotteryRepository(db).get_by_code(code)
    if lottery is None:
        raise NotFoundError(f"lottery {code!r} does not exist")
    return lottery
