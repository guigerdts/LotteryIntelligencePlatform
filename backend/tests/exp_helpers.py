"""Shared seed helpers for exp domain tests (EXP-001/003/005)."""

from __future__ import annotations

from backend.app.models.lottery import Lottery
from backend.app.models.ml_snapshot import MlSnapshot
from backend.app.models.opt_snapshot import OptSnapshot

ML_FP = "in" + "f" * 62
_BASE = dict(
    lottery_id=1,
    model_set="default",
    version="1",
    checksum="c" * 64,
    input_fingerprint=ML_FP,
    cut=10,
    status="active",
    is_locked=False,
    draw_count=100,
    draws_from=1,
    draws_to=100,
)


def seed_lottery(db) -> Lottery:
    lottery = Lottery(
        id=1,
        code="TEST",
        name="Test Lottery",
        country="US",
        min_number=1,
        max_number=50,
        numbers_to_select=5,
    )
    db.add(lottery)
    db.commit()
    return lottery


def seed_metric_snapshot(db, model, *, window: int | None = None) -> int:
    """Seed MlSnapshot or DlSnapshot; return its id."""
    gen = "ml_generator_version" if model is MlSnapshot else "dl_generator_version"
    kw = {"window": window} if window is not None else {}
    snap = model(**_BASE, **{gen: f"{gen}-1"}, **kw)
    db.add(snap)
    db.flush()
    return snap.id


def create_opt_snapshot(db, *, fingerprint: str = "fp-opt") -> int:
    snap = OptSnapshot(
        lottery_id=1,
        optimizer="ga",
        model_set="default",
        objective_metric="f1",
        objective_direction="maximize",
        algorithm_params="{}",
        search_space="{}",
        termination="fixed",
        termination_params="{}",
        fingerprint=fingerprint,
        version="1",
        status="active",
        is_locked=False,
        draw_count=100,
    )
    db.add(snap)
    db.flush()
    return snap.id
