"""FeatureValue repository: batched draw reads + deterministic payload bulk insert (P2-03).

Mirrors ``StatPayloadRepository`` (design §3/§9):
1. ``iter_draws`` — the lottery-scoped, keyset-paginated read over
   ``draw JOIN draw_numbers`` in ``BATCH_SIZE`` pages, grouped into per-draw
   ``DrawRow`` in ``ORDER BY draw.draw_number, draw_numbers.id`` order (the FES-05
   determinism contract). It never materializes the full draw set in memory.
2. ``bulk_insert`` — writes one snapshot's ``feature_values`` rows in deterministic
   key order (``feature_id``, then ``draw_number``), so the physical insertion/rowid
   sequence is identical across two independent generations (GF1/FES-05). Payload
   rows are grouped in ``batch_size`` flushes for bounded memory.

Repositories never commit; the service owns the single atomic transaction.
"""

from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from backend.app.feature_engineering.context import DrawRow
from backend.app.models import Draw, DrawNumber
from backend.app.models.feature_value import FeatureValue

# Deterministic read page: process 1_000 draw_number rows at a time (design §3).
BATCH_SIZE = 1_000


class FeatureValueRepository:
    """Persistence primitives for ``feature_values`` payload rows over one DI session."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def iter_draws(
        self, lottery_id: int, *, after_draw_number: int | None = None
    ) -> Iterator[DrawRow]:
        """Stream ``DrawRow`` in key ``OrderBy draw_number, draw_numbers.id`` order.

        Keyset-paginated over ``draw JOIN draw_numbers`` screened by
        ``draw.lottery_id = :id`` and ``draw.is_deleted = 0`` and ordered by
        ``draw.draw_number, draw_numbers.id`` (design §9 / FES-05). ``after_draw_number``
        filters to the incremental delta (``>:n``) with the same deterministic keys.
        Draws whose rows span a page boundary are carried across pages so every
        ``numbers`` list is complete and in position order; memory stays
        ``O(BATCH_SIZE)`` regardless of the total draw count.
        """
        last_draw_number: int | None = None
        last_number_id: int | None = None
        carried_draw_number: int | None = None
        carried_numbers: list[int] = []

        while True:
            stmt = (
                select(Draw.draw_number, DrawNumber.id, DrawNumber.number)
                .join(DrawNumber, DrawNumber.draw_id == Draw.id)
                .where(Draw.lottery_id == lottery_id, Draw.is_deleted.is_(False))
                .order_by(Draw.draw_number, DrawNumber.id)
                .limit(BATCH_SIZE)
            )
            if after_draw_number is not None:
                stmt = stmt.where(Draw.draw_number > after_draw_number)
            if last_draw_number is not None and last_number_id is not None:
                stmt = stmt.where(
                    or_(
                        Draw.draw_number > last_draw_number,
                        (Draw.draw_number == last_draw_number) & (DrawNumber.id > last_number_id),
                    )
                )

            rows = [(dn, nid, num) for (dn, nid, num) in self._session.execute(stmt).all()]
            if not rows:
                if carried_draw_number is not None:
                    yield DrawRow(draw_number=carried_draw_number, numbers=tuple(carried_numbers))
                return

            for draw_number, _nid, number in rows:
                if carried_draw_number is not None and draw_number == carried_draw_number:
                    carried_numbers.append(number)
                    continue
                if carried_draw_number is not None:
                    yield DrawRow(draw_number=carried_draw_number, numbers=tuple(carried_numbers))
                carried_draw_number = draw_number
                carried_numbers = [number]

            last_draw_number = rows[-1][0]
            last_number_id = rows[-1][1]

    def bulk_insert(
        self,
        snapshot_id: int,
        *,
        rows: list[tuple[str, str, int, object]],
        batch_size: int = BATCH_SIZE,
    ) -> None:
        """Insert all ``feature_values`` payload rows for a snapshot in deterministic order.

        ``rows`` is the already deterministic sequence of
        ``(feature_id, feature_version, draw_number, value)`` tuples — produced by the
        service in ``(feature_id, draw_number)`` key order so the physical insertion
        order (and therefore the ordersize across two generators) is identical (GF1,
        design §9). Rows are flushed in ``batch_size`` groups for bounded memory.
        """
        payload_rows = [
            FeatureValue(
                snapshot_id=snapshot_id,
                feature_id=feature_id,
                feature_version=feature_version,
                draw_number=draw_number,
                value=value,
            )
            for (feature_id, feature_version, draw_number, value) in rows
        ]
        for index in range(0, len(payload_rows), batch_size):
            self._session.add_all(payload_rows[index : index + batch_size])
            self._session.flush()

    def values_for_snapshot(
        self,
        snapshot_id: int,
        *,
        feature: str | None = None,
        last: int = 0,
    ) -> list[FeatureValue]:
        """Read one snapshot's payload rows in deterministic order (FES-05/09 reads).

        ``ORDER BY feature_id, draw_number`` — the same key order ``bulk_insert``
        wrote them in — so every read returns the byte-stable sequence the checksum
        covers (GF1). ``feature`` filters to a single ``feature_id`` and ``last>0``
        caps the list (``0`` = unbounded). Reads answer from stored ``feature_*``
        only; generation is never triggered here (FES-09).
        """
        stmt = (
            select(FeatureValue)
            .where(FeatureValue.snapshot_id == snapshot_id)
            .order_by(FeatureValue.feature_id, FeatureValue.draw_number)
        )
        if feature is not None:
            stmt = stmt.where(FeatureValue.feature_id == feature)
        rows = list(self._session.execute(stmt).scalars().all())
        return rows[:last] if last else rows
