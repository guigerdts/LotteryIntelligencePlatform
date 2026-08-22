"""Real-path seam coverage: persisted F4 snapshot -> readers -> ML/DL matrices.

The contract tests pin ``ML_FEATURE_ORDER``/``DL_FEATURE_ORDER`` as literal
tuples and the engine unit tests feed synthetic in-memory rows; neither
exercises the actual persistence seam. These tests generate a REAL F4 snapshot
through ``FeatureEngineService`` over a migrated SQLite DB, read its
``feature_values`` rows exactly like the production adapters do, and prove the
matrix/window builders succeed using only what F4 actually persists (finding #9:
the training contracts must equal persistence reality, never demand
mapping-valued features that carry no scalar cell).
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from alembic.config import Config
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from alembic import command
from backend.app.core.db import build_engine
from backend.app.dl.providers import DrawRow
from backend.app.dl.providers import FeatureRow as DlFeatureRow
from backend.app.dl.window import DL_FEATURE_ORDER, build_windows
from backend.app.ml.feature_reader import FeatureValueRow, build_feature_matrix
from backend.app.ml.features import ML_FEATURE_ORDER
from backend.app.models import FeatureValue
from backend.app.services.draw_service import DrawService
from backend.app.services.feature_engine_service import FeatureEngineService
from backend.app.services.lottery_service import LotteryService

ALEMBIC_INI = Path(__file__).resolve().parents[2] / "alembic.ini"


def _fresh_db(tmp_path: Path, name: str) -> Session:
    """Build an independent tmp migrated SQLite DB and return a session on it."""
    db_path = tmp_path / f"{name}.db"
    cfg = Config(str(ALEMBIC_INI))
    cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db_path}")
    command.upgrade(cfg, "head")
    engine = build_engine(f"sqlite:///{db_path}")
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    session = factory()
    session._engine = engine  # keep alive until test ends
    return session


def _seed_and_generate(db: Session, *, draws: int = 12) -> int:
    """Seed one lottery with deterministic draws, generate F4, return snapshot id."""
    lottery_id = (
        LotteryService(db)
        .create(
            {
                "code": "SEAM",
                "name": "Seam Fixture",
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
    service = DrawService(db)
    for draw_number in range(1, draws + 1):
        numbers = [(draw_number + offset) % 45 or 45 for offset in range(4)]
        service.create_draw_bundle(
            lottery_id=lottery_id,
            draw_number=draw_number,
            draw_date=date(2024, 1, draw_number),
            numbers=numbers,
            super_number=None,
            jackpot=None,
            winners=None,
        )
        db.commit()
    return FeatureEngineService(db).generate(lottery_code="SEAM", scope="full").id


def _persisted_rows(db: Session, snapshot_id: int) -> list[FeatureValueRow]:
    """Read ``feature_values`` exactly like the production ML adapters."""
    rows = db.execute(
        select(FeatureValue)
        .where(FeatureValue.snapshot_id == snapshot_id)
        .order_by(FeatureValue.draw_number, FeatureValue.feature_id)
    ).scalars()
    return [
        FeatureValueRow(
            feature_id=row.feature_id, draw_number=row.draw_number, value=float(row.value)
        )
        for row in rows
    ]


def test_ml_matrix_builds_from_persisted_snapshot(tmp_path: Path) -> None:
    """``build_feature_matrix`` succeeds over ONLY what F4 persists (8 columns)."""
    db = _fresh_db(tmp_path, "ml_seam")
    snapshot_id = _seed_and_generate(db)

    rows = _persisted_rows(db, snapshot_id)
    persisted_ids = {row.feature_id for row in rows}
    # Seam invariant: training contract == persistence reality.
    assert persisted_ids == set(ML_FEATURE_ORDER)

    matrix, draw_numbers = build_feature_matrix(rows)
    assert matrix.shape == (12, len(ML_FEATURE_ORDER))
    assert draw_numbers == list(range(1, 13))


def test_dl_windows_build_from_persisted_snapshot(tmp_path: Path) -> None:
    """``build_windows`` succeeds over ONLY what F4 persists (8 columns)."""
    db = _fresh_db(tmp_path, "dl_seam")
    snapshot_id = _seed_and_generate(db)

    rows = db.execute(select(FeatureValue).where(FeatureValue.snapshot_id == snapshot_id)).scalars()
    dl_rows = [
        DlFeatureRow(feature_id=row.feature_id, draw_number=row.draw_number, value=float(row.value))
        for row in rows
    ]
    # The window axis comes from the persisted feature rows themselves;
    # build_windows only consumes ``draw_number`` from the draw list.
    dl_draws = [
        DrawRow(draw_number=n, numbers=()) for n in sorted({r.draw_number for r in dl_rows})
    ]

    windows = build_windows(dl_draws, dl_rows, W=5)
    assert len(windows) == 12 - 5 + 1
    assert windows[-1].draw_number == 12
    assert windows[0].feature_matrix.shape == (5, len(DL_FEATURE_ORDER))


def test_ml_dl_share_identical_persistable_order() -> None:
    """ML and DL contracts stay byte-identical (F12 parity over persistable ids)."""
    assert tuple(DL_FEATURE_ORDER) == tuple(ML_FEATURE_ORDER)
