"""Registry isolation gates (GF2, FES-07/FES-08): P2-08 and P2-09.

- **GF2(b)** (P2-08): a ``future-statistics`` feature is declared + versioned but
  produces NO persisted value (FES-08 "declared, never computed, no fake/default").
- **GF2(a)** (P2-09): registering a NEW feature does NOT alter existing features'
  outputs (FES-07) — the existing features' values, and the shared-registry scenario,
  remain identical whether or not the extra feature is present.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from alembic.config import Config
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from alembic import command
from backend.app.core.db import build_engine
from backend.app.feature_engineering.registry import (
    SOURCE_FUTURE_STATISTICS,
    FeatureDefinition,
    FeatureRegistry,
)
from backend.app.models.feature_value import FeatureValue
from backend.app.services.draw_service import DrawService
from backend.app.services.feature_engine_service import (
    FeatureEngineService,
    build_feature_registry,
)
from backend.app.services.lottery_service import LotteryService

ALEMBIC_INI = Path(__file__).resolve().parents[1] / "alembic.ini"


def _fresh_db(tmp_path: Path, name: str) -> Session:
    db_path = tmp_path / f"{name}.db"
    cfg = Config(str(ALEMBIC_INI))
    cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db_path}")
    command.upgrade(cfg, "head")
    engine = build_engine(f"sqlite:///{db_path}")
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    session = factory()
    session._output_engine = engine
    return session


def _seed(db: Session) -> int:
    lottery_id = (
        LotteryService(db)
        .create(
            {
                "code": "ISO",
                "name": "Isolation",
                "country": "AR",
                "min_number": 1,
                "max_number": 45,
                "numbers_to_select": 4,
                "super_number_min": 1,
                "super_number_max": 3,
            }
        )
        .id
    )
    for number in range(1, 7):
        nums = [((number * 2 + offset) % 45) or 45 for offset in range(4)]
        DrawService(db).create_draw_bundle(
            lottery_id=lottery_id,
            draw_number=number,
            draw_date=date(2024, 3, number),
            numbers=nums,
            super_number=None,
            jackpot=None,
            winners=None,
        )
        db.commit()
    return lottery_id


def _values(db: Session, snapshot_id: int) -> dict[str, list[tuple]]:
    rows = db.execute(
        select(FeatureValue)
        .where(FeatureValue.snapshot_id == snapshot_id)
        .order_by(FeatureValue.feature_id, FeatureValue.draw_number)
    ).scalars()
    out: dict[str, list[tuple]] = {}
    for row in rows:
        out.setdefault(row.feature_id, []).append((row.draw_number, str(row.value)))
    return out


# --- GF2(b): future-statistics declared, never persisted (FES-08) ------------


def test_future_statistics_feature_produces_no_persisted_value(tmp_path: Path) -> None:
    """GF2(b): a future-statistics feature stays declared but writes NO rows."""
    db = _fresh_db(tmp_path, "gf2b")
    lottery_id = _seed(db)

    registry = build_feature_registry()
    future = [d for d in registry.definitions().values() if d.source == SOURCE_FUTURE_STATISTICS]
    assert future, "default registry must declare a future-statistics feature."

    snapshot = FeatureEngineService(db, registry=registry).generate(
        lottery_id=lottery_id, scope="full"
    )
    persisted = _values(db, snapshot.id)
    for definition in future:
        assert definition.id not in persisted, (
            f"future-statistics feature {definition.id!r} must NOT persist a value"
        )
    # At least the core features WERE persisted (so the emptiness is meaningful).
    assert "draw_sum" in persisted


def test_future_statistics_feature_type_is_source_future() -> None:
    """The declared future feature carries source='future-statistics' (FES-08)."""
    registry = build_feature_registry()
    future = [d for d in registry.definitions().values() if d.source == SOURCE_FUTURE_STATISTICS]
    assert len(future) == 1
    assert future[0].id == "draw_correlation"


# --- GF2(a): registering a new feature does NOT alter existing outputs (FES-07) ---


def _registry_with_extra_feature() -> FeatureRegistry:
    """A registry identical to the canonical one plus one extra core feature."""
    registry = build_feature_registry()

    def _extra(ctx) -> int:
        return sum(ctx.draw.numbers) * 1000

    registry.register(
        FeatureDefinition(
            id="extra_test_feature",
            name="Extra Test Feature",
            category="core",
            description="An additional feature not in the canonical set",
            source="core",
            inputs=("numbers",),
            algorithm="scaled-sum",
            params={},
            dependencies=(),
            complexity="O(n)",
            version="1.0.0",
            status="active",
            history=(),
        ),
        _extra,
    )
    return registry


def test_registering_new_feature_does_not_alter_existing_outputs(tmp_path: Path) -> None:
    """GF2(a): adding a feature leaves existing features' values byte-identical."""
    db1 = _fresh_db(tmp_path, "gf2a_base")
    l1 = _seed(db1)
    base = FeatureEngineService(db1, registry=build_feature_registry()).generate(
        lottery_id=l1, scope="full"
    )
    base_values = _values(db1, base.id)

    db2 = _fresh_db(tmp_path, "gf2a_extra")
    l2 = _seed(db2)
    extra = FeatureEngineService(db2, registry=_registry_with_extra_feature()).generate(
        lottery_id=l2, scope="full"
    )
    extra_values = _values(db2, extra.id)

    # The extra feature is present in the extended feed.
    assert "extra_test_feature" in extra_values

    # Every shared (existing) feature is byte-identical across both registries.
    for feature_id in set(base_values) & set(extra_values):
        assert base_values[feature_id] == extra_values[feature_id], feature_id

    # The extra feature is the ONLY difference.
    assert set(extra_values) - set(base_values) == {"extra_test_feature"}
