"""Registry isolation gates (GF2, FES-07/FES-08): P2-08, P2-09, and P3-09.

- **GF2(b)** (P2-08): a ``future-statistics`` feature is declared + versioned but
  produces NO persisted value (FES-08 "declared, never computed, no fake/default").
- **GF2(a)** (P2-09): registering a NEW feature does NOT alter existing features'
  outputs (FES-07) — the existing features' values, and the shared per-registry
  scenario, remain unchanged whether or not the extra feature is present.
- **P3-09** (e2e via the API surface): the same two gates driven through the real
  PR3 surface — ``POST /feature-engine/generate`` + ``GET /{code}/features`` —
  instead of the service layer. A feature registered with the build registry
  seams lands through the surface and adds ONLY its own ``feature_values`` rows;
  the ``future-statistics`` feature stays declared but never appears in the
  surface read of ANY snapshot.
"""

from __future__ import annotations

import io
import json
from contextlib import redirect_stdout
from datetime import date
from pathlib import Path

from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

import backend.app.cli as cli_module
from alembic import command
from backend.app.core.db import build_engine
from backend.app.feature_engineering.registry import (
    SOURCE_FUTURE_STATISTICS,
    FeatureDefinition,
    FeatureRegistry,
)
from backend.app.main import create_app
from backend.app.models.feature_value import FeatureValue
from backend.app.repositories.base import get_db
from backend.app.services.draw_service import DrawService
from backend.app.services.feature_engine_service import (
    FeatureEngineService,
    build_feature_registry,
)
from backend.app.services.lottery_service import LotteryService

ALEMBIC_INI = Path(__file__).resolve().parents[1] / "alembic.ini"


def _fresh_factory(tmp_path: Path, name: str) -> sessionmaker[Session]:
    """A session factory on a tmp migrated SQLite DB (''head'' = 0006 feature_*).

    Keeps the engine alive via the factory's ``bind`` so the SQLite file survives
    for the whole test (GF2 e2e legs need independent, identically-migrated DBs).
    """
    db_path = tmp_path / f"{name}.db"
    cfg = Config(str(ALEMBIC_INI))
    cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db_path}")
    command.upgrade(cfg, "head")
    engine = build_engine(f"sqlite:///{db_path}")
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def _fresh_db(tmp_path: Path, name: str) -> Session:
    """A session on a fresh migrated tmp DB (engine kept alive via ``_output_engine``)."""
    factory = _fresh_factory(tmp_path, name)
    session = factory()
    session._output_engine = factory.kw["bind"]
    return session


def _seed(db: Session) -> int:
    """Seed the ISO lottery with 6 deterministic draws; return its id."""
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
    """Feature -> list of (draw_number, value) rows for a snapshot (ordered)."""
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
        """Compute a scaled-sum probe value: sum of the draw's numbers * 1000."""
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


# --- P3-09: GF2 e2e via the PR3 surface (CLI + API) --------------------------


def _run_cli(argv: list[str], factory: sessionmaker) -> str:
    """Run the CLI against ``factory``-bound sessions; return captured stdout.

    Mirrors the P3-08 helper in ``test_determinism.py`` — the surface layer of
    PR3 is the ``lip feature-engine`` command, so GF2 e2e must drive it through
    exactly that command line, not the service directly.
    """
    original = cli_module.SessionLocal
    cli_module.SessionLocal = factory
    buf = io.StringIO()
    try:
        with redirect_stdout(buf):
            rc = cli_module.main(argv)
    finally:
        cli_module.SessionLocal = original
    assert rc == 0, f"CLI {argv} failed (rc={rc})"
    return buf.getvalue()


def _client_on(factory: sessionmaker) -> TestClient:
    """A TestClient whose ``get_db`` dependency targets the factory's tmp DB."""
    app = create_app()

    def _override():
        """Yield a session from ``factory`` per request (get_db replacement)."""
        session = factory()
        try:
            yield session
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    app.dependency_overrides[get_db] = _override
    return TestClient(app)


