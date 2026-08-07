"""Statistics API router: manual generate + on-demand reads (design §5, backend delta).

Strict read/write separation (C5): ``POST /statistics/generate`` is the ONLY
write path — it is idempotent (design §5: an existing active snapshot that would
reproduce the same result is returned, not duplicated). ``GET /statistics/...``
endpoints are reads only and NEVER precompute (STE-10): a missing snapshot
surfaces ``SNAPSHOT_NOT_FOUND`` (404) and an unknown lottery ``RESOURCE_NOT_FOUND``
(404) — both via the global domain handler. All responses use the Fase 0
envelope (REQ-02); the router only parses the request, resolves the lottery code
and delegates to ``StatisticsService`` — no SQL, no business logic here.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from backend.app.repositories.base import get_db
from backend.app.repositories.lottery_repository import LotteryRepository
from backend.app.schemas.envelope import SuccessEnvelope
from backend.app.schemas.statistics import (
    AverageList,
    AverageRow,
    FrequencyList,
    FrequencyRow,
    GapList,
    GapRow,
    GenerateRequest,
    GenerateSnapshot,
)
from backend.app.services.errors import NotFoundError
from backend.app.services.statistics_service import StatisticsService

router = APIRouter(prefix="/statistics", tags=["statistics"])

DbSession = Annotated[Session, Depends(get_db)]


@router.post(
    "/generate",
    response_model=SuccessEnvelope[GenerateSnapshot],
    summary="Generate (or idempotently return) a statistics snapshot",
)
def generate_snapshot(
    payload: GenerateRequest, db: DbSession, response: Response
) -> SuccessEnvelope[GenerateSnapshot]:
    """Trigger snapshot generation on demand; idempotent (design §5).

    Resolves ``lottery_code`` (unknown → 404 ``RESOURCE_NOT_FOUND``), selects the
    metric bundle and scope, and delegates to ``StatisticsService.generate``. When
    an ``active`` snapshot already reproduces the prospective result exactly, the
    existing snapshot is returned with HTTP 200; a new version is written and
    returned with HTTP 201. Unrecoverable engine failure maps to
    ``generation_error`` (500).
    """
    lottery = _resolve_lottery(db, payload.lottery_code)
    metric_set = _resolve_metric_set(payload.metrics)
    previous = _active_snapshot_id(db, lottery.id)
    snapshot = StatisticsService(db).generate(
        lottery_id=lottery.id,
        metric_set=metric_set,
        scope=payload.scope,
    )
    data = GenerateSnapshot(
        snapshot_id=snapshot.id,
        lottery_code=payload.lottery_code,
        version=snapshot.version,
        metric_set=snapshot.metric_set,
        generator_version=snapshot.generator_version,
        draws_from=snapshot.draws_from,
        draws_to=snapshot.draws_to,
        draw_count=snapshot.draw_count,
        checksum=snapshot.checksum,
        incremental=payload.scope == "incremental",
    )
    if snapshot.id != previous:
        response.status_code = status.HTTP_201_CREATED
    return SuccessEnvelope(data=data)


@router.get(
    "/{lottery_code}/frequencies",
    response_model=SuccessEnvelope[FrequencyList],
    summary="Read per-number frequencies from the active snapshot (no precompute)",
)
def read_frequencies(
    lottery_code: str,
    db: DbSession,
    last: Annotated[int, Query(ge=0)] = 0,
) -> SuccessEnvelope[FrequencyList]:
    """Return the frequency distribution from the active snapshot, bounded by ``last``.

    ``last=0`` returns every number; ``last>0`` caps the list. Missing snapshot →
    ``SNAPSHOT_NOT_FOUND`` (404); unknown lottery → ``RESOURCE_NOT_FOUND`` (404).
    No generation is ever triggered (STE-10).
    """
    snapshot, rows = StatisticsService(db).read_frequencies(lottery_code=lottery_code, last=last)
    return SuccessEnvelope(
        data=FrequencyList(
            snapshot_id=snapshot.id,
            lottery_code=lottery_code,
            version=snapshot.version,
            generator_version=snapshot.generator_version,
            draws_from=snapshot.draws_from,
            draws_to=snapshot.draws_to,
            draw_count=snapshot.draw_count,
            checksum=snapshot.checksum,
            frequencies=[FrequencyRow(number=r.number, count=r.count) for r in rows],
        )
    )


@router.get(
    "/{lottery_code}/gaps",
    response_model=SuccessEnvelope[GapList],
    summary="Read per-number gap summaries from the active snapshot (no precompute)",
)
def read_gaps(
    lottery_code: str,
    db: DbSession,
    last: Annotated[int, Query(ge=0)] = 0,
) -> SuccessEnvelope[GapList]:
    """Return per-number gap summaries from the active snapshot, bounded by ``last``."""
    snapshot, rows = StatisticsService(db).read_gaps(lottery_code=lottery_code, last=last)
    return SuccessEnvelope(
        data=GapList(
            snapshot_id=snapshot.id,
            lottery_code=lottery_code,
            version=snapshot.version,
            generator_version=snapshot.generator_version,
            draws_from=snapshot.draws_from,
            draws_to=snapshot.draws_to,
            draw_count=snapshot.draw_count,
            checksum=snapshot.checksum,
            gaps=[
                GapRow(
                    number=r.number,
                    count=r.count,
                    min_gap=r.min_gap,
                    max_gap=r.max_gap,
                    avg_gap=float(r.avg_gap) if r.avg_gap is not None else None,
                )
                for r in rows
            ],
        )
    )


@router.get(
    "/{lottery_code}/averages",
    response_model=SuccessEnvelope[AverageList],
    summary="Read NULL-aware series averages from the active snapshot (no precompute)",
)
def read_averages(lottery_code: str, db: DbSession) -> SuccessEnvelope[AverageList]:
    """Return the jackpot/winners NULL-aware means (D4), from the active snapshot."""
    snapshot, rows = StatisticsService(db).read_averages(lottery_code=lottery_code)
    return SuccessEnvelope(
        data=AverageList(
            snapshot_id=snapshot.id,
            lottery_code=lottery_code,
            version=snapshot.version,
            generator_version=snapshot.generator_version,
            draws_from=snapshot.draws_from,
            draws_to=snapshot.draws_to,
            draw_count=snapshot.draw_count,
            checksum=snapshot.checksum,
            averages={
                r.series_key: AverageRow(
                    mean=float(r.mean) if r.mean is not None else None,
                    non_null_count=r.non_null_count,
                )
                for r in rows
            },
        )
    )


def _resolve_lottery(db: Session, lottery_code: str):
    """Resolve a ``lottery_code`` natural key to its row (404 when unknown, CD-07)."""
    lottery = LotteryRepository(db).get_by_code(lottery_code)
    if lottery is None:
        raise NotFoundError(f"lottery {lottery_code!r} does not exist")
    return lottery


def _resolve_metric_set(metrics: list[str]) -> str:
    """Collapse the ``metrics`` list onto the single supported bundle (``core``).

    The generator supports exactly one metric set this release (design §8); the
    request list is validated by the schema boundary (default ``["core"]``).
    """
    return metrics[0] if metrics else "core"


def _active_snapshot_id(db: Session, lottery_id: int) -> int | None:
    """Return the current active snapshot id for idempotency 200-vs-201 detection."""
    from backend.app.repositories.stat_snapshot_repository import StatSnapshotRepository

    snapshot = StatSnapshotRepository(db).get_active(lottery_id, "core")
    return snapshot.id if snapshot is not None else None
