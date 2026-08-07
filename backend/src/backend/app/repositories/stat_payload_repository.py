"""StatPayload repository: batched draw reads + deterministic payload bulk insert.

Owns two concerns (design §3/§9):
1. ``iter_draws`` — the lottery-scoped, keyset-paginated read over
   ``draw JOIN draw_numbers`` in ``BATCH_SIZE`` pages, grouped into per-draw
   number lists in ``ORDER BY draw.draw_number, draw_numbers.id`` order (the
   determinism contract, design §9). It never materializes the full draw set in
   memory (STE-08/C6): each page is an independent keyset page with
   ``O(BATCH_SIZE)`` memory and a single-row carry buffer for a draw split across
   a page boundary.
2. ``bulk_insert`` — writes one snapshot's payload rows (frequency, positions,
   gaps, averages, scalars) in deterministic sorted order, so the physical
   insertion/rowid sequence is identical across two independent generations
   (G9: insertion-order assertion).

Repositories never commit; the service owns the single atomic transaction.
"""

from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from backend.app.models import Draw, DrawNumber
from backend.app.models.stat_average import StatAverage
from backend.app.models.stat_frequency import StatFrequency
from backend.app.models.stat_frequency_position import StatFrequencyPosition
from backend.app.models.stat_gap import StatGap
from backend.app.models.stat_scalar import StatScalar

# Deterministic read page: process 1_000 draw_number rows at a time (design §3).
BATCH_SIZE = 1_000


class StatPayloadRepository:
    """Persistence primitives for ``stat_*`` payload rows over one DI session."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def iter_draws(
        self, lottery_id: int, *, after_draw_number: int | None = None
    ) -> Iterator[tuple[int, list[int], object, object]]:
        """Stream ``(draw_number, [numbers], jackpot, winners)`` in keyset order.

        Keyset-paginated over ``draw JOIN draw_numbers`` screened by
        ``draw.lottery_id = :id AND draw.is_deleted = 0`` and ordered by
        ``draw.draw_number, draw_numbers.id`` (design §3/§9). ``after_draw_number``
        filters to the incremental delta (``draw_number > :n``, STE-06) with the
        same deterministic keys. Draws whose rows span a page boundary are carried
        across pages, so every ``numbers`` list is complete and in position order;
        ``jackpot``/``winners`` are sampled per draw. Memory stays
        ``O(BATCH_SIZE)`` regardless of the total draw count (STE-08).
        """
        last_draw_number: int | None = None
        last_number_id: int | None = None
        carried_draw_number: int | None = None
        carried_numbers: list[int] = []
        carried_jackpot: object = None
        carried_winners: object = None

        while True:
            stmt = (
                select(
                    Draw.draw_number,
                    DrawNumber.id,
                    DrawNumber.number,
                    Draw.jackpot,
                    Draw.winners,
                )
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

            rows = [
                (dn, nid, num, jack, winners)
                for (dn, nid, num, jack, winners) in self._session.execute(stmt).all()
            ]
            if not rows:
                if carried_draw_number is not None:
                    yield carried_draw_number, carried_numbers, carried_jackpot, carried_winners
                return

            for draw_number, _nid, number, jackpot, winners in rows:
                if carried_draw_number is not None and draw_number == carried_draw_number:
                    carried_numbers.append(number)
                    continue
                if carried_draw_number is not None:
                    yield carried_draw_number, carried_numbers, carried_jackpot, carried_winners
                carried_draw_number = draw_number
                carried_numbers = [number]
                carried_jackpot = jackpot
                carried_winners = winners

            last_draw_number = rows[-1][0]
            last_number_id = rows[-1][1]

    def bulk_insert(
        self,
        snapshot_id: int,
        *,
        frequencies: dict[int, int],
        positions: dict[tuple[int, int], int],
        gaps: dict[int, tuple[int, int | None, int | None, object]],
        averages: dict[str, tuple[object, int]],
        scalars: dict[str, object],
        batch_size: int = BATCH_SIZE,
    ) -> None:
        """Insert all payload rows for a snapshot in deterministic key order.

        Every row set is emitted sorted by its primary-key leading columns
        (``number`` ASC, ``(number, position)`` ASC, ``number`` ASC,
        ``series_key`` ASC, ``name`` ASC), matching the checksum's canonical sort
        so the physical insertion/rowid sequence is identical across two
        independent generations (G9, design §9). Payload rows are grouped in
        ``batch_size`` flushes for bounded memory.
        """
        sections: list[list[object]] = [
            [
                StatFrequency(snapshot_id=snapshot_id, number=number, count=count)
                for number, count in sorted(frequencies.items())
            ],
            [
                StatFrequencyPosition(
                    snapshot_id=snapshot_id, number=number, position=position, count=count
                )
                for (number, position), count in sorted(positions.items())
            ],
            [
                StatGap(
                    snapshot_id=snapshot_id,
                    number=int(number),
                    count=gaps[number][0],
                    min_gap=gaps[number][1],
                    max_gap=gaps[number][2],
                    avg_gap=gaps[number][3],
                )
                for number in sorted(gaps, key=int)
            ],
            [
                StatAverage(
                    snapshot_id=snapshot_id,
                    series_key=key,
                    mean=averages[key][0],
                    non_null_count=averages[key][1],
                )
                for key in sorted(averages)
            ],
            [
                StatScalar(snapshot_id=snapshot_id, name=name, value=value)
                for name, value in sorted(scalars.items())
            ],
        ]
        for section in sections:
            for index in range(0, len(section), batch_size):
                self._session.add_all(section[index : index + batch_size])
                self._session.flush()