def _extra_registry_with_extra_feature() -> FeatureRegistry:
    """The canonical registry plus one extra core feature (GF2(a) delta driver)."""
    registry = build_feature_registry()

    def _extra(ctx) -> int:
        """Compute a scaled-sum probe value: sum of the draw's numbers * 1000."""
        return sum(ctx.draw.numbers) * 1000

    registry.register(
        FeatureDefinition(
            id="surface_extra_feature",
            name="Surface Extra Feature",
            category="core",
            description="Extra feature registered for the GF2(a) e2e delta check",
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


def test_gf2a_e2e_extra_feature_via_cli_only_adds_that_feature(tmp_path: Path, monkeypatch) -> None:
    """GF2(a) e2e (P3-09): registering a new feature lands only its own rows.

    Two twin DBs with identical draws: leg A runs ``lip feature-engine generate``
    with the canonical registry; leg B registers ONE extra core feature and runs
    the same CLI. The persisted delta between the legs must be exactly the extra
    feature's rows — the delta goes through the CLI surface. Service seam: the
    service resolves ``build_feature_registry`` at call time, so monkeypatching
    the module attribute stands in for a deployed registry that ships the new
    feature.
    """
    import backend.app.services.feature_engine_service as fe_service

    factory_a = _fresh_factory(tmp_path, "gf2a_cli_base")
    factory_b = _fresh_factory(tmp_path, "gf2a_cli_extra")
    for factory in (factory_a, factory_b):
        with factory() as db:
            _seed(db)

    leg_a = json.loads(_run_cli(["feature-engine", "generate", "--lottery", "ISO"], factory_a))
    monkeypatch.setattr(fe_service, "build_feature_registry", _extra_registry_with_extra_feature)
    leg_b = json.loads(_run_cli(["feature-engine", "generate", "--lottery", "ISO"], factory_b))

    with factory_a() as a, factory_b() as b:
        base = _values(a, leg_a["snapshot_id"])
        extra = _values(b, leg_b["snapshot_id"])

    # The new feature's rows are the ONLY difference (GF2(a)).
    assert "surface_extra_feature" in extra
    assert set(extra) - set(base) == {"surface_extra_feature"}
    for feature_id in set(base) & set(extra):
        assert base[feature_id] == extra[feature_id], feature_id


def test_gf2b_e2e_future_statistics_produces_no_rows_via_api(tmp_path: Path) -> None:
    """GF2(b) e2e (P3-09): future-statistics declared but NEVER served nor stored.

    Drive the API surface (``POST /generate`` + ``GET /{code}/features``) on a
    fresh DB; the ``future-statistics`` feature id must not appear in the served
    feature list, and no ``feature_values`` row may exist for it — while core
    features ARE served (so the emptiness is meaningful).
    """
    factory = _fresh_factory(tmp_path, "gf2b_surface")
    with factory() as db:
        _seed(db)

    with _client_on(factory) as client:
        resp = client.post("/api/v1/feature-engine/generate", json={"lottery_code": "ISO"})
        assert resp.status_code == 201
        assert resp.json()["data"]["draw_count"] == 6

        served = client.get("/api/v1/feature-engine/ISO/features")
        assert served.status_code == 200
        served_ids = {row["feature_id"] for row in served.json()["data"]["features"]}

    # The one future-statistics feature may never surface a row (FES-08).
    assert "draw_correlation" not in served_ids
    # Core features ARE served — the empty result is not trivially vacuous.
    assert served_ids >= {"draw_sum", "draw_mean", "draw_range"}

    with factory() as db:
        rows = (
            db.execute(select(FeatureValue).where(FeatureValue.feature_id == "draw_correlation"))
            .scalars()
            .all()
        )
        assert rows == []


def test_gf2b_future_statistics_declared_in_default_registry() -> None:
    """The future-statistics feature stays declared (P3-09 baseline sanity)."""
    registry = build_feature_registry()
    future = [d for d in registry.definitions().values() if d.source == SOURCE_FUTURE_STATISTICS]
    assert len(future) == 1
    assert future[0].id == "draw_correlation"  # declared, versioned, never scheduled.
