"""Shared fixtures for the Generator surface tests (S3, T-GEN-023..025).

Provides a ``seed_gen_data`` fixture returning a callable that populates the
migrated test DB with the F11/F12/F5 prerequisites a generate() needs:
lottery → ranking → active selection → scored entries → active prob snapshot
with per-number values. Tests override the numeric ranges to exercise
space-exhaustion and distribution edge cases.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, timedelta
from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from backend.app.models.draw import Draw
from backend.app.models.lottery import Lottery
from backend.app.models.meta_ranking import MetaRanking
from backend.app.models.meta_selection import MetaSelection
from backend.app.models.meta_selection_entry import MetaSelectionEntry
from backend.app.models.prob_snapshot import ProbSnapshot
from backend.app.models.prob_value import ProbValue
from backend.app.models.super_number import SuperNumber

SeedResult = dict[str, int]


@pytest.fixture
def seed_gen_data(db: Session) -> Callable[..., SeedResult]:
    """Return a callable that seeds generator prerequisites on the test DB.

    By default also imports ``sb_observations`` draws with SuperBalota values so
    ``GenService`` finds non-empty SB history (R2/GEN_NO_HISTORY); pass
    ``with_sb_history=False`` to exercise the zero-history path.
    """

    def _seed(
        *,
        min_number: int = 1,
        max_number: int = 49,
        numbers_to_select: int = 6,
        super_number_min: int | None = 1,
        super_number_max: int | None = 9,
        scores: tuple[float, ...] = (0.7, 0.3),
        with_distribution: bool = True,
        selection_status: str = "active",
        context: str = "ctx",
        with_sb_history: bool = True,
        sb_observations: int = 32,
        sb_fixed_value: int | None = None,
    ) -> SeedResult:
        lottery = Lottery(
            code=f"GEN-{context}",
            name=f"Generator {context}",
            country="AR",
            min_number=min_number,
            max_number=max_number,
            numbers_to_select=numbers_to_select,
            super_number_min=super_number_min,
            super_number_max=super_number_max,
        )
        db.add(lottery)
        db.flush()

        ranking = MetaRanking(
            lottery_id=lottery.id,
            context_hash=context,
            version="1",
            status="active",
            fingerprint=f"rank_fp_{context}",
        )
        db.add(ranking)
        db.flush()

        selection = MetaSelection(
            lottery_id=lottery.id,
            context_hash=context,
            version="1",
            status=selection_status,
            fingerprint=f"sel_fp_{context}",
        )
        db.add(selection)
        db.flush()

        for rank, score in enumerate(scores, start=1):
            db.add(
                MetaSelectionEntry(
                    selection_id=selection.id,
                    ranking_id=ranking.id,
                    model_id=f"m{rank}",
                    engine_type="backtesting" if rank == 1 else "ml",
                    rank=rank,
                    score=score,
                )
            )
        db.flush()

        if with_sb_history:
            span = (super_number_max or 16) - (super_number_min or 1) + 1
            base = date(2020, 1, 1)
            for i in range(sb_observations):
                draw = Draw(
                    lottery_id=lottery.id,
                    draw_number=i + 1,
                    draw_date=base + timedelta(weeks=i),
                    is_deleted=False,
                )
                db.add(draw)
                db.flush()
                value = (
                    sb_fixed_value
                    if sb_fixed_value is not None
                    else (super_number_min or 1) + (i % span)
                )
                db.add(SuperNumber(draw_id=draw.id, value=value))
            db.flush()

        prob_snapshot_id: int | None = None
        if with_distribution:
            prob = ProbSnapshot(
                lottery_id=lottery.id,
                model_set="core",
                version="1",
                prob_generator_version="1.0.0",
                checksum=f"chk_{context}",
                input_fingerprint=f"pfp_{context}",
                status="active",
                is_locked=True,
                draw_count=0,
                draws_from=0,
                draws_to=0,
            )
            db.add(prob)
            db.flush()
            prob_snapshot_id = prob.id
            db.add_all(
                [
                    ProbValue(
                        snapshot_id=prob.id,
                        model_id="empirical",
                        model_version="1.0.0",
                        subject=str(n),
                        draw_number=None,
                        value=Decimal("0.05"),
                        params_json="{}",
                    )
                    for n in range(min_number, max_number + 1)
                ]
            )
            db.flush()

        db.commit()
        return {
            "lottery_id": lottery.id,
            "ranking_id": ranking.id,
            "selection_id": selection.id,
            "prob_snapshot_id": prob_snapshot_id,
        }

    return _seed
