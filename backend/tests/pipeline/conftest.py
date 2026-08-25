"""Fixtures for the pipeline orchestrator service-layer tests (S2, R1-R4).

Service-layer harness only (no HTTP): a seeded-import SQLite fixture with one
lottery plus ~105 imported draws, stage spies that record start/end events for
every service call in the canonical chain, and helpers to clear per-stage
artifacts (healing matrix) and to count stored snapshot versions (R4).
"""

from __future__ import annotations

import importlib
import os
from collections.abc import Callable, Iterator
from datetime import datetime, timedelta
from typing import Any

import pytest
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from backend.app.models.draw import Draw
from backend.app.models.draw_number import DrawNumber
from backend.app.models.lottery import Lottery
from backend.app.models.super_number import SuperNumber

# Canonical chain order under test (spec R1/R3).
STAGE_ORDER: tuple[str, ...] = (
    "stats",
    "features",
    "gen",
)


def _seed_lottery_with_draws(db: Session) -> int:
    """Insert one lottery plus deterministic draw history; return its id."""
    lottery = Lottery(
        code="PIPE",
        name="Pipeline Fixture",
        country="AR",
        min_number=1,
        max_number=8,
        numbers_to_select=3,
        super_number_min=1,
        super_number_max=5,
    )
    db.add(lottery)
    db.flush()

    from itertools import combinations

    combos = list(combinations(range(1, 9), 3))
    base = datetime(2020, 1, 1, 12, 0, 0)
    # Stride coprime with len(combos) spreads every number evenly across the
    # history so per-number ML targets never collapse to a single class.
    for i in range(105):
        draw = Draw(
            lottery_id=lottery.id,
            draw_number=i + 1,
            draw_date=base + timedelta(weeks=i),
            is_deleted=False,
        )
        db.add(draw)
        db.flush()
        for position, number in enumerate(combos[(i * 97) % len(combos)], start=1):
            db.add(DrawNumber(draw_id=draw.id, position=position, number=number))
        db.add(SuperNumber(draw_id=draw.id, value=(i % 5) + 1))
    db.commit()
    return int(lottery.id)


@pytest.fixture
def pipeline_db(db: Session) -> int:
    """Seed the default lottery + imported draws; yield the lottery id."""
    return _seed_lottery_with_draws(db)


@pytest.fixture
def add_fresh_draw(db: Session) -> Callable[[int, int], None]:
    """Return a callable appending one new imported draw to a lottery."""

    def _add(lottery_id: int, draw_number: int) -> None:
        from itertools import combinations

        combos = list(combinations(range(1, 9), 3))
        draw = Draw(
            lottery_id=lottery_id,
            draw_number=draw_number,
            draw_date=datetime(2022, 1, 1, 12, 0, 0) + timedelta(weeks=draw_number),
            is_deleted=False,
        )
        db.add(draw)
        db.flush()
        for position, number in enumerate(combos[(draw_number * 97) % len(combos)], start=1):
            db.add(DrawNumber(draw_id=draw.id, position=position, number=number))
        db.add(SuperNumber(draw_id=draw.id, value=(draw_number % 5) + 1))
        db.flush()

    return _add


@pytest.fixture
def stage_recorder(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, str]]:
    """Instrument every stage-service entry point; record ("stage","start"/"end")."""
    events: list[tuple[str, str]] = []
    targets: list[tuple[str, str, str, str]] = [
        (
            "backend.app.services.statistics_service",
            "StatisticsService",
            "generate",
            "stats",
        ),
        (
            "backend.app.services.feature_engine_service",
            "FeatureEngineService",
            "generate",
            "features",
        ),
        ("backend.app.services.probability_service", "ProbabilityService", "generate", "features"),
        ("backend.app.services.gen_service", "GenService", "generate", "gen"),
    ]
    for module_name, class_name, method_name, stage in targets:
        cls: Any = getattr(importlib.import_module(module_name), class_name)
        original: Any = getattr(cls, method_name)

        def _wrap(stage: str, original: Any) -> Any:
            def wrapper(*args: Any, **kwargs: Any) -> Any:
                events.append((stage, "start"))
                try:
                    return original(*args, **kwargs)
                finally:
                    events.append((stage, "end"))

            return wrapper

        monkeypatch.setattr(cls, method_name, _wrap(stage, original))
    return events


def clear_stages(db: Session, lottery_id: int, keep: set[str]) -> None:
    """Delete every artifact store NOT listed in *keep* (healing-matrix seeding)."""
    # stage → (children [(model, fk_col)], header models); all children are
    # deleted before their headers so the id-subqueries stay populated.
    specs: list[tuple[str, list[tuple[Any, str]], list[Any]]] = [
        (
            "gen",
            [(_import_model("gen_combination", "GenCombination"), "snapshot_id")],
            [_import_model("gen_snapshot", "GenSnapshot")],
        ),
        (
            "features",
            [
                (_import_model("prob_value", "ProbValue"), "snapshot_id"),
                (_import_model("feature_value", "FeatureValue"), "snapshot_id"),
            ],
            [
                _import_model("prob_snapshot", "ProbSnapshot"),
                _import_model("feature_snapshot", "FeatureSnapshot"),
            ],
        ),
        (
            "stats",
            [
                (_import_model("stat_frequency", "StatFrequency"), "snapshot_id"),
                (_import_model("stat_frequency_position", "StatFrequencyPosition"), "snapshot_id"),
                (_import_model("stat_gap", "StatGap"), "snapshot_id"),
                (_import_model("stat_average", "StatAverage"), "snapshot_id"),
                (_import_model("stat_scalar", "StatScalar"), "snapshot_id"),
            ],
            [_import_model("stat_snapshot", "StatSnapshot")],
        ),
    ]
    for stage, children, parents in specs:
        if stage in keep:
            continue
        parent_ids = [select(p.id).where(p.lottery_id == lottery_id) for p in parents]
        combined = parent_ids[0]
        for extra in parent_ids[1:]:
            combined = combined.union(extra)
        for child, fk in children:
            db.execute(delete(child).where(getattr(child, fk).in_(combined)))
        for p in parents:
            db.execute(delete(p).where(p.lottery_id == lottery_id))
    db.flush()


def _import_model(module_name: str, class_name: str) -> Any:
    """Import and return a model class lazily once env pinning is in place."""
    return getattr(importlib.import_module(f"backend.app.models.{module_name}"), class_name)


def artifact_versions(db: Session, lottery_id: int) -> dict[str, int]:
    """Count stored header rows per stage store (zero-side-effect probe, R4)."""
    from sqlalchemy import func

    headers: list[tuple[str, Any]] = [
        ("stats", _import_model("stat_snapshot", "StatSnapshot")),
        ("features", _import_model("feature_snapshot", "FeatureSnapshot")),
        ("prob", _import_model("prob_snapshot", "ProbSnapshot")),
        ("gen", _import_model("gen_snapshot", "GenSnapshot")),
    ]
    counts: dict[str, int] = {}
    for name, model in headers:
        stmt = select(func.count()).select_from(model).where(model.lottery_id == lottery_id)
        counts[name] = int(db.execute(stmt).scalar())
    return counts


@pytest.fixture
def run_chain(db: Session) -> Iterator[Callable[..., Any]]:
    """Return a callable running PipelineService.run against the shared session."""
    from backend.app.services.pipeline_service import PipelineService

    def _run(lottery_id: int, **kwargs: Any) -> Any:
        return PipelineService(db).run(lottery_id=lottery_id, **kwargs)

    yield _run
